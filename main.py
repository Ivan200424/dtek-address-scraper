"""Main entry point for DTEK outage monitoring bot."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from bot.handlers import register_handlers
from config.settings import settings
from database.connection import Database
from services.monitoring import MonitoringService
from utils.helpers import setup_logging


async def main() -> None:
    """Main function to start the bot."""
    # 1. Setup logging
    setup_logging(settings.LOG_LEVEL)
    logger = logging.getLogger("main")
    logger.info("Starting DTEK outage monitoring bot...")

    # 2. Connect to database
    db = Database()
    await db.connect()
    await db.init_tables()
    logger.info("Database connected and initialized")

    # 3. Create Telegram application
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Store database and settings in bot data
    app.bot_data["db"] = db
    app.bot_data["max_addresses"] = settings.MAX_ADDRESSES_PER_USER

    # 4. Register handlers
    register_handlers(app)
    logger.info("Bot handlers registered")

    # 5. Create monitoring service
    monitoring = MonitoringService(db, app, settings)

    # 6. Setup scheduler for periodic checks
    scheduler = AsyncIOScheduler(timezone=settings.TZ)
    scheduler.add_job(
        monitoring.run_check,
        "interval",
        seconds=settings.CHECK_INTERVAL,
        id="outage_check",
        name="Periodic outage check",
    )
    scheduler.start()
    logger.info("Monitoring started (checking every %d seconds)", settings.CHECK_INTERVAL)

    # 7. Start bot
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("Bot is running!")

    # 8. Keep bot running
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping bot...")
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await db.disconnect()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
