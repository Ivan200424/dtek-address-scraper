"""Сервіс сповіщень користувачів."""

import logging
from typing import Any

from bot import messages
from config.regions import REGIONS
from database.connection import Database
from database.models import create_notification, get_user_by_chat_id
from utils.helpers import escape_html, format_datetime

class NotificationService:
    """Сервіс для відправки сповіщень користувачам через Telegram."""

    def __init__(self, db: Database, bot_app: Any) -> None:
        """Ініціалізація сервісу сповіщень.

        Args:
            db: Об'єкт бази даних.
            bot_app: Application з python-telegram-bot.
        """
        self.db = db
        self.bot = bot_app.bot
        self.logger = logging.getLogger("notification")

    async def send_outage_notification(
        self,
        chat_id: int,
        address: dict,
        outage: dict,
        region_name: str,
    ) -> None:
        """Відправити сповіщення про відключення.

        Args:
            chat_id: ID чату користувача.
            address: Дані адреси.
            outage: Дані відключення.
            region_name: Назва регіону.
        """
        try:
            outage_type = outage.get("outage_type", "emergency")
            outage_type_emoji = "🔴" if outage_type == "emergency" else "🟡"
            outage_type_text = (
                "Аварійне відключення" if outage_type == "emergency"
                else "Планове відключення"
            )

            text = messages.OUTAGE_NOTIFICATION.format(
                outage_type_emoji=outage_type_emoji,
                outage_type_text=outage_type_text,
                address=escape_html(address.get("full_address", "")),
                region_name=escape_html(region_name),
                start_time=format_datetime(outage.get("start_time")),
                end_time=format_datetime(outage.get("end_time")),
                description=escape_html(outage.get("description", "—")),
                source_url=outage.get("source_url", REGIONS.get(outage.get("region", ""), {}).get("url", "")),
            )

            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
            )

            # Записати сповіщення в БД
            db_user = await get_user_by_chat_id(self.db, chat_id)
            if db_user and outage.get("id"):
                await create_notification(
                    self.db,
                    user_id=db_user["id"],
                    outage_id=outage["id"],
                    status="sent",
                )

            self.logger.info(
                "Сповіщення відправлено до %s: %s",
                chat_id,
                address.get("full_address", ""),
            )

        except Exception as e:
            self.logger.error(
                "Помилка відправки сповіщення до %s: %s", chat_id, e
            )
            # Спробувати записати невдале сповіщення
            try:
                db_user = await get_user_by_chat_id(self.db, chat_id)
                if db_user and outage.get("id"):
                    await create_notification(
                        self.db,
                        user_id=db_user["id"],
                        outage_id=outage["id"],
                        status="failed",
                    )
            except Exception:
                pass

    async def send_restoration_notification(
        self,
        chat_id: int,
        address: dict,
        region_name: str,
    ) -> None:
        """Сповіщення про відновлення електропостачання.

        Args:
            chat_id: ID чату користувача.
            address: Дані адреси.
            region_name: Назва регіону.
        """
        try:
            text = messages.RESTORATION_NOTIFICATION.format(
                address=escape_html(address.get("full_address", "")),
                region_name=escape_html(region_name),
            )

            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
            )
            self.logger.info(
                "Сповіщення про відновлення відправлено до %s", chat_id
            )
        except Exception as e:
            self.logger.error(
                "Помилка відправки сповіщення про відновлення до %s: %s",
                chat_id, e,
            )
