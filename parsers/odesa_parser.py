"""Парсер аварійних відключень ДТЕК Одеські електромережі."""

from parsers.base_parser import BaseParser
from config.regions import REGIONS


class OdesaParser(BaseParser):
    """Парсер для ДТЕК Одеські електромережі (Одеська область)."""

    def __init__(self) -> None:
        """Ініціалізація парсера для Одеської області."""
        region = REGIONS["odesa"]
        super().__init__("odesa", region["url"])

    async def parse_outages(self) -> list[dict]:
        """Розпарсити відключення для Одеської області.

        Returns:
            Список відключень у стандартному форматі.
        """
        outages: list[dict] = []

        try:
            html, api_responses = await self.fetch_page()

            # Спробувати використати перехоплені API відповіді
            if api_responses:
                for api_resp in api_responses:
                    try:
                        data = api_resp.get("data")
                        parsed = self._parse_api_data(data)
                        outages.extend(parsed)
                    except Exception as e:
                        self.logger.warning(
                            "Помилка парсингу API відповіді: %s", e
                        )

            # Якщо API не дав результатів — парсити HTML
            if not outages:
                outages = self._parse_html(html)

            self.logger.info(
                "Знайдено %d відключень для Одеси", len(outages)
            )

        except Exception as e:
            self.logger.error("Помилка парсингу Одеса: %s", e)

        return outages

    def _parse_api_data(self, data) -> list[dict]:
        """Розпарсити дані з API відповіді.

        Args:
            data: JSON дані з API.

        Returns:
            Список відключень.

        Note:
            Структура API може змінюватись — потрібно оновити після аналізу реальних даних.
        """
        outages: list[dict] = []

        if not data:
            return outages

        try:
            items = data if isinstance(data, list) else data.get("data", data.get("items", []))

            if not isinstance(items, list):
                return outages

            for item in items:
                try:
                    outage = {
                        "outage_type": item.get("type", "emergency"),
                        "affected_area": item.get("address", item.get("area", str(item))),
                        "start_time": None,
                        "end_time": None,
                        "description": item.get("description", item.get("reason", "")),
                        "raw_data": item,
                    }
                    outages.append(outage)
                except Exception as e:
                    self.logger.warning("Помилка обробки елементу API: %s", e)
        except Exception as e:
            self.logger.warning("Помилка парсингу API даних: %s", e)

        return outages

    def _parse_html(self, html: str) -> list[dict]:
        """Розпарсити HTML сторінку відключень.

        Args:
            html: HTML вміст сторінки.

        Returns:
            Список відключень.

        Note:
            Селектори потрібно оновити після аналізу реальної структури сайту ДТЕК.
        """
        outages: list[dict] = []

        try:
            if "аварійн" in html.lower() or "відключен" in html.lower():
                self.logger.info(
                    "HTML містить інформацію про відключення, "
                    "потрібно оновити CSS селектори для точного парсингу"
                )

            self.logger.debug("HTML довжина: %d символів", len(html))

        except Exception as e:
            self.logger.error("Помилка парсингу HTML: %s", e)

        return outages
