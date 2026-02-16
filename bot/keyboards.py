"""Keyboard layouts for the bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from config.regions import REGIONS, REGION_EMOJIS


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Create main menu keyboard.
    
    Returns:
        ReplyKeyboardMarkup with main menu buttons
    """
    keyboard = [
        ["📍 Додати адресу", "📋 Мої адреси"],
        ["🔍 Перевірити статус", "🗑 Видалити адресу"],
        ["❓ Допомога"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def region_keyboard() -> InlineKeyboardMarkup:
    """Create region selection keyboard.
    
    Returns:
        InlineKeyboardMarkup with region buttons
    """
    buttons = []
    for key, region in REGIONS.items():
        emoji = REGION_EMOJIS.get(key, "📍")
        button = InlineKeyboardButton(
            f"{emoji} {region['name']}",
            callback_data=f"region_{key}",
        )
        buttons.append([button])
    
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard() -> ReplyKeyboardMarkup:
    """Create confirmation keyboard.
    
    Returns:
        ReplyKeyboardMarkup with confirm/cancel buttons
    """
    keyboard = [
        ["✅ Підтвердити", "❌ Скасувати"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def addresses_keyboard(addresses: list) -> InlineKeyboardMarkup:
    """Create keyboard with address list for deletion.
    
    Args:
        addresses: List of address records
        
    Returns:
        InlineKeyboardMarkup with address buttons
    """
    buttons = []
    for addr in addresses:
        emoji = REGION_EMOJIS.get(addr["region"], "📍")
        text = f"{emoji} {addr['full_address']}"
        # Truncate long addresses
        if len(text) > 60:
            text = text[:57] + "..."
        
        button = InlineKeyboardButton(
            text,
            callback_data=f"delete_{addr['id']}",
        )
        buttons.append([button])
    
    return InlineKeyboardMarkup(buttons)


def confirm_delete_keyboard(address_id: int) -> InlineKeyboardMarkup:
    """Create confirmation keyboard for address deletion.
    
    Args:
        address_id: Address ID
        
    Returns:
        InlineKeyboardMarkup with confirm/cancel buttons
    """
    buttons = [
        [
            InlineKeyboardButton("✅ Так, видалити", callback_data=f"confirm_del_{address_id}"),
            InlineKeyboardButton("❌ Скасувати", callback_data="cancel_delete"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)
