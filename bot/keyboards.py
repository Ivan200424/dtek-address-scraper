"""Клавіатури Telegram-бота."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from config.regions import REGIONS, REGION_EMOJIS


def region_keyboard() -> InlineKeyboardMarkup:
    """Клавіатура вибору регіону (4 кнопки)."""
    buttons = [
        [InlineKeyboardButton(
            f"{REGION_EMOJIS[key]} {region['name']}",
            callback_data=f"region_{key}",
        )]
        for key, region in REGIONS.items()
    ]
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавіатура з кнопкою скасування."""
    return ReplyKeyboardMarkup(
        [["❌ Скасувати"]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def addresses_keyboard(addresses: list) -> InlineKeyboardMarkup:
    """Клавіатура зі списком адрес для видалення.

    Args:
        addresses: Список адрес з БД.

    Returns:
        InlineKeyboardMarkup зі списком адрес.
    """
    buttons = [
        [InlineKeyboardButton(
            f"🗑 {addr['full_address']}",
            callback_data=f"delete_{addr['id']}",
        )]
        for addr in addresses
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_delete_keyboard(address_id: int) -> InlineKeyboardMarkup:
    """Клавіатура підтвердження видалення адреси.

    Args:
        address_id: ID адреси для видалення.

    Returns:
        InlineKeyboardMarkup з кнопками підтвердження.
    """
    buttons = [
        [
            InlineKeyboardButton("✅ Так, видалити", callback_data=f"confirm_del_{address_id}"),
            InlineKeyboardButton("❌ Ні, залишити", callback_data="cancel_delete"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Головне меню бота."""
    buttons = [
        ["📍 Додати адресу", "📋 Мої адреси"],
        ["🔍 Перевірити статус", "❓ Допомога"],
    ]
    return ReplyKeyboardMarkup(
        buttons,
        resize_keyboard=True,
    )
