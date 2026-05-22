"""
Implementasi async UserRepository memakai asyncpg.

Race condition handling:
- Balance deduction: UPDATE users SET balance = balance - $2 WHERE telegram_id = $1 AND balance >= $2
- Balance addition: UPDATE users SET balance = balance + $2 WHERE telegram_id = $1 AND NOT is_banned
"""
from __future__ import annotations

import logging
from typing import Optional

import asyncpg

from ...domain.entities import User
from ...domain.interfaces import UserRepository

logger = logging.getLogger(__name__)

_USER_COLUMNS = (
    "telegram_id, username, first_name, last_name, phone, balance, is_banned, "
    "created_at, updated_at"
)


def _row_to_user(row: asyncpg.Record) -> User:
    """Map asyncpg.Record -> domain entity User."""
    return User(
        telegram_id=row["telegram_id"],
        username=row["username"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        phone=row["phone"],
        balance=row["balance"],
        is_banned=row["is_banned"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class AsyncPgUserRepository(UserRepository):
    """Implementasi UserRepository memakai asyncpg connection pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------
    async def get_or_create(self, telegram_id: int) -> User:
        """Ambil user atau buat baru jika belum ada."""
        query = f"""
            SELECT {_USER_COLUMNS}
              FROM users
             WHERE telegram_id = $1
             LIMIT 1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(telegram_id))

                if row:
                    return _row_to_user(row)

                # User belum ada, buat baru
                insert_query = """
                    INSERT INTO users (telegram_id, balance, is_banned)
                    VALUES ($1, 0, FALSE)
                    RETURNING """ + _USER_COLUMNS
                new_row = await conn.fetchrow(insert_query, int(telegram_id))
                return _row_to_user(new_row)

        except asyncpg.PostgresError:
            logger.exception("get_or_create failed (telegram_id=%s)", telegram_id)
            raise

    async def get_by_id(self, telegram_id: int) -> Optional[User]:
        """Ambil user by telegram ID."""
        query = f"""
            SELECT {_USER_COLUMNS}
              FROM users
             WHERE telegram_id = $1
             LIMIT 1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(telegram_id))
        except asyncpg.PostgresError:
            logger.exception("get_by_id failed (telegram_id=%s)", telegram_id)
            raise

        return _row_to_user(row) if row else None

    # ------------------------------------------------------------------
    # WRITE - ATOMIC
    # ------------------------------------------------------------------
    async def deduct_balance(self, telegram_id: int, amount: int) -> bool:
        """Kurangi saldo user secara atomic.

        --- LOGIKA KRITIS ---
        SATU statement UPDATE dengan guard `balance >= amount` dan `NOT is_banned`.
        Postgres akan memegang row-lock selama UPDATE, sehingga concurrent UPDATE
        pada row yang sama akan dijalankan serial. Yang gagal match langsung
        mengembalikan 0 row -> kita return False.
        """
        if amount <= 0:
            raise ValueError("amount harus > 0")

        query = """
            UPDATE users
               SET balance = balance - $2
             WHERE telegram_id = $1
               AND NOT is_banned
               AND balance >= $2
         RETURNING telegram_id
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(telegram_id), int(amount))
        except asyncpg.PostgresError:
            logger.exception(
                "deduct_balance failed (telegram_id=%s amount=%s)", telegram_id, amount
            )
            raise

        success = row is not None
        if not success:
            logger.info(
                "deduct_balance rejected (telegram_id=%s amount=%s) - "
                "saldo tidak cukup / user banned / user tidak ada",
                telegram_id,
                amount,
            )
        return success

    async def add_balance(self, telegram_id: int, amount: int) -> bool:
        """Tambah saldo user secara atomic."""
        if amount <= 0:
            raise ValueError("amount harus > 0")

        query = """
            UPDATE users
               SET balance = balance + $2
             WHERE telegram_id = $1
               AND NOT is_banned
         RETURNING telegram_id
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(telegram_id), int(amount))
        except asyncpg.PostgresError:
            logger.exception(
                "add_balance failed (telegram_id=%s amount=%s)", telegram_id, amount
            )
            raise

        success = row is not None
        if not success:
            logger.info(
                "add_balance rejected (telegram_id=%s amount=%s) - "
                "user banned / user tidak ada",
                telegram_id,
                amount,
            )
        return success


# ======================================================================
# FALLBACK: In-memory mock repository
# ======================================================================

class MockUserRepository(UserRepository):
    """Fallback repository pakai in-memory dict (untuk dev tanpa DB)."""

    def __init__(self) -> None:
        self._users: dict[int, User] = {}

    async def get_or_create(self, telegram_id: int) -> User:
        """Ambil atau buat user baru."""
        if telegram_id not in self._users:
            self._users[telegram_id] = User(
                telegram_id=telegram_id,
                balance=0,
                is_banned=False,
            )
        return self._users[telegram_id]

    async def get_by_id(self, telegram_id: int) -> Optional[User]:
        """Ambil user by ID."""
        return self._users.get(telegram_id)

    async def deduct_balance(self, telegram_id: int, amount: int) -> bool:
        """Mock deduct (tidak atomic)."""
        if amount <= 0:
            raise ValueError("amount harus > 0")

        user = self._users.get(telegram_id)
        if not user or user.is_banned or user.balance < amount:
            return False

        user.balance -= amount
        return True

    async def add_balance(self, telegram_id: int, amount: int) -> bool:
        """Mock add (tidak atomic)."""
        if amount <= 0:
            raise ValueError("amount harus > 0")

        user = self._users.get(telegram_id)
        if not user or user.is_banned:
            return False

        user.balance += amount
        return True
