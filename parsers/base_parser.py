"""Базовий клас парсера сайтів ДТЕК."""

import logging
import re
from abc import ABC, abstractmethod

from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential


class BaseParser(ABC):
    """Базовий клас для всіх парсерів сайтів ДТЕК."""

    def __init__(self, region_key: str, url: str) -> None:
        """Ініціалізація парсера.

        Args:
            region_key: Ключ регіону.
            url: URL сторінки відключень.
        """
        self.region_key = region_key
        self.url = url
        self.logger = logging.getLogger(f"parser.{region_key}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def fetch_page(self) -> tuple[str, list[dict]]:
        """Відкрити сторінку через async_playwright і повернути HTML та перехоплені API відповіді.

        Returns:
            Кортеж (html, api_responses).
        """
        api_responses: list[dict] = []

        async def handle_response(response) -> None:
            """Перехоплення API відповідей."""
            url_lower = response.url.lower()
            if "api" in url_lower or "shutdown" in url_lower:
                try:
                    data = await response.json()
                    api_responses.append({"url": response.url, "data": data})
                except Exception:
                    pass

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()
                page.set_default_timeout(30000)

                # Перехоплення API запитів
                page.on("response", handle_response)

                await page.goto(self.url, wait_until="networkidle")
                # Додаткове очікування для JavaScript
                await page.wait_for_timeout(2000)
                html = await page.content()
                return html, api_responses
            finally:
                await browser.close()

    @abstractmethod
    async def parse_outages(self) -> list[dict]:
        """Розпарсити відключення та повернути список словників.

        Returns:
            Список словників з інформацією про відключення:
            {
                "outage_type": "emergency" | "planned",
                "affected_area": str,
                "start_time": datetime | None,
                "end_time": datetime | None,
                "description": str,
                "raw_data": dict,
            }
        """
        pass

    @staticmethod
    def normalize_address(address: str) -> str:
        """Нормалізувати адресу для порівняння.

        1. Привести до нижнього регістру
        2. strip()
        3. Замінити скорочення на повні форми
        4. Видалити множинні пробіли
        5. Видалити зайві символи

        Args:
            address: Вхідна адреса.

        Returns:
            Нормалізована адреса.
        """
        result = address.lower().strip()

        # Замінити скорочення (тільки з крапкою, щоб уникнути хибних збігів)
        replacements = [
            (r"(?<!\w)вул\.\s*", "вулиця "),
            (r"(?<!\w)просп\.\s*", "проспект "),
            (r"(?<!\w)пр-т\.\s*", "проспект "),
            (r"(?<!\w)пр\.\s*", "проспект "),
            (r"(?<!\w)бул\.\s*", "бульвар "),
            (r"(?<!\w)б-р\.\s*", "бульвар "),
            (r"(?<!\w)пров\.\s*", "провулок "),
            (r"(?<!\w)пл\.\s*", "площа "),
            (r"(?<!\w)м\.\s*", "місто "),
            (r"(?<!\w)с-ще\.\s*", "селище "),
            (r"(?<!\w)смт\.\s*", "смт "),
            (r"(?<!\w)с\.\s*", "село "),
        ]

        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)

        # Видалити множинні пробіли
        result = re.sub(r"\s+", " ", result)

        # Залишити літери, цифри, пробіли, дефіси, коми
        result = re.sub(r"[^\w\s\-,]", "", result)

        return result.strip()
