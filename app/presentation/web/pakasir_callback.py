"""
FastAPI webhook handler untuk Pakasir payment callbacks.

Endpoint:
  POST /webhook/pakasir - Menerima callback dari Pakasir saat payment completed

Flow:
1. Pakasir kirim POST request dengan payment data (JSON body)
2. Verify via Transaction Detail API (Pakasir ga pakai signature)
3. Determine type: deposit atau order payment
4. Process accordingly (add balance / update order + deliver akun)
5. Return 200 OK
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import Request
from config.settings import STORE_CONTACT
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Bot instance di-inject dari main.py (shared dengan callbacks.py)
_bot = None


def set_bot(bot) -> None:
    """Inject bot instance."""
    global _bot
    _bot = bot


async def pakasir_webhook(request: Request):
    """Handle Pakasir payment callback.

    Pakasir mengirim POST dengan body JSON:
    {
      "amount": 22000,
      "order_id": "xxx",
      "project": "er-zft",
      "status": "completed",
      "payment_method": "qris",
      "completed_at": "2024-09-10T08:07:02.819+07:00"
    }
    """
    try:
        body = await request.body()
        data = json.loads(body)

        order_id = data.get("order_id", "")
        status = data.get("status", "")
        amount = data.get("amount", 0)
        payment_method = data.get("payment_method", "")

        logger.info(
            "[pakasir_webhook] 📥 Callback: order_id=%s status=%s amount=%s method=%s",
            order_id, status, amount, payment_method,
        )

        # Only process completed payments
        if status != "completed":
            logger.info("[pakasir_webhook] Status=%s (bukan completed), skip", status)
            return JSONResponse(content={"success": True}, status_code=200)

        # Verify via Pakasir Transaction Detail API
        from app.infrastructure.payment.factory import get_active_provider
        provider = get_active_provider()
        if provider and hasattr(provider, "verify_callback"):
            callback_data = await provider.verify_callback(data)
            if not callback_data:
                logger.warning("[pakasir_webhook] ❌ Verification failed for order_id=%s", order_id)
                return JSONResponse(content={"success": False, "message": "verification failed"}, status_code=200)
        else:
            logger.warning("[pakasir_webhook] No provider for verification, trusting webhook data")

        # Determine type: deposit atau order
        if order_id.startswith("DEP-"):
            await _handle_deposit_callback(order_id, amount)
        else:
            await _handle_order_callback(order_id, amount)

        return JSONResponse(content={"success": True}, status_code=200)

    except Exception as e:
        logger.error("[pakasir_webhook] ❌ Error: %s", str(e), exc_info=True)
        return JSONResponse(content={"success": True}, status_code=200)


async def _handle_deposit_callback(merchant_ref: str, amount: int) -> None:
    """Handle deposit payment callback dari Pakasir."""
    # Parse user_id dari merchant_ref: DEP-{user_id}-{timestamp}
    parts = merchant_ref.split("-")
    if len(parts) < 3:
        logger.error("[pakasir_webhook] Invalid deposit ref: %s", merchant_ref)
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        logger.error("[pakasir_webhook] Cannot parse user_id from: %s", merchant_ref)
        return

    # Process deposit
    from app.application.services.factory import get_deposit_service
    deposit_svc = await get_deposit_service()
    success = await deposit_svc.process_deposit_callback(
        user_id=user_id,
        amount=amount,
        payment_ref=merchant_ref,
    )

    if success and _bot:
        try:
            new_balance = await deposit_svc.get_user_balance(user_id)
            await _bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>DEPOSIT BERHASIL!</b>\n\n"
                    f"• Ref : {merchant_ref}\n"
                    f"• Nominal : Rp {amount:,}\n"
                    f"• Saldo Baru : Rp {new_balance:,}\n\n"
                    f"💰 Saldo telah ditambahkan. Selamat berbelanja!"
                ),
                parse_mode="HTML",
            )
            logger.info("[pakasir_webhook] ✅ Deposit notification sent to user %s", user_id)
        except Exception as e:
            logger.error("[pakasir_webhook] Failed to notify user %s: %s", user_id, e)


async def _handle_order_callback(order_id: str, amount: int) -> None:
    """Handle order payment callback dari Pakasir."""
    # Update order status
    from app.application.services.factory import get_payment_service
    payment_svc = await get_payment_service()
    result = await payment_svc.process_order_payment(
        order_id=order_id,
        status="PAID",
        payment_ref=f"pakasir:{order_id}",
    )

    if not result.success:
        logger.error("[pakasir_webhook] Failed to process order %s: %s", order_id, result.error_message)
        return

    if not _bot:
        logger.warning("[pakasir_webhook] Bot not available for notification")
        return

    try:
        # Cleanup flow messages (same as Tripay webhook)
        try:
            from app.presentation.order_message_tracker import pop as _pop_track
            tracked = _pop_track(order_id)
            if tracked:
                chat_id_track, msg_ids_track = tracked
                for mid in msg_ids_track:
                    try:
                        await _bot.delete_message(chat_id=chat_id_track, message_id=mid)
                    except Exception:
                        pass
        except Exception:
            pass

        # Get order details
        from app.infrastructure.database.factory import (
            get_order_repository,
            get_product_repository,
            get_user_repository,
        )
        order_repo = await get_order_repository()
        product_repo = await get_product_repository()

        order = await order_repo.get_by_id(order_id)
        if not order:
            logger.error("[pakasir_webhook] Order %s not found", order_id)
            return

        product = await product_repo.get_by_id(order.product_id)
        product_name = product.name if product else "Unknown Product"

        # Auto-deliver accounts
        from app.application.services.delivery_service import deliver_accounts
        delivery = await deliver_accounts(
            order_id=order_id,
            product_id=order.product_id,
            quantity=order.quantity,
            user_id=order.user_id,
            variant_id=order.variant_id,
        )

        from datetime import datetime as dt
        now = dt.now().strftime("%d %b %Y pukul %H:%M")

        # PESAN 1: Detail transaksi + account data
        msg1 = (
            f"╭─── {{ TRANSAKSI SUKSES }} ───\n"
            f"│\n"
            f"│ Pay ID : {order_id[:8]}\n"
            f"│ Nama Produk : {product_name}\n"
            f"│ Jumlah Beli : {order.quantity}\n"
            f"│ Total : Rp {order.total_price:,}\n"
            f"│ Methode Pay : QRIS (Pakasir)\n"
            f"│ Tanggal : {now}\n"
            f"│\n"
        )

        if delivery.success and delivery.accounts:
            msg1 += f"│ ── {{ PRODUCT DETAIL }} ──\n│\n"
            for line in delivery.formatted_text.split("\n"):
                msg1 += f"│ {line}\n"
            msg1 += f"│\n"
        else:
            msg1 += (
                f"│ ── {{ PRODUCT DETAIL }} ──\n│\n"
                f"│ ⚠️ Akun belum tersedia.\n"
                f"│ Admin akan kirim manual.\n│\n"
            )

        msg1 += f"╰──────────────────────────────"

        await _bot.send_message(chat_id=order.user_id, text=msg1, parse_mode="HTML")

        # PESAN 2: Delivery description
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
                f"Apabila ada kendala pada akun silahkan forward detail transaksi sukses "
                f"beserta kendala pada akun ke {STORE_CONTACT}"
            )
            await _bot.send_message(chat_id=order.user_id, text=msg2, parse_mode="HTML")

        logger.info("[pakasir_webhook] ✅ Order notification sent to user %s", order.user_id)

        # Notify admin
        from config.settings import ADMIN_IDS
        user_repo = await get_user_repository()
        user_data = await user_repo.get_by_id(order.user_id)
        username = user_data.username if user_data and user_data.username else f"@id:{order.user_id}"
        now_str = dt.now().strftime("%d/%m/%Y %H:%M")

        delivered_text = delivery.formatted_text if delivery.success else ""

        for admin_id in ADMIN_IDS:
            try:
                admin_msg = (
                    f"🔔 <b>ORDER PAID</b> (Pakasir)\n\n"
                    f"Kode : {order_id[:8]}\n"
                    f"Produk : {product_name}\n"
                    f"Jumlah : {order.quantity}\n"
                    f"Total : Rp {order.total_price:,}\n"
                    f"Customer : @{username}\n"
                    f"Tanggal : {now_str}\n"
                )
                if delivered_text:
                    admin_msg += f"\n📦 Akun terkirim:\n{delivered_text}\n"

                await _bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
            except Exception as e:
                logger.error("[pakasir_webhook] Failed to notify admin %s: %s", admin_id, e)

    except Exception as e:
        logger.error("[pakasir_webhook] Failed to send notification: %s", str(e), exc_info=True)
