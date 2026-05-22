from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_keyboard(total_products: int) -> ReplyKeyboardMarkup:
    """Build main menu keyboard.

    Layout (sesuai referensi):
    Row 1: [List Produk] [Voucher] [Laporan Stok]   ← 3 kolom
    Row 2-N: [1][2][3][4][5][6]                      ← 6 kolom per baris
    Row Last: [Deposit] [Cara Order] [Informasi]     ← 3 kolom
    """
    keyboard = []

    # Row 1: Menu utama (3 kolom)
    keyboard.append([
        KeyboardButton(text="📋 List Produk"),
        KeyboardButton(text="🎫 Voucher"),
        KeyboardButton(text="📊 Laporan Stok"),
    ])

    # Row 2-N: Angka produk (6 per baris)
    row = []
    for i in range(1, total_products + 1):
        row.append(KeyboardButton(text=str(i)))
        if len(row) == 6:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)  # Sisa angka yang kurang dari 6

    # Row terakhir: Deposit, Cara Order, Informasi (3 kolom)
    keyboard.append([
        KeyboardButton(text="💰 Deposit"),
        KeyboardButton(text="❓ Cara Order"),
        KeyboardButton(text="⚠️ Informasi"),
    ])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=False,  # Bisa di-hide saat user tekan back
        input_field_placeholder="Pilih menu atau nomor produk...",
    )
