"""
Payment Provider Factory.

Berdasarkan PAYMENT_PROVIDER di .env, return provider yang aktif.
Supported: "tripay", "pakasir", "gopay"
Supported: "tripay", "pakasir", "gopay", "gopay_web"
"""
from __future__ import annotations

import logging
from typing import Optional

from config import settings
from .base import PaymentProvider
from .pakasir import PakasirProvider
from .gopay_web import GoPayWebProvider

logger = logging.getLogger(__name__)

_provider: Optional[PaymentProvider] = None


def get_active_provider() -> Optional[PaymentProvider]:
    """Get singleton payment provider berdasarkan config.

    Returns:
        PaymentProvider instance, atau None jika belum di-configure.
    """
    global _provider

    if _provider is not None:
        return _provider

    provider_name = getattr(settings, "PAYMENT_PROVIDER", "tripay").lower()

    if provider_name == "pakasir":
        _provider = _init_pakasir()
    elif provider_name == "tripay":
        _provider = _init_tripay()
    elif provider_name == "gopay":
        _provider = _init_gopay()
    elif provider_name == "gopay_web":
        _provider = GoPayWebProvider()
    else:
        logger.error("[payment] Unknown PAYMENT_PROVIDER: %s", provider_name)
        return None

    return _provider


def _init_pakasir() -> Optional[PaymentProvider]:
    """Initialize Pakasir provider."""
    base_url = getattr(settings, "PAKASIR_BASE_URL", "")
    project_slug = getattr(settings, "PAKASIR_PROJECT_SLUG", "")
    api_key = getattr(settings, "PAKASIR_API_KEY", "")
    method = getattr(settings, "PAKASIR_PAYMENT_METHOD", "qris")

    if not project_slug or not api_key:
        logger.warning("[payment] Pakasir belum di-configure (missing slug/api_key)")
        return None

    from .pakasir import PakasirProvider
    provider = PakasirProvider(
        base_url=base_url or "https://app.pakasir.com",
        project_slug=project_slug,
        api_key=api_key,
        payment_method=method,
    )
    logger.info(
        "[payment] ✅ PakasirProvider initialized (project=%s, method=%s)",
        project_slug, method,
    )
    return provider


def _init_tripay() -> Optional[PaymentProvider]:
    """Initialize Tripay provider (wrapped as PaymentProvider interface)."""
    from .tripay import get_tripay_client
    tripay = get_tripay_client()

    if not tripay:
        return None

    # Wrap TripayClient ke PaymentProvider interface
    from .tripay_adapter import TripayAdapter
    adapter = TripayAdapter(tripay)
    logger.info("[payment] ✅ TripayAdapter initialized")
    return adapter


def _init_gopay() -> Optional[PaymentProvider]:
    """Initialize GoPay Custom QRIS provider (local EMVCo generation)."""
    static_qris = getattr(settings, "GOPAY_STATIC_QRIS", "")

    if not static_qris:
        logger.warning(
            "[payment] GoPay belum di-configure (GOPAY_STATIC_QRIS kosong). "
            "Isi dengan full EMVCo string dari QRIS statis merchant GoPay."
        )
        return None

    from .gopay_qris import GopayProvider
    provider = GopayProvider(static_qris=static_qris)
    logger.info("[payment] ✅ GopayProvider initialized (qris_len=%s)", len(static_qris))
    return provider

