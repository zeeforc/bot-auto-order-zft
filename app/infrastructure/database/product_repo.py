"""
Implementasi async ProductRepository memakai asyncpg (PostgreSQL/Supabase).

Kenapa asyncpg, bukan supabase-py?
- supabase-py v2 secara default sync (memakai PostgREST). Untuk kebutuhan
  atomic update + concurrency tinggi (ratusan user checkout barengan),
  driver native PostgreSQL jauh lebih reliable dan cepat.
- DATABASE_URL Supabase (Connection Pooling URL) tetap bisa dipakai oleh
  asyncpg via DSN biasa.

Race condition handling:
  Pemotongan stok memakai SATU query atomic:
      UPDATE products
         SET stock = stock - $2
       WHERE id = $1
         AND is_active = TRUE
         AND stock >= $2
  Jika 100 user menekan "Konfirmasi" bersamaan, hanya yang berhasil
  match `stock >= qty` yang akan ter-update. Sisanya dapat False
  -> handler tampilkan pesan "stok habis" ke user.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import asyncpg

from ...domain.entities import Product
from ...domain.interfaces import ProductRepository

logger = logging.getLogger(__name__)


# Kolom yang selalu di-select. Dipusatkan agar konsisten di seluruh query.
_PRODUCT_COLUMNS = (
    "id, name, description, category, price, stock, is_active, "
    "created_at, updated_at"
)


def _row_to_product(row: asyncpg.Record) -> Product:
    """Map asyncpg.Record -> domain entity Product."""
    return Product(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        short_description=row.get("short_description"),
        category=row["category"],
        price=row["price"],
        stock=row["stock"],
        is_active=row["is_active"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class AsyncPgProductRepository(ProductRepository):
    """Implementasi ProductRepository memakai asyncpg connection pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------
    async def list_paginated(
        self,
        limit: int = 10,
        offset: int = 0,
        only_active: bool = True,
    ) -> List[Product]:
        # Defensive: clamp limit agar tidak ada user/handler nakal narik
        # 1 juta row sekaligus.
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))

        where_clause = "WHERE is_active = TRUE" if only_active else ""
        query = f"""
            SELECT
                p.id, p.name, p.description, p.short_description, p.category, p.price,
                COALESCE((
                    SELECT SUM(
                        (SELECT COUNT(*) FROM account_stock a
                         WHERE a.variant_id = v.id AND a.is_used = FALSE)
                    )
                    FROM product_variants v
                    WHERE v.product_id = p.id AND v.is_active = TRUE
                ), p.stock) AS stock,
                p.is_active, p.created_at, p.updated_at
            FROM products p
            {where_clause.replace('is_active', 'p.is_active') if where_clause else ''}
            ORDER BY p.name ASC
            LIMIT $1 OFFSET $2
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, limit, offset)
        except asyncpg.PostgresError:
            logger.exception("list_paginated failed (limit=%s offset=%s)", limit, offset)
            raise

        return [_row_to_product(r) for r in rows]

    async def count(self, only_active: bool = True) -> int:
        where_clause = "WHERE is_active = TRUE" if only_active else ""
        query = f"SELECT COUNT(*) AS total FROM products {where_clause}"

        try:
            async with self._pool.acquire() as conn:
                value = await conn.fetchval(query)
        except asyncpg.PostgresError:
            logger.exception("count failed")
            raise
        return int(value or 0)

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        query = """
            SELECT
                p.id, p.name, p.description, p.short_description, p.category, p.price,
                COALESCE((
                    SELECT SUM(
                        (SELECT COUNT(*) FROM account_stock a
                         WHERE a.variant_id = v.id AND a.is_used = FALSE)
                    )
                    FROM product_variants v
                    WHERE v.product_id = p.id AND v.is_active = TRUE
                ), p.stock) AS stock,
                p.is_active, p.created_at, p.updated_at
            FROM products p
            WHERE p.id = $1
            LIMIT 1
        """
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, int(product_id))
        except asyncpg.PostgresError:
            logger.exception("get_by_id failed (id=%s)", product_id)
            raise

        return _row_to_product(row) if row else None

    # ------------------------------------------------------------------
    # WRITE - ATOMIC
    # ------------------------------------------------------------------
    async def decrement_stock(self, product_id: int, qty: int) -> bool:
        """Kurangi stok secara atomic.

        --- LOGIKA KRITIS ---
        SATU statement UPDATE dengan guard `stock >= qty`. Postgres akan
        memegang row-lock selama UPDATE, sehingga concurrent UPDATE pada
        row yang sama akan dijalankan serial. Yang gagal match (stok
        kurang) langsung mengembalikan 0 row -> kita return False.

        Kenapa pakai RETURNING?
        - Lebih hemat 1 round-trip dibanding cek `cmd_status`.
        - Sekaligus bisa dipakai untuk dapat sisa stok kalau dibutuhkan
          handler (saat ini cuma dipakai untuk konfirmasi sukses).
        """
        if qty <= 0:
            raise ValueError("qty harus > 0")

        query = """
            UPDATE products
               SET stock = stock - $2
             WHERE id = $1
               AND is_active = TRUE
               AND stock >= $2
         RETURNING id
        """

        try:
            async with self._pool.acquire() as conn:
                # Tidak butuh transaction eksplisit: single statement
                # sudah atomic di Postgres.
                row = await conn.fetchrow(query, int(product_id), int(qty))
        except asyncpg.PostgresError:
            logger.exception(
                "decrement_stock failed (product_id=%s qty=%s)", product_id, qty
            )
            raise

        success = row is not None
        if not success:
            logger.info(
                "decrement_stock rejected (product_id=%s qty=%s) - "
                "stok tidak cukup / produk tidak aktif",
                product_id,
                qty,
            )
        return success


# ======================================================================
# FALLBACK: In-memory mock repository (untuk development tanpa DB)
# ======================================================================

class MockProductRepository(ProductRepository):
    """Fallback repository pakai in-memory dict (untuk dev tanpa DB)."""

    def __init__(self) -> None:
        # Data dummy (sama seperti yang di DB, semua harga Rp 1 untuk testing)
        self._products = {
            1: Product(
                id=1,
                name="CANVA PRO TEAM 1 TAHUN",
                description="Canva Pro Team Annual Subscription",
                category="design",
                price=1,
                stock=277,
                is_active=True,
            ),
            2: Product(
                id=2,
                name="NETFLIX PREMIUM 1 BULAN",
                description="Netflix Premium 1 Month Shared",
                category="streaming",
                price=1,
                stock=100,
                is_active=True,
            ),
            3: Product(
                id=3,
                name="SPOTIFY PREMIUM 1 BULAN",
                description="Spotify Premium Individual 1 Month",
                category="streaming",
                price=1,
                stock=200,
                is_active=True,
            ),
            4: Product(
                id=4,
                name="ADOBE PHOTOSHOP CC 1 TAHUN",
                description="Adobe Photoshop CC Annual License",
                category="software",
                price=1,
                stock=50,
                is_active=True,
            ),
            5: Product(
                id=5,
                name="CHATGPT PLUS 1 BULAN",
                description="ChatGPT Plus Subscription 1 Month",
                category="ai",
                price=1,
                stock=60,
                is_active=True,
            ),
        }

    async def list_paginated(
        self,
        limit: int = 10,
        offset: int = 0,
        only_active: bool = True,
    ) -> List[Product]:
        products = list(self._products.values())
        if only_active:
            products = [p for p in products if p.is_active]
        return products[offset : offset + limit]

    async def count(self, only_active: bool = True) -> int:
        products = list(self._products.values())
        if only_active:
            products = [p for p in products if p.is_active]
        return len(products)

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        return self._products.get(int(product_id))

    async def decrement_stock(self, product_id: int, qty: int) -> bool:
        """Mock decrement (tidak atomic, hanya untuk dev)."""
        if qty <= 0:
            raise ValueError("qty harus > 0")

        prod = self._products.get(int(product_id))
        if not prod or not prod.is_active or prod.stock < qty:
            return False

        prod.stock -= qty
        prod.updated_at = __import__("datetime").datetime.now()
        return True
