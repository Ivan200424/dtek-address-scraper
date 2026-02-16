"""Configuration for DTEK regions and queue numbers."""

# DTEK regions configuration
REGIONS = {
    "kyiv": {
        "name": "Київ",
        "code": "kem",
        "url": "https://www.dtek-kem.com.ua/ua/shutdowns",
    },
    "kyiv_region": {
        "name": "Київська область",
        "code": "krem",
        "url": "https://www.dtek-krem.com.ua/ua/shutdowns",
    },
    "dnipro": {
        "name": "Дніпропетровська область",
        "code": "dnem",
        "url": "https://www.dtek-dnem.com.ua/ua/shutdowns",
    },
    "odesa": {
        "name": "Одеська область",
        "code": "oem",
        "url": "https://www.dtek-oem.com.ua/ua/shutdowns",
    },
}

# Queue numbers by region (total 102 queues)

# Kyiv - 66 queues: Standard 12 + Additional 54 (7.1 to 60.1)
KYIV_QUEUES = [
    # Standard 12 queues
    "1.1", "1.2", "2.1", "2.2", "3.1", "3.2",
    "4.1", "4.2", "5.1", "5.2", "6.1", "6.2",
    # Additional 54 queues (7.1 to 60.1)
    "7.1", "8.1", "9.1", "10.1", "11.1", "12.1", "13.1", "14.1", "15.1",
    "16.1", "17.1", "18.1", "19.1", "20.1", "21.1", "22.1", "23.1", "24.1",
    "25.1", "26.1", "27.1", "28.1", "29.1", "30.1", "31.1", "32.1", "33.1",
    "34.1", "35.1", "36.1", "37.1", "38.1", "39.1", "40.1", "41.1", "42.1",
    "43.1", "44.1", "45.1", "46.1", "47.1", "48.1", "49.1", "50.1", "51.1",
    "52.1", "53.1", "54.1", "55.1", "56.1", "57.1", "58.1", "59.1", "60.1",
]

# Kyiv Region - 12 queues
KYIV_REGION_QUEUES = [
    "1.1", "1.2", "2.1", "2.2", "3.1", "3.2",
    "4.1", "4.2", "5.1", "5.2", "6.1", "6.2",
]

# Dnipro - 12 queues
DNIPRO_QUEUES = [
    "1.1", "1.2", "2.1", "2.2", "3.1", "3.2",
    "4.1", "4.2", "5.1", "5.2", "6.1", "6.2",
]

# Odesa - 12 queues
ODESA_QUEUES = [
    "1.1", "1.2", "2.1", "2.2", "3.1", "3.2",
    "4.1", "4.2", "5.1", "5.2", "6.1", "6.2",
]

# Map region keys to their queues
REGION_QUEUES = {
    "kyiv": KYIV_QUEUES,
    "kyiv_region": KYIV_REGION_QUEUES,
    "dnipro": DNIPRO_QUEUES,
    "odesa": ODESA_QUEUES,
}

# Emoji for each region
REGION_EMOJIS = {
    "kyiv": "🏙",
    "kyiv_region": "🏘",
    "dnipro": "🏭",
    "odesa": "🌊",
}

# Total queues verification: 66 + 12 + 12 + 12 = 102
TOTAL_QUEUES = sum(len(queues) for queues in REGION_QUEUES.values())
assert TOTAL_QUEUES == 102, f"Expected 102 queues, got {TOTAL_QUEUES}"
