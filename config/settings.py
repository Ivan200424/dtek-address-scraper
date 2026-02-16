"""Settings configuration using environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://user:password@localhost:5432/dtek_bot"
    )
    DB_POOL_MIN_SIZE: int = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
    DB_POOL_MAX_SIZE: int = int(os.getenv("DB_POOL_MAX_SIZE", "10"))

    # Monitoring
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", "300"))  # 5 minutes
    MAX_ADDRESSES_PER_USER: int = int(os.getenv("MAX_ADDRESSES_PER_USER", "10"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Timezone
    TZ: str = os.getenv("TZ", "Europe/Kyiv")

    # Playwright
    PLAYWRIGHT_TIMEOUT: int = int(os.getenv("PLAYWRIGHT_TIMEOUT", "60000"))  # 60 seconds


settings = Settings()
