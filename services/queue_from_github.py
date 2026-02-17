"""Fallback queue data from outage-data-ua GitHub repository.

This module fetches schedule data from the Baskerville42/outage-data-ua repository
which updates every 5 minutes and contains schedule data for all queues.

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
        Dict containing schedule data for all queues in the region, or None on error
        
    Example response:
        {
            "1.1": {
                "schedule": [...],
                "last_updated": "2026-02-17T09:00:00Z"
            },
            "1.2": {...},
            ...
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
        logger.info("Successfully fetched schedule data for %s (%d queues)", region_key, len(data))
        return data
        
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON from %s: %s", url, e)
        return None
    except Exception as e:
        logger.error("Error fetching schedule data: %s", e, exc_info=True)
        return None


async def get_queue_schedule(region_key: str, queue_number: str) -> Optional[Dict[str, Any]]:
    """Get schedule for a specific queue.
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        queue_number: Queue number (e.g., "3.1", "1.2")
        
    Returns:
        Dict with schedule data for the queue, or None if not found
    """
    schedules = await fetch_region_schedules(region_key)
    
    if not schedules:
        return None
    
    return schedules.get(queue_number)


async def verify_queue_number(region_key: str, queue_number: str) -> bool:
    """Verify that a queue number exists in the GitHub data.
    
    This can be used to validate queue numbers returned by the DTEK scraper.
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        queue_number: Queue number to verify (e.g., "3.1")
        
    Returns:
        True if queue exists, False otherwise
    """
    schedules = await fetch_region_schedules(region_key)
    
    if not schedules:
        # If we can't fetch data, assume the queue is valid
        logger.warning("Could not verify queue %s for %s (GitHub data unavailable)", 
                      queue_number, region_key)
        return True
    
    exists = queue_number in schedules
    
    if not exists:
        logger.warning("Queue %s not found in GitHub data for %s", queue_number, region_key)
    
    return exists


async def format_queue_schedule(region_key: str, queue_number: str) -> Optional[str]:
    """Format schedule for a queue as human-readable text.
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        queue_number: Queue number (e.g., "3.1")
        
    Returns:
        Formatted schedule text, or None if not available
    """
    schedule_data = await get_queue_schedule(region_key, queue_number)
    
    if not schedule_data:
        return None
    
    schedule = schedule_data.get("schedule", [])
    last_updated = schedule_data.get("last_updated", "невідомо")
    
    if not schedule:
        return f"📅 Розклад для черги {queue_number}:\nДані відсутні"
    
    lines = [f"📅 Розклад для черги {queue_number}:"]
    
    for entry in schedule[:7]:  # Show up to 7 days
        date = entry.get("date", "")
        hours = entry.get("outage_hours", [])
        
        if hours:
            hours_str = ", ".join(f"{h[0]}-{h[1]}" for h in hours)
            lines.append(f"  {date}: {hours_str}")
        else:
            lines.append(f"  {date}: немає відключень")
    
    lines.append(f"\n🕒 Оновлено: {last_updated}")
    
    return "\n".join(lines)
