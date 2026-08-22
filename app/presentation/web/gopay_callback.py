"""
FastAPI webhook handler untuk GoPay Custom QRIS via MacroDroid.

Endpoint:
  POST /webhook/gopay/{secret_token} - Menerima notifikasi dari MacroDroid

Flow:
1. MacroDroid intercept notifikasi GoPay Merchant di Android
2. MacroDroid kirim POST request ke endpoint ini dengan teks notifikasi
3. Extract nominal (amount) dari teks via regex
4. Match amount dengan pending order di DB (via OrderService)
5. Jika cocok → mark paid → deliver accounts → notify user & admin
6. Return 200 OK

MacroDroid Setup:
- Trigger: Notification Received → App: GoPay Merchant → Contains: "Rp"
- Action: HTTP Request → POST → URL + Header + Body
- Body: {"pesan": "[notification_text]"}
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from config import settings
from app.application.services.factory import get_order_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Bot instance akan di-inject dari main.py
_bot = None


def set_bot(bot) -> None:
    """Inject bot instance untuk kirim notifikasi ke user."""
    global _bot
    _bot = bot


def _extract_amount(text: str) -> Optional[int]:
    """Extract nominal pembayaran dari teks notifikasi GoPay.

    Patterns yang di-handle:
    - "Pembayaran Rp50.021 berhasil diterima"
    - "Rp 50.021"
    - "Rp50021"
    - "Rp 1.234.567"

    Returns:
        Integer amount (IDR) atau None jika tidak ditemukan.
    """
    match = re.search(r'Rp\.?\s*(\d+(?:\.\d+)*)', text, re.IGNORECASE)
    if not match:
        return None

    amount_str = match.group(1).replace('.', '')
    try:
        return int(amount_str)
    except ValueError:
        return None


@router.post("/webhook/gopay/{secret_token}")
async def gopay_macrodroid_webhook(request: Request, secret_token: str):
    """Handle GoPay payment notification dari MacroDroid."""
    # 1. Verify secret token
    expected_secret = settings.GOPAY_WEBHOOK_SECRET
    if not expected_secret:
        logger.warning("[gopay-webhook] GOPAY_WEBHOOK_SECRET belum di-set!")
        return JSONResponse(content={"status": "error", "message": "Webhook not configured"}, status_code=200)

    if secret_token != expected_secret:
        logger.warning("[gopay-webhook] Invalid secret token: %s", secret_token[:8])
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2. Parse body
    try:
        data = await request.json()
    except Exception as e:
        logger.error("[gopay-webhook] Failed to parse JSON body: %s", e)
        return JSONResponse(content={"status": "error", "message": "Invalid JSON"}, status_code=200)

    notif_text = data.get("pesan", "") or data.get("text", "")
    if not notif_text:
        logger.info("[gopay-webhook] Empty notification text, ignoring")
        return JSONResponse(content={"status": "ignored", "reason": "Empty text"}, status_code=200)

    logger.info("[gopay-webhook] Incoming: %s", notif_text[:200])

    # 3. Extract amount
    amount = _extract_amount(notif_text)
    if amount is None:
        logger.info("[gopay-webhook] No amount pattern found in: %s", notif_text[:100])
        return JSONResponse(content={"status": "ignored", "reason": "No amount pattern found"}, status_code=200)

    logger.info("[gopay-webhook] Extracted amount: Rp %s", f"{amount:,}")

    # 4. Match with pending order via OrderService
    try:
        order_service = await get_order_service()
        order = await order_service.process_gopay_webhook(amount)
    except Exception as e:
        logger.error("[gopay-webhook] process_gopay_webhook error: %s", e, exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=200)

    if order is None:
        logger.info("[gopay-webhook] No pending order matched for amount=%s", amount)
        return JSONResponse(content={"status": "ignored", "reason": f"No pending order for Rp {amount:,}"}, status_code=200)

    # 5. Order matched! Deliver & notify
    logger.info("[gopay-webhook] Order PAID: order_id=%s user=%s amount=%s", order.id, order.user_id, amount)
    await send_gopay_success_notification(order)
    return JSONResponse(content={"status": "success", "order_id": order.id, "amount": amount}, status_code=200)


async def send_gopay_success_notification(order) -> None:
    """Kirim notifikasi sukses dan akun ke user setelah pembayaran GoPay berhasil."""
    if not _bot:
        logger.error("[gopay-webhook] _bot is not set, cannot send notification")
        return

    try:
        # 1. Cleanup flow messages (QRIS pending, konfirmasi, dll)
        try:
            from app.presentation.order_message_tracker import pop as _pop_track
            tracked = _pop_track(str(order.id))
            if tracked:
                chat_id_track, msg_ids_track = tracked
                for mid in msg_ids_track:
                    try:
                        await _bot.delete_message(chat_id=chat_id_track, message_id=mid)
                    except Exception:
                        pass
        except Exception as _e:
            logger.warning("[gopay-webhook] Cleanup flow messages failed: %s", _e)

        # 2. Auto-deliver accounts
        from app.application.services.delivery_service import deliver_accounts
        delivery = await deliver_accounts(
            order_id=order.id,
            product_id=order.product_id,
            quantity=order.quantity,
            user_id=order.user_id,
            variant_id=order.variant_id,
        )

        # 3. Get product name
        from app.infrastructure.database.factory import get_product_repository
        product_repo = await get_product_repository()
        product = await product_repo.get_by_id(order.product_id)
        product_name = product.name if product else "Unknown"

        from datetime import datetime as dt
        now = dt.now().strftime("%d %b %Y pukul %H:%M")

        # 4. PESAN 1: Detail transaksi + account data ke user
        msg1 = (
            f"\u256d\u2500\u2500\u2500 {{ TRANSAKSI SUKSES }} \u2500\u2500\u2500\n"
            f"\u2502\n"
            f"\u2502 Pay ID      : {order.id[:8]}\n"
            f"\u2502 Nama Produk : {product_name}\n"
            f"\u2502 Jumlah Beli : {order.quantity}\n"
            f"\u2502 Total       : Rp {order.total_price:,}\n"
            f"\u2502 Methode Pay : \U0001f7e2 GoPay QRIS\n"
            f"\u2502 Tanggal     : {now}\n"
            f"\u2502\n"
        )

        if delivery.success and delivery.accounts:
            msg1 += f"\u2502 \u2500\u2500 {{ PRODUCT DETAIL }} \u2500\u2500\n\u2502\n"
            for line in delivery.formatted_text.split("\n"):
                msg1 += f"\u2502 {line}\n"
            msg1 += f"\u2502\n"
        else:
            msg1 += (
                f"\u2502 \u2500\u2500 {{ PRODUCT DETAIL }} \u2500\u2500\n"
                f"\u2502\n"
                f"\u2502 \u26a0\ufe0f Akun belum tersedia.\n"
                f"\u2502 Admin akan kirim manual.\n"
                f"\u2502\n"
            )

        msg1 += f"\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"

        await _bot.send_message(chat_id=order.user_id, text=msg1, parse_mode="HTML")

        # 5. PESAN 2: Delivery description (T&C, cara login)
        delivery_desc = ""
        try:
            from app.infrastructure.database.connection import get_pool
            pool = get_pool()
            if pool:
                async with pool.acquire() as conn:
                    if order.variant_id:
                        dd = await conn.fetchval(
                            "SELECT delivery_description FROM product_variants WHERE id = $1",
                            order.variant_id,
                        )
                        if dd:
                            delivery_desc = dd
                    if not delivery_desc:
                        dd = await conn.fetchval(
                            "SELECT delivery_description FROM products WHERE id = $1",
                            order.product_id,
                        )
                        if dd:
                            delivery_desc = dd
        except Exception:
            pass

        if delivery_desc:
            msg2 = (
                f"[ {product_name} ]\n\n"
                f"{delivery_desc}\n\n"
                f"────────────────────\n"
                f"Terimakasih telah berbelanja!"
            )
            await _bot.send_message(chat_id=order.user_id, text=msg2)

        # 6. Notify admin
        try:
            from config.settings import ADMIN_IDS
            from app.infrastructure.database.factory import get_user_repository
            user_repo = await get_user_repository()
            user_data = await user_repo.get_by_id(order.user_id)
            username = user_data.username if user_data and user_data.username else f"id:{order.user_id}"
            now_admin = dt.now().strftime("%d/%m/%Y %H:%M")

            admin_text = (
                f"<b>ORDER PAID (GoPay)</b>\n\n"
                f"Kode     : {order.id[:8]}\n"
                f"Produk   : {product_name}\n"
                f"Jumlah   : {order.quantity}\n"
                f"Total    : Rp {order.total_price:,}\n"
                f"Customer : @{username}\n"
                f"Tanggal  : {now_admin}\n"
            )
            if delivery.success and delivery.accounts:
                admin_text += f"\nAkun terkirim:\n{delivery.formatted_text}\n"
            else:
                admin_text += "\nAkun belum tersedia. Kirim manual ke user."

            for admin_id in ADMIN_IDS:
                if str(admin_id) == str(order.user_id):
                    # Skip sending admin notif if the admin is the one who bought it (to prevent double messages)
                    continue
                try:
                    await _bot.send_message(chat_id=admin_id, text=admin_text, parse_mode="HTML")
                except Exception as e:
                    logger.error("[gopay-webhook] Failed to notify admin %s: %s", admin_id, e)
        except Exception as e:
            logger.error("[gopay-webhook] Failed to send admin notification: %s", e)

        logger.info("[gopay-webhook] Notification sent successfully for order=%s", order.id)

    except Exception as e:
        logger.error("[gopay-webhook] Error in send_gopay_success_notification: %s", e, exc_info=True)
