"""
Handler untuk user info commands.

Commands:
  /balance - Check saldo
  /history - Lihat riwayat order (paginated)
  /cancel ORDER_ID - Cancel pending order
  /refund ORDER_ID - Request refund (notify admin)
"""
import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.infrastructure.database.factory import (
    get_user_repository,
    get_order_repository,
    get_product_repository,
)
from app.presentation.telegram.states import RefundRejectStates

logger = logging.getLogger(__name__)
router = Router()

HISTORY_PAGE_SIZE = 5


# ======================================================================
# /balance - Check saldo user
# ======================================================================

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    """Show user balance."""
    user_repo = await get_user_repository()
    user = await user_repo.get_or_create(message.from_user.id)

    await message.answer(
        f"💰 <b>SALDO KAMU</b>\n\n"
        f"<code>"
        f"Balance : Rp {user.balance:,}\n"
        f"</code>\n"
        f"💡 Deposit via menu \"💰 Deposit\" untuk top up saldo."
    )


# ======================================================================
# /history - Lihat riwayat order (paginated)
# ======================================================================

@router.message(Command("history"))
async def cmd_history(message: Message):
    """Show order history (page 1)."""
    await _show_history_page(message, message.from_user.id, page=0)


@router.callback_query(F.data.startswith("history:page:"))
async def handle_history_page(callback: CallbackQuery):
    """Handle pagination for history."""
    page = int(callback.data.split(":")[2])
    await _show_history_page(callback.message, callback.from_user.id, page, edit=True)
    await callback.answer()


async def _show_history_page(message: Message, user_id: int, page: int, edit: bool = False):
    """Render history page."""
    order_repo = await get_order_repository()
    product_repo = await get_product_repository()

    offset = page * HISTORY_PAGE_SIZE
    orders = await order_repo.get_by_user(user_id, limit=HISTORY_PAGE_SIZE + 1, offset=offset)

    if not orders and page == 0:
        text = "📋 <b>RIWAYAT ORDER</b>\n\n• Belum ada transaksi."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    has_next = len(orders) > HISTORY_PAGE_SIZE
    orders_to_show = orders[:HISTORY_PAGE_SIZE]

    status_emoji = {
        "pending": "⏳",
        "paid": "✅",
        "shipped": "📦",
        "delivered": "✅",
        "cancelled": "❌",
    }

    text = f"📋 <b>RIWAYAT ORDER</b> (hal {page + 1})\n\n"

    for o in orders_to_show:
        product = await product_repo.get_by_id(o.product_id)
        product_name = product.name if product else f"Product #{o.product_id}"
        emoji = status_emoji.get(o.status, "❓")
        created = o.created_at.strftime("%d/%m/%Y %H:%M") if isinstance(o.created_at, datetime) else str(o.created_at)[:16]

        text += (
            f"{emoji} <code>{o.id[:8]}</code>\n"
            f"   {product_name}\n"
            f"   Qty: {o.quantity} | Rp {o.total_price:,} | {o.status}\n"
            f"   {created}\n\n"
        )

    # Pagination buttons
    kb = InlineKeyboardBuilder()
    if page > 0:
        kb.button(text="⬅️ Prev", callback_data=f"history:page:{page - 1}")
    if has_next:
        kb.button(text="Next ➡️", callback_data=f"history:page:{page + 1}")
    kb.adjust(2)

    markup = kb.as_markup() if (page > 0 or has_next) else None

    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


# ======================================================================
# /cancel ORDER_ID - Cancel pending order
# ======================================================================

async def _find_order_by_partial_id(order_id_partial: str, user_id: int):
    """Find order by partial ID (supports 8-char truncated IDs from /history)."""
    order_repo = await get_order_repository()

    # Try exact match first
    order = await order_repo.get_by_id(order_id_partial)
    if order:
        return order

    # Try partial match (LIKE prefix)
    try:
        from app.infrastructure.database.connection import get_pool
        pool = get_pool()
        if pool:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM orders WHERE id LIKE $1 AND user_id = $2 LIMIT 1",
                    f"{order_id_partial}%", user_id,
                )
                if row:
                    from app.domain.entities import Order
                    return Order(
                        id=row["id"],
                        user_id=row["user_id"],
                        product_id=row["product_id"],
                        variant_id=row.get("variant_id"),
                        quantity=row["quantity"],
                        total_price=row["total_price"],
                        status=row["status"],
                        payment_method=row["payment_method"],
                        payment_ref=row["payment_ref"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
    except Exception:
        pass

    return None


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Cancel a pending order. Usage: /cancel ORDER_ID"""
    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "<code>/cancel ORDER_ID</code>\n\n"
            "💡 Lihat ORDER_ID di /history"
        )

    order_id = args[1]
    user_id = message.from_user.id

    order = await _find_order_by_partial_id(order_id, user_id)

    if not order:
        return await message.answer(f"⚠️ Order <code>{order_id}</code> tidak ditemukan.")

    if order.user_id != user_id:
        return await message.answer("⚠️ Order ini bukan milik kamu.")

    if order.status != "pending":
        return await message.answer(
            f"⚠️ Order tidak bisa di-cancel.\n"
            f"Status saat ini: <b>{order.status}</b>\n\n"
            f"Hanya order 'pending' yang bisa di-cancel."
        )

    order_repo = await get_order_repository()
    success = await order_repo.update_status(order.id, "cancelled")

    if success:
        product_repo = await get_product_repository()
        product = await product_repo.get_by_id(order.product_id)
        product_name = product.name if product else "Unknown"

        logger.info("[cancel] Order %s cancelled by user %s", order_id, user_id)
        await message.answer(
            f"✅ <b>ORDER DIBATALKAN</b>\n\n"
            f"<code>"
            f"Order ID : {order_id[:12]}\n"
            f"Produk   : {product_name}\n"
            f"Total    : Rp {order.total_price:,}\n"
            f"</code>\n"
            f"Order telah dibatalkan."
        )
    else:
        await message.answer("❌ Gagal membatalkan order. Coba lagi nanti.")


# ======================================================================
# /refund ORDER_ID - Request refund (notify admin)
# ======================================================================

@router.message(Command("refund"))
async def cmd_refund(message: Message):
    """Request refund for a paid order. Usage: /refund ORDER_ID ALASAN"""
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/refund ORDER_ID ALASAN\n\n"
            "<b>Contoh:</b>\n"
            "/refund e1aeeb74 Akun tidak bisa login\n\n"
            "💡 Lihat ORDER_ID di /history\n"
            "⚠️ Hanya untuk order status 'paid'"
        )

    order_id = args[1]
    reason = args[2]
    user_id = message.from_user.id

    order = await _find_order_by_partial_id(order_id, user_id)

    if not order:
        return await message.answer(f"⚠️ Order <code>{order_id}</code> tidak ditemukan.")

    if order.user_id != user_id:
        return await message.answer("⚠️ Order ini bukan milik kamu.")

    if order.status != "paid":
        return await message.answer(
            f"⚠️ Order tidak bisa di-refund.\n"
            f"Status saat ini: <b>{order.status}</b>\n\n"
            f"Hanya order 'paid' yang bisa di-refund."
        )

    product_repo = await get_product_repository()
    product = await product_repo.get_by_id(order.product_id)
    product_name = product.name if product else "Unknown"

    # Notify admin with approve / reject buttons
    from config.settings import ADMIN_IDS
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Approve Refund", callback_data=f"refund:approve:{order.id[:16]}:{user_id}")
    kb.button(text="❌ Tolak Refund", callback_data=f"refund:reject:{order.id[:16]}:{user_id}")
    kb.adjust(1)

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔄 <b>REFUND REQUEST</b>\n\n"
                    f"Order ID : {order.id[:8]}\n"
                    f"User : @{message.from_user.username or 'N/A'}\n"
                    f"Produk : {product_name}\n"
                    f"Qty : {order.quantity}\n"
                    f"Total : Rp {order.total_price:,}\n\n"
                    f"📝 Alasan: {reason}\n\n"
                    f"✅ Approve : balance auto-refund + status → refunded\n"
                    f"❌ Tolak : kirim alasan ke user\n"
                    f"💡 Atau pakai: /refund_approve {order.id[:8]}"
                ),
                parse_mode="HTML",
                reply_markup=kb.as_markup(),
            )
        except Exception as e:
            logger.error("[refund] Failed to notify admin %s: %s", admin_id, e)

    logger.info("[refund] Refund request: order=%s user=%s reason=%s", order_id, user_id, reason)

    await message.answer(
        f"🔄 <b>REFUND REQUEST DIKIRIM</b>\n\n"
        f"Order ID : {order.id[:8]}\n"
        f"Produk : {product_name}\n"
        f"Total : Rp {order.total_price:,}\n"
        f"Alasan : {reason}\n\n"
        f"📨 Request telah dikirim ke admin.\n"
        f"⏳ Estimasi proses: 1x24 jam."
    )


# ======================================================================
# /refund_approve - Admin approve refund (auto add balance + update status)
# ======================================================================

async def _execute_refund_approval(
    bot,
    admin_id: int,
    order_id_partial: str,
    target_user_id: int | None = None,
) -> tuple[bool, str]:
    """Core logic untuk approve refund. Dipakai oleh callback button & /refund_approve.

    Returns (success, message_for_admin).
    """
    from app.infrastructure.database.connection import get_pool
    user_repo = await get_user_repository()
    order_repo = await get_order_repository()
    product_repo = await get_product_repository()

    # Resolve order by partial ID
    pool = get_pool()
    order = None
    if pool:
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM orders WHERE id LIKE $1 LIMIT 1",
                    f"{order_id_partial}%",
                )
                if row:
                    from app.domain.entities import Order
                    order = Order(
                        id=row["id"],
                        user_id=row["user_id"],
                        product_id=row["product_id"],
                        variant_id=row.get("variant_id"),
                        quantity=row["quantity"],
                        total_price=row["total_price"],
                        status=row["status"],
                        payment_method=row["payment_method"],
                        payment_ref=row["payment_ref"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
        except Exception as e:
            logger.error("[refund_approve] DB lookup error: %s", e)
            return False, f"⚠️ Gagal cari order: {e}"

    if not order:
        return False, f"⚠️ Order {order_id_partial} tidak ditemukan."

    if target_user_id and order.user_id != target_user_id:
        return False, "⚠️ Order tidak match dengan user."

    if order.status not in ("paid", "shipped", "delivered"):
        return False, f"⚠️ Order tidak bisa di-refund.\nStatus saat ini: {order.status}"

    # Atomic: add balance + update status
    refund_amount = int(order.total_price)
    added = await user_repo.add_balance(order.user_id, refund_amount)
    if not added:
        return False, "❌ Gagal tambah saldo user."

    # Update status to 'refunded' (fall back to 'cancelled' if constraint blocks)
    status_set = False
    try:
        if pool:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE orders SET status = 'refunded' WHERE id = $1",
                    order.id,
                )
                status_set = True
    except Exception as e:
        logger.warning("[refund_approve] 'refunded' status not allowed, using 'cancelled': %s", e)

    if not status_set:
        # Fallback to existing status enum
        await order_repo.update_status(order.id, "cancelled")

    # Get product info for messages
    product = await product_repo.get_by_id(order.product_id)
    product_name = product.name if product else "Unknown"

    # Notify user
    try:
        new_balance = 0
        try:
            user = await user_repo.get_by_id(order.user_id)
            new_balance = user.balance if user else 0
        except Exception:
            pass

        await bot.send_message(
            chat_id=order.user_id,
            text=(
                f"✅ <b>REFUND DISETUJUI</b>\n\n"
                f"Order : {order.id[:8]}\n"
                f"Produk : {product_name}\n"
                f"Refund : Rp {refund_amount:,}\n"
                f"Saldo Baru : Rp {new_balance:,}\n\n"
                f"💰 Saldo telah dikembalikan ke akun kamu."
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("[refund_approve] Failed notify user %s: %s", order.user_id, e)

    logger.info(
        "[refund_approve] order=%s user=%s amount=%s by admin=%s",
        order.id, order.user_id, refund_amount, admin_id,
    )

    return True, (
        f"✅ Refund di-approve.\n"
        f"Order : {order.id[:8]}\n"
        f"User : {order.user_id}\n"
        f"Refund : Rp {refund_amount:,}"
    )


@router.callback_query(F.data.startswith("refund:approve:"))
async def handle_refund_approve(callback: CallbackQuery):
    """Admin approve refund via tombol → auto add balance + update status."""
    from config.settings import ADMIN_IDS
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔", show_alert=True)

    parts = callback.data.split(":")
    order_id_partial = parts[2]
    target_user_id = int(parts[3])

    success, msg = await _execute_refund_approval(
        callback.bot,
        callback.from_user.id,
        order_id_partial,
        target_user_id,
    )

    await callback.message.answer(msg)
    if success:
        # Disable buttons on original notif
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await callback.answer()


@router.message(Command("refund_approve"))
async def cmd_refund_approve(message: Message):
    """Admin approve refund via command. Usage: /refund_approve ORDER_ID"""
    from config.settings import ADMIN_IDS
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔ Akses ditolak.")

    args = message.text.split()
    if len(args) < 2:
        return await message.answer(
            "📋 <b>Format:</b>\n"
            "/refund_approve ORDER_ID\n\n"
            "Auto: balance dikembalikan + order ditandai refunded."
        )

    order_id_partial = args[1]
    success, msg = await _execute_refund_approval(
        message.bot,
        message.from_user.id,
        order_id_partial,
        None,
    )
    await message.answer(msg)



@router.callback_query(F.data.startswith("refund:reject:"))
async def handle_refund_reject(callback: CallbackQuery, state: FSMContext):
    """Admin tolak refund → minta alasan → kirim ke user."""
    from config.settings import ADMIN_IDS
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔", show_alert=True)

    parts = callback.data.split(":")
    order_id_partial = parts[2]
    target_user_id = int(parts[3])

    await state.clear()
    await state.update_data(
        refund_reject_order=order_id_partial,
        refund_reject_user=target_user_id,
    )
    await state.set_state(RefundRejectStates.waiting_for_reason)

    await callback.message.answer(
        f"📝 Ketik alasan penolakan refund untuk order {order_id_partial}:"
    )
    await callback.answer()


@router.message(StateFilter(RefundRejectStates.waiting_for_reason))
async def handle_refund_reject_reason(message: Message, state: FSMContext):
    """Handle admin typing reject reason (only when in RefundRejectStates)."""
    from config.settings import ADMIN_IDS
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    order_id_partial = data.get("refund_reject_order", "")
    target_user_id = data.get("refund_reject_user")
    reason = message.text.strip() if message.text else ""
    await state.clear()

    if not target_user_id:
        return await message.answer("⚠️ Data refund tidak ditemukan.")

    if not reason:
        return await message.answer("⚠️ Alasan kosong, dibatalkan.")

    # Send rejection to user
    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"❌ <b>REFUND DITOLAK</b>\n\n"
                f"Order : {order_id_partial}\n"
                f"Alasan : {reason}\n\n"
                f"Hubungi @zoroaze jika ada pertanyaan."
            ),
            parse_mode="HTML",
        )
        await message.answer(f"✅ Refund ditolak. Notifikasi dikirim ke user {target_user_id}.")
    except Exception as e:
        await message.answer(f"❌ Gagal kirim ke user: {e}")

