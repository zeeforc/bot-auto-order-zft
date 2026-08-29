"""
OrderService - Business logic untuk eksekusi order.

Tanggung jawab:
1. Validasi stok & saldo
2. Deduct stok (atomic)
3. Deduct saldo (atomic) - jika metode saldo
4. Create order record di DB
5. Return result (success/fail + detail)
6. Generate unique amount untuk GoPay (anti-collision)
7. Process GoPay webhook payment (match amount → PAID → deliver)

Semua operasi atomic di level DB, bukan di Python.
"""
from __future__ import annotations

import logging
import random
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
        order_repo: OrderRepository,
        user_repo: UserRepository,
        product_repo: ProductRepository,
    ) -> None:
        self._order_repo = order_repo
        self._user_repo = user_repo
        self._product_repo = product_repo
        self._payment_locks: dict[int, float] = {}

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

            # Real-time stock check dari account_stock (bukan cached product.stock)
            real_stock = await self._get_real_stock(product_id, variant_id)
            if real_stock < quantity:
                return OrderResult(
                    success=False,
                    error_code="INSUFFICIENT_STOCK",
                    error_message=f"Stok tidak cukup. Tersisa {real_stock}.",
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
        price_per_item = product.price
        if quantity >= 200:
            price_per_item = int(product.price * 0.9)
        return price_per_item * quantity

    async def _get_real_stock(self, product_id: int, variant_id: int | None) -> int:
        """Get real-time stock dari account_stock table (bukan cached).

        Ini lebih akurat daripada product.stock karena langsung count
        akun yang available di pool.
        """
        try:
            from app.infrastructure.database.connection import get_pool
            pool = get_pool()
            if not pool:
                return 999  # Fallback: allow order jika DB ga reachable

            async with pool.acquire() as conn:
                if variant_id:
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM account_stock WHERE variant_id = $1 AND is_used = FALSE",
                        int(variant_id),
                    )
                else:
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM account_stock WHERE product_id = $1 AND is_used = FALSE",
                        int(product_id),
                    )
                return int(count) if count else 0
        except Exception as e:
            logger.warning("[order] _get_real_stock error: %s (fallback to allow)", e)
            return 999  # Fallback: allow order, delivery will handle "akun belum tersedia"

    # ======================================================================
    # GoPay Custom QRIS — Unique Amount & Webhook Processing
    # ======================================================================

    async def acquire_payment_lock(self, amount: int, duration_minutes: int = 15) -> bool:
        """Acquire in-memory lock untuk nominal pas (GoPay QRIS).
        
        Mencegah dua user checkout dengan nominal yang sama persis dalam
        waktu yang bersamaan.
        
        Args:
            amount: Nominal yang akan dilock.
            duration_minutes: Durasi lock dalam menit.
            
        Returns:
            True jika berhasil dilock, False jika sedang dilock orang lain.
        """
        import time
        now = time.time()
        
        # Bersihkan lock yang expired
        expired_keys = [k for k, v in self._payment_locks.items() if v < now]
        for k in expired_keys:
            del self._payment_locks[k]
            
        if amount in self._payment_locks:
            return False  # Masih dilock
            
        self._payment_locks[amount] = now + (duration_minutes * 60)
        logger.info("[order] 🔒 Lock acquired for amount=%s (duration=%sm)", amount, duration_minutes)
        return True
        
    def release_payment_lock(self, amount: int) -> None:
        """Release in-memory lock untuk nominal tertentu."""
        if amount in self._payment_locks:
            del self._payment_locks[amount]
            logger.info("[order] 🔓 Lock released for amount=%s", amount)

    async def process_gopay_webhook(self, amount: int) -> Optional[Order]:
        """Match pembayaran GoPay dengan pending order berdasarkan amount.

        Flow (ATOMIC / Transactional):
        1. SELECT pending order dengan total_price = amount & method = 'gopay'
        2. UPDATE status → 'paid'
        3. Return order untuk delivery + notification di caller

        Args:
            amount: Nominal yang dibayar (dari notifikasi GoPay, sudah di-parse).

        Returns:
            Order jika match ditemukan dan berhasil di-update.
            None jika tidak ada pending order yang cocok.
        """
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            logger.error("[order] process_gopay_webhook: DB pool unavailable")
            return None

        try:
            async with pool.acquire() as conn:
                # Atomic transaction: select + update dalam satu koneksi
                async with conn.transaction():
                    # 1. Cari pending order yang match (FIFO: oldest first)
                    row = await conn.fetchrow(
                        """
                        SELECT id, user_id, product_id, quantity, total_price,
                               status, payment_method, payment_ref, variant_id,
                               created_at, updated_at
                        FROM orders
                        WHERE total_price = $1
                          AND status = 'pending'
                          AND payment_method = 'gopay'
                        ORDER BY created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                        """,
                        amount,
                    )

                    if not row:
                        logger.info(
                            "[order] GoPay webhook: no pending order for amount=%s",
                            amount,
                        )
                        return None

                    order_id = row["id"]

                    # 2. Update status → paid (atomic)
                    await conn.execute(
                        """
                        UPDATE orders
                        SET status = 'paid', updated_at = NOW()
                        WHERE id = $1
                        """,
                        order_id,
                    )

                    logger.info(
                        "[order] ✅ GoPay webhook matched: order_id=%s amount=%s user=%s",
                        order_id, amount, row["user_id"],
                    )

                    # 3. Return Order entity
                    return Order(
                        id=row["id"],
                        user_id=row["user_id"],
                        product_id=row["product_id"],
                        quantity=row["quantity"],
                        total_price=row["total_price"],
                        status="paid",
                        payment_method=row["payment_method"],
                        payment_ref=row["payment_ref"],
                        variant_id=row["variant_id"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )

        except Exception as e:
            logger.error(
                "[order] ❌ process_gopay_webhook error: %s (amount=%s)",
                e, amount, exc_info=True,
            )
            return None
