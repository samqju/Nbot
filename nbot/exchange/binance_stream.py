"""WebSocket-first Binance USD-M public market data.

The hot path is WebSocket owned. REST is retained only for clock/bootstrap and
explicit recovery of an already-open position. New entries never silently fall
back to REST market truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import math
import re
import threading
import time
from typing import Any, Callable

from nbot.common.market import AggTrade
from nbot.exchange.binance_public import (
    BinanceLivePublicMarketConfig,
    BinanceLivePublicMarketData,
)
from nbot.exchange.contracts import Quote

LOGGER = logging.getLogger("nbot.v3.binance_stream")
LIVE_PUBLIC_WS_URL = "wss://fstream.binance.com/ws"
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,40}$")


class BinanceLiveStreamError(RuntimeError):
    """Fresh WebSocket market truth is unavailable or malformed."""


@dataclass(frozen=True, slots=True)
class BinanceLiveStreamConfig:
    ws_url: str = LIVE_PUBLIC_WS_URL
    first_event_timeout_seconds: float = 4.0
    max_quote_age_ms: int = 2_000
    reconnect_min_seconds: float = 0.5
    reconnect_max_seconds: float = 15.0
    ping_interval_seconds: float = 15.0
    ping_timeout_seconds: float = 10.0
    max_symbols: int = 200
    enable_book_ticker: bool = True
    enable_agg_trade: bool = False

    def validate(self) -> None:
        if self.ws_url != LIVE_PUBLIC_WS_URL:
            raise ValueError("LIVE_STREAM_BINANCE_HOST_NOT_PINNED")
        if not 0.1 <= float(self.first_event_timeout_seconds) <= 30.0:
            raise ValueError("LIVE_STREAM_FIRST_EVENT_TIMEOUT_INVALID")
        if isinstance(self.max_quote_age_ms, bool) or not 100 <= int(self.max_quote_age_ms) <= 30_000:
            raise ValueError("LIVE_STREAM_MAX_QUOTE_AGE_INVALID")
        if not 0.1 <= float(self.reconnect_min_seconds) <= float(self.reconnect_max_seconds) <= 60.0:
            raise ValueError("LIVE_STREAM_RECONNECT_INVALID")
        if not 1.0 <= float(self.ping_interval_seconds) <= 60.0:
            raise ValueError("LIVE_STREAM_PING_INTERVAL_INVALID")
        if not 0.5 <= float(self.ping_timeout_seconds) < float(self.ping_interval_seconds):
            raise ValueError("LIVE_STREAM_PING_TIMEOUT_INVALID")
        if isinstance(self.max_symbols, bool) or not 1 <= int(self.max_symbols) <= 500:
            raise ValueError("LIVE_STREAM_SYMBOL_LIMIT_INVALID")
        if not self.enable_book_ticker and not self.enable_agg_trade:
            raise ValueError("LIVE_STREAM_NO_STREAMS_ENABLED")


@dataclass(frozen=True, slots=True)
class QuoteUpdate:
    sequence: int
    quote: Quote
    received_at_ms: int


def _default_ws_app_factory(url: str, **callbacks: Any):
    try:
        import websocket  # type: ignore
    except Exception as exc:  # pragma: no cover - deployment dependency
        raise BinanceLiveStreamError(
            "LIVE_STREAM_DEPENDENCY_MISSING:install requirements.txt"
        ) from exc
    return websocket.WebSocketApp(url, **callbacks)


class BinanceLiveWebSocketMarketData:
    """Threaded dynamic-subscription market stream.

    bookTicker is the executable bid/ask source for Execution. aggTrade is the
    chronological trade-price source for counterfactual research. Both can share
    this implementation while selecting only the stream kinds each process needs.
    """

    def __init__(
        self,
        config: BinanceLiveStreamConfig | None = None,
        *,
        rest_recovery: BinanceLivePublicMarketData | None = None,
        ws_app_factory: Callable[..., Any] | None = None,
        now_ms_fn: Callable[[], int] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
    ) -> None:
        self.config = config or BinanceLiveStreamConfig()
        self.config.validate()
        self._rest = rest_recovery or BinanceLivePublicMarketData(
            BinanceLivePublicMarketConfig()
        )
        self._ws_app_factory = ws_app_factory or _default_ws_app_factory
        self._now_ms = now_ms_fn or (lambda: int(time.time() * 1000))
        self._monotonic = monotonic_fn or time.monotonic
        self._condition = threading.Condition(threading.RLock())
        self._connected = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws: Any | None = None
        self._symbols: set[str] = set()
        self._latest_quotes: dict[str, QuoteUpdate] = {}
        self._last_quote_read_sequence: dict[str, int] = {}
        self._sequence = 0
        self._request_id = 0
        self._trade_listeners: list[Callable[[AggTrade], None]] = []
        self._status_listeners: list[Callable[[str, int], None]] = []
        self._last_error: str | None = None
        self._connection_generation = 0

    @staticmethod
    def _symbol(value: str) -> str:
        symbol = str(value).strip().upper()
        if _SYMBOL_RE.fullmatch(symbol) is None:
            raise ValueError("LIVE_STREAM_SYMBOL_INVALID")
        return symbol

    def add_trade_listener(self, listener: Callable[[AggTrade], None]) -> None:
        if not callable(listener):
            raise TypeError("LIVE_STREAM_TRADE_LISTENER_INVALID")
        with self._condition:
            self._trade_listeners.append(listener)

    def add_status_listener(self, listener: Callable[[str, int], None]) -> None:
        if not callable(listener):
            raise TypeError("LIVE_STREAM_STATUS_LISTENER_INVALID")
        with self._condition:
            self._status_listeners.append(listener)

    def connect(self) -> None:
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._last_error = None
        # REST is deliberately only a bootstrap clock/recovery channel.
        self._rest.connect()
        thread = threading.Thread(
            target=self._run, name="nbot-binance-live-stream", daemon=True
        )
        with self._condition:
            self._thread = thread
        thread.start()
        if not self._connected.wait(float(self.config.first_event_timeout_seconds)):
            self.disconnect()
            raise BinanceLiveStreamError("LIVE_STREAM_CONNECT_TIMEOUT")

    def disconnect(self) -> None:
        self._stop.set()
        with self._condition:
            ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._connected.clear()
        try:
            self._rest.disconnect()
        finally:
            with self._condition:
                self._ws = None
                self._thread = None

    def is_healthy(self) -> bool:
        thread = self._thread
        return bool(self._connected.is_set() and thread is not None and thread.is_alive())

    def status(self) -> dict[str, Any]:
        with self._condition:
            now = int(self._now_ms())
            ages = {
                symbol: max(0, now - int(update.quote.timestamp_ms))
                for symbol, update in self._latest_quotes.items()
            }
            return {
                "transport": "BINANCE_WSS_PRIMARY",
                "connected": self._connected.is_set(),
                "connection_generation": self._connection_generation,
                "subscriptions": sorted(self._symbols),
                "quote_age_ms": ages,
                "last_error": self._last_error,
                "rest_role": "BOOTSTRAP_AND_OPEN_POSITION_RECOVERY_ONLY",
            }

    def subscribe(self, symbol: str) -> None:
        symbol = self._symbol(symbol)
        send = False
        with self._condition:
            if symbol not in self._symbols:
                if len(self._symbols) >= int(self.config.max_symbols):
                    raise BinanceLiveStreamError("LIVE_STREAM_SYMBOL_LIMIT_EXCEEDED")
                self._symbols.add(symbol)
                send = self._connected.is_set() and self._ws is not None
        if send:
            self._send_subscriptions((symbol,))

    def quote(self, symbol: str) -> Quote:
        """Return a newly observed fresh WSS bid/ask.

        EntryLifecycle deliberately asks more than once (initial quote, stop
        feasibility, final pre-order recheck). Reusing the same cached update
        would weaken that final recheck, so ordinary quote reads advance past
        the last update returned by this method. Open-position management uses
        wait_quote() with its own explicit sequence cursor.
        """
        symbol = self._symbol(symbol)
        with self._condition:
            previous = int(self._last_quote_read_sequence.get(symbol, 0))
        update = self.wait_quote(
            symbol,
            after_sequence=previous,
            timeout_seconds=float(self.config.first_event_timeout_seconds),
        )
        with self._condition:
            self._last_quote_read_sequence[symbol] = max(
                int(self._last_quote_read_sequence.get(symbol, 0)),
                int(update.sequence),
            )
        return update.quote

    def wait_quote(
        self,
        symbol: str,
        *,
        after_sequence: int = 0,
        timeout_seconds: float | None = None,
    ) -> QuoteUpdate:
        if not self.config.enable_book_ticker:
            raise BinanceLiveStreamError("LIVE_STREAM_BOOK_TICKER_DISABLED")
        symbol = self._symbol(symbol)
        self.subscribe(symbol)
        timeout = (
            float(self.config.first_event_timeout_seconds)
            if timeout_seconds is None else float(timeout_seconds)
        )
        if timeout <= 0:
            raise ValueError("LIVE_STREAM_WAIT_TIMEOUT_INVALID")
        deadline = self._monotonic() + timeout
        with self._condition:
            while True:
                update = self._latest_quotes.get(symbol)
                now = int(self._now_ms())
                if (
                    update is not None
                    and update.sequence > int(after_sequence)
                    and 0 <= now - int(update.quote.timestamp_ms) <= int(self.config.max_quote_age_ms)
                ):
                    return update
                remaining = deadline - self._monotonic()
                if remaining <= 0:
                    reason = self._last_error or "NO_FRESH_BOOK_TICKER"
                    raise BinanceLiveStreamError(
                        f"LIVE_STREAM_QUOTE_TIMEOUT:{symbol}:{reason}"
                    )
                self._condition.wait(min(remaining, 0.25))

    def recovery_quote(self, symbol: str) -> Quote:
        """Explicit REST recovery for an already-open position only."""
        return self._rest.quote(self._symbol(symbol))

    def _streams_for(self, symbol: str) -> list[str]:
        base = symbol.lower()
        streams: list[str] = []
        if self.config.enable_book_ticker:
            streams.append(f"{base}@bookTicker")
        if self.config.enable_agg_trade:
            streams.append(f"{base}@aggTrade")
        return streams

    def _send_subscriptions(self, symbols: tuple[str, ...] | list[str]) -> None:
        params = [stream for symbol in symbols for stream in self._streams_for(symbol)]
        if not params:
            return
        with self._condition:
            ws = self._ws
            if ws is None or not self._connected.is_set():
                return
            self._request_id += 1
            request_id = self._request_id
        try:
            ws.send(json.dumps({"method": "SUBSCRIBE", "params": params, "id": request_id}))
        except Exception as exc:
            with self._condition:
                self._last_error = f"SUBSCRIBE:{type(exc).__name__}"
            raise BinanceLiveStreamError("LIVE_STREAM_SUBSCRIBE_FAILED") from exc

    def _notify_status(self, state: str) -> None:
        with self._condition:
            listeners = tuple(self._status_listeners)
        at_ms = int(self._now_ms())
        for listener in listeners:
            try:
                listener(state, at_ms)
            except Exception:
                LOGGER.exception("LIVE_STREAM_STATUS_LISTENER_FAILED")

    def _on_open(self, ws: Any) -> None:
        with self._condition:
            self._ws = ws
            self._connection_generation += 1
            self._last_error = None
            symbols = tuple(sorted(self._symbols))
            self._connected.set()
            self._condition.notify_all()
        if symbols:
            self._send_subscriptions(symbols)
        self._notify_status("CONNECTED")

    def _on_close(self, _ws: Any, _code: Any = None, _message: Any = None) -> None:
        self._connected.clear()
        with self._condition:
            self._condition.notify_all()
        self._notify_status("DISCONNECTED")

    def _on_error(self, _ws: Any, error: Any) -> None:
        with self._condition:
            self._last_error = f"{type(error).__name__}:{str(error)[:160]}"
            self._condition.notify_all()

    def _on_message(self, _ws: Any, message: str) -> None:
        try:
            payload = json.loads(message)
            if not isinstance(payload, dict):
                raise ValueError("PAYLOAD_NOT_OBJECT")
            if "result" in payload and "id" in payload:
                return
            data = payload.get("data", payload)
            if not isinstance(data, dict):
                raise ValueError("DATA_NOT_OBJECT")
            event = data.get("e")
            if event == "bookTicker":
                self._accept_book_ticker(data)
            elif event == "aggTrade":
                self._accept_agg_trade(data)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            with self._condition:
                self._last_error = f"MESSAGE:{type(exc).__name__}:{str(exc)[:120]}"
            LOGGER.warning("LIVE_STREAM_INVALID_MESSAGE error=%s", exc)

    def _accept_book_ticker(self, data: dict[str, Any]) -> None:
        symbol = self._symbol(str(data["s"]))
        bid, ask = float(data["b"]), float(data["a"])
        timestamp_ms = int(data.get("E") or data.get("T") or 0)
        quote = Quote(symbol=symbol, bid=bid, ask=ask, timestamp_ms=timestamp_ms)
        now = int(self._now_ms())
        if timestamp_ms > now + 5_000:
            raise ValueError("BOOK_TICKER_FUTURE")
        with self._condition:
            previous = self._latest_quotes.get(symbol)
            if previous is not None and timestamp_ms < previous.quote.timestamp_ms:
                return
            self._sequence += 1
            self._latest_quotes[symbol] = QuoteUpdate(self._sequence, quote, now)
            self._condition.notify_all()

    def _accept_agg_trade(self, data: dict[str, Any]) -> None:
        trade = AggTrade(
            symbol=self._symbol(str(data["s"])),
            price=float(data["p"]),
            quantity=float(data["q"]),
            event_time_ms=int(data["E"]),
            trade_time_ms=int(data["T"]),
            aggregate_trade_id=int(data["a"]),
            first_trade_id=int(data["f"]),
            last_trade_id=int(data["l"]),
            buyer_is_maker=bool(data["m"]),
        )
        with self._condition:
            listeners = tuple(self._trade_listeners)
        for listener in listeners:
            try:
                listener(trade)
            except Exception:
                LOGGER.exception(
                    "LIVE_STREAM_TRADE_LISTENER_FAILED symbol=%s trade_id=%s",
                    trade.symbol, trade.aggregate_trade_id,
                )

    def _run(self) -> None:
        backoff = float(self.config.reconnect_min_seconds)
        while not self._stop.is_set():
            try:
                app = self._ws_app_factory(
                    self.config.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                with self._condition:
                    self._ws = app
                app.run_forever(
                    ping_interval=float(self.config.ping_interval_seconds),
                    ping_timeout=float(self.config.ping_timeout_seconds),
                )
            except Exception as exc:
                with self._condition:
                    self._last_error = f"RUN:{type(exc).__name__}:{str(exc)[:160]}"
                    self._condition.notify_all()
            finally:
                if self._connected.is_set():
                    self._on_close(self._ws)
            if self._stop.is_set():
                break
            if self._stop.wait(backoff):
                break
            backoff = min(float(self.config.reconnect_max_seconds), backoff * 2.0)
