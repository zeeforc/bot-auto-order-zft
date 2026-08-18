"""
GoPay Custom QRIS Payment Provider (Async).

Generate dynamic EMVCo QRIS dari static QRIS string milik merchant GoPay.
Pembayaran dideteksi via MacroDroid Android notification interception,
bukan API resmi — sehingga ZERO FEE.

Flow:
1. Ambil static QRIS string dari env (GOPAY_STATIC_QRIS)
2. Inject Tag 54 (Transaction Amount) dengan nominal unik
3. Recalculate CRC16-CCITT (Tag 63)
4. Generate QR image (PNG bytes)
5. User scan & bayar → MacroDroid intercept notif → POST webhook → match amount

Dependencies: crcmod, qrcode
"""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, Optional

import crcmod.predefined
import qrcode

from config import settings
from .base import PaymentProvider, PaymentResult, CallbackData

logger = logging.getLogger(__name__)


def _build_dynamic_qris(static_qris: str, amount: int) -> str:
    """Manipulasi EMVCo QRIS string: inject Tag 54 (amount) + recalc CRC16.

    Args:
        static_qris: Full EMVCo string (termasuk CRC di 4 char terakhir).
        amount: Nominal pembayaran (IDR, integer).

    Returns:
        EMVCo string baru dengan Tag 54 + CRC16 yang valid.

    Raises:
        ValueError: Jika static_qris kosong atau terlalu pendek.
    """
    if not static_qris or len(static_qris) < 50:
        raise ValueError(
            "GOPAY_STATIC_QRIS tidak valid. Pastikan berisi full EMVCo string "
            "(minimal 50 karakter, termasuk CRC)."
        )

    # 1. Remove existing CRC (Tag 63 = 4 char terakhir: "6304" + 4 hex)
    #    Format CRC di EMVCo: "6304XXXX" (tag=63, len=04, value=XXXX)
    #    Tapi di string akhir, hanya 4 hex terakhir yang kita buang
    #    karena "6304" adalah prefix tag, bukan bagian CRC value saja.
    #    Kita perlu remove "6304XXXX" (8 chars) dari akhir.
    if static_qris.endswith("6304") or len(static_qris) < 8:
        # Edge case: string belum ada CRC value
        qris_without_crc = static_qris
    else:
        # Normal: remove last 4 hex chars (CRC value) tapi keep "6304" prefix
        # Sebenarnya, kita remove semua dari "6304" ke akhir
        crc_tag_pos = static_qris.rfind("6304")
        if crc_tag_pos != -1:
            qris_without_crc = static_qris[:crc_tag_pos]
        else:
            # Fallback: just remove last 4 chars
            qris_without_crc = static_qris[:-4]

    # 2. Construct Tag 54 (Transaction Amount)
    amount_str = str(amount)
    amount_len = str(len(amount_str)).zfill(2)
    tag_54 = f"54{amount_len}{amount_str}"

    # 3. Remove existing Tag 54 if present (dari QRIS yang sudah ada amount)
    #    Cari pattern "54XX..." dan remove
    import re
    qris_without_crc = re.sub(r"54\d{2}\d+(?=5[5-9]|6[0-9])", "", qris_without_crc)

    # 4. Insert Tag 54 sebelum Tag 58 (Country Code: "5802ID")
    insert_pos = qris_without_crc.find("5802ID")
    if insert_pos == -1:
        # Fallback: insert sebelum Tag 59 atau di akhir
        insert_pos = qris_without_crc.find("59")
        if insert_pos == -1:
            insert_pos = len(qris_without_crc)

    new_payload = qris_without_crc[:insert_pos] + tag_54 + qris_without_crc[insert_pos:]

    # 5. Append CRC tag prefix + recalculate CRC16-CCITT
    new_payload += "6304"  # Tag 63, Length 04
    crc16 = crcmod.predefined.Crc("crc-ccitt-false")
    crc16.update(new_payload.encode("utf-8"))
    crc_value = crc16.hexdigest().upper().zfill(4)

    final_string = new_payload + crc_value
    return final_string


def _generate_qr_bytes(data: str) -> bytes:
    """Generate QR code image (PNG bytes) dari EMVCo QRIS string.

    Output: high-res PNG, compact, scannable oleh semua e-wallet.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


class GopayProvider(PaymentProvider):
    """GoPay Custom QRIS provider — generate dynamic QRIS locally, zero fee.

    Tidak menggunakan API eksternal. QRIS di-generate dari static string
    milik merchant GoPay dengan manipulasi EMVCo Tag 54 (amount).
    """

    def __init__(self, static_qris: str) -> None:
        self._static_qris = static_qris

    @property
    def name(self) -> str:
        return "GoPay QRIS"

    async def create_payment(
        self,
        order_id: str,
        amount: int,
        product_name: str = "",
        user_id: int = 0,
    ) -> PaymentResult:
        """Generate dynamic QRIS dengan amount yang sudah unik.

        Args:
            order_id: ID order dari sistem kita
            amount: Nominal FINAL (sudah termasuk kode unik)
            product_name: Nama produk (untuk logging)
            user_id: Telegram user ID

        Returns:
            PaymentResult dengan qr_string berisi EMVCo string
        """
        try:
            qris_string = _build_dynamic_qris(self._static_qris, amount)

            logger.info(
                "[gopay] ✅ QRIS generated: order_id=%s amount=%s user=%s qris_len=%s",
                order_id, amount, user_id, len(qris_string),
            )

            return PaymentResult(
                success=True,
                reference=order_id,
                merchant_ref=order_id,
                qr_string=qris_string,
                checkout_url="",  # Tidak ada checkout URL — scan QR langsung
                amount=amount,
                fee=0,  # ZERO FEE — ini keunggulan GoPay custom
                total_amount=amount,
                expired_at=None,
                payment_method="gopay_qris",
            )

        except ValueError as e:
            logger.error("[gopay] ❌ Config error: %s", e)
            return PaymentResult(success=False, error=str(e))
        except Exception as e:
            logger.error("[gopay] ❌ Generate QRIS error: %s", e, exc_info=True)
            return PaymentResult(success=False, error=f"Gagal generate QRIS: {e}")

    async def create_deposit(
        self,
        user_id: int,
        amount: int,
    ) -> PaymentResult:
        """Generate QRIS untuk deposit saldo via GoPay."""
        import time
        order_id = f"DEP-{user_id}-{int(time.time())}"
        return await self.create_payment(
            order_id=order_id,
            amount=amount,
            product_name="Deposit Saldo",
            user_id=user_id,
        )

    async def verify_callback(self, data: Dict[str, Any]) -> CallbackData | None:
        """GoPay custom tidak punya callback verification standar.

        Verifikasi dilakukan di level endpoint (secret token).
        Method ini return CallbackData langsung dari parsed data.
        """
        order_id = data.get("order_id", "")
        amount = data.get("amount", 0)
        status = data.get("status", "paid")

        if not amount:
            return None

        return CallbackData(
            order_id=order_id,
            amount=int(amount),
            status=status,
            payment_method="gopay_qris",
            raw=data,
        )

    async def cancel_transaction(self, order_id: str, amount: int) -> bool:
        """GoPay custom tidak punya API cancel — no-op.

        Order cancellation ditangani di level DB (update status → cancelled).
        """
        logger.info("[gopay] Cancel request (no-op): order_id=%s", order_id)
        return True
