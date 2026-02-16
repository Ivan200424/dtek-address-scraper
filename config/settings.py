"""Налаштування бота — завантаження змінних оточення."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Клас налаштувань бота з валідацією."""

    TELEGRAM_BOT_TOKEN: str
    DATABASE_URL: str | None
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    CHECK_INTERVAL: int
    LOG_LEVEL: str
    TZ: str
    MAX_ADDRESSES_PER_USER: int
    BROWSER_TIMEOUT: int

    def __init__(self) -> None:
        """Ініціалізація налаштувань з змінних оточення."""
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN є обов'язковим! Вкажіть його в .env файлі.")

        # Параметри PostgreSQL
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        self.DB_HOST = os.getenv("DB_HOST", "localhost")
        self.DB_PORT = int(os.getenv("DB_PORT", "5432"))
        self.DB_NAME = os.getenv("DB_NAME", "power_outage_bot")
        self.DB_USER = os.getenv("DB_USER", "postgres")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD", "")

        # Моніторинг
        self.CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "300"))

        # Логування
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

        # Часова зона
        self.TZ = os.getenv("TZ", "Europe/Kiev")

        # Ліміти
        self.MAX_ADDRESSES_PER_USER = int(os.getenv("MAX_ADDRESSES_PER_USER", "10"))
        self.BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30"))

    def get_database_url(self) -> str:
        """Отримати URL підключення до бази даних."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
