"""
Handler untuk voucher system.

User commands:
  - /voucher <code> - Check & activate voucher untuk checkout berikutnya

Admin commands (di admin.py):
  - /addvoucher - Create voucher baru
  - /listvoucher - List voucher aktif
  - /delvoucher <id> - Deactivate voucher
"""
import logging
from typing import Dict, Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.application.services.factory import get_voucher_service

logger = logging.getLogger(__name__)
router = Router()

# In-memory: user_id → voucher code yang aktif (belum dipakai)
_active_vouchers: Dict[int, str] = {}


def get_user_voucher(user_id: int) -> Optional[str]:
    """Get active voucher code untuk user (dipanggil dari order flow)."""
    return _active_vouchers.get(user_id)


def clear_user_voucher(user_id: int) -> None:
    """Clear voucher setelah dipakai (dipanggil dari order flow)."""
    _active_vouchers.pop(user_id, None)


@router.message(Command("voucher"))
async def cmd_voucher(message: Message):
    """Check voucher info & activate: /voucher KODE"""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📋 <b>Cara pakai voucher:</b>\n\n"
            "Ketik: /voucher KODE\n"
            "Contoh: /voucher WELCOME10\n\n"
            "💡 Voucher akan otomatis di-apply saat checkout berikutnya."
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

    # Activate voucher untuk user ini
    _active_vouchers[message.from_user.id] = code

    text = (
        f"🎫 <b>VOUCHER: {v.code}</b>\n\n"
        f"• Diskon: {discount_text}{max_disc}\n"
        f"• Min. Pembelian: {min_text}\n"
        f"• Sisa Kuota: {remaining}x\n"
        f"• Status: ✅ Aktif\n\n"
        f"✅ Voucher aktif! Diskon otomatis di-apply saat checkout berikutnya."
    )
    await message.answer(text)
