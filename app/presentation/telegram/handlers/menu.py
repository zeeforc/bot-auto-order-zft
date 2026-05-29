"""
Handler untuk reply keyboard buttons (List Produk, Laporan Stok, Deposit, dll).
Termasuk handler untuk angka produk (1-21) yang dipilih user.

Sekarang mengambil data dari database (via ProductRepository).
"""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from app.presentation.telegram.handlers.start import format_product_list, _total_pages, _get_total_products
from app.presentation.telegram.keyboards.inline import get_pagination_keyboard
from app.presentation.telegram.keyboards.order import get_product_detail_keyboard
from app.presentation.telegram.states import OrderStates
from app.infrastructure.database.factory import get_product_repository

logger = logging.getLogger(__name__)
router = Router()


# --- 1. Tombol "📋 List Produk" ---
@router.message(F.text == "📋 List Produk")
async def menu_list_produk(message: Message):
    logger.info("[menu] List Produk pressed by user_id=%s", message.from_user.id)
    tp = await _total_pages()
    await message.answer(
        text=await format_product_list(page=1),
        reply_markup=get_pagination_keyboard(current_page=1, total_pages=tp)
    )


# --- 2. Tombol "🎫 Voucher" ---
@router.message(F.text == "🎫 Voucher")
async def menu_voucher(message: Message):
    logger.info("[menu] Voucher pressed by user_id=%s", message.from_user.id)
    await message.answer(
        "🎫 <b>VOUCHER</b>\n\n"
        "Punya kode voucher? Redeem sekarang!\n\n"
        "<b>Format:</b>\n"
        "<code>/voucher KODE_VOUCHER</code>\n\n"
        "<b>Contoh:</b>\n"
        "<code>/voucher WELCOME10</code>"
    )


# --- 3. Tombol "📊 Laporan Stok" ---
@router.message(F.text == "📊 Laporan Stok")
async def menu_laporan_stok(message: Message):
    logger.info("[menu] Laporan Stok pressed by user_id=%s", message.from_user.id)

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        if pool:
            async with pool.acquire() as conn:
                products = await conn.fetch("""
                    SELECT p.id, p.name FROM products p
                    WHERE p.is_active = TRUE ORDER BY p.name
                """)

                text = "╭─── <b>[ LAPORAN STOK ]</b> ───\n│\n"
                for prod in products:
                    # Get variants with real-time stock
                    variants = await conn.fetch("""
                        SELECT v.name,
                               COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
                        FROM product_variants v
                        WHERE v.product_id = $1 AND v.is_active = TRUE
                        ORDER BY v.id
                    """, prod['id'])

                    if variants:
                        total_stock = sum(v['stock'] for v in variants)
                        text += f"├ <b>{prod['name']}</b> ({total_stock})\n"
                        for v in variants:
                            text += f"│   ➯ {v['name']}: {v['stock']}x\n"
                    else:
                        text += f"├ {prod['name']}: 0x\n"

                text += "│\n╰──────────────────────\n"
                text += f"📄 Total produk aktif: {len(products)}\n"
        else:
            text = "⚠️ Database tidak tersedia."
    except Exception as e:
        logger.error("[menu] Laporan stok error: %s", e)
        text = "⚠️ Gagal memuat laporan stok. Coba lagi nanti."

    # Telegram limit 4096 chars
    if len(text) > 4000:
        text = text[:3950] + "\n\n... (truncated)"

    await message.answer(text)


# --- 3. Tombol "💰 Deposit" ---
@router.message(F.text == "💰 Deposit")
async def menu_deposit(message: Message, state: FSMContext):
    logger.info("[menu] Deposit pressed by user_id=%s", message.from_user.id)

    # Ambil saldo real dari DB
    from app.application.services.factory import get_deposit_service
    try:
        deposit_svc = await get_deposit_service()
        balance = await deposit_svc.get_user_balance(message.from_user.id)
    except Exception:
        balance = 0

    # Langsung masuk deposit flow
    from app.presentation.telegram.handlers.deposit import _get_deposit_preset_keyboard, MIN_DEPOSIT, MAX_DEPOSIT
    from app.presentation.telegram.states import DepositStates

    await state.clear()

    text = (
        "💰 <b>DEPOSIT SALDO</b>\n\n"
        f"Saldo saat ini: <b>Rp {balance:,}</b>\n\n"
        "Pilih nominal atau ketik jumlah deposit:\n"
        f"📌 Min: Rp {MIN_DEPOSIT:,}\n"
        f"📌 Max: Rp {MAX_DEPOSIT:,}\n"
    )

    await message.answer(text=text, reply_markup=_get_deposit_preset_keyboard())
    await state.set_state(DepositStates.waiting_for_amount)


# --- 4. Tombol "❓ Cara Order" ---
@router.message(F.text == "❓ Cara Order")
async def menu_cara_order(message: Message):
    logger.info("[menu] Cara Order pressed by user_id=%s", message.from_user.id)
    total = await _get_total_products()
    text = (
        "<b>📚 CARA ORDER di T-STORE AUTO ORDER 24 JAM</b>\n\n"
        "1️⃣ Ketik /start untuk memulai\n"
        f"2️⃣ Pilih nomor produk yang kamu inginkan (1-{total})\n"
        "3️⃣ Atur jumlah pembelian dengan tombol ➕ / ➖\n"
        "4️⃣ Pilih metode pembayaran (Saldo / Buy Now)\n"
        "5️⃣ Isi catatan untuk penjual (opsional)\n"
        "6️⃣ Konfirmasi pesanan dan bayar - Selesai!\n\n"
        "❓ Punya pertanyaan? Hubungi admin"
    )
    await message.answer(text)


# --- 5. Tombol "⚠️ Informasi" ---
@router.message(F.text == "⚠️ Informasi")
async def menu_informasi(message: Message):
    logger.info("[menu] Informasi pressed by user_id=%s", message.from_user.id)

    user_id = message.from_user.id
    username = message.from_user.username or "TanpaUsername"

    # Ambil saldo real dari DB
    from app.application.services.factory import get_order_service
    try:
        order_svc = await get_order_service()
        balance = await order_svc.get_user_balance(user_id)
    except Exception:
        balance = 0

    text = (
        "╭─── <b>[ SALDO ]</b> ───\n"
        f"├ <b>• ID :</b> <code>{user_id}</code>\n"
        f"├ <b>• Username :</b> @{username}\n"
        f"├ <b>• Saldo :</b> Rp {balance:,}\n"
        f"├ <b>• LEVEL :</b> BASIC\n"
        f"├ <b>• Pemakaian Saldo :</b> Rp 0\n"
        f"├ <b>• Jumlah Beli :</b> 0\n"
        "╰──────────────────────\n\n"
        "🛠 <b>UP LEVEL untuk diskon lebih besar!</b>"
    )
    await message.answer(text)


# --- 6. Handler untuk angka produk (nomor dari keyboard) ---
@router.message(F.text.regexp(r'^\d+$'))
async def handle_product_number(message: Message, state: FSMContext):
    """Handle ketika user ketik/tap angka (nomor urut produk).

    Nomor = urutan sequential (1, 2, 3...) sorted by nama abjad.
    Bukan product ID database.
    """
    seq_number = int(message.text)
    logger.info("[menu] Product number %s pressed by user_id=%s", seq_number, message.from_user.id)

    # Resolve sequential number → actual product
    # Nomor 1 = produk pertama sorted by name ASC
    try:
        repo = await get_product_repository()
        total = await repo.count(only_active=True)

        if seq_number < 1 or seq_number > total:
            return await message.answer(f"⚠️ Nomor produk tidak valid! Pilih 1 - {total}")

        # Get the product at position seq_number (offset = seq_number - 1)
        products = await repo.list_paginated(limit=1, offset=seq_number - 1)
        if not products:
            return await message.answer(f"⚠️ Produk tidak ditemukan.")

        product = products[0]
    except Exception as e:
        logger.error("[menu] Failed to get product seq=%s: %s", seq_number, e)
        return await message.answer("⚠️ Gagal memuat produk. Coba lagi nanti.")

    if not product.is_available():
        return await message.answer(f"⚠️ Produk <b>{product.name}</b> sedang tidak tersedia.")

    await state.clear()

    # Get variants for this product
    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    variants = []
    if pool:
        async with pool.acquire() as conn:
            variants = await conn.fetch(
                """
                SELECT v.id, v.name, v.code, v.description, v.price,
                       COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
                FROM product_variants v
                WHERE v.product_id = $1 AND v.is_active = TRUE
                ORDER BY v.id
                """,
                product.id,
            )

    if variants:
        # Product has variants — show overview + variant buttons
        # Use short_description for overview (not the long delivery text)
        short_desc = getattr(product, 'short_description', None) or product.description or product.name
        total_sold = 0  # TODO: bisa hitung dari orders nanti

        text = (
            f"<b>{product.name.upper()}</b>\n\n"
            f"➥ Stok Tersedia : {product.stock}\n"
            f"➥ Deskripsi : {short_desc}\n\n"
            f"➥ Variasi :\n"
        )
        for v in variants:
            text += f"  ➯ {v['name']} - Rp {v['price']:,} ({v['stock']})\n"

        text += f"\n📅 {datetime.now().strftime('%d %b %Y %H:%M')}\n"
        text += "\nPilih variasi di bawah:"

        # Build variant buttons
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        kb = InlineKeyboardBuilder()
        for v in variants:
            kb.button(
                text=f"{v['name']} ({v['stock']})",
                callback_data=f"variant:{v['id']}",
            )
        kb.adjust(1)

        await message.answer(text=text, reply_markup=kb.as_markup())

    else:
        # No variants — direct to order flow (legacy behavior)
        wholesale_price = int(product.price * 0.9)

        await state.update_data(product_data={
            "id": product.id,
            "name": product.name,
            "description": product.description or product.name,
            "price": product.price,
            "wholesale": wholesale_price,
            "stock": product.stock,
            "code": f"P{product.id:03d}",
            "variant_id": None,
        })

        caption = (
            f"<b>{product.name.upper()}</b>\n\n"
            f"➥ Produk : {product.name}\n"
            f"➥ Kode : P{product.id:03d}\n"
            f"➥ Sisa Stok : {product.stock}\n"
            f"➥ Deskripsi : {product.description or product.name}\n\n"
            f"➥ Jumlah : 1\n"
            f"➥ Harga : Rp {product.price:,}\n"
            f"➥ Total Harga : Rp {product.price:,}\n"
        )

        try:
            product_msg = await message.answer_photo(
                photo=FSInputFile("assets/banner_store.jpg"),
                caption=caption,
                reply_markup=get_product_detail_keyboard(product.id, qty=1)
            )
        except Exception:
            product_msg = await message.answer(
                text=caption,
                reply_markup=get_product_detail_keyboard(product.id, qty=1)
            )

        await state.update_data(_product_msg_id=product_msg.message_id, _msg_ids=[])
        await state.set_state(OrderStates.waiting_for_qty_or_checkout)


# --- 6b. Handler untuk variant selection ---
@router.callback_query(F.data.startswith("variant:"))
async def handle_variant_selection(callback: CallbackQuery, state: FSMContext):
    """User pilih variasi → tampilkan detail + qty selector + buy buttons."""
    variant_id = int(callback.data.split(":")[1])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    if not pool:
        return await callback.answer("❌ DB error", show_alert=True)

    async with pool.acquire() as conn:
        variant = await conn.fetchrow(
            """
            SELECT v.id, v.product_id, v.name, v.code, v.description, v.price, v.account_template,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock,
                   p.name as parent_name, p.short_description as parent_desc
            FROM product_variants v
            JOIN products p ON v.product_id = p.id
            WHERE v.id = $1
            """,
            variant_id,
        )

    if not variant:
        return await callback.answer("⚠️ Variasi tidak ditemukan.", show_alert=True)

    if variant['stock'] <= 0:
        return await callback.answer("⚠️ Stok variasi ini habis!", show_alert=True)

    await state.clear()

    # Store variant data in FSM
    wholesale_price = int(variant['price'] * 0.9)
    await state.update_data(product_data={
        "id": variant['product_id'],
        "name": variant['name'],
        "description": variant['description'] or variant['name'],
        "price": variant['price'],
        "wholesale": wholesale_price,
        "stock": variant['stock'],
        "code": variant['code'] or f"V{variant_id}",
        "variant_id": variant_id,
    })

    desc = variant['description'] or variant['name']
    now_str = datetime.now().strftime("%d %b %Y %H:%M")

    caption = (
        f"<b>{variant['name'].upper()}</b>\n\n"
        f"➥ Produk : {variant['parent_name']}\n"
        f"➥ Variasi : {variant['name']}\n"
        f"➥ Kode : {variant['code'] or f'V{variant_id}'}\n"
        f"➥ Sisa Stok : {variant['stock']}\n"
        f"➥ Deskripsi : {desc}\n\n"
        f"➥ Jumlah : 1\n"
        f"➥ Harga : Rp {variant['price']:,}\n"
        f"➥ Total Harga : Rp {variant['price']:,}\n\n"
        f"📅 {now_str}"
    )

    try:
        product_msg = await callback.message.answer_photo(
            photo=FSInputFile("assets/banner_store.jpg"),
            caption=caption,
            reply_markup=get_product_detail_keyboard(variant['product_id'], qty=1)
        )
    except Exception:
        product_msg = await callback.message.answer(
            text=caption,
            reply_markup=get_product_detail_keyboard(variant['product_id'], qty=1)
        )

    await state.update_data(_product_msg_id=product_msg.message_id, _msg_ids=[])
    await state.set_state(OrderStates.waiting_for_qty_or_checkout)
    await callback.answer()


# --- 7. Catch-all handler untuk text yang gak match (debug) ---
@router.message(F.text)
async def handle_unknown_text(message: Message):
    """Catch-all handler untuk text yang gak match handler di atas."""
    logger.info("[menu] Unknown text from user_id=%s: %r", message.from_user.id, message.text)
    await message.answer(
        "🤔 Perintah tidak dikenali. Ketik /start untuk melihat menu utama, "
        "atau pilih dari keyboard di bawah."
    )
