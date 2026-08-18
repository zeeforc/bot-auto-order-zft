import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import aiohttp

from app.infrastructure.payment.base import PaymentProvider, PaymentResult
from config import settings
from app.infrastructure.payment.gopay_qris import _build_dynamic_qris, _generate_qr_bytes

logger = logging.getLogger(__name__)

class GoPayWebProvider(PaymentProvider):
    """
    GoPay Web Provider.
    Menggunakan API Dashboard Web GoBiz/GoPay Merchant (Scraping/Web API).
    """

    def __init__(self):
        self.api_url = getattr(settings, "GOBIZ_API_URL", "")
        self.cookie = getattr(settings, "GOBIZ_COOKIE", "")
        self.authorization = getattr(settings, "GOBIZ_AUTHORIZATION", "")

        if not self.api_url:
            logger.warning("[gopay-web] GOBIZ_API_URL belum di-setting di .env")

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
                error_message="GOPAY_STATIC_QRIS belum dikonfigurasi di .env",
            )

        try:
            # Generate QRIS dinamis menggunakan fungsi yang sudah ada
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
        """Tidak didukung oleh GoPayWebProvider."""
        return PaymentResult(success=False, error="Deposit tidak didukung oleh GoPay Web")

    async def verify_callback(self, data: dict) -> None:
        """Tidak dipakai — GoPayWeb menggunakan polling, bukan webhook callback."""
        return None

    async def cancel_transaction(self, order_id: str, amount: int) -> bool:
        """Tidak didukung — tidak ada API cancel di GoBiz Web."""
        return False

    async def check_payment_status(self, amount: int, created_after: datetime) -> bool:
        """
        Cek apakah ada transaksi masuk (SETTLEMENT) dengan nominal `amount`
        setelah waktu `created_after`.
        """
        if not self.api_url:
            logger.error("[gopay-web] GOBIZ_API_URL tidak diset.")
            return False

        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        if self.cookie:
            headers["Cookie"] = self.cookie
        if self.authorization:
            headers["Authorization"] = self.authorization

        try:
            async with aiohttp.ClientSession() as session:
                # Menggunakan method GET (biasanya API mutasi menggunakan GET)
                # Jika butuh parameter tambahan (seperti from, size, date), 
                # bisa ditambahkan di dalam URL lewat .env
                async with session.get(self.api_url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        text = await response.text()
                        logger.error("[gopay-web] Gagal fetch GoBiz API: %s - %s", response.status, text)
                        return False
                    
                    data = await response.json()
                    transactions = data.get("transactions", [])
                    
                    # Pastikan created_after memiliki tzinfo (timezone-aware)
                    if created_after.tzinfo is None:
                        created_after = created_after.replace(tzinfo=timezone.utc)
                    
                    for trx in transactions:
                        # 1. Cek status
                        if trx.get("transaction_status") != "SETTLEMENT":
                            continue
                        
                        # 2. Parse waktu
                        trx_time_str = trx.get("transaction_time") # "2026-08-19T04:33:55+07:00"
                        if not trx_time_str:
                            continue
                        
                        try:
                            # Python 3.7+ mendukung fromisoformat
                            trx_time = datetime.fromisoformat(trx_time_str)
                        except ValueError:
                            continue
                            
                        # Hanya cek transaksi yang terjadi SETELAH order dibuat
                        if trx_time < created_after:
                            continue

                        # 3. Cek nominal
                        # GoBiz web mereturn gross_amount dikali 100 (misal 100700 -> Rp 1.007)
                        gross_amount = trx.get("gross_amount", 0)
                        real_amount = gross_amount // 100
                        
                        if real_amount == amount:
                            logger.info("[gopay-web] Ditemukan transaksi cocok! Amount: %s, Time: %s", amount, trx_time_str)
                            return True
                            
            return False

        except Exception as e:
            logger.error("[gopay-web] Error saat check_payment_status: %s", e)
            return False
