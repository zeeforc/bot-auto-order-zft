"""
Handler untuk order flow: qty change, checkout, note, confirmation, cancel.

Flow:
1. User pilih produk (dari menu.py) -> masuk OrderStates.waiting_for_qty_or_checkout
2. User adjust qty (+/-) atau langsung checkout
3. Pilih metode: saldo / now (QRIS)
4. Isi catatan (optional)
5. Konfirmasi -> execute via OrderService
"""
import asyncio
import io
import logging
from datetime import datetime, timedelta

import qrcode
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.presentation.telegram.states import OrderStates
from app.presentation.telegram.keyboards import order as kb
from app.application.services.factory import get_order_service
from config import settings

QRIS_EXPIRE_SECONDS = 15 * 60  # 15 menit

logger = logging.getLogger(__name__)
router = Router()


async def _notify_admin_new_order(
    bot, user, product_name: str, order_id: str, qty: int, total: int,
    delivered_accounts: str = "",
) -> None:
    """Kirim notifikasi ke admin saat order PAID (saldo = instant paid)."""
    from config.settings import ADMIN_IDS

    username = user.username if hasattr(user, 'username') and user.username else f"@id:{user.id}"
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    text = (
        f"🔔 <b>ORDER PAID</b>\n\n"
        f"Kode : {order_id[:8]}\n"
        f"Produk : {product_name}\n"
        f"Jumlah : {qty}\n"
        f"Total : Rp {total:,}\n"
        f"Customer : @{username}\n"
        f"Tanggal : {now}\n"
    )

    if delivered_accounts:
        text += f"\n📦 Akun terkirim:\n{delivered_accounts}\n"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.error("[order] Failed to notify admin %s: %s", admin_id, e)


def _generate_qr_image(data: str) -> bytes:
    """Generate QR code image (PNG bytes) dari EMV QRIS string.

    Hanya dipanggil di production mode (qr_string valid >= 50 chars).
    Output: high-res PNG, padat, bisa di-scan langsung oleh e-wallet.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def _is_valid_qris_string(qr_string: str | None) -> bool:
    """Check apakah qr_string adalah EMV QRIS asli (bukan sandbox placeholder)."""
    if not qr_string:
        return False
    if qr_string == "SANDBOX MODE":
        return False
    if len(qr_string) < 50:
        return False
    return True


# --- FLOW: QTY +/- via inline button ---
@router.callback_query(OrderStates.waiting_for_qty_or_checkout, F.data.startswith("qty:"))
async def handle_qty_change(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    action = parts[1]

    if action == "noop":
        return await callback.answer()

    product_id = int(parts[2])
    current_qty = int(parts[3])

    # Ambil data produk dari FSM state
    data = await state.get_data()
    product_data = data.get("product_data")

    if not product_data:
        return await callback.answer("⚠️ Data produk tidak ditemukan.", show_alert=True)

    stock = product_data["stock"]
    new_qty = current_qty + 1 if action == "plus" else current_qty - 1

    if new_qty < 1:
        return await callback.answer("⚠️ Minimal pembelian adalah 1!", show_alert=True)
    if new_qty > stock:
        return await callback.answer("⚠️ Stok produk tidak mencukupi!", show_alert=True)

    # Hitung skema harga grosir otomatis (200+ pakai wholesale)
    price = product_data["price"]
    wholesale = product_data.get("wholesale", int(price * 0.9))
    price_per_item = wholesale if new_qty >= 200 else price
    total_price = price_per_item * new_qty

    # Update caption dengan qty & total harga baru
    updated_caption = (
        f"<b>tambahkan jumlah pembelian:</b>\n\n"
        f"• Produk : {product_data['name']}\n"
        f"• Kode : {product_data.get('code', f'P{product_id:03d}')}\n"
        f"• Sisa Stok : {stock}\n"
        f"• Total Stok : {stock}\n"
        f"• Desk : {product_data['name']}\n\n"
        f"▪︎ Jumlah : {new_qty}\n"
        f"• Harga : Rp {price_per_item:,}\n"
        f"• Total Harga : Rp {total_price:,}\n\n"
        f"——[ 🎫 Harga Grosir ]\n"
        f"• Min 200 : Rp {wholesale:,}\n"
    )

    try:
        await callback.message.edit_caption(
            caption=updated_caption,
            reply_markup=kb.get_product_detail_keyboard(product_id, new_qty)
        )
    except Exception:
        await callback.message.edit_text(
            text=updated_caption,
            reply_markup=kb.get_product_detail_keyboard(product_id, new_qty)
        )
    await callback.answer()


# --- FLOW: CHECKOUT METHOD (Saldo / Buy Now) ---
@router.callback_query(OrderStates.waiting_for_qty_or_checkout, F.data.startswith("checkout:"))
async def handle_checkout_method(callback: CallbackQuery, state: FSMContext):
    _, method, product_id, qty = callback.data.split(":")
    logger.info(
        "[order] Checkout method=%s product_id=%s qty=%s by user_id=%s",
        method, product_id, qty, callback.from_user.id
    )

    # Simpan ke FSM context
    await state.update_data(product_id=int(product_id), qty=int(qty), method=method)

    # Track message for cleanup
    note_msg = await callback.message.answer(
        text="📋 <b>Catatan untuk penjual</b>\n\nMau isi catatan atau skip?",
        reply_markup=kb.get_note_choice_keyboard(int(product_id))
    )
    data = await state.get_data()
    msg_ids = data.get("_msg_ids", [])
    msg_ids.append(note_msg.message_id)
    await state.update_data(_msg_ids=msg_ids)

    await state.set_state(OrderStates.waiting_for_note_choice)
    await callback.answer()


# --- FLOW: ISI CATATAN (atau skip) ---
@router.callback_query(OrderStates.waiting_for_note_choice, F.data == "note:fill")
async def ask_for_note_text(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        text="📝 Silakan <b>ketik catatan</b> untuk penjual.\nMaks 500 karakter.",
        reply_markup=kb.get_note_choice_keyboard(0)
    )
    await state.set_state(OrderStates.waiting_for_note_text)
    await callback.answer()


@router.callback_query(OrderStates.waiting_for_note_text, F.data == "note:skip")
@router.callback_query(OrderStates.waiting_for_note_choice, F.data == "note:skip")
async def skip_note(callback: CallbackQuery, state: FSMContext):
    await state.update_data(note="Tanpa catatan")
    await render_confirmation_screen(callback.message, state)
    await callback.answer()


@router.message(OrderStates.waiting_for_note_text)
async def process_note_text(message: Message, state: FSMContext):
    if len(message.text) > 500:
        return await message.answer("⚠️ Catatan terlalu panjang! Maksimal 500 karakter.")

    await state.update_data(note=message.text)
    await render_confirmation_screen(message, state)


# --- FLOW: KONFIRMASI ---
async def render_confirmation_screen(message: Message, state: FSMContext):
    """Render layar konfirmasi pesanan (dengan voucher jika ada)."""
    data = await state.get_data()
    product_data = data.get("product_data")

    if not product_data:
        return await message.answer("⚠️ Data produk tidak ditemukan.")

    qty = data["qty"]
    price = product_data["price"]
    wholesale = product_data.get("wholesale", int(price * 0.9))
    price_per_item = wholesale if qty >= 200 else price
    total_price = price_per_item * qty

    # Check voucher
    discount = 0
    voucher_code = ""
    voucher_id = None
    try:
        from app.presentation.telegram.handlers.voucher import get_user_voucher
        from app.application.services.factory import get_voucher_service
        active_code = get_user_voucher(message.chat.id)
        if active_code:
            voucher_svc = await get_voucher_service()
            v_result = await voucher_svc.validate_voucher(
                code=active_code,
                user_id=message.chat.id,
                total_price=total_price,
            )
            if v_result.valid:
                discount = v_result.discount
                voucher_code = active_code
                voucher_id = v_result.voucher.id
    except Exception:
        pass

    final_price = total_price - discount

    # Store voucher info in state for execution
    await state.update_data(
        _voucher_code=voucher_code,
        _voucher_id=voucher_id,
        _voucher_discount=discount,
    )

    conf_text = (
        f"📄 <b>Konfirmasi Pesanan</b>\n\n"
        f"• Produk : {product_data['name']}\n"
        f"• Qty : {qty}\n"
        f"• Harga/unit : Rp {price_per_item:,}\n"
        f"• Subtotal : Rp {total_price:,}\n"
    )
    if discount > 0:
        conf_text += (
            f"• Voucher : {voucher_code} (-Rp {discount:,})\n"
            f"• <b>Total : Rp {final_price:,}</b>\n"
        )
    else:
        conf_text += f"• <b>Total : Rp {total_price:,}</b>\n"

    conf_text += (
        f"• Metode : {data['method'].upper()}\n\n"
        f"📝 Catatan untuk penjual:\n"
        f"{data['note']}"
    )
    conf_msg = await message.answer(text=conf_text, reply_markup=kb.get_confirmation_keyboard())

    # Track confirmation message for cleanup
    msg_ids = data.get("_msg_ids", [])
    msg_ids.append(conf_msg.message_id)
    await state.update_data(_msg_ids=msg_ids)

    await state.set_state(OrderStates.waiting_for_confirmation)


# --- FLOW: EKSEKUSI TRANSAKSI (via OrderService) ---
@router.callback_query(OrderStates.waiting_for_confirmation, F.data == "order:confirm")
async def execute_order(callback: CallbackQuery, state: FSMContext):
    # Anti double-click: check & set processing flag
    data = await state.get_data()
    if data.get("_processing"):
        return await callback.answer("⏳ Sedang diproses...", show_alert=False)

    await state.update_data(_processing=True)

    product_data = data.get("product_data")

    if not product_data:
        await state.clear()
        return await callback.answer("⚠️ Data produk tidak ditemukan.", show_alert=True)

    product_id = data["product_id"]
    method = data["method"]
    qty = data["qty"]
    note = data.get("note", "Tanpa catatan")
    # Voucher data from confirmation screen
    _voucher_code = data.get("_voucher_code", "")
    _voucher_id = data.get("_voucher_id")
    _voucher_discount = data.get("_voucher_discount", 0)
    # Capture tracked messages for cleanup after success
    _cleanup_msg_ids = data.get("_msg_ids", [])
    _cleanup_product_msg_id = data.get("_product_msg_id")

    logger.info(
        "[order] Execute order: user_id=%s product_id=%s qty=%s method=%s",
        callback.from_user.id, product_id, qty, method,
    )

    # Clear state immediately to prevent double execution
    await state.clear()

    # Get OrderService
    order_service = await get_order_service()

    # CASE 1: BAYAR PAKAI SALDO
    if method == "saldo":
        # Check saldo dulu untuk UX yang lebih baik
        user_balance = await order_service.get_user_balance(callback.from_user.id)
        price = product_data["price"]
        wholesale = product_data.get("wholesale", int(price * 0.9))
        price_per_item = wholesale if qty >= 200 else price
        total_cost = price_per_item * qty

        # Apply voucher discount
        if _voucher_discount > 0:
            total_cost = max(0, total_cost - _voucher_discount)

        if user_balance < total_cost:
            await callback.answer(
                text=(
                    f"Saldo tidak cukup!\n"
                    f"Saldo: Rp {user_balance:,}\n"
                    f"Dibutuhkan: Rp {total_cost:,}"
                ),
                show_alert=True,
            )
            return

        # Execute order via service (with variant_id + unit_price)
        result = await order_service.execute_order(
            user_id=callback.from_user.id,
            product_id=product_id,
            quantity=qty,
            payment_method="saldo",
            variant_id=product_data.get("variant_id"),
            unit_price=price_per_item,
        )

        if not result.success:
            await callback.message.answer(
                f"❌ <b>Gagal memproses order</b>\n\n{result.error_message}"
            )
            await state.clear()
            await callback.answer()
            return

        # Sukses! Tampilkan detail transaksi
        new_balance = await order_service.get_user_balance(callback.from_user.id)

        # Auto-deliver accounts
        from app.application.services.delivery_service import deliver_accounts
        delivery = await deliver_accounts(
            order_id=result.order.id,
            product_id=product_id,
            quantity=qty,
            user_id=callback.from_user.id,
            variant_id=product_data.get("variant_id"),
        )

        now = datetime.now().strftime("%d %b %Y pukul %H:%M")

        # PESAN 1: Detail transaksi + account data
        msg1 = (
            f"╭─── {{ TRANSAKSI SUKSES }} ───\n"
            f"│\n"
            f"│ Pay ID : {result.order.id[:8]}\n"
            f"│ Nama Produk : {product_data['name']}\n"
            f"│ Jumlah Beli : {qty}\n"
            f"│ Harga : Rp {price_per_item:,}\n"
            f"│ Total : Rp {total_cost:,}\n"
            f"│ Methode Pay : Saldo\n"
            f"│ Saldo Awal : Rp {user_balance:,}\n"
            f"│ Sisa Saldo : Rp {new_balance:,}\n"
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

        await callback.message.answer(msg1)

        # PESAN 2: Delivery description (T&C, syarat, cara login)
        # Priority: variant.delivery_description → product.delivery_description → fallback
        delivery_desc = ""
        try:
            from app.infrastructure.database.connection import get_pool
            pool = get_pool()
            if pool:
                async with pool.acquire() as conn:
                    variant_id = product_data.get("variant_id")
                    if variant_id:
                        dd = await conn.fetchval(
                            "SELECT delivery_description FROM product_variants WHERE id = $1",
                            variant_id,
                        )
                        if dd:
                            delivery_desc = dd
                    if not delivery_desc:
                        dd = await conn.fetchval(
                            "SELECT delivery_description FROM products WHERE id = $1",
                            product_id,
                        )
                        if dd:
                            delivery_desc = dd
        except Exception:
            pass

        if delivery_desc:
            msg2 = (
                f"[ {product_data['name']} ]\n\n"
                f"{delivery_desc}\n\n"
                f"────────────────────\n"
                f"Apabila ada kendala pada akun silahkan forward detail transaksi sukses "
                f"beserta kendala pada akun ke {settings.STORE_CONTACT}"
            )
            await callback.message.answer(msg2)

        # Notify admin (include delivered accounts)
        await _notify_admin_new_order(
            callback.bot, callback.from_user,
            product_data['name'], result.order.id, qty, total_cost,
            delivered_accounts=delivery.formatted_text if delivery.success else "",
        )

        # Apply voucher (mark as used) if applicable
        if _voucher_id and _voucher_discount > 0:
            try:
                from app.application.services.factory import get_voucher_service
                from app.presentation.telegram.handlers.voucher import clear_user_voucher
                voucher_svc = await get_voucher_service()
                await voucher_svc.apply_voucher(_voucher_id, callback.from_user.id, result.order.id)
                clear_user_voucher(callback.from_user.id)
                logger.info("[order] Voucher applied: code=%s discount=%s", _voucher_code, _voucher_discount)
            except Exception as e:
                logger.error("[order] Failed to apply voucher: %s", e)

        # Cleanup flow messages (variant detail, catatan, konfirmasi)
        chat_id = callback.message.chat.id
        cleanup_ids = list(_cleanup_msg_ids)
        if _cleanup_product_msg_id:
            cleanup_ids.append(_cleanup_product_msg_id)
        cleanup_ids.append(callback.message.message_id)  # konfirmasi message itself
        for mid in cleanup_ids:
            try:
                await callback.bot.delete_message(chat_id=chat_id, message_id=mid)
            except Exception:
                pass

    # CASE 2: BAYAR LANGSUNG VIA QRIS
    elif method == "now":
        # Calculate total first
        price = product_data["price"]
        wholesale = product_data.get("wholesale", int(price * 0.9))
        price_per_item = wholesale if qty >= 200 else price
        total_cost = price_per_item * qty

        # Apply voucher discount
        if _voucher_discount > 0:
            total_cost = max(0, total_cost - _voucher_discount)

        # Minimum amount check for payment gateway
        if total_cost < 500:
            await callback.message.answer(
                f"⚠️ Total setelah diskon terlalu kecil (Rp {total_cost:,}).\n"
                f"Minimal transaksi QRIS: Rp 500.\n\n"
                f"Coba order tanpa voucher atau tambah qty."
            )
            await callback.answer()
            return

        # Execute order (status = pending, with variant_id + unit_price)
        result = await order_service.execute_order(
            user_id=callback.from_user.id,
            product_id=product_id,
            quantity=qty,
            payment_method="now",
            variant_id=product_data.get("variant_id"),
            unit_price=price_per_item,
        )

        if not result.success:
            await callback.message.answer(
                f"❌ <b>Gagal memproses order</b>\n\n{result.error_message}"
            )
            await state.clear()
            await callback.answer()
            return

        # Generate QRIS via active payment provider
        from app.infrastructure.payment.factory import get_active_provider
        provider = get_active_provider()

        if provider:
            # Real payment generation
            payment = await provider.create_payment(
                order_id=result.order.id,
                amount=total_cost,
                product_name=product_data["name"],
                user_id=callback.from_user.id,
            )

            if payment.success:
                # Success - show payment info
                fee = payment.fee
                total_pay = payment.total_amount
                qr_string = payment.qr_string
                checkout_url = payment.checkout_url
                reference = payment.reference

                # Format waktu ke WIB (UTC+7)
                from datetime import timezone
                wib = timezone(timedelta(hours=7))
                now = datetime.now(wib)
                expired_at = now + timedelta(seconds=QRIS_EXPIRE_SECONDS)
                jam_str = now.strftime("%d %b %Y pukul %H:%M")
                expired_str = expired_at.strftime("%Y-%m-%d %H:%M:%S")

                # Build caption — hide fee line if 0
                caption_qris = (
                    f"╭─────{{ ⏳ TRANSAKSI PENDING }}─────\n"
                    f"│\n"
                    f"│ • ID Payment  : <code>{reference}</code>\n"
                    f"│ • Service     : QRIS ({provider.name})\n"
                    f"│ • Produk      : {product_data['name']}\n"
                    f"│ • Harga/Unit  : Rp {price_per_item:,}\n"
                    f"│ • Jumlah      : {qty}\n"
                )
                if _voucher_discount > 0:
                    caption_qris += f"│ • Voucher     : {_voucher_code} (-Rp {_voucher_discount:,})\n"
                if fee > 0:
                    caption_qris += f"│ • Fee         : Rp {fee:,}\n"
                caption_qris += (
                    f"│ • Note        : {note}\n"
                    f"│ • <b>Total Bayar : Rp {total_pay:,}</b>\n"
                    f"│ • Jam/Tanggal : {jam_str}\n"
                    f"│ • Bayar sblm  : {expired_str}\n"
                )

                if checkout_url:
                    caption_qris += f"│ • Link        : {checkout_url}\n"

                caption_qris += (
                    f"│\n"
                    f"╰──────────────────────────────────"
                )

                # Cancel button
                cancel_kb = InlineKeyboardBuilder()
                cancel_kb.button(text="❌ Batalkan Pembayaran", callback_data=f"qris:cancel:{result.order.id}")

                try:
                    if _is_valid_qris_string(qr_string):
                        # PRODUCTION: Generate QR image dari EMV QRIS string asli
                        qr_bytes = _generate_qr_image(qr_string)
                        qr_photo = BufferedInputFile(qr_bytes, filename="qris.png")
                        qris_msg = await callback.message.answer_photo(
                            photo=qr_photo,
                            caption=caption_qris,
                            reply_markup=cancel_kb.as_markup(),
                        )
                    else:
                        # SANDBOX: Tampilkan text only + checkout link
                        qris_msg = await callback.message.answer(
                            text=caption_qris,
                            reply_markup=cancel_kb.as_markup(),
                        )
                except Exception as e:
                    logger.error("[order] Failed to send QRIS: %s", e)
                    qris_msg = await callback.message.answer(
                        text=caption_qris,
                        reply_markup=cancel_kb.as_markup(),
                    )

                # Track flow messages so webhook bisa hapus saat PAID
                from app.presentation.order_message_tracker import track as _track_msgs
                flow_ids = list(_cleanup_msg_ids)
                if _cleanup_product_msg_id:
                    flow_ids.append(_cleanup_product_msg_id)
                flow_ids.append(callback.message.message_id)  # konfirmasi msg
                flow_ids.append(qris_msg.message_id)          # QRIS msg itself
                _track_msgs(result.order.id, callback.message.chat.id, flow_ids)

                # Apply voucher (mark as used) for QRIS orders
                if _voucher_id and _voucher_discount > 0:
                    try:
                        from app.application.services.factory import get_voucher_service
                        from app.presentation.telegram.handlers.voucher import clear_user_voucher
                        voucher_svc = await get_voucher_service()
                        await voucher_svc.apply_voucher(_voucher_id, callback.from_user.id, result.order.id)
                        clear_user_voucher(callback.from_user.id)
                        logger.info("[order] Voucher applied (QRIS): code=%s discount=%s", _voucher_code, _voucher_discount)
                    except Exception as e:
                        logger.error("[order] Failed to apply voucher (QRIS): %s", e)

                # Schedule auto-delete after 15 minutes
                asyncio.create_task(
                    _auto_expire_qris(callback.bot, qris_msg, result.order.id)
                )
            else:
                # Payment provider error - show fallback
                logger.error("[order] Payment error: %s", payment.error)
                caption_qris = (
                    f"————— [ ⏳ TRANSAKSI PENDING ] —————\n\n"
                    f"• Order ID : <code>{result.order.id}</code>\n"
                    f"• Produk : {product_data['name']}\n"
                    f"• Total : Rp {total_cost:,}\n\n"
                    f"⚠️ Gagal generate QRIS. Silakan coba lagi atau hubungi admin.\n"
                    f"Error: {payment.error}\n"
                )
                await callback.message.answer(text=caption_qris)
        else:
            # Mock mode (provider not configured)
            cancel_kb = InlineKeyboardBuilder()
            cancel_kb.button(text="❌ Batalkan Pembayaran", callback_data=f"qris:cancel:{result.order.id}")

            caption_qris = (
                f"————— [ ⏳ TRANSAKSI PENDING ] —————\n\n"
                f"• Order ID : <code>{result.order.id}</code>\n"
                f"• Service Payment : QRIS (mock)\n"
                f"• Total : Rp {total_cost:,}\n\n"
                f"⚠️ Payment gateway belum di-configure. Hubungi admin.\n"
            )
            try:
                qris_msg = await callback.message.answer_photo(
                    photo=FSInputFile("assets/mock_qris.jpg"),
                    caption=caption_qris,
                    reply_markup=cancel_kb.as_markup(),
                )
            except Exception:
                qris_msg = await callback.message.answer(
                    text=caption_qris,
                    reply_markup=cancel_kb.as_markup(),
                )

            asyncio.create_task(
                _auto_expire_qris(callback.bot, qris_msg, result.order.id)
            )

            # Track also for mock mode
            from app.presentation.order_message_tracker import track as _track_msgs
            flow_ids = list(_cleanup_msg_ids)
            if _cleanup_product_msg_id:
                flow_ids.append(_cleanup_product_msg_id)
            flow_ids.append(callback.message.message_id)
            flow_ids.append(qris_msg.message_id)
            _track_msgs(result.order.id, callback.message.chat.id, flow_ids)

    # CASE 3: BAYAR VIA GOPAY QRIS (No Fee — MacroDroid)
    elif method == "gopay":
        # Calculate base total
        price = product_data["price"]
        wholesale = product_data.get("wholesale", int(price * 0.9))
        price_per_item = wholesale if qty >= 200 else price
        base_cost = price_per_item * qty

        # Apply voucher discount
        if _voucher_discount > 0:
            base_cost = max(0, base_cost - _voucher_discount)

        # Minimum amount check
        if base_cost < 100:
            await callback.message.answer(
                f"⚠️ Total terlalu kecil (Rp {base_cost:,}).\n"
                f"Minimal transaksi GoPay QRIS: Rp 100."
            )
            await callback.answer()
            return

        # Generate unique amount (anti-collision)
        try:
            final_amount = await order_service.generate_unique_amount(base_cost)
        except Exception as e:
            logger.error("[order] GoPay unique amount error: %s", e)
            await callback.message.answer(
                "❌ Gagal generate nominal unik. Coba lagi nanti."
            )
            await callback.answer()
            return

        unique_code = final_amount - base_cost

        # Execute order (status = pending, payment_method = gopay)
        result = await order_service.execute_order(
            user_id=callback.from_user.id,
            product_id=product_id,
            quantity=qty,
            payment_method="gopay",
            variant_id=product_data.get("variant_id"),
            unit_price=price_per_item,
        )

        if not result.success:
            await callback.message.answer(
                f"❌ <b>Gagal memproses order</b>\n\n{result.error_message}"
            )
            await callback.answer()
            return

        # Override total_price di DB dengan final_amount (termasuk kode unik)
        try:
            from app.infrastructure.database.connection import get_pool
            pool = get_pool()
            if pool:
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE orders SET total_price = $1 WHERE id = $2",
                        final_amount, result.order.id,
                    )
        except Exception as e:
            logger.error("[order] Failed to update gopay amount: %s", e)

        # Generate QRIS via GoPay provider
        from app.infrastructure.payment.gopay_qris import GopayProvider, _generate_qr_bytes
        gopay_static = settings.GOPAY_STATIC_QRIS

        if gopay_static:
            from app.infrastructure.payment.gopay_qris import _build_dynamic_qris
            try:
                qris_string = _build_dynamic_qris(gopay_static, final_amount)
                qr_bytes = _generate_qr_bytes(qris_string)
            except Exception as e:
                logger.error("[order] GoPay QRIS generation error: %s", e)
                await callback.message.answer(
                    f"❌ Gagal generate QRIS GoPay.\n\nError: {e}\n\n"
                    f"Pastikan GOPAY_STATIC_QRIS sudah diisi dengan benar di .env"
                )
                await callback.answer()
                return
        else:
            await callback.message.answer(
                "⚠️ GoPay QRIS belum di-configure.\n\n"
                "Admin perlu mengisi GOPAY_STATIC_QRIS di .env terlebih dahulu."
            )
            await callback.answer()
            return

        # Format waktu
        now = datetime.now()
        expired_at = now + timedelta(seconds=QRIS_EXPIRE_SECONDS)
        jam_str = now.strftime("%d %b %Y pukul %H:%M")
        expired_str = expired_at.strftime("%Y-%m-%d %H:%M:%S")

        # Build caption — emphasize exact amount
        caption_gopay = (
            f"╭─────{{ ⏳ TRANSAKSI PENDING }}─────\n"
            f"│\n"
            f"│ • ID Payment  : <code>{result.order.id[:8]}</code>\n"
            f"│ • Service     : 🟢 GoPay QRIS (No Fee)\n"
            f"│ • Produk      : {product_data['name']}\n"
            f"│ • Harga/Unit  : Rp {price_per_item:,}\n"
            f"│ • Jumlah      : {qty}\n"
        )
        if _voucher_discount > 0:
            caption_gopay += f"│ • Voucher     : {_voucher_code} (-Rp {_voucher_discount:,})\n"
        caption_gopay += (
            f"│ • Kode Unik   : +Rp {unique_code:,}\n"
            f"│ • Fee         : Rp 0 (GRATIS)\n"
            f"│ • Note        : {note}\n"
            f"│ • <b>TOTAL BAYAR : Rp {final_amount:,}</b>\n"
            f"│ • Jam/Tanggal : {jam_str}\n"
            f"│ • Bayar sblm  : {expired_str}\n"
            f"│\n"
            f"│ ⚠️ <b>BAYAR HARUS PAS Rp {final_amount:,}</b>\n"
            f"│ Jika nominal tidak tepat, pembayaran\n"
            f"│ tidak terdeteksi otomatis!\n"
            f"│\n"
            f"╰──────────────────────────────────"
        )

        # Action buttons
        cancel_kb = InlineKeyboardBuilder()
        cancel_kb.button(text="🔄 Cek Pembayaran", callback_data=f"qris:check:{result.order.id}")
        cancel_kb.button(text="❌ Batalkan Pembayaran", callback_data=f"qris:cancel:{result.order.id}")
        cancel_kb.adjust(1)

        try:
            qr_photo = BufferedInputFile(qr_bytes, filename="gopay_qris.png")
            qris_msg = await callback.message.answer_photo(
                photo=qr_photo,
                caption=caption_gopay,
                reply_markup=cancel_kb.as_markup(),
            )
        except Exception as e:
            logger.error("[order] Failed to send GoPay QRIS photo: %s", e)
            qris_msg = await callback.message.answer(
                text=caption_gopay,
                reply_markup=cancel_kb.as_markup(),
            )

        # Track flow messages for cleanup
        from app.presentation.order_message_tracker import track as _track_msgs
        flow_ids = list(_cleanup_msg_ids)
        if _cleanup_product_msg_id:
            flow_ids.append(_cleanup_product_msg_id)
        flow_ids.append(callback.message.message_id)
        flow_ids.append(qris_msg.message_id)
        _track_msgs(result.order.id, callback.message.chat.id, flow_ids)

        # Apply voucher if applicable
        if _voucher_id and _voucher_discount > 0:
            try:
                from app.application.services.factory import get_voucher_service
                from app.presentation.telegram.handlers.voucher import clear_user_voucher
                voucher_svc = await get_voucher_service()
                await voucher_svc.apply_voucher(_voucher_id, callback.from_user.id, result.order.id)
                clear_user_voucher(callback.from_user.id)
                logger.info("[order] Voucher applied (GoPay): code=%s discount=%s", _voucher_code, _voucher_discount)
            except Exception as e:
                logger.error("[order] Failed to apply voucher (GoPay): %s", e)

        # Schedule auto-expire after 15 minutes
        asyncio.create_task(
            _auto_expire_qris(callback.bot, qris_msg, result.order.id)
        )

    await callback.answer()


# --- GLOBAL: CANCEL ORDER ---
@router.callback_query(F.data == "order:cancel")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    logger.info("[order] Cancel by user_id=%s", callback.from_user.id)

    # Get tracked message IDs before clearing state
    data = await state.get_data()
    msg_ids = data.get("_msg_ids", [])
    product_msg_id = data.get("_product_msg_id")

    await state.clear()

    # Delete all tracked messages (product detail, note, confirmation)
    chat_id = callback.message.chat.id
    if product_msg_id:
        msg_ids.append(product_msg_id)

    # Also delete the message containing the cancel button itself
    msg_ids.append(callback.message.message_id)

    for mid in msg_ids:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass  # Message might already be deleted or too old

    # Send clean cancel confirmation
    await callback.bot.send_message(
        chat_id=chat_id,
        text="❌ Transaksi telah dibatalkan.",
    )
    await callback.answer()


# --- CHECK QRIS PAYMENT ---
@router.callback_query(F.data.startswith("qris:check:"))
async def check_qris_payment(callback: CallbackQuery):
    """Cek pembayaran secara manual ke GoBiz Web API."""
    order_id = callback.data.split(":", 2)[2]
    
    try:
        from app.infrastructure.database.factory import get_order_repository
        from app.infrastructure.payment.factory import get_active_provider
        
        order_repo = await get_order_repository()
        order = await order_repo.get_by_id(order_id)
        
        if not order:
            await callback.answer("Order tidak ditemukan.", show_alert=True)
            return
            
        if order.status != "pending":
            await callback.answer(f"Order sudah {order.status}.", show_alert=True)
            return

        provider = get_active_provider()
        if not hasattr(provider, "check_payment_status"):
            await callback.answer("Fitur cek otomatis tidak didukung oleh metode ini.", show_alert=True)
            return
            
        # Cek ke GoBiz Web API
        # Nominal total yang harus dibayar ada di order.total_price
        is_paid = await provider.check_payment_status(
            amount=order.total_price, 
            created_after=order.created_at
        )
        
        if is_paid:
            # Jika dibayar, kita jalankan logic success seperti di webhook
            from app.application.services.factory import get_order_service
            order_svc = await get_order_service()
            
            # Kita panggil proses sukses via gopay webhook khusus
            # Karena logic gopay webhook butuh amount untuk pencarian, kita sediakan
            # Tapi karena kita sudah tahu order_id, kita langsung update status & kirim akun
            
            success_order = await order_svc.process_gopay_webhook(order.total_price)
            if success_order:
                await callback.answer("✅ Pembayaran berhasil terverifikasi!", show_alert=True)
                # Cleanup messages
                try:
                    from app.presentation.order_message_tracker import pop as _pop_track
                    tracked = _pop_track(str(order_id))
                    if tracked:
                        chat_id_track, msg_ids_track = tracked
                        for mid in msg_ids_track:
                            try:
                                await callback.bot.delete_message(chat_id=chat_id_track, message_id=mid)
                            except Exception:
                                pass
                except Exception:
                    pass
                
                # Kirim notifikasi sukses via send_gopay_success_notification
                from app.presentation.web.gopay_callback import send_gopay_success_notification
                await send_gopay_success_notification(success_order)
                return
            else:
                await callback.answer("Gagal memproses penyelesaian order.", show_alert=True)
        else:
            await callback.answer("❌ Pembayaran belum masuk. Tunggu sebentar dan coba lagi.", show_alert=True)
            
    except Exception as e:
        logger.error("[order] Failed to check order %s: %s", order_id, e)
        await callback.answer("Terjadi kesalahan saat mengecek.", show_alert=True)


# --- CANCEL QRIS PAYMENT ---
@router.callback_query(F.data.startswith("qris:cancel:"))
async def cancel_qris_payment(callback: CallbackQuery):
    """Cancel pending QRIS payment dan hapus pesan QR."""
    order_id = callback.data.split(":", 2)[2]
    logger.info("[order] QRIS cancel: order_id=%s user_id=%s", order_id, callback.from_user.id)

    # Update order status ke cancelled
    try:
        from app.infrastructure.database.factory import get_order_repository
        order_repo = await get_order_repository()
        await order_repo.update_status(order_id, "cancelled")
    except Exception as e:
        logger.error("[order] Failed to cancel order %s: %s", order_id, e)

    # Clear tracker (no need to auto-delete via webhook anymore)
    try:
        from app.presentation.order_message_tracker import clear as _clear_track
        _clear_track(order_id)
    except Exception:
        pass

    # Delete the QRIS message
    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_caption(
                caption=f"❌ <b>PEMBAYARAN DIBATALKAN</b>\n\nOrder ID: <code>{order_id}</code>"
            )
        except Exception:
            try:
                await callback.message.edit_text(
                    text=f"❌ <b>PEMBAYARAN DIBATALKAN</b>\n\nOrder ID: <code>{order_id}</code>"
                )
            except Exception:
                pass

    await callback.bot.send_message(
        chat_id=callback.message.chat.id,
        text="❌ Pembayaran dibatalkan. Order telah di-cancel.",
    )
    await callback.answer()


# --- AUTO-EXPIRE QRIS ---
async def _auto_expire_qris(bot: Bot, message: Message, order_id: str) -> None:
    """Auto-delete QRIS message after expiry and cancel the order."""
    await asyncio.sleep(QRIS_EXPIRE_SECONDS)

    # Check if order is still pending (belum dibayar/dibatalkan)
    try:
        from app.infrastructure.database.factory import get_order_repository
        order_repo = await get_order_repository()
        order = await order_repo.get_by_id(order_id)

        if order and order.status == "pending":
            # Cancel the order
            await order_repo.update_status(order_id, "cancelled")
            logger.info("[order] ⏰ Auto-expired: order_id=%s", order_id)

            # Clear flow message tracker (won't be needed anymore)
            try:
                from app.presentation.order_message_tracker import clear as _clear_track
                _clear_track(order_id)
            except Exception:
                pass

            # Delete the QRIS message
            try:
                await message.delete()
            except Exception:
                try:
                    await message.edit_caption(
                        caption=f"⏰ <b>PEMBAYARAN EXPIRED</b>\n\nOrder <code>{order_id}</code> telah dibatalkan karena melewati batas waktu."
                    )
                except Exception:
                    try:
                        await message.edit_text(
                            text=f"⏰ <b>PEMBAYARAN EXPIRED</b>\n\nOrder <code>{order_id}</code> telah dibatalkan karena melewati batas waktu."
                        )
                    except Exception:
                        pass
    except Exception as e:
        logger.error("[order] Auto-expire error for %s: %s", order_id, e)
