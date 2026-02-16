"""Сервіс порівняння адрес з зонами відключень."""

import re

from parsers.base_parser import BaseParser


class AddressMatcher:
    """Клас для перевірки збігу адрес користувачів з зонами відключень."""

    @staticmethod
    def check_match(user_normalized_address: str, outage_affected_area: str) -> bool:
        """Перевірити чи адреса користувача потрапляє в зону відключення.

        Алгоритм:
        1. Нормалізувати обидві адреси.
        2. Перевірити чи назва вулиці з адреси користувача міститься в зоні відключення.
        3. Якщо вулиця збігається — перевірити номер будинку.
        4. Повернути True/False.

        Args:
            user_normalized_address: Нормалізована адреса користувача.
            outage_affected_area: Текст зони відключення.

        Returns:
            True якщо адреса потрапляє в зону відключення.
        """
        normalized_area = BaseParser.normalize_address(outage_affected_area)

        # Витягнути назву вулиці з адреси користувача
        street = AddressMatcher.extract_street_name(user_normalized_address)
        if not street:
            return False

        # Перевірити чи вулиця є в зоні відключення
        if street not in normalized_area:
            return False

        # Витягнути номер будинку з адреси користувача
        building = AddressMatcher.extract_building_number(user_normalized_address)
        if not building:
            # Якщо номер будинку не вказано — збіг по вулиці
            return True

        # Перевірити збіг номера будинку
        # Спробувати знайти конкретні будинки або діапазони в зоні відключення
        area_buildings = AddressMatcher._extract_buildings_from_area(normalized_area, street)

        if not area_buildings:
            # Якщо будинки не вказані в зоні — збіг по вулиці
            return True

        # Перевірити чи будинок користувача є в списку
        building_lower = building.lower().strip()
        for area_building in area_buildings:
            if building_lower == area_building.lower().strip():
                return True

        return False

    @staticmethod
    def extract_street_name(address: str) -> str:
        """Витягнути назву вулиці з повної адреси.

        Args:
            address: Нормалізована адреса.

        Returns:
            Назва вулиці.
        """
        # Видалити типові префікси
        prefixes = ["вулиця", "проспект", "бульвар", "провулок", "площа", "шосе"]

        parts = address.split(",")
        # Шукаємо частину з назвою вулиці (зазвичай друга частина після міста)
        for part in parts:
            part = part.strip()
            for prefix in prefixes:
                if prefix in part:
                    # Повернути назву без префікса
                    name = part.replace(prefix, "").strip()
                    if name:
                        return name

        # Якщо префікс не знайдено — повернути другу частину
        if len(parts) >= 2:
            return parts[1].strip()

        return address.strip()

    @staticmethod
    def extract_building_number(address: str) -> str:
        """Витягнути номер будинку з адреси.

        Args:
            address: Нормалізована адреса.

        Returns:
            Номер будинку або порожній рядок.
        """
        parts = address.split(",")
        if len(parts) >= 3:
            return parts[-1].strip()

        # Спробувати знайти номер в кінці адреси
        match = re.search(r"(\d+[а-яА-Яa-zA-Z]?)\s*$", address)
        if match:
            return match.group(1)

        return ""

    @staticmethod
    def parse_building_range(range_str: str) -> list[str]:
        """Розпарсити діапазон будинків.

        '1-10' → ['1','2','3',...,'10']
        '1, 3, 5' → ['1','3','5']
        '1а, 2, 3б' → ['1а','2','3б']

        Args:
            range_str: Рядок з номерами будинків.

        Returns:
            Список номерів будинків.
        """
        buildings: list[str] = []

        # Розбити по комі
        parts = [p.strip() for p in range_str.split(",") if p.strip()]

        for part in parts:
            # Перевірити чи це діапазон (наприклад, 1-10)
            range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2))
                buildings.extend(str(i) for i in range(start, end + 1))
            else:
                buildings.append(part)

        return buildings

    @staticmethod
    def _extract_buildings_from_area(area: str, street: str) -> list[str]:
        """Витягнути номери будинків з тексту зони відключення для конкретної вулиці.

        Args:
            area: Нормалізований текст зони відключення.
            street: Назва вулиці.

        Returns:
            Список номерів будинків.
        """
        buildings: list[str] = []

        # Знайти частину тексту після назви вулиці
        idx = area.find(street)
        if idx < 0:
            return buildings

        after_street = area[idx + len(street):]

        # Шукаємо номери будинків після назви вулиці
        # Наприклад: "вулиця Хрещатик 1, 3, 5-10, 12а"
        building_match = re.match(r"[\s,:]*([0-9а-яА-Яa-zA-Z\s,\-]+)", after_street)
        if building_match:
            buildings_str = building_match.group(1).strip()
            # Зупинитись на наступному слові (назва іншої вулиці)
            end_match = re.search(r"[а-яА-Яa-zA-Z]{3,}", buildings_str)
            if end_match:
                buildings_str = buildings_str[:end_match.start()].strip().rstrip(",").strip()

            if buildings_str:
                buildings = AddressMatcher.parse_building_range(buildings_str)

        return buildings

    @staticmethod
    def find_matching_addresses(
        db_addresses: list, outage_affected_area: str
    ) -> list:
        """Знайти всі адреси з БД що потрапляють в зону відключення.

        Args:
            db_addresses: Список адрес з БД.
            outage_affected_area: Текст зони відключення.

        Returns:
            Список адрес що збігаються.
        """
        matching = []
        for addr in db_addresses:
            normalized = addr.get("normalized_address") or BaseParser.normalize_address(
                addr.get("full_address", "")
            )
            if AddressMatcher.check_match(normalized, outage_affected_area):
                matching.append(addr)
        return matching
