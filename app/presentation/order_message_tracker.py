"""
In-memory tracker untuk pesan flow order (cross-layer).

Digunakan oleh:
- telegram/handlers/order.py: register pesan flow saat QRIS dibuat
- web/callbacks.py: delete pesan flow saat webhook PAID datang

Kenapa in-memory:
- Pesan flow short-lived (max 15 menit, sesuai TTL QRIS)
- Single-process bot, tidak butuh persistence cross-restart
- Hindari migration tambahan untuk kolom qris_message_id

Kalau bot di-restart sebelum payment masuk, message ID hilang dan pesan
QRIS tidak otomatis terhapus, tapi auto-expire 15 menit tetap berjalan
dari side order.py karena message object di-capture closure di task.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# order_id → (chat_id, [message_ids])
_tracker: Dict[str, Tuple[int, List[int]]] = {}


def track(order_id: str, chat_id: int, message_ids: List[int]) -> None:
    """Daftarkan pesan flow yang harus dihapus saat order PAID."""
    if not order_id or not message_ids:
        return
    _tracker[str(order_id)] = (int(chat_id), [int(m) for m in message_ids if m])


def pop(order_id: str) -> Tuple[int, List[int]] | None:
    """Ambil & hapus tracking untuk order_id (dipanggil saat webhook PAID)."""
    return _tracker.pop(str(order_id), None)


def clear(order_id: str) -> None:
    """Hapus tracking untuk order_id (dipanggil saat order cancelled/expired)."""
    _tracker.pop(str(order_id), None)
