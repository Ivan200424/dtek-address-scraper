"""Queue checker service using AJAX API approach.

This module uses direct AJAX requests to DTEK API instead of form filling.
Based on the working approach from https://github.com/mr-devboy/dtek-monitor
"""

import logging
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config.regions import REGIONS

logger = logging.getLogger("services.queue_checker")

# Timeouts for Playwright operations (milliseconds)
NAVIGATION_TIMEOUT = 60000  # 60 seconds
AJAX_TIMEOUT = 30000  # 30 seconds

# Prefixes to strip from city and street names
CITY_PREFIXES = ["м. ", "с. ", "смт. ", "с-ще. "]
STREET_PREFIXES = ["вул. ", "просп. ", "пров. ", "пл. ", "б-р. "]


def strip_prefix(text: str, prefixes: list[str]) -> str:
    """Strip known prefixes from text.

    Args:
        text: Text to strip prefix from
        prefixes: List of prefixes to try removing

    Returns:
        Text with prefix removed if found, otherwise original text
    """
    if not text:
        return text

    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix):]

    return text


async def search_street(
    page,
    csrf_token: str,
    region_key: str,
    city: Optional[str],
    street_query: str,
) -> Optional[str]:
    """Search for exact street name using DTEK getStreet API.
    
    Args:
        page: Playwright page object (already opened with CSRF token)
        csrf_token: CSRF token from the page
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        city: City name (can be None for Kyiv)
        street_query: User's street input to search for
        
    Returns:
        Exact street name from DTEK database or None if not found
    """
    is_kyiv = region_key == "kyiv"
    clean_city = strip_prefix(city, CITY_PREFIXES) if city else ""
    clean_street = strip_prefix(street_query, STREET_PREFIXES)
    
    logger.info("Searching for street: '%s' in city: '%s'", clean_street, clean_city)
    
    try:
        response_data = await page.evaluate(
            """async ({ isKyiv, city, street, csrfToken }) => {
                const formData = new URLSearchParams();
                formData.append("method", "getStreet");

                let i = 0;
                
                if (!isKyiv && city) {
                    formData.append(`data[${i}][name]`, "city");
                    formData.append(`data[${i}][value]`, city);
                    i++;
                }

                formData.append(`data[${i}][name]`, "street");
                formData.append(`data[${i}][value]`, street);

                const response = await fetch("/ua/ajax", {
                    method: "POST",
                    headers: {
                        "x-requested-with": "XMLHttpRequest",
                        "x-csrf-token": csrfToken,
                    },
                    body: formData,
                });
                return await response.json();
            }""",
            {"isKyiv": is_kyiv, "city": clean_city, "street": clean_street, "csrfToken": csrf_token}
        )
        
        logger.debug("getStreet response: %s", response_data)
        
        # Response format: { data: ["exact street name 1", "exact street name 2", ...] }
        if response_data and "data" in response_data:
            data = response_data["data"]
            if isinstance(data, list) and len(data) > 0:
                # Return the first matching street name
                # DTEK API returns results sorted by relevance, with best match first
                exact_street = data[0]
                logger.info("Found exact street name: '%s' for query: '%s'", exact_street, clean_street)
                return exact_street
            else:
                logger.warning("No streets found for query: '%s'", clean_street)
                return None
        else:
            logger.warning("Invalid getStreet response format")
            return None
            
    except Exception as e:
        logger.error("Error searching for street: %s", e, exc_info=True)
        return None


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
    3. Calls getStreet API to resolve exact street name
    4. Makes POST request to /ua/ajax with method=getHomeNum using page.evaluate()
    5. Parses JSON response to extract queue number from response.data[building].group
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        city: City name (can be None for Kyiv)
        street: Street name (will be resolved via getStreet API)
        building: Building number
        
    Returns:
        Queue number as string or None if not found
    """
    if region_key not in REGIONS:
        logger.error("Unknown region: %s", region_key)
        return None

    base_url = REGIONS[region_key]["url"]

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
                # Step 1: Open the shutdowns page and wait for full load
                logger.info("Opening page: %s", base_url)
                await page.goto(base_url, timeout=NAVIGATION_TIMEOUT, wait_until="load")
                logger.info("Page loaded successfully")

                # Step 2: Extract CSRF token
                csrf_token = await page.evaluate(
                    "() => document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')"
                )
                
                if not csrf_token:
                    logger.error("CSRF token not found on page")
                    return None

                logger.info("CSRF token obtained")

                # Step 3: Resolve exact street name using getStreet API
                # This ensures we use the correct name from DTEK's database
                exact_street = await search_street(page, csrf_token, region_key, city, street)
                
                # If street resolution failed, fall back to cleaned user input
                if not exact_street:
                    logger.warning("Street resolution failed, using cleaned user input")
                    exact_street = strip_prefix(street, STREET_PREFIXES)
                
                is_kyiv = region_key == "kyiv"
                clean_city = strip_prefix(city, CITY_PREFIXES) if city else ""
                
                logger.info(
                    "Using street name: '%s' for city: '%s' (from user input: '%s')",
                    exact_street, clean_city, street
                )
                
                # Step 4: Make AJAX request using page.evaluate (same context as browser)
                # Fixed: Use dynamic counter for data[] indices instead of hardcoded values
                response_data = await page.evaluate(
                    """async ({ isKyiv, city, street, csrfToken }) => {
                        const formData = new URLSearchParams();
                        formData.append("method", "getHomeNum");

                        // Use dynamic counter for data[] indices
                        let i = 0;
                        
                        if (!isKyiv && city) {
                            formData.append(`data[${i}][name]`, "city");
                            formData.append(`data[${i}][value]`, city);
                            i++;
                        }

                        formData.append(`data[${i}][name]`, "street");
                        formData.append(`data[${i}][value]`, street);
                        i++;
                        
                        formData.append(`data[${i}][name]`, "updateFact");
                        formData.append(`data[${i}][value]`, new Date().toLocaleString("uk-UA"));

                        const response = await fetch("/ua/ajax", {
                            method: "POST",
                            headers: {
                                "x-requested-with": "XMLHttpRequest",
                                "x-csrf-token": csrfToken,
                            },
                            body: formData,
                        });
                        return await response.json();
                    }""",
                    {"isKyiv": is_kyiv, "city": clean_city, "street": exact_street, "csrfToken": csrf_token}
                )

                logger.info("AJAX response received")
                logger.debug("Response data keys: %s", list(response_data.keys()) if isinstance(response_data, dict) else "not a dict")

                # Step 5: Extract queue number from response
                # Response format: { data: { "1": { group: "2.1", ... }, "2": { ... } }, ... }
                # The building number is the key in the data object
                if not response_data or "data" not in response_data:
                    logger.warning("No 'data' field in response for %s, %s, %s", clean_city, clean_street, building)
                    logger.debug("Full response: %s", response_data)
                    return None

                data = response_data["data"]
                
                if not isinstance(data, dict):
                    logger.warning("Response 'data' is not a dict: %s", type(data))
                    return None
                
                logger.info("Response contains %d building entries", len(data))
                logger.debug("Available buildings in response: %s", list(data.keys())[:20])

                # Try exact match first
                house_data = data.get(building)
                
                # If not found, try normalized building number (e.g., "01" -> "1")
                if not house_data:
                    building_stripped = building.lstrip("0") or "0"
                    house_data = data.get(building_stripped)

                # If still not found, try case-insensitive search
                if not house_data:
                    building_lower = building.lower()
                    for key, value in data.items():
                        if key.lower() == building_lower:
                            house_data = value
                            break

                if not house_data:
                    logger.warning(
                        "Building '%s' not found in response data. Available keys: %s",
                        building, list(data.keys())[:20]
                    )
                    return None

                # Extract group (queue number) from house data
                if isinstance(house_data, dict):
                    group = house_data.get("group")
                    if group:
                        queue_number = str(group)
                        logger.info("Found queue number: %s for building %s", queue_number, building)
                        return queue_number
                    else:
                        logger.warning("No 'group' field in house data: %s", house_data)
                        return None
                else:
                    logger.warning("House data is not a dict: %s", type(house_data))
                    return None

            except PlaywrightTimeoutError as e:
                logger.error("Timeout loading page %s: %s", base_url, e)
                return None
            except Exception as e:
                logger.error("Error getting queue number: %s", e, exc_info=True)
                return None
            finally:
                await browser.close()

    except Exception as e:
        logger.error("Error launching Playwright: %s", e, exc_info=True)
        return None
