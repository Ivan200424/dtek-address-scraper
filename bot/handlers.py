"""Обробники команд Telegram-бота."""

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
from config.regions import REGIONS
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
from parsers.base_parser import BaseParser
from services.address_matcher import AddressMatcher
from utils.helpers import (
    escape_html,
    format_datetime,
    get_region_emoji,
    validate_building,
    validate_city,
    validate_street,
)

logger = logging.getLogger("bot.handlers")

# Стани ConversationHandler для додавання адреси
SELECT_REGION, ENTER_CITY, ENTER_STREET, ENTER_BUILDING, CONFIRM_ADDRESS = range(5)


def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    """Отримати об'єкт бази даних з контексту бота."""
    return context.bot_data["db"]


def get_max_addresses(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отримати максимальну кількість адрес з контексту бота."""
    return context.bot_data.get("max_addresses", 10)


# ===================== /start =====================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /start."""
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
        logger.info("Користувач %s (%s) почав роботу з ботом", user.id, user.username)
    except Exception as e:
        logger.error("Помилка збереження користувача: %s", e)

    await update.message.reply_text(
        messages.WELCOME_MESSAGE,
        reply_markup=keyboards.main_menu_keyboard(),
    )


# ===================== /help =====================

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /help."""
    await update.message.reply_text(messages.HELP_MESSAGE)


# ===================== /add_address (ConversationHandler) =====================

async def add_address_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Початок додавання адреси — перевірити ліміт та показати регіони."""
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
        logger.error("Помилка перевірки ліміту адрес: %s", e)

    await update.message.reply_text(
        messages.SELECT_REGION,
        reply_markup=keyboards.region_keyboard(),
    )
    return SELECT_REGION


async def region_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обробка вибору регіону."""
    query = update.callback_query
    await query.answer()

    region_key = query.data.replace("region_", "")
    if region_key not in REGIONS:
        await query.edit_message_text("❌ Невідомий регіон. Спробуйте ще раз.")
        return SELECT_REGION

    context.user_data["region"] = region_key
    region_name = REGIONS[region_key]["name"]

    # Для Києва пропускаємо етап міста
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
    """Обробка введення міста."""
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
    """Обробка введення вулиці."""
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
    """Обробка введення номера будинку — показати підсумок з інформацією про відключення."""
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
    full_address = f"{city}, {street}, {building}"

    # Перевірити поточні відключення за цією адресою
    outage_status = await _check_address_outages(
        context, region_key, full_address
    )

    await update.message.reply_text(
        messages.CONFIRM_ADDRESS.format(
            region_name=region_name,
            city=city,
            street=street,
            building=building,
            full_address=full_address,
            outage_status=outage_status,
        ),
        reply_markup=keyboards.confirm_keyboard(),
    )
    return CONFIRM_ADDRESS


async def _check_address_outages(
    context: ContextTypes.DEFAULT_TYPE,
    region_key: str,
    full_address: str,
) -> str:
    """Перевірити поточні відключення для адреси.

    Args:
        context: Контекст бота.
        region_key: Ключ регіону.
        full_address: Повна адреса.

    Returns:
        Текст зі статусом відключень.
    """
    db = get_db(context)
    normalized = BaseParser.normalize_address(full_address)

    try:
        outages = await get_active_outages(db, region_key)
        if not outages:
            return messages.OUTAGE_STATUS_NONE

        matching_outages = []
        matcher = AddressMatcher()
        for outage in outages:
            if matcher.check_match(normalized, outage["affected_area"]):
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

            items.append(messages.OUTAGE_STATUS_ITEM.format(
                emoji=emoji,
                outage_type=type_text,
                start_time=format_datetime(outage.get("start_time")),
                end_time=format_datetime(outage.get("end_time")),
            ))

        return messages.OUTAGE_STATUS_INFO.format(
            outages_list="\n".join(items)
        )
    except Exception as e:
        logger.error("Помилка перевірки відключень для адреси: %s", e)
        return messages.OUTAGE_STATUS_NONE


async def confirm_address_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Підтвердження та збереження адреси."""
    user = update.effective_user
    db = get_db(context)

    region_key = context.user_data.get("region", "")
    city = context.user_data.get("city", "")
    street = context.user_data.get("street", "")
    building = context.user_data.get("building", "")
    full_address = f"{city}, {street}, {building}"
    normalized = BaseParser.normalize_address(full_address)

    try:
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            db_user = await create_user(db, user.id, user.username, user.first_name, user.last_name)

        await add_address(
            db,
            user_id=db_user["id"],
            region=region_key,
            city=city,
            street=street,
            building=building,
            full_address=full_address,
            normalized_address=normalized,
        )
        await update.message.reply_text(
            messages.ADDRESS_SAVED,
            reply_markup=keyboards.main_menu_keyboard(),
        )
        logger.info("Адресу збережено для користувача %s: %s", user.id, full_address)
    except Exception as e:
        logger.error("Помилка збереження адреси: %s", e)
        await update.message.reply_text(messages.ERROR_MESSAGE)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Скасування операції."""
    context.user_data.clear()
    await update.message.reply_text(
        messages.OPERATION_CANCELLED,
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


# ===================== /my_addresses =====================

async def my_addresses_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обробник команди /my_addresses — список адрес."""
    user = update.effective_user
    db = get_db(context)

    try:
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            # Автоматично створити користувача якщо не існує
            db_user = await create_user(db, user.id, user.username, user.first_name, user.last_name)
        
        if not db_user:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        addresses = await get_user_addresses(db, db_user["id"])
        if not addresses:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        text = "📋 Ваші адреси:\n\n"
        for i, addr in enumerate(addresses, 1):
            emoji = get_region_emoji(addr["region"])
            region_name = REGIONS.get(addr["region"], {}).get("name", addr["region"])
            text += f"{i}. {emoji} {region_name}\n   📍 {addr['full_address']}\n\n"

        await update.message.reply_text(text)
    except Exception as e:
        logger.error("Помилка отримання адрес: %s", e)
        await update.message.reply_text(messages.ERROR_MESSAGE)


# ===================== /delete_address =====================

async def delete_address_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Показати список адрес для видалення."""
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
        logger.error("Помилка отримання адрес для видалення: %s", e)
        await update.message.reply_text(messages.ERROR_MESSAGE)


async def delete_address_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обробка натискання на адресу для видалення — запитати підтвердження."""
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
        logger.error("Помилка підготовки видалення: %s", e)


async def confirm_delete_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Підтвердження видалення адреси."""
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
        logger.error("Помилка видалення адреси: %s", e)
        await query.edit_message_text(messages.ERROR_MESSAGE)


async def cancel_delete_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Скасування видалення адреси."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(messages.DELETE_CANCELLED)


# ===================== /status =====================

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник команди /status — перевірити поточні відключення."""
    user = update.effective_user
    db = get_db(context)

    try:
        db_user = await get_user_by_chat_id(db, user.id)
        if not db_user:
            # Автоматично створити користувача якщо не існує
            db_user = await create_user(db, user.id, user.username, user.first_name, user.last_name)
        
        if not db_user:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        addresses = await get_user_addresses(db, db_user["id"])
        if not addresses:
            await update.message.reply_text(messages.NO_ADDRESSES)
            return

        # Зібрати унікальні регіони
        user_regions = set(addr["region"] for addr in addresses)
        has_outages = False
        text = messages.STATUS_HEADER

        for region_key in user_regions:
            outages = await get_active_outages(db, region_key)
            if outages:
                has_outages = True
                region_name = REGIONS.get(region_key, {}).get("name", region_key)
                emoji = get_region_emoji(region_key)
                text += f"\n{emoji} {region_name}:\n"
                for outage in outages:
                    outage_emoji = "🔴" if outage["outage_type"] == "emergency" else "🟡"
                    text += (
                        f"  {outage_emoji} {escape_html(outage['affected_area'])}\n"
                        f"  ⏰ {format_datetime(outage['start_time'])} — "
                        f"{format_datetime(outage['end_time'])}\n\n"
                    )

        if not has_outages:
            await update.message.reply_text(messages.STATUS_NO_OUTAGES)
        else:
            await update.message.reply_text(text)
    except Exception as e:
        logger.error("Помилка перевірки статусу: %s", e)
        await update.message.reply_text(messages.ERROR_MESSAGE)


# ===================== Текстові кнопки меню =====================

async def menu_text_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обробка текстових кнопок головного меню (крім 'Додати адресу')."""
    text = update.message.text

    if text == "📋 Мої адреси":
        await my_addresses_handler(update, context)
    elif text == "🔍 Перевірити статус":
        await status_handler(update, context)
    elif text == "🗑 Видалити адресу":
        await delete_address_start(update, context)
    elif text == "❓ Допомога":
        await help_handler(update, context)


# ===================== Menu interrupt handlers (для ConversationHandler fallbacks) =====================

async def menu_interrupt_my_addresses(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обробка кнопки 'Мої адреси' під час conversation — очистити стан і показати адреси."""
    context.user_data.clear()
    await my_addresses_handler(update, context)
    return ConversationHandler.END


async def menu_interrupt_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обробка кнопки 'Перевірити статус' під час conversation — очистити стан і показати статус."""
    context.user_data.clear()
    await status_handler(update, context)
    return ConversationHandler.END


async def menu_interrupt_help(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обробка кнопки 'Допомога' під час conversation — очистити стан і показати допомогу."""
    context.user_data.clear()
    await help_handler(update, context)
    return ConversationHandler.END


async def menu_interrupt_delete_address(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обробка кнопки 'Видалити адресу' під час conversation — очистити стан і показати список адрес."""
    context.user_data.clear()
    await delete_address_start(update, context)
    return ConversationHandler.END


# ===================== Error handler =====================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальний обробник помилок."""
    logger.error("Помилка при обробці оновлення: %s", context.error)
    if update and hasattr(update, "effective_message") and update.effective_message:
        try:
            await update.effective_message.reply_text(messages.ERROR_MESSAGE)
        except Exception:
            pass


# ===================== Реєстрація handlers =====================

def register_handlers(app) -> None:
    """Зареєструвати всі обробники команд.

    Args:
        app: Application з python-telegram-bot.
    """
    # ConversationHandler для додавання адреси
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
                    city_entered
                ),
            ],
            ENTER_STREET: [
                MessageHandler(
                    filters.TEXT 
                    & ~filters.COMMAND 
                    & ~filters.Regex(r"^(📋 Мої адреси|🔍 Перевірити статус|❓ Допомога|📍 Додати адресу|🗑 Видалити адресу)$"),
                    street_entered
                ),
            ],
            ENTER_BUILDING: [
                MessageHandler(
                    filters.TEXT 
                    & ~filters.COMMAND 
                    & ~filters.Regex(r"^(📋 Мої адреси|🔍 Перевірити статус|❓ Допомога|📍 Додати адресу|🗑 Видалити адресу)$"),
                    building_entered
                ),
            ],
            CONFIRM_ADDRESS: [
                MessageHandler(filters.Regex("^✅ Підтвердити$"), confirm_address_handler),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            MessageHandler(filters.Regex("^❌ Скасувати$"), cancel_handler),
            # Обробка кнопок меню — завершити розмову і виконати дію
            MessageHandler(filters.Regex("^📋 Мої адреси$"), menu_interrupt_my_addresses),
            MessageHandler(filters.Regex("^🔍 Перевірити статус$"), menu_interrupt_status),
            MessageHandler(filters.Regex("^❓ Допомога$"), menu_interrupt_help),
            MessageHandler(filters.Regex("^🗑 Видалити адресу$"), menu_interrupt_delete_address),
        ],
        per_message=False,
    )

    # Реєстрація обробників
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(add_address_conv)
    app.add_handler(CommandHandler("my_addresses", my_addresses_handler))
    app.add_handler(CommandHandler("delete_address", delete_address_start))
    app.add_handler(CommandHandler("status", status_handler))

    # Callback handlers для видалення адрес
    app.add_handler(CallbackQueryHandler(delete_address_callback, pattern=r"^delete_\d+$"))
    app.add_handler(CallbackQueryHandler(confirm_delete_callback, pattern=r"^confirm_del_\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_delete_callback, pattern=r"^cancel_delete$"))

    # Текстові кнопки меню (крім "Додати адресу" — обробляється в ConversationHandler)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(
            r"^(📋 Мої адреси|🔍 Перевірити статус|🗑 Видалити адресу|❓ Допомога)$"
        ),
        menu_text_handler,
    ))

    # Глобальний обробник помилок
    app.add_error_handler(error_handler)
