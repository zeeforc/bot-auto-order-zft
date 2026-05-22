"""
Async PostgreSQL connection pool (asyncpg).

Pool dibuat sekali di startup bot, lalu di-inject ke repository
sebagai dependency. Ini menghindari overhead bikin koneksi tiap query
dan aman untuk concurrency tinggi.
"""
from __future__ import annotations

import logging
from typing import Optional

import asyncpg

from config import settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_pool(
    min_size: int = 1,
    max_size: int = 10,
    command_timeout: float = 10.0,
) -> asyncpg.Pool:
    """Inisialisasi connection pool. Idempotent.

    Raises:
        RuntimeError: Jika DATABASE_URL belum di-set.
    """
    global _pool
    if _pool is not None:
        return _pool

    dsn = settings.DATABASE_URL
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL belum di-set di .env. Format: "
            "postgresql://user:pass@host:5432/dbname"
        )

    # Supabase pooler (PgBouncer) tidak support prepared statements,
    # jadi kita disable statement cache.
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
        statement_cache_size=0,
    )
    logger.info("asyncpg pool initialized (min=%s max=%s)", min_size, max_size)
    return _pool


async def close_pool() -> None:
    """Tutup pool saat shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")


def get_pool() -> asyncpg.Pool:
    """Akses pool yang sudah di-init. Raise jika belum di-init."""
    if _pool is None:
        raise RuntimeError("DB pool belum diinisialisasi. Panggil init_pool() dulu.")
    return _pool


# ======================================================================
# Helper: Cek koneksi DB (untuk fallback logic)
# ======================================================================

async def test_db_connection() -> bool:
    """Test koneksi database. Return True jika berhasil."""
    if not settings.DATABASE_URL:
        return False
    try:
        pool = await init_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception as e:
        logger.error("test_db_connection failed: %s", str(e))
        return False
