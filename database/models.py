"""CRUD операції з базою даних."""

import json
import logging
from datetime import datetime
from typing import Any

from database.connection import Database

logger = logging.getLogger("database.models")


# ===================== Users =====================

async def create_user(
    db: Database,
    chat_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> Any:
    """Створити або оновити користувача (INSERT ... ON CONFLICT DO UPDATE)."""
    try:
        return await db.fetchrow(
            """
            INSERT INTO users (chat_id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (chat_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                is_active = TRUE
            RETURNING *
            """,
            chat_id, username, first_name, last_name,
        )
    except Exception as e:
        logger.error("Помилка створення користувача: %s", e)
        raise


async def get_user_by_chat_id(db: Database, chat_id: int) -> Any:
    """Отримати користувача за chat_id."""
    try:
        return await db.fetchrow(
            "SELECT * FROM users WHERE chat_id = $1", chat_id
        )
    except Exception as e:
        logger.error("Помилка отримання користувача: %s", e)
        raise


async def deactivate_user(db: Database, chat_id: int) -> None:
    """Деактивувати користувача."""
    try:
        await db.execute(
            "UPDATE users SET is_active = FALSE WHERE chat_id = $1", chat_id
        )
    except Exception as e:
        logger.error("Помилка деактивації користувача: %s", e)
        raise


# ===================== Addresses =====================

async def add_address(
    db: Database,
    user_id: int,
    region: str,
    city: str | None,
    street: str,
    building: str | None,
    full_address: str,
    normalized_address: str | None,
    queue_number: str | None = None,
) -> Any:
    """Додати адресу користувача."""
    try:
        return await db.fetchrow(
            """
            INSERT INTO addresses
                (user_id, region, city, street, building, full_address, normalized_address, queue_number)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            user_id, region, city, street, building, full_address, normalized_address, queue_number,
        )
    except Exception as e:
        logger.error("Помилка додавання адреси: %s", e)
        raise


async def get_user_addresses(db: Database, user_id: int) -> list[Any]:
    """Отримати список адрес користувача."""
    try:
        return await db.fetch(
            "SELECT * FROM addresses WHERE user_id = $1 ORDER BY created_at", user_id
        )
    except Exception as e:
        logger.error("Помилка отримання адрес: %s", e)
        raise


async def delete_address(db: Database, address_id: int, user_id: int) -> bool:
    """Видалити адресу (перевірити що належить цьому user_id)."""
    try:
        result = await db.execute(
            "DELETE FROM addresses WHERE id = $1 AND user_id = $2",
            address_id, user_id,
        )
        return result == "DELETE 1"
    except Exception as e:
        logger.error("Помилка видалення адреси: %s", e)
        raise


async def get_addresses_by_region(db: Database, region: str) -> list[Any]:
    """Отримати всі адреси для регіону."""
    try:
        return await db.fetch(
            """
            SELECT a.*, u.chat_id
            FROM addresses a
            JOIN users u ON a.user_id = u.id
            WHERE a.region = $1 AND u.is_active = TRUE
            """,
            region,
        )
    except Exception as e:
        logger.error("Помилка отримання адрес за регіоном: %s", e)
        raise


async def count_user_addresses(db: Database, user_id: int) -> int:
    """Кількість адрес користувача."""
    try:
        return await db.fetchval(
            "SELECT COUNT(*) FROM addresses WHERE user_id = $1", user_id
        )
    except Exception as e:
        logger.error("Помилка підрахунку адрес: %s", e)
        raise


async def update_address_queue(
    db: Database, address_id: int, queue_number: str | None
) -> bool:
    """Оновити номер черги для адреси."""
    try:
        result = await db.execute(
            "UPDATE addresses SET queue_number = $1 WHERE id = $2",
            queue_number, address_id,
        )
        return result == "UPDATE 1"
    except Exception as e:
        logger.error("Помилка оновлення номера черги: %s", e)
        raise


# ===================== Outages =====================

async def create_outage(
    db: Database,
    region: str,
    outage_type: str,
    affected_area: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    description: str | None = None,
    source_url: str | None = None,
    raw_data: dict | None = None,
) -> Any:
    """Створити запис про відключення."""
    try:
        raw_json = json.dumps(raw_data, ensure_ascii=False, default=str) if raw_data else None
        return await db.fetchrow(
            """
            INSERT INTO outages
                (region, outage_type, affected_area, start_time, end_time,
                 description, source_url, raw_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING *
            """,
            region, outage_type, affected_area, start_time, end_time,
            description, source_url, raw_json,
        )
    except Exception as e:
        logger.error("Помилка створення запису відключення: %s", e)
        raise


async def get_active_outages(
    db: Database, region: str | None = None
) -> list[Any]:
    """Отримати активні відключення (end_time > now або end_time IS NULL)."""
    try:
        if region:
            return await db.fetch(
                """
                SELECT * FROM outages
                WHERE region = $1
                  AND (end_time > NOW() OR end_time IS NULL)
                ORDER BY created_at DESC
                """,
                region,
            )
        return await db.fetch(
            """
            SELECT * FROM outages
            WHERE end_time > NOW() OR end_time IS NULL
            ORDER BY created_at DESC
            """,
        )
    except Exception as e:
        logger.error("Помилка отримання активних відключень: %s", e)
        raise


async def outage_exists(
    db: Database, region: str, affected_area: str, outage_type: str
) -> bool:
    """Перевірити чи вже існує таке відключення (щоб не дублювати)."""
    try:
        result = await db.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM outages
                WHERE region = $1
                  AND affected_area = $2
                  AND outage_type = $3
                  AND (end_time > NOW() OR end_time IS NULL)
            )
            """,
            region, affected_area, outage_type,
        )
        return result
    except Exception as e:
        logger.error("Помилка перевірки існування відключення: %s", e)
        raise


# ===================== Notifications =====================

async def create_notification(
    db: Database, user_id: int, outage_id: int, status: str = "sent"
) -> Any:
    """Записати сповіщення."""
    try:
        return await db.fetchrow(
            """
            INSERT INTO notifications (user_id, outage_id, status)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, outage_id) DO NOTHING
            RETURNING *
            """,
            user_id, outage_id, status,
        )
    except Exception as e:
        logger.error("Помилка створення сповіщення: %s", e)
        raise


async def notification_already_sent(
    db: Database, user_id: int, outage_id: int
) -> bool:
    """Перевірити чи вже надсилали сповіщення."""
    try:
        result = await db.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM notifications
                WHERE user_id = $1 AND outage_id = $2
            )
            """,
            user_id, outage_id,
        )
        return result
    except Exception as e:
        logger.error("Помилка перевірки сповіщення: %s", e)
        raise
