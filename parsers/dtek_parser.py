"""DTEK website parser using AJAX approach."""

import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config.regions import REGIONS

logger = logging.getLogger("parsers.dtek_parser")

NAVIGATION_TIMEOUT = 60000  # 60 seconds


class DtekParser:
    """Parser for DTEK power outage websites."""

    @staticmethod
    def normalize_address(address: str) -> str:
        """Normalize address for comparison.
        
        Args:
            address: Address string
            
        Returns:
            Normalized address
        """
        # Convert to lowercase
        normalized = address.lower().strip()
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Normalize prefixes
        replacements = {
            'вулиця': 'вул.',
            'проспект': 'просп.',
            'провулок': 'пров.',
            'площа': 'пл.',
            'бульвар': 'б-р.',
            'місто': 'м.',
            'село': 'с.',
            'селище': 'смт.',
        }
        
        for full, short in replacements.items():
            normalized = normalized.replace(full, short)
        
        return normalized

    async def parse_outages(self, region_key: str) -> List[Dict[str, Any]]:
        """Parse outages from DTEK website.
        
        Args:
            region_key: Region key (kyiv, kyiv_region, dnipro, odesa)
            
        Returns:
            List of outage dictionaries
        """
        if region_key not in REGIONS:
            logger.error("Unknown region: %s", region_key)
            return []

        url = REGIONS[region_key]["url"]
        logger.info("Parsing outages from: %s", url)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    locale="uk-UA",
                )
                page = await context.new_page()

                try:
                    # Open the page
                    await page.goto(url, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                    logger.info("Page loaded: %s", url)

                    # Wait for content to load
                    await page.wait_for_timeout(3000)

                    # Try to extract outages from the page
                    outages = await self._extract_outages_from_page(page, region_key, url)
                    
                    logger.info("Parsed %d outages from %s", len(outages), region_key)
                    return outages

                except PlaywrightTimeoutError as e:
                    logger.error("Timeout loading page %s: %s", url, e)
                    return []
                except Exception as e:
                    logger.error("Error parsing %s: %s", url, e, exc_info=True)
                    return []
                finally:
                    await browser.close()

        except Exception as e:
            logger.error("Failed to launch browser: %s", e)
            return []

    async def _extract_outages_from_page(
        self, page, region_key: str, url: str
    ) -> List[Dict[str, Any]]:
        """Extract outage information from page.
        
        Args:
            page: Playwright page object
            region_key: Region key
            url: Source URL
            
        Returns:
            List of outage dictionaries
        """
        outages = []

        try:
            # Get page content
            content = await page.content()

            # Try different selectors for outage information
            # This is a placeholder - actual implementation depends on DTEK site structure
            
            # Look for emergency outages (аварійні відключення)
            emergency_selectors = [
                ".emergency-outage",
                ".outage-emergency",
                "[class*='emergency']",
                "text=/аварійн/i",
            ]

            for selector in emergency_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.text_content()
                        if text and "відключ" in text.lower():
                            outage = {
                                "outage_type": "emergency",
                                "affected_area": text.strip(),
                                "start_time": None,
                                "end_time": None,
                                "description": None,
                                "source_url": url,
                                "raw_data": {"text": text.strip()},
                            }
                            outages.append(outage)
                except Exception:
                    continue

            # Look for planned outages (планові відключення)
            planned_selectors = [
                ".planned-outage",
                ".outage-planned",
                "[class*='planned']",
                "text=/планов/i",
            ]

            for selector in planned_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.text_content()
                        if text and "відключ" in text.lower():
                            outage = {
                                "outage_type": "planned",
                                "affected_area": text.strip(),
                                "start_time": None,
                                "end_time": None,
                                "description": None,
                                "source_url": url,
                                "raw_data": {"text": text.strip()},
                            }
                            outages.append(outage)
                except Exception:
                    continue

            # Try to extract structured data from JSON-LD or data attributes
            try:
                json_ld = await page.evaluate(
                    """() => {
                        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                        return Array.from(scripts).map(s => s.textContent);
                    }"""
                )
                # Parse JSON-LD if available
                # This would need to be adapted based on actual DTEK site structure
            except Exception:
                pass

        except Exception as e:
            logger.error("Error extracting outages: %s", e)

        return outages
