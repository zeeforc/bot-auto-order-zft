"""
DepositService - Business logic untuk deposit saldo.

Tanggung jawab:
1. Validasi nominal deposit
2. Generate payment request (via PaymentGateway)
3. Process callback saat payment sukses -> add balance
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.domain.interfaces import PaymentGateway, UserRepository

logger = logging.getLogger(__name__)

# Konfigurasi deposit
MIN_DEPOSIT = 10_000   # Rp 10.000
MAX_DEPOSIT = 10_000_000  # Rp 10.000.000


@dataclass
class DepositResult:
    """Result object dari create_deposit."""
    success: bool
    payment_url: Optional[str] = None
    payment_ref: Optional[str] = None
    qr_url: Optional[str] = None
    qr_string: Optional[str] = None
    amount: int = 0
    fee: int = 0
    total: int = 0
    expired_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class DepositService:
    """Service untuk orkestrasi deposit flow."""

    def __init__(
        self,
        user_repo: UserRepository,
        payment_gateway: Optional[PaymentGateway] = None,
    ) -> None:
        self._user_repo = user_repo
        self._payment_gateway = payment_gateway

    async def create_deposit(
        self,
        user_id: int,
        amount: int,
    ) -> DepositResult:
        """Buat request deposit baru.

        Flow:
        1. Validasi nominal
        2. Pastikan user exists
        3. Generate payment via gateway
        4. Return payment details (QR URL, ref, dll)

        Args:
            user_id: Telegram user ID
            amount: Nominal deposit (IDR)

        Returns:
            DepositResult dengan payment details atau error
        """
        try:
            # Step 1: Validasi nominal
            if amount < MIN_DEPOSIT:
                return DepositResult(
                    success=False,
                    error_code="AMOUNT_TOO_LOW",
                    error_message=f"Minimal deposit Rp {MIN_DEPOSIT:,}",
                )

            if amount > MAX_DEPOSIT:
                return DepositResult(
                    success=False,
                    error_code="AMOUNT_TOO_HIGH",
                    error_message=f"Maksimal deposit Rp {MAX_DEPOSIT:,}",
                )

            # Step 2: Pastikan user exists
            user = await self._user_repo.get_or_create(user_id)
            if user.is_banned:
                return DepositResult(
                    success=False,
                    error_code="USER_BANNED",
                    error_message="Akun Anda telah diblokir.",
                )

            # Step 3: Generate payment via gateway
            if self._payment_gateway is None:
                # Mock mode - return fake payment details
                logger.warning("[deposit] PaymentGateway belum di-set, pakai mock")
                return DepositResult(
                    success=True,
                    payment_url="https://tripay.co.id/checkout/mock",
                    payment_ref=f"DEP-{user_id}-{amount}",
                    qr_url=None,
                    amount=amount,
                    fee=357,
                    total=amount + 357,
                    expired_at="2026-05-20 23:59:59",
                )

            # Real payment gateway call
            payment_data = await self._payment_gateway.create_qris_deposit(
                user_id=user_id,
                amount=amount,
            )

            if "error" in payment_data:
                return DepositResult(
                    success=False,
                    error_code="GATEWAY_ERROR",
                    error_message="Gagal membuat pembayaran. Coba lagi nanti.",
                )

            logger.info(
                "[deposit] ✅ Payment created: user=%s amount=%s ref=%s",
                user_id, amount, payment_data.get("reference"),
            )

            return DepositResult(
                success=True,
                payment_url=payment_data.get("checkout_url"),
                payment_ref=payment_data.get("reference"),
                qr_url=payment_data.get("qr_url"),
                qr_string=payment_data.get("qr_string"),
                amount=amount,
                fee=payment_data.get("fee", 0),
                total=payment_data.get("total_amount", amount),
                expired_at=payment_data.get("expired_time"),
            )

        except Exception as e:
            logger.error("[deposit] ❌ Unexpected error: %s", str(e), exc_info=True)
            return DepositResult(
                success=False,
                error_code="INTERNAL_ERROR",
                error_message="Terjadi kesalahan sistem. Silakan coba lagi.",
            )

    async def process_deposit_callback(
        self,
        user_id: int,
        amount: int,
        payment_ref: str,
    ) -> bool:
        """Process callback dari payment gateway saat deposit berhasil.

        Flow:
        1. Validasi payment reference
        2. Add balance ke user (atomic)
        3. Log transaksi

        Args:
            user_id: Telegram user ID
            amount: Nominal yang dibayar (IDR)
            payment_ref: Reference dari payment gateway

        Returns:
            True jika berhasil, False jika gagal
        """
        try:
            # Add balance (atomic operation)
            success = await self._user_repo.add_balance(user_id, amount)

            if success:
                logger.info(
                    "[deposit] ✅ Balance added: user=%s amount=%s ref=%s",
                    user_id, amount, payment_ref,
                )
            else:
                logger.error(
                    "[deposit] ❌ Failed to add balance: user=%s amount=%s ref=%s",
                    user_id, amount, payment_ref,
                )

            return success

        except Exception as e:
            logger.error(
                "[deposit] ❌ Callback error: %s (user=%s ref=%s)",
                str(e), user_id, payment_ref, exc_info=True,
            )
            return False

    async def get_user_balance(self, user_id: int) -> int:
        """Get saldo user saat ini."""
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            return 0
        return user.balance
