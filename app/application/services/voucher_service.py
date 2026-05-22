"""
VoucherService - Business logic untuk voucher system.

Tanggung jawab:
1. Validate voucher code
2. Calculate discount
3. Apply voucher (increment usage + record)
4. Admin: create/deactivate voucher
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from app.domain.entities import Voucher
from app.domain.interfaces import VoucherRepository

logger = logging.getLogger(__name__)


@dataclass
class VoucherValidationResult:
    """Result dari validate_voucher."""
    valid: bool
    voucher: Optional[Voucher] = None
    discount: int = 0
    error_message: Optional[str] = None


class VoucherService:
    """Service untuk voucher operations."""

    def __init__(self, voucher_repo: VoucherRepository) -> None:
        self._repo = voucher_repo

    async def validate_voucher(
        self,
        code: str,
        user_id: int,
        total_price: int,
    ) -> VoucherValidationResult:
        """Validate voucher dan hitung diskon.

        Args:
            code: Kode voucher
            user_id: Telegram user ID
            total_price: Total harga sebelum diskon

        Returns:
            VoucherValidationResult
        """
        # 1. Cari voucher
        voucher = await self._repo.get_by_code(code)
        if voucher is None:
            return VoucherValidationResult(
                valid=False,
                error_message="Kode voucher tidak ditemukan.",
            )

        # 2. Check validity
        if not voucher.is_valid():
            if not voucher.is_active:
                msg = "Voucher sudah tidak aktif."
            elif voucher.used_count >= voucher.max_usage:
                msg = "Voucher sudah habis dipakai."
            else:
                msg = "Voucher sudah expired."
            return VoucherValidationResult(valid=False, error_message=msg)

        # 3. Check user sudah pernah pakai
        already_used = await self._repo.has_user_used(voucher.id, user_id)
        if already_used:
            return VoucherValidationResult(
                valid=False,
                error_message="Kamu sudah pernah menggunakan voucher ini.",
            )

        # 4. Check min purchase
        if total_price < voucher.min_purchase:
            return VoucherValidationResult(
                valid=False,
                error_message=f"Minimal pembelian Rp {voucher.min_purchase:,} untuk voucher ini.",
            )

        # 5. Calculate discount
        discount = voucher.calculate_discount(total_price)

        return VoucherValidationResult(
            valid=True,
            voucher=voucher,
            discount=discount,
        )

    async def apply_voucher(
        self,
        voucher_id: int,
        user_id: int,
        order_id: Optional[str] = None,
    ) -> bool:
        """Apply voucher (increment usage + record).

        Call ini SETELAH order berhasil dibuat.

        Returns:
            True jika berhasil, False jika gagal.
        """
        # Atomic increment
        incremented = await self._repo.increment_usage(voucher_id)
        if not incremented:
            logger.warning("[voucher] increment_usage failed: id=%s", voucher_id)
            return False

        # Record usage
        recorded = await self._repo.record_usage(voucher_id, user_id, order_id)
        if not recorded:
            logger.warning("[voucher] record_usage failed: id=%s user=%s", voucher_id, user_id)

        logger.info("[voucher] ✅ Applied: id=%s user=%s order=%s", voucher_id, user_id, order_id)
        return True

    # --- Admin operations ---

    async def create_voucher(
        self,
        code: str,
        discount_type: str,
        discount_value: int,
        min_purchase: int = 0,
        max_discount: Optional[int] = None,
        max_usage: int = 1,
        expired_at=None,
    ) -> Voucher:
        """Create voucher baru (admin only)."""
        voucher = await self._repo.create(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            min_purchase=min_purchase,
            max_discount=max_discount,
            max_usage=max_usage,
            expired_at=expired_at,
        )
        logger.info("[voucher] ✅ Created: code=%s type=%s value=%s", code, discount_type, discount_value)
        return voucher

    async def list_active_vouchers(self) -> List[Voucher]:
        """List semua voucher aktif."""
        return await self._repo.list_active()

    async def deactivate_voucher(self, voucher_id: int) -> bool:
        """Deactivate voucher."""
        result = await self._repo.deactivate(voucher_id)
        if result:
            logger.info("[voucher] ✅ Deactivated: id=%s", voucher_id)
        return result
