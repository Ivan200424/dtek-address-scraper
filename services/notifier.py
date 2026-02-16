"""Notification service for sending alerts to users."""

import logging
from typing import List, Dict, Any

from telegram import Bot
from telegram.error import TelegramError

from config.regions import REGIONS, REGION_EMOJIS
from database.connection import Database
from database.models import (
    get_all_active_users,
    get_user_addresses,
    create_notification,
)

logger = logging.getLogger("services.notifier")


class Notifier:
    """Service for sending notifications to users."""

    def __init__(self, db: Database, bot: Bot):
        """Initialize notifier.
        
        Args:
            db: Database connection
            bot: Telegram bot instance
        """
        self.db = db
        self.bot = bot

    async def notify_users_about_outages(
        self, region_key: str, outages: List[Dict[str, Any]]
    ) -> None:
        """Notify users about new outages in their region.
        
        Args:
            region_key: Region key
            outages: List of outage records
        """
        if not outages:
            return

        try:
            # Get all active users
            users = await get_all_active_users(self.db)
            logger.info("Notifying %d users about %d outages in %s", 
                       len(users), len(outages), region_key)

            for user in users:
                try:
                    # Get user's addresses in this region
                    addresses = await get_user_addresses(self.db, user["id"])
                    user_addresses_in_region = [
                        addr for addr in addresses if addr["region"] == region_key
                    ]

                    if not user_addresses_in_region:
                        continue

                    # Check if any outage affects user's addresses
                    relevant_outages = []
                    for outage in outages:
                        for addr in user_addresses_in_region:
                            # Simple check: if address is mentioned in affected area
                            # In production, use more sophisticated address matching
                            if self._address_matches(addr, outage["affected_area"]):
                                relevant_outages.append((outage, addr))
                                break

                    if relevant_outages:
                        await self._send_notification(user, relevant_outages, region_key)

                except Exception as e:
                    logger.error("Error notifying user %s: %s", user["chat_id"], e)

        except Exception as e:
            logger.error("Error in notify_users_about_outages: %s", e)

    def _address_matches(self, address: Dict[str, Any], affected_area: str) -> bool:
        """Check if address is affected by outage.
        
        Args:
            address: Address record
            affected_area: Affected area description
            
        Returns:
            True if address matches
        """
        # Normalize both strings for comparison
        normalized_addr = address.get("normalized_address", "").lower()
        normalized_area = affected_area.lower()

        # Check if street is mentioned in affected area
        street = address.get("street", "").lower()
        if street and street in normalized_area:
            return True

        # Check if full address is mentioned
        if normalized_addr and normalized_addr in normalized_area:
            return True

        return False

    async def _send_notification(
        self,
        user: Dict[str, Any],
        outages: List[tuple],
        region_key: str,
    ) -> None:
        """Send notification to user about outages.
        
        Args:
            user: User record
            outages: List of (outage, address) tuples
            region_key: Region key
        """
        try:
            region_name = REGIONS[region_key]["name"]
            emoji = REGION_EMOJIS.get(region_key, "⚡")

            message = f"🚨 Нове відключення в регіоні {emoji} {region_name}!\n\n"

            for outage, addr in outages:
                outage_emoji = "🔴" if outage["outage_type"] == "emergency" else "🟡"
                outage_type = (
                    "Аварійне відключення"
                    if outage["outage_type"] == "emergency"
                    else "Планове відключення"
                )

                message += f"{outage_emoji} {outage_type}\n"
                message += f"📍 Ваша адреса: {addr['full_address']}\n"
                
                if addr.get("queue_number"):
                    message += f"🔢 Черга: {addr['queue_number']}\n"
                
                message += f"🗺 Зона відключення: {outage['affected_area']}\n"

                if outage.get("start_time"):
                    message += f"⏰ Початок: {outage['start_time'].strftime('%d.%m.%Y %H:%M')}\n"
                if outage.get("end_time"):
                    message += f"⏰ Кінець: {outage['end_time'].strftime('%d.%m.%Y %H:%M')}\n"

                message += "\n"

            # Send message
            await self.bot.send_message(
                chat_id=user["chat_id"],
                text=message,
            )

            # Record notification
            for outage, _ in outages:
                await create_notification(self.db, user["id"], outage["id"])

            logger.info("Notification sent to user %s", user["chat_id"])

        except TelegramError as e:
            logger.error("Telegram error sending to %s: %s", user["chat_id"], e)
        except Exception as e:
            logger.error("Error sending notification to %s: %s", user["chat_id"], e)
