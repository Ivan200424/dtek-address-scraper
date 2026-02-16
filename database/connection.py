"""Підключення до бази даних PostgreSQL через asyncpg."""

import logging
import os
from typing import Any

import asyncpg

from config.settings import Settings

logger = logging.getLogger("database")


class Database:
    """Клас для роботи з PostgreSQL через asyncpg connection pool."""

    def __init__(self, settings: Settings) -> None:
        """Ініціалізація з налаштуваннями."""
        self.settings = settings
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Створити connection pool через asyncpg."""
        try:
            if self.settings.DATABASE_URL:
                self.pool = await asyncpg.create_pool(
                    dsn=self.settings.DATABASE_URL,
                    min_size=2,
                    max_size=10,
                )
            else:
                self.pool = await asyncpg.create_pool(
                    host=self.settings.DB_HOST,
                    port=self.settings.DB_PORT,
                    database=self.settings.DB_NAME,
                    user=self.settings.DB_USER,
                    password=self.settings.DB_PASSWORD,
                    min_size=2,
                    max_size=10,
                )
            logger.info("Підключення до БД встановлено")
        except Exception as e:
            logger.error("Помилка підключення до БД: %s", e)
            raise

    async def disconnect(self) -> None:
        """Закрити connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Підключення до БД закрито")

    async def execute(self, query: str, *args: Any) -> str:
        """Виконати запит без повернення результату."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Виконати запит і повернути всі рядки."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Виконати запит і повернути один рядок."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Виконати запит і повернути одне значення."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def init_tables(self) -> None:
        """Виконати init.sql для створення таблиць."""
        sql_path = os.path.join(
            os.path.dirname(__file__), "migrations", "init.sql"
        )
        try:
            with open(sql_path, "r", encoding="utf-8") as f:
                sql = f.read()
            async with self.pool.acquire() as conn:
                await conn.execute(sql)
            logger.info("Таблиці БД ініціалізовано")
        except Exception as e:
            logger.error("Помилка ініціалізації таблиць: %s", e)
            raise
