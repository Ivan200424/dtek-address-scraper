"""Queue checker service using AJAX API approach.

This module uses direct AJAX requests to DTEK API instead of form filling.
Based on the working approach from https://github.com/mr-devboy/dtek-monitor
"""

import json
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config.regions import REGIONS

logger = logging.getLogger("services.queue_checker")

# Timeouts for Playwright operations (milliseconds)
NAVIGATION_TIMEOUT = 60000  # 60 seconds
AJAX_TIMEOUT = 30000  # 30 seconds


async def get_queue_number(
    region_key: str,
    city: Optional[str],
    street: str,
    building: str,
) -> Optional[str]:
    """Get queue number for address using AJAX API.
    
    This function:
    1. Opens the DTEK shutdowns page via Playwright
    2. Extracts CSRF token from meta tag
    3. Makes POST request to /ua/ajax with method=getHomeNum
    4. Parses JSON response to get queue number from 'group' field
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        city: City name (can be None for Kyiv)
        street: Street name
        building: Building number
        
    Returns:
        Queue number as string or None if not found
    """
    if region_key not in REGIONS:
        logger.error("Unknown region: %s", region_key)
        return None

    region_code = REGIONS[region_key]["code"]
    base_url = REGIONS[region_key]["url"]
    
    # Construct base domain from URL
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    ajax_url = urljoin(base_domain, "/ua/ajax")

    logger.info(
        "Getting queue number for %s, %s, %s (region: %s)",
        city, street, building, region_key
    )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="uk-UA",
            )
            page = await context.new_page()

            try:
                # Step 1: Open the shutdowns page
                logger.info("Opening page: %s", base_url)
                await page.goto(base_url, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                logger.info("Page loaded successfully")

                # Step 2: Extract CSRF token from meta tag
                csrf_token = await page.evaluate(
                    "() => document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')"
                )
                
                if not csrf_token:
                    logger.error("CSRF token not found on page")
                    return None
                
                logger.info("CSRF token obtained")

                # Step 3: Prepare form data for AJAX request
                # Format according to DTEK API expectations
                form_data = {
                    "method": "getHomeNum",
                }
                
                data_index = 0
                
                # For regions other than Kyiv, add city parameter
                if region_key != "kyiv" and city:
                    form_data[f"data[{data_index}][name]"] = "city"
                    form_data[f"data[{data_index}][value]"] = city
                    data_index += 1
                
                # Add street parameter
                form_data[f"data[{data_index}][name]"] = "street"
                form_data[f"data[{data_index}][value]"] = street
                data_index += 1
                
                # Add building parameter (house_num)
                form_data[f"data[{data_index}][name]"] = "house_num"
                form_data[f"data[{data_index}][value]"] = building
                data_index += 1
                
                # Add updateFact with current datetime
                current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                form_data[f"data[{data_index}][name]"] = "updateFact"
                form_data[f"data[{data_index}][value]"] = current_datetime

                logger.info("Sending AJAX request to: %s", ajax_url)
                logger.debug("Form data: %s", form_data)

                # Step 4: Make AJAX POST request
                response = await page.request.post(
                    ajax_url,
                    headers={
                        "X-CSRF-TOKEN": csrf_token,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    form=form_data,
                    timeout=AJAX_TIMEOUT,
                )

                if response.status != 200:
                    logger.error("AJAX request failed with status: %d", response.status)
                    return None

                # Step 5: Parse JSON response
                try:
                    response_data = await response.json()
                    logger.info("AJAX response received")
                    logger.debug("Response data: %s", json.dumps(response_data, ensure_ascii=False)[:500])
                    
                    # Extract queue number from 'group' field
                    if isinstance(response_data, dict):
                        queue_number = response_data.get("group")
                        
                        if queue_number:
                            # Convert to string and validate
                            queue_str = str(queue_number).strip()
                            if queue_str and queue_str.lower() != "null":
                                logger.info("Queue number found: %s", queue_str)
                                return queue_str
                            else:
                                logger.warning("Queue number is null or empty")
                        else:
                            logger.warning("'group' field not found in response")
                            
                            # Try to extract from 'data' field if available
                            data_field = response_data.get("data")
                            if isinstance(data_field, dict):
                                # Check if any building entry has group info
                                for building_key, building_data in data_field.items():
                                    if isinstance(building_data, dict) and "group" in building_data:
                                        group_value = building_data["group"]
                                        if group_value:
                                            logger.info("Queue number found in data field: %s", group_value)
                                            return str(group_value).strip()
                    
                    logger.warning("Could not extract queue number from response")
                    return None
                    
                except json.JSONDecodeError as e:
                    logger.error("Failed to parse JSON response: %s", e)
                    return None

            except PlaywrightTimeoutError as e:
                logger.error("Timeout error: %s", e)
                return None
            except Exception as e:
                logger.error("Error getting queue number: %s", e, exc_info=True)
                return None
            finally:
                await browser.close()

    except Exception as e:
        logger.error("Failed to launch Playwright: %s", e)
        return None
