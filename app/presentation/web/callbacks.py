"""
FastAPI webhook handler untuk Tripay payment callbacks.

Endpoint:
  POST /webhook/tripay - Menerima callback dari Tripay saat payment berhasil/gagal
  GET  /health         - Health check endpoint

Flow:
1. Tripay kirim POST request dengan payment data
2. Verify signature (HMAC-SHA256 dengan private key)
3. Determine type: deposit atau order payment
4. Process accordingly (add balance / update order status)
5. Send notification ke user via Telegram bot
6. Return 200 OK (WAJIB return 200, kalau tidak Tripay akan retry)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.application.services.factory import get_payment_service, get_deposit_service
from app.infrastructure.payment.tripay import get_tripay_client
from config.settings import WEBHOOK_SECRET, STORE_CONTACT

logger = logging.getLogger(__name__)

# FastAPI app instance
app = FastAPI(title="T-Store Webhook", docs_url=None, redoc_url=None)

# Bot instance akan di-inject dari main.py
_bot = None


def set_bot(bot) -> None:
    """Inject bot instance untuk kirim notifikasi ke user."""
    global _bot
    _bot = bot


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "T-Store Webhook"}


@app.post("/webhook/tripay")
async def tripay_webhook(request: Request):
    """Handle Tripay payment callback.

    Tripay mengirim POST dengan body JSON berisi:
    - reference: transaction reference (dari Tripay)
    - merchant_ref: our merchant reference (format: DEP-{user_id}-{timestamp} atau order_id)
    - status: PAID, EXPIRED, FAILED
    - amount_received: jumlah yang diterima
    - total_amount: total yang harus dibayar
    - fee_merchant: fee yang ditanggung merchant
    - paid_at: waktu pembayaran
    """
    try:
        # 1. Read raw body
        body = await request.body()
        signature = request.headers.get("X-Callback-Signature", "")

        logger.info("[webhook] 📥 Incoming callback, signature present: %s", bool(signature))

        # 2. Verify signature menggunakan Tripay private key
        tripay_client = get_tripay_client()
        if tripay_client and signature:
            if not tripay_client.verify_callback_signature(body, signature):
                logger.warning("[webhook] ❌ Invalid signature!")
                raise HTTPException(status_code=403, detail="Invalid signature")
            logger.info("[webhook] ✅ Signature verified")
        elif not signature:
            logger.warning("[webhook] ⚠️ No signature in request (testing mode?)")

        # 3. Parse body
        data = json.loads(body)
        merchant_ref = data.get("merchant_ref", "")
        status = data.get("status", "")
        amount = data.get("amount_received", data.get("total_amount", 0))
        reference = data.get("reference", "")
        paid_at = data.get("paid_at", "")

        logger.info(
            "[webhook] 📋 Callback data: merchant_ref=%s status=%s amount=%s reference=%s",
            merchant_ref, status, amount, reference,
        )

        # 4. Determine type: deposit atau order
        if merchant_ref.startswith("DEP-"):
            # Deposit callback
            await _handle_deposit_callback(merchant_ref, status, amount, reference)
        else:
            # Order payment callback
            await _handle_order_callback(merchant_ref, status, reference, paid_at)

        return JSONResponse(content={"success": True}, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[webhook] ❌ Error processing callback: %s", str(e), exc_info=True)
        # Return 200 anyway to prevent Tripay from retrying
        return JSONResponse(content={"success": True}, status_code=200)


async def _handle_deposit_callback(
    merchant_ref: str, status: str, amount: int, reference: str
) -> None:
    """Handle deposit payment callback.

    merchant_ref format: DEP-{user_id}-{timestamp}
    """
    if status != "PAID":
        logger.info("[webhook] Deposit %s status=%s (bukan PAID), skip", merchant_ref, status)
        return

    # Parse user_id dari merchant_ref
    parts = merchant_ref.split("-")
    if len(parts) < 3:
        logger.error("[webhook] Invalid deposit ref format: %s", merchant_ref)
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        logger.error("[webhook] Cannot parse user_id from ref: %s", merchant_ref)
        return

    # Process deposit
    deposit_svc = await get_deposit_service()
    success = await deposit_svc.process_deposit_callback(
        user_id=user_id,
        amount=amount,
        payment_ref=merchant_ref,
    )

    if success and _bot:
        # Notify user via Telegram
        try:
            new_balance = 0
            try:
                new_balance = await deposit_svc.get_user_balance(user_id)
            except Exception:
                pass

            await _bot.send_message(
                chat_id=user_id,
                text=(
                    f"✅ <b>DEPOSIT BERHASIL!</b>\n\n"
                    f"• Ref : <code>{reference or merchant_ref}</code>\n"
                    f"• Nominal : Rp {amount:,}\n"
                    f"• Saldo Baru : Rp {new_balance:,}\n\n"
                    f"💰 Saldo telah ditambahkan. Selamat berbelanja!"
                ),
                parse_mode="HTML",
            )
            logger.info("[webhook] ✅ Deposit notification sent to user %s", user_id)
        except Exception as e:
            logger.error("[webhook] Failed to notify user %s: %s", user_id, str(e))
    elif success:
        logger.warning("[webhook] Deposit processed but bot not available for notification")


async def _handle_order_callback(
    order_id: str, status: str, reference: str, paid_at: str
) -> None:
    """Handle order payment callback.

    Flow saat PAID:
    1. Update order status → paid
    2. Store payment reference
    3. Get order + product details
    4. Send notification ke user (order berhasil + account details)
    """
    # Get payment service
    payment_svc = await get_payment_service()
    result = await payment_svc.process_order_payment(
        order_id=order_id,
        status=status,
        payment_ref=reference,
    )

    if not result.success:
        logger.error(
            "[webhook] Failed to process order %s: %s",
            order_id, result.error_message,
        )
        return

    # Jika status bukan PAID, tidak perlu kirim notifikasi
    if status != "PAID":
        logger.info("[webhook] Order %s status=%s (bukan PAID), no notification", order_id, status)
        return

    # Store payment reference di order
    try:
        from app.infrastructure.database.factory import get_order_repository
        order_repo = await get_order_repository()
        if reference:
            await order_repo.update_payment_ref(order_id, reference)
    except Exception as e:
        logger.error("[webhook] Failed to update payment_ref: %s", e)

    # Get order details untuk notifikasi
    if _bot:
        try:
            # Cleanup flow messages (QRIS pending, konfirmasi, catatan, detail variant)
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
            except Exception as _e:
                logger.warning("[webhook] Cleanup flow messages failed: %s", _e)

            from app.infrastructure.database.factory import (
                get_order_repository,
                get_product_repository,
                get_user_repository,
            )
            order_repo = await get_order_repository()
            product_repo = await get_product_repository()

            order = await order_repo.get_by_id(order_id)
            if not order:
                logger.error("[webhook] Order %s not found for notification", order_id)
                return

            product = await product_repo.get_by_id(order.product_id)
            product_name = product.name if product else "Unknown Product"

            # Send success notification to user
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
                f"│ Ref : {reference}\n"
                f"│ Nama Produk : {product_name}\n"
                f"│ Jumlah Beli : {order.quantity}\n"
                f"│ Total : Rp {order.total_price:,}\n"
                f"│ Methode Pay : QRIS\n"
                f"│ Tanggal : {now}\n"
                f"│\n"
            )

            if delivery.success and delivery.accounts:
                msg1 += (
                    f"│ ── {{ PRODUCT DETAIL }} ──\n"
                    f"│\n"
                )
                for line in delivery.formatted_text.split("\n"):
                    msg1 += f"│ {line}\n"
                msg1 += f"│\n"
            else:
                msg1 += (
                    f"│ ── {{ PRODUCT DETAIL }} ──\n"
                    f"│\n"
                    f"│ ⚠️ Akun belum tersedia.\n"
                    f"│ Admin akan kirim manual.\n"
                    f"│\n"
                )

            msg1 += f"╰──────────────────────────────"

            await _bot.send_message(
                chat_id=order.user_id,
                text=msg1,
                parse_mode="HTML",
            )

            # PESAN 2: Delivery description (T&C, syarat, cara login)
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
                await _bot.send_message(
                    chat_id=order.user_id,
                    text=msg2,
                    parse_mode="HTML",
                )

            logger.info(
                "[webhook] ✅ Order payment notification sent to user %s (order=%s)",
                order.user_id, order_id,
            )

            # Notify admin about new paid order
            from config.settings import ADMIN_IDS
            from datetime import datetime as dt

            # Get username
            user_repo = await get_user_repository()
            user_data = await user_repo.get_by_id(order.user_id)
            username = user_data.username if user_data and user_data.username else f"@id:{order.user_id}"
            now = dt.now().strftime("%d/%m/%Y %H:%M")

            for admin_id in ADMIN_IDS:
                if str(admin_id) == str(order.user_id):
                    continue
                try:
                    admin_text = (
                        f"🔔 <b>ORDER PAID</b>\n\n"
                        f"Kode : {order_id[:8]}\n"
                        f"Produk : {product_name}\n"
                        f"Jumlah : {order.quantity}\n"
                        f"Total : Rp {order.total_price:,}\n"
                        f"Customer : @{username}\n"
                        f"Tanggal : {now}\n"
                    )
                    if delivery.success and delivery.accounts:
                        admin_text += f"\n📦 Akun terkirim:\n{delivery.formatted_text}\n"
                    else:
                        admin_text += "\n⚠️ Akun belum tersedia. Kirim manual ke user."

                    await _bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error("[webhook] Failed to notify admin %s: %s", admin_id, e)

        except Exception as e:
            logger.error("[webhook] Failed to send order notification: %s", str(e), exc_info=True)
    else:
        logger.warning("[webhook] Bot not available, cannot send notification for order %s", order_id)
