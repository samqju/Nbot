"""Authenticated Binance Futures mainnet user-stream foundation.

Phase 2.3 is observation-only. It manages the listen-key lifecycle, receives
private account events, exposes health/readiness, and stores a bounded event
queue. It contains no order, leverage, cancellation, or position-changing
operation.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Optional

import requests
import websocket

from execution.exceptions import OperationalExchangeError


class LiveUserStream:
    """Hardened, read-only user-data stream lifecycle."""

    def __init__(
        self,
        *,
        system_log,
        session,
        base_url: str,
        user_ws_url: str,
        websocket_factory: Callable[..., Any] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self.system_log = system_log
        self.session = session
        self.base_url = str(base_url).rstrip("/")
        self.user_ws_url = str(user_ws_url).rstrip("/")
        self.websocket_factory = websocket_factory or websocket.create_connection
        self.sleep_fn = sleep_fn or time.sleep

        self.ready_timeout_seconds = float(
            os.getenv("LIVE_USER_STREAM_READY_TIMEOUT", "20")
        )
        self.keepalive_interval_seconds = float(
            os.getenv("LIVE_USER_STREAM_KEEPALIVE_SECONDS", "1800")
        )
        self.reconnect_delay_seconds = float(
            os.getenv("LIVE_USER_STREAM_RECONNECT_SECONDS", "5")
        )
        self.recv_timeout_seconds = float(
            os.getenv("LIVE_USER_STREAM_RECV_TIMEOUT_SECONDS", "60")
        )
        self.event_queue_max = int(
            os.getenv("LIVE_USER_STREAM_EVENT_QUEUE_MAX", "1000")
        )

        if not self.user_ws_url.startswith("wss://"):
            raise RuntimeError("LIVE_USER_WS_URL_INVALID")
        if not (1 <= self.ready_timeout_seconds <= 120):
            raise RuntimeError("LIVE_USER_STREAM_READY_TIMEOUT_INVALID")
        if not (60 <= self.keepalive_interval_seconds <= 3500):
            raise RuntimeError("LIVE_USER_STREAM_KEEPALIVE_INVALID")
        if not (1 <= self.reconnect_delay_seconds <= 300):
            raise RuntimeError("LIVE_USER_STREAM_RECONNECT_INVALID")
        if not (5 <= self.recv_timeout_seconds <= 300):
            raise RuntimeError("LIVE_USER_STREAM_RECV_TIMEOUT_INVALID")
        if not (10 <= self.event_queue_max <= 10000):
            raise RuntimeError("LIVE_USER_STREAM_EVENT_QUEUE_MAX_INVALID")

        self._ready = threading.Event()
        self._stop = threading.Event()
        self._healthy = False
        self._thread: Optional[threading.Thread] = None
        self._ws = None
        self._listen_key: Optional[str] = None
        self._last_event_ts_ms: Optional[int] = None
        self._events: Deque[dict] = deque(maxlen=self.event_queue_max)
        self._lock = threading.Lock()

    def _listen_key_request(self, method: str, listen_key: str | None = None):
        params = {}
        if listen_key:
            params["listenKey"] = listen_key
        request = getattr(self.session, method)
        try:
            response = request(
                f"{self.base_url}/fapi/v1/listenKey",
                params=params,
                timeout=15,
            )
        except requests.RequestException as exc:
            raise OperationalExchangeError(
                f"LIVE_USER_STREAM_REST_ERROR | method={method.upper()} | {exc}"
            ) from exc
        if response.status_code != 200:
            raise OperationalExchangeError(
                "LIVE_USER_STREAM_REST_FAILED | "
                f"method={method.upper()} | status={response.status_code} | "
                f"body={response.text[:300]}"
            )
        return response.json()

    def _create_listen_key(self) -> str:
        data = self._listen_key_request("post")
        listen_key = str(data.get("listenKey", "")).strip()
        if not listen_key:
            raise OperationalExchangeError("LIVE_USER_STREAM_LISTEN_KEY_MISSING")
        return listen_key

    def _keepalive_listen_key(self, listen_key: str) -> None:
        self._listen_key_request("put", listen_key)

    def _close_listen_key(self, listen_key: str) -> None:
        try:
            self._listen_key_request("delete", listen_key)
        except Exception as exc:
            self.system_log.warning(
                f"LIVE_USER_STREAM_LISTEN_KEY_CLOSE_FAILED | error={exc}"
            )

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._ready.clear()
        self._healthy = False
        self._thread = threading.Thread(
            target=self._run,
            name="live-user-stream",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.system_log.info("LIVE_USER_STREAM_STOPPING")
        self._stop.set()
        self._ready.clear()
        self._healthy = False
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5)
        listen_key = self._listen_key
        self._listen_key = None
        if listen_key:
            self._close_listen_key(listen_key)
        self.system_log.info("LIVE_USER_STREAM_STOPPED")

    def wait_ready(self, timeout: float | None = None) -> bool:
        wait_timeout = (
            self.ready_timeout_seconds if timeout is None else float(timeout)
        )
        return self._ready.wait(wait_timeout)

    def is_healthy(self) -> bool:
        return self._healthy and self._ready.is_set() and not self._stop.is_set()

    def last_event_timestamp_ms(self) -> int | None:
        return self._last_event_ts_ms

    def drain_events(self, limit: int | None = None) -> list[dict]:
        with self._lock:
            count = len(self._events) if limit is None else max(0, int(limit))
            count = min(count, len(self._events))
            return [self._events.popleft() for _ in range(count)]

    def _record_event(self, event: dict) -> None:
        if not isinstance(event, dict):
            raise OperationalExchangeError("LIVE_USER_STREAM_EVENT_SCHEMA_INVALID")
        with self._lock:
            self._events.append(event)
        self._last_event_ts_ms = int(time.time() * 1000)

    def _run(self) -> None:
        while not self._stop.is_set():
            listen_key = None
            ws = None
            keepalive_deadline = 0.0
            try:
                listen_key = self._create_listen_key()
                self._listen_key = listen_key
                ws_url = f"{self.user_ws_url}/{listen_key}"
                self.system_log.info(
                    "LIVE_USER_STREAM_CONNECT_ATTEMPT | auth=LISTEN_KEY"
                )
                ws = self.websocket_factory(
                    ws_url,
                    timeout=self.recv_timeout_seconds,
                )
                self._ws = ws
                if hasattr(ws, "settimeout"):
                    ws.settimeout(self.recv_timeout_seconds)

                self._healthy = True
                self._ready.set()
                keepalive_deadline = (
                    time.monotonic() + self.keepalive_interval_seconds
                )
                self.system_log.info(
                    "LIVE_USER_STREAM_CONNECTED | mode=READ_ONLY"
                )

                while not self._stop.is_set():
                    if time.monotonic() >= keepalive_deadline:
                        self._keepalive_listen_key(listen_key)
                        keepalive_deadline = (
                            time.monotonic() + self.keepalive_interval_seconds
                        )
                        self.system_log.info("LIVE_USER_STREAM_KEEPALIVE_OK")

                    try:
                        message = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        if hasattr(ws, "ping"):
                            ws.ping()
                        continue

                    if not message:
                        raise OperationalExchangeError(
                            "LIVE_USER_STREAM_CLOSED_WITHOUT_MESSAGE"
                        )

                    event = json.loads(message)
                    self._record_event(event)

                    event_type = str(event.get("e", "UNKNOWN"))
                    if event_type == "listenKeyExpired":
                        raise OperationalExchangeError(
                            "LIVE_USER_STREAM_LISTEN_KEY_EXPIRED"
                        )

            except Exception as exc:
                self._healthy = False
                self._ready.clear()
                if self._stop.is_set():
                    self.system_log.info(
                        "LIVE_USER_STREAM_SHUTDOWN_OBSERVED"
                    )
                else:
                    self.system_log.error(
                        f"LIVE_USER_STREAM_RECONNECTING | error={exc}"
                    )
            finally:
                self._ws = None
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
                if listen_key:
                    self._close_listen_key(listen_key)
                self._listen_key = None

            if not self._stop.is_set():
                self.sleep_fn(self.reconnect_delay_seconds)
