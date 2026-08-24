"""Small standard-library Telegram transport for NBOT V3.

Guarantees:
- optional configuration;
- bounded HTTP timeouts;
- send/edit failures return safely and never raise into worker loops;
- command listener authorizes both chat and operator user;
- queued commands are discarded before polling begins so stale /enable cannot
  change a restarted worker.
"""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
import logging
import queue
import threading
import time
from typing import Callable, Mapping
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

MAX_MESSAGE_LENGTH = 4000


class TelegramPollingError(RuntimeError):
    """Telegram command polling failed; caller must back off before retrying."""


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""
    operator_user_id: str = ""
    timeout_seconds: float = 5.0

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    @property
    def commands_enabled(self) -> bool:
        return bool(self.enabled and self.operator_user_id)

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
        *,
        prefix: str,
    ) -> "TelegramConfig":
        prefix = str(prefix).strip().upper()
        if prefix not in {"EXECUTION", "OBSERVATION"}:
            raise ValueError("NBOT_TELEGRAM_PREFIX_INVALID")
        token = str(environment.get(f"{prefix}_TELEGRAM_BOT_TOKEN", "")).strip()
        chat_id = str(environment.get(f"{prefix}_TELEGRAM_CHAT_ID", "")).strip()
        operator = str(environment.get(f"{prefix}_TELEGRAM_OPERATOR_USER_ID", "")).strip()
        # Execution accepts the old generic names as a compatibility fallback
        # for existing Testnet secret files. Observation intentionally does not:
        # sharing one long-poll bot between VPS roles would race getUpdates.
        if prefix == "EXECUTION":
            token = token or str(environment.get("TELEGRAM_BOT_TOKEN", "")).strip()
            chat_id = chat_id or str(environment.get("TELEGRAM_CHAT_ID", "")).strip()
            operator = operator or str(environment.get("TELEGRAM_OPERATOR_USER_ID", "")).strip()
        timeout_raw = str(environment.get("NBOT_TELEGRAM_TIMEOUT_SECONDS", "5.0")).strip()
        try:
            timeout = float(timeout_raw)
        except ValueError as exc:
            raise ValueError("NBOT_TELEGRAM_TIMEOUT_INVALID") from exc
        if not (0.5 <= timeout <= 30.0):
            raise ValueError("NBOT_TELEGRAM_TIMEOUT_INVALID")
        # Partial send configuration is treated as disabled rather than fatal;
        # Telegram is optional and cannot be allowed to block the worker.
        if bool(token) != bool(chat_id):
            token = ""
            chat_id = ""
            operator = ""
        return cls(token, chat_id, operator, timeout)


class TelegramClient:
    """Best-effort Telegram Bot API client."""

    def __init__(
        self,
        config: TelegramConfig,
        *,
        logger: logging.Logger | None = None,
        requester: Callable[[str, Mapping[str, object], float], dict | None] | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self._requester = requester or self._http_request

    def _log(self, level: str, message: str) -> None:
        if self.logger is None:
            return
        getattr(self.logger, level, self.logger.info)(message)

    def _http_request(
        self,
        method: str,
        payload: Mapping[str, object],
        timeout: float,
    ) -> dict | None:
        url = f"https://api.telegram.org/bot{self.config.bot_token}/{method}"
        encoded = urlparse.urlencode(
            {key: json.dumps(value) if isinstance(value, (dict, list)) else value for key, value in payload.items()}
        ).encode("utf-8")
        req = urlrequest.Request(url, data=encoded, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=timeout) as response:
                raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                self._log("warning", "TELEGRAM_RESPONSE_TOO_LARGE")
                return None
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict) or data.get("ok") is not True:
                self._log("warning", f"TELEGRAM_API_ERROR method={method}")
                return None
            return data
        except (urlerror.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            self._log("warning", f"TELEGRAM_REQUEST_FAILED method={method} error={type(exc).__name__}:{exc}")
            return None
        except Exception as exc:  # best-effort boundary: never raise into worker
            self._log("warning", f"TELEGRAM_REQUEST_FAILED method={method} error={type(exc).__name__}:{exc}")
            return None


    def _request(self, method: str, payload: Mapping[str, object], timeout: float) -> dict | None:
        try:
            return self._requester(method, payload, timeout)
        except Exception as exc:
            self._log("warning", f"TELEGRAM_REQUEST_FAILED method={method} error={type(exc).__name__}:{exc}")
            return None

    @staticmethod
    def _trim(text: str) -> str:
        text = str(text or "")
        if len(text) <= MAX_MESSAGE_LENGTH:
            return text
        return text[: MAX_MESSAGE_LENGTH - 16] + "\n\n[TRUNCATED]"

    def send_message(self, text: str) -> int | None:
        if not self.config.enabled or not text:
            return None
        data = self._request(
            "sendMessage",
            {
                "chat_id": self.config.chat_id,
                "text": self._trim(text),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            self.config.timeout_seconds,
        )
        try:
            message_id = data["result"]["message_id"] if data else None
            return int(message_id) if message_id is not None else None
        except (KeyError, TypeError, ValueError):
            self._log("warning", "TELEGRAM_SEND_RESPONSE_INVALID")
            return None

    def edit_message(self, message_id: int | None, text: str) -> bool:
        if not self.config.enabled or not message_id or not text:
            return False
        data = self._request(
            "editMessageText",
            {
                "chat_id": self.config.chat_id,
                "message_id": int(message_id),
                "text": self._trim(text),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            self.config.timeout_seconds,
        )
        return bool(data and data.get("ok") is True)

    def send_info(self, title: str, body: str = "") -> int | None:
        return self.send_message(f"🟢 <b>{html.escape(title)}</b>\n\n{body}".rstrip())

    def send_warning(self, title: str, body: str = "") -> int | None:
        return self.send_message(f"🟡 <b>{html.escape(title)}</b>\n\n{body}".rstrip())

    def send_critical(self, title: str, body: str = "") -> int | None:
        return self.send_message(f"🔴 <b>{html.escape(title)}</b>\n\n{body}".rstrip())

    def get_updates(self, *, offset: int | None, timeout_seconds: int) -> list[dict]:
        if not self.config.commands_enabled:
            return []
        payload: dict[str, object] = {
            "timeout": max(0, int(timeout_seconds)),
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = int(offset)
        data = self._request(
            "getUpdates",
            payload,
            max(self.config.timeout_seconds, float(timeout_seconds) + 10.0),
        )
        # A failed Bot API request must never be mistaken for a healthy empty
        # long poll.  Returning [] here would make the listener spin immediately
        # and hammer Telegram after a transient/server-side restriction.
        if data is None:
            raise TelegramPollingError("TELEGRAM_GET_UPDATES_FAILED")
        result = data.get("result")
        if not isinstance(result, list):
            raise TelegramPollingError("TELEGRAM_GET_UPDATES_RESULT_INVALID")
        return list(result)


class TelegramCommandListener:
    """One authorized long-poll listener.  Failure never touches worker state."""

    def __init__(
        self,
        client: TelegramClient,
        callback: Callable[[str], None],
        *,
        logger: logging.Logger | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.callback = callback
        self.logger = logger
        self.sleep = sleep
        self._offset: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _log(self, level: str, message: str) -> None:
        if self.logger is not None:
            getattr(self.logger, level, self.logger.info)(message)

    def _dispatch(self, update: Mapping[str, object]) -> None:
        try:
            update_id = int(update.get("update_id"))
        except (TypeError, ValueError):
            return
        self._offset = max(update_id + 1, self._offset or 0)
        message = update.get("message")
        if not isinstance(message, Mapping):
            return
        chat = message.get("chat")
        sender = message.get("from")
        if not isinstance(chat, Mapping) or not isinstance(sender, Mapping):
            return
        if str(chat.get("id")) != self.client.config.chat_id:
            return
        if str(sender.get("id")) != self.client.config.operator_user_id:
            return
        text = str(message.get("text") or "").strip()
        if not text:
            return
        try:
            self.callback(text)
        except Exception as exc:
            self._log("warning", f"TELEGRAM_COMMAND_CALLBACK_FAILED error={type(exc).__name__}:{exc}")

    def _prime(self) -> bool:
        """Discard updates queued before startup; stale /enable must never apply."""
        if not self.client.config.commands_enabled:
            return False
        try:
            discarded = 0
            while True:
                rows = self.client.get_updates(offset=self._offset, timeout_seconds=0)
                if not rows:
                    break
                discarded += len(rows)
                for row in rows:
                    try:
                        update_id = int(row.get("update_id"))
                    except (TypeError, ValueError, AttributeError):
                        continue
                    self._offset = max(update_id + 1, self._offset or 0)
                if len(rows) < 100:
                    break
            if discarded:
                self._log("info", f"TELEGRAM_COMMAND_BACKLOG_DISCARDED count={discarded}")
            return True
        except Exception as exc:
            self._log("warning", f"TELEGRAM_COMMAND_PRIME_FAILED error={type(exc).__name__}:{exc}")
            return False

    def start(self) -> bool:
        if self._thread is not None or not self._prime():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="nbot-telegram-operator", daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        consecutive_failures = 0
        while not self._stop.is_set():
            try:
                rows = self.client.get_updates(offset=self._offset, timeout_seconds=60)
                if consecutive_failures:
                    self._log(
                        "info",
                        f"TELEGRAM_COMMAND_POLL_RECOVERED failures={consecutive_failures}",
                    )
                consecutive_failures = 0
                for row in rows:
                    if isinstance(row, Mapping):
                        self._dispatch(row)
            except Exception as exc:
                consecutive_failures += 1
                delay = min(60.0, 5.0 * (2 ** min(consecutive_failures - 1, 4)))
                # Log the first failure and each backoff transition.  Once the
                # 60-second cap is reached, log only every tenth capped failure.
                if consecutive_failures <= 5 or consecutive_failures % 10 == 0:
                    self._log(
                        "warning",
                        "TELEGRAM_COMMAND_POLL_BACKOFF "
                        f"failures={consecutive_failures} delay_seconds={delay:.0f} "
                        f"error={type(exc).__name__}:{exc}",
                    )
                self.sleep(delay)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)


class TelegramDispatcher:
    """Bounded background send/edit queue.

    Worker/capital/collector threads only enqueue. Network latency or Telegram
    outage is therefore unable to delay the caller. Command polling remains a
    separate listener thread.
    """

    def __init__(
        self,
        client: TelegramClient,
        *,
        logger: logging.Logger | None = None,
        max_queue: int = 100,
    ) -> None:
        self.client = client
        self.logger = logger
        self._queue: queue.Queue[tuple[str, tuple, Callable[[object], None] | None]] = queue.Queue(
            maxsize=max(1, int(max_queue))
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _log(self, level: str, message: str) -> None:
        if self.logger is not None:
            getattr(self.logger, level, self.logger.info)(message)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="nbot-telegram-dispatch", daemon=True
        )
        self._thread.start()

    def _enqueue(
        self,
        operation: str,
        args: tuple,
        callback: Callable[[object], None] | None = None,
    ) -> bool:
        if not self.client.config.enabled:
            if callback is not None:
                try:
                    callback(None)
                except Exception:
                    pass
            return False
        self.start()
        try:
            self._queue.put_nowait((operation, args, callback))
            return True
        except queue.Full:
            self._log("warning", f"TELEGRAM_DISPATCH_QUEUE_FULL operation={operation}")
            if callback is not None:
                try:
                    callback(None)
                except Exception:
                    pass
            return False

    def send_message(
        self, text: str, *, callback: Callable[[object], None] | None = None
    ) -> bool:
        return self._enqueue("send", (text,), callback)

    def edit_message(self, message_id: int | None, text: str) -> bool:
        if not message_id:
            return False
        return self._enqueue("edit", (int(message_id), text))

    def send_info(self, title: str, body: str = "") -> bool:
        text = f"🟢 <b>{html.escape(title)}</b>\n\n{body}".rstrip()
        return self.send_message(text)

    def send_warning(self, title: str, body: str = "") -> bool:
        text = f"🟡 <b>{html.escape(title)}</b>\n\n{body}".rstrip()
        return self.send_message(text)

    def send_critical(self, title: str, body: str = "") -> bool:
        text = f"🔴 <b>{html.escape(title)}</b>\n\n{body}".rstrip()
        return self.send_message(text)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                operation, args, callback = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            result = None
            try:
                if operation == "send":
                    result = self.client.send_message(*args)
                elif operation == "edit":
                    result = self.client.edit_message(*args)
            except Exception as exc:
                self._log("warning", f"TELEGRAM_DISPATCH_FAILED operation={operation} error={type(exc).__name__}:{exc}")
            finally:
                if callback is not None:
                    try:
                        callback(result)
                    except Exception as exc:
                        self._log("warning", f"TELEGRAM_DISPATCH_CALLBACK_FAILED error={type(exc).__name__}:{exc}")
                self._queue.task_done()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)
