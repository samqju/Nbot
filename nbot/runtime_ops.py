from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable

import requests


DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)sZ %(levelname)s %(name)s %(message)s"


def _level_from_env() -> int:
    name = os.getenv("BOT_LOG_LEVEL", "INFO").strip().upper()
    return int(getattr(logging, name, logging.INFO))


def _rotating_handler(path: Path, *, level: int) -> RotatingFileHandler:
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path,
        maxBytes=int(os.getenv("NBOT_LOG_MAX_BYTES", str(DEFAULT_LOG_MAX_BYTES))),
        backupCount=int(os.getenv("NBOT_LOG_BACKUP_COUNT", str(DEFAULT_LOG_BACKUP_COUNT))),
        encoding="utf-8",
    )
    handler.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    return handler


def configure_role_logging(
    role: str,
    *,
    log_path: Path,
    trade_log_path: Path | None = None,
    stderr: bool = True,
) -> tuple[logging.Logger, logging.Logger | None]:
    """Configure one-process role logging without cross-worker shared files.

    Each worker process writes to its own rotating file. Execution may also
    receive a separate trade-audit logger. Existing handlers are replaced so a
    test or restart cannot accidentally duplicate every log line.
    """
    normalized = str(role).strip().upper()
    if normalized not in {"EXECUTION", "OBSERVATION"}:
        raise ValueError("NBOT_LOG_ROLE_INVALID")
    level = _level_from_env()

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    root.addHandler(_rotating_handler(Path(log_path), level=level))
    if stderr:
        stream = logging.StreamHandler()
        stream.setLevel(level)
        formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")
        formatter.converter = time.gmtime
        stream.setFormatter(formatter)
        root.addHandler(stream)

    role_logger = logging.getLogger(f"nbot.v2.{normalized.lower()}")
    role_logger.setLevel(level)
    role_logger.propagate = True

    trade_logger: logging.Logger | None = None
    if trade_log_path is not None:
        trade_logger = logging.getLogger("nbot.v2.execution.trade")
        trade_logger.setLevel(level)
        trade_logger.propagate = False
        for handler in list(trade_logger.handlers):
            trade_logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        trade_logger.addHandler(_rotating_handler(Path(trade_log_path), level=level))
    return role_logger, trade_logger


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    operator_user_id: str
    role: str
    api_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls, role: str) -> "TelegramConfig | None":
        role = str(role).strip().upper()
        if role == "EXECUTION":
            token = os.getenv("EXECUTION_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
            chat = os.getenv("EXECUTION_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
            operator = os.getenv("EXECUTION_TELEGRAM_OPERATOR_USER_ID") or os.getenv("TELEGRAM_OPERATOR_USER_ID")
        elif role == "OBSERVATION":
            # Observation deliberately has no fallback to the V1/shared bot.
            # Two long-poll consumers on one Telegram bot would race for updates.
            token = os.getenv("OBSERVATION_TELEGRAM_BOT_TOKEN")
            chat = os.getenv("OBSERVATION_TELEGRAM_CHAT_ID")
            operator = os.getenv("OBSERVATION_TELEGRAM_OPERATOR_USER_ID")
        else:
            raise ValueError("TELEGRAM_ROLE_INVALID")
        if not token or not chat or not operator:
            return None
        return cls(str(token), str(chat), str(operator), role)


class TelegramOperator:
    """Optional, non-authoritative Telegram notifier/operator listener.

    Notification failures never raise into trading/observation code. Operator
    commands run on a daemon listener thread. Queued commands are discarded on
    startup so an old /enable cannot become active after a restart.
    """

    MAX_MESSAGE_LENGTH = 4000

    def __init__(self, config: TelegramConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self._last_update_id: int | None = None
        self._listener_started = False
        self._listener_lock = threading.Lock()

    @classmethod
    def from_env(cls, role: str, logger: logging.Logger) -> "TelegramOperator | None":
        cfg = TelegramConfig.from_env(role)
        return None if cfg is None else cls(cfg, logger)

    @property
    def configured(self) -> bool:
        return True

    def _safe_post(self, method: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.config.bot_token}/{method}",
                json=payload,
                timeout=self.config.api_timeout_seconds,
            )
            if response.status_code != 200:
                self.logger.error("TELEGRAM_HTTP_ERROR role=%s status=%s", self.config.role, response.status_code)
                return None
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception as exc:
            self.logger.error("TELEGRAM_SEND_FAILED role=%s error=%s:%s", self.config.role, type(exc).__name__, exc)
            return None

    def send(self, level: str, title: str, body: str = "") -> None:
        prefix = {"INFO": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}.get(level.upper(), "ℹ️")
        text = f"{prefix} <b>{title}</b>"
        if body:
            text += f"\n\n{body}"
        if len(text) > self.MAX_MESSAGE_LENGTH:
            text = text[: self.MAX_MESSAGE_LENGTH - 14] + "\n\n[TRUNCATED]"
        self._safe_post(
            "sendMessage",
            {
                "chat_id": self.config.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )

    def info(self, title: str, body: str = "") -> None:
        self.send("INFO", title, body)

    def warning(self, title: str, body: str = "") -> None:
        self.send("WARNING", title, body)

    def critical(self, title: str, body: str = "") -> None:
        self.send("CRITICAL", title, body)

    def _prime_backlog(self) -> bool:
        url = f"https://api.telegram.org/bot{self.config.bot_token}/getUpdates"
        try:
            discarded = 0
            while True:
                params: dict[str, Any] = {"timeout": 0}
                if self._last_update_id is not None:
                    params["offset"] = self._last_update_id + 1
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                if not isinstance(data, dict) or data.get("ok") is False:
                    raise RuntimeError("TELEGRAM_GET_UPDATES_PRIME_FAILED")
                rows = data.get("result", [])
                if not rows:
                    break
                discarded += len(rows)
                self._last_update_id = max(int(row["update_id"]) for row in rows)
                if len(rows) < 100:
                    break
            if discarded:
                self.logger.info("TELEGRAM_OPERATOR_BACKLOG_DISCARDED role=%s count=%s", self.config.role, discarded)
            return True
        except Exception as exc:
            self.logger.error("TELEGRAM_OPERATOR_PRIME_FAILED role=%s error=%s:%s", self.config.role, type(exc).__name__, exc)
            return False

    def start_listener(self, callback: Callable[[str], None]) -> bool:
        with self._listener_lock:
            if self._listener_started:
                return False
            if not self._prime_backlog():
                return False
            self._listener_started = True

        url = f"https://api.telegram.org/bot{self.config.bot_token}/getUpdates"

        def poll() -> None:
            while True:
                try:
                    params: dict[str, Any] = {"timeout": 60}
                    if self._last_update_id is not None:
                        params["offset"] = self._last_update_id + 1
                    response = requests.get(url, params=params, timeout=70)
                    data = response.json()
                    if not isinstance(data, dict):
                        raise RuntimeError("TELEGRAM_GET_UPDATES_INVALID")
                    for update in data.get("result", []):
                        self._last_update_id = int(update["update_id"])
                        message = update.get("message") or {}
                        user_id = str((message.get("from") or {}).get("id") or "")
                        if user_id != self.config.operator_user_id:
                            continue
                        text = str(message.get("text") or "").strip()
                        if text:
                            callback(text)
                except Exception as exc:
                    self.logger.error("TELEGRAM_OPERATOR_LISTENER_ERROR role=%s error=%s:%s", self.config.role, type(exc).__name__, exc)
                    time.sleep(5)

        threading.Thread(target=poll, name=f"nbot-{self.config.role.lower()}-telegram", daemon=True).start()
        self.logger.info("TELEGRAM_OPERATOR_LISTENER_STARTED role=%s", self.config.role)
        return True


def telegram_escape_plain(value: Any) -> str:
    # Messages use HTML parse mode. Status fields are controlled strings/numbers;
    # escape the few special characters that may occur in error/reason fields.
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
