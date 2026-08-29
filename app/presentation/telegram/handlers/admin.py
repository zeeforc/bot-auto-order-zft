import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from config import settings
from app.presentation.telegram.states import (
    AddProductStates,
    EditProductStates,
    DelProductStates,
    BulkAddStates,
    AddVariantStates,
    AddStockStates,
    EditVariantStates,
    DelVariantStates,
    DelAllStockStates,
)

logger = logging.getLogger(__name__)
router = Router()

# Runtime QRIS method (bisa diganti tanpa restart bot)
_current_qris_method: str = settings.QRIS_METHOD

# Available QRIS methods
QRIS_METHODS = {
    "QRIS": {"name": "QRIS by ShopeePay", "fee": "Rp 0 (no fee)"},
    "QRIS2": {"name": "QRIS Standard", "fee": "~Rp 820"},
    "QRISC": {"name": "QRIS Customizable", "fee": "~Rp 820"},
    "QRIS_SHOPEEPAY": {"name": "QRIS Custom ShopeePay", "fee": "Rp 0 (no fee)"},
}


def get_qris_method() -> str:
    """Get current active QRIS method. Dipanggil oleh service layer."""
    return _current_qris_method


def _is_admin(user_id: int) -> bool:
    """Check apakah user adalah admin."""
    return user_id in settings.ADMIN_IDS


def _get_qris_select_keyboard() -> InlineKeyboardMarkup:
    """Keyboard untuk pilih QRIS method."""
    builder = InlineKeyboardBuilder()
    for code, info in QRIS_METHODS.items():
        active = " ✅" if code == _current_qris_method else ""
        builder.button(
            text=f"{info['name']} ({info['fee']}){active}",
            callback_data=f"admin:setqris:{code}",
        )
    builder.adjust(1)
    return builder.as_markup()


# --- /admin command ---
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    logger.info("[admin] /admin from user_id=%s, ADMIN_IDS=%s", message.from_user.id, settings.ADMIN_IDS)
    if not _is_admin(message.from_user.id):
        return  # Silent ignore untuk non-admin

    text = (
        "🔧 <b>ADMIN PANEL</b>\n\n"
        "<b>Payment:</b>\n"
        "• /setprovider - Ganti Payment Provider (GoPay/Pakasir)\n"
        "• /getprovider - Lihat Provider aktif\n"
        "• /setqris - Ganti tipe QRIS gateway\n"
        "• /getqris - Lihat tipe QRIS aktif\n\n"
        "<b>Produk:</b>\n"
        "• /addproduct - Tambah produk (step-by-step)\n"
        "• /editproduct - Edit produk (interactive)\n"
        "• /delproduct - Hapus produk\n"
        "• /listproduct - List semua produk\n"
        "• /restock ID QTY - Quick add stock\n"
        "• /bulkadd - Add banyak produk sekaligus\n"
        "• /hideproduct ID - Sembunyikan produk\n"
        "• /showproduct ID - Tampilkan produk\n\n"
        "<b>Variant:</b>\n"
        "• /addvariant ID - Tambah variasi\n"
        "• /editvariant ID - Edit variasi\n"
        "• /delvariant ID - Hapus variasi\n"
        "• /listvariant ID - List variasi\n"
        "• /hidevariant ID - Sembunyikan variant\n"
        "• /showvariant ID - Tampilkan variant\n\n"
        "<b>Account Stock:</b>\n"
        "• /addstock ID - Add akun ke variant\n"
        "• /viewstock ID - Lihat stok akun\n"
        "• /stockall - Summary stok semua produk\n"
        "• /settemplate ID - Set format tampilan akun\n\n"
        "<b>Voucher:</b>\n"
        "• /addvoucher - Buat voucher baru\n"
        "• /listvoucher - List voucher aktif\n"
        "• /delvoucher ID - Hapus voucher\n\n"
        "<b>User:</b>\n"
        "• /banuser USER_ID - Ban user\n"
        "• /unbanuser USER_ID - Unban user\n"
        "• /broadcast PESAN - Kirim ke semua user\n\n"
        "<b>Refund:</b>\n"
        "• /refund_approve ORDER_ID - Approve refund\n\n"
        "<b>Analytics:</b>\n"
        "• /report [daily|weekly|monthly] - Laporan\n"
        "• /topproducts - Produk terlaris\n"
        "• /topusers - User top spender\n\n"
        "<b>Bulk Operations:</b>\n"
        "• /bulkdel product 1,2,3\n"
        "• /bulkdel variant 1,2,3\n"
        "• /bulkdel stock ID\n"
        "• /bulkdel stockvar ID\n\n"
        "<b>Webhook & Debug:</b>\n"
        "• /testwebhook ORDER_ID - Simulasi PAID\n"
        "• /webhookinfo - Info webhook\n"
        "• /stats - Statistik bot\n"
    )
    await message.answer(text)


# --- /setqris command ---
@router.message(Command("setqris"))
async def cmd_setqris(message: Message):
    if not _is_admin(message.from_user.id):
        return

    text = (
        "⚙️ <b>Pilih QRIS Method</b>\n\n"
        f"Aktif saat ini: <b>{_current_qris_method}</b> "
        f"({QRIS_METHODS.get(_current_qris_method, {}).get('name', 'Unknown')})\n\n"
        "Pilih method di bawah:"
    )
    await message.answer(text, reply_markup=_get_qris_select_keyboard())


# --- Callback: set QRIS method ---
@router.callback_query(F.data.startswith("admin:setqris:"))
async def handle_setqris(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return await callback.answer("⛔ Unauthorized", show_alert=True)

    global _current_qris_method
    method = callback.data.split(":")[2]

    if method not in QRIS_METHODS:
        return await callback.answer("⚠️ Method tidak valid!", show_alert=True)

    old_method = _current_qris_method
    _current_qris_method = method

    logger.info("[admin] QRIS method changed: %s → %s by user_id=%s", old_method, method, callback.from_user.id)

    info = QRIS_METHODS[method]
    await callback.message.edit_text(
        text=(
            f"✅ <b>QRIS Method Updated!</b>\n\n"
            f"• Sebelumnya: {old_method}\n"
            f"• Sekarang: <b>{method}</b>\n"
            f"• Nama: {info['name']}\n"
            f"• Fee: {info['fee']}\n\n"
            f"💡 Perubahan langsung aktif tanpa restart bot."
        )
    )
    await callback.answer("✅ Updated!")


# --- /getqris command ---
@router.message(Command("getqris"))
async def cmd_getqris(message: Message):
    if not _is_admin(message.from_user.id):
        return

    info = QRIS_METHODS.get(_current_qris_method, {})
    text = (
        f"📋 <b>QRIS Method Aktif</b>\n\n"
        f"• Code: <code>{_current_qris_method}</code>\n"
        f"• Nama: {info.get('name', 'Unknown')}\n"
        f"• Fee: {info.get('fee', 'Unknown')}\n"
    )
    await message.answer(text)


# --- /setprovider command ---
@router.message(Command("setprovider"))
async def cmd_setprovider(message: Message):
    if not _is_admin(message.from_user.id):
        return

    from app.infrastructure.payment.factory import get_active_provider_name
    active = get_active_provider_name()

    text = (
        "⚙️ <b>Toggle Payment Provider</b>\n\n"
        f"Aktif saat ini: <b>{active.upper()}</b>\n\n"
        "Klik tombol di bawah untuk mengganti:"
    )

    builder = InlineKeyboardBuilder()
    
    if active == "gopay_web":
        # Jika gopay_web aktif, tombol switch ke pakasir
        builder.button(text="🔄 Switch ke Pakasir", callback_data="admin:setprovider:pakasir")
    else:
        # Jika pakasir aktif, tombol switch ke gopay_web
        builder.button(text="🔄 Switch ke GoPay QRIS", callback_data="admin:setprovider:gopay_web")
        
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())


# --- Callback: set payment provider ---
@router.callback_query(F.data.startswith("admin:setprovider:"))
async def handle_setprovider(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        return await callback.answer("⛔ Unauthorized", show_alert=True)

    provider_name = callback.data.split(":")[2]
    
    from app.infrastructure.payment.factory import get_active_provider_name, set_active_provider
    old_provider = get_active_provider_name()
    
    if old_provider == provider_name:
        return await callback.answer("⚠️ Provider sudah aktif!", show_alert=True)
        
    set_active_provider(provider_name)
    logger.info("[admin] Payment provider changed: %s → %s by user_id=%s", old_provider, provider_name, callback.from_user.id)
    
    await callback.message.edit_text(
        text=(
            f"✅ <b>Payment Provider Updated!</b>\n\n"
            f"• Sebelumnya: {old_provider}\n"
            f"• Sekarang: <b>{provider_name}</b>\n\n"
            f"💡 Perubahan langsung aktif dan tersimpan di .env!"
        )
    )
    await callback.answer("✅ Updated!")


# --- /getprovider command ---
@router.message(Command("getprovider"))
async def cmd_getprovider(message: Message):
    if not _is_admin(message.from_user.id):
        return

    from app.infrastructure.payment.factory import get_active_provider_name, get_active_provider
    name = get_active_provider_name()
    
    provider = get_active_provider()
    provider_class = provider.__class__.__name__ if provider else "None"
    
    text = (
        f"📋 <b>Payment Provider Aktif</b>\n\n"
        f"• Identifier: <code>{name}</code>\n"
        f"• Class: <code>{provider_class}</code>\n"
    )
    await message.answer(text)


# --- /stats command ---
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not _is_admin(message.from_user.id):
        return

    try:
        from app.infrastructure.database.factory import (
            get_product_repository,
            get_user_repository,
            get_order_repository,
        )

        product_repo = await get_product_repository()
        user_repo = await get_user_repository()
        order_repo = await get_order_repository()

        total_products = await product_repo.count(only_active=True)

        text = (
            "📊 <b>BOT STATISTICS</b>\n\n"
            f"• Total Produk Aktif: {total_products}\n"
            f"• QRIS Method: {_current_qris_method}\n"
            f"• Environment: {settings.ENVIRONMENT}\n"
            f"• Repo Type: {type(product_repo).__name__}\n"
        )
    except Exception as e:
        text = f"📊 <b>BOT STATISTICS</b>\n\n⚠️ Error: {str(e)}"

    await message.answer(text)


# ======================================================================
# VOUCHER ADMIN COMMANDS
# ======================================================================

@router.message(Command("addvoucher"))
async def cmd_addvoucher(message: Message):
    """Create voucher: /addvoucher CODE TYPE VALUE [MAX_USAGE] [MIN_PURCHASE]

    Examples:
      /addvoucher WELCOME10 percent 10 100
      /addvoucher DISKON5K fixed 5000 50 20000
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 4:
        await message.answer(
            "📋 <b>Format:</b>\n"
            "<code>/addvoucher CODE TYPE VALUE [MAX_USAGE] [MIN_PURCHASE]</code>\n\n"
            "<b>Contoh:</b>\n"
            "• <code>/addvoucher WELCOME10 percent 10 100</code>\n"
            "  → Diskon 10%, max 100x pakai\n"
            "• <code>/addvoucher DISKON5K fixed 5000 50 20000</code>\n"
            "  → Diskon Rp 5.000, max 50x, min belanja Rp 20.000\n\n"
            "<b>TYPE:</b> fixed | percent\n"
            "<b>MAX_USAGE:</b> default 1\n"
            "<b>MIN_PURCHASE:</b> default 0"
        )
        return

    code = args[1].upper()
    discount_type = args[2].lower()
    discount_value = int(args[3])
    max_usage = int(args[4]) if len(args) > 4 else 1
    min_purchase = int(args[5]) if len(args) > 5 else 0

    if discount_type not in ("fixed", "percent"):
        return await message.answer("⚠️ TYPE harus 'fixed' atau 'percent'")

    if discount_type == "percent" and discount_value > 100:
        return await message.answer("⚠️ Percent tidak boleh lebih dari 100")

    try:
        from app.application.services.factory import get_voucher_service
        voucher_svc = await get_voucher_service()

        # Max discount untuk percent type (default 50% dari value * 1000)
        max_discount = None
        if discount_type == "percent":
            max_discount = discount_value * 10000  # e.g. 10% → max Rp 100.000

        voucher = await voucher_svc.create_voucher(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            min_purchase=min_purchase,
            max_discount=max_discount,
            max_usage=max_usage,
        )

        disc_text = f"Rp {discount_value:,}" if discount_type == "fixed" else f"{discount_value}%"
        await message.answer(
            f"✅ <b>Voucher Created!</b>\n\n"
            f"• Code: <code>{voucher.code}</code>\n"
            f"• Diskon: {disc_text}\n"
            f"• Max Usage: {max_usage}x\n"
            f"• Min Purchase: Rp {min_purchase:,}\n"
        )
    except Exception as e:
        await message.answer(f"❌ Gagal buat voucher: {str(e)}")


@router.message(Command("listvoucher"))
async def cmd_listvoucher(message: Message):
    """List semua voucher aktif."""
    if not _is_admin(message.from_user.id):
        return

    try:
        from app.application.services.factory import get_voucher_service
        voucher_svc = await get_voucher_service()
        vouchers = await voucher_svc.list_active_vouchers()

        if not vouchers:
            return await message.answer("📋 Tidak ada voucher aktif.")

        text = "🎫 <b>VOUCHER AKTIF</b>\n\n"
        for v in vouchers:
            disc = f"Rp {v.discount_value:,}" if v.discount_type == "fixed" else f"{v.discount_value}%"
            remaining = v.max_usage - v.used_count
            text += (
                f"[{v.id}] <code>{v.code}</code>\n"
                f"    Diskon: {disc} | Sisa: {remaining}x\n\n"
            )

        text += "💡 /delvoucher ID untuk deactivate"
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.message(Command("delvoucher"))
async def cmd_delvoucher(message: Message):
    """Deactivate voucher: /delvoucher ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Format: <code>/delvoucher ID</code>")

    try:
        voucher_id = int(args[1])
        from app.application.services.factory import get_voucher_service
        voucher_svc = await get_voucher_service()
        success = await voucher_svc.deactivate_voucher(voucher_id)

        if success:
            await message.answer(f"✅ Voucher ID {voucher_id} deactivated.")
        else:
            await message.answer(f"⚠️ Voucher ID {voucher_id} tidak ditemukan.")
    except ValueError:
        await message.answer("⚠️ ID harus angka.")
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ======================================================================
# WEBHOOK ADMIN COMMANDS
# ======================================================================

@router.message(Command("testwebhook"))
async def cmd_testwebhook(message: Message):
    """Simulasi callback PAID untuk testing (works with any provider).

    Usage: /testwebhook ORDER_ID
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/testwebhook ORDER_ID\n\n"
            "Simulasi callback PAID.\n"
            "Order status akan di-update + notifikasi dikirim ke user."
        )

    order_id = args[1]

    try:
        from app.infrastructure.database.factory import get_order_repository, get_product_repository
        order_repo = await get_order_repository()
        product_repo = await get_product_repository()

        # Check order exists
        order = await order_repo.get_by_id(order_id)
        if not order:
            return await message.answer(f"⚠️ Order {order_id} tidak ditemukan.")

        if order.status != "pending":
            return await message.answer(
                f"⚠️ Order {order_id} status sudah {order.status}.\n"
                f"Hanya order 'pending' yang bisa di-test."
            )

        # Simulate callback processing via Tripay handler (legacy, still works)
        from app.presentation.web.callbacks import _handle_order_callback
        await _handle_order_callback(
            order_id=order_id,
            status="PAID",
            reference=f"TEST-{order_id[:8]}",
            paid_at="just now (simulated)",
        )

        product = await product_repo.get_by_id(order.product_id)
        product_name = product.name if product else "Unknown"

        await message.answer(
            f"✅ <b>Webhook Simulated!</b>\n\n"
            f"• Order: {order_id[:12]}\n"
            f"• Produk: {product_name}\n"
            f"• User: {order.user_id}\n"
            f"• Status: pending → paid\n\n"
            f"📨 Notifikasi sudah dikirim ke user."
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.message(Command("webhookinfo"))
async def cmd_webhookinfo(message: Message):
    """Show webhook configuration info."""
    if not _is_admin(message.from_user.id):
        return

    from config.settings import WEBHOOK_SECRET, WEBHOOK_PORT, ENVIRONMENT
    from app.infrastructure.payment.tripay import get_tripay_client

    secret_masked = WEBHOOK_SECRET[:4] + "***" + WEBHOOK_SECRET[-4:] if len(WEBHOOK_SECRET) > 8 else "NOT SET"
    tripay = get_tripay_client()
    base_url = tripay.base_url if tripay else "N/A"
    merchant = settings.TRIPAY_MERCHANT_CODE or "N/A"

    text = (
        "🌐 <b>WEBHOOK INFO</b>\n\n"
        f"• Mode: {ENVIRONMENT}\n"
        f"• Tripay URL: {base_url}\n"
        f"• Merchant: {merchant}\n"
        f"• Port: {WEBHOOK_PORT}\n"
        f"• Secret: {secret_masked}\n"
        f"• Endpoint: POST /webhook/tripay\n"
        f"• Health: GET /health\n\n"
    )

    if ENVIRONMENT == "production":
        text += (
            "<b>Production Callback URL:</b>\n"
            f"http://103.76.108.195:{WEBHOOK_PORT}/webhook/tripay\n\n"
            "💡 Set URL ini di Tripay Dashboard → Merchant → Callback\n"
            "⚠️ Pastikan port terbuka di firewall server"
        )
    else:
        text += (
            f"<b>Setup ngrok:</b>\n"
            f"ngrok http {WEBHOOK_PORT}\n\n"
            f"<b>Tripay Callback URL:</b>\n"
            f"https://YOUR-NGROK-URL/webhook/tripay\n\n"
            f"💡 Setelah ngrok jalan, copy URL-nya ke\n"
            f"Tripay Dashboard → Merchant → Callback URL"
        )
    await message.answer(text)


# ======================================================================
# PRODUCT MANAGEMENT COMMANDS (Interactive FSM)
# ======================================================================

VALID_CATEGORIES = ["design", "streaming", "software", "ai", "productivity", "lainnya"]
VALID_FIELDS = ["name", "description", "short_description", "delivery_description", "category", "price", "stock"]


def _cancel_kb(back_callback: str | None = None):
    """Inline keyboard with optional back + cancel buttons.

    Args:
        back_callback: If provided, show "🔙 Kembali" button with this callback.
                       If None, only show "❌ Batal".
    """
    kb = InlineKeyboardBuilder()
    if back_callback:
        kb.button(text="🔙 Kembali", callback_data=back_callback)
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    if back_callback:
        kb.adjust(2)
    return kb.as_markup()


def _category_kb(back_callback: str = "admin:cancel"):
    """Inline keyboard for category selection."""
    kb = InlineKeyboardBuilder()
    for cat in VALID_CATEGORIES:
        kb.button(text=cat.title(), callback_data=f"admin:cat:{cat}")
    kb.button(text="🔙 Kembali", callback_data=back_callback)
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()


def _confirm_kb(yes_data: str = "admin:confirm", back_data: str = "admin:cancel"):
    """Inline keyboard with Confirm + Back + Cancel."""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Konfirmasi", callback_data=yes_data)
    kb.button(text="🔙 Kembali", callback_data=back_data)
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    kb.adjust(1, 2)
    return kb.as_markup()


def _field_kb(back_callback: str = "admin:cancel"):
    """Inline keyboard for field selection."""
    kb = InlineKeyboardBuilder()
    for field in VALID_FIELDS:
        kb.button(text=field.title(), callback_data=f"admin:field:{field}")
    kb.button(text="🔙 Kembali", callback_data=back_callback)
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()


# ----- /addproduct (Interactive) -----
@router.message(Command("addproduct"))
async def cmd_addproduct(message: Message, state: FSMContext):
    """Start interactive add product flow."""
    if not _is_admin(message.from_user.id):
        return

    from app.presentation.telegram.states import AddProductStates
    await state.clear()
    await state.set_state(AddProductStates.waiting_for_name)

    await message.answer(
        "➕ <b>TAMBAH PRODUK BARU</b>\n\n"
        "📝 Step 1/5: Masukkan <b>Nama Produk</b>\n\n"
        "<i>Contoh: Netflix Premium 1 Bulan</i>",
        reply_markup=_cancel_kb(),
    )


@router.message(AddProductStates.waiting_for_name)
async def addproduct_name(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if len(name) < 3 or len(name) > 128:
        return await message.answer("⚠️ Nama harus 3-128 karakter. Coba lagi:")

    await state.update_data(name=name)
    await state.set_state(AddProductStates.waiting_for_description)

    await message.answer(
        f"✅ Nama: <b>{name}</b>\n\n"
        "📝 Step 2/5: Masukkan <b>Deskripsi</b>\n\n"
        "<i>Contoh: Netflix Premium Shared, garansi 30 hari</i>",
        reply_markup=_cancel_kb(),
    )


@router.message(AddProductStates.waiting_for_description)
async def addproduct_description(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    desc = message.text.strip()
    if len(desc) > 500:
        return await message.answer("⚠️ Deskripsi maksimal 500 karakter. Coba lagi:")

    await state.update_data(description=desc)
    await state.set_state(AddProductStates.waiting_for_category)

    await message.answer(
        f"✅ Deskripsi: <i>{desc}</i>\n\n"
        "📝 Step 3/5: Pilih <b>Kategori</b>",
        reply_markup=_category_kb(),
    )


@router.callback_query(AddProductStates.waiting_for_category, F.data.startswith("admin:cat:"))
async def addproduct_category(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    category = callback.data.split(":")[2]
    await state.update_data(category=category)
    await state.set_state(AddProductStates.waiting_for_price)

    await callback.message.edit_text(
        f"✅ Kategori: <b>{category}</b>\n\n"
        "📝 Step 4/5: Masukkan <b>Harga (IDR)</b>\n\n"
        "<i>Contoh: 25000 (= Rp 25.000)</i>",
        reply_markup=_cancel_kb(),
    )
    await callback.answer()


@router.message(AddProductStates.waiting_for_price)
async def addproduct_price(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip().replace(".", "").replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        return await message.answer("⚠️ Harga harus angka positif. Coba lagi:")

    await state.update_data(price=price)
    await state.set_state(AddProductStates.waiting_for_stock)

    await message.answer(
        f"✅ Harga: <b>Rp {price:,}</b>\n\n"
        "📝 Step 5/5: Masukkan <b>Stok awal</b>\n\n"
        "<i>Contoh: 100</i>",
        reply_markup=_cancel_kb(),
    )


@router.message(AddProductStates.waiting_for_stock)
async def addproduct_stock(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
    except ValueError:
        return await message.answer("⚠️ Stok harus angka >= 0. Coba lagi:")

    await state.update_data(stock=stock)
    await state.set_state(AddProductStates.waiting_for_confirmation)

    data = await state.get_data()
    await message.answer(
        f"📋 <b>KONFIRMASI PRODUK BARU</b>\n\n"
        f"• Nama       : {data['name']}\n"
        f"• Deskripsi  : {data['description']}\n"
        f"• Kategori   : {data['category']}\n"
        f"• Harga      : Rp {data['price']:,}\n"
        f"• Stok       : {data['stock']}\n\n"
        f"Simpan produk ini?",
        reply_markup=_confirm_kb("admin:addproduct:confirm"),
    )


@router.callback_query(AddProductStates.waiting_for_confirmation, F.data == "admin:addproduct:confirm")
async def addproduct_confirm(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    await state.clear()

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await callback.message.edit_text("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO products (name, description, category, price, stock, is_active)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                RETURNING id, name, price, stock
                """,
                data['name'], data['description'], data['category'], data['price'], data['stock'],
            )

        await callback.message.edit_text(
            f"✅ <b>PRODUK BERHASIL DITAMBAHKAN</b>\n\n"
            f"• ID       : <b>{row['id']}</b>\n"
            f"• Nama     : {row['name']}\n"
            f"• Kategori : {data['category']}\n"
            f"• Harga    : Rp {row['price']:,}\n"
            f"• Stok     : {row['stock']}\n"
        )
        logger.info("[admin] Product added: id=%s name=%s", row['id'], data['name'])
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {str(e)}")
    await callback.answer()


# ----- /editproduct (Interactive) -----
@router.message(Command("editproduct"))
async def cmd_editproduct(message: Message, state: FSMContext):
    """Start interactive edit product flow."""
    if not _is_admin(message.from_user.id):
        return

    from app.presentation.telegram.states import EditProductStates
    await state.clear()
    await state.set_state(EditProductStates.waiting_for_id)

    await message.answer(
        "✏️ <b>EDIT PRODUK</b>\n\n"
        "📝 Masukkan <b>ID Produk</b> yang ingin di-edit:\n\n"
        "<i>Tip: lihat list produk pakai /listproduct atau klik nomor di menu</i>",
        reply_markup=_cancel_kb(),
    )


@router.message(EditProductStates.waiting_for_id)
async def editproduct_id(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        product_id = int(message.text.strip())
    except ValueError:
        return await message.answer("⚠️ ID harus angka. Coba lagi:")

    # Verify product exists
    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT id, name, description, category, price, stock, is_active FROM products WHERE id = $1",
                product_id,
            )

        if not product:
            return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan. Coba lagi:")

        await state.update_data(product_id=product_id)
        await state.set_state(EditProductStates.waiting_for_field)

        await message.answer(
            f"📋 <b>PRODUK DITEMUKAN</b>\n\n"
            f"• ID         : {product['id']}\n"
            f"• Nama       : {product['name']}\n"
            f"• Deskripsi  : {product['description']}\n"
            f"• Kategori   : {product['category']}\n"
            f"• Harga      : Rp {product['price']:,}\n"
            f"• Stok       : {product['stock']}\n"
            f"• Active     : {product['is_active']}\n\n"
            f"Pilih <b>field</b> yang ingin di-edit:",
            reply_markup=_field_kb(back_callback="editproduct:back_to_id"),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(EditProductStates.waiting_for_field, F.data.startswith("admin:field:"))
async def editproduct_field(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    field = callback.data.split(":")[2]
    await state.update_data(field=field)
    await state.set_state(EditProductStates.waiting_for_value)

    if field == "category":
        await callback.message.edit_text(
            f"📝 Pilih <b>Kategori</b> baru:",
            reply_markup=_category_kb(),
        )
    else:
        hint = {
            "name": "<i>Contoh: Netflix Premium 2 Bulan</i>",
            "description": "<i>Contoh: Netflix Premium Shared, garansi 60 hari</i>",
            "price": "<i>Contoh: 50000</i>",
            "stock": "<i>Contoh: 200</i>",
        }
        await callback.message.edit_text(
            f"📝 Masukkan nilai baru untuk <b>{field}</b>:\n\n{hint.get(field, '')}",
            reply_markup=_cancel_kb(),
        )
    await callback.answer()


# Handle category selection during edit
@router.callback_query(EditProductStates.waiting_for_value, F.data.startswith("admin:cat:"))
async def editproduct_category_value(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return
    category = callback.data.split(":")[2]
    await _apply_edit(callback.message, state, category, edit_msg=True)
    await callback.answer()


@router.message(EditProductStates.waiting_for_value)
async def editproduct_value(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await _apply_edit(message, state, message.text.strip(), edit_msg=False)


async def _apply_edit(message: Message, state: FSMContext, value, edit_msg: bool):
    """Apply the edit to the database."""
    data = await state.get_data()
    field = data["field"]
    product_id = data["product_id"]

    # Validate numeric fields
    if field in ("price", "stock"):
        try:
            value = int(str(value).replace(".", "").replace(",", ""))
            if value < 0:
                raise ValueError
        except ValueError:
            await message.answer(f"⚠️ {field} harus angka >= 0. Coba lagi:")
            return

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            query = f"UPDATE products SET {field} = $2 WHERE id = $1 RETURNING id, name, price, stock"
            row = await conn.fetchrow(query, product_id, value)

        # Keep state for back button
        await state.set_state(EditProductStates.waiting_for_field)

        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Kembali ke Produk", callback_data=f"editproduct:back:{product_id}")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        text = (
            f"✅ <b>PRODUK DIUPDATE</b>\n\n"
            f"ID : {row['id']}\n"
            f"Nama : {row['name']}\n"
            f"Harga : Rp {row['price']:,}\n"
            f"Stok : {row['stock']}\n"
            f"Field : {field} → {value}"
        )

        if edit_msg:
            await message.edit_text(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text, reply_markup=kb.as_markup())

        logger.info("[admin] Product edited: id=%s field=%s value=%s", product_id, field, value)
    except Exception as e:
        await state.clear()
        if edit_msg:
            await message.edit_text(f"❌ Error: {str(e)}")
        else:
            await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(F.data == "editproduct:back_to_id")
async def editproduct_back_to_id(callback: CallbackQuery, state: FSMContext):
    """Kembali ke step input ID produk."""
    if not _is_admin(callback.from_user.id):
        return
    await state.clear()
    await state.set_state(EditProductStates.waiting_for_id)

    await callback.message.answer(
        "✏️ <b>EDIT PRODUK</b>\n\n"
        "📝 Masukkan <b>ID Produk</b> yang ingin di-edit:\n\n"
        "<i>Tip: lihat list produk pakai /listproduct atau klik nomor di menu</i>",
        reply_markup=_cancel_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("editproduct:back:"))
async def editproduct_back(callback: CallbackQuery, state: FSMContext):
    """Kembali ke menu field selection produk."""
    if not _is_admin(callback.from_user.id):
        return

    product_id = int(callback.data.split(":")[2])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow(
            "SELECT id, name, description, category, price, stock, is_active FROM products WHERE id = $1",
            product_id,
        )

    if not product:
        await state.clear()
        return await callback.answer("⚠️ Produk tidak ditemukan.", show_alert=True)

    await state.update_data(product_id=product_id)
    await state.set_state(EditProductStates.waiting_for_field)

    await callback.message.answer(
        f"📋 <b>PRODUK DETAIL</b>\n\n"
        f"ID : {product['id']}\n"
        f"Nama : {product['name']}\n"
        f"Deskripsi : {product['description']}\n"
        f"Kategori : {product['category']}\n"
        f"Harga : Rp {product['price']:,}\n"
        f"Stok : {product['stock']}\n"
        f"Active : {product['is_active']}\n\n"
        f"Pilih field yang mau di-edit:",
        reply_markup=_field_kb(back_callback="editproduct:back_to_id"),
    )
    await callback.answer()


# ----- /delproduct (Interactive with confirmation) -----
@router.message(Command("delproduct"))
async def cmd_delproduct(message: Message, state: FSMContext):
    """Start interactive delete product flow."""
    if not _is_admin(message.from_user.id):
        return

    from app.presentation.telegram.states import DelProductStates
    await state.clear()
    await state.set_state(DelProductStates.waiting_for_id)

    await message.answer(
        "🗑️ <b>HAPUS PRODUK</b>\n\n"
        "📝 Masukkan <b>ID Produk</b> yang ingin di-hapus:",
        reply_markup=_cancel_kb(),
    )


@router.message(DelProductStates.waiting_for_id)
async def delproduct_id(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        product_id = int(message.text.strip())
    except ValueError:
        return await message.answer("⚠️ ID harus angka. Coba lagi:")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT id, name, price, stock FROM products WHERE id = $1",
                product_id,
            )

        if not product:
            return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

        await state.update_data(product_id=product_id, product_name=product['name'])
        await state.set_state(DelProductStates.waiting_for_confirmation)

        await message.answer(
            f"⚠️ <b>KONFIRMASI HAPUS</b>\n\n"
            f"• ID    : {product['id']}\n"
            f"• Nama  : {product['name']}\n"
            f"• Harga : Rp {product['price']:,}\n"
            f"• Stok  : {product['stock']}\n\n"
            f"Yakin ingin menghapus produk ini?\n"
            f"<i>(soft delete: produk akan di-nonaktifkan, bukan dihapus permanen)</i>",
            reply_markup=_confirm_kb("admin:delproduct:confirm"),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(DelProductStates.waiting_for_confirmation, F.data == "admin:delproduct:confirm")
async def delproduct_confirm(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    await state.clear()

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE products SET is_active = FALSE WHERE id = $1 RETURNING id, name",
                data['product_id'],
            )

        if row:
            await callback.message.edit_text(
                f"✅ Produk <b>{row['name']}</b> (ID: {row['id']}) telah di-nonaktifkan."
            )
            logger.info("[admin] Product deactivated: id=%s", row['id'])
        else:
            await callback.message.edit_text(f"⚠️ Produk tidak ditemukan.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {str(e)}")
    await callback.answer()


# ----- /restock (Quick stock add) -----
@router.message(Command("restock"))
async def cmd_restock(message: Message):
    """Quick restock: tambah stok ke produk existing.

    Usage: /restock ID JUMLAH
    Contoh: /restock 1 100 (tambah 100 stok ke produk ID 1)
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 3:
        return await message.answer(
            "📦 <b>RESTOCK PRODUK</b>\n\n"
            "<b>Format:</b>\n"
            "<code>/restock ID JUMLAH</code>\n\n"
            "<b>Contoh:</b>\n"
            "• <code>/restock 1 100</code> → tambah 100 stok ke produk ID 1\n"
            "• <code>/restock 5 -50</code> → kurangi 50 stok\n\n"
            "💡 Cara cepat tambah stok tanpa edit field manual."
        )

    try:
        product_id = int(args[1])
        qty = int(args[2])
    except ValueError:
        return await message.answer("⚠️ ID dan jumlah harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE products
                   SET stock = stock + $2
                 WHERE id = $1
                   AND stock + $2 >= 0
                RETURNING id, name, stock
                """,
                product_id, qty,
            )

        if not row:
            return await message.answer(
                f"⚠️ Gagal restock. Produk ID {product_id} tidak ada,\n"
                f"atau jumlah pengurangan lebih besar dari stok saat ini."
            )

        action = "ditambah" if qty > 0 else "dikurangi"
        await message.answer(
            f"✅ <b>STOK DI-UPDATE</b>\n\n"
            f"• ID         : {row['id']}\n"
            f"• Nama       : {row['name']}\n"
            f"• Stok {action:<10}: {abs(qty)}\n"
            f"• Stok Total : <b>{row['stock']}</b>"
        )
        logger.info("[admin] Restock: id=%s qty=%s new_stock=%s", product_id, qty, row['stock'])
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ----- /addstock (Interactive: pilih produk → pilih variant → paste akun) -----
@router.message(Command("addstock"))
async def cmd_addstock(message: Message, state: FSMContext):
    """Interactive add stock: pilih produk → pilih variant → paste akun."""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📦 <b>ADD ACCOUNT STOCK</b>\n\n"
            "Format: /addstock [ID produk induk]\n\n"
            "Contoh: /addstock 1\n"
            "Bot akan tampilkan variant, pilih, lalu paste akun."
        )

    try:
        product_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID produk harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT id, name FROM products WHERE id = $1", product_id
            )
            if not product:
                return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

            variants = await conn.fetch(
                """SELECT v.id, v.name,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
            FROM product_variants v WHERE v.product_id = $1 AND v.is_active = TRUE ORDER BY v.id""",
                product_id,
            )

        if not variants:
            # No variants — add directly to product level
            await state.clear()
            await state.update_data(addstock_product_id=product_id, addstock_variant_id=None)
            await state.set_state(AddStockStates.waiting_for_accounts)
            return await message.answer(
                f"📦 <b>{product['name']}</b>\n\n"
                f"Produk ini tidak punya variant.\n"
                f"Paste data akun sekarang (1 akun per baris):\n\n"
                f"💡 Format: field1|field2|field3\n"
                f"Contoh: email@gmail.com|password123",
                reply_markup=_cancel_kb(),
            )

        # Has variants — show variant buttons
        await state.clear()
        await state.update_data(addstock_product_id=product_id)
        await state.set_state(AddStockStates.waiting_for_variant_select)

        kb = InlineKeyboardBuilder()
        for v in variants:
            kb.button(text=f"{v['name']} (stok: {v['stock']})", callback_data=f"addstock:var:{v['id']}")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await message.answer(
            f"📦 <b>ADD STOCK - {product['name']}</b>\n\n"
            f"Pilih variant yang mau di-restock:",
            reply_markup=kb.as_markup(),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(AddStockStates.waiting_for_variant_select, F.data.startswith("addstock:var:"))
async def addstock_variant_selected(callback: CallbackQuery, state: FSMContext):
    """User pilih variant → minta paste akun."""
    if not _is_admin(callback.from_user.id):
        return

    variant_id = int(callback.data.split(":")[2])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        variant = await conn.fetchrow(
            "SELECT id, name, account_template, product_id FROM product_variants WHERE id = $1", variant_id
        )
        # Fallback: check product-level template if variant doesn't have one
        template = variant['account_template'] if variant and variant['account_template'] else None
        if not template and variant:
            prod_tmpl = await conn.fetchval(
                "SELECT account_template FROM products WHERE id = $1", variant['product_id']
            )
            if prod_tmpl:
                template = prod_tmpl

    if not variant:
        return await callback.answer("⚠️ Variant tidak ditemukan.", show_alert=True)

    await state.update_data(addstock_variant_id=variant_id)
    await state.set_state(AddStockStates.waiting_for_accounts)

    # Build dynamic format hint + contoh based on template
    if template:
        labels = template.split("|")
        format_str = "|".join(labels)
        # Generate example based on labels
        example_parts = []
        for lbl in labels:
            lbl_lower = lbl.lower()
            if "email" in lbl_lower:
                example_parts.append("user@gmail.com")
            elif "pass" in lbl_lower:
                example_parts.append("Password123")
            elif "profile" in lbl_lower or "profil" in lbl_lower:
                example_parts.append("Profile 1")
            elif "pin" in lbl_lower:
                example_parts.append("1234")
            else:
                example_parts.append(f"data_{lbl_lower}")
        example = "|".join(example_parts)
        hint_text = (
            f"Format: {format_str}\n\n"
            f"Contoh:\n"
            f"{example}"
        )
    else:
        hint_text = (
            f"Format: data_akun (1 baris per akun)\n\n"
            f"Contoh:\n"
            f"user@gmail.com|Password123"
        )

    await callback.message.edit_text(
        f"📦 <b>ADD STOCK - {variant['name']}</b>\n\n"
        f"Paste data akun sekarang (1 akun per baris):\n\n"
        f"{hint_text}",
        reply_markup=_cancel_kb(),
    )
    await callback.answer()


@router.message(AddStockStates.waiting_for_accounts)
async def addstock_receive_accounts(message: Message, state: FSMContext):
    """Receive pasted account data and insert to DB."""
    if not _is_admin(message.from_user.id):
        return

    data = await state.get_data()
    product_id = data.get("addstock_product_id")
    variant_id = data.get("addstock_variant_id")

    lines = [line.strip() for line in message.text.split("\n") if line.strip()]
    if not lines:
        return await message.answer("⚠️ Tidak ada data akun.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            inserted = 0
            for acc in lines:
                try:
                    await conn.execute(
                        "INSERT INTO account_stock (product_id, variant_id, account_data) VALUES ($1, $2, $3)",
                        product_id, variant_id, acc,
                    )
                    inserted += 1
                except Exception:
                    pass

            # Update variant stock
            if variant_id:
                available = await conn.fetchval(
                    "SELECT COUNT(*) FROM account_stock WHERE variant_id = $1 AND is_used = FALSE",
                    variant_id,
                )
                await conn.execute("UPDATE product_variants SET stock = $2 WHERE id = $1", variant_id, available)

                # Sync parent stock
                parent_stock = await conn.fetchval(
                    "SELECT COALESCE(SUM(stock), 0) FROM product_variants WHERE product_id = $1 AND is_active = TRUE",
                    product_id,
                )
                await conn.execute("UPDATE products SET stock = $2 WHERE id = $1", product_id, parent_stock)

                vname = await conn.fetchval("SELECT name FROM product_variants WHERE id = $1", variant_id)
            else:
                available = await conn.fetchval(
                    "SELECT COUNT(*) FROM account_stock WHERE product_id = $1 AND is_used = FALSE",
                    product_id,
                )
                await conn.execute("UPDATE products SET stock = $2 WHERE id = $1", product_id, available)
                vname = None

        target = vname or f"Product ID {product_id}"

        # Reset state to allow more stock additions via back button
        await state.clear()

        # Back button → kembali ke pilih variant
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Kembali ke Variant", callback_data=f"addstock:back:{product_id}")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await message.answer(
            f"✅ <b>STOCK DITAMBAHKAN</b>\n\n"
            f"Target : {target}\n"
            f"Ditambah : {inserted} akun\n"
            f"Stok tersedia : {available}",
            reply_markup=kb.as_markup(),
        )
        logger.info("[admin] Addstock: variant=%s added=%s total=%s", variant_id or product_id, inserted, available)
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(F.data.startswith("addstock:back:"))
async def addstock_back(callback: CallbackQuery, state: FSMContext):
    """Kembali ke menu pilih variant untuk add stock lagi."""
    if not _is_admin(callback.from_user.id):
        return

    product_id = int(callback.data.split(":")[2])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT id, name FROM products WHERE id = $1", product_id)
        variants = await conn.fetch(
            """SELECT v.id, v.name,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
            FROM product_variants v WHERE v.product_id = $1 AND v.is_active = TRUE ORDER BY v.id""",
            product_id,
        )

    if not product:
        return await callback.answer("⚠️ Produk tidak ditemukan.", show_alert=True)

    if not variants:
        return await callback.answer("⚠️ Tidak ada variant.", show_alert=True)

    await state.clear()
    await state.update_data(addstock_product_id=product_id)
    await state.set_state(AddStockStates.waiting_for_variant_select)

    kb = InlineKeyboardBuilder()
    for v in variants:
        kb.button(text=f"{v['name']} (stok: {v['stock']})", callback_data=f"addstock:var:{v['id']}")
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    kb.adjust(1)

    await callback.message.answer(
        f"📦 <b>ADD STOCK - {product['name']}</b>\n\n"
        f"Pilih variant yang mau di-restock:",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


# ----- /addvariant (Interactive: tambah variasi ke produk induk) -----
@router.message(Command("addvariant"))
async def cmd_addvariant(message: Message, state: FSMContext):
    """Interactive add variant ke produk induk."""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📦 <b>ADD VARIANT</b>\n\n"
            "Format: /addvariant [ID produk induk]\n\n"
            "Contoh: /addvariant 1\n"
            "Bot akan tanya nama, kode, deskripsi, dan harga."
        )

    try:
        product_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            product = await conn.fetchrow("SELECT id, name FROM products WHERE id = $1", product_id)

        if not product:
            return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

        await state.clear()
        await state.update_data(variant_product_id=product_id, variant_product_name=product['name'])
        await state.set_state(AddVariantStates.waiting_for_name)

        await message.answer(
            f"➕ <b>TAMBAH VARIANT - {product['name']}</b>\n\n"
            f"Step 1/4: Masukkan <b>Nama Variasi</b>\n\n"
            f"Contoh: CANVA PRO TEAM 1 BULAN",
            reply_markup=_cancel_kb(),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.message(AddVariantStates.waiting_for_name)
async def addvariant_name(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if len(name) < 3:
        return await message.answer("⚠️ Nama minimal 3 karakter.")

    await state.update_data(variant_name=name)
    await state.set_state(AddVariantStates.waiting_for_code)

    await message.answer(
        f"✅ Nama: <b>{name}</b>\n\n"
        f"Step 2/4: Masukkan <b>Kode</b> (singkat, unik)\n\n"
        f"Contoh: ct1m, nf1b, sp3m",
        reply_markup=_cancel_kb(),
    )


@router.message(AddVariantStates.waiting_for_code)
async def addvariant_code(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    code = message.text.strip().lower()
    if len(code) > 32:
        return await message.answer("⚠️ Kode maksimal 32 karakter.")

    await state.update_data(variant_code=code)
    await state.set_state(AddVariantStates.waiting_for_description)

    await message.answer(
        f"✅ Kode: <b>{code}</b>\n\n"
        f"Step 3/4: Masukkan <b>Deskripsi</b> variasi\n\n"
        f"Ini yang akan ditampilkan ke user saat pilih variasi.\n"
        f"Contoh: Canva Pro via invite, garansi 30 hari",
        reply_markup=_cancel_kb(),
    )


@router.message(AddVariantStates.waiting_for_description)
async def addvariant_description(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    desc = message.text.strip()

    await state.update_data(variant_description=desc)
    await state.set_state(AddVariantStates.waiting_for_price)

    await message.answer(
        f"✅ Deskripsi: <i>{desc[:100]}</i>\n\n"
        f"Step 4/4: Masukkan <b>Harga (IDR)</b>\n\n"
        f"Contoh: 25000",
        reply_markup=_cancel_kb(),
    )


@router.message(AddVariantStates.waiting_for_price)
async def addvariant_price(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        price = int(message.text.strip().replace(".", "").replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        return await message.answer("⚠️ Harga harus angka positif.")

    await state.update_data(variant_price=price)
    await state.set_state(AddVariantStates.waiting_for_confirmation)

    data = await state.get_data()
    await message.answer(
        f"📋 <b>KONFIRMASI VARIANT BARU</b>\n\n"
        f"Produk Induk : {data['variant_product_name']}\n"
        f"Nama Variasi : {data['variant_name']}\n"
        f"Kode : {data['variant_code']}\n"
        f"Deskripsi : {data['variant_description'][:80]}\n"
        f"Harga : Rp {price:,}\n\n"
        f"Simpan?",
        reply_markup=_confirm_kb("admin:addvariant:confirm"),
    )


@router.callback_query(AddVariantStates.waiting_for_confirmation, F.data == "admin:addvariant:confirm")
async def addvariant_confirm(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    await state.clear()

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO product_variants (product_id, name, code, description, price, stock)
                VALUES ($1, $2, $3, $4, $5, 0)
                RETURNING id, name
                """,
                data['variant_product_id'],
                data['variant_name'],
                data['variant_code'],
                data['variant_description'],
                data['variant_price'],
            )

        await callback.message.edit_text(
            f"✅ <b>VARIANT DITAMBAHKAN</b>\n\n"
            f"ID Variant : {row['id']}\n"
            f"Nama : {row['name']}\n"
            f"Produk Induk : {data['variant_product_name']}\n"
            f"Harga : Rp {data['variant_price']:,}\n"
            f"Stok : 0 (tambah via /addstock {data['variant_product_id']})"
        )
        logger.info("[admin] Variant added: id=%s name=%s parent=%s", row['id'], row['name'], data['variant_product_id'])
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {str(e)}")
    await callback.answer()


# ----- /viewstock (View account stock for a product) -----
@router.message(Command("viewstock"))
async def cmd_viewstock(message: Message):
    """View account stock per produk. Usage: /viewstock ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b> /viewstock ID\n\n"
            "Lihat jumlah akun tersedia per produk."
        )

    try:
        product_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT id, name FROM products WHERE id = $1", product_id
            )
            if not product:
                return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

            available = await conn.fetchval(
                "SELECT COUNT(*) FROM account_stock WHERE product_id = $1 AND is_used = FALSE",
                product_id,
            )
            used = await conn.fetchval(
                "SELECT COUNT(*) FROM account_stock WHERE product_id = $1 AND is_used = TRUE",
                product_id,
            )
            total = available + used

        await message.answer(
            f"📦 <b>ACCOUNT STOCK - {product['name']}</b>\n\n"
            f"Tersedia : {available}\n"
            f"Terpakai : {used}\n"
            f"Total : {total}"
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ----- /stockall (View all products account stock summary) -----
@router.message(Command("stockall"))
async def cmd_stockall(message: Message):
    """View account stock summary for all products."""
    if not _is_admin(message.from_user.id):
        return

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.id, p.name,
                       COUNT(a.id) FILTER (WHERE a.is_used = FALSE) as available,
                       COUNT(a.id) FILTER (WHERE a.is_used = TRUE) as used
                FROM products p
                LEFT JOIN account_stock a ON a.product_id = p.id
                WHERE p.is_active = TRUE
                GROUP BY p.id, p.name
                ORDER BY p.id
                """
            )

        if not rows:
            return await message.answer("📦 Belum ada produk.")

        text = "📦 <b>ACCOUNT STOCK SUMMARY</b>\n\n"
        for r in rows:
            avail = r['available'] or 0
            used = r['used'] or 0
            text += f"[{r['id']}] {r['name']}\n    Tersedia: {avail} | Terpakai: {used}\n\n"

        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ----- /settemplate (Set display template for product accounts) -----
@router.message(Command("settemplate"))
async def cmd_settemplate(message: Message):
    """Set template tampilan akun per produk.

    Usage: /settemplate ID Label1|Label2|Label3
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer(
            "📋 <b>SET ACCOUNT TEMPLATE</b>\n\n"
            "<b>Format:</b>\n"
            "/settemplate ID Label1|Label2|Label3\n\n"
            "<b>Contoh:</b>\n"
            "/settemplate 5 Email|Password|Profile|PIN\n"
            "/settemplate 1 Email|Password\n\n"
            "💡 Label harus match jumlah field di data akun.\n"
            "Misal data: email@gmail.com|Pass123|Profile 3|1234\n"
            "Template: Email|Password|Profile|PIN"
        )

    try:
        product_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID harus angka.")

    template = args[2].strip()

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE products SET account_template = $2 WHERE id = $1 RETURNING id, name",
                product_id, template,
            )

        if not row:
            return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

        labels = template.split("|")
        await message.answer(
            f"✅ <b>TEMPLATE DI-SET</b>\n\n"
            f"Produk : {row['name']}\n"
            f"Template : {template}\n"
            f"Fields : {len(labels)} ({', '.join(labels)})\n\n"
            f"💡 Saat deliver, akun ditampilkan:\n"
            + "\n".join(f"  {lbl} : (data)" for lbl in labels)
        )
        logger.info("[admin] Template set: product=%s template=%s", product_id, template)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ----- /listproduct (Quick view all products) -----
@router.message(Command("listproduct"))
async def cmd_listproduct(message: Message):
    """List all products with ID, name, price, stock."""
    if not _is_admin(message.from_user.id):
        return

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, name, category, price, stock, is_active FROM products ORDER BY id"
            )

        if not rows:
            return await message.answer("📋 Belum ada produk.")

        text = "📦 <b>SEMUA PRODUK</b>\n\n"
        for r in rows:
            status = "✅" if r['is_active'] else "❌"
            text += (
                f"{status} <b>[{r['id']}]</b> {r['name']}\n"
                f"     Rp {r['price']:,} | Stok: {r['stock']} | {r['category']}\n\n"
            )

        # Telegram message limit ~4096 chars
        if len(text) > 4000:
            text = text[:3950] + "\n\n... (truncated)"

        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ----- /bulkadd (Add multiple products at once) -----
@router.message(Command("bulkadd"))
async def cmd_bulkadd(message: Message, state: FSMContext):
    """Bulk add: paste multi-line text untuk add banyak produk sekaligus."""
    if not _is_admin(message.from_user.id):
        return

    from app.presentation.telegram.states import BulkAddStates
    await state.clear()
    await state.set_state(BulkAddStates.waiting_for_data)

    await message.answer(
        "📦 <b>BULK ADD PRODUK</b>\n\n"
        "Paste data produk dengan format <b>1 baris per produk</b>:\n\n"
        "<code>NAMA | DESKRIPSI | KATEGORI | HARGA | STOK</code>\n\n"
        "<b>Contoh (paste sekaligus):</b>\n"
        "<code>Netflix 1 Bulan | Premium shared | streaming | 25000 | 100\n"
        "Spotify 1 Bulan | Individual | streaming | 15000 | 200\n"
        "Canva Pro 1 Tahun | Team annual | design | 150000 | 50</code>\n\n"
        "<b>Kategori valid:</b> design, streaming, software, ai, productivity, lainnya\n\n"
        "💡 Bisa puluhan baris sekaligus. Kirim sekarang:",
        reply_markup=_cancel_kb(),
    )


@router.message(BulkAddStates.waiting_for_data)
async def bulkadd_data(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    lines = [line.strip() for line in message.text.split("\n") if line.strip()]
    if not lines:
        return await message.answer("⚠️ Tidak ada data. Coba lagi:")

    # Parse all lines
    parsed = []
    errors = []
    for i, line in enumerate(lines, 1):
        parts = [p.strip() for p in line.split("|")]
        if len(parts) != 5:
            errors.append(f"Baris {i}: format salah (butuh 5 kolom dipisah '|')")
            continue
        try:
            name, desc, cat, price_s, stock_s = parts
            price = int(price_s.replace(".", "").replace(",", ""))
            stock = int(stock_s)
            if price < 0 or stock < 0:
                raise ValueError("nilai negatif")
            parsed.append((name, desc, cat, price, stock))
        except ValueError as ve:
            errors.append(f"Baris {i}: {ve} ({line[:40]})")

    if errors and not parsed:
        return await message.answer(
            f"❌ <b>Semua baris error:</b>\n\n" + "\n".join(errors[:10])
        )

    await state.update_data(parsed=parsed, errors=errors)
    await state.set_state(BulkAddStates.waiting_for_confirmation)

    preview = "\n".join([
        f"{i+1}. {p[0][:30]} | {p[2]} | Rp {p[3]:,} | stok {p[4]}"
        for i, p in enumerate(parsed[:10])
    ])
    if len(parsed) > 10:
        preview += f"\n... +{len(parsed) - 10} produk lainnya"

    text = f"📋 <b>PREVIEW BULK ADD</b>\n\n"
    text += f"✅ Valid : <b>{len(parsed)} produk</b>\n"
    if errors:
        text += f"❌ Error : <b>{len(errors)} baris</b>\n\n"
        text += "<i>Errors:</i>\n" + "\n".join(errors[:5]) + "\n"
    text += f"\n<b>Preview:</b>\n{preview}\n\nLanjutkan?"

    await message.answer(
        text,
        reply_markup=_confirm_kb("admin:bulkadd:confirm"),
    )


@router.callback_query(BulkAddStates.waiting_for_confirmation, F.data == "admin:bulkadd:confirm")
async def bulkadd_confirm(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    parsed = data.get("parsed", [])
    await state.clear()

    if not parsed:
        return await callback.message.edit_text("⚠️ Tidak ada produk untuk di-insert.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await callback.message.edit_text("❌ Database tidak tersedia.")

        inserted = 0
        async with pool.acquire() as conn:
            for name, desc, cat, price, stock in parsed:
                try:
                    await conn.execute(
                        """
                        INSERT INTO products (name, description, category, price, stock, is_active)
                        VALUES ($1, $2, $3, $4, $5, TRUE)
                        """,
                        name, desc, cat, price, stock,
                    )
                    inserted += 1
                except Exception as e:
                    logger.error("[bulkadd] Failed insert %s: %s", name, e)

        await callback.message.edit_text(
            f"✅ <b>BULK ADD SELESAI</b>\n\n"
            f"• Sukses : <b>{inserted}</b> produk\n"
            f"• Gagal  : {len(parsed) - inserted}\n\n"
            f"💡 Cek dengan /listproduct"
        )
        logger.info("[admin] Bulk add: %s/%s products", inserted, len(parsed))
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {str(e)}")
    await callback.answer()


# ----- Generic cancel handler for admin FSM flows -----
@router.callback_query(F.data == "admin:cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel any admin FSM flow."""
    if not _is_admin(callback.from_user.id):
        return
    current = await state.get_state()
    await state.clear()
    if current:
        await callback.message.edit_text("❌ Dibatalkan.")
    await callback.answer()


# ======================================================================
# USER MANAGEMENT COMMANDS
# ======================================================================

@router.message(Command("banuser"))
async def cmd_banuser(message: Message):
    """Ban user. Usage: /banuser USER_ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("📋 <b>Format:</b> <code>/banuser USER_ID</code>")

    try:
        target_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ USER_ID harus angka.")

    # Don't allow banning admins
    if target_id in settings.ADMIN_IDS:
        return await message.answer("⚠️ Tidak bisa ban admin.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE users SET is_banned = TRUE WHERE telegram_id = $1 RETURNING telegram_id, username",
                target_id,
            )

        if not row:
            return await message.answer(f"⚠️ User {target_id} tidak ditemukan di database.")

        username = row['username'] or 'N/A'
        await message.answer(f"🚫 User <code>{target_id}</code> (@{username}) telah di-<b>BAN</b>.")
        logger.info("[admin] User banned: %s", target_id)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.message(Command("unbanuser"))
async def cmd_unbanuser(message: Message):
    """Unban user. Usage: /unbanuser USER_ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer("📋 <b>Format:</b> <code>/unbanuser USER_ID</code>")

    try:
        target_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ USER_ID harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE users SET is_banned = FALSE WHERE telegram_id = $1 RETURNING telegram_id, username",
                target_id,
            )

        if not row:
            return await message.answer(f"⚠️ User {target_id} tidak ditemukan di database.")

        username = row['username'] or 'N/A'
        await message.answer(f"✅ User <code>{target_id}</code> (@{username}) telah di-<b>UNBAN</b>.")
        logger.info("[admin] User unbanned: %s", target_id)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ======================================================================
# BROADCAST COMMAND
# ======================================================================

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """Broadcast pesan ke semua user.

    Usage:
      /broadcast PESAN (text only)
      Kirim foto dengan caption /broadcast PESAN (foto + text)
    """
    if not _is_admin(message.from_user.id):
        return

    text = message.text.replace("/broadcast", "", 1).strip() if message.text else ""
    caption = message.caption.replace("/broadcast", "", 1).strip() if message.caption else ""
    photo = None

    # Check if message has photo
    if message.photo:
        photo = message.photo[-1].file_id
        text = caption or text
    elif message.reply_to_message and message.reply_to_message.photo:
        photo = message.reply_to_message.photo[-1].file_id
        if not text and message.reply_to_message.caption:
            text = message.reply_to_message.caption

    if not text and not photo:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/broadcast PESAN\n\n"
            "<b>Dengan gambar:</b>\n"
            "Kirim foto + caption /broadcast PESAN\n\n"
            "<b>Contoh:</b>\n"
            "/broadcast 🎉 Promo hari ini! Diskon 50%"
        )

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT telegram_id FROM users WHERE is_banned = FALSE AND telegram_id != $1",
                message.from_user.id,  # Exclude admin from broadcast
            )

        if not rows:
            return await message.answer("⚠️ Tidak ada user di database.")

        # Confirmation step
        mode = "📷 Foto + Text" if photo else "📝 Text only"
        preview = text[:100] + "..." if len(text) > 100 else text
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Kirim Broadcast", callback_data="broadcast:confirm")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await message.answer(
            f"📢 <b>PREVIEW BROADCAST</b>\n\n"
            f"• Mode: {mode}\n"
            f"• Target: {len(rows)} user\n"
            f"• Pesan: {preview}\n\n"
            f"Yakin kirim?",
            reply_markup=kb.as_markup(),
        )

        # Store broadcast data for confirmation handler
        # Using a simple module-level dict (keyed by admin_id)
        _pending_broadcasts[message.from_user.id] = {
            "text": text,
            "photo": photo,
            "rows": rows,
        }

    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# Pending broadcast storage (admin_id → data)
_pending_broadcasts: dict = {}


@router.callback_query(F.data == "broadcast:confirm")
async def handle_broadcast_confirm(callback: CallbackQuery):
    """Execute broadcast after admin confirmation."""
    if not _is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    data = _pending_broadcasts.pop(callback.from_user.id, None)
    if not data:
        await callback.message.edit_text("⚠️ Broadcast expired. Kirim ulang /broadcast.")
        return await callback.answer()

    text = data["text"]
    photo = data["photo"]
    rows = data["rows"]
    broadcast_text = f"📢 <b>BROADCAST</b>\n\n{text}" if text else ""

    await callback.message.edit_text(f"📢 Mengirim broadcast ke {len(rows)} user...")
    await callback.answer()

    import asyncio
    sent = 0
    failed = 0

    for row in rows:
        try:
            if photo:
                await callback.bot.send_photo(
                    chat_id=row['telegram_id'],
                    photo=photo,
                    caption=broadcast_text,
                    parse_mode="HTML",
                )
            else:
                await callback.bot.send_message(
                    chat_id=row['telegram_id'],
                    text=broadcast_text,
                    parse_mode="HTML",
                )
            sent += 1
        except Exception:
            failed += 1

        # Rate limit: 25 msg/sec (safe margin under Telegram's 30/sec limit)
        if sent % 25 == 0:
            await asyncio.sleep(1.1)

    # Send preview of broadcast to admin (same as what users received)
    if photo:
        await callback.bot.send_photo(
            chat_id=callback.from_user.id,
            photo=photo,
            caption=broadcast_text,
            parse_mode="HTML",
        )
    else:
        await callback.bot.send_message(
            chat_id=callback.from_user.id,
            text=broadcast_text,
            parse_mode="HTML",
        )

    await callback.message.edit_text(
        f"📢 <b>BROADCAST SELESAI</b>\n\n"
        f"• Terkirim : {sent}\n"
        f"• Gagal    : {failed}\n"
        f"• Total    : {len(rows)}"
    )
    logger.info("[admin] Broadcast sent: %s/%s (photo=%s)", sent, len(rows), bool(photo))


@router.message(Command("broadcastpoll"))
async def cmd_broadcastpoll(message: Message):
    """Broadcast poll/voting ke semua user.

    Usage: /broadcastpoll PERTANYAAN|OPSI1|OPSI2|OPSI3
    Contoh: /broadcastpoll Kalo aku open PO Capcut 1B mau ga?|Mau banget|Mungkin|Ga dulu
    """
    if not _is_admin(message.from_user.id):
        return

    raw = message.text.replace("/broadcastpoll", "", 1).strip()
    if not raw or "|" not in raw:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/broadcastpoll PERTANYAAN|OPSI1|OPSI2|OPSI3\n\n"
            "<b>Contoh:</b>\n"
            "/broadcastpoll Kalo aku open PO Capcut 1B mau ga?|Mau banget|Mungkin|Ga dulu\n\n"
            "💡 Minimal 2 opsi, maksimal 10 opsi. Pisahkan dengan |"
        )

    parts = [p.strip() for p in raw.split("|")]
    question = parts[0]
    options = parts[1:]

    if len(options) < 2:
        return await message.answer("⚠️ Minimal 2 opsi jawaban.")
    if len(options) > 10:
        return await message.answer("⚠️ Maksimal 10 opsi jawaban.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT telegram_id FROM users WHERE is_banned = FALSE AND telegram_id != $1",
                message.from_user.id,
            )

        if not rows:
            return await message.answer("⚠️ Tidak ada user di database.")

        # Confirmation
        options_preview = "\n".join(f"  • {o}" for o in options)
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Kirim Poll", callback_data="broadcastpoll:confirm")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await message.answer(
            f"📊 <b>PREVIEW POLL</b>\n\n"
            f"Pertanyaan: {question}\n"
            f"Opsi:\n{options_preview}\n\n"
            f"Target: {len(rows)} user\n"
            f"Yakin kirim?",
            reply_markup=kb.as_markup(),
        )

        _pending_polls[message.from_user.id] = {
            "question": question,
            "options": options,
            "rows": rows,
        }

    except Exception as e:
        await message.answer(f"❌ Error: {e}")


_pending_polls: dict = {}

# Poll tracking: aggregate votes from all users
_active_polls: dict = {}       # poll_track_id → {question, options, votes, voters, ...}
_poll_id_map: dict = {}        # telegram_poll_id → poll_track_id


@router.callback_query(F.data == "broadcastpoll:confirm")
async def handle_broadcastpoll_confirm(callback: CallbackQuery):
    """Execute broadcast poll after confirmation."""
    if not _is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    data = _pending_polls.pop(callback.from_user.id, None)
    if not data:
        await callback.message.edit_text("⚠️ Poll expired. Kirim ulang /broadcastpoll.")
        return await callback.answer()

    question = data["question"]
    options = data["options"]
    rows = data["rows"]

    await callback.message.edit_text(f"📊 Mengirim poll ke {len(rows)} user...")
    await callback.answer()

    import asyncio
    sent = 0
    failed = 0

    # Generate unique poll_id tracker
    import time
    poll_track_id = f"poll_{int(time.time())}"

    # Store poll metadata for aggregation
    _active_polls[poll_track_id] = {
        "question": question,
        "options": options,
        "votes": {i: 0 for i in range(len(options))},
        "voters": {},  # user_id → option_index
        "total_sent": 0,
        "admin_id": callback.from_user.id,
        "telegram_poll_ids": [],  # track all poll IDs for matching
    }

    for row in rows:
        try:
            poll_msg = await callback.bot.send_poll(
                chat_id=row['telegram_id'],
                question=question,
                options=options,
                is_anonymous=False,  # Non-anonymous so we get poll_answer updates
            )
            # Map telegram poll_id to our tracker
            if poll_msg.poll:
                _poll_id_map[poll_msg.poll.id] = poll_track_id
                _active_polls[poll_track_id]["telegram_poll_ids"].append(poll_msg.poll.id)
            sent += 1
        except Exception:
            failed += 1

        if sent % 25 == 0:
            await asyncio.sleep(1.1)

    _active_polls[poll_track_id]["total_sent"] = sent

    await callback.message.edit_text(
        f"📊 <b>POLL BROADCAST SELESAI</b>\n\n"
        f"• Pertanyaan: {question}\n"
        f"• Terkirim : {sent}\n"
        f"• Gagal    : {failed}\n"
        f"• Total    : {len(rows)}\n\n"
        f"💡 Lihat hasil: /pollresult {poll_track_id}"
    )
    logger.info("[admin] Poll broadcast sent: %s/%s question=%s track=%s", sent, len(rows), question, poll_track_id)


@router.poll_answer()
async def handle_poll_answer(poll_answer):
    """Track poll votes from users for aggregation."""
    telegram_poll_id = poll_answer.poll_id
    user_id = poll_answer.user.id

    # Find our tracker for this poll
    poll_track_id = _poll_id_map.get(telegram_poll_id)
    if not poll_track_id or poll_track_id not in _active_polls:
        return  # Not our tracked poll

    poll_data = _active_polls[poll_track_id]

    # Remove previous vote if user changed answer
    if user_id in poll_data["voters"]:
        old_option = poll_data["voters"][user_id]
        poll_data["votes"][old_option] = max(0, poll_data["votes"][old_option] - 1)

    # Record new vote (poll_answer.option_ids is a list of selected options)
    if poll_answer.option_ids:
        option_idx = poll_answer.option_ids[0]  # Single-choice poll
        poll_data["votes"][option_idx] = poll_data["votes"].get(option_idx, 0) + 1
        poll_data["voters"][user_id] = option_idx
    else:
        # User retracted vote
        poll_data["voters"].pop(user_id, None)


@router.message(Command("pollresult"))
async def cmd_pollresult(message: Message):
    """Lihat hasil poll. Usage: /pollresult [POLL_ID]

    Tanpa ID: tampilkan poll terakhir.
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()

    if len(args) >= 2:
        poll_track_id = args[1]
    else:
        # Get latest poll
        if not _active_polls:
            return await message.answer("⚠️ Belum ada poll aktif.")
        poll_track_id = list(_active_polls.keys())[-1]

    poll_data = _active_polls.get(poll_track_id)
    if not poll_data:
        return await message.answer(f"⚠️ Poll {poll_track_id} tidak ditemukan.")

    question = poll_data["question"]
    options = poll_data["options"]
    votes = poll_data["votes"]
    total_votes = sum(votes.values())
    total_sent = poll_data["total_sent"]

    text = f"📊 <b>HASIL POLL</b>\n\n"
    text += f"❓ {question}\n\n"

    for i, option in enumerate(options):
        count = votes.get(i, 0)
        pct = round(count / total_votes * 100) if total_votes > 0 else 0
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        text += f"{option}\n{bar} {count} vote ({pct}%)\n\n"

    text += (
        f"Total vote: {total_votes} / {total_sent} user\n"
        f"Response rate: {round(total_votes / total_sent * 100) if total_sent > 0 else 0}%\n\n"
        f"ID: {poll_track_id}"
    )

    await message.answer(text)


# ======================================================================
# ANALYTICS & REPORTING COMMANDS
# ======================================================================

@router.message(Command("report"))
async def cmd_report(message: Message):
    """Laporan penjualan. Usage: /report [daily|weekly|monthly]"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    period = args[1].lower() if len(args) > 1 else "daily"

    if period not in ("daily", "weekly", "monthly"):
        return await message.answer(
            "📋 <b>Format:</b> <code>/report [daily|weekly|monthly]</code>\n\n"
            "Default: daily"
        )

    interval_map = {"daily": "1 day", "weekly": "7 days", "monthly": "30 days"}
    period_label = {"daily": "Hari Ini", "weekly": "7 Hari Terakhir", "monthly": "30 Hari Terakhir"}

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        interval = interval_map[period]

        async with pool.acquire() as conn:
            total_orders = await conn.fetchval(
                f"SELECT COUNT(*) FROM orders WHERE created_at >= NOW() - INTERVAL '{interval}'"
            )
            paid_orders = await conn.fetchval(
                f"SELECT COUNT(*) FROM orders WHERE status = 'paid' AND created_at >= NOW() - INTERVAL '{interval}'"
            )
            revenue = await conn.fetchval(
                f"SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status = 'paid' AND created_at >= NOW() - INTERVAL '{interval}'"
            )
            cancelled = await conn.fetchval(
                f"SELECT COUNT(*) FROM orders WHERE status = 'cancelled' AND created_at >= NOW() - INTERVAL '{interval}'"
            )
            pending = await conn.fetchval(
                f"SELECT COUNT(*) FROM orders WHERE status = 'pending' AND created_at >= NOW() - INTERVAL '{interval}'"
            )
            buyers = await conn.fetchval(
                f"SELECT COUNT(DISTINCT user_id) FROM orders WHERE created_at >= NOW() - INTERVAL '{interval}'"
            )

        # Tombol detail + excel
        kb = InlineKeyboardBuilder()
        kb.button(text="📋 Detail Transaksi", callback_data=f"report:detail:{period}")
        kb.button(text="📥 Download Excel", callback_data=f"report:excel:{period}")
        kb.adjust(2)

        await message.answer(
            f"📊 <b>LAPORAN PENJUALAN - {period_label[period]}</b>\n\n"
            f"Total Order : {total_orders}\n"
            f"Paid : {paid_orders}\n"
            f"Pending : {pending}\n"
            f"Cancelled : {cancelled}\n"
            f"Revenue : Rp {revenue:,}\n"
            f"Buyers : {buyers}\n\n"
            f"💡 /report daily | weekly | monthly",
            reply_markup=kb.as_markup(),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(F.data.startswith("report:detail:"))
async def report_detail(callback: CallbackQuery):
    """Show detailed transaction table."""
    if not _is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    period = callback.data.split(":")[2]
    interval_map = {"daily": "1 day", "weekly": "7 days", "monthly": "30 days"}
    interval = interval_map.get(period, "1 day")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT o.id, o.quantity, o.total_price, o.created_at, o.status,
                       p.name as product_name, p.price as unit_price,
                       u.username, u.telegram_id
                FROM orders o
                JOIN products p ON o.product_id = p.id
                JOIN users u ON o.user_id = u.telegram_id
                WHERE o.created_at >= NOW() - INTERVAL '{interval}'
                  AND o.status = 'paid'
                ORDER BY o.created_at DESC
                LIMIT 20
                """,
            )

        if not rows:
            await callback.answer("Belum ada transaksi paid.", show_alert=True)
            return

        text = f"📋 <b>DETAIL TRANSAKSI ({period})</b>\n\n"

        for i, r in enumerate(rows, 1):
            code = r['id'][:8]
            prod = r['product_name']
            qty = r['quantity']
            user = r['username'] or str(r['telegram_id'])
            unit = r['unit_price']
            total = r['total_price']
            date = r['created_at'].strftime("%d/%m/%Y %H:%M")

            text += (
                f"<b>{i}. {prod}</b>\n"
                f"   Kode : {code}\n"
                f"   Qty : {qty}\n"
                f"   User : {user}\n"
                f"   Harga : Rp {unit:,}\n"
                f"   Total : Rp {total:,}\n"
                f"   Tanggal : {date}\n\n"
            )

        if len(text) > 4000:
            text = text[:3950] + "\n\n... (truncated)"

        await callback.message.answer(text)
    except Exception as e:
        await callback.message.answer(f"❌ Error: {str(e)}")
    await callback.answer()


@router.callback_query(F.data.startswith("report:excel:"))
async def report_excel(callback: CallbackQuery):
    """Generate and send Excel report."""
    if not _is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)

    period = callback.data.split(":")[2]
    interval_map = {"daily": "1 day", "weekly": "7 days", "monthly": "30 days"}
    interval = interval_map.get(period, "1 day")

    await callback.answer("⏳ Generating Excel...")

    try:
        from app.infrastructure.database.connection import get_pool
        import openpyxl
        from openpyxl.styles import Font, Alignment, Border, Side
        from io import BytesIO
        from datetime import datetime as dt
        from aiogram.types import BufferedInputFile

        pool = get_pool()
        if not pool:
            return await callback.message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT o.id, o.quantity, o.total_price, o.created_at, o.status,
                       o.payment_method,
                       p.name as product_name, p.price as unit_price,
                       u.username, u.telegram_id, u.first_name
                FROM orders o
                JOIN products p ON o.product_id = p.id
                JOIN users u ON o.user_id = u.telegram_id
                WHERE o.created_at >= NOW() - INTERVAL '{interval}'
                ORDER BY o.created_at DESC
                """,
            )

        # Create Excel workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Report {period}"

        # Header styling
        header_font = Font(bold=True, size=11)
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'),
        )

        # Headers
        headers = ["No", "Kode Transaksi", "Produk", "Qty", "Customer", "Harga Satuan", "Total", "Status", "Tanggal"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')

        # Data rows
        for i, r in enumerate(rows, 1):
            row_num = i + 1
            customer = r['username'] or r['first_name'] or str(r['telegram_id'])
            date_str = r['created_at'].strftime("%Y-%m-%d %H:%M")

            data = [
                i,
                r['id'][:12],
                r['product_name'],
                r['quantity'],
                customer,
                r['unit_price'],
                r['total_price'],
                r['status'],
                date_str,
            ]
            for col, val in enumerate(data, 1):
                cell = ws.cell(row=row_num, column=col, value=val)
                cell.border = thin_border

        # Auto-width columns
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

        # Save to buffer
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)

        filename = f"report_{period}_{dt.now().strftime('%Y%m%d_%H%M')}.xlsx"
        doc = BufferedInputFile(buf.getvalue(), filename=filename)

        await callback.message.answer_document(
            document=doc,
            caption=f"📊 Laporan {period} - {len(rows)} transaksi\n📅 Generated: {dt.now().strftime('%d/%m/%Y %H:%M')}",
        )
    except Exception as e:
        await callback.message.answer(f"❌ Error generate Excel: {str(e)}")


@router.message(Command("topproducts"))
async def cmd_topproducts(message: Message):
    """Top produk terlaris."""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.name, COUNT(o.id) as total_orders, SUM(o.quantity) as total_qty,
                       SUM(o.total_price) as total_revenue
                FROM orders o
                JOIN products p ON o.product_id = p.id
                WHERE o.status = 'paid'
                GROUP BY p.id, p.name
                ORDER BY total_orders DESC
                LIMIT $1
                """,
                limit,
            )

        if not rows:
            return await message.answer("📊 Belum ada data penjualan.")

        text = f"🏆 <b>TOP {limit} PRODUK TERLARIS</b>\n\n"
        for i, row in enumerate(rows, 1):
            text += (
                f"{i}. <b>{row['name']}</b>\n"
                f"   Orders: {row['total_orders']} | Qty: {row['total_qty']} | Revenue: Rp {row['total_revenue']:,}\n\n"
            )

        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.message(Command("topusers"))
async def cmd_topusers(message: Message):
    """Top user dengan transaksi terbanyak."""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    limit = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT u.telegram_id, u.username, u.first_name,
                       COUNT(o.id) as total_orders, SUM(o.total_price) as total_spent
                FROM orders o
                JOIN users u ON o.user_id = u.telegram_id
                WHERE o.status = 'paid'
                GROUP BY u.telegram_id, u.username, u.first_name
                ORDER BY total_spent DESC
                LIMIT $1
                """,
                limit,
            )

        if not rows:
            return await message.answer("📊 Belum ada data transaksi.")

        text = f"👑 <b>TOP {limit} USER</b>\n\n"
        for i, row in enumerate(rows, 1):
            name = row['username'] or row['first_name'] or str(row['telegram_id'])
            text += (
                f"{i}. <b>@{name}</b>\n"
                f"   Orders: {row['total_orders']} | Spent: Rp {row['total_spent']:,}\n\n"
            )

        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")



# ======================================================================
# VARIANT EDIT & DELETE COMMANDS
# ======================================================================

VARIANT_EDIT_FIELDS = ["name", "code", "description", "delivery_description", "price", "stock", "account_template"]


@router.message(Command("editvariant"))
async def cmd_editvariant(message: Message, state: FSMContext):
    """Interactive edit variant. Usage: /editvariant ID_PRODUK_INDUK"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "✏️ <b>EDIT VARIANT</b>\n\n"
            "Format: /editvariant [ID produk induk]\n\n"
            "Contoh: /editvariant 1\n"
            "Bot akan tampilkan list variant, pilih, lalu edit field."
        )

    try:
        product_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            product = await conn.fetchrow("SELECT id, name FROM products WHERE id = $1", product_id)
            if not product:
                return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

            variants = await conn.fetch(
                """
                SELECT v.id, v.name, v.price,
                       COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
                FROM product_variants v
                WHERE v.product_id = $1
                ORDER BY v.id
                """,
                product_id,
            )

        if not variants:
            return await message.answer(f"⚠️ Produk {product['name']} belum punya variant.")

        await state.clear()
        await state.update_data(editvariant_product_id=product_id)
        await state.set_state(EditVariantStates.waiting_for_variant_select)

        kb = InlineKeyboardBuilder()
        for v in variants:
            kb.button(
                text=f"{v['name']} (Rp {v['price']:,} | stok {v['stock']})",
                callback_data=f"editvariant:select:{v['id']}",
            )
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await message.answer(
            f"✏️ <b>EDIT VARIANT - {product['name']}</b>\n\n"
            f"Pilih variant yang mau di-edit:",
            reply_markup=kb.as_markup(),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(EditVariantStates.waiting_for_variant_select, F.data.startswith("editvariant:select:"))
async def editvariant_selected(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    variant_id = int(callback.data.split(":")[2])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchrow(
            """SELECT v.id, v.name, v.code, v.description, v.price,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock,
                   v.account_template
            FROM product_variants v WHERE v.id = $1""",
            variant_id,
        )

    if not v:
        return await callback.answer("⚠️ Variant tidak ditemukan.", show_alert=True)

    await state.update_data(editvariant_id=variant_id)
    await state.set_state(EditVariantStates.waiting_for_field)

    # Get product_id from state for back navigation
    state_data = await state.get_data()
    parent_product_id = state_data.get("editvariant_product_id")

    # Show variant detail + field selection
    kb = InlineKeyboardBuilder()
    for f in VARIANT_EDIT_FIELDS:
        kb.button(text=f.title(), callback_data=f"editvariant:field:{f}")
    if parent_product_id:
        kb.button(text="🔙 Kembali", callback_data=f"editvariant:back_to_select:{parent_product_id}")
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    kb.adjust(2, 2, 2, 2)

    template = v['account_template'] or "(belum di-set)"

    await callback.message.edit_text(
        f"📋 <b>VARIANT DETAIL</b>\n\n"
        f"ID         : {v['id']}\n"
        f"Nama       : {v['name']}\n"
        f"Kode       : {v['code']}\n"
        f"Deskripsi  : {(v['description'] or '')[:80]}\n"
        f"Harga      : Rp {v['price']:,}\n"
        f"Stok       : {v['stock']}\n"
        f"Template   : {template}\n\n"
        f"Pilih field yang mau di-edit:",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(EditVariantStates.waiting_for_field, F.data.startswith("editvariant:field:"))
async def editvariant_field(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    field = callback.data.split(":")[2]
    await state.update_data(editvariant_field=field)
    await state.set_state(EditVariantStates.waiting_for_value)

    hints = {
        "name": "Contoh: CANVA PRO TEAM 1 BULAN",
        "code": "Contoh: ct1m",
        "description": "Deskripsi singkat variant ini",
        "price": "Contoh: 25000",
        "stock": "Contoh: 100 (jumlah stok manual)",
        "account_template": "Contoh: Email|Password|Profile|PIN",
    }

    await callback.message.edit_text(
        f"✏️ Edit field: <b>{field}</b>\n\n"
        f"Masukkan nilai baru:\n\n"
        f"<i>{hints.get(field, '')}</i>",
        reply_markup=_cancel_kb(),
    )
    await callback.answer()


@router.message(EditVariantStates.waiting_for_value)
async def editvariant_value(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return

    data = await state.get_data()
    field = data["editvariant_field"]
    variant_id = data["editvariant_id"]
    value = message.text.strip()

    # Validate numeric fields
    if field in ("price", "stock"):
        try:
            value = int(value.replace(".", "").replace(",", ""))
            if value < 0:
                raise ValueError
        except ValueError:
            return await message.answer(f"⚠️ {field} harus angka >= 0. Coba lagi:")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            query = f"UPDATE product_variants SET {field} = $2 WHERE id = $1 RETURNING id, name, price, stock, product_id"
            row = await conn.fetchrow(query, variant_id, value)

            # If stock was edited, sync parent stock
            if field == "stock" and row:
                parent_total = await conn.fetchval(
                    "SELECT COALESCE(SUM(stock), 0) FROM product_variants WHERE product_id = $1 AND is_active = TRUE",
                    row['product_id'],
                )
                await conn.execute("UPDATE products SET stock = $2 WHERE id = $1", row['product_id'], parent_total)

        if not row:
            await state.clear()
            return await message.answer(f"⚠️ Variant tidak ditemukan.")

        # Keep state for back button (so user can edit other fields)
        await state.set_state(EditVariantStates.waiting_for_field)

        # Back button → kembali ke field selection
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Kembali ke Variant", callback_data=f"editvariant:back:{variant_id}")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await message.answer(
            f"✅ <b>VARIANT DI-UPDATE</b>\n\n"
            f"ID : {row['id']}\n"
            f"Nama : {row['name']}\n"
            f"Harga : Rp {row['price']:,}\n"
            f"Stok : {row['stock']}\n"
            f"Field : {field} → {value}",
            reply_markup=kb.as_markup(),
        )
        logger.info("[admin] Variant edited: id=%s field=%s", variant_id, field)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(F.data.startswith("editvariant:back:"))
async def editvariant_back(callback: CallbackQuery, state: FSMContext):
    """Kembali ke menu field selection untuk variant yang sama."""
    if not _is_admin(callback.from_user.id):
        return

    variant_id = int(callback.data.split(":")[2])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchrow(
            """SELECT v.id, v.name, v.code, v.description, v.price,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock,
                   v.account_template
            FROM product_variants v WHERE v.id = $1""",
            variant_id,
        )

    if not v:
        await state.clear()
        return await callback.answer("⚠️ Variant tidak ditemukan.", show_alert=True)

    await state.update_data(editvariant_id=variant_id)
    await state.set_state(EditVariantStates.waiting_for_field)

    # Get product_id from state for back navigation
    state_data = await state.get_data()
    parent_product_id = state_data.get("editvariant_product_id")

    kb = InlineKeyboardBuilder()
    for f in VARIANT_EDIT_FIELDS:
        kb.button(text=f.title(), callback_data=f"editvariant:field:{f}")
    if parent_product_id:
        kb.button(text="🔙 Kembali", callback_data=f"editvariant:back_to_select:{parent_product_id}")
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    kb.adjust(2, 2, 2, 2)

    template = v['account_template'] or "(belum di-set)"

    await callback.message.answer(
        f"📋 <b>VARIANT DETAIL</b>\n\n"
        f"ID         : {v['id']}\n"
        f"Nama       : {v['name']}\n"
        f"Kode       : {v['code']}\n"
        f"Deskripsi  : {(v['description'] or '')[:80]}\n"
        f"Harga      : Rp {v['price']:,}\n"
        f"Stok       : {v['stock']}\n"
        f"Template   : {template}\n\n"
        f"Pilih field yang mau di-edit:",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.message(Command("delvariant"))
async def cmd_delvariant(message: Message, state: FSMContext):
    """Interactive delete variant. Usage: /delvariant ID_PRODUK_INDUK"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "🗑️ <b>HAPUS VARIANT</b>\n\n"
            "Format: /delvariant [ID produk induk]\n\n"
            "Contoh: /delvariant 1"
        )

    try:
        product_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()

        async with pool.acquire() as conn:
            product = await conn.fetchrow("SELECT id, name FROM products WHERE id = $1", product_id)
            if not product:
                return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

            variants = await conn.fetch(
                """SELECT v.id, v.name,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
            FROM product_variants v WHERE v.product_id = $1 AND v.is_active = TRUE ORDER BY v.id""",
                product_id,
            )

        if not variants:
            return await message.answer(f"⚠️ Produk {product['name']} belum punya variant aktif.")

        await state.clear()
        await state.update_data(delvariant_product_id=product_id)
        await state.set_state(DelVariantStates.waiting_for_variant_select)

        kb = InlineKeyboardBuilder()
        for v in variants:
            kb.button(text=f"{v['name']} (stok {v['stock']})", callback_data=f"delvariant:select:{v['id']}")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await message.answer(
            f"🗑️ <b>HAPUS VARIANT - {product['name']}</b>\n\n"
            f"Pilih variant yang mau dihapus:",
            reply_markup=kb.as_markup(),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(DelVariantStates.waiting_for_variant_select, F.data.startswith("delvariant:select:"))
async def delvariant_selected(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    variant_id = int(callback.data.split(":")[2])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchrow(
            """SELECT v.id, v.name, v.price,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
            FROM product_variants v WHERE v.id = $1""", variant_id
        )

    if not v:
        return await callback.answer("⚠️ Tidak ditemukan.", show_alert=True)

    await state.update_data(delvariant_id=variant_id, delvariant_name=v['name'])
    await state.set_state(DelVariantStates.waiting_for_confirmation)

    await callback.message.edit_text(
        f"⚠️ <b>KONFIRMASI HAPUS</b>\n\n"
        f"ID : {v['id']}\n"
        f"Nama : {v['name']}\n"
        f"Harga : Rp {v['price']:,}\n"
        f"Stok : {v['stock']}\n\n"
        f"Yakin hapus variant ini?\n"
        f"<i>(soft delete: variant di-nonaktifkan, account stock tetap utuh)</i>",
        reply_markup=_confirm_kb("admin:delvariant:confirm"),
    )
    await callback.answer()


@router.callback_query(DelVariantStates.waiting_for_confirmation, F.data == "admin:delvariant:confirm")
async def delvariant_confirm(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    variant_id = data['delvariant_id']
    await state.clear()

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE product_variants SET is_active = FALSE WHERE id = $1 RETURNING id, name, product_id",
                variant_id,
            )
            # Sync parent stock
            if row:
                parent_total = await conn.fetchval(
                    "SELECT COALESCE(SUM(stock), 0) FROM product_variants WHERE product_id = $1 AND is_active = TRUE",
                    row['product_id'],
                )
                await conn.execute("UPDATE products SET stock = $2 WHERE id = $1", row['product_id'], parent_total)

        if row:
            await callback.message.edit_text(
                f"✅ Variant <b>{row['name']}</b> (ID: {row['id']}) telah di-nonaktifkan."
            )
            logger.info("[admin] Variant deactivated: id=%s", row['id'])
        else:
            await callback.message.edit_text("⚠️ Variant tidak ditemukan.")
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {str(e)}")
    await callback.answer()


@router.message(Command("listvariant"))
async def cmd_listvariant(message: Message):
    """List all variants of a product. Usage: /listvariant ID_PRODUK_INDUK"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>LIST VARIANT</b>\n\n"
            "Format: /listvariant [ID produk induk]\n"
            "Contoh: /listvariant 1"
        )

    try:
        product_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID harus angka.")

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            product = await conn.fetchrow("SELECT id, name FROM products WHERE id = $1", product_id)
            if not product:
                return await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")

            variants = await conn.fetch(
                """
                SELECT v.id, v.name, v.code, v.price, v.is_active,
                       COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
                FROM product_variants v
                WHERE v.product_id = $1
                ORDER BY v.id
                """,
                product_id,
            )

        if not variants:
            return await message.answer(f"📋 {product['name']} belum punya variant.")

        text = f"📋 <b>VARIANT - {product['name']}</b>\n\n"
        for v in variants:
            status = "✅" if v['is_active'] else "❌"
            text += (
                f"{status} <b>[ID:{v['id']}]</b> {v['name']}\n"
                f"     Kode: {v['code']} | Rp {v['price']:,} | stok {v['stock']}\n\n"
            )

        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")



@router.callback_query(F.data.startswith("editvariant:back_to_select:"))
async def editvariant_back_to_select(callback: CallbackQuery, state: FSMContext):
    """Kembali ke menu pilih variant (step sebelumnya)."""
    if not _is_admin(callback.from_user.id):
        return

    product_id = int(callback.data.split(":")[2])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    async with pool.acquire() as conn:
        product = await conn.fetchrow("SELECT id, name FROM products WHERE id = $1", product_id)
        variants = await conn.fetch(
            """
            SELECT v.id, v.name, v.price,
                   COALESCE((SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE), 0) AS stock
            FROM product_variants v
            WHERE v.product_id = $1
            ORDER BY v.id
            """,
            product_id,
        )

    if not product:
        return await callback.answer("⚠️ Produk tidak ditemukan.", show_alert=True)

    await state.clear()
    await state.update_data(editvariant_product_id=product_id)
    await state.set_state(EditVariantStates.waiting_for_variant_select)

    kb = InlineKeyboardBuilder()
    for v in variants:
        kb.button(
            text=f"{v['name']} (Rp {v['price']:,} | stok {v['stock']})",
            callback_data=f"editvariant:select:{v['id']}",
        )
    kb.button(text="❌ Batal", callback_data="admin:cancel")
    kb.adjust(1)

    await callback.message.answer(
        f"✏️ <b>EDIT VARIANT - {product['name']}</b>\n\n"
        f"Pilih variant yang mau di-edit:",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()



# ======================================================================
# BULK DELETE COMMANDS
# ======================================================================

@router.message(Command("bulkdel"))
async def cmd_bulkdel(message: Message):
    """Bulk delete products or variants.

    Usage:
      /bulkdel product 1,5,7    → hapus produk ID 1, 5, 7
      /bulkdel variant 3,4,5    → hapus variant ID 3, 4, 5
      /bulkdel stock 5          → hapus semua akun unused di produk ID 5
      /bulkdel stockvar 3       → hapus semua akun unused di variant ID 3
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer(
            "🗑️ <b>BULK DELETE</b>\n\n"
            "<b>Format:</b>\n"
            "/bulkdel product 1,5,7\n"
            "/bulkdel variant 3,4,5\n"
            "/bulkdel stock 5\n"
            "/bulkdel stockvar 3\n\n"
            "<b>Contoh:</b>\n"
            "/bulkdel product 13,15,16,17,18,19\n"
            "→ Hapus 6 produk sekaligus\n\n"
            "/bulkdel variant 1,2,3\n"
            "→ Hapus 3 variant sekaligus\n\n"
            "/bulkdel stock 5\n"
            "→ Hapus semua akun unused di produk ID 5\n\n"
            "/bulkdel stockvar 3\n"
            "→ Hapus semua akun unused di variant ID 3"
        )

    mode = args[1].lower()
    ids_str = args[2].strip()

    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if not pool:
            return await message.answer("❌ Database tidak tersedia.")

        if mode == "product":
            ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE products SET is_active = FALSE WHERE id = ANY($1::bigint[])",
                    ids,
                )
            await message.answer(
                f"✅ <b>BULK DELETE PRODUK</b>\n\n"
                f"Dihapus : {len(ids)} produk\n"
                f"IDs : {ids_str}\n"
                f"Result : {result}"
            )

        elif mode == "variant":
            ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "UPDATE product_variants SET is_active = FALSE WHERE id = ANY($1::bigint[])",
                    ids,
                )
                # Sync parent stocks
                await conn.execute("""
                    UPDATE products p SET stock = COALESCE((
                        SELECT SUM(
                            (SELECT COUNT(*) FROM account_stock a WHERE a.variant_id = v.id AND a.is_used = FALSE)
                        ) FROM product_variants v WHERE v.product_id = p.id AND v.is_active = TRUE
                    ), 0)
                """)
            await message.answer(
                f"✅ <b>BULK DELETE VARIANT</b>\n\n"
                f"Dihapus : {len(ids)} variant\n"
                f"IDs : {ids_str}\n"
                f"Result : {result}"
            )

        elif mode == "stock":
            product_id = int(ids_str)
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM account_stock WHERE product_id = $1 AND is_used = FALSE",
                    product_id,
                )
                # Sync stock
                await conn.execute("""
                    UPDATE product_variants v SET stock = (
                        SELECT COUNT(*) FROM account_stock WHERE variant_id = v.id AND is_used = FALSE
                    ) WHERE v.product_id = $1
                """, product_id)
                await conn.execute("""
                    UPDATE products SET stock = COALESCE((
                        SELECT SUM(stock) FROM product_variants WHERE product_id = $1 AND is_active = TRUE
                    ), 0) WHERE id = $1
                """, product_id)
            await message.answer(
                f"✅ <b>STOCK CLEARED</b>\n\n"
                f"Produk ID : {product_id}\n"
                f"Result : {result}\n"
                f"Semua akun unused dihapus."
            )

        elif mode == "stockvar":
            variant_id = int(ids_str)
            async with pool.acquire() as conn:
                result = await conn.execute(
                    "DELETE FROM account_stock WHERE variant_id = $1 AND is_used = FALSE",
                    variant_id,
                )
                # Sync variant stock
                await conn.execute(
                    "UPDATE product_variants SET stock = 0 WHERE id = $1", variant_id
                )
                # Sync parent
                v = await conn.fetchrow("SELECT product_id FROM product_variants WHERE id = $1", variant_id)
                if v:
                    await conn.execute("""
                        UPDATE products SET stock = COALESCE((
                            SELECT SUM(stock) FROM product_variants WHERE product_id = $1 AND is_active = TRUE
                        ), 0) WHERE id = $1
                    """, v['product_id'])
            await message.answer(
                f"✅ <b>VARIANT STOCK CLEARED</b>\n\n"
                f"Variant ID : {variant_id}\n"
                f"Result : {result}\n"
                f"Semua akun unused dihapus."
            )

        else:
            await message.answer("⚠️ Mode tidak valid. Pilih: product, variant, stock, stockvar")

        logger.info("[admin] Bulk delete: mode=%s ids=%s", mode, ids_str)
    except ValueError:
        await message.answer("⚠️ Format ID salah. Gunakan angka dipisah koma.")
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")


# ======================================================================
# HIDE / SHOW PRODUCT & VARIANT
# ======================================================================

@router.message(Command("hideproduct"))
async def cmd_hideproduct(message: Message):
    """Hide product dari katalog. Usage: /hideproduct ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/hideproduct ID\n\n"
            "Produk akan disembunyikan dari katalog user.\n"
            "💡 Gunakan /showproduct ID untuk menampilkan kembali."
        )

    try:
        product_id = int(args[1])
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE products SET is_active = FALSE WHERE id = $1 RETURNING id, name",
                product_id,
            )
        if row:
            await message.answer(f"✅ Produk <b>{row['name']}</b> (ID {row['id']}) disembunyikan dari katalog.")
            logger.info("[admin] Product hidden: id=%s", product_id)
        else:
            await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")
    except ValueError:
        await message.answer("⚠️ ID harus angka.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


@router.message(Command("showproduct"))
async def cmd_showproduct(message: Message):
    """Show product kembali di katalog. Usage: /showproduct ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/showproduct ID\n\n"
            "Produk akan ditampilkan kembali di katalog user."
        )

    try:
        product_id = int(args[1])
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE products SET is_active = TRUE WHERE id = $1 RETURNING id, name",
                product_id,
            )
        if row:
            await message.answer(f"✅ Produk <b>{row['name']}</b> (ID {row['id']}) ditampilkan kembali di katalog.")
            logger.info("[admin] Product shown: id=%s", product_id)
        else:
            await message.answer(f"⚠️ Produk ID {product_id} tidak ditemukan.")
    except ValueError:
        await message.answer("⚠️ ID harus angka.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


@router.message(Command("hidevariant"))
async def cmd_hidevariant(message: Message):
    """Hide variant dari katalog. Usage: /hidevariant VARIANT_ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/hidevariant VARIANT_ID\n\n"
            "Variant akan disembunyikan dari pilihan user."
        )

    try:
        variant_id = int(args[1])
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE product_variants SET is_active = FALSE WHERE id = $1 RETURNING id, name",
                variant_id,
            )
        if row:
            await message.answer(f"✅ Variant <b>{row['name']}</b> (ID {row['id']}) disembunyikan.")
            logger.info("[admin] Variant hidden: id=%s", variant_id)
        else:
            await message.answer(f"⚠️ Variant ID {variant_id} tidak ditemukan.")
    except ValueError:
        await message.answer("⚠️ ID harus angka.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


@router.message(Command("showvariant"))
async def cmd_showvariant(message: Message):
    """Show variant kembali. Usage: /showvariant VARIANT_ID"""
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/showvariant VARIANT_ID\n\n"
            "Variant akan ditampilkan kembali."
        )

    try:
        variant_id = int(args[1])
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE product_variants SET is_active = TRUE WHERE id = $1 RETURNING id, name",
                variant_id,
            )
        if row:
            await message.answer(f"✅ Variant <b>{row['name']}</b> (ID {row['id']}) ditampilkan kembali.")
            logger.info("[admin] Variant shown: id=%s", variant_id)
        else:
            await message.answer(f"⚠️ Variant ID {variant_id} tidak ditemukan.")
    except ValueError:
        await message.answer("⚠️ ID harus angka.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


# ======================================================================
# DELETE / EDIT INDIVIDUAL STOCK ACCOUNT
# ======================================================================

@router.message(Command("delstock"))
async def cmd_delstock(message: Message):
    """Hapus akun individual dari stock.

    Usage:
      /delstock ID              → hapus akun by account_stock ID
      /delstock search EMAIL    → cari & hapus akun by data content

    Contoh:
      /delstock 142
      /delstock search netflix@gmail.com
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/delstock ID\n"
            "/delstock search KEYWORD\n\n"
            "<b>Contoh:</b>\n"
            "/delstock 142\n"
            "/delstock search netflix@gmail.com\n\n"
            "💡 Gunakan /viewstock ID_PRODUK untuk lihat daftar akun + ID-nya"
        )

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    if not pool:
        return await message.answer("❌ Database tidak tersedia.")

    mode = args[1].lower()

    if mode == "search" and len(args) >= 3:
        # Search mode: cari akun by content
        keyword = args[2].strip()
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT s.id, s.account_data, s.is_used, s.variant_id, v.name as variant_name
                       FROM account_stock s
                       LEFT JOIN product_variants v ON v.id = s.variant_id
                       WHERE s.account_data ILIKE $1
                       LIMIT 10""",
                    f"%{keyword}%",
                )

            if not rows:
                return await message.answer(f"⚠️ Tidak ditemukan akun dengan keyword: {keyword}")

            text = f"🔍 <b>Hasil pencarian: {keyword}</b>\n\n"
            for r in rows:
                status = "✅ Available" if not r['is_used'] else "❌ Used"
                vname = r['variant_name'] or "N/A"
                data_preview = r['account_data'][:40] + "..." if len(r['account_data']) > 40 else r['account_data']
                text += f"[{r['id']}] {data_preview}\n    Variant: {vname} | {status}\n\n"

            text += "💡 Hapus dengan: /delstock ID"
            await message.answer(text)
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

    else:
        # Direct delete by ID
        try:
            stock_id = int(mode)
        except ValueError:
            return await message.answer("⚠️ ID harus angka. Atau gunakan: /delstock search KEYWORD")

        try:
            async with pool.acquire() as conn:
                # Get info dulu sebelum hapus
                row = await conn.fetchrow(
                    """SELECT s.id, s.account_data, s.is_used, s.variant_id, s.product_id,
                              v.name as variant_name, p.name as product_name
                       FROM account_stock s
                       LEFT JOIN product_variants v ON v.id = s.variant_id
                       LEFT JOIN products p ON p.id = s.product_id
                       WHERE s.id = $1""",
                    stock_id,
                )

                if not row:
                    return await message.answer(f"⚠️ Account stock ID {stock_id} tidak ditemukan.")

                # Hapus
                await conn.execute("DELETE FROM account_stock WHERE id = $1", stock_id)

                # Sync stock count variant + parent
                if row['variant_id']:
                    await conn.execute("""
                        UPDATE product_variants SET stock = (
                            SELECT COUNT(*) FROM account_stock
                            WHERE variant_id = $1 AND is_used = FALSE
                        ) WHERE id = $1
                    """, row['variant_id'])
                if row['product_id']:
                    await conn.execute("""
                        UPDATE products SET stock = COALESCE((
                            SELECT SUM(CASE WHEN NOT is_used THEN 1 ELSE 0 END)
                            FROM account_stock WHERE product_id = $1
                        ), 0) WHERE id = $1
                    """, row['product_id'])

            data_preview = row['account_data'][:50]
            status = "Available" if not row['is_used'] else "Used"
            await message.answer(
                f"✅ <b>AKUN DIHAPUS</b>\n\n"
                f"• ID : {stock_id}\n"
                f"• Data : {data_preview}\n"
                f"• Produk : {row['product_name'] or 'N/A'}\n"
                f"• Variant : {row['variant_name'] or 'N/A'}\n"
                f"• Status : {status}"
            )
            logger.info("[admin] Stock deleted: id=%s data=%s", stock_id, data_preview)
        except Exception as e:
            await message.answer(f"❌ Error: {e}")


@router.message(Command("editstock"))
async def cmd_editstock(message: Message):
    """Edit data akun individual.

    Usage: /editstock ID DATA_BARU

    Contoh:
      /editstock 142 newemail@gmail.com|newpass123|Profile1|5678
    """
    if not _is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/editstock ID DATA_BARU\n\n"
            "<b>Contoh:</b>\n"
            "/editstock 142 newemail@gmail.com|newpass|Profile1|1234\n\n"
            "💡 Gunakan /delstock search KEYWORD untuk cari ID akun"
        )

    try:
        stock_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ ID harus angka.")

    new_data = args[2].strip()
    if not new_data:
        return await message.answer("⚠️ Data baru tidak boleh kosong.")

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    if not pool:
        return await message.answer("❌ Database tidak tersedia.")

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE account_stock SET account_data = $2 WHERE id = $1 RETURNING id, account_data",
                stock_id, new_data,
            )

        if not row:
            return await message.answer(f"⚠️ Account stock ID {stock_id} tidak ditemukan.")

        await message.answer(
            f"✅ <b>AKUN DIUPDATE</b>\n\n"
            f"• ID : {stock_id}\n"
            f"• Data Baru : {new_data[:60]}"
        )
        logger.info("[admin] Stock edited: id=%s", stock_id)
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


# ======================================================================
# /delallstock — Hapus semua stok variant (interaktif)
# ======================================================================

@router.message(Command("delallstock"))
async def cmd_delallstock(message: Message, state: FSMContext):
    """Hapus semua akun unused dari variant tertentu secara interaktif.

    Flow: Pilih produk → Pilih variant → Konfirmasi → Hapus
    """
    if not _is_admin(message.from_user.id):
        return

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()
    if not pool:
        return await message.answer("❌ Database tidak tersedia.")

    try:
        async with pool.acquire() as conn:
            products = await conn.fetch(
                """SELECT id, name FROM products WHERE is_active = TRUE ORDER BY name ASC"""
            )

        if not products:
            return await message.answer("⚠️ Tidak ada produk aktif di database.")

        kb = InlineKeyboardBuilder()
        for p in products:
            kb.button(
                text=f"[{p['id']}] {p['name']}",
                callback_data=f"delallstock:prod:{p['id']}",
            )
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await state.set_state(DelAllStockStates.waiting_for_product_select)
        await message.answer(
            "🗑️ <b>HAPUS SEMUA STOK VARIANT</b>\n\n"
            "Pilih <b>produk</b> yang variantnya ingin dikosongkan stoknya:",
            reply_markup=kb.as_markup(),
        )
    except Exception as e:
        await message.answer(f"❌ Error: {e}")


@router.callback_query(DelAllStockStates.waiting_for_product_select, F.data.startswith("delallstock:prod:"))
async def delallstock_product_selected(callback: CallbackQuery, state: FSMContext):
    """Tampilkan daftar variant setelah produk dipilih."""
    product_id = int(callback.data.split(":")[-1])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            product = await conn.fetchrow("SELECT id, name FROM products WHERE id = $1", product_id)
            variants = await conn.fetch(
                """SELECT id, name, stock FROM product_variants
                   WHERE product_id = $1 AND is_active = TRUE
                   ORDER BY name ASC""",
                product_id,
            )

        if not product:
            return await callback.answer("⚠️ Produk tidak ditemukan.", show_alert=True)

        if not variants:
            return await callback.answer("⚠️ Produk ini tidak punya variant aktif.", show_alert=True)

        await state.update_data(delallstock_product_id=product_id, delallstock_product_name=product["name"])
        await state.set_state(DelAllStockStates.waiting_for_variant_select)

        kb = InlineKeyboardBuilder()
        for v in variants:
            kb.button(
                text=f"{v['name']} (stok: {v['stock']})",
                callback_data=f"delallstock:var:{v['id']}",
            )
        kb.button(text="🔙 Kembali", callback_data="delallstock:back_to_product")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await callback.message.edit_text(
            f"🗑️ <b>HAPUS SEMUA STOK VARIANT</b>\n\n"
            f"Produk: <b>{product['name']}</b>\n\n"
            f"Pilih <b>variant</b> yang stoknya ingin dikosongkan:",
            reply_markup=kb.as_markup(),
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)


@router.callback_query(DelAllStockStates.waiting_for_variant_select, F.data == "delallstock:back_to_product")
async def delallstock_back_to_product(callback: CallbackQuery, state: FSMContext):
    """Kembali ke pilih produk."""
    from app.infrastructure.database.connection import get_pool
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            products = await conn.fetch(
                "SELECT id, name FROM products WHERE is_active = TRUE ORDER BY name ASC"
            )

        kb = InlineKeyboardBuilder()
        for p in products:
            kb.button(
                text=f"[{p['id']}] {p['name']}",
                callback_data=f"delallstock:prod:{p['id']}",
            )
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await state.set_state(DelAllStockStates.waiting_for_product_select)
        await callback.message.edit_text(
            "🗑️ <b>HAPUS SEMUA STOK VARIANT</b>\n\n"
            "Pilih <b>produk</b> yang variantnya ingin dikosongkan stoknya:",
            reply_markup=kb.as_markup(),
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)


@router.callback_query(DelAllStockStates.waiting_for_variant_select, F.data.startswith("delallstock:var:"))
async def delallstock_variant_selected(callback: CallbackQuery, state: FSMContext):
    """Tampilkan konfirmasi sebelum hapus."""
    variant_id = int(callback.data.split(":")[-1])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            variant = await conn.fetchrow(
                """SELECT v.id, v.name, v.stock, p.name as product_name
                   FROM product_variants v
                   JOIN products p ON p.id = v.product_id
                   WHERE v.id = $1""",
                variant_id,
            )

        if not variant:
            return await callback.answer("⚠️ Variant tidak ditemukan.", show_alert=True)

        data = await state.get_data()
        await state.update_data(delallstock_variant_id=variant_id, delallstock_variant_name=variant["name"])
        await state.set_state(DelAllStockStates.waiting_for_confirmation)

        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Ya, Hapus Semua", callback_data=f"delallstock:confirm:{variant_id}")
        kb.button(text="🔙 Kembali", callback_data=f"delallstock:back_to_variant:{data.get('delallstock_product_id', 0)}")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await callback.message.edit_text(
            f"⚠️ <b>KONFIRMASI HAPUS STOK</b>\n\n"
            f"Produk  : <b>{variant['product_name']}</b>\n"
            f"Variant : <b>{variant['name']}</b>\n"
            f"Stok    : <b>{variant['stock']} akun</b>\n\n"
            f"<i>Semua akun <u>yang belum terpakai</u> di variant ini akan dihapus permanen.\n"
            f"Akun yang sudah terkirim ke customer TIDAK akan dihapus.</i>\n\n"
            f"Lanjutkan?",
            reply_markup=kb.as_markup(),
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)


@router.callback_query(DelAllStockStates.waiting_for_confirmation, F.data.startswith("delallstock:back_to_variant:"))
async def delallstock_back_to_variant(callback: CallbackQuery, state: FSMContext):
    """Kembali ke pilih variant."""
    product_id = int(callback.data.split(":")[-1])
    data = await state.get_data()
    product_name = data.get("delallstock_product_name", "")

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            variants = await conn.fetch(
                """SELECT id, name, stock FROM product_variants
                   WHERE product_id = $1 AND is_active = TRUE ORDER BY name ASC""",
                product_id,
            )

        await state.set_state(DelAllStockStates.waiting_for_variant_select)
        kb = InlineKeyboardBuilder()
        for v in variants:
            kb.button(
                text=f"{v['name']} (stok: {v['stock']})",
                callback_data=f"delallstock:var:{v['id']}",
            )
        kb.button(text="🔙 Kembali", callback_data="delallstock:back_to_product")
        kb.button(text="❌ Batal", callback_data="admin:cancel")
        kb.adjust(1)

        await callback.message.edit_text(
            f"🗑️ <b>HAPUS SEMUA STOK VARIANT</b>\n\n"
            f"Produk: <b>{product_name}</b>\n\n"
            f"Pilih <b>variant</b> yang stoknya ingin dikosongkan:",
            reply_markup=kb.as_markup(),
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Error: {e}", show_alert=True)


@router.callback_query(DelAllStockStates.waiting_for_confirmation, F.data.startswith("delallstock:confirm:"))
async def delallstock_confirm(callback: CallbackQuery, state: FSMContext):
    """Eksekusi hapus semua stok unused di variant."""
    variant_id = int(callback.data.split(":")[-1])

    from app.infrastructure.database.connection import get_pool
    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            # Ambil info variant dulu
            variant = await conn.fetchrow(
                """SELECT v.id, v.name, v.product_id, p.name as product_name
                   FROM product_variants v
                   JOIN products p ON p.id = v.product_id
                   WHERE v.id = $1""",
                variant_id,
            )
            if not variant:
                await callback.answer("⚠️ Variant tidak ditemukan.", show_alert=True)
                await state.clear()
                return

            # Hitung dulu berapa yang akan dihapus
            count_before = await conn.fetchval(
                "SELECT COUNT(*) FROM account_stock WHERE variant_id = $1 AND is_used = FALSE",
                variant_id,
            )

            # Hapus semua akun unused
            result = await conn.execute(
                "DELETE FROM account_stock WHERE variant_id = $1 AND is_used = FALSE",
                variant_id,
            )

            # Sync stock variant → 0
            await conn.execute(
                "UPDATE product_variants SET stock = 0 WHERE id = $1",
                variant_id,
            )

            # Sync stock produk induk
            await conn.execute(
                """UPDATE products SET stock = COALESCE((
                    SELECT SUM(stock) FROM product_variants
                    WHERE product_id = $1 AND is_active = TRUE
                ), 0) WHERE id = $1""",
                variant["product_id"],
            )

        await state.clear()
        await callback.message.edit_text(
            f"✅ <b>STOK BERHASIL DIHAPUS</b>\n\n"
            f"Produk  : <b>{variant['product_name']}</b>\n"
            f"Variant : <b>{variant['name']}</b>\n"
            f"Dihapus : <b>{count_before} akun</b>\n\n"
            f"<i>Stok variant sekarang: 0</i>"
        )
        logger.info(
            "[admin] delallstock: variant_id=%s deleted=%s accounts",
            variant_id, count_before,
        )
        await callback.answer("✅ Stok berhasil dihapus!")
    except Exception as e:
        logger.error("[admin] delallstock error: %s", e)
        await callback.answer(f"❌ Error: {e}", show_alert=True)
        await state.clear()

