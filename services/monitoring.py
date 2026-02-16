"""Monitoring service for periodic outage checks."""

import logging

from telegram.ext import Application

from config.settings import settings
from database.connection import Database
from services.outage_checker import OutageChecker
from services.notifier import Notifier

logger = logging.getLogger("services.monitoring")


class MonitoringService:
    """Service for periodic monitoring of power outages."""

    def __init__(self, db: Database, app: Application, settings_obj=None):
        """Initialize monitoring service.
        
        Args:
            db: Database connection
            app: Telegram application
            settings_obj: Settings object (optional)
        """
        self.db = db
        self.app = app
        self.settings = settings_obj or settings
        self.outage_checker = OutageChecker(db)
        self.notifier = Notifier(db, app.bot)

    async def run_check(self) -> None:
        """Run periodic check for outages."""
        try:
            logger.info("Starting periodic outage check")

            # Check all regions
            results = await self.outage_checker.check_all_regions()

            # Notify users about new outages
            for region_key, outages in results.items():
                if outages:
                    logger.info("Found %d new outages in %s", len(outages), region_key)
                    await self.notifier.notify_users_about_outages(region_key, outages)

            logger.info("Periodic check completed")

        except Exception as e:
            logger.error("Error in periodic check: %s", e, exc_info=True)
