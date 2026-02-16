"""Налаштування логування."""

import logging
import sys


def setup_logging(log_level: str = "INFO") -> None:
    """Налаштувати логування для всіх модулів бота.

    Args:
        log_level: Рівень логування (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Налаштувати кореневий логер
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Окремі логери для модулів
    for module_name in ("bot", "parser", "monitoring", "notification", "database"):
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(numeric_level)
