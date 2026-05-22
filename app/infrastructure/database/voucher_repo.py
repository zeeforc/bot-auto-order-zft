"""
Implementasi async VoucherRepository memakai asyncpg.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

import asyncpg

from ...domain.entities import Voucher
from ...domain.interfaces import VoucherRepository

logger = logging.getLogger(__name__)


def _row_to_voucher(row: asyncpg.Record) -> Voucher:
    """Map asyncpg.Record -> domain entity Voucher."""
    return Voucher(
        id=row["id"],
        code=row["code"],
        discount_type=row["discount_type"],
        discount_value=row["discount_value"],
        min_purchase=row["min_purchase"],
        max_discount=row["max_discount"],
        max_usage=row["max_usage"],
        used_count=row["used_count"],
        is_active=row["is_active"],
        expired_at=row["expired_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


_VOUCHER_COLUMNS = (
    "id, code, discount_type, discount_value, min_purchase, max_discount, "
    "max_usage, used_count, is_active, expired_at, created_at, updated_at"
)


class AsyncPgVoucherRepository(VoucherRepository):
    """Implementasi VoucherRepository memakai asyncpg."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_code(self, code: str) -> Optional[Voucher]:
        query = f"""
            SELECT {_VOUCHER_COLUMNS}
              FROM vouchers
             WHERE UPPER(code) = UPPER($1)
             LIMIT 1
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, code.strip())
        except asyncpg.PostgresError:
            logger.exception("get_by_code failed (code=%s)", code)
            raise
        return _row_to_voucher(row) if row else None

    async def increment_usage(self, voucher_id: int) -> bool:
        """Atomic increment used_count WHERE used_count < max_usage."""
        query = """
            UPDATE vouchers
               SET used_count = used_count + 1
             WHERE id = $1
               AND is_active = TRUE
               AND used_count < max_usage
         RETURNING id
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(voucher_id))
        except asyncpg.PostgresError:
            logger.exception("increment_usage failed (id=%s)", voucher_id)
            raise
        return row is not None

    async def has_user_used(self, voucher_id: int, user_id: int) -> bool:
        query = """
            SELECT 1 FROM voucher_usages
             WHERE voucher_id = $1 AND user_id = $2
             LIMIT 1
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(voucher_id), int(user_id))
        except asyncpg.PostgresError:
            logger.exception("has_user_used failed")
            raise
        return row is not None

    async def record_usage(self, voucher_id: int, user_id: int, order_id: Optional[str] = None) -> bool:
        query = """
            INSERT INTO voucher_usages (voucher_id, user_id, order_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (voucher_id, user_id) DO NOTHING
            RETURNING id
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(voucher_id), int(user_id), order_id)
        except asyncpg.PostgresError:
            logger.exception("record_usage failed")
            raise
        return row is not None

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
        query = f"""
            INSERT INTO vouchers (code, discount_type, discount_value, min_purchase, max_discount, max_usage, expired_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING {_VOUCHER_COLUMNS}
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    query, code.upper(), discount_type, int(discount_value),
                    int(min_purchase), max_discount, int(max_usage), expired_at,
                )
        except asyncpg.PostgresError:
            logger.exception("create voucher failed (code=%s)", code)
            raise
        return _row_to_voucher(row)

    async def list_active(self) -> List[Voucher]:
        query = f"""
            SELECT {_VOUCHER_COLUMNS}
              FROM vouchers
             WHERE is_active = TRUE
             ORDER BY created_at DESC
        """
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
        except asyncpg.PostgresError:
            logger.exception("list_active failed")
            raise
        return [_row_to_voucher(r) for r in rows]

    async def deactivate(self, voucher_id: int) -> bool:
        query = """
            UPDATE vouchers SET is_active = FALSE WHERE id = $1 RETURNING id
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(voucher_id))
        except asyncpg.PostgresError:
            logger.exception("deactivate failed (id=%s)", voucher_id)
            raise
        return row is not None


# ======================================================================
# FALLBACK: Mock repository
# ======================================================================

class MockVoucherRepository(VoucherRepository):
    """Mock voucher repository untuk dev tanpa DB."""

    def __init__(self) -> None:
        self._vouchers: dict[int, Voucher] = {
            1: Voucher(id=1, code="WELCOME10", discount_type="percent", discount_value=10, max_usage=100, max_discount=50000),
            2: Voucher(id=2, code="DISKON5K", discount_type="fixed", discount_value=5000, max_usage=50),
        }
        self._usages: set[tuple[int, int]] = set()
        self._next_id = 3

    async def get_by_code(self, code: str) -> Optional[Voucher]:
        for v in self._vouchers.values():
            if v.code.upper() == code.upper().strip():
                return v
        return None

    async def increment_usage(self, voucher_id: int) -> bool:
        v = self._vouchers.get(voucher_id)
        if not v or not v.is_active or v.used_count >= v.max_usage:
            return False
        v.used_count += 1
        return True

    async def has_user_used(self, voucher_id: int, user_id: int) -> bool:
        return (voucher_id, user_id) in self._usages

    async def record_usage(self, voucher_id: int, user_id: int, order_id: Optional[str] = None) -> bool:
        key = (voucher_id, user_id)
        if key in self._usages:
            return False
        self._usages.add(key)
        return True

    async def create(self, code: str, discount_type: str, discount_value: int,
                     min_purchase: int = 0, max_discount: Optional[int] = None,
                     max_usage: int = 1, expired_at: Optional[Any] = None) -> Voucher:
        v = Voucher(
            id=self._next_id, code=code.upper(), discount_type=discount_type,
            discount_value=discount_value, min_purchase=min_purchase,
            max_discount=max_discount, max_usage=max_usage, expired_at=expired_at,
        )
        self._vouchers[self._next_id] = v
        self._next_id += 1
        return v

    async def list_active(self) -> List[Voucher]:
        return [v for v in self._vouchers.values() if v.is_active]

    async def deactivate(self, voucher_id: int) -> bool:
        v = self._vouchers.get(voucher_id)
        if not v:
            return False
        v.is_active = False
        return True
