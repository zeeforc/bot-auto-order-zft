"""
Handler untuk voucher system.

User commands:
  - Ketik kode voucher saat checkout (di order flow)
  - /voucher <code> - Check voucher info

Admin commands (di admin.py):
  - /addvoucher - Create voucher baru
  - /listvoucher - List voucher aktif
  - /delvoucher <id> - Deactivate voucher
"""
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.application.services.factory import get_voucher_service

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("voucher"))
async def cmd_voucher(message: Message):
    """Check voucher info: /voucher KODE"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📋 <b>Cara pakai voucher:</b>\n\n"
            "Ketik: <code>/voucher KODE</code>\n"
            "Contoh: <code>/voucher WELCOME10</code>\n\n"
            "💡 Voucher akan otomatis di-apply saat checkout."
        )
        return

    code = args[1].strip().upper()
    logger.info("[voucher] Check code=%s by user_id=%s", code, message.from_user.id)

    voucher_svc = await get_voucher_service()

    # Validate dengan dummy price untuk info
    result = await voucher_svc.validate_voucher(
        code=code,
        user_id=message.from_user.id,
        total_price=100000,  # Dummy untuk check validity
    )

    if not result.valid:
        await message.answer(f"❌ {result.error_message}")
        return

    v = result.voucher
    discount_text = (
        f"Rp {v.discount_value:,}" if v.discount_type == "fixed"
        else f"{v.discount_value}%"
    )
    max_disc = f" (max Rp {v.max_discount:,})" if v.max_discount else ""
    min_text = f"Rp {v.min_purchase:,}" if v.min_purchase > 0 else "Tidak ada"
    remaining = v.max_usage - v.used_count

    text = (
        f"🎫 <b>VOUCHER: {v.code}</b>\n\n"
        f"• Diskon: {discount_text}{max_disc}\n"
        f"• Min. Pembelian: {min_text}\n"
        f"• Sisa Kuota: {remaining}x\n"
        f"• Status: {'✅ Aktif' if v.is_valid() else '❌ Tidak Aktif'}\n\n"
        f"💡 Voucher akan otomatis di-apply saat checkout."
    )
    await message.answer(text)
