"""Database connection and pool management."""

import logging
from typing import Optional

import asyncpg

from config.settings import settings

logger = logging.getLogger("database.connection")


class Database:
    """PostgreSQL database connection pool manager."""

    def __init__(self):
        """Initialize database manager."""
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create database connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=settings.DATABASE_URL,
                min_size=settings.DB_POOL_MIN_SIZE,
                max_size=settings.DB_POOL_MAX_SIZE,
            )
            logger.info("Database connection pool created")
        except Exception as e:
            logger.error("Failed to create database pool: %s", e)
            raise

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    async def init_tables(self) -> None:
        """Initialize database tables from migration file."""
        if not self.pool:
            raise RuntimeError("Database not connected")

        try:
            with open("database/migrations/init.sql", "r", encoding="utf-8") as f:
                sql = f.read()

            async with self.pool.acquire() as conn:
                # Execute each statement separately to handle DROP + CREATE properly
                statements = [s.strip() for s in sql.split(';') if s.strip()]
                for statement in statements:
                    if statement:
                        await conn.execute(statement + ';')
                logger.info("Database tables initialized")
        except Exception as e:
            logger.error("Failed to initialize tables: %s", e)
            raise
