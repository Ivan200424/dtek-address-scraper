"""Сервіс для отримання номера черги відключення через парсинг сайтів ДТЕК."""

import logging
import re
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from config.regions import REGIONS

logger = logging.getLogger("services.queue_checker")

# Таймаути для Playwright операцій (в мілісекундах)
NAVIGATION_TIMEOUT = 60000  # 60 секунд
AUTOCOMPLETE_TIMEOUT = 15000  # 15 секунд (збільшено)
WRAPPER_TIMEOUT = 120000  # 120 секунд


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
    
    region_code = REGIONS[region_key].get("code")
    if not region_code:
        logger.error("Відсутній код регіону для: %s", region_key)
        return None
    
    url = f"https://www.dtek-{region_code}.com.ua/ua/shutdowns"
    logger.info("Отримання номера черги для %s, %s, %s (регіон: %s, URL: %s)", 
                city, street, building, region_key, url)
    
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
                
                # Дочекатися завантаження основного wrapper (обробка екрану очікування)
                try:
                    await page.wait_for_selector(".wrapper", state="attached", timeout=WRAPPER_TIMEOUT)
                    logger.info("Wrapper знайдено, форма має бути доступна")
                except PlaywrightTimeoutError:
                    logger.warning("Таймаут очікування .wrapper, продовжуємо")
                
                # Отримати номер черги
                queue_number = await _fill_form_and_get_queue(
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


async def _try_close_popup(page) -> None:
    """Спробувати закрити popup/modal вікно, якщо воно є.
    
    Args:
        page: Playwright page object
    """
    popup_close_selectors = [
        "button.close",
        ".modal .close",
        ".popup .close",
        "[class*='close']",
        "button[aria-label='Close']",
        ".modal-header .close",
        "button.btn-close",
        ".modal button",
        "[data-dismiss='modal']",
    ]
    
    for selector in popup_close_selectors:
        try:
            btn = await page.wait_for_selector(selector, state="visible", timeout=3000)
            if btn:
                await btn.click()
                logger.info("Закрито popup через: %s", selector)
                await page.wait_for_timeout(500)
                return
        except PlaywrightTimeoutError:
            continue
        except Exception as e:
            logger.debug("Помилка при спробі закрити popup через %s: %s", selector, e)
            continue
    
    logger.debug("Popup не знайдено або вже закрито")


async def _fill_autocomplete(page, field_name: str, value: str) -> bool:
    """Заповнити поле з автодоповненням на сайті ДТЕК.
    
    Real DTEK sites use input[name=X] with sibling .autocomplete-items > div dropdowns.
    
    Args:
        page: Playwright page object
        field_name: Назва поля (city, street, house_num)
        value: Значення для введення
        
    Returns:
        True якщо успішно, False якщо помилка
    """
    # Validate field_name to prevent selector injection
    valid_fields = {'city', 'street', 'house_num'}
    if field_name not in valid_fields:
        logger.error("Некоректне ім'я поля: %s. Дозволені: %s", field_name, valid_fields)
        return False
    
    # Альтернативні селектори для полів на випадок іншої DOM-структури
    alternative_selectors = {
        'city': [
            "input[name=city]",
            "input[placeholder*='Почніть вводити']",
            "input[placeholder*='населений пункт']",
            "input[placeholder*='нас. пункт']",
            ".autocomplete input",
            "[class*='city'] input",
            "input[id*='city']",
            "input[id*='locality']",
        ],
        'street': [
            "input[name=street]",
            "input[placeholder*='вулиц']",
            "input[placeholder*='Почніть вводити дан']",
            "[class*='street'] input",
            "input[id*='street']",
        ],
        'house_num': [
            "input[name=house_num]",
            "input[placeholder*='будинку']",
            "input[placeholder*='Номер будинку']",
            "[class*='house'] input",
            "input[id*='house']",
            "input[id*='building']",
        ]
    }
    
    selectors_to_try = alternative_selectors.get(field_name, [f"input[name={field_name}]"])
    
    # Спробувати знайти поле використовуючи альтернативні селектори
    input_selector = None
    for selector in selectors_to_try:
        try:
            element = await page.wait_for_selector(selector, state="attached", timeout=3000)
            if element:
                input_selector = selector
                logger.info("Знайдено поле %s через селектор: %s", field_name, selector)
                break
        except PlaywrightTimeoutError:
            continue
    
    if not input_selector:
        logger.error("Не вдалося знайти поле %s через жоден з селекторів", field_name)
        return False
    
    option_selector = f"{input_selector} ~ .autocomplete-items > div"
    
    try:
        # Очікування та заповнення поля (використання type замість fill для емуляції набору)
        await page.type(input_selector, value, delay=50)
        logger.info("Заповнено поле %s значенням: %s", field_name, value)
        
        # Очікування появи випадаючого списку автодоповнення
        await page.wait_for_selector(option_selector, state="visible", timeout=AUTOCOMPLETE_TIMEOUT)
        logger.info("Випадаючий список автодоповнення для %s з'явився", field_name)
        
        # Клік по першій опції
        await page.click(option_selector, timeout=5000)
        logger.info("Вибрано першу опцію з автодоповнення для %s", field_name)
        
        # Очікування встановлення значення
        # Use Playwright's evaluate with parameterized selector for safety
        await page.wait_for_function(
            "(selector) => !!document.querySelector(selector)?.value",
            input_selector,
            timeout=5000
        )
        logger.info("Значення поля %s встановлено", field_name)
        
        return True
    except PlaywrightTimeoutError as e:
        logger.error("Таймаут при заповненні поля %s: %s", field_name, e)
        return False
    except Exception as e:
        logger.error("Помилка при заповненні поля %s: %s", field_name, e)
        return False


async def _fill_form_and_get_queue(
    page,
    region_key: str,
    city: Optional[str],
    street: str,
    building: str
) -> Optional[str]:
    """Заповнити форму на сайті ДТЕК та отримати номер черги.
    
    Використовує правильні селектори на основі реальної структури сайтів ДТЕК:
    - input[name=city] для міста/населеного пункту
    - input[name=street] для вулиці
    - input[name=house_num] для будинку
    - .autocomplete-items > div для випадаючих списків
    - DisconSchedule.group для отримання номера черги
    """
    try:
        # Спробувати закрити popup (якщо є)
        await _try_close_popup(page)
        
        # Перехоплення AJAX відповіді ПЕРЕД заповненням полів
        ajax_response_data = None

        async def handle_response(response):
            nonlocal ajax_response_data
            if "/ua/ajax" in response.url or "ajax" in response.url.lower():
                try:
                    data = await response.json()
                    ajax_response_data = data
                    logger.info("Перехоплено AJAX: %s", response.url)
                except Exception:
                    pass

        page.on("response", handle_response)
        
        try:
            # Для всіх регіонів, окрім Києва, потрібно заповнити поле міста
            if region_key != "kyiv" and city:
                success = await _fill_autocomplete(page, "city", city)
                if not success:
                    logger.warning("Не вдалося заповнити поле міста")
                    return "невідомо"
                
                # Короткий таймаут після вибору міста (дозволити AJAX оновити залежні поля)
                await page.wait_for_timeout(1000)
            
            # Заповнити вулицю
            success = await _fill_autocomplete(page, "street", street)
            if not success:
                logger.warning("Не вдалося заповнити поле вулиці")
                return "невідомо"
            
            # Короткий таймаут після вибору вулиці (дозволити AJAX оновити залежні поля)
            await page.wait_for_timeout(1000)
            
            # Заповнити будинок
            success = await _fill_autocomplete(page, "house_num", building)
            if not success:
                logger.warning("Не вдалося заповнити поле будинку")
                return "невідомо"
            
            # Після заповнення всіх полів, дочекатися оновлення інформації
            await page.wait_for_timeout(3000)
            
            # Спробувати знайти badge з номером черги на сторінці
            try:
                queue_el = await page.query_selector("text=/[Чч]ерга\\s*\\d/")
                if queue_el:
                    text = await queue_el.text_content()
                    match = re.search(r'(\d+\.?\d*)', text)
                    if match:
                        queue_number = match.group(1)
                        logger.info("Знайдено номер черги через badge: %s", queue_number)
                        return queue_number
            except Exception as e:
                logger.debug("Помилка пошуку badge: %s", e)
            
            # Спробувати отримати номер черги з JavaScript змінної DisconSchedule.group
            try:
                queue_group = await page.evaluate(
                    "() => window.DisconSchedule?.group || null"
                )
                
                if queue_group:
                    logger.info("Отримано значення DisconSchedule.group: %s (type: %s)", queue_group, type(queue_group).__name__)
                    
                    # Handle numeric types directly
                    if isinstance(queue_group, (int, float)):
                        queue_number = str(queue_group)
                        logger.info("Знайдено номер черги (числовий тип): %s", queue_number)
                        return queue_number
                    
                    # Парсинг номера черги з формату "1.1 черга" або подібного
                    # Підтримка десяткових чисел (1.1, 2.2) та цілих чисел (1, 2)
                    match = re.search(r'(\d+(?:\.\d+)?)', str(queue_group))
                    if match:
                        queue_number = match.group(1)
                        logger.info("Знайдено номер черги (через regex): %s", queue_number)
                        return queue_number
                else:
                    logger.warning("DisconSchedule.group не знайдено або порожнє")
            except Exception as e:
                logger.error("Помилка читання DisconSchedule.group: %s", e)
            
            # Спробувати отримати номер черги з перехопленої AJAX відповіді
            if ajax_response_data:
                try:
                    # Шукати в AJAX відповіді поле з номером черги
                    if isinstance(ajax_response_data, dict):
                        for key in ['group', 'queue', 'queue_number', 'черга']:
                            if key in ajax_response_data:
                                queue_value = ajax_response_data[key]
                                if queue_value:
                                    match = re.search(r'(\d+(?:\.\d+)?)', str(queue_value))
                                    if match:
                                        queue_number = match.group(1)
                                        logger.info("Знайдено номер черги через AJAX відповідь: %s", queue_number)
                                        return queue_number
                except Exception as e:
                    logger.debug("Помилка обробки AJAX відповіді: %s", e)
            
            # Альтернативний підхід: перехоплення AJAX відповіді до /ua/ajax
            # Якщо DisconSchedule.group не спрацював, спробуємо знайти інформацію на сторінці
            try:
                page_content = await page.content()
                
                # Шукати патерни типу "1.1 черга", "Черга: 1.1", тощо
                # Підтримка як десяткових (1.1, 2.2), так і цілих чисел (1, 2)
                patterns = [
                    r'(\d+(?:\.\d+)?)\s*черга',
                    r'черга[:\s]+(\d+(?:\.\d+)?)',
                    r'група[:\s]+(\d+(?:\.\d+)?)',
                    r'group[:\s]+(\d+(?:\.\d+)?)',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, page_content, re.IGNORECASE)
                    if match:
                        queue_number = match.group(1)
                        logger.info("Знайдено номер черги через патерн '%s': %s", pattern, queue_number)
                        return queue_number
            except Exception as e:
                logger.error("Помилка пошуку номера черги в контенті сторінки: %s", e)
            
            logger.warning("Не вдалось знайти номер черги")
            return "невідомо"
        finally:
            # Видалити обробник відповідей, щоб уникнути витоку пам'яті
            page.remove_listener("response", handle_response)
        
    except Exception as e:
        logger.error("Помилка при заповненні форми та отриманні черги: %s", e)
        return "невідомо"
