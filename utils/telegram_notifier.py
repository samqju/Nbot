# utils/telegram_notifier.py
# ==========================================================
# TELEGRAM NOTIFIER (PHASE E.1)
# ==========================================================
# Responsibilities:
# - Send Telegram messages
# - Edit existing Telegram messages
# - NEVER raise exceptions
# - NEVER block trading
#
# This module is FIRE-AND-FORGET.
# Failures are swallowed by design.
# ==========================================================

import requests
import logging
from typing import Optional

# ----------------------------------------------------------
# Configuration (env-based, no config.py dependency)
# ----------------------------------------------------------

TELEGRAM_BOT_TOKEN = None
TELEGRAM_CHAT_ID = None

TELEGRAM_API_TIMEOUT = 5  # seconds (hard cap)

# ----------------------------------------------------------
# Internal logger (isolated)
# ----------------------------------------------------------

_logger = logging.getLogger("telegram")
_logger.setLevel(logging.INFO)

# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------

def _is_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def configure(bot_token: str, chat_id: str) -> None:
    """
    Configure Telegram credentials.
    Called once at startup (optional).
    """
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    TELEGRAM_BOT_TOKEN = bot_token
    TELEGRAM_CHAT_ID = chat_id


# ----------------------------------------------------------
# Public API
# ----------------------------------------------------------

def send_message(text: str) -> Optional[int]:
    """
    Send a new Telegram message.

    Returns:
        message_id (int) if successful
        None if failed or not configured
    """
    if not _is_configured():
        return None

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        resp = requests.post(
            url,
            json=payload,
            timeout=TELEGRAM_API_TIMEOUT,
        )

        if resp.status_code != 200:
            _logger.warning(
                f"TELEGRAM_SEND_FAILED | status={resp.status_code}"
            )
            return None

        data = resp.json()
        return data.get("result", {}).get("message_id")

    except Exception as e:
        _logger.warning(f"TELEGRAM_SEND_EXCEPTION | {e}")
        return None


def edit_message(message_id: int, text: str) -> None:
    """
    Edit an existing Telegram message.

    Failures are silently ignored.
    """
    if not _is_configured():
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        resp = requests.post(
            url,
            json=payload,
            timeout=TELEGRAM_API_TIMEOUT,
        )

        if resp.status_code != 200:
            _logger.warning(
                f"TELEGRAM_EDIT_FAILED | status={resp.status_code}"
            )

    except Exception as e:
        _logger.warning(f"TELEGRAM_EDIT_EXCEPTION | {e}")
        return
