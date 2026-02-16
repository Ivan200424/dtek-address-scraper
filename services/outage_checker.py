"""Outage checker service for monitoring DTEK sites."""

import logging
from typing import List, Dict, Any

from parsers.dtek_parser import DtekParser
from config.regions import REGIONS
from database.connection import Database
from database.models import create_outage, get_active_outages

logger = logging.getLogger("services.outage_checker")


class OutageChecker:
    """Service for checking power outages."""

    def __init__(self, db: Database):
        """Initialize outage checker.
        
        Args:
            db: Database connection
        """
        self.db = db
        self.parser = DtekParser()

    async def check_region(self, region_key: str) -> List[Dict[str, Any]]:
        """Check outages for a specific region.
        
        Args:
            region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
            
        Returns:
            List of new outages found
        """
        if region_key not in REGIONS:
            logger.error("Unknown region: %s", region_key)
            return []

        try:
            logger.info("Checking outages for region: %s", region_key)
            
            # Parse outages from DTEK site
            outages = await self.parser.parse_outages(region_key)
            
            if not outages:
                logger.info("No outages found for %s", region_key)
                return []

            # Get existing active outages
            existing_outages = await get_active_outages(self.db, region_key)
            existing_areas = {o["affected_area"] for o in existing_outages}

            # Filter new outages
            new_outages = []
            for outage in outages:
                if outage["affected_area"] not in existing_areas:
                    # Create outage record in database
                    created = await create_outage(
                        self.db,
                        region=region_key,
                        outage_type=outage["outage_type"],
                        affected_area=outage["affected_area"],
                        start_time=outage.get("start_time"),
                        end_time=outage.get("end_time"),
                        description=outage.get("description"),
                        source_url=outage.get("source_url"),
                        raw_data=outage.get("raw_data"),
                    )
                    if created:
                        new_outages.append(created)
                        logger.info("New outage recorded: %s", outage["affected_area"])

            logger.info("Found %d new outages for %s", len(new_outages), region_key)
            return new_outages

        except Exception as e:
            logger.error("Error checking region %s: %s", region_key, e, exc_info=True)
            return []

    async def check_all_regions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Check outages for all regions.
        
        Returns:
            Dict mapping region keys to lists of new outages
        """
        results = {}
        for region_key in REGIONS.keys():
            results[region_key] = await self.check_region(region_key)
        return results
