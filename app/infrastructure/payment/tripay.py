"""
Tripay Payment Gateway Client (Async).

Dokumentasi Tripay API:
- Base URL Sandbox: https://tripay.co.id/api-sandbox
- Base URL Production: https://tripay.co.id/api
- Closed Transaction: POST /transaction/create
- Transaction Detail: GET /transaction/detail?reference=xxx
- Callback Signature: HMAC-SHA256(private_key, json_body)

Signature untuk create transaction:
  hmac_sha256(private_key, merchant_code + merchant_ref + amount)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict, Optional

import httpx

from config import settings
from ...domain.interfaces import PaymentGateway

logger = logging.getLogger(__name__)


class TripayClient(PaymentGateway):
    """Async Tripay API Client.

    Supports:
    - Create closed transaction (QRIS, VA, etc.)
    - Get transaction detail
    - Verify callback signature
    """

    SANDBOX_URL = "https://tripay.co.id/api-sandbox"
    PRODUCTION_URL = "https://tripay.co.id/api"

    def __init__(
        self,
        api_key: str,
        private_key: str,
        merchant_code: str,
        sandbox: bool = True,
    ) -> None:
        self.api_key = api_key
        self.private_key = private_key
        self.merchant_code = merchant_code
        self.base_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL
        self._client = httpx.AsyncClient(timeout=30.0)

    def _create_signature(self, merchant_ref: str, amount: int) -> str:
        """Generate signature untuk create transaction.

        Formula: HMAC-SHA256(private_key, merchant_code + merchant_ref + amount)
        """
        raw = self.merchant_code + merchant_ref + str(amount)
        return hmac.new(
            key=self.private_key.encode("utf-8"),
            msg=raw.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def verify_callback_signature(self, payload: bytes, signature: str) -> bool:
        """Verify callback signature dari Tripay.

        Formula: HMAC-SHA256(private_key, json_body)
        """
        expected = hmac.new(
            key=self.private_key.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def create_qris_deposit(
        self,
        user_id: int,
        amount: int,
        method: Optional[str] = None,
        expire_seconds: int = 30 * 60,
    ) -> Dict[str, Any]:
        """Create QRIS payment untuk deposit.

        Args:
            user_id: Telegram user ID (untuk merchant_ref)
            amount: Nominal deposit (IDR)
            method: QRIS method code. Jika None, pakai setting dari admin.
            expire_seconds: Waktu expire dalam detik (default 30 menit).

        Returns:
            Dict dengan keys: reference, checkout_url, qr_url, qr_string,
            amount, fee, total_amount, expired_time, status
            Atau dict dengan key 'error' jika gagal.
        """
        # Get method dari admin setting jika tidak di-specify
        if method is None:
            from app.presentation.telegram.handlers.admin import get_qris_method
            method = get_qris_method()

        merchant_ref = f"DEP-{user_id}-{int(time.time())}"
        signature = self._create_signature(merchant_ref, amount)

        payload = {
            "method": method,
            "merchant_ref": merchant_ref,
            "amount": amount,
            "customer_name": f"User {user_id}",
            "customer_email": f"user{user_id}@tstore.bot",
            "customer_phone": "08000000000",
            "order_items": [
                {
                    "name": "Deposit Saldo",
                    "price": amount,
                    "quantity": 1,
                }
            ],
            "expired_time": int(time.time()) + expire_seconds,
            "signature": signature,
        }

        return await self._create_transaction(payload, merchant_ref)

    async def create_order_payment(
        self,
        order_id: str,
        amount: int,
        product_name: str,
        user_id: int,
        method: Optional[str] = None,
        expire_seconds: int = 15 * 60,
    ) -> Dict[str, Any]:
        """Create QRIS payment untuk order.

        Args:
            order_id: ID order
            amount: Total harga (IDR)
            product_name: Nama produk
            user_id: Telegram user ID
            method: QRIS method code. Jika None, pakai setting dari admin.
            expire_seconds: Waktu expire dalam detik (default 15 menit).

        Returns:
            Dict dengan payment details atau error.
        """
        # Get method dari admin setting jika tidak di-specify
        if method is None:
            from app.presentation.telegram.handlers.admin import get_qris_method
            method = get_qris_method()

        merchant_ref = order_id
        signature = self._create_signature(merchant_ref, amount)

        payload = {
            "method": method,
            "merchant_ref": merchant_ref,
            "amount": amount,
            "customer_name": f"User {user_id}",
            "customer_email": f"user{user_id}@tstore.bot",
            "customer_phone": "08000000000",
            "order_items": [
                {
                    "name": product_name,
                    "price": amount,
                    "quantity": 1,
                }
            ],
            "expired_time": int(time.time()) + expire_seconds,
            "signature": signature,
        }

        return await self._create_transaction(payload, merchant_ref)

    async def get_transaction_detail(self, reference: str) -> Dict[str, Any]:
        """Get detail transaksi by reference.

        Args:
            reference: Merchant reference / transaction reference

        Returns:
            Dict dengan transaction detail atau error.
        """
        try:
            response = await self._client.get(
                f"{self.base_url}/transaction/detail",
                params={"reference": reference},
                headers=self._headers(),
            )

            data = response.json()
            if data.get("success"):
                return data["data"]
            else:
                logger.error("[tripay] Get detail failed: %s", data.get("message"))
                return {"error": data.get("message", "Unknown error")}

        except Exception as e:
            logger.error("[tripay] Get detail exception: %s", str(e))
            return {"error": str(e)}

    async def _create_transaction(
        self, payload: Dict[str, Any], merchant_ref: str
    ) -> Dict[str, Any]:
        """Internal: create closed transaction."""
        try:
            logger.info(
                "[tripay] 📤 Creating transaction: method=%s ref=%s amount=%s base_url=%s",
                payload.get("method"), merchant_ref, payload.get("amount"), self.base_url,
            )

            response = await self._client.post(
                f"{self.base_url}/transaction/create",
                json=payload,
                headers=self._headers(),
            )

            data = response.json()
            logger.info("[tripay] 📥 Response status=%s success=%s", response.status_code, data.get("success"))

            if data.get("success"):
                result = data["data"]
                # Fee: production pakai fee_customer (yang dibayar user)
                # total_amount: jumlah yang harus dibayar user (amount + fee_customer)
                fee = result.get("fee_customer", 0) or result.get("fee", 0)
                total_amount = result.get("amount_received", result.get("total_fee", 0))
                # amount_received di Tripay = amount - fee_merchant (yang masuk ke kita)
                # Yang user bayar = amount (sudah include fee_customer kalau ada)
                # Pakai field "amount" sebagai total bayar user
                pay_amount = result.get("amount", 0)

                logger.info(
                    "[tripay] ✅ Transaction created: ref=%s pay_amount=%s fee=%s qr_string_len=%s",
                    result.get("reference"), pay_amount, fee,
                    len(result.get("qr_string", "") or ""),
                )
                return {
                    "reference": result.get("reference"),
                    "merchant_ref": result.get("merchant_ref"),
                    "checkout_url": result.get("checkout_url"),
                    "qr_url": result.get("qr_url"),
                    "qr_string": result.get("qr_string"),
                    "amount": pay_amount,
                    "fee": fee,
                    "total_amount": pay_amount,  # amount = total yang user bayar
                    "expired_time": result.get("expired_time"),
                    "status": result.get("status"),
                }
            else:
                error_msg = data.get("message", "Unknown error")
                logger.error("[tripay] ❌ Create failed: %s | full response: %s", error_msg, json.dumps(data))
                return {"error": error_msg}

        except httpx.TimeoutException:
            logger.error("[tripay] ❌ Request timeout")
            return {"error": "Request timeout. Coba lagi nanti."}
        except Exception as e:
            logger.error("[tripay] ❌ Exception: %s", str(e), exc_info=True)
            return {"error": str(e)}

    def _headers(self) -> Dict[str, str]:
        """Standard headers untuk Tripay API."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()


# ======================================================================
# Singleton factory
# ======================================================================

_tripay_client: Optional[TripayClient] = None


def get_tripay_client() -> Optional[TripayClient]:
    """Get singleton TripayClient. Returns None jika belum di-configure."""
    global _tripay_client

    if _tripay_client is not None:
        return _tripay_client

    api_key = settings.TRIPAY_API_KEY
    private_key = settings.TRIPAY_API_SECRET
    merchant_code = settings.TRIPAY_MERCHANT_CODE

    # Jika belum di-configure, return None (mock mode)
    if not api_key or api_key.startswith("your_"):
        logger.warning("[tripay] ⚠️ Tripay belum di-configure, pakai mock mode")
        return None

    is_sandbox = settings.ENVIRONMENT != "production"

    # Safety check: warn if using DEV key in production mode
    if not is_sandbox and api_key.startswith("DEV-"):
        logger.warning(
            "[tripay] ⚠️ ENVIRONMENT=production tapi API key masih DEV (sandbox key). "
            "QRIS akan pakai production URL tapi key sandbox — kemungkinan akan error. "
            "Ganti TRIPAY_API_KEY ke production key dari dashboard Tripay."
        )

    _tripay_client = TripayClient(
        api_key=api_key,
        private_key=private_key,
        merchant_code=merchant_code,
        sandbox=is_sandbox,
    )
    logger.info(
        "[tripay] ✅ TripayClient initialized (sandbox=%s, merchant=%s, base_url=%s)",
        is_sandbox, merchant_code, _tripay_client.base_url,
    )
    return _tripay_client
