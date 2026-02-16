"""Bot command handlers."""

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot import keyboards, messages
from config.regions import REGIONS, REGION_EMOJIS
from database.connection import Database
from database.models import (
    add_address,
    count_user_addresses,
    create_user,
    delete_address,
    get_active_outages,
    get_user_addresses,
    get_user_by_chat_id,
)
from parsers.dtek_parser import DtekParser
from services.queue_checker import get_queue_number

logger = logging.getLogger("bot.handlers")

# Conversation states for address addition
SELECT_REGION, ENTER_CITY, ENTER_STREET, ENTER_BUILDING, CONFIRM_ADDRESS = range(5)


def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    """Get database from bot context."""
    return context.bot_data["db"]


def get_max_addresses(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get max addresses per user from bot context."""
    return context.bot_data.get("max_addresses", 10)


# ==================== Helper Functions ====================

def validate_city(city: str) -> bool:
    """Validate city name has proper prefix."""
    city_lower = city.lower().strip()
    valid_prefixes = ["м. ", "с. ", "смт. ", "с-ще. "]
    return any(city_lower.startswith(prefix) for prefix in valid_prefixes)


def validate_street(street: str) -> bool:
    """Validate street name has proper prefix."""
    street_lower = street.lower().strip()
    valid_prefixes = ["вул. ", "просп. ", "пров. ", "пл. ", "б-р. "]
    return any(street_lower.startswith(prefix) for prefix in valid_prefixes)


def validate_building(building: str) -> bool:
    """Validate building number."""
    # Allow numbers, letters, and common separators
    import re
    return bool(re.match(r'^[\dА-Яа-яA-Za-z\-/]+$', building.strip()))


def format_datetime(dt) -> str:
    """Format datetime for display."""
    if dt is None:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")


# ==================== Command Handlers ====================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    db = get_db(context)

    try:
        await create_user(
            db,
            chat_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )
        logger.info("User %s (%s) started bot", user.id, user.username)
    except Exception as e:
        logger.error("Error creating user: %s", e)

    await update.message.reply_text(
        messages.WELCOME_MESSAGE,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(messages.HELP_MESSAGE)


# ==================== Add Address Conversation ====================

async def add_address_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start add address conversation."""
    user = update.effective_user
    db = get_db(context)
    max_addr = get_max_addresses(context)

    try:
        db_user = await get_user_by_chat_id(db, user.id)
        if db_user:
            count = await count_user_addresses(db, db_user["id"])
            if count >= max_addr:
                await update.message.reply_text(
                    messages.MAX_ADDRESSES_REACHED.format(max_addresses=max_addr)
                )
                return ConversationHandler.END
    except Exception as e:
        logger.error("Error checking address limit: %s", e)

    await update.message.reply_text(
        messages.SELECT_REGION,
        reply_markup=keyboards.region_keyboard(),
    )
    return SELECT_REGION


async def region_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle region selection."""
    query = update.callback_query
    await query.answer()

    region_key = query.data.replace("region_", "")
    if region_key not in REGIONS:
        await query.edit_message_text("❌ Невідомий регіон. Спробуйте ще раз.")
        return SELECT_REGION

    context.user_data["region"] = region_key
    region_name = REGIONS[region_key]["name"]

    # For Kyiv, skip city entry
    if region_key == "kyiv":
        context.user_data["city"] = "м. Київ"
        await query.edit_message_text(
            f"✅ Регіон: {region_name}\n🏙 Населений пункт: м. Київ\n\n{messages.ENTER_STREET}"
        )
        return ENTER_STREET

    await query.edit_message_text(
        f"✅ Регіон: {region_name}\n\n{messages.ENTER_CITY}"
    )
    return ENTER_CITY


async def city_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle city entry."""
    city = update.message.text.strip()

    if city == "❌ Скасувати":
        return await cancel_handler(update, context)

    if not validate_city(city):
        await update.message.reply_text(messages.INVALID_CITY_PREFIX)
        return ENTER_CITY

    context.user_data["city"] = city
    await update.message.reply_text(messages.ENTER_STREET)
    return ENTER_STREET


async def street_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle street entry."""
    street = update.message.text.strip()

    if street == "❌ Скасувати":
        return await cancel_handler(update, context)

    if not validate_street(street):
        await update.message.reply_text(messages.INVALID_STREET_PREFIX)
        return ENTER_STREET

    context.user_data["street"] = street
    await update.message.reply_text(messages.ENTER_BUILDING)
    return ENTER_BUILDING


async def building_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle building entry and show confirmation."""
    building = update.message.text.strip()

    if building == "❌ Скасувати":
        return await cancel_handler(update, context)

    if not validate_building(building):
        await update.message.reply_text(messages.INVALID_BUILDING)
        return ENTER_BUILDING

    context.user_data["building"] = building

    region_key = context.user_data["region"]
    city = context.user_data["city"]
    street = context.user_data["street"]
    region_name = REGIONS[region_key]["name"]

    # Check for current outages
    outage_status = await _check_address_outages(context, region_key, city, street, building)

    # Get queue number using AJAX approach
    await update.message.reply_text("🔍 Перевіряю номер черги відключення...")
    try:
        queue_number = await get_queue_number(region_key, city, street, building)
        context.user_data["queue_number"] = queue_number

        if queue_number and queue_number != "невідомо":
            queue_info = f"🔢 Черга відключення: {queue_number}"
        else:
            queue_info = "🔢 Черга відключення: невідомо"
    except Exception as e:
        logger.error("Error getting queue number: %s", e, exc_info=True)
        queue_info = "🔢 Черга відключення: невідомо"
        context.user_data["queue_number"] = None

    await update.message.reply_text(
        messages.CONFIRM_ADDRESS.format(
            region_name=region_name,
            city=city,
            street=street,
            building=building,
            queue_info=queue_info,
            outage_status=outage_status,
        ),
        reply_markup=keyboards.confirm_keyboard(),
    )
    return CONFIRM_ADDRESS


async def _check_address_outages(
    context: ContextTypes.DEFAULT_TYPE,
    region_key: str,
    city: str,
    street: str,
    building: str,
) -> str:
    """Check current outages for address."""
    db = get_db(context)
    full_address = f"{city}, {street}, {building}"
    normalized = DtekParser.normalize_address(full_address)

    try:
        outages = await get_active_outages(db, region_key)
        if not outages:
            return messages.OUTAGE_STATUS_NONE

        # Simple matching - check if street is mentioned in affected area
        matching_outages = []
        for outage in outages:
            affected_lower = outage["affected_area"].lower()
            street_lower = street.lower()
            if street_lower in affected_lower:
                matching_outages.append(outage)

        if not matching_outages:
            return messages.OUTAGE_STATUS_NONE

        items = []
        for outage in matching_outages:
            outage_type = outage.get("outage_type", "emergency")
            if outage_type == "emergency":
                emoji = "🔴"
                type_text = "Аварійне відключення"
            elif outage_type == "planned":
                emoji = "🟡"
                type_text = "Планове відключення"
            else:
                emoji = "⚪"
                type_text = outage_type

            items.append(
                messages.OUTAGE_STATUS_ITEM.format(
                    emoji=emoji,
                    outage_type=type_text,
                    start_time=format_datetime(outage.get("start_time")),
                    end_time=format_datetime(outage.get("end_time")),
                )
            )

        return messages.OUTAGE_STATUS_INFO.format(outages_list="\n".join(items))

    except Exception as e:
        logger.error("Error checking outages: %s", e)
        return messages.OUTAGE_STATUS_NONE


async def confirm_address_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Confirm and save address - FIXED VERSION."""
    user = update.effective_user
    db = get_db(context)

    # Ensure all required data is in user_data
    required_keys = ["region", "city", "street", "building"]
    missing_keys = [k for k in required_keys if k not in context.user_data]
    
    if missing_keys:
        logger.error("Missing user_data keys for user %s: %s", user.id, missing_keys)
        await update.message.reply_text(
            "❌ Виникла помилка. Будь ласка, спробуйте додати адресу знову.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Extract data from context.user_data
    region_key = context.user_data["region"]
    city = context.user_data["city"]
    street = context.user_data["street"]
    building = context.user_data["building"]
    queue_number = context.user_data.get("queue_number")

    # Handle "невідомо" case
    if queue_number == "невідомо" or not queue_number:
        queue_number = None

    full_address = f"{city}, {street}, {building}"
    
    # Normalize address
    try:
        normalized = DtekParser.normalize_address(full_address)
    except Exception as e:
        logger.warning("Error normalizing address '%s': %s", full_address, e)
        normalized = full_address.lower()

    try:
        # Get or create user
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            db_user = await create_user(
                db, user.id, user.username, user.first_name, user.last_name
            )

        # Save address with queue_number
        await add_address(
            db,
            user_id=db_user["id"],
            region=region_key,
            city=city,
            street=street,
            building=building,
            full_address=full_address,
            normalized_address=normalized,
            queue_number=queue_number,
        )

        await update.message.reply_text(
            messages.ADDRESS_SAVED,
            reply_markup=keyboards.main_menu_keyboard(),
        )
        logger.info("Address saved: user=%s, addr=%s, queue=%s", 
                   user.id, full_address, queue_number)

    except Exception as e:
        logger.error("Error saving address for user %s: %s", user.id, e, exc_info=True)
        await update.message.reply_text(
            "❌ Не вдалося зберегти адресу. Спробуйте ще раз.",
            reply_markup=keyboards.main_menu_keyboard(),
        )

    # Always clear user_data at the end
    context.user_data.clear()
    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation."""
    context.user_data.clear()
    await update.message.reply_text(
        messages.OPERATION_CANCELLED,
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


# ==================== My Addresses ====================

async def my_addresses_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /my_addresses command."""
    user = update.effective_user
    db = get_db(context)

    try:
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            # Create user if not exists
            try:
                db_user = await create_user(
                    db, user.id, user.username, user.first_name, user.last_name
                )
            except Exception as e:
                logger.error("Error creating user: %s", e)
                await update.message.reply_text(messages.ERROR_MESSAGE)
                return

        addresses = await get_user_addresses(db, db_user["id"])
        if not addresses:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        text = "📋 Ваші адреси:\n\n"
        for i, addr in enumerate(addresses, 1):
            emoji = REGION_EMOJIS.get(addr["region"], "📍")
            region_name = REGIONS.get(addr["region"], {}).get("name", addr["region"])
            queue_info = ""
            if addr.get("queue_number"):
                queue_info = f"\n   🔢 Черга: {addr['queue_number']}"
            text += f"{i}. {emoji} {region_name}\n   📍 {addr['full_address']}{queue_info}\n\n"

        await update.message.reply_text(text)

    except Exception as e:
        logger.error("Error getting addresses: %s", e)
        await update.message.reply_text(messages.ERROR_MESSAGE)


# ==================== Delete Address ====================

async def delete_address_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show list of addresses for deletion."""
    user = update.effective_user
    db = get_db(context)

    try:
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        addresses = await get_user_addresses(db, db_user["id"])
        if not addresses:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        await update.message.reply_text(
            messages.SELECT_ADDRESS_TO_DELETE,
            reply_markup=keyboards.addresses_keyboard(addresses),
        )

    except Exception as e:
        logger.error("Error getting addresses for deletion: %s", e)
        await update.message.reply_text(messages.ERROR_MESSAGE)


async def delete_address_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle address deletion request."""
    query = update.callback_query
    await query.answer()

    address_id = int(query.data.replace("delete_", ""))
    db = get_db(context)

    try:
        user = update.effective_user
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            return

        addresses = await get_user_addresses(db, db_user["id"])
        addr = next((a for a in addresses if a["id"] == address_id), None)
        if not addr:
            await query.edit_message_text("❌ Адресу не знайдено.")
            return

        await query.edit_message_text(
            messages.CONFIRM_DELETE.format(address=addr["full_address"]),
            reply_markup=keyboards.confirm_delete_keyboard(address_id),
        )

    except Exception as e:
        logger.error("Error preparing deletion: %s", e)


async def confirm_delete_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Confirm address deletion."""
    query = update.callback_query
    await query.answer()

    address_id = int(query.data.replace("confirm_del_", ""))
    db = get_db(context)

    try:
        user = update.effective_user
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            return

        deleted = await delete_address(db, address_id, db_user["id"])
        if deleted:
            await query.edit_message_text(messages.DELETE_CONFIRMED)
        else:
            await query.edit_message_text("❌ Не вдалося видалити адресу.")

    except Exception as e:
        logger.error("Error deleting address: %s", e)
        await query.edit_message_text(messages.ERROR_MESSAGE)


async def cancel_delete_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Cancel address deletion."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(messages.DELETE_CANCELLED)


# ==================== Status ====================

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command."""
    user = update.effective_user
    db = get_db(context)

    try:
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            # Create user if not exists
            try:
                db_user = await create_user(
                    db, user.id, user.username, user.first_name, user.last_name
                )
            except Exception as e:
                logger.error("Error creating user: %s", e)
                await update.message.reply_text(messages.ERROR_MESSAGE)
                return

        addresses = await get_user_addresses(db, db_user["id"])
        if not addresses:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        # Get unique regions
        user_regions = set(addr["region"] for addr in addresses)
        has_outages = False
        text = messages.STATUS_HEADER

        for region_key in user_regions:
            outages = await get_active_outages(db, region_key)
            if outages:
                has_outages = True
                region_name = REGIONS.get(region_key, {}).get("name", region_key)
                emoji = REGION_EMOJIS.get(region_key, "📍")
                text += f"\n{emoji} {region_name}:\n"
                for outage in outages:
                    outage_emoji = "🔴" if outage["outage_type"] == "emergency" else "🟡"
                    text += (
                        f"  {outage_emoji} {outage['affected_area']}\n"
                        f"  ⏰ {format_datetime(outage['start_time'])} — "
                        f"{format_datetime(outage['end_time'])}\n\n"
                    )

        if not has_outages:
            await update.message.reply_text(messages.STATUS_NO_OUTAGES)
        else:
            await update.message.reply_text(text)

    except Exception as e:
        logger.error("Error checking status: %s", e)
        await update.message.reply_text(messages.ERROR_MESSAGE)


# ==================== Menu Text Handlers ====================

async def menu_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle main menu text buttons."""
    text = update.message.text

    if text == "📋 Мої адреси":
        await my_addresses_handler(update, context)
    elif text == "🔍 Перевірити статус":
        await status_handler(update, context)
    elif text == "🗑 Видалити адресу":
        await delete_address_start(update, context)
    elif text == "❓ Допомога":
        await help_handler(update, context)


# ==================== Menu Interrupt Handlers ====================

async def menu_interrupt_my_addresses(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle My Addresses button during conversation."""
    context.user_data.clear()
    await my_addresses_handler(update, context)
    return ConversationHandler.END


async def menu_interrupt_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle Status button during conversation."""
    context.user_data.clear()
    await status_handler(update, context)
    return ConversationHandler.END


async def menu_interrupt_help(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle Help button during conversation."""
    context.user_data.clear()
    await help_handler(update, context)
    return ConversationHandler.END


async def menu_interrupt_delete_address(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle Delete Address button during conversation."""
    context.user_data.clear()
    await delete_address_start(update, context)
    return ConversationHandler.END


# ==================== Error Handler ====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler."""
    logger.error("Error handling update: %s", context.error, exc_info=context.error)
    if update and hasattr(update, "effective_message") and update.effective_message:
        try:
            await update.effective_message.reply_text(messages.ERROR_MESSAGE)
        except Exception:
            pass


# ==================== Handler Registration ====================

def register_handlers(app) -> None:
    """Register all bot handlers.
    
    Args:
        app: Telegram Application instance
    """
    # Add address conversation handler
    add_address_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add_address", add_address_start),
            MessageHandler(filters.Regex("^📍 Додати адресу$"), add_address_start),
        ],
        states={
            SELECT_REGION: [
                CallbackQueryHandler(region_selected, pattern=r"^region_"),
            ],
            ENTER_CITY: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND
                    & ~filters.Regex(r"^(📋 Мої адреси|🔍 Перевірити статус|❓ Допомога|📍 Додати адресу|🗑 Видалити адресу)$"),
                    city_entered,
                ),
            ],
            ENTER_STREET: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND
                    & ~filters.Regex(r"^(📋 Мої адреси|🔍 Перевірити статус|❓ Допомога|📍 Додати адресу|🗑 Видалити адресу)$"),
                    street_entered,
                ),
            ],
            ENTER_BUILDING: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND
                    & ~filters.Regex(r"^(📋 Мої адреси|🔍 Перевірити статус|❓ Допомога|📍 Додати адресу|🗑 Видалити адресу)$"),
                    building_entered,
                ),
            ],
            CONFIRM_ADDRESS: [
                MessageHandler(filters.Regex("^✅ Підтвердити$"), confirm_address_handler),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            MessageHandler(filters.Regex("^❌ Скасувати$"), cancel_handler),
            # Menu interrupts
            MessageHandler(filters.Regex("^📋 Мої адреси$"), menu_interrupt_my_addresses),
            MessageHandler(filters.Regex("^🔍 Перевірити статус$"), menu_interrupt_status),
            MessageHandler(filters.Regex("^❓ Допомога$"), menu_interrupt_help),
            MessageHandler(filters.Regex("^🗑 Видалити адресу$"), menu_interrupt_delete_address),
        ],
        per_message=False,
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(add_address_conv)
    app.add_handler(CommandHandler("my_addresses", my_addresses_handler))
    app.add_handler(CommandHandler("delete_address", delete_address_start))
    app.add_handler(CommandHandler("status", status_handler))

    # Callback handlers for address deletion
    app.add_handler(CallbackQueryHandler(delete_address_callback, pattern=r"^delete_\d+$"))
    app.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_del_\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_delete_callback, pattern=r"^cancel_delete$"))

    # Menu text button handler
    app.add_handler(
        MessageHandler(
            filters.TEXT
            & filters.Regex(r"^(📋 Мої адреси|🔍 Перевірити статус|🗑 Видалити адресу|❓ Допомога)$"),
            menu_text_handler,
        )
    )

    # Global error handler
    app.add_error_handler(error_handler)
