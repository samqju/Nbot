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
import os
import requests
from typing import Optional
import time
import threading

# ----------------------------------------------------------
# Internal Configuration
# ----------------------------------------------------------

_TELEGRAM_BOT_TOKEN = None
_TELEGRAM_CHAT_ID = None
_CONFIGURED = False

TELEGRAM_API_TIMEOUT = 5
MAX_MESSAGE_LENGTH = 4000  # Safety margin under Telegram 4096 limit

AUTHORIZED_USER_ID = os.getenv("TELEGRAM_OPERATOR_USER_ID")

_system_log = None

def inject_loggers(system_log):
    global _system_log
    _system_log = system_log

def _log_error(msg: str):
    if _system_log:
        _system_log.error(msg)

def _log_info(msg: str):
    if _system_log:
        _system_log.info(msg)

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
        _log_info("TELEGRAM_ALREADY_CONFIGURED")
        return

    if not bot_token or not chat_id:
        _log_error("TELEGRAM_CONFIG_INVALID")
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
            _log_error(
                f"TELEGRAM_HTTP_ERROR | status={resp.status_code}"
            )
            return None

        return resp.json()

    except requests.exceptions.Timeout:
        _log_error("TELEGRAM_TIMEOUT")
        return None

    except Exception as e:
        _log_error(f"TELEGRAM_EXCEPTION | {e}")
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
        f"Entry: {entry_price:.8f}\n"
        f"Stop: {stop_loss:.8f}\n"
        f"Qty: {qty:.6f}\n"
        f"Risk: {risk_usd:.2f} USD\n"
    )


def format_trade_close_panel(
    *,
    symbol: str,
    side: str,
    entry_price,
    initial_stop_loss,
    final_stop_loss,
    qty,
    risk_usd,
    exit_price,
    realized_pnl,
    r_multiple,
    status: str = "CLOSED",
    exit_reason: str | None = None,
) -> str:
    """Return a null-safe final trade receipt for Telegram."""

    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    text = (
        f"📊 <b>TRADE {status}</b>\n\n"
        f"Symbol: {symbol}\n"
        f"Side: {side}\n"
        f"Entry: {_number(entry_price):.8f}\n"
        f"Initial Stop: {_number(initial_stop_loss):.8f}\n"
        f"Final Stop: {_number(final_stop_loss):.8f}\n"
        f"Qty: {_number(qty):.6f}\n"
        f"Risk: {_number(risk_usd):.2f} USD\n"
        f"Exit: {_number(exit_price):.8f}\n"
        f"PnL: {_number(realized_pnl):+.2f} USD\n"
        f"Result: {_number(r_multiple):+.2f}R\n"
    )
    if exit_reason:
        text += f"Exit Reason: {exit_reason}\n"
    return text


def send_trade_panel(text: str) -> Optional[int]:
    return send_message(text)

# ==========================================================
# OPERATOR COMMAND LISTENER
# ==========================================================

_LAST_UPDATE_ID = None
_LISTENER_STARTED = False
_LISTENER_LOCK = threading.Lock()

def start_operator_listener(command_callback):
    """
    Start long-poll Telegram command listener.
    Only processes commands from AUTHORIZED_USER_ID.
    """

    global _LISTENER_STARTED, _LAST_UPDATE_ID

    if not _is_configured():
        return False

    if not AUTHORIZED_USER_ID:
        _log_error("AUTHORIZED_USER_ID_NOT_SET")
        return False

    with _LISTENER_LOCK:
        if _LISTENER_STARTED:
            _log_info("TELEGRAM_OPERATOR_LISTENER_ALREADY_STARTED")
            return False
        _LISTENER_STARTED = True

    url = f"https://api.telegram.org/bot{_TELEGRAM_BOT_TOKEN}/getUpdates"

    # Fail closed on commands queued while Execution was offline. A stale
    # /enable must never arm trading after a restart merely because Telegram
    # retained the update. Commands sent after this listener starts are handled
    # normally.
    try:
        discarded = 0
        while True:
            params = {"timeout": 0}
            if _LAST_UPDATE_ID is not None:
                params["offset"] = _LAST_UPDATE_ID + 1
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if not isinstance(data, dict) or data.get("ok") is False:
                raise RuntimeError("TELEGRAM_GET_UPDATES_PRIME_FAILED")
            updates = data.get("result", [])
            if not updates:
                break
            discarded += len(updates)
            _LAST_UPDATE_ID = max(int(item["update_id"]) for item in updates)
            if len(updates) < 100:
                break
        if discarded:
            _log_info(
                "TELEGRAM_OPERATOR_BACKLOG_DISCARDED | "
                f"count={discarded}"
            )
    except Exception as exc:
        # Fail closed for operator control: if we cannot establish a safe
        # Telegram offset, do not consume potentially stale queued commands.
        # Execution itself continues normally.
        _log_error(f"OPERATOR_LISTENER_PRIME_ERROR | {exc}")
        with _LISTENER_LOCK:
            _LISTENER_STARTED = False
        return False

    def _poll():
        global _LAST_UPDATE_ID

        while True:
            try:
                params = {"timeout": 60}
                if _LAST_UPDATE_ID is not None:
                    params["offset"] = _LAST_UPDATE_ID + 1

                resp = requests.get(url, params=params, timeout=70)
                data = resp.json()

                for update in data.get("result", []):
                    _LAST_UPDATE_ID = update["update_id"]

                    message = update.get("message")
                    if not message:
                        continue

                    user = message.get("from", {})
                    user_id = str(user.get("id"))

                    if user_id != str(AUTHORIZED_USER_ID):
                        continue

                    text = message.get("text", "")
                    if text:
                        command_callback(text.strip())

            except Exception as e:
                _log_error(f"OPERATOR_LISTENER_ERROR | {e}")
                time.sleep(5)

    threading.Thread(
        target=_poll,
        name="nbot-telegram-operator",
        daemon=True,
    ).start()
    return True
