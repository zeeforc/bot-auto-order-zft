"""
Pakasir Payment Gateway Provider (Async) - API v2.

Docs: https://pakasir.com/p/create-transaction

API v2 Endpoints:
- Create: POST https://app.pakasir.com/api/v2/create-transaction/{slug}/{order_id} (Header: X-Api-Key)
- Status: GET  https://app.pakasir.com/api/v2/transaction-status/{slug}/{txn_id} (Header: X-Api-Key)
- Cancel: POST https://app.pakasir.com/api/v2/cancel-transaction/{slug}/{txn_id} (Header: X-Api-Key)

Webhook v2:
- Header: X-Secret: {secret}
- Body:
{
  "txn_id": "vwiqpcriq",
  "order_id": "INV123123",
  "amount": 99000,
  "is_sandbox": false,
  "status": "completed",
  "completed_at": "2025-09-19T01:18:49.678622564Z"
}
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx

from config import settings
from .base import PaymentProvider, PaymentResult, CallbackData

logger = logging.getLogger(__name__)


class PakasirProvider(PaymentProvider):
    """Pakasir payment gateway provider (API v2)."""

    def __init__(
        self,
        base_url: str,
        project_slug: str,
        api_key: str,
        payment_method: str = "qris",
        webhook_secret: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_slug = project_slug
        self.api_key = api_key
        self.payment_method = payment_method
        self.webhook_secret = webhook_secret
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def name(self) -> str:
        return "Pakasir"

    async def create_payment(
        self,
        order_id: str,
        amount: int,
        product_name: str = "",
        user_id: int = 0,
    ) -> PaymentResult:
        """Create QRIS/VA payment via Pakasir API v2."""
        # API v2: POST /api/v2/create-transaction/{slug}/{order_id}
        url = f"{self.base_url}/api/v2/create-transaction/{self.project_slug}/{order_id}"
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
        }
        payload = {
            "method": self.payment_method,
            "amount": amount,
        }

        logger.info(
            "[pakasir] 📤 Creating transaction v2: method=%s order_id=%s amount=%s slug=%s",
            self.payment_method, order_id, amount, self.project_slug,
        )

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            data = response.json()

            logger.info("[pakasir] 📥 Response status=%s body=%s", response.status_code, data)

            if response.status_code == 200:
                # API v2 returns fields directly at root
                txn_id = data.get("txn_id", "")
                qr_string = data.get("qr_string", "")
                fee = data.get("fee", 0)
                total = data.get("total_payment", amount)
                expired_at = data.get("expired_at", "")
                payment_link = data.get("payment_link")
                if not payment_link and txn_id:
                    payment_link = f"{self.base_url}/pay-v2/{txn_id}?qris_only=1"

                # Fallback support if legacy v1 wrapper returned
                if not qr_string and "payment" in data:
                    legacy_payment = data["payment"]
                    qr_string = legacy_payment.get("payment_number", "")
                    fee = legacy_payment.get("fee", fee)
                    total = legacy_payment.get("total_payment", total)
                    expired_at = legacy_payment.get("expired_at", expired_at)

                logger.info(
                    "[pakasir] ✅ Transaction created v2: order_id=%s txn_id=%s total=%s fee=%s qr_len=%s",
                    order_id, txn_id, total, fee, len(qr_string),
                )

                return PaymentResult(
                    success=True,
                    reference=txn_id or order_id,
                    merchant_ref=order_id,
                    qr_string=qr_string,
                    checkout_url=payment_link or f"{self.base_url}/pay-v2/{txn_id or order_id}?qris_only=1",
                    amount=amount,
                    fee=fee,
                    total_amount=total,
                    expired_at=expired_at,
                    payment_method=data.get("payment_method", self.payment_method),
                    raw_response=data,
                )
            else:
                error_msg = data.get("message", data.get("error", str(data)))
                logger.error("[pakasir] ❌ Create failed: %s", error_msg)
                return PaymentResult(success=False, error=error_msg, raw_response=data)

        except httpx.TimeoutException:
            logger.error("[pakasir] ❌ Request timeout")
            return PaymentResult(success=False, error="Request timeout. Coba lagi nanti.")
        except Exception as e:
            logger.error("[pakasir] ❌ Exception: %s", str(e), exc_info=True)
            return PaymentResult(success=False, error=str(e))

    async def create_deposit(
        self,
        user_id: int,
        amount: int,
    ) -> PaymentResult:
        """Create deposit payment via Pakasir."""
        # Generate unique order_id for deposit
        order_id = f"DEP-{user_id}-{int(time.time())}"
        return await self.create_payment(
            order_id=order_id,
            amount=amount,
            product_name="Deposit Saldo",
            user_id=user_id,
        )

    async def verify_callback(
        self,
        data: Dict[str, Any],
        secret_header: Optional[str] = None,
    ) -> CallbackData | None:
        """Verify webhook callback dari Pakasir (v2)."""
        # 1. Verify X-Secret jika webhook_secret diset
        if self.webhook_secret:
            if not secret_header or secret_header != self.webhook_secret:
                logger.warning(
                    "[pakasir] ❌ Webhook secret invalid: got=%s expected=%s",
                    secret_header, self.webhook_secret,
                )
                return None

        order_id = data.get("order_id", "")
        txn_id = data.get("txn_id", "")
        amount = data.get("amount", 0)
        status = data.get("status", "")
        project = data.get("project", "")

        if not order_id or not amount:
            logger.warning("[pakasir] Callback invalid: missing order_id or amount")
            return None

        # Verify project matches jika ada di payload
        if project and project != self.project_slug:
            logger.warning(
                "[pakasir] Callback project mismatch: got=%s expected=%s",
                project, self.project_slug,
            )
            return None

        # Double-check via Status API v2
        verified = await self._verify_transaction(order_id, amount, txn_id=txn_id)
        if not verified:
            logger.warning(
                "[pakasir] Callback verification failed for order_id=%s txn_id=%s",
                order_id, txn_id,
            )
            return None

        return CallbackData(
            order_id=order_id,
            amount=int(amount),
            status=status,  # "completed"
            payment_method=data.get("payment_method", self.payment_method),
            completed_at=data.get("completed_at", ""),
            raw=data,
        )

    async def _verify_transaction(
        self,
        order_id: str,
        amount: int,
        txn_id: Optional[str] = None,
    ) -> bool:
        """Verify transaksi via Transaction Status API v2."""
        target_id = txn_id or order_id
        url = f"{self.base_url}/api/v2/transaction-status/{self.project_slug}/{target_id}"
        headers = {"X-Api-Key": self.api_key}

        try:
            response = await self._client.get(url, headers=headers)
            data = response.json()

            if response.status_code == 200:
                tx_status = data.get("status", "")
                if tx_status == "completed":
                    logger.info(
                        "[pakasir] ✅ Transaction verified v2: id=%s order_id=%s",
                        target_id, order_id,
                    )
                    return True
                else:
                    logger.warning(
                        "[pakasir] Transaction not completed: id=%s status=%s",
                        target_id, tx_status,
                    )
                    return False
            else:
                logger.warning(
                    "[pakasir] Status API v2 returned %s, trying fallback",
                    response.status_code,
                )
                # Fallback to v1 endpoint jika status v2 gagal
                legacy_url = (
                    f"{self.base_url}/api/transactiondetail"
                    f"?project={self.project_slug}"
                    f"&amount={amount}"
                    f"&order_id={order_id}"
                    f"&api_key={self.api_key}"
                )
                legacy_res = await self._client.get(legacy_url)
                if legacy_res.status_code == 200:
                    tx = legacy_res.json().get("transaction", {})
                    if tx.get("status") == "completed":
                        return True
                return False

        except Exception as e:
            logger.error("[pakasir] Verify exception: %s", e)
            # Fallback to trust webhook data jika check detail network error
            logger.warning("[pakasir] Falling back to trust webhook data")
            return True

    async def cancel_transaction(
        self,
        order_id: str,
        amount: int = 0,
        txn_id: Optional[str] = None,
    ) -> bool:
        """Cancel transaksi pending di Pakasir API v2."""
        target_id = txn_id or order_id
        url = f"{self.base_url}/api/v2/cancel-transaction/{self.project_slug}/{target_id}"
        headers = {"X-Api-Key": self.api_key}

        try:
            response = await self._client.post(url, headers=headers)
            if response.status_code == 200:
                logger.info("[pakasir] ✅ Transaction cancelled v2: id=%s", target_id)
                return True
            else:
                logger.warning("[pakasir] Cancel failed v2: status=%s", response.status_code)
                # Fallback v1
                v1_url = f"{self.base_url}/api/transactioncancel"
                v1_payload = {
                    "project": self.project_slug,
                    "order_id": order_id,
                    "amount": amount,
                    "api_key": self.api_key,
                }
                v1_res = await self._client.post(v1_url, json=v1_payload)
                return v1_res.status_code == 200
        except Exception as e:
            logger.error("[pakasir] Cancel exception: %s", e)
            return False

    async def simulate_payment(self, order_id: str, amount: int) -> bool:
        """Simulasi pembayaran (sandbox mode)."""
        url = f"{self.base_url}/api/paymentsimulation"
        payload = {
            "project": self.project_slug,
            "order_id": order_id,
            "amount": amount,
            "api_key": self.api_key,
        }

        try:
            response = await self._client.post(url, json=payload)
            if response.status_code == 200:
                logger.info("[pakasir] ✅ Payment simulated: order_id=%s", order_id)
                return True
            else:
                logger.warning(
                    "[pakasir] Simulate failed: status=%s body=%s",
                    response.status_code, response.text,
                )
                return False
        except Exception as e:
            logger.error("[pakasir] Simulate exception: %s", e)
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
