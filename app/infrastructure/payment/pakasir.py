"""
Pakasir Payment Gateway Provider (Async).

Docs: https://pakasir.com/p/docs

API Endpoints:
- Create: POST https://app.pakasir.com/api/transactioncreate/{method}
- Cancel: POST https://app.pakasir.com/api/transactioncancel
- Detail: GET  https://app.pakasir.com/api/transactiondetail?project=&amount=&order_id=&api_key=
- Simulate: POST https://app.pakasir.com/api/paymentsimulation

Webhook body (POST ke URL kita):
{
  "amount": 22000,
  "order_id": "xxx",
  "project": "slug",
  "status": "completed",
  "payment_method": "qris",
  "completed_at": "2024-09-10T08:07:02.819+07:00"
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
    """Pakasir payment gateway provider."""

    def __init__(
        self,
        base_url: str,
        project_slug: str,
        api_key: str,
        payment_method: str = "qris",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.project_slug = project_slug
        self.api_key = api_key
        self.payment_method = payment_method
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
        """Create QRIS/VA payment via Pakasir API."""
        url = f"{self.base_url}/api/transactioncreate/{self.payment_method}"
        payload = {
            "project": self.project_slug,
            "order_id": order_id,
            "amount": amount,
            "api_key": self.api_key,
        }

        logger.info(
            "[pakasir] 📤 Creating transaction: method=%s order_id=%s amount=%s",
            self.payment_method, order_id, amount,
        )

        try:
            response = await self._client.post(url, json=payload)
            data = response.json()

            logger.info("[pakasir] 📥 Response status=%s", response.status_code)

            if response.status_code == 200 and "payment" in data:
                payment = data["payment"]
                fee = payment.get("fee", 0)
                total = payment.get("total_payment", amount)
                qr_string = payment.get("payment_number", "")
                expired_at = payment.get("expired_at", "")

                logger.info(
                    "[pakasir] ✅ Transaction created: order_id=%s total=%s fee=%s qr_len=%s",
                    order_id, total, fee, len(qr_string),
                )

                return PaymentResult(
                    success=True,
                    reference=order_id,  # Pakasir uses order_id as reference
                    merchant_ref=order_id,
                    qr_string=qr_string,
                    checkout_url=f"{self.base_url}/pay/{self.project_slug}/{amount}?order_id={order_id}&qris_only=1",
                    amount=amount,
                    fee=fee,
                    total_amount=total,
                    expired_at=expired_at,
                    payment_method=self.payment_method,
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

    async def verify_callback(self, data: Dict[str, Any]) -> CallbackData | None:
        """Verify webhook callback dari Pakasir.

        Pakasir ga pakai signature — verify via Transaction Detail API.
        """
        order_id = data.get("order_id", "")
        amount = data.get("amount", 0)
        status = data.get("status", "")
        project = data.get("project", "")

        if not order_id or not amount:
            logger.warning("[pakasir] Callback invalid: missing order_id or amount")
            return None

        # Verify project matches
        if project and project != self.project_slug:
            logger.warning(
                "[pakasir] Callback project mismatch: got=%s expected=%s",
                project, self.project_slug,
            )
            return None

        # Double-check via Transaction Detail API
        verified = await self._verify_transaction(order_id, amount)
        if not verified:
            logger.warning("[pakasir] Callback verification failed for order_id=%s", order_id)
            return None

        return CallbackData(
            order_id=order_id,
            amount=int(amount),
            status=status,  # "completed"
            payment_method=data.get("payment_method", ""),
            completed_at=data.get("completed_at", ""),
            raw=data,
        )

    async def _verify_transaction(self, order_id: str, amount: int) -> bool:
        """Verify transaksi via Transaction Detail API (recommended by Pakasir docs)."""
        url = (
            f"{self.base_url}/api/transactiondetail"
            f"?project={self.project_slug}"
            f"&amount={amount}"
            f"&order_id={order_id}"
            f"&api_key={self.api_key}"
        )

        try:
            response = await self._client.get(url)
            data = response.json()

            if response.status_code == 200:
                tx = data.get("transaction", {})
                if tx.get("status") == "completed" and tx.get("order_id") == order_id:
                    logger.info("[pakasir] ✅ Transaction verified: order_id=%s", order_id)
                    return True
                else:
                    logger.warning(
                        "[pakasir] Transaction not completed: order_id=%s status=%s",
                        order_id, tx.get("status"),
                    )
                    return False
            else:
                logger.warning("[pakasir] Detail API error: status=%s", response.status_code)
                return False

        except Exception as e:
            logger.error("[pakasir] Verify exception: %s", e)
            # Jika verify gagal, tetap proses (fallback trust webhook)
            # Ini trade-off: lebih baik deliver akun daripada user bayar tapi ga dapet
            logger.warning("[pakasir] Falling back to trust webhook data")
            return True

    async def cancel_transaction(self, order_id: str, amount: int) -> bool:
        """Cancel transaksi pending di Pakasir."""
        url = f"{self.base_url}/api/transactioncancel"
        payload = {
            "project": self.project_slug,
            "order_id": order_id,
            "amount": amount,
            "api_key": self.api_key,
        }

        try:
            response = await self._client.post(url, json=payload)
            if response.status_code == 200:
                logger.info("[pakasir] ✅ Transaction cancelled: order_id=%s", order_id)
                return True
            else:
                logger.warning("[pakasir] Cancel failed: status=%s", response.status_code)
                return False
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
                logger.warning("[pakasir] Simulate failed: status=%s body=%s", response.status_code, response.text)
                return False
        except Exception as e:
            logger.error("[pakasir] Simulate exception: %s", e)
            return False

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
