"""
Factory untuk Service Layer instances.

Menyediakan singleton services yang sudah di-inject dengan repositories.
Handler tinggal import `get_order_service()`, `get_deposit_service()`, dll.
"""
from __future__ import annotations

import logging
from typing import Optional

from .order_service import OrderService
from .deposit_service import DepositService
from .payment_service import PaymentService
from .voucher_service import VoucherService

logger = logging.getLogger(__name__)

_order_service: Optional[OrderService] = None
_deposit_service: Optional[DepositService] = None
_payment_service: Optional[PaymentService] = None
_voucher_service: Optional[VoucherService] = None


async def get_order_service() -> OrderService:
    """Get singleton OrderService instance."""
    global _order_service
    if _order_service is not None:
        return _order_service

    # Lazy import untuk avoid circular
    from app.infrastructure.database.factory import (
        get_order_repository,
        get_product_repository,
        get_user_repository,
    )

    product_repo = await get_product_repository()
    user_repo = await get_user_repository()
    order_repo = await get_order_repository()

    _order_service = OrderService(
        product_repo=product_repo,
        user_repo=user_repo,
        order_repo=order_repo,
    )
    logger.info("✅ OrderService initialized")
    return _order_service


async def get_deposit_service() -> DepositService:
    """Get singleton DepositService instance."""
    global _deposit_service
    if _deposit_service is not None:
        return _deposit_service

    from app.infrastructure.database.factory import get_user_repository
    from config.settings import PAYMENT_PROVIDER

    user_repo = await get_user_repository()

    # Jika pakai Tripay, inject TripayClient langsung (legacy path)
    # Jika pakai Pakasir/lainnya, set None → deposit_service akan pakai generic provider
    payment_gateway = None
    if PAYMENT_PROVIDER == "tripay":
        from app.infrastructure.payment.tripay import get_tripay_client
        payment_gateway = get_tripay_client()

    _deposit_service = DepositService(
        user_repo=user_repo,
        payment_gateway=payment_gateway,
    )

    mode = f"generic ({PAYMENT_PROVIDER})" if payment_gateway is None else "Tripay (direct)"
    logger.info("✅ DepositService initialized (mode=%s)", mode)
    return _deposit_service


async def get_payment_service() -> PaymentService:
    """Get singleton PaymentService instance."""
    global _payment_service
    if _payment_service is not None:
        return _payment_service

    from app.infrastructure.database.factory import (
        get_order_repository,
        get_user_repository,
    )
    from config.settings import WEBHOOK_SECRET

    order_repo = await get_order_repository()
    user_repo = await get_user_repository()

    _payment_service = PaymentService(
        order_repo=order_repo,
        user_repo=user_repo,
        webhook_secret=WEBHOOK_SECRET,
    )
    logger.info("✅ PaymentService initialized")
    return _payment_service


async def reset_services() -> None:
    """Reset all service singletons (untuk testing)."""
    global _order_service, _deposit_service, _payment_service, _voucher_service
    _order_service = None
    _deposit_service = None
    _payment_service = None
    _voucher_service = None


async def get_voucher_service() -> VoucherService:
    """Get singleton VoucherService instance."""
    global _voucher_service
    if _voucher_service is not None:
        return _voucher_service

    from app.infrastructure.database.factory import get_voucher_repository

    voucher_repo = await get_voucher_repository()

    _voucher_service = VoucherService(voucher_repo=voucher_repo)
    logger.info("✅ VoucherService initialized")
    return _voucher_service
