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
    """Перевірити валідність назви вулиці з префіксом.

    Вулиця повинна починатися з одного з префіксів:
    вул., просп., пров., пл., б-р.

    Args:
        street: Назва вулиці з префіксом.

    Returns:
        True якщо валідна.
    """
    s = street.strip()
    if len(s) < 2:
        return False
    # Перевіряємо наявність одного з допустимих префіксів
    prefix_pattern = r"^(вул\.|просп\.|пров\.|пл\.|б-р\.)\s+"
    match = re.match(prefix_pattern, s, re.IGNORECASE)
    if not match:
        return False
    # Назва після префікса повинна містити мінімум 2 символи
    name_part = s[match.end():].strip()
    if len(name_part) < 2:
        return False
    # Дозволяємо літери (кирилиця та латиниця), цифри, пробіли, дефіси, крапки
    name_pattern = r"^[a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9\s\-\.\']+$"
    return bool(re.match(name_pattern, name_part))


def validate_building(building: str) -> bool:
    """Перевірити валідність номера будинку.

    Args:
        building: Номер будинку.

    Returns:
        True якщо валідний.
    """
    return len(building.strip()) >= 1


def validate_city(city: str) -> bool:
    """Перевірити валідність назви населеного пункту з префіксом.

    Населений пункт повинен починатися з одного з префіксів:
    м., с., смт., с-ще.

    Args:
        city: Назва населеного пункту з префіксом.

    Returns:
        True якщо валідна.
    """
    c = city.strip()
    if len(c) < 2:
        return False
    # Перевіряємо наявність одного з допустимих префіксів
    prefix_pattern = r"^(м\.|с\.|смт\.|с-ще\.)\s+"
    match = re.match(prefix_pattern, c, re.IGNORECASE)
    if not match:
        return False
    # Назва після префікса повинна містити мінімум 2 символи
    name_part = c[match.end():].strip()
    if len(name_part) < 2:
        return False
    # Дозволяємо літери (кирилиця та латиниця), цифри, пробіли, дефіси, апострофи
    name_pattern = r"^[a-zA-Zа-яА-ЯіІїЇєЄґҐ0-9\s\-\']+$"
    return bool(re.match(name_pattern, name_part))


def get_region_emoji(region_key: str) -> str:
    """Повернути emoji для регіону.

    Args:
        region_key: Ключ регіону.

    Returns:
        Emoji символ.
    """
    return REGION_EMOJIS.get(region_key, "📍")
