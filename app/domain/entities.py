"""
Enterprise business rules untuk Bot Auto Order
Domain models: User, Product, Order

Catatan:
- Semua nilai uang (balance, price) memakai `int` dalam satuan Rupiah (IDR)
  tanpa desimal. Hindari `float` untuk uang.
- Entity di sini hanya menampung data + business rule kecil. Akses DB
  ditangani di layer infrastructure.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class User:
    """User entity - Business rules untuk user."""
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    balance: int = 0  # IDR
    is_banned: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_new(self) -> bool:
        """Check if user is newly created (today)."""
        return (datetime.now() - self.created_at).days == 0


@dataclass
class Product:
    """Product entity - Business rules untuk product."""
    id: int
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    category: Optional[str] = None
    price: int = 0          # IDR
    stock: int = 0
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_available(self) -> bool:
        """Business rule: produk dapat dibeli jika aktif & stok > 0."""
        return self.is_active and self.stock > 0


@dataclass
class Order:
    """Order entity - Business rules untuk order."""
    id: str
    user_id: int
    product_id: int
    quantity: int
    total_price: int
    status: str  # pending, paid, shipped, delivered, cancelled
    payment_method: Optional[str] = None
    payment_ref: Optional[str] = None
    variant_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def can_cancel(self) -> bool:
        """Business rule: hanya bisa cancel kalau belum dibayar."""
        return self.status == "pending"

    def mark_paid(self) -> None:
        """Mark order as paid."""
        if self.status == "pending":
            self.status = "paid"
            self.updated_at = datetime.now()


@dataclass
class Voucher:
    """Voucher entity - Business rules untuk voucher/diskon."""
    id: int
    code: str
    discount_type: str  # 'fixed' atau 'percent'
    discount_value: int  # IDR (fixed) atau persen (percent)
    min_purchase: int = 0
    max_discount: Optional[int] = None  # Batas max diskon untuk percent type
    max_usage: int = 1
    used_count: int = 0
    is_active: bool = True
    expired_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def is_valid(self) -> bool:
        """Check apakah voucher masih valid."""
        if not self.is_active:
            return False
        if self.used_count >= self.max_usage:
            return False
        if self.expired_at and datetime.now() > self.expired_at:
            return False
        return True

    def calculate_discount(self, total_price: int) -> int:
        """Hitung diskon berdasarkan type dan value.

        Returns:
            Jumlah diskon (IDR). 0 jika tidak memenuhi min_purchase.
        """
        if total_price < self.min_purchase:
            return 0

        if self.discount_type == "fixed":
            return min(self.discount_value, total_price)
        elif self.discount_type == "percent":
            discount = int(total_price * self.discount_value / 100)
            if self.max_discount:
                discount = min(discount, self.max_discount)
            return min(discount, total_price)
        return 0
