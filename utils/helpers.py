"""Допоміжні функції."""

import re
from datetime import datetime

from config.regions import REGION_EMOJIS


def format_datetime(dt: datetime | None) -> str:
    """Форматувати дату/час у 'DD.MM.YYYY HH:MM'.

    Args:
        dt: Об'єкт datetime або None.

    Returns:
        Відформатований рядок або 'невідомо'.
    """
    if dt is None:
        return "невідомо"
    return dt.strftime("%d.%m.%Y %H:%M")


def truncate_text(text: str, max_length: int = 200) -> str:
    """Обрізати текст з '...' якщо перевищує максимальну довжину.

    Args:
        text: Вхідний текст.
        max_length: Максимальна довжина.

    Returns:
        Обрізаний текст.
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def escape_html(text: str) -> str:
    """Екранувати HTML символи для Telegram.

    Args:
        text: Вхідний текст.

    Returns:
        Текст з екранованими HTML символами.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def validate_street(street: str) -> bool:
    """Перевірити валідність назви вулиці.

    Args:
        street: Назва вулиці.

    Returns:
        True якщо валідна.
    """
    if len(street.strip()) < 2:
        return False
    # Дозволяємо літери (кирилиця та латиниця), цифри, пробіли, дефіси, крапки
    pattern = r"^[a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9\s\-\.\']+$"
    return bool(re.match(pattern, street.strip()))


def validate_building(building: str) -> bool:
    """Перевірити валідність номера будинку.

    Args:
        building: Номер будинку.

    Returns:
        True якщо валідний.
    """
    return len(building.strip()) >= 1


def get_region_emoji(region_key: str) -> str:
    """Повернути emoji для регіону.

    Args:
        region_key: Ключ регіону.

    Returns:
        Emoji символ.
    """
    return REGION_EMOJIS.get(region_key, "📍")
