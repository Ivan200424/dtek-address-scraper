"""Queue checker service using form interaction (primary) with AJAX fallback.

This module implements two approaches to get queue numbers:

PRIMARY: Form interaction (like a real user)
1. Navigate to DTEK shutdowns page
2. Fill city autocomplete (for non-Kyiv regions)
3. Fill street autocomplete
4. Extract queue from building list

FALLBACK: AJAX API approach
1. getCity - Search for city by name, returns cityId
2. getStreet - Search for street using cityId, returns exact street name
3. getHomeNum - Get building data using cityId and street, returns queue groups

Based on the working approach from https://github.com/mr-devboy/dtek-monitor
Updated to prioritize form interaction for better reliability.
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config.regions import REGIONS

logger = logging.getLogger("services.queue_checker")

# Timeouts for Playwright operations (milliseconds)
NAVIGATION_TIMEOUT = 60000  # 60 seconds
AJAX_TIMEOUT = 30000  # 30 seconds

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  # seconds
RETRY_BACKOFF_MULTIPLIER = 2

# User-Agent to avoid anti-bot detection
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Prefixes to strip from city and street names
CITY_PREFIXES = ["м. ", "с. ", "смт. ", "с-ще. "]
STREET_PREFIXES = ["вул. ", "просп. ", "пров. ", "пл. ", "б-р. "]

# Autocomplete dropdown selectors (common patterns for jQuery UI and custom implementations)
AUTOCOMPLETE_SELECTORS = [
    '.ui-menu-item:first-child',
    '.ui-autocomplete li:first-child',
    '[role="option"]:first-child',
    '.autocomplete-item:first-child',
    '.suggestion:first-child',
]

# Building select dropdown selector
BUILDING_SELECT_SELECTOR = 'select[name*="building" i], select[name*="home" i], select[id*="building" i], select[id*="home" i]'


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


async def get_city(
    page,
    csrf_token: str,
    city_query: str,
) -> Optional[str]:
    """Search for city and return cityId using DTEK getCity API.
    
    Args:
        page: Playwright page object (already opened with CSRF token)
        csrf_token: CSRF token from the page
        city_query: City name to search for
        
    Returns:
        City ID from DTEK database or None if not found
    """
    clean_city = strip_prefix(city_query, CITY_PREFIXES)
    
    logger.info("Searching for city: '%s'", clean_city)
    
    try:
        response_data = await page.evaluate(
            """async ({ city, csrfToken }) => {
                const formData = new URLSearchParams();
                formData.append("method", "getCity");
                formData.append("data[0][name]", "city");
                formData.append("data[0][value]", city);

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
            {"city": clean_city, "csrfToken": csrf_token}
        )
        
        logger.debug("getCity response: %s", response_data)
        
        # Response format: { data: [{ id: "123", name: "City Name" }, ...] }
        if response_data and "data" in response_data:
            data = response_data["data"]
            if isinstance(data, list) and len(data) > 0:
                # Return the first matching city ID
                city_data = data[0]
                if isinstance(city_data, dict) and "id" in city_data:
                    city_id = str(city_data["id"])
                    logger.info("Found city ID: '%s' for query: '%s'", city_id, clean_city)
                    return city_id
                else:
                    logger.warning("Invalid city data format: %s", city_data)
                    return None
            else:
                logger.warning("No cities found for query: '%s'", clean_city)
                return None
        else:
            logger.warning("Invalid getCity response format")
            return None
            
    except Exception as e:
        logger.error("Error searching for city: %s", e, exc_info=True)
        return None


async def search_street(
    page,
    csrf_token: str,
    region_key: str,
    city: Optional[str],
    street_query: str,
) -> tuple[Optional[str], Optional[str]]:
    """Search for exact street name using DTEK getStreet API.
    
    For non-Kyiv regions, this function:
    1. Calls getCity API to get cityId
    2. Calls getStreet API with cityId to get exact street name
    
    For Kyiv, it directly calls getStreet without city parameter.
    
    Args:
        page: Playwright page object (already opened with CSRF token)
        csrf_token: CSRF token from the page
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        city: City name (can be None for Kyiv)
        street_query: User's street input to search for
        
    Returns:
        Tuple of (exact_street_name, city_id) from DTEK database or (None, None) if not found
    """
    is_kyiv = region_key == "kyiv"
    clean_street = strip_prefix(street_query, STREET_PREFIXES)
    
    # Step 1: For non-Kyiv regions, get cityId first
    city_id = None
    if not is_kyiv and city:
        city_id = await get_city(page, csrf_token, city)
        if not city_id:
            logger.warning("City not found in DTEK database: '%s'", city)
            return None, None
        logger.info("Using city ID: '%s' for street search", city_id)
    
    logger.info("Searching for street: '%s' in city: '%s'", clean_street, city or "Kyiv")
    
    try:
        # Step 2: Call getStreet API with cityId (for non-Kyiv) or without city (for Kyiv)
        response_data = await page.evaluate(
            """async ({ isKyiv, cityId, street, csrfToken }) => {
                const formData = new URLSearchParams();
                formData.append("method", "getStreet");

                let i = 0;
                
                if (!isKyiv && cityId) {
                    formData.append(`data[${i}][name]`, "city");
                    formData.append(`data[${i}][value]`, cityId);
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
            {"isKyiv": is_kyiv, "cityId": city_id, "street": clean_street, "csrfToken": csrf_token}
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
                return exact_street, city_id
            else:
                logger.warning("No streets found for query: '%s'", clean_street)
                # Return None for street but keep city_id for fallback attempt
                return None, city_id
        else:
            logger.warning("Invalid getStreet response format")
            # Return None for street but keep city_id for fallback attempt
            return None, city_id
            
    except Exception as e:
        logger.error("Error searching for street: %s", e, exc_info=True)
        # Return None for both on exception
        return None, None


async def _get_queue_number_form_interaction(
    region_key: str,
    base_url: str,
    city: Optional[str],
    street: str,
    building: str,
) -> Dict[str, Any]:
    """Get queue number by interacting with DTEK form like a real user.
    
    This approach fills in the form on the DTEK shutdowns page exactly like a human would:
    1. Navigate to shutdowns page
    2. Find and fill city autocomplete (for non-Kyiv regions)
    3. Wait for suggestions and click first match
    4. Find and fill street autocomplete
    5. Wait for suggestions and click first match
    6. Extract queue number from building list
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        base_url: Base URL of DTEK website
        city: City name (can be None for Kyiv)
        street: Street name
        building: Building number
        
    Returns:
        Dict with 'queue', 'error', and optionally 'no_retry' keys
    """
    is_kyiv = region_key == "kyiv"
    clean_city = strip_prefix(city, CITY_PREFIXES) if city else None
    clean_street = strip_prefix(street, STREET_PREFIXES)
    
    logger.info(
        "Form interaction: Getting queue for %s, %s, %s (region: %s)",
        clean_city, clean_street, building, region_key
    )
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="uk-UA",
                user_agent=USER_AGENT,
            )
            page = await context.new_page()
            
            try:
                # Step 1: Navigate to shutdowns page
                logger.info("Opening page: %s", base_url)
                await page.goto(base_url, timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
                logger.info("Page loaded successfully")
                
                # Check for suspect HTML
                content = await page.content()
                if len(content) < 1000:
                    logger.warning("Suspect HTML: page content too small (%d bytes)", len(content))
                    return {"queue": None, "error": "Page loaded but content seems incomplete"}
                
                # Step 2: For non-Kyiv regions, find and fill city input
                if not is_kyiv and clean_city:
                    logger.info("Searching for city input field...")
                    
                    # Try to find city input using common selectors
                    city_input = None
                    city_selectors = [
                        'input[name*="city" i]',
                        'input[id*="city" i]',
                        'input[placeholder*="місто" i]',
                        'input[placeholder*="населений" i]',
                    ]
                    
                    for selector in city_selectors:
                        try:
                            city_input = await page.wait_for_selector(selector, timeout=5000)
                            if city_input:
                                logger.info("Found city input with selector: %s", selector)
                                break
                        except Exception:
                            continue
                    
                    if not city_input:
                        logger.warning("City input not found, trying AJAX fallback")
                        return {"queue": None, "error": "City input field not found on page"}
                    
                    # Clear and type city name
                    await city_input.click()
                    await city_input.fill("")
                    await city_input.type(clean_city, delay=100)
                    logger.info("Typed city: %s", clean_city)
                    
                    # Wait for autocomplete dropdown to appear
                    await page.wait_for_timeout(1500)
                    
                    # Try to find and click autocomplete suggestion
                    suggestion_clicked = False
                    for selector in AUTOCOMPLETE_SELECTORS:
                        try:
                            suggestion = await page.wait_for_selector(selector, timeout=3000)
                            if suggestion:
                                await suggestion.click()
                                logger.info("Clicked city suggestion with selector: %s", selector)
                                suggestion_clicked = True
                                break
                        except Exception:
                            continue
                    
                    if not suggestion_clicked:
                        logger.warning("City autocomplete suggestion not found")
                        # Continue anyway, the input might be accepted as-is
                    
                    # Wait for city selection to process
                    await page.wait_for_timeout(1000)
                
                # Step 3: Find and fill street input
                logger.info("Searching for street input field...")
                
                street_input = None
                street_selectors = [
                    'input[name*="street" i]',
                    'input[id*="street" i]',
                    'input[placeholder*="вулиц" i]',
                    'input[placeholder*="street" i]',
                ]
                
                for selector in street_selectors:
                    try:
                        street_input = await page.wait_for_selector(selector, timeout=5000)
                        if street_input:
                            logger.info("Found street input with selector: %s", selector)
                            break
                    except Exception:
                        continue
                
                if not street_input:
                    logger.warning("Street input not found, trying AJAX fallback")
                    return {"queue": None, "error": "Street input field not found on page"}
                
                # Clear and type street name
                await street_input.click()
                await street_input.fill("")
                await street_input.type(clean_street, delay=100)
                logger.info("Typed street: %s", clean_street)
                
                # Wait for autocomplete dropdown to appear
                await page.wait_for_timeout(1500)
                
                # Try to find and click autocomplete suggestion
                suggestion_clicked = False
                for selector in AUTOCOMPLETE_SELECTORS:
                    try:
                        suggestion = await page.wait_for_selector(selector, timeout=3000)
                        if suggestion:
                            await suggestion.click()
                            logger.info("Clicked street suggestion with selector: %s", selector)
                            suggestion_clicked = True
                            break
                    except Exception:
                        continue
                
                if not suggestion_clicked:
                    logger.warning("Street autocomplete suggestion not found")
                    # Continue anyway
                
                # Wait for street selection to process and building list to load
                await page.wait_for_timeout(2000)
                
                # Step 4: Try to find the building in the page and extract queue number
                logger.info("Searching for building: %s", building)
                
                # Try to extract building data from the page
                # The exact structure depends on how DTEK displays results
                # We'll try multiple approaches
                
                # Approach 1: Look for building in a select dropdown
                building_select = None
                try:
                    building_select = await page.wait_for_selector(BUILDING_SELECT_SELECTOR, timeout=3000)
                except Exception:
                    pass
                
                if building_select:
                    logger.info("Found building select dropdown")
                    # Get all options from the building select dropdown
                    options_data = await page.evaluate('''() => {
                        const selector = 'select[name*="building" i], select[name*="home" i], select[id*="building" i], select[id*="home" i]';
                        const select = document.querySelector(selector);
                        if (!select) return null;
                        
                        const options = Array.from(select.options).map(opt => ({
                            value: opt.value,
                            text: opt.textContent.trim(),
                        }));
                        
                        return options;
                    }''')
                    
                    if options_data:
                        logger.debug("Found %d building options", len(options_data))
                        # Try to find building and extract queue from option text
                        # Format might be like "1 - черга 3.1" or "буд. 1 (3.1)"
                        for option in options_data:
                            option_text = option.get('text', '')
                            option_value = option.get('value', '')
                            
                            # Check if this option matches our building
                            # Use exact match for option_value, and word boundary match for option_text
                            # This prevents partial matches like '1' matching '10', '11', etc.
                            if building == option_value:
                                logger.info("Found building by value match: %s", option_text)
                                # Try to extract queue number from text
                                queue_match = re.search(r'(\d+\.\d+)', option_text)
                                if queue_match:
                                    queue_number = queue_match.group(1)
                                    logger.info("Extracted queue number from form: %s", queue_number)
                                    return {"queue": queue_number, "error": None}
                            # Also check if building appears as a word in option text (with word boundaries)
                            elif re.search(rf'\b{re.escape(building)}\b', option_text):
                                logger.info("Found building by text match: %s", option_text)
                                queue_match = re.search(r'(\d+\.\d+)', option_text)
                                if queue_match:
                                    queue_number = queue_match.group(1)
                                    logger.info("Extracted queue number from form: %s", queue_number)
                                    return {"queue": queue_number, "error": None}
                
                # Approach 2: Look for building data in page text/elements
                page_text = await page.evaluate('() => document.body.innerText')
                logger.debug("Page text length: %d", len(page_text))
                
                # Try to find building and queue in page text
                # This is a fallback if we can't interact with form elements
                # Look for patterns like "будинок 1 - черга 3.1" or "1 (3.1)"
                # Escape building number to handle special regex characters
                escaped_building = re.escape(building)
                patterns = [
                    rf'{escaped_building}\s*[-–—]\s*черга\s*(\d+\.\d+)',
                    rf'{escaped_building}\s*\((\d+\.\d+)\)',
                    rf'будинок\s*{escaped_building}.*?(\d+\.\d+)',
                    rf'буд\.\s*{escaped_building}.*?(\d+\.\d+)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        queue_number = match.group(1)
                        logger.info("Extracted queue from page text: %s", queue_number)
                        return {"queue": queue_number, "error": None}
                
                logger.warning("Could not extract queue number from form interaction")
                return {"queue": None, "error": "Building not found in form results"}
                
            except PlaywrightTimeoutError as e:
                logger.error("Timeout during form interaction: %s", e)
                return {"queue": None, "error": f"Timeout during form interaction"}
            except Exception as e:
                logger.error("Error during form interaction: %s", e, exc_info=True)
                return {"queue": None, "error": f"Error during form interaction: {str(e)}"}
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error("Error launching Playwright for form interaction: %s", e, exc_info=True)
        return {"queue": None, "error": f"Failed to launch browser: {str(e)}"}


async def get_queue_number(
    region_key: str,
    city: Optional[str],
    street: str,
    building: str,
) -> Dict[str, Any]:
    """Get queue number for address using form interaction (primary) with AJAX fallback.
    
    This function first tries to interact with the DTEK form like a real user:
    1. Navigate to shutdowns page
    2. Fill city autocomplete (for non-Kyiv)
    3. Fill street autocomplete
    4. Extract queue from building list
    
    If form interaction fails, it falls back to the AJAX API approach:
    1. Extract CSRF token
    2. Call getCity -> getStreet -> getHomeNum API chain
    3. Parse JSON response
    
    Args:
        region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
        city: City name (can be None for Kyiv)
        street: Street name
        building: Building number
        
    Returns:
        Dict with 'queue' and 'error' keys:
        - {"queue": "3.1", "error": None} on success
        - {"queue": None, "error": "Error description"} on failure
    """
    if region_key not in REGIONS:
        error_msg = f"Unknown region: {region_key}"
        logger.error(error_msg)
        return {"queue": None, "error": error_msg}

    base_url = REGIONS[region_key]["url"]

    logger.info(
        "Getting queue number for %s, %s, %s (region: %s)",
        city, street, building, region_key
    )
    
    # First, try form interaction approach (primary method)
    logger.info("Trying form interaction approach...")
    form_result = await _get_queue_number_form_interaction(region_key, base_url, city, street, building)
    
    if form_result["queue"] is not None:
        logger.info("Form interaction succeeded, queue: %s", form_result["queue"])
        return form_result
    
    # If form interaction failed, log and try AJAX fallback
    logger.warning("Form interaction failed: %s. Trying AJAX fallback...", form_result.get("error"))
    
    # Retry loop for AJAX approach
    for attempt in range(MAX_RETRIES):
        try:
            result = await _get_queue_number_attempt(region_key, base_url, city, street, building)
            if result["queue"] is not None or result.get("no_retry"):
                return result
            
            # If we got an error but should retry
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_RETRY_DELAY * (RETRY_BACKOFF_MULTIPLIER ** attempt)
                logger.warning(
                    "AJAX attempt %d/%d failed: %s. Retrying in %.1f seconds...",
                    attempt + 1, MAX_RETRIES, result["error"], delay
                )
                await asyncio.sleep(delay)
            else:
                # Last attempt failed
                logger.error("All %d AJAX attempts failed. Last error: %s", MAX_RETRIES, result["error"])
                return result
                
        except Exception as e:
            error_msg = f"Unexpected error on AJAX attempt {attempt + 1}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_RETRY_DELAY * (RETRY_BACKOFF_MULTIPLIER ** attempt)
                logger.warning("Retrying in %.1f seconds...", delay)
                await asyncio.sleep(delay)
            else:
                return {"queue": None, "error": error_msg}
    
    return {"queue": None, "error": "All methods failed (form interaction + AJAX)"}


async def _get_queue_number_attempt(
    region_key: str,
    base_url: str,
    city: Optional[str],
    street: str,
    building: str,
) -> Dict[str, Any]:
    """Single attempt to get queue number.
    
    Returns:
        Dict with 'queue', 'error', and optionally 'no_retry' keys
    """
    
    is_kyiv = region_key == "kyiv"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="uk-UA",
                user_agent=USER_AGENT,
            )
            page = await context.new_page()

            try:
                # Step 1: Open the shutdowns page and wait for full load
                logger.info("Opening page: %s", base_url)
                await page.goto(base_url, timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
                logger.info("Page loaded successfully")
                
                # Check for suspect HTML (too small response, missing expected elements)
                content = await page.content()
                if len(content) < 1000:
                    logger.warning("Suspect HTML: page content too small (%d bytes)", len(content))
                    return {"queue": None, "error": "Page loaded but content seems incomplete"}

                # Step 2: Extract CSRF token
                csrf_token = await page.evaluate(
                    "() => document.querySelector('meta[name=\"csrf-token\"]')?.getAttribute('content')"
                )
                
                if not csrf_token:
                    logger.error("CSRF token not found on page")
                    return {"queue": None, "error": "CSRF token not found on page"}

                logger.info("CSRF token obtained")

                # Step 3: Resolve exact street name and cityId using getCity -> getStreet API chain
                # This ensures we use the correct IDs from DTEK's database
                exact_street, city_id = await search_street(page, csrf_token, region_key, city, street)
                
                # Check if city lookup failed for non-Kyiv regions
                if not is_kyiv and city and city_id is None:
                    logger.error("City not found in DTEK database: '%s'", city)
                    return {"queue": None, "error": f"City '{city}' not found in DTEK database", "no_retry": True}
                
                # Track if street was found in DTEK database
                street_not_found = exact_street is None
                
                # If street resolution failed, fall back to cleaned user input
                if street_not_found:
                    logger.warning("Street resolution failed, using cleaned user input")
                    exact_street = strip_prefix(street, STREET_PREFIXES)
                
                logger.info(
                    "Using street name: '%s' (cityId: %s) (from user input: '%s')",
                    exact_street, city_id or "N/A", street
                )
                
                # Step 4: Make AJAX request using page.evaluate (same context as browser)
                # For non-Kyiv regions, use cityId instead of city name
                response_data = await page.evaluate(
                    """async ({ isKyiv, cityId, street, csrfToken }) => {
                        const formData = new URLSearchParams();
                        formData.append("method", "getHomeNum");

                        // Use dynamic counter for data[] indices
                        let i = 0;
                        
                        if (!isKyiv && cityId) {
                            formData.append(`data[${i}][name]`, "city");
                            formData.append(`data[${i}][value]`, cityId);
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
                    {"isKyiv": is_kyiv, "cityId": city_id, "street": exact_street, "csrfToken": csrf_token}
                )

                logger.info("AJAX response received")
                logger.debug("Response data keys: %s", list(response_data.keys()) if isinstance(response_data, dict) else "not a dict")

                # Step 5: Extract queue number from response
                # Response format: { data: { "1": { group: "2.1", ... }, "2": { ... } }, ... }
                # The building number is the key in the data object
                if not response_data or "data" not in response_data:
                    logger.warning("No 'data' field in response for city: %s, street: %s, building: %s", city, exact_street, building)
                    logger.debug("Full response: %s", response_data)
                    if street_not_found:
                        return {"queue": None, "error": "Street not found in DTEK database", "no_retry": True}
                    return {"queue": None, "error": "No data returned from DTEK API"}

                data = response_data["data"]
                
                if not isinstance(data, dict):
                    logger.warning("Response 'data' is not a dict: %s", type(data))
                    return {"queue": None, "error": "Invalid response format from DTEK API"}
                
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
                    return {"queue": None, "error": f"Building {building} not found at this address", "no_retry": True}

                # Extract group (queue number) from house data
                if isinstance(house_data, dict):
                    group = house_data.get("group")
                    if group:
                        queue_number = str(group)
                        logger.info("Found queue number: %s for building %s", queue_number, building)
                        return {"queue": queue_number, "error": None}
                    else:
                        logger.warning("No 'group' field in house data: %s", house_data)
                        return {"queue": None, "error": "No queue information available for this building", "no_retry": True}
                else:
                    logger.warning("House data is not a dict: %s", type(house_data))
                    return {"queue": None, "error": "Invalid building data format"}

            except PlaywrightTimeoutError as e:
                logger.error("Timeout loading page %s: %s", base_url, e)
                return {"queue": None, "error": f"Timeout loading DTEK website"}
            except Exception as e:
                logger.error("Error getting queue number: %s", e, exc_info=True)
                return {"queue": None, "error": f"Error during page interaction: {str(e)}"}
            finally:
                await browser.close()

    except Exception as e:
        logger.error("Error launching Playwright: %s", e, exc_info=True)
        return {"queue": None, "error": f"Failed to launch browser: {str(e)}"}
