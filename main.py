"""Точка входу для бота моніторингу відключень ДТЕК."""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from bot.handlers import register_handlers
from config.settings import Settings
from database.connection import Database
from services.monitoring import MonitoringService
from utils.logger import setup_logging


async def main() -> None:
    """Основна функція запуску бота."""
    # 1. Завантажити налаштування
    settings = Settings()

    # 2. Налаштувати логування
    setup_logging(settings.LOG_LEVEL)
    logger = logging.getLogger("main")
    logger.info("Запуск бота...")

    # 3. Підключитись до БД
    db = Database(settings)
    await db.connect()
    await db.init_tables()
    logger.info("БД підключена")

    # 4. Створити Application
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Зберегти db та settings в контексті бота
    app.bot_data["db"] = db
    app.bot_data["max_addresses"] = settings.MAX_ADDRESSES_PER_USER

    # 5. Зареєструвати handlers
    register_handlers(app)
    logger.info("Обробники зареєстровано")

    # 6. Створити MonitoringService
    monitoring = MonitoringService(db, app, settings)

    # 7. Налаштувати APScheduler
    scheduler = AsyncIOScheduler(timezone=settings.TZ)
    scheduler.add_job(
        monitoring.run_check,
        "interval",
        seconds=settings.CHECK_INTERVAL,
        id="outage_check",
        name="Перевірка відключень",
    )
    scheduler.start()
    logger.info("Моніторинг запущено (кожні %d сек)", settings.CHECK_INTERVAL)

    # 8. Запустити бота
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    logger.info("Бот запущено!")

    # 9. Тримати бота запущеним
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Зупинка бота...")
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await db.disconnect()
        logger.info("Бот зупинено")


if __name__ == "__main__":
    asyncio.run(main())
