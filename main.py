import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config.settings import BOT_TOKEN
from app.presentation.telegram.handlers import start, menu, order, deposit, admin, voucher, info
from app.infrastructure.database.connection import init_pool, close_pool, test_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def on_startup() -> None:
    """Initialize resources on bot startup."""
    db_ok = await test_db_connection()
    if db_ok:
        logger.info("✅ Database connection OK")
    else:
        logger.warning("⚠️ Database tidak tersedia, pakai mock repositories")


async def on_shutdown() -> None:
    """Cleanup resources on bot shutdown."""
    await close_pool()
    logger.info("🔌 Database pool closed")


async def _register_commands(bot: Bot) -> None:
    """Register bot commands with different scopes for admin vs user.

    - User biasa: hanya lihat commands dasar
    - Admin: lihat semua commands termasuk admin commands
    """
    from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
    from config.settings import ADMIN_IDS

    # Commands untuk semua user (default scope)
    user_commands = [
        BotCommand(command="start", description="Mulai bot"),
        BotCommand(command="balance", description="Cek saldo"),
        BotCommand(command="history", description="Riwayat order"),
        BotCommand(command="voucher", description="Redeem voucher"),
        BotCommand(command="cancel", description="Cancel order"),
        BotCommand(command="refund", description="Request refund"),
    ]

    # Commands untuk admin (semua commands)
    admin_commands = [
        BotCommand(command="start", description="Mulai bot"),
        BotCommand(command="admin", description="Menu admin"),
        BotCommand(command="balance", description="Cek saldo"),
        BotCommand(command="history", description="Riwayat order"),
        BotCommand(command="voucher", description="Redeem voucher"),
        BotCommand(command="addproduct", description="Tambah produk (interactive)"),
        BotCommand(command="editproduct", description="Edit produk"),
        BotCommand(command="delproduct", description="Hapus produk"),
        BotCommand(command="restock", description="Quick restock: /restock ID QTY"),
        BotCommand(command="listproduct", description="List semua produk"),
        BotCommand(command="bulkadd", description="Bulk add produk"),
        BotCommand(command="addstock", description="Add akun ke produk/variant"),
        BotCommand(command="addvariant", description="Tambah variasi produk"),
        BotCommand(command="editvariant", description="Edit variasi produk"),
        BotCommand(command="delvariant", description="Hapus variasi produk"),
        BotCommand(command="listvariant", description="List variasi per produk"),
        BotCommand(command="viewstock", description="Lihat stok akun produk"),
        BotCommand(command="stockall", description="Summary stok akun semua produk"),
        BotCommand(command="settemplate", description="Set template tampilan akun"),
        BotCommand(command="addvoucher", description="Buat voucher"),
        BotCommand(command="listvoucher", description="List voucher aktif"),
        BotCommand(command="delvoucher", description="Hapus voucher"),
        BotCommand(command="banuser", description="Ban user"),
        BotCommand(command="unbanuser", description="Unban user"),
        BotCommand(command="broadcast", description="Broadcast ke semua user"),
        BotCommand(command="report", description="Laporan penjualan"),
        BotCommand(command="topproducts", description="Produk terlaris"),
        BotCommand(command="topusers", description="User top spender"),
        BotCommand(command="setqris", description="Ganti QRIS method"),
        BotCommand(command="getqris", description="Lihat QRIS method"),
        BotCommand(command="stats", description="Statistik bot"),
        BotCommand(command="testwebhook", description="Simulasi callback PAID"),
        BotCommand(command="webhookinfo", description="Info webhook"),
        BotCommand(command="bulkdel", description="Bulk delete produk/variant/stock"),
        BotCommand(command="refund_approve", description="Approve refund: /refund_approve ORDER_ID"),
    ]

    # Set default commands (untuk semua user)
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    # Set admin commands (per admin user)
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
            logger.info("✅ Admin commands registered for user %s", admin_id)
        except Exception as e:
            logger.warning("⚠️ Failed to set admin commands for %s: %s", admin_id, e)

    logger.info("✅ Bot commands registered (user: %d, admin: %d)",
                len(user_commands), len(admin_commands))


async def run_bot() -> None:
    """Run Telegram bot polling."""
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    # Lifecycle hooks
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Daftarkan Router (urutan PENTING - lebih spesifik dulu!)
    # 1. admin.py: admin commands (/admin, /setqris, /stats, /addvoucher, etc)
    # 2. start.py: /start command + page pagination + popular shortcut
    # 3. voucher.py: /voucher command
    # 4. deposit.py: deposit flow (FSM states + callbacks)
    # 5. order.py: callback queries untuk order flow (qty, checkout, note, confirm, cancel)
    # 6. menu.py: reply keyboard buttons + angka produk + catch-all (HARUS TERAKHIR)
    dp.include_router(admin.router)
    dp.include_router(info.router)
    dp.include_router(start.router)
    dp.include_router(voucher.router)
    dp.include_router(deposit.router)
    dp.include_router(order.router)
    dp.include_router(menu.router)

    # Inject bot ke webhook handler untuk notifikasi
    from app.presentation.web.callbacks import set_bot
    set_bot(bot)

    # Register bot commands (different for admin vs user)
    await _register_commands(bot)

    logger.info("🚀 Bot siap! Kirim /start di Telegram.")
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()


async def run_webhook_server() -> None:
    """Run FastAPI webhook server."""
    import uvicorn
    from app.presentation.web.callbacks import app as webhook_app
    from config.settings import WEBHOOK_PORT

    config = uvicorn.Config(
        webhook_app,
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def _cleanup_stale_orders() -> None:
    """Background task: cancel orders pending > 30 menit (safety net)."""
    while True:
        await asyncio.sleep(30 * 60)  # Run every 30 minutes
        try:
            from app.infrastructure.database.connection import get_pool
            pool = get_pool()
            if pool:
                async with pool.acquire() as conn:
                    result = await conn.execute("""
                        UPDATE orders SET status = 'cancelled'
                        WHERE status = 'pending'
                          AND created_at < NOW() - INTERVAL '30 minutes'
                    """)
                    if "UPDATE" in result and result != "UPDATE 0":
                        logger.info("[cleanup] Stale orders cancelled: %s", result)
        except Exception as e:
            logger.error("[cleanup] Error: %s", e)


async def main() -> None:
    """Run bot + webhook server + cleanup task concurrently."""
    from config.settings import ENVIRONMENT

    logger.info("🌐 Mode: %s - running bot + webhook server", ENVIRONMENT)
    await asyncio.gather(
        run_bot(),
        run_webhook_server(),
        _cleanup_stale_orders(),
    )


if __name__ == "__main__":
    asyncio.run(main())
