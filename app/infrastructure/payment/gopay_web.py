import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import aiohttp

from app.infrastructure.payment.base import PaymentProvider, PaymentResult
from config import settings
from app.infrastructure.payment.gopay_qris import _build_dynamic_qris, _generate_qr_bytes

logger = logging.getLogger(__name__)

class GoPayWebProvider(PaymentProvider):
    """
    GoPay Web Provider.
    Menggunakan API Gateway Node.js (ahmadzakiyox) untuk Auto-Refresh Token.
    """

    def __init__(self):
        self.gateway_url = getattr(settings, "GOPAY_GATEWAY_URL", "http://127.0.0.1:3000").rstrip("/")
        self.gateway_api_key = getattr(settings, "GOPAY_GATEWAY_API_KEY", "")

        if not self.gateway_api_key:
            logger.warning("[gopay-web] GOPAY_GATEWAY_API_KEY belum di-setting di .env")

    @property
    def name(self) -> str:
        return "GoPay QRIS (Auto)"

    async def create_payment(
        self, order_id: str, amount: int, product_name: str, user_id: int
    ) -> PaymentResult:
        """
        Generate QRIS secara lokal (karena Static QRIS GoPay bisa di-inject nominal).
        """
        static_qris = settings.GOPAY_STATIC_QRIS
        if not static_qris:
            return PaymentResult(
                success=False,
                error="GOPAY_STATIC_QRIS belum dikonfigurasi di .env",
            )

        try:
            dynamic_qris = _build_dynamic_qris(static_qris, amount)
            qr_bytes = _generate_qr_bytes(dynamic_qris)

            return PaymentResult(
                success=True,
                reference=str(uuid.uuid4())[:8],
                checkout_url="",
                qr_string=dynamic_qris,
                total_amount=amount,
                fee=0,
            )
        except Exception as e:
            logger.error("[gopay-web] Gagal generate QRIS: %s", e)
            return PaymentResult(
                success=False,
                error="Gagal generate QRIS dinamis",
            )

    async def create_deposit(self, user_id: int, amount: int) -> PaymentResult:
        return PaymentResult(success=False, error="Deposit tidak didukung oleh GoPay Web")

    async def verify_callback(self, data: dict) -> None:
        return None

    async def cancel_transaction(self, order_id: str, amount: int) -> bool:
        return False

    async def check_payment_status(self, amount: int, created_after: datetime) -> bool:
        """
        Cek pembayaran via Node.js Gateway.
        Gateway akan mencocokkan nominal.
        """
        if not self.gateway_api_key:
            logger.error("[gopay-web] GOPAY_GATEWAY_API_KEY tidak diset.")
            return False

        # Gateway Node.js membandingkan targetAmount dengan tx.gross_amount dari Gojek (yang dalam sen)
        # Jadi kita harus mengirimkan amount * 100 (misal Rp 1.002 -> 100200)
        gateway_amount = amount * 100

        # Generate unique trx_id based on amount and time to prevent gateway cache collisions
        trx_id = f"TRX-{amount}-{int(created_after.timestamp())}"

        # Build url for nodejs gateway
        url = f"{self.gateway_url}/check-payment?amount={gateway_amount}&trx_id={trx_id}&api_key={self.gateway_api_key}"
        logger.debug("[gopay-web] Requesting Gateway: %s", url)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    text = await response.text()
                    if response.status != 200:
                        text = await response.text()
                        logger.error("[gopay-web] Gateway Error: %s - %s", response.status, text[:200])
                        return False

                    try:
                        data = await response.json()
                    except:
                        logger.error("[gopay-web] Gateway returned invalid JSON: %s", text)
                        return False
                    
                    logger.info("[gopay-web] Gateway Response: %s", data)
                    
                    if data.get("success") and data.get("paid"):
                        logger.info("[gopay-web] ✅ Transaksi cocok (via gateway)! Amount: %s", amount)
                        return True
                        
            return False

        except Exception as e:
            logger.error("[gopay-web] Error saat request ke Gateway: %s", e)
            return False
