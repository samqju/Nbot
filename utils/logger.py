# ==========================================================
# SIMPLIFIED LOGGER (3 FILE MODE)
# ==========================================================

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

os.makedirs(LOG_DIR, exist_ok=True)

FORMATTER = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s"
)

def _build_logger(name, filename):
    logger = logging.getLogger(name)
    level_name = os.getenv("BOT_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        handler = RotatingFileHandler(
            os.path.join(LOG_DIR, filename),
            maxBytes=MAX_LOG_SIZE_BYTES,
            backupCount=BACKUP_COUNT,
        )
        handler.setLevel(level)
        handler.setFormatter(FORMATTER)
        logger.addHandler(handler)

    return logger


class _InfoPrefixFilter(logging.Filter):
    """Keep warnings/errors while allowing only selected INFO event prefixes."""

    def __init__(self, prefixes):
        super().__init__()
        self.prefixes = tuple(str(value) for value in prefixes if str(value))

    def filter(self, record):
        if record.levelno >= logging.WARNING:
            return True
        if record.levelno != logging.INFO:
            return False
        message = record.getMessage()
        return any(message.startswith(prefix) for prefix in self.prefixes)


def restrict_info_to_prefixes(logger, prefixes):
    """Restrict one process logger to warnings/errors plus approved INFO events."""
    normalized = tuple(str(value) for value in prefixes if str(value))
    marker = ("NBOT_INFO_PREFIX_FILTER", normalized)
    if getattr(logger, "_nbot_info_filter_marker", None) == marker:
        return logger
    logger.addFilter(_InfoPrefixFilter(normalized))
    logger._nbot_info_filter_marker = marker
    return logger


# ==========================================================
# PUBLIC LOGGERS
# ==========================================================

def system_logger():
    return _build_logger("system", "system.txt")


def trade_logger():
    return _build_logger("trades", "trades.txt")


