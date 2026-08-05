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


# ==========================================================
# PUBLIC LOGGERS
# ==========================================================

def system_logger():
    return _build_logger("system", "system.txt")


def trade_logger():
    return _build_logger("trades", "trades.txt")


