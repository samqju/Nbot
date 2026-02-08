# ================================
# LOGGER UTILITY
# ================================
# Centralized multi-file logging (PASS 5)
# Provides a single shared logger for the bot.
# No logic, no side effects.

# ================================
# IMPORTS
# ================================

import logging
import os

# ================================
# GET LOGGER
# ================================

LOG_DIR = "logs"

os.makedirs(LOG_DIR, exist_ok=True)

_FORMATTER = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s"
)


def _file_handler(filename, level):
    handler = logging.FileHandler(os.path.join(LOG_DIR, filename))
    handler.setLevel(level)
    handler.setFormatter(_FORMATTER)
    return handler


def _get_logger(name, filename, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        logger.addHandler(_file_handler(filename, level))

    return logger


# ---- PUBLIC LOGGERS ----

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


# ---- BACKWARD COMPATIBILITY ----

def setup_logger(name):
    """
    Legacy entrypoint.
    Defaults to system logger behavior.
    """
    return system_logger()
