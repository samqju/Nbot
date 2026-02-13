# ==========================================================
# TELEGRAM NOTIFIER
# ==========================================================
# Fire-and-forget alerting module.
#
# Structural Guarantees:
# - Non-blocking
# - Never raises exceptions
# - Idempotent configuration
# - Message size guard
# - Structured failure logging
# ==========================================================

import requests
import logging
from typing import Optional

# ----------------------------------------------------------
# Internal Configuration
# ----------------------------------------------------------

_TELEGRAM_BOT_TOKEN = None
_TELEGRAM_CHAT_ID = None
_CONFIGURED = False

TELEGRAM_API_TIMEOUT = 5
MAX_MESSAGE_LENGTH = 4000  # Safety margin under Telegram 4096 limit

_logger = logging.getLogger("telegram")
_logger.setLevel(logging.INFO)


# ----------------------------------------------------------
# Configuration
# ----------------------------------------------------------

def configure(bot_token: str, chat_id: str) -> None:
    """
    Configure Telegram credentials.
    Idempotent — only first call takes effect.
    """

    global _TELEGRAM_BOT_TOKEN, _TELEGRAM_CHAT_ID, _CONFIGURED

    if _CONFIGURED:
        _logger.warning("TELEGRAM_ALREADY_CONFIGURED")
        return

    if not bot_token or not chat_id:
        _logger.warning("TELEGRAM_CONFIG_INVALID")
        return

    _TELEGRAM_BOT_TOKEN = bot_token
    _TELEGRAM_CHAT_ID = chat_id
    _CONFIGURED = True


def _is_configured() -> bool:
    return _CONFIGURED


# ----------------------------------------------------------
# Internal Send Helper
# ----------------------------------------------------------

def _safe_post(url: str, payload: dict) -> Optional[dict]:
    try:
        resp = requests.post(
            url,
            json=payload,
            timeout=TELEGRAM_API_TIMEOUT,
        )

        if resp.status_code != 200:
            _logger.warning(
                f"TELEGRAM_HTTP_ERROR | status={resp.status_code}"
            )
            return None

        return resp.json()

    except requests.exceptions.Timeout:
        _logger.warning("TELEGRAM_TIMEOUT")
        return None

    except Exception as e:
        _logger.warning(f"TELEGRAM_EXCEPTION | {e}")
        return None


# ----------------------------------------------------------
# Public API
# ----------------------------------------------------------

def send_message(text: str) -> Optional[int]:
    """
    Send a new Telegram message.
    Returns message_id if successful.
    """

    if not _is_configured():
        return None

    if not text:
        return None

    # Message length guard
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH] + "\n\n[TRUNCATED]"

    url = f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": _TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    data = _safe_post(url, payload)

    if not data:
        return None

    return data.get("result", {}).get("message_id")


def edit_message(message_id: int, text: str) -> None:
    """
    Edit existing Telegram message.
    Failures are silently ignored.
    """

    if not _is_configured():
        return

    if not message_id or not text:
        return

    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH] + "\n\n[TRUNCATED]"

    url = f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}/editMessageText"

    payload = {
        "chat_id": _TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    _safe_post(url, payload)


# ==========================================================
# Structured Alert API
# ==========================================================

def send_info(title: str, body: str = "") -> Optional[int]:
    return send_message(
        f"🟢 <b>{title}</b>\n\n{body}"
    )


def send_warning(title: str, body: str = "") -> Optional[int]:
    return send_message(
        f"🟡 <b>{title}</b>\n\n{body}"
    )


def send_critical(title: str, body: str = "") -> Optional[int]:
    return send_message(
        f"🔴 <b>{title}</b>\n\n{body}"
    )


# ----------------------------------------------------------
# Trade Panel Formatter
# ----------------------------------------------------------

def format_trade_panel(
    *,
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    qty: float,
    risk_usd: float,
    status: str,
) -> str:

    return (
        f"📊 <b>TRADE {status}</b>\n\n"
        f"Symbol: {symbol}\n"
        f"Side: {side}\n"
        f"Entry: {entry_price:.4f}\n"
        f"Stop: {stop_loss:.4f}\n"
        f"Qty: {qty:.6f}\n"
        f"Risk: {risk_usd:.2f} USD\n"
    )


def send_trade_panel(text: str) -> Optional[int]:
    return send_message(text)
