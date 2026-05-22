"""
Abstract interfaces untuk Bot Auto Order.

Layer ini HANYA berisi kontrak (ABC). Tidak boleh ada implementasi DB,
HTTP client, atau library framework di sini.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .entities import Product, User, Order, Voucher


class ProductRepository(ABC):
    """Kontrak akses data produk.

    Implementasi konkret ada di `app/infrastructure/database/product_repo.py`.
    """

    @abstractmethod
    async def list_paginated(
        self,
        limit: int = 10,
        offset: int = 0,
        only_active: bool = True,
    ) -> List[Product]:
        """Ambil daftar produk dengan pagination.

        Args:
            limit: Maksimal jumlah row yang dikembalikan (1..100).
            offset: Offset baris untuk pagination.
            only_active: Jika True, hanya return produk dengan `is_active = TRUE`.

        Returns:
            List[Product] - bisa kosong jika tidak ada data.
        """
        raise NotImplementedError

    @abstractmethod
    async def count(self, only_active: bool = True) -> int:
        """Hitung total produk (dipakai untuk metadata pagination)."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, product_id: int) -> Optional[Product]:
        """Ambil detail produk by ID.

        Returns:
            Product jika ditemukan, None jika tidak.
        """
        raise NotImplementedError

    @abstractmethod
    async def decrement_stock(self, product_id: int, qty: int) -> bool:
        """Kurangi stok produk secara ATOMIC (anti race condition).

        Implementasi WAJIB memakai single SQL UPDATE dengan guard
        `stock >= qty`. JANGAN load-then-update di Python.

        Args:
            product_id: ID produk.
            qty: Jumlah yang akan dikurangi (harus > 0).

        Returns:
            True  -> stok berhasil dikurangi.
            False -> stok tidak cukup / produk tidak ada / tidak aktif.
        """
        raise NotImplementedError


class UserRepository(ABC):
    """Kontrak akses data user."""

    @abstractmethod
    async def get_or_create(self, telegram_id: int) -> User:
        """Ambil user atau buat baru jika belum ada.

        Args:
            telegram_id: Telegram user ID.

        Returns:
            User entity (baru atau existing).
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, telegram_id: int) -> Optional[User]:
        """Ambil user by telegram ID."""
        raise NotImplementedError

    @abstractmethod
    async def deduct_balance(self, telegram_id: int, amount: int) -> bool:
        """Kurangi saldo user secara ATOMIC.

        Implementasi WAJIB memakai single SQL UPDATE dengan guard
        `balance >= amount`. JANGAN load-then-update di Python.

        Args:
            telegram_id: Telegram user ID.
            amount: Jumlah yang akan dikurangi (harus > 0).

        Returns:
            True  -> saldo berhasil dikurangi.
            False -> saldo tidak cukup / user tidak ada / user banned.
        """
        raise NotImplementedError

    @abstractmethod
    async def add_balance(self, telegram_id: int, amount: int) -> bool:
        """Tambah saldo user secara ATOMIC.

        Args:
            telegram_id: Telegram user ID.
            amount: Jumlah yang akan ditambah (harus > 0).

        Returns:
            True  -> saldo berhasil ditambah.
            False -> user tidak ada / user banned.
        """
        raise NotImplementedError


class OrderRepository(ABC):
    """Kontrak akses data order."""

    @abstractmethod
    async def create(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        total_price: int,
        payment_method: str,
        variant_id: Optional[int] = None,
    ) -> Order:
        """Buat order baru.

        Args:
            user_id: Telegram user ID.
            product_id: ID produk induk.
            quantity: Jumlah pembelian.
            total_price: Total harga (IDR).
            payment_method: Metode pembayaran (saldo, qris, va, dll).
            variant_id: ID variant (jika ada).

        Returns:
            Order entity (dengan ID yang sudah di-generate).
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, order_id: str) -> Optional[Order]:
        """Ambil order by ID."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Order]:
        """Ambil order user dengan pagination."""
        raise NotImplementedError

    @abstractmethod
    async def update_status(self, order_id: str, status: str) -> bool:
        """Update status order.

        Args:
            order_id: ID order.
            status: Status baru (pending, paid, shipped, delivered, cancelled).

        Returns:
            True jika berhasil, False jika order tidak ditemukan.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_payment_ref(self, order_id: str, payment_ref: str) -> bool:
        """Update payment reference dari gateway.

        Args:
            order_id: ID order.
            payment_ref: Reference dari payment gateway (Tripay).

        Returns:
            True jika berhasil, False jika order tidak ditemukan.
        """
        raise NotImplementedError


class PaymentGateway(ABC):
    """Kontrak payment gateway (Tripay, dll)."""

    @abstractmethod
    async def create_qris_deposit(self, user_id: int, amount: int) -> Dict[str, Any]:
        raise NotImplementedError


class VoucherRepository(ABC):
    """Kontrak akses data voucher."""

    @abstractmethod
    async def get_by_code(self, code: str) -> Optional[Voucher]:
        """Ambil voucher by code (case-insensitive)."""
        raise NotImplementedError

    @abstractmethod
    async def increment_usage(self, voucher_id: int) -> bool:
        """Increment used_count secara atomic.

        Returns:
            True jika berhasil (used_count < max_usage).
            False jika voucher sudah habis.
        """
        raise NotImplementedError

    @abstractmethod
    async def has_user_used(self, voucher_id: int, user_id: int) -> bool:
        """Check apakah user sudah pernah pakai voucher ini."""
        raise NotImplementedError

    @abstractmethod
    async def record_usage(self, voucher_id: int, user_id: int, order_id: Optional[str] = None) -> bool:
        """Record penggunaan voucher oleh user."""
        raise NotImplementedError

    @abstractmethod
    async def create(
        self,
        code: str,
        discount_type: str,
        discount_value: int,
        min_purchase: int = 0,
        max_discount: Optional[int] = None,
        max_usage: int = 1,
        expired_at: Optional[Any] = None,
    ) -> Voucher:
        """Create voucher baru (admin only)."""
        raise NotImplementedError

    @abstractmethod
    async def list_active(self) -> List[Voucher]:
        """List semua voucher yang masih aktif."""
        raise NotImplementedError

    @abstractmethod
    async def deactivate(self, voucher_id: int) -> bool:
        """Deactivate voucher."""
        raise NotImplementedError
