"""Fallback queue data from outage-data-ua GitHub repository.

This module fetches schedule data from the Baskerville42/outage-data-ua repository
which updates every 5 minutes and contains schedule data for all queues.

NOTE: The actual data format from the GitHub repo is more complex than initially
designed. The data uses "GPV" prefix for queue numbers (e.g., "GPV1.1", "GPV3.1")
and has a nested structure with timestamps and hour-by-hour status.

This module is currently a stub for future implementation. The main queue detection
functionality in queue_checker.py does not depend on this module.

Can be used to:
- Verify queue numbers from the DTEK website
- Show schedule information for a specific queue
- Provide fallback when DTEK website is unavailable
"""

import logging
from typing import Optional, Dict, Any
import asyncio
import json

logger = logging.getLogger("services.queue_from_github")

# GitHub repository URL for schedule data
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data"

# Region mapping to GitHub JSON files
REGION_TO_FILE = {
    "kyiv": "kyiv.json",
    "kyiv_region": "kyiv-region.json",
    "dnipro": "dnipro.json",
    "odesa": "odesa.json",
}


async def fetch_region_schedules(region_key: str) -> Optional[Dict[str, Any]]:
    """Fetch schedule data for a region from GitHub.
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        
    Returns:
        Dict containing full data from GitHub, or None on error
        
    Example response structure:
        {
            "regionId": "kyiv-region",
            "lastUpdated": "2026-02-17T09:51:17.242Z",
            "fact": {
                "data": {
                    "1771279200": {  # timestamp
                        "GPV1.1": { "1": "yes", "2": "yes", ... },  # hour-by-hour
                        "GPV1.2": { ... },
                        ...
                    }
                }
            }
        }
    """
    if region_key not in REGION_TO_FILE:
        logger.error("Unknown region: %s", region_key)
        return None
    
    filename = REGION_TO_FILE[region_key]
    url = f"{GITHUB_RAW_BASE}/{filename}"
    
    logger.info("Fetching schedule data from: %s", url)
    
    try:
        # Use asyncio to run subprocess for curl (simple HTTP GET)
        # Alternative: could use aiohttp if it was in requirements
        process = await asyncio.create_subprocess_exec(
            "curl", "-s", "-f", "--max-time", "10", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error("Failed to fetch %s: %s", url, stderr.decode())
            return None
        
        data = json.loads(stdout.decode())
        logger.info("Successfully fetched schedule data for %s", region_key)
        return data
        
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from %s: %s", url, e)
        return None
    except Exception as e:
        logger.error("Error fetching schedule data: %s", e, exc_info=True)
        return None


async def get_queue_schedule(region_key: str, queue_number: str) -> Optional[Dict[str, Any]]:
    """Get schedule for a specific queue.
    
    NOTE: This is a stub implementation. The actual data format from GitHub
    uses "GPV" prefixes and requires more complex parsing.
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        queue_number: Queue number (e.g., "3.1", "1.2")
        
    Returns:
        Dict with schedule data for the queue, or None if not found
    """
    schedules = await fetch_region_schedules(region_key)
    
    if not schedules:
        return None
    
    # TODO: Parse the actual GitHub data format
    # The data uses "GPV" prefix, e.g., "GPV3.1" instead of "3.1"
    # and has a nested timestamp-based structure
    
    logger.warning("get_queue_schedule is not fully implemented - data format needs parsing")
    return None


async def verify_queue_number(region_key: str, queue_number: str) -> bool:
    """Verify that a queue number exists in the GitHub data.
    
    NOTE: This is a stub implementation. Always returns True for now.
    
    This can be used to validate queue numbers returned by the DTEK scraper.
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        queue_number: Queue number to verify (e.g., "3.1")
        
    Returns:
        True (always, until parsing is implemented)
    """
    # For now, just return True - we don't want to block valid queue numbers
    # TODO: Implement parsing of GitHub data format with GPV prefixes
    logger.debug("verify_queue_number called for %s in %s (stub implementation)", 
                queue_number, region_key)
    return True


async def format_queue_schedule(region_key: str, queue_number: str) -> Optional[str]:
    """Format schedule for a queue as human-readable text.
    
    NOTE: This is a stub implementation.
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        queue_number: Queue number (e.g., "3.1")
        
    Returns:
        None (until parsing is implemented)
    """
    logger.warning("format_queue_schedule is not fully implemented")
    return None
