"""
Implementasi async OrderRepository memakai asyncpg.

Order ID di-generate sebagai UUID atau nanoid di aplikasi, bukan auto-increment.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import uuid4

import asyncpg

from ...domain.entities import Order
from ...domain.interfaces import OrderRepository

logger = logging.getLogger(__name__)

_ORDER_COLUMNS = (
    "id, user_id, product_id, variant_id, quantity, total_price, status, "
    "payment_method, payment_ref, created_at, updated_at"
)


def _row_to_order(row: asyncpg.Record) -> Order:
    """Map asyncpg.Record -> domain entity Order."""
    return Order(
        id=row["id"],
        user_id=row["user_id"],
        product_id=row["product_id"],
        variant_id=row["variant_id"] if "variant_id" in row else None,
        quantity=row["quantity"],
        total_price=row["total_price"],
        status=row["status"],
        payment_method=row["payment_method"],
        payment_ref=row["payment_ref"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class AsyncPgOrderRepository(OrderRepository):
    """Implementasi OrderRepository memakai asyncpg connection pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    async def create(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        total_price: int,
        payment_method: str,
        variant_id: int | None = None,
    ) -> Order:
        """Buat order baru."""
        order_id = str(uuid4())

        query = f"""
            INSERT INTO orders (id, user_id, product_id, variant_id, quantity, total_price, status, payment_method)
            VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
            RETURNING {_ORDER_COLUMNS}
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    query,
                    order_id,
                    int(user_id),
                    int(product_id),
                    int(variant_id) if variant_id is not None else None,
                    int(quantity),
                    int(total_price),
                    payment_method,
                )
        except asyncpg.PostgresError:
            logger.exception(
                "create failed (user_id=%s product_id=%s variant=%s qty=%s)",
                user_id,
                product_id,
                variant_id,
                quantity,
            )
            raise

        return _row_to_order(row)

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------
    async def get_by_id(self, order_id: str) -> Optional[Order]:
        """Ambil order by ID."""
        query = f"""
            SELECT {_ORDER_COLUMNS}
              FROM orders
             WHERE id = $1
             LIMIT 1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, str(order_id))
        except asyncpg.PostgresError:
            logger.exception("get_by_id failed (order_id=%s)", order_id)
            raise

        return _row_to_order(row) if row else None

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Order]:
        """Ambil order user dengan pagination."""
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))

        query = f"""
            SELECT {_ORDER_COLUMNS}
              FROM orders
             WHERE user_id = $1
             ORDER BY created_at DESC
             LIMIT $2 OFFSET $3
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, int(user_id), limit, offset)
        except asyncpg.PostgresError:
            logger.exception("get_by_user failed (user_id=%s)", user_id)
            raise

        return [_row_to_order(r) for r in rows]

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------
    async def update_status(self, order_id: str, status: str) -> bool:
        """Update status order."""
        valid_statuses = {"pending", "paid", "shipped", "delivered", "cancelled", "refunded"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")

        query = """
            UPDATE orders
               SET status = $2
             WHERE id = $1
         RETURNING id
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, str(order_id), status)
        except asyncpg.PostgresError:
            logger.exception("update_status failed (order_id=%s status=%s)", order_id, status)
            raise

        success = row is not None
        if not success:
            logger.info("update_status: order not found (order_id=%s)", order_id)
        return success

    async def update_payment_ref(self, order_id: str, payment_ref: str) -> bool:
        """Update payment reference dari gateway."""
        query = """
            UPDATE orders
               SET payment_ref = $2
             WHERE id = $1
         RETURNING id
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, str(order_id), payment_ref)
        except asyncpg.PostgresError:
            logger.exception("update_payment_ref failed (order_id=%s)", order_id)
            raise

        return row is not None


# ======================================================================
# FALLBACK: In-memory mock repository
# ======================================================================

class MockOrderRepository(OrderRepository):
    """Fallback repository pakai in-memory dict (untuk dev tanpa DB)."""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    async def create(
        self,
        user_id: int,
        product_id: int,
        quantity: int,
        total_price: int,
        payment_method: str,
        variant_id: int | None = None,
    ) -> Order:
        """Buat order baru."""
        order_id = str(uuid4())
        order = Order(
            id=order_id,
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            total_price=total_price,
            status="pending",
            payment_method=payment_method,
        )
        self._orders[order_id] = order
        return order

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        """Ambil order by ID."""
        return self._orders.get(str(order_id))

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Order]:
        """Ambil order user dengan pagination."""
        user_orders = [o for o in self._orders.values() if o.user_id == user_id]
        user_orders.sort(key=lambda o: o.created_at, reverse=True)
        return user_orders[offset : offset + limit]

    async def update_status(self, order_id: str, status: str) -> bool:
        """Update status order."""
        valid_statuses = {"pending", "paid", "shipped", "delivered", "cancelled", "refunded"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}")

        order = self._orders.get(str(order_id))
        if not order:
            return False

        order.status = status
        return True

    async def update_payment_ref(self, order_id: str, payment_ref: str) -> bool:
        """Update payment reference."""
        order = self._orders.get(str(order_id))
        if not order:
            return False

        order.payment_ref = payment_ref
        return True
