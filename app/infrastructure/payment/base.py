"""
Base classes untuk Payment Provider (multi-gateway support).

Semua provider (Tripay, Pakasir, dll) harus implement PaymentProvider ABC.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class PaymentResult:
    """Hasil dari create_payment — generic untuk semua gateway."""
    success: bool
    # Payment info (jika success=True)
    reference: str = ""           # ID transaksi dari gateway
    merchant_ref: str = ""        # ID order kita
    qr_string: str = ""           # EMV QRIS string (untuk generate QR image)
    checkout_url: str = ""        # URL checkout (fallback kalau QR ga bisa)
    amount: int = 0               # Nominal asli
    fee: int = 0                  # Fee yang ditanggung
    total_amount: int = 0         # Total yang user bayar (amount + fee)
    expired_at: Optional[str] = None  # ISO datetime string
    payment_method: str = ""      # qris, bni_va, dll
    # Error info (jika success=False)
    error: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CallbackData:
    """Data dari webhook callback — generic untuk semua gateway."""
    order_id: str
    amount: int
    status: str              # "completed" / "paid" / "expired" / "failed"
    payment_method: str = ""
    completed_at: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    """Abstract base class untuk payment gateway provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nama provider (untuk display)."""
        ...

    @abstractmethod
    async def create_payment(
        self,
        order_id: str,
        amount: int,
        product_name: str = "",
        user_id: int = 0,
    ) -> PaymentResult:
        """Buat transaksi pembayaran baru.

        Args:
            order_id: ID order dari sistem kita
            amount: Nominal yang harus dibayar (IDR)
            product_name: Nama produk (untuk display di gateway)
            user_id: Telegram user ID

        Returns:
            PaymentResult dengan QR string / checkout URL
        """
        ...

    @abstractmethod
    async def create_deposit(
        self,
        user_id: int,
        amount: int,
    ) -> PaymentResult:
        """Buat transaksi deposit saldo.

        Args:
            user_id: Telegram user ID
            amount: Nominal deposit (IDR)

        Returns:
            PaymentResult
        """
        ...

    @abstractmethod
    async def verify_callback(self, data: Dict[str, Any]) -> CallbackData | None:
        """Verify dan parse webhook callback.

        Args:
            data: Raw body dari webhook POST

        Returns:
            CallbackData jika valid, None jika invalid/gagal verify
        """
        ...

    @abstractmethod
    async def cancel_transaction(self, order_id: str, amount: int) -> bool:
        """Cancel transaksi yang masih pending.

        Returns:
            True jika berhasil cancel
        """
        ...

    async def simulate_payment(self, order_id: str, amount: int) -> bool:
        """Simulasi pembayaran (sandbox mode). Default: not supported."""
        return False
