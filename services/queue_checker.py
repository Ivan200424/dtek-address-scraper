"""Сервіс для отримання номера черги відключення через парсинг сайтів ДТЕК."""

import asyncio
import logging
import re
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config.regions import REGIONS

logger = logging.getLogger("services.queue_checker")

# Таймаути для Playwright операцій (в мілісекундах)
NAVIGATION_TIMEOUT = 30000  # 30 секунд
AUTOCOMPLETE_TIMEOUT = 10000  # 10 секунд


async def get_queue_number(
    region_key: str,
    city: Optional[str],
    street: str,
    building: str
) -> Optional[str]:
    """Отримати номер черги для адреси через парсинг сайту ДТЕК.
    
    Args:
        region_key: Ключ регіону (kyiv, kyiv_region, dnipro, odesa)
        city: Назва населеного пункту (може бути None для Києва)
        street: Назва вулиці
        building: Номер будинку
    
    Returns:
        Номер черги як рядок або None якщо не вдалось отримати
    """
    if region_key not in REGIONS:
        logger.error("Невідомий регіон: %s", region_key)
        return None
    
    url = REGIONS[region_key]["url"]
    logger.info("Отримання номера черги для %s, %s, %s (регіон: %s)", city, street, building, region_key)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="uk-UA"
            )
            page = await context.new_page()
            
            try:
                # Відкрити сторінку з відключеннями
                await page.goto(url, timeout=NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
                logger.info("Сторінка %s завантажена", url)
                
                # Спробувати знайти форму пошуку адреси
                # Різні сайти ДТЕК можуть мати різні селектори
                queue_number = await _extract_queue_for_region(
                    page, region_key, city, street, building
                )
                
                return queue_number
                
            except PlaywrightTimeoutError as e:
                logger.error("Таймаут при завантаженні сторінки %s: %s", url, e)
                return None
            except Exception as e:
                logger.error("Помилка при отриманні номера черги: %s", e)
                return None
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error("Помилка при запуску Playwright: %s", e)
        return None


async def _extract_queue_for_region(
    page,
    region_key: str,
    city: Optional[str],
    street: str,
    building: str
) -> Optional[str]:
    """Витягнути номер черги з сторінки для конкретного регіону.
    
    Кожен сайт ДТЕК має свій власний інтерфейс, тому потрібна окрема логіка.
    """
    try:
        # Загальний підхід: шукаємо форму з полями для адреси
        # Більшість сайтів ДТЕК мають структуру:
        # - Поле для населеного пункту (якщо не Київ)
        # - Поле для вулиці
        # - Поле для будинку
        # - Кнопка пошуку
        # - Результат з номером черги
        
        # Дочекатись завантаження форми
        await page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
        
        # Для регіональних сайтів (не Київ) потрібно спочатку заповнити поле міста/населеного пункту
        if region_key != "kyiv" and city:
            city_selectors = [
                "input[placeholder*='населений пункт']",
                "input[placeholder*='Оберіть населений пункт']",
                "input[placeholder*='місто']",
                "input[name*='city']",
                "input[id*='city']",
                "[class*='autocomplete'] input",
                "[role='combobox']",
            ]
            
            city_input = None
            for selector in city_selectors:
                try:
                    city_input = await page.wait_for_selector(selector, timeout=5000)
                    if city_input:
                        logger.info("Знайдено поле міста за селектором: %s", selector)
                        break
                except Exception:
                    continue
            
            if city_input:
                # Ввести назву міста та дочекатись автодоповнення
                await city_input.fill(city)
                await page.wait_for_timeout(2000)  # Дочекатись автодоповнення
                
                # Спробувати вибрати з автодоповнення
                try:
                    # Натиснути першу опцію в автодоповненні
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(1000)
                except Exception:
                    pass
            else:
                logger.warning("Не знайдено поле для вводу міста/населеного пункту")
        
        # Спробувати різні можливі селектори для форми пошуку вулиці
        possible_selectors = [
            "input[placeholder*='Оберіть вулицю']",
            "input[placeholder*='вулиця']",
            "input[name*='street']",
            "input[id*='street']",
            ".search-form input",
            "#address-search input",
            "[class*='autocomplete'] input",
            "[class*='select'] input",
            "[role='combobox']",
        ]
        
        street_input = None
        for selector in possible_selectors:
            try:
                street_input = await page.wait_for_selector(selector, timeout=5000)
                if street_input:
                    logger.info("Знайдено поле вулиці за селектором: %s", selector)
                    break
            except Exception:
                continue
        
        if not street_input:
            logger.warning("Не знайдено поле для вводу вулиці на сторінці")
            return "невідомо"
        
        # Ввести вулицю та дочекатись автодоповнення
        await street_input.fill(street)
        await page.wait_for_timeout(2000)  # Дочекатись автодоповнення
        
        # Спробувати вибрати з автодоповнення
        try:
            # Натиснути першу опцію в автодоповненні
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        
        # Знайти поле будинку
        building_selectors = [
            "input[placeholder*='будинок']",
            "input[placeholder*='будівля']",
            "input[name*='building']",
            "input[id*='building']"
        ]
        
        building_input = None
        for selector in building_selectors:
            try:
                building_input = await page.wait_for_selector(selector, timeout=5000)
                if building_input:
                    logger.info("Знайдено поле будинку за селектором: %s", selector)
                    break
            except Exception:
                continue
        
        if building_input:
            await building_input.fill(building)
            await page.wait_for_timeout(1000)
        
        # Натиснути кнопку пошуку
        search_button_selectors = [
            "button[type='submit']",
            "button:has-text('Знайти')",
            "button:has-text('Пошук')",
            ".search-button",
            "#search-btn"
        ]
        
        for selector in search_button_selectors:
            try:
                await page.click(selector, timeout=5000)
                logger.info("Натиснуто кнопку пошуку за селектором: %s", selector)
                break
            except Exception:
                continue
        
        # Дочекатись результату
        await page.wait_for_timeout(3000)
        
        # Шукаємо номер черги в результатах
        queue_patterns = [
            "черга",
            "група",
            "group",
            "queue"
        ]
        
        # Отримати весь текст сторінки
        page_text = await page.inner_text("body")
        
        # Шукати номер черги в тексті
        for pattern in queue_patterns:
            # Шукаємо патерни типу "Черга: 1.1" або "Група 2.2" тощо
            # Підтримуємо як цілі числа (1, 2), так і дробові (1.1, 2.2)
            match = re.search(rf"{pattern}[:\s]+(\d+\.?\d*)", page_text, re.IGNORECASE)
            if match:
                queue_num = match.group(1)
                logger.info("Знайдено номер черги: %s", queue_num)
                return queue_num
        
        # Якщо не знайшли специфічний патерн, шукаємо просто цифри після ключових слів
        logger.warning("Не вдалось знайти номер черги на сторінці")
        return "невідомо"
        
    except Exception as e:
        logger.error("Помилка при витягуванні номера черги: %s", e)
        return "невідомо"
