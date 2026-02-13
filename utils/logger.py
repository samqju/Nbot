# ==========================================================
# LOGGER UTILITY
# ==========================================================
# Centralized multi-file logging.
#
# Structural Guarantees:
# - Idempotent logger creation
# - No duplicate handlers
# - File rotation enabled
# - No propagation to root logger
# - Safe directory initialization
# ==========================================================

import logging
import os
from logging.handlers import RotatingFileHandler


# ----------------------------------------------------------
# Configuration
# ----------------------------------------------------------

LOG_DIR = "logs"
MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3

_FORMATTER = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
)


# ----------------------------------------------------------
# Directory Initialization
# ----------------------------------------------------------

def _ensure_log_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"LOG_DIRECTORY_INIT_FAILED | {e}")


_ensure_log_dir()


# ----------------------------------------------------------
# Handler Factory
# ----------------------------------------------------------

def _file_handler(filename, level):

    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=MAX_LOG_SIZE_BYTES,
        backupCount=BACKUP_COUNT,
    )

    handler.setLevel(level)
    handler.setFormatter(_FORMATTER)

    return handler


# ----------------------------------------------------------
# Logger Factory (Idempotent)
# ----------------------------------------------------------

def _get_logger(name, filename, level=logging.INFO):

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    # Prevent duplicate handlers
    if not any(
        isinstance(h, RotatingFileHandler)
        and h.baseFilename.endswith(filename)
        for h in logger.handlers
    ):
        logger.addHandler(_file_handler(filename, level))

    return logger


# ----------------------------------------------------------
# Public Loggers
# ----------------------------------------------------------

def system_logger():
    return _get_logger("system", "system.log", logging.INFO)


def trade_logger():
    return _get_logger("trades", "trades.log", logging.INFO)


def risk_logger():
    return _get_logger("risk", "risk.log", logging.INFO)


def daily_logger():
    return _get_logger("daily", "daily.log", logging.INFO)


def debug_logger():
    return _get_logger("debug", "debug.log", logging.DEBUG)


# ----------------------------------------------------------
# Backward Compatibility
# ----------------------------------------------------------

def setup_logger(name):
    return system_logger()
