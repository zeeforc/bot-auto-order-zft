"""
Handler /start dan pagination untuk daftar produk utama.

Sekarang mengambil data dari database (via ProductRepository).
Fallback ke mock jika DB tidak tersedia.
"""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile

from app.presentation.telegram.keyboards.reply import get_main_menu_keyboard
from app.presentation.telegram.keyboards.inline import get_pagination_keyboard
from app.infrastructure.database.factory import get_product_repository, get_user_repository

router = Router()
logger = logging.getLogger(__name__)

ITEMS_PER_PAGE = 10


async def _get_total_products() -> int:
    """Get total active products dari DB."""
    try:
        repo = await get_product_repository()
        return await repo.count(only_active=True)
    except Exception as e:
        logger.error("[start] Failed to get product count: %s", e)
        return 0


async def _get_products_page(page: int) -> list:
    """Get products untuk halaman tertentu dari DB."""
    try:
        repo = await get_product_repository()
        offset = (page - 1) * ITEMS_PER_PAGE
        products = await repo.list_paginated(limit=ITEMS_PER_PAGE, offset=offset)
        return products
    except Exception as e:
        logger.error("[start] Failed to get products page %s: %s", page, e)
        return []


async def _total_pages() -> int:
    """Hitung total halaman."""
    total = await _get_total_products()
    return max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)


async def format_product_list(page: int) -> str:
    """Format daftar produk induk untuk halaman tertentu (dari DB).

    Nomor ditampilkan sequential (1, 2, 3...) bukan ID database.
    Sorted by nama (abjad).
    """
    products = await _get_products_page(page)
    tp = await _total_pages()

    if not products:
        return "<b>LIST PRODUCT</b>\n\n<i>Belum ada produk tersedia.</i>"

    # Nomor urut = offset + index (bukan product.id)
    offset = (page - 1) * ITEMS_PER_PAGE

    text = "<b>LIST PRODUCT</b>\n\n"
    for i, product in enumerate(products, start=offset + 1):
        text += f"[{i}]. {product.name.upper()} ( {product.stock} )\n"

    now = datetime.now()
    text += f"\n📄 Halaman {page} / {tp}\n"
    text += f"📅 {now.strftime('%d %b %Y %I:%M %p')}\n"
    return text


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    # Ensure user exists in DB
    try:
        user_repo = await get_user_repository()
        await user_repo.get_or_create(message.from_user.id)
    except Exception as e:
        logger.error("[start] Failed to get_or_create user: %s", e)

    total_products = await _get_total_products()
    tp = await _total_pages()

    try:
        banner = FSInputFile("assets/banner_store.jpg")
        await message.answer_photo(
            photo=banner,
            caption=await format_product_list(page=1),
            reply_markup=get_pagination_keyboard(current_page=1, total_pages=tp)
        )
    except Exception:
        await message.answer(
            text=await format_product_list(page=1),
            reply_markup=get_pagination_keyboard(current_page=1, total_pages=tp)
        )

    # Trigger reply keyboard
    await message.answer(
        text="Sistem Otomatis 24 Jam Siap Melayani. Silakan gunakan menu di bawah.",
        reply_markup=get_main_menu_keyboard(total_products=total_products)
    )


@router.callback_query(F.data.startswith("page:"))
async def handle_pagination(callback: CallbackQuery):
    """Handle tombol pagination (Sebelumnya / Selanjutnya)."""
    page = int(callback.data.split(":")[1])
    tp = await _total_pages()

    try:
        await callback.message.edit_caption(
            caption=await format_product_list(page=page),
            reply_markup=get_pagination_keyboard(current_page=page, total_pages=tp)
        )
    except Exception:
        await callback.message.edit_text(
            text=await format_product_list(page=page),
            reply_markup=get_pagination_keyboard(current_page=page, total_pages=tp)
        )
    await callback.answer()


@router.callback_query(F.data == "shortcut:popular")
async def handle_popular_shortcut(callback: CallbackQuery):
    """Handle tombol 🔥 PRODUK POPULER - top 5 by stock."""
    try:
        repo = await get_product_repository()
        # Ambil semua produk aktif, sort by stock descending
        all_products = await repo.list_paginated(limit=100, offset=0)
        sorted_products = sorted(all_products, key=lambda p: p.stock, reverse=True)[:5]

        text = "🔥 <b>PRODUK POPULER</b>\n\n"
        for i, prod in enumerate(sorted_products, 1):
            text += f"{i}. [{prod.id}] {prod.name}\n"
            text += f"   💰 Rp {prod.price:,} | Stok: {prod.stock}\n\n"

        text += "💡 Ketik nomor produk untuk melihat detail."
    except Exception as e:
        logger.error("[start] Popular shortcut error: %s", e)
        text = "⚠️ Gagal memuat produk populer. Coba lagi nanti."

    await callback.message.answer(text=text)
    await callback.answer()
