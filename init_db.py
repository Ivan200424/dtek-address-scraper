"""Скрипт ініціалізації бази даних."""

import asyncio

from config.settings import Settings
from database.connection import Database
from utils.logger import setup_logging


async def init() -> None:
    """Ініціалізувати базу даних."""
    settings = Settings()
    setup_logging(settings.LOG_LEVEL)

    db = Database(settings)
    await db.connect()
    await db.init_tables()
    print("✅ База даних ініціалізована!")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(init())
