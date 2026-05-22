"""
Factory untuk ProductRepository, UserRepository, OrderRepository.

Logika:
1. Coba test koneksi DB dulu.
2. Kalau berhasil -> pakai Async*Repository.
3. Kalau gagal (DB down / belum di-migrate) -> pakai Mock*Repository.

Handler tinggal import `get_product_repository()`, `get_user_repository()`, dll.
"""
from __future__ import annotations

import logging

from ...domain.interfaces import OrderRepository, ProductRepository, UserRepository, VoucherRepository

logger = logging.getLogger(__name__)

_product_repo: ProductRepository | None = None
_user_repo: UserRepository | None = None
_order_repo: OrderRepository | None = None
_voucher_repo: VoucherRepository | None = None


async def get_product_repository() -> ProductRepository:
    """Get singleton ProductRepository instance."""
    global _product_repo
    if _product_repo is not None:
        return _product_repo

    # Lazy import biar gak circular
    from .connection import get_pool, init_pool, test_db_connection
    from .product_repo import AsyncPgProductRepository, MockProductRepository

    # Coba koneksi DB
    if await test_db_connection():
        pool = get_pool()
        _product_repo = AsyncPgProductRepository(pool)
        logger.info("✅ ProductRepository: pakai AsyncPgProductRepository (DB)")
    else:
        _product_repo = MockProductRepository()
        logger.warning("⚠️ ProductRepository: pakai MockProductRepository (fallback)")

    return _product_repo


async def get_user_repository() -> UserRepository:
    """Get singleton UserRepository instance."""
    global _user_repo
    if _user_repo is not None:
        return _user_repo

    # Lazy import
    from .connection import get_pool, test_db_connection
    from .user_repo import AsyncPgUserRepository, MockUserRepository

    # Coba koneksi DB
    if await test_db_connection():
        pool = get_pool()
        _user_repo = AsyncPgUserRepository(pool)
        logger.info("✅ UserRepository: pakai AsyncPgUserRepository (DB)")
    else:
        _user_repo = MockUserRepository()
        logger.warning("⚠️ UserRepository: pakai MockUserRepository (fallback)")

    return _user_repo


async def get_order_repository() -> OrderRepository:
    """Get singleton OrderRepository instance."""
    global _order_repo
    if _order_repo is not None:
        return _order_repo

    # Lazy import
    from .connection import get_pool, test_db_connection
    from .order_repo import AsyncPgOrderRepository, MockOrderRepository

    # Coba koneksi DB
    if await test_db_connection():
        pool = get_pool()
        _order_repo = AsyncPgOrderRepository(pool)
        logger.info("✅ OrderRepository: pakai AsyncPgOrderRepository (DB)")
    else:
        _order_repo = MockOrderRepository()
        logger.warning("⚠️ OrderRepository: pakai MockOrderRepository (fallback)")

    return _order_repo


async def get_voucher_repository() -> VoucherRepository:
    """Get singleton VoucherRepository instance."""
    global _voucher_repo
    if _voucher_repo is not None:
        return _voucher_repo

    from .connection import get_pool, test_db_connection
    from .voucher_repo import AsyncPgVoucherRepository, MockVoucherRepository

    if await test_db_connection():
        pool = get_pool()
        _voucher_repo = AsyncPgVoucherRepository(pool)
        logger.info("✅ VoucherRepository: pakai AsyncPgVoucherRepository (DB)")
    else:
        _voucher_repo = MockVoucherRepository()
        logger.warning("⚠️ VoucherRepository: pakai MockVoucherRepository (fallback)")

    return _voucher_repo


async def reset_repositories() -> None:
    """Reset all singletons (untuk testing)."""
    global _product_repo, _user_repo, _order_repo, _voucher_repo
    _product_repo = None
    _user_repo = None
    _order_repo = None
    _voucher_repo = None
