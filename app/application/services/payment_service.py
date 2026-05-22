"""
PaymentService - Business logic untuk handle payment webhook/callback.

Tanggung jawab:
1. Verify signature dari payment gateway
2. Update order status (pending -> paid)
3. Trigger delivery (send account details ke user)
4. Handle deposit callback (add balance)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.domain.interfaces import OrderRepository, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class WebhookResult:
    """Result object dari process_webhook."""
    success: bool
    order_id: Optional[str] = None
    status: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class PaymentService:
    """Service untuk handle payment webhook dari Tripay."""

    def __init__(
        self,
        order_repo: OrderRepository,
        user_repo: UserRepository,
        webhook_secret: str = "",
    ) -> None:
        self._order_repo = order_repo
        self._user_repo = user_repo
        self._webhook_secret = webhook_secret

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature dari Tripay.

        Tripay menggunakan HMAC-SHA256 untuk signature verification.

        Args:
            payload: Raw request body (bytes)
            signature: Signature dari header X-Callback-Signature

        Returns:
            True jika signature valid
        """
        if not self._webhook_secret:
            logger.warning("[payment] Webhook secret belum di-set!")
            return False

        expected = hmac.HMAC(
            key=self._webhook_secret.encode(),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_order_payment(
        self,
        order_id: str,
        status: str,
        payment_ref: Optional[str] = None,
    ) -> WebhookResult:
        """Process payment callback untuk order.

        Flow:
        1. Get order dari DB
        2. Validasi status transition (pending -> paid)
        3. Update order status
        4. Return result

        Args:
            order_id: ID order
            status: Status baru dari gateway (PAID, EXPIRED, FAILED)
            payment_ref: Reference dari payment gateway

        Returns:
            WebhookResult
        """
        try:
            # Step 1: Get order
            order = await self._order_repo.get_by_id(order_id)
            if order is None:
                return WebhookResult(
                    success=False,
                    error_code="ORDER_NOT_FOUND",
                    error_message=f"Order {order_id} tidak ditemukan.",
                )

            # Step 2: Validasi status transition
            if order.status != "pending":
                logger.warning(
                    "[payment] Order %s sudah status=%s, skip update",
                    order_id, order.status,
                )
                return WebhookResult(
                    success=True,
                    order_id=order_id,
                    status=order.status,
                )

            # Step 3: Map gateway status ke internal status
            internal_status = self._map_gateway_status(status)

            # Step 4: Update order status
            updated = await self._order_repo.update_status(order_id, internal_status)
            if not updated:
                return WebhookResult(
                    success=False,
                    error_code="UPDATE_FAILED",
                    error_message="Gagal update status order.",
                )

            logger.info(
                "[payment] ✅ Order %s updated: %s -> %s (ref=%s)",
                order_id, order.status, internal_status, payment_ref,
            )

            return WebhookResult(
                success=True,
                order_id=order_id,
                status=internal_status,
            )

        except Exception as e:
            logger.error("[payment] ❌ Error: %s", str(e), exc_info=True)
            return WebhookResult(
                success=False,
                error_code="INTERNAL_ERROR",
                error_message="Terjadi kesalahan sistem.",
            )

    async def process_deposit_payment(
        self,
        user_id: int,
        amount: int,
        status: str,
        payment_ref: str,
    ) -> WebhookResult:
        """Process payment callback untuk deposit.

        Flow:
        1. Validasi status = PAID
        2. Add balance ke user (atomic)
        3. Return result

        Args:
            user_id: Telegram user ID
            amount: Nominal deposit (IDR)
            status: Status dari gateway
            payment_ref: Reference dari payment gateway

        Returns:
            WebhookResult
        """
        try:
            if status != "PAID":
                logger.info(
                    "[payment] Deposit %s status=%s (bukan PAID), skip",
                    payment_ref, status,
                )
                return WebhookResult(
                    success=True,
                    status=status,
                )

            # Add balance (atomic)
            success = await self._user_repo.add_balance(user_id, amount)
            if not success:
                return WebhookResult(
                    success=False,
                    error_code="BALANCE_ADD_FAILED",
                    error_message="Gagal menambah saldo user.",
                )

            logger.info(
                "[payment] ✅ Deposit sukses: user=%s amount=%s ref=%s",
                user_id, amount, payment_ref,
            )

            return WebhookResult(
                success=True,
                status="paid",
            )

        except Exception as e:
            logger.error("[payment] ❌ Deposit error: %s", str(e), exc_info=True)
            return WebhookResult(
                success=False,
                error_code="INTERNAL_ERROR",
                error_message="Terjadi kesalahan sistem.",
            )

    @staticmethod
    def _map_gateway_status(gateway_status: str) -> str:
        """Map status dari payment gateway ke internal status."""
        mapping = {
            "PAID": "paid",
            "EXPIRED": "cancelled",
            "FAILED": "cancelled",
            "UNPAID": "pending",
            "REFUND": "refunded",
        }
        return mapping.get(gateway_status.upper(), "pending")
