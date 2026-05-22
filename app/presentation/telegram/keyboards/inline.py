from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def get_pagination_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Logika penambahan tombol navigasi halaman
    if current_page > 1:
        builder.button(text="⬅️ Sebelumnya", callback_data=f"page:{current_page - 1}")
    if current_page < total_pages:
        builder.button(text="➡️ Selanjutnya", callback_data=f"page:{current_page + 1}")
        
    builder.button(text="🔥 PRODUK POPULER", callback_data="shortcut:popular")
    builder.adjust(2 if (current_page > 1 and current_page < total_pages) else 1, 1)
    
    return builder.as_markup()