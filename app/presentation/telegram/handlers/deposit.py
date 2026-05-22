"""
Handler untuk deposit saldo.

Flow:
1. User klik "💰 Deposit" → tampilkan saldo + instruksi
2. User ketik nominal → validasi + tampilkan konfirmasi
3. User konfirmasi → generate QRIS via Tripay (atau mock)
4. User bayar → webhook callback update saldo (handled by PaymentService)
"""
import io
import logging
from datetime import datetime, timedelta

import qrcode
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from app.presentation.telegram.states import DepositStates
from app.application.services.factory import get_deposit_service

logger = logging.getLogger(__name__)
router = Router()

MIN_DEPOSIT = 10_000
MAX_DEPOSIT = 10_000_000


def _generate_qr_image(data: str) -> bytes:
    """Generate QR code image (PNG bytes) dari EMV QRIS string."""
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
    """Check apakah qr_string adalah EMV QRIS asli."""
    if not qr_string:
        return False
    if qr_string == "SANDBOX MODE":
        return False
    if len(qr_string) < 50:
        return False
    return True


def _get_deposit_confirm_keyboard(amount: int) -> InlineKeyboardMarkup:
    """Keyboard konfirmasi deposit."""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"✅ Deposit Rp {amount:,}", callback_data=f"deposit:confirm:{amount}")
    builder.button(text="❌ Batal", callback_data="deposit:cancel")
    builder.adjust(1)
    return builder.as_markup()


def _get_deposit_preset_keyboard() -> InlineKeyboardMarkup:
    """Keyboard preset nominal deposit."""
    builder = InlineKeyboardBuilder()
    presets = [10000, 25000, 50000, 100000, 200000, 500000]
    for amount in presets:
        label = f"Rp {amount:,}"
        builder.button(text=label, callback_data=f"deposit:preset:{amount}")
    builder.button(text="❌ Batal", callback_data="deposit:cancel")
    builder.adjust(3, 3, 1)
    return builder.as_markup()


# --- ENTRY: Dari menu.py "💰 Deposit" button ---
# Note: menu.py sudah handle tampilan awal deposit.
# Handler ini menangkap input nominal setelah user masuk state deposit.


@router.callback_query(F.data == "deposit:start")
async def start_deposit_flow(callback: CallbackQuery, state: FSMContext):
    """Start deposit flow via inline button."""
    await state.clear()

    deposit_svc = await get_deposit_service()
    balance = await deposit_svc.get_user_balance(callback.from_user.id)

    text = (
        "💰 <b>DEPOSIT SALDO</b>\n\n"
        f"Saldo saat ini: <b>Rp {balance:,}</b>\n\n"
        "Pilih nominal atau ketik jumlah deposit:\n"
        f"📌 Min: Rp {MIN_DEPOSIT:,}\n"
        f"📌 Max: Rp {MAX_DEPOSIT:,}\n"
    )

    await callback.message.answer(text=text, reply_markup=_get_deposit_preset_keyboard())
    await state.set_state(DepositStates.waiting_for_amount)
    await callback.answer()


# --- PRESET NOMINAL ---
@router.callback_query(DepositStates.waiting_for_amount, F.data.startswith("deposit:preset:"))
async def handle_deposit_preset(callback: CallbackQuery, state: FSMContext):
    """Handle preset nominal button."""
    amount = int(callback.data.split(":")[2])
    await state.update_data(amount=amount)

    text = (
        f"💰 <b>Konfirmasi Deposit</b>\n\n"
        f"• Nominal : <b>Rp {amount:,}</b>\n"
        f"• Metode : QRIS\n"
        f"• Fee : ~Rp 357\n\n"
        f"Lanjutkan?"
    )

    await callback.message.answer(text=text, reply_markup=_get_deposit_confirm_keyboard(amount))
    await state.set_state(DepositStates.waiting_for_confirmation)
    await callback.answer()


# --- INPUT MANUAL NOMINAL ---
@router.message(DepositStates.waiting_for_amount, F.text.regexp(r'^\d+$'))
async def handle_deposit_amount_input(message: Message, state: FSMContext):
    """Handle manual input nominal deposit."""
    amount = int(message.text)

    if amount < MIN_DEPOSIT:
        return await message.answer(
            f"⚠️ Minimal deposit <b>Rp {MIN_DEPOSIT:,}</b>.\nSilakan masukkan nominal yang valid."
        )

    if amount > MAX_DEPOSIT:
        return await message.answer(
            f"⚠️ Maksimal deposit <b>Rp {MAX_DEPOSIT:,}</b>.\nSilakan masukkan nominal yang valid."
        )

    await state.update_data(amount=amount)

    text = (
        f"💰 <b>Konfirmasi Deposit</b>\n\n"
        f"• Nominal : <b>Rp {amount:,}</b>\n"
        f"• Metode : QRIS\n"
        f"• Fee : ~Rp 357\n\n"
        f"Lanjutkan?"
    )

    await message.answer(text=text, reply_markup=_get_deposit_confirm_keyboard(amount))
    await state.set_state(DepositStates.waiting_for_confirmation)


# --- KONFIRMASI DEPOSIT ---
@router.callback_query(DepositStates.waiting_for_confirmation, F.data.startswith("deposit:confirm:"))
async def confirm_deposit(callback: CallbackQuery, state: FSMContext):
    """Process deposit setelah user konfirmasi."""
    amount = int(callback.data.split(":")[2])
    user_id = callback.from_user.id

    logger.info("[deposit] Confirm deposit: user=%s amount=%s", user_id, amount)

    # Call DepositService
    deposit_svc = await get_deposit_service()
    result = await deposit_svc.create_deposit(user_id=user_id, amount=amount)

    if not result.success:
        await callback.message.answer(
            f"❌ <b>Gagal membuat deposit</b>\n\n{result.error_message}"
        )
        await state.clear()
        await callback.answer()
        return

    # Format waktu
    now = datetime.now()
    jam_str = now.strftime("%d %b %Y pukul %H:%M")

    # Tampilkan payment details
    caption = (
        f"╭─────{{ ⏳ DEPOSIT PENDING }}─────\n"
        f"│\n"
        f"│ • Ref         : <code>{result.payment_ref}</code>\n"
        f"│ • Service     : QRIS\n"
        f"│ • Nominal     : Rp {result.amount:,}\n"
        f"│ • Fee         : Rp {result.fee:,}\n"
        f"│ • <b>Total Bayar : Rp {result.total:,}</b>\n"
        f"│ • Jam/Tanggal : {jam_str}\n"
        f"│ • Bayar sblm  : {result.expired_at or '30 menit'}\n"
    )

    if result.payment_url:
        caption += f"│ • Link        : {result.payment_url}\n"

    caption += (
        f"│\n"
        f"╰──────────────────────────────────"
    )

    # Kirim QRIS: production = QR image, sandbox = text + link
    try:
        if _is_valid_qris_string(result.qr_string):
            # PRODUCTION: Generate QR image dari EMV QRIS string asli
            qr_bytes = _generate_qr_image(result.qr_string)
            qr_photo = BufferedInputFile(qr_bytes, filename="qris_deposit.png")
            await callback.message.answer_photo(
                photo=qr_photo,
                caption=caption,
            )
        else:
            # SANDBOX: Text only + checkout link
            await callback.message.answer(text=caption)
    except Exception as e:
        logger.error("[deposit] Failed to send QRIS: %s", e)
        await callback.message.answer(text=caption)

    await state.clear()
    await callback.answer()


# --- CANCEL DEPOSIT ---
@router.callback_query(F.data == "deposit:cancel")
async def cancel_deposit(callback: CallbackQuery, state: FSMContext):
    """Cancel deposit flow."""
    logger.info("[deposit] Cancel by user_id=%s", callback.from_user.id)
    await state.clear()
    await callback.message.answer("❌ Deposit dibatalkan.")
    await callback.answer()
