from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

# Gambar 1: Keyboard Detail Produk
def get_product_detail_keyboard(product_id: int, qty: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Baris 1: Kontrol Quantity
    builder.button(text="➖", callback_data=f"qty:minus:{product_id}:{qty}")
    builder.button(text=f"🔢 {qty}", callback_data="qty:noop")
    builder.button(text="➕", callback_data=f"qty:plus:{product_id}:{qty}")
    
    # Baris 2: Metode Pembayaran (Saldo & QRIS via provider aktif)
    builder.button(text="💳 Buy ( Saldo )", callback_data=f"checkout:saldo:{product_id}:{qty}")
    builder.button(text="⚡ Buy ( Now )", callback_data=f"checkout:now:{product_id}:{qty}")
    
    # Baris 3: GoPay QRIS (No Fee — via MacroDroid)
    builder.button(text="🟢 GoPay QRIS (No Fee)", callback_data=f"checkout:gopay:{product_id}:{qty}")
    
    builder.adjust(3, 2, 1)
    return builder.as_markup()

# Gambar 2 & 3: Keyboard Opsi Catatan
def get_note_choice_keyboard(product_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Isi Catatan", callback_data="note:fill")
    builder.button(text="⏩ Skip", callback_data="note:skip")
    builder.button(text="❌ Batal", callback_data="order:cancel")
    builder.adjust(2, 1)
    return builder.as_markup()

# Gambar 4: Keyboard Konfirmasi Akhir
def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Konfirmasi & Proses", callback_data="order:confirm")
    builder.button(text="❌ Batal", callback_data="order:cancel")
    builder.adjust(1, 1)
    return builder.as_markup()