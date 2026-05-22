"""
OrderService - Business logic untuk eksekusi order.

Tanggung jawab:
1. Validasi stok & saldo
2. Deduct stok (atomic)
3. Deduct saldo (atomic) - jika metode saldo
4. Create order record di DB
5. Return result (success/fail + detail)

Semua operasi atomic di level DB, bukan di Python.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.domain.entities import Order, Product, User
from app.domain.interfaces import OrderRepository, ProductRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """Result object dari execute_order."""
    success: bool
    order: Optional[Order] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class OrderService:
    """Service untuk orkestrasi order flow.

    Menggunakan repository pattern - tidak tahu detail DB implementation.
    Semua operasi kritis (stok, saldo) dilakukan atomic di level repository.
    """

    def __init__(
        self,
        product_repo: ProductRepository,
        user_repo: UserRepository,
        order_repo: OrderRepository,
    ) -> None:
        self._product_repo = product_repo
        self._user_repo = user_repo
        self._order_repo = order_repo

    async def execute_order(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        payment_method: str,
        variant_id: int | None = None,
        unit_price: int | None = None,
    ) -> OrderResult:
        """Eksekusi order lengkap.

        Args:
            user_id: Telegram user ID
            product_id: ID produk induk
            quantity: Jumlah pembelian
            payment_method: 'saldo' atau 'now' (QRIS)
            variant_id: ID variant (jika ada)
            unit_price: Override harga per unit (untuk variant pricing)
        """
        try:
            # Step 1: Validasi produk
            product = await self._product_repo.get_by_id(product_id)
            if product is None:
                return OrderResult(
                    success=False,
                    error_code="PRODUCT_NOT_FOUND",
                    error_message="Produk tidak ditemukan.",
                )

            if not product.is_available():
                return OrderResult(
                    success=False,
                    error_code="PRODUCT_UNAVAILABLE",
                    error_message="Produk sedang tidak tersedia.",
                )

            if product.stock < quantity:
                return OrderResult(
                    success=False,
                    error_code="INSUFFICIENT_STOCK",
                    error_message=f"Stok tidak cukup. Tersisa {product.stock}.",
                )

            # Step 2: Hitung total harga (pakai unit_price jika ada, fallback ke product.price)
            if unit_price is not None:
                total_price = unit_price * quantity
            else:
                total_price = self._calculate_total(product, quantity)

            # Step 3: Jika bayar pakai saldo, deduct dulu
            if payment_method == "saldo":
                balance_deducted = await self._user_repo.deduct_balance(user_id, total_price)
                if not balance_deducted:
                    return OrderResult(
                        success=False,
                        error_code="INSUFFICIENT_BALANCE",
                        error_message="Saldo tidak cukup untuk melakukan pembelian.",
                    )

            # Step 4: Skip product-level stock deduction
            # Stock is computed dynamically from account_stock count.
            # delivery_service akan handle pengambilan akun + mark used.

            # Step 5: Create order record (with variant_id)
            order_status = "paid" if payment_method == "saldo" else "pending"
            order = await self._order_repo.create(
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                total_price=total_price,
                payment_method=payment_method,
                variant_id=variant_id,
            )

            # Update status jika saldo (langsung paid)
            if payment_method == "saldo":
                await self._order_repo.update_status(order.id, "paid")

            logger.info(
                "[order] ✅ Order sukses: order_id=%s user=%s product=%s variant=%s qty=%s total=%s method=%s",
                order.id, user_id, product_id, variant_id, quantity, total_price, payment_method,
            )

            return OrderResult(success=True, order=order)

        except Exception as e:
            logger.error("[order] ❌ Unexpected error: %s", str(e), exc_info=True)
            return OrderResult(
                success=False,
                error_code="INTERNAL_ERROR",
                error_message="Terjadi kesalahan sistem. Silakan coba lagi nanti.",
            )

    async def get_user_balance(self, user_id: int) -> int:
        """Get saldo user saat ini."""
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            return 0
        return user.balance

    async def get_product_detail(self, product_id: int) -> Optional[Product]:
        """Get detail produk."""
        return await self._product_repo.get_by_id(product_id)

    def _calculate_total(self, product: Product, quantity: int) -> int:
        """Hitung total harga dengan logika grosir.

        Rule: qty >= 200 pakai harga grosir (diskon ~10%).
        Untuk sekarang, grosir = price * 0.9 (bisa di-customize nanti).
        """
        # TODO: Harga grosir bisa disimpan di DB nanti
        # Untuk sekarang pakai simple discount 10% untuk qty >= 200
        price_per_item = product.price
        if quantity >= 200:
            price_per_item = int(product.price * 0.9)  # 10% discount
        return price_per_item * quantity
