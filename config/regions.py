"""Конфігурація регіонів ДТЕК."""

# Регіони ДТЕК з URL-адресами сайтів
REGIONS: dict[str, dict[str, str]] = {
    "kyiv": {
        "name": "Київ",
        "url": "https://www.dtek-kem.com.ua/ua/shutdowns",
        "code": "kem",
        "company": "ДТЕК Київські електромережі",
    },
    "kyiv_region": {
        "name": "Київська область",
        "url": "https://www.dtek-krem.com.ua/ua/shutdowns",
        "code": "krem",
        "company": "ДТЕК Київські регіональні електромережі",
    },
    "dnipro": {
        "name": "Дніпропетровська область",
        "url": "https://www.dtek-dnem.com.ua/ua/shutdowns",
        "code": "dnem",
        "company": "ДТЕК Дніпровські електромережі",
    },
    "odesa": {
        "name": "Одеська область",
        "url": "https://www.dtek-oem.com.ua/ua/shutdowns",
        "code": "oem",
        "company": "ДТЕК Одеські електромережі",
    },
}

# Маппінг назви регіону → ключ для зручного пошуку
REGION_NAME_TO_KEY: dict[str, str] = {
    region["name"]: key for key, region in REGIONS.items()
}

# Emoji для кожного регіону
REGION_EMOJIS: dict[str, str] = {
    "kyiv": "🏙",
    "kyiv_region": "🏘",
    "dnipro": "🏭",
    "odesa": "🌊",
}
