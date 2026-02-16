"""Сервіс моніторингу відключень електроенергії."""

import asyncio
import logging
from typing import Any

from config.regions import REGIONS
from database.connection import Database
from database.models import (
    create_outage,
    get_addresses_by_region,
    notification_already_sent,
    outage_exists,
    get_user_by_chat_id,
)
from parsers.dnipro_parser import DniproParser
from parsers.kyiv_parser import KyivParser
from parsers.kyiv_region_parser import KyivRegionParser
from parsers.odesa_parser import OdesaParser
from services.address_matcher import AddressMatcher
from services.notification import NotificationService

class MonitoringService:
    """Сервіс моніторингу аварійних відключень ДТЕК."""

    def __init__(self, db: Database, bot_app: Any, settings: Any) -> None:
        """Ініціалізація сервісу моніторингу.

        Args:
            db: Об'єкт бази даних.
            bot_app: Application з python-telegram-bot.
            settings: Налаштування.
        """
        self.db = db
        self.bot_app = bot_app
        self.settings = settings
        self.parsers = [
            KyivParser(),
            KyivRegionParser(),
            DniproParser(),
            OdesaParser(),
        ]
        self.matcher = AddressMatcher()
        self.notifier = NotificationService(db, bot_app)
        self.logger = logging.getLogger("monitoring")

    async def run_check(self) -> None:
        """Основний цикл перевірки відключень.

        Викликається APScheduler кожні CHECK_INTERVAL секунд.
        """
        self.logger.info("Початок перевірки відключень...")
        total_new_outages = 0
        total_notifications = 0

        for parser in self.parsers:
            try:
                new_outages, notifications = await self.check_region(parser)
                total_new_outages += new_outages
                total_notifications += notifications
            except Exception as e:
                self.logger.error(
                    "Помилка перевірки регіону %s: %s",
                    parser.region_key, e,
                )

            # Затримка між парсерами
            await asyncio.sleep(2)

        self.logger.info(
            "Перевірку завершено: %d нових відключень, %d сповіщень",
            total_new_outages,
            total_notifications,
        )

    async def check_region(self, parser) -> tuple[int, int]:
        """Перевірити один регіон.

        Args:
            parser: Парсер для регіону.

        Returns:
            Кортеж (кількість нових відключень, кількість сповіщень).
        """
        new_outages_count = 0
        notifications_count = 0

        try:
            outages = await parser.parse_outages()

            for outage_data in outages:
                try:
                    # Перевірити чи вже існує
                    exists = await outage_exists(
                        self.db,
                        parser.region_key,
                        outage_data["affected_area"],
                        outage_data["outage_type"],
                    )
                    if exists:
                        continue

                    # Зберегти в БД
                    region_url = REGIONS.get(parser.region_key, {}).get("url", "")
                    db_outage = await create_outage(
                        self.db,
                        region=parser.region_key,
                        outage_type=outage_data["outage_type"],
                        affected_area=outage_data["affected_area"],
                        start_time=outage_data.get("start_time"),
                        end_time=outage_data.get("end_time"),
                        description=outage_data.get("description", ""),
                        source_url=region_url,
                        raw_data=outage_data.get("raw_data"),
                    )
                    new_outages_count += 1

                    # Знайти адреси користувачів для цього регіону
                    addresses = await get_addresses_by_region(
                        self.db, parser.region_key
                    )

                    # Перевірити збіг кожної адреси з зоною відключення
                    matching = self.matcher.find_matching_addresses(
                        addresses, outage_data["affected_area"]
                    )

                    region_name = REGIONS.get(parser.region_key, {}).get(
                        "name", parser.region_key
                    )

                    for addr in matching:
                        try:
                            # Перевірити чи вже надсилали
                            db_user = await get_user_by_chat_id(
                                self.db, addr["chat_id"]
                            )
                            if not db_user:
                                continue

                            already_sent = await notification_already_sent(
                                self.db,
                                user_id=db_user["id"],
                                outage_id=db_outage["id"],
                            )
                            if already_sent:
                                continue

                            # Відправити сповіщення
                            outage_with_id = {**outage_data, "id": db_outage["id"]}
                            await self.notifier.send_outage_notification(
                                chat_id=addr["chat_id"],
                                address=dict(addr),
                                outage=outage_with_id,
                                region_name=region_name,
                            )
                            notifications_count += 1

                        except Exception as e:
                            self.logger.error(
                                "Помилка обробки адреси %s: %s",
                                addr.get("full_address"), e,
                            )

                except Exception as e:
                    self.logger.error(
                        "Помилка обробки відключення: %s", e
                    )

        except Exception as e:
            self.logger.error(
                "Помилка перевірки регіону %s: %s",
                parser.region_key, e,
            )

        return new_outages_count, notifications_count
