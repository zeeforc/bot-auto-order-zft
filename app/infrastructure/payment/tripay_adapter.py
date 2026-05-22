"""
Adapter: wrap existing TripayClient ke PaymentProvider interface.

Ini bridge supaya TripayClient yang udah ada bisa dipakai via
generic PaymentProvider interface tanpa rewrite total.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from .base import PaymentProvider, PaymentResult, CallbackData
from .tripay import TripayClient

logger = logging.getLogger(__name__)


class TripayAdapter(PaymentProvider):
    """Adapter: TripayClient → PaymentProvider interface."""

    def __init__(self, client: TripayClient) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "Tripay"

    async def create_payment(
        self,
        order_id: str,
        amount: int,
        product_name: str = "",
        user_id: int = 0,
    ) -> PaymentResult:
        """Create payment via Tripay."""
        data = await self._client.create_order_payment(
            order_id=order_id,
            amount=amount,
            product_name=product_name or "Order",
            user_id=user_id,
        )

        if "error" in data:
            return PaymentResult(success=False, error=data["error"])

        return PaymentResult(
            success=True,
            reference=data.get("reference", ""),
            merchant_ref=order_id,
            qr_string=data.get("qr_string", ""),
            checkout_url=data.get("checkout_url", ""),
            amount=data.get("amount", amount),
            fee=data.get("fee", 0),
            total_amount=data.get("total_amount", amount),
            expired_at=str(data.get("expired_time", "")),
            payment_method="qris",
            raw_response=data,
        )

    async def create_deposit(
        self,
        user_id: int,
        amount: int,
    ) -> PaymentResult:
        """Create deposit via Tripay."""
        data = await self._client.create_qris_deposit(
            user_id=user_id,
            amount=amount,
        )

        if "error" in data:
            return PaymentResult(success=False, error=data["error"])

        return PaymentResult(
            success=True,
            reference=data.get("reference", ""),
            merchant_ref=data.get("merchant_ref", f"DEP-{user_id}-{int(time.time())}"),
            qr_string=data.get("qr_string", ""),
            checkout_url=data.get("checkout_url", ""),
            amount=data.get("amount", amount),
            fee=data.get("fee", 0),
            total_amount=data.get("total_amount", amount),
            expired_at=str(data.get("expired_time", "")),
            payment_method="qris",
            raw_response=data,
        )

    async def verify_callback(self, data: Dict[str, Any]) -> CallbackData | None:
        """Verify Tripay callback (signature already verified in webhook handler)."""
        order_id = data.get("merchant_ref", "")
        status = data.get("status", "")
        amount = data.get("amount_received", data.get("total_amount", 0))

        if not order_id:
            return None

        # Map Tripay status to internal
        status_map = {
            "PAID": "completed",
            "EXPIRED": "expired",
            "FAILED": "failed",
            "REFUND": "refunded",
        }

        return CallbackData(
            order_id=order_id,
            amount=int(amount),
            status=status_map.get(status, status.lower()),
            payment_method=data.get("payment_method", "qris"),
            completed_at=data.get("paid_at", ""),
            raw=data,
        )

    async def cancel_transaction(self, order_id: str, amount: int) -> bool:
        """Tripay doesn't have a cancel API — just let it expire."""
        logger.info("[tripay_adapter] Cancel not supported, will auto-expire: %s", order_id)
        return True

    async def simulate_payment(self, order_id: str, amount: int) -> bool:
        """Tripay sandbox doesn't have simulation API — use /testwebhook instead."""
        return False
