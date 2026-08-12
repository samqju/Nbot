"""Read-only Binance USD-M Futures market-data client.

This client uses public REST and public WebSocket endpoints only. It has no
API credentials, signing code, private user stream, or order methods.
"""

import json
import os
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlparse

import requests
import websocket

from config import TRADING_ENV
from execution.exceptions import OperationalExchangeError


_TIMEOUT_SECONDS = 5

_LIVE_LEGACY_MARKET_WS_URL = (
    "wss://fstream.binance.com/ws/!ticker@arr"
)
_LIVE_PUBLIC_MARKET_WS_URL = (
    "wss://fstream.binance.com/market/ws/!ticker@arr"
)


@dataclass(frozen=True)
class PriceTick:
    symbol: str
    price: float
    timestamp: int


class BinanceMarketClient:
    """Public-only market client for TESTNET or LIVE Binance Futures."""

    def __init__(self, *, system_log):
        self.system_log = system_log
        self.environment = TRADING_ENV

        prefix = "LIVE" if self.environment == "LIVE" else "TESTNET"
        self.base_url = os.getenv(f"{prefix}_BASE_URL", "").strip()
        configured_market_ws_url = os.getenv(
            f"{prefix}_MARKET_WS_URL", ""
        ).strip()
        self.market_ws_url = self._normalize_market_ws_url(
            configured_market_ws_url
        )

        self._validate_endpoints()
        self.session = requests.Session()
        self._symbol_filters = {}
        self.execution_health_monitor = None
        self._market_integrity_lock = threading.Lock()
        self._market_integrity = {
            "transport_mode": "NOT_STARTED",
            "ws_connect_attempts": 0,
            "ws_connections": 0,
            "ws_disconnects": 0,
            "rest_fallback_activations": 0,
            "rest_batches": 0,
            "rest_poll_failures": 0,
            "last_ws_message_monotonic": None,
            "last_rest_batch_monotonic": None,
            "latest_ws_event_lag_ms": None,
            "max_ws_event_lag_ms": None,
        }

    def set_execution_health_monitor(self, monitor) -> None:
        """Attach optional execution-only measurement instrumentation."""
        self.execution_health_monitor = monitor

    def _record_market_integrity(
        self,
        *,
        mode: str | None = None,
        counter: str | None = None,
        ws_message: bool = False,
        rest_batch: bool = False,
        ws_event_lag_ms: int | None = None,
    ) -> None:
        """Update bounded public-market transport telemetry only."""
        now = time.perf_counter()
        try:
            with self._market_integrity_lock:
                if mode is not None:
                    self._market_integrity["transport_mode"] = str(mode)
                if counter is not None:
                    self._market_integrity[counter] = (
                        int(self._market_integrity.get(counter, 0)) + 1
                    )
                if ws_message:
                    self._market_integrity[
                        "last_ws_message_monotonic"
                    ] = now
                if rest_batch:
                    self._market_integrity[
                        "last_rest_batch_monotonic"
                    ] = now
                if ws_event_lag_ms is not None:
                    lag = int(ws_event_lag_ms)
                    self._market_integrity[
                        "latest_ws_event_lag_ms"
                    ] = lag
                    previous = self._market_integrity.get(
                        "max_ws_event_lag_ms"
                    )
                    if previous is None or lag > int(previous):
                        self._market_integrity[
                            "max_ws_event_lag_ms"
                        ] = lag
        except Exception:
            return

    def market_data_integrity_snapshot(self) -> dict:
        """Return read-only transport health for Observation telemetry."""
        try:
            now = time.perf_counter()
            with self._market_integrity_lock:
                data = dict(self._market_integrity)
            ws_seen = data.pop("last_ws_message_monotonic", None)
            rest_seen = data.pop("last_rest_batch_monotonic", None)
            data["last_ws_message_age_seconds"] = (
                None if ws_seen is None else max(0.0, now - float(ws_seen))
            )
            data["last_rest_batch_age_seconds"] = (
                None
                if rest_seen is None
                else max(0.0, now - float(rest_seen))
            )
            return data
        except Exception:
            return {}

    def _normalize_market_ws_url(self, configured_url: str) -> str:
        """Migrate the retired LIVE ticker path without touching TESTNET.

        Binance moved USD-M public market streams under the ``/market``
        namespace. Existing deployments may still have the old raw-stream URL
        in ``.env``; normalize that exact legacy value so the runtime starts
        receiving frames immediately after this code upgrade.
        """
        configured_url = str(configured_url or "").strip()
        if (
            self.environment == "LIVE"
            and configured_url.rstrip("/")
            == _LIVE_LEGACY_MARKET_WS_URL
        ):
            self.system_log.warning(
                "PUBLIC_WS_URL_MIGRATED | "
                f"environment=LIVE | old={configured_url} | "
                f"new={_LIVE_PUBLIC_MARKET_WS_URL}"
            )
            return _LIVE_PUBLIC_MARKET_WS_URL
        return configured_url

    def _validate_endpoints(self) -> None:
        if not self.base_url:
            raise RuntimeError(f"{self.environment}_BASE_URL_MISSING")
        if not self.market_ws_url:
            raise RuntimeError(f"{self.environment}_MARKET_WS_URL_MISSING")

        rest_host = (urlparse(self.base_url).hostname or "").lower()
        ws_host = (urlparse(self.market_ws_url).hostname or "").lower()

        expected = {
            "LIVE": ("fapi.binance.com", "fstream.binance.com"),
            "TESTNET": ("demo-fapi.binance.com", "stream.binancefuture.com"),
        }
        expected_rest, expected_ws = expected[self.environment]

        if rest_host != expected_rest:
            raise RuntimeError(
                f"{self.environment}_REST_HOST_UNEXPECTED | host={rest_host}"
            )
        if ws_host != expected_ws:
            raise RuntimeError(
                f"{self.environment}_MARKET_WS_HOST_UNEXPECTED | host={ws_host}"
            )

    def _public_get(self, path: str, params: dict | None = None):
        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                params=params or {},
                timeout=_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                raise OperationalExchangeError(
                    f"PUBLIC_REST_GET_FAILED | path={path} | "
                    f"status={response.status_code} | body={response.text[:300]}"
                )
            return response.json()
        except requests.exceptions.Timeout as exc:
            raise OperationalExchangeError("PUBLIC_REST_TIMEOUT") from exc
        except OperationalExchangeError:
            raise
        except Exception as exc:
            raise OperationalExchangeError(
                f"PUBLIC_REST_ERROR | path={path} | {exc}"
            ) from exc

    def connect(self) -> None:
        self._public_get("/fapi/v1/ping")
        self._symbol_filters = self._load_symbol_filters()
        if not self._symbol_filters:
            raise OperationalExchangeError("PUBLIC_SYMBOL_FILTERS_EMPTY")
        self.system_log.info(
            f"{self.environment}_PUBLIC_MARKET_CONNECT_OK | auth=NONE"
        )


    def preflight(self, *, symbol: str, candle_limit: int) -> dict:
        """Verify the public market-data functions required by paper trading."""
        symbol = str(symbol).strip().upper()
        if not symbol or not symbol.endswith("USDT"):
            raise ValueError("PUBLIC_PREFLIGHT_SYMBOL_INVALID")
        if not isinstance(candle_limit, int) or not (2 <= candle_limit <= 100):
            raise ValueError("PUBLIC_PREFLIGHT_CANDLE_LIMIT_INVALID")
        if symbol not in self._symbol_filters:
            raise OperationalExchangeError(
                f"PUBLIC_PREFLIGHT_SYMBOL_FILTER_MISSING | symbol={symbol}"
            )

        price = self.get_last_price(symbol)
        spread_pct = self.get_current_spread_pct(symbol=symbol)
        candles = self.get_historical_candles(
            symbol=symbol,
            interval="5m",
            limit=candle_limit,
        )
        if len(candles) < 1:
            raise OperationalExchangeError(
                f"PUBLIC_PREFLIGHT_CANDLES_EMPTY | symbol={symbol}"
            )

        report = {
            "environment": self.environment,
            "auth": "NONE",
            "symbol": symbol,
            "last_price": float(price),
            "spread_pct": float(spread_pct),
            "completed_candles": len(candles),
            "tick_size": float(self._symbol_filters[symbol]["tickSize"]),
        }
        self.system_log.info(
            "PUBLIC_MARKET_PREFLIGHT_OK | "
            f"environment={report['environment']} | auth=NONE | "
            f"symbol={symbol} | last_price={report['last_price']} | "
            f"spread_pct={report['spread_pct']:.8f} | "
            f"completed_candles={report['completed_candles']} | "
            f"tick_size={report['tick_size']}"
        )
        return report

    def disconnect(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass

    def _load_symbol_filters(self) -> dict:
        data = self._public_get("/fapi/v1/exchangeInfo")
        filters = {}
        for item in data.get("symbols", []):
            symbol = item.get("symbol")
            symbol_filters = item.get("filters", [])
            price_filter = next(
                (f for f in symbol_filters if f.get("filterType") == "PRICE_FILTER"),
                None,
            )
            if not symbol or not price_filter:
                continue
            try:
                tick_size = float(price_filter["tickSize"])
            except (KeyError, TypeError, ValueError):
                continue
            if tick_size > 0:
                filters[symbol] = {"tickSize": tick_size}
        return filters

    def quantize_price(self, symbol: str, price: float) -> float:
        item = self._symbol_filters.get(str(symbol).upper())
        if not item:
            raise OperationalExchangeError(
                f"SYMBOL_FILTERS_MISSING | symbol={symbol}"
            )
        price_dec = Decimal(str(price))
        tick_dec = Decimal(str(item["tickSize"]))
        quantized = (price_dec // tick_dec) * tick_dec
        return float(quantized.quantize(tick_dec, rounding=ROUND_DOWN))

    def position_price_stream(self, symbol: str):
        """Yield last-price ticks for exactly one Execution-owned symbol.

        A quiet symbol is not considered stale merely because its last traded
        price has not changed.  Liveness is instead determined by the dedicated
        symbol WebSocket connection itself.  Only when that connection times
        out or becomes unavailable do we poll public REST until the next
        WebSocket retry.
        """
        from config import (
            PAPER_REST_POLL_INTERVAL_SECONDS,
            PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS,
            PAPER_WS_RETRY_INTERVAL_SECONDS,
        )

        symbol = str(symbol or "").strip().upper()
        if not symbol or not symbol.endswith("USDT"):
            raise ValueError("PUBLIC_POSITION_STREAM_SYMBOL_INVALID")
        stream_url = self._position_stream_url(symbol)

        recovering_from_failure = False
        while True:
            ws = None
            received_first = False
            try:
                self.system_log.info(
                    "PUBLIC_POSITION_WS_CONNECT_ATTEMPT | "
                    f"environment={self.environment} | auth=NONE | "
                    f"symbol={symbol} | url={stream_url}"
                )
                ws = websocket.create_connection(
                    stream_url,
                    timeout=PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS,
                )
                if recovering_from_failure:
                    self.system_log.info(
                        "PUBLIC_POSITION_WS_RECOVERED | "
                        f"environment={self.environment} | auth=NONE | "
                        f"symbol={symbol}"
                    )
                    recovering_from_failure = False
                else:
                    self.system_log.info(
                        "PUBLIC_POSITION_WS_CONNECTED | "
                        f"environment={self.environment} | auth=NONE | "
                        f"symbol={symbol}"
                    )

                while True:
                    message = ws.recv()
                    tick = self._parse_ws_symbol_ticker_message(
                        message,
                        expected_symbol=symbol,
                    )
                    if not received_first:
                        received_first = True
                        self.system_log.info(
                            "PUBLIC_POSITION_WS_FIRST_TICK_OK | "
                            f"environment={self.environment} | auth=NONE | "
                            f"symbol={symbol}"
                        )
                    yield tick
            except websocket.WebSocketTimeoutException:
                recovering_from_failure = True
                self._record_position_ws_disconnect()
                phase = "ACTIVE" if received_first else "FIRST_TICK"
                self.system_log.warning(
                    "PUBLIC_POSITION_WS_TIMEOUT | "
                    f"environment={self.environment} | symbol={symbol} | "
                    f"phase={phase} | "
                    f"timeout_seconds={PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS}"
                )
            except OperationalExchangeError as exc:
                recovering_from_failure = True
                self._record_position_ws_disconnect()
                self.system_log.warning(
                    "PUBLIC_POSITION_WS_UNAVAILABLE | "
                    f"environment={self.environment} | symbol={symbol} | "
                    f"error={exc}"
                )
            except Exception as exc:
                recovering_from_failure = True
                self._record_position_ws_disconnect()
                self.system_log.warning(
                    "PUBLIC_POSITION_WS_UNAVAILABLE | "
                    f"environment={self.environment} | symbol={symbol} | "
                    f"error={type(exc).__name__}:{exc}"
                )
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

            yield from self._position_rest_fallback_ticks(
                symbol=symbol,
                poll_interval_seconds=PAPER_REST_POLL_INTERVAL_SECONDS,
                retry_after_seconds=PAPER_WS_RETRY_INTERVAL_SECONDS,
            )

    def _position_stream_url(self, symbol: str) -> str:
        token = "!ticker@arr"
        if token not in self.market_ws_url:
            raise RuntimeError(
                "PUBLIC_MARKET_WS_URL_STREAM_TOKEN_UNEXPECTED | "
                f"url={self.market_ws_url}"
            )
        return self.market_ws_url.replace(
            token,
            f"{str(symbol).lower()}@ticker",
            1,
        )

    @staticmethod
    def _parse_ws_symbol_ticker_message(
        message,
        *,
        expected_symbol: str,
    ) -> PriceTick:
        try:
            data = json.loads(message)
        except (TypeError, json.JSONDecodeError) as exc:
            raise OperationalExchangeError(
                "PUBLIC_POSITION_WS_JSON_INVALID"
            ) from exc
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            data = data["data"]
        if not isinstance(data, dict):
            raise OperationalExchangeError(
                "PUBLIC_POSITION_WS_SCHEMA_INVALID | expected=ticker_object"
            )
        symbol = str(data.get("s", "")).upper()
        if symbol != str(expected_symbol).upper():
            raise OperationalExchangeError(
                "PUBLIC_POSITION_WS_SYMBOL_MISMATCH | "
                f"expected={expected_symbol} | received={symbol or 'MISSING'}"
            )
        try:
            price = float(data.get("c", 0))
        except (TypeError, ValueError) as exc:
            raise OperationalExchangeError(
                f"PUBLIC_POSITION_WS_PRICE_INVALID | symbol={symbol}"
            ) from exc
        if price <= 0:
            raise OperationalExchangeError(
                f"PUBLIC_POSITION_WS_PRICE_INVALID | symbol={symbol}"
            )
        return PriceTick(
            symbol=symbol,
            price=price,
            timestamp=int(time.time() * 1000),
        )

    def _position_rest_fallback_ticks(
        self,
        *,
        symbol: str,
        poll_interval_seconds: float,
        retry_after_seconds: float,
    ):
        """Poll one symbol only while its dedicated WebSocket is unavailable."""
        self.system_log.warning(
            "PUBLIC_POSITION_REST_FALLBACK_ACTIVE | "
            f"environment={self.environment} | auth=NONE | "
            f"symbol={symbol} | poll_interval_seconds={poll_interval_seconds} | "
            f"ws_retry_seconds={retry_after_seconds}"
        )
        retry_deadline = time.monotonic() + retry_after_seconds
        while time.monotonic() < retry_deadline:
            cycle_started = time.monotonic()
            refresh_started = time.perf_counter()
            try:
                price = float(self.get_last_price(symbol))
            except OperationalExchangeError as exc:
                self._record_position_rest_result(
                    success=False,
                    elapsed_ms=(time.perf_counter() - refresh_started) * 1000.0,
                )
                self.system_log.warning(
                    "PUBLIC_POSITION_REST_POLL_FAILED | "
                    f"environment={self.environment} | symbol={symbol} | "
                    f"error={exc}"
                )
            else:
                self._record_position_rest_result(
                    success=True,
                    elapsed_ms=(time.perf_counter() - refresh_started) * 1000.0,
                )
                yield PriceTick(
                    symbol=symbol,
                    price=price,
                    timestamp=int(time.time() * 1000),
                )

            elapsed = time.monotonic() - cycle_started
            sleep_for = max(0.0, poll_interval_seconds - elapsed)
            if sleep_for:
                time.sleep(sleep_for)

        self.system_log.info(
            "PUBLIC_POSITION_WS_RETRY_DUE | "
            f"environment={self.environment} | auth=NONE | symbol={symbol}"
        )

    def _record_position_ws_disconnect(self) -> None:
        monitor = self.execution_health_monitor
        if monitor is not None:
            monitor.increment("position_ws_disconnects")

    def _record_position_rest_result(
        self,
        *,
        success: bool,
        elapsed_ms: float,
    ) -> None:
        monitor = self.execution_health_monitor
        if monitor is None:
            return
        monitor.increment(
            "position_rest_fallback_success"
            if success
            else "position_rest_fallback_failure"
        )
        monitor.observe_ms("position_rest_fallback_ms", elapsed_ms)

    def price_stream(self):
        """Yield public futures ticks with a fail-safe REST fallback.

        Binance WebSocket delivery can be unavailable on some VPS network
        paths even when the TLS handshake succeeds. The client therefore
        waits only for a bounded first tick, then polls the public all-symbol
        ticker endpoint and periodically retries WebSocket delivery.
        """
        from config import (
            PAPER_REST_POLL_INTERVAL_SECONDS,
            PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS,
            PAPER_WS_RETRY_INTERVAL_SECONDS,
        )

        while True:
            ws = None
            try:
                self._record_market_integrity(
                    mode="WS_CONNECTING",
                    counter="ws_connect_attempts",
                )
                self.system_log.info(
                    "PUBLIC_WS_CONNECT_ATTEMPT | "
                    f"environment={self.environment} | auth=NONE | "
                    f"url={self.market_ws_url}"
                )
                ws = websocket.create_connection(
                    self.market_ws_url,
                    timeout=PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS,
                )
                self._record_market_integrity(
                    mode="WEBSOCKET",
                    counter="ws_connections",
                )
                self.system_log.info(
                    "PUBLIC_WS_CONNECTED | "
                    f"environment={self.environment} | auth=NONE"
                )
                message = ws.recv()
                first_ticks = self._parse_ws_ticker_message(message)
                if not first_ticks:
                    raise OperationalExchangeError(
                        "PUBLIC_WS_FIRST_TICK_EMPTY"
                    )
                self.system_log.info(
                    "PUBLIC_WS_FIRST_TICK_OK | "
                    f"environment={self.environment} | auth=NONE | "
                    f"symbols={len(first_ticks)}"
                )
                for tick in first_ticks:
                    yield tick

                while True:
                    message = ws.recv()
                    for tick in self._parse_ws_ticker_message(message):
                        yield tick
            except websocket.WebSocketTimeoutException:
                self.system_log.warning(
                    "PUBLIC_WS_FIRST_TICK_TIMEOUT | "
                    f"environment={self.environment} | "
                    f"timeout_seconds={PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS}"
                )
            except OperationalExchangeError as exc:
                self.system_log.warning(
                    "PUBLIC_WS_UNAVAILABLE | "
                    f"environment={self.environment} | error={exc}"
                )
            except Exception as exc:
                self.system_log.warning(
                    "PUBLIC_WS_UNAVAILABLE | "
                    f"environment={self.environment} | "
                    f"error={type(exc).__name__}:{exc}"
                )
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

            self._record_market_integrity(
                counter="ws_disconnects",
            )
            yield from self._rest_fallback_ticks(
                poll_interval_seconds=PAPER_REST_POLL_INTERVAL_SECONDS,
                retry_after_seconds=PAPER_WS_RETRY_INTERVAL_SECONDS,
            )

    def _parse_ws_ticker_message(self, message) -> list[PriceTick]:
        try:
            data = json.loads(message)
        except (TypeError, json.JSONDecodeError) as exc:
            raise OperationalExchangeError("PUBLIC_WS_JSON_INVALID") from exc
        if not isinstance(data, list):
            raise OperationalExchangeError(
                "PUBLIC_WS_SCHEMA_INVALID | expected=ticker_array"
            )
        timestamp = int(time.time() * 1000)
        ticks = []
        event_times = []
        for row in data:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("s", "")).upper()
            event_time = row.get("E")
            if (
                not isinstance(event_time, bool)
                and isinstance(event_time, (int, float))
                and int(event_time) > 0
            ):
                event_times.append(int(event_time))
            if not symbol.endswith("USDT"):
                continue
            try:
                price = float(row.get("c", 0))
            except (TypeError, ValueError):
                continue
            if price > 0:
                ticks.append(
                    PriceTick(symbol=symbol, price=price, timestamp=timestamp)
                )
        event_lag_ms = (
            None if not event_times else timestamp - max(event_times)
        )
        self._record_market_integrity(
            mode="WEBSOCKET",
            ws_message=True,
            ws_event_lag_ms=event_lag_ms,
        )
        return ticks

    def _rest_fallback_ticks(
        self,
        *,
        poll_interval_seconds: float,
        retry_after_seconds: float,
    ):
        self._record_market_integrity(
            mode="REST_FALLBACK",
            counter="rest_fallback_activations",
        )
        self.system_log.warning(
            "PUBLIC_MARKET_REST_FALLBACK_ACTIVE | "
            f"environment={self.environment} | auth=NONE | "
            f"poll_interval_seconds={poll_interval_seconds} | "
            f"ws_retry_seconds={retry_after_seconds}"
        )
        retry_deadline = time.monotonic() + retry_after_seconds
        first_batch = True
        while time.monotonic() < retry_deadline:
            started = time.monotonic()
            try:
                data = self._public_get("/fapi/v1/ticker/price")
                ticks = self._parse_rest_price_rows(data)
                if not ticks:
                    raise OperationalExchangeError(
                        "PUBLIC_REST_TICK_BATCH_EMPTY"
                    )
                self._record_market_integrity(
                    mode="REST_FALLBACK",
                    counter="rest_batches",
                    rest_batch=True,
                )
                if first_batch:
                    self.system_log.info(
                        "PUBLIC_REST_FIRST_TICK_OK | "
                        f"environment={self.environment} | auth=NONE | "
                        f"symbols={len(ticks)}"
                    )
                    first_batch = False
                for tick in ticks:
                    yield tick
            except OperationalExchangeError as exc:
                self._record_market_integrity(
                    mode="REST_FALLBACK",
                    counter="rest_poll_failures",
                )
                self.system_log.warning(
                    "PUBLIC_REST_POLL_FAILED | "
                    f"environment={self.environment} | error={exc}"
                )

            elapsed = time.monotonic() - started
            sleep_for = max(0.0, poll_interval_seconds - elapsed)
            if sleep_for:
                time.sleep(sleep_for)

        self._record_market_integrity(mode="WS_RETRY_DUE")
        self.system_log.info(
            "PUBLIC_WS_RETRY_DUE | "
            f"environment={self.environment} | auth=NONE"
        )

    @staticmethod
    def _parse_rest_price_rows(data) -> list[PriceTick]:
        if not isinstance(data, list):
            raise OperationalExchangeError(
                "PUBLIC_REST_TICK_SCHEMA_INVALID | expected=price_array"
            )
        timestamp = int(time.time() * 1000)
        ticks = []
        for row in data:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol", "")).upper()
            if not symbol.endswith("USDT"):
                continue
            try:
                price = float(row.get("price", 0))
            except (TypeError, ValueError):
                continue
            if price > 0:
                ticks.append(
                    PriceTick(symbol=symbol, price=price, timestamp=timestamp)
                )
        return ticks

    def get_historical_candles(self, *, symbol: str, interval: str, limit: int):
        data = self._public_get(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        now_ms = int(time.time() * 1000)
        candles = []
        for candle in data:
            if not isinstance(candle, (list, tuple)) or len(candle) < 7:
                raise OperationalExchangeError(
                    f"HISTORICAL_CANDLE_SCHEMA_INVALID | symbol={symbol}"
                )
            open_time = int(candle[0])
            close_time = int(candle[6])
            if close_time >= now_ms:
                continue
            o, h, l, c = map(float, candle[1:5])
            if min(o, h, l, c) <= 0 or h < max(o, c) or l > min(o, c):
                raise OperationalExchangeError(
                    f"HISTORICAL_CANDLE_VALUES_INVALID | symbol={symbol} | "
                    f"open_time={open_time}"
                )
            candles.append((open_time, o, h, l, c))
        return candles

    def get_market_context_rows(self, *, symbols) -> dict[str, dict]:
        """Return bulk public 24h/liquidity measurements for Observation.

        This is deliberately a read-only bulk operation: one 24h ticker read
        and one book-ticker read cover the whole requested observation set.
        """
        requested = {
            str(symbol).strip().upper()
            for symbol in symbols
            if str(symbol).strip()
        }
        if not requested:
            raise ValueError("MARKET_CONTEXT_SYMBOLS_EMPTY")

        tickers = self._public_get("/fapi/v1/ticker/24hr")
        books = self._public_get("/fapi/v1/ticker/bookTicker")
        if not isinstance(tickers, list) or not isinstance(books, list):
            raise OperationalExchangeError(
                "MARKET_CONTEXT_BULK_SCHEMA_INVALID"
            )

        book_by_symbol = {
            str(row.get("symbol", "")).upper(): row
            for row in books
            if isinstance(row, dict)
        }
        rows = {}
        for ticker in tickers:
            if not isinstance(ticker, dict):
                continue
            symbol = str(ticker.get("symbol", "")).upper()
            if symbol not in requested:
                continue
            book = book_by_symbol.get(symbol)
            if not isinstance(book, dict):
                continue
            try:
                last_price = float(ticker.get("lastPrice", 0))
                change_pct = float(ticker.get("priceChangePercent", 0))
                quote_volume = float(ticker.get("quoteVolume", 0))
                bid = float(book.get("bidPrice", 0))
                ask = float(book.get("askPrice", 0))
            except (TypeError, ValueError):
                continue
            if (
                last_price <= 0
                or quote_volume < 0
                or bid <= 0
                or ask <= 0
                or ask < bid
            ):
                continue
            mid = (bid + ask) / 2.0
            rows[symbol] = {
                "last_price": last_price,
                "price_change_pct_24h": change_pct,
                "quote_volume_usd": quote_volume,
                "spread_pct": ((ask - bid) / mid) * 100.0,
            }
        return rows

    def get_virtual_cost_evidence_rows(
        self,
        *,
        symbols,
        start_ms: int,
        end_ms: int,
    ) -> dict:
        """Return one bulk spread snapshot plus actual funding history.

        Spread comes from the public all-symbol book ticker. Funding comes
        from Binance's public funding-rate history over the requested time
        window. The funding history is marked incomplete when Binance returns
        the endpoint limit, because a truncated response must never be treated
        as proof that no additional funding event occurred.
        """
        requested = {
            str(symbol).strip().upper()
            for symbol in symbols
            if str(symbol).strip()
        }
        if not requested:
            raise ValueError("VIRTUAL_COST_EVIDENCE_SYMBOLS_EMPTY")
        start_ms = int(start_ms)
        end_ms = int(end_ms)
        if start_ms < 0 or end_ms <= 0 or start_ms > end_ms:
            raise ValueError("VIRTUAL_COST_EVIDENCE_WINDOW_INVALID")

        books = self._public_get("/fapi/v1/ticker/bookTicker")
        funding_limit = 1000
        funding = []
        funding_history_complete = True
        funding_parse_errors = 0
        funding_cursor = start_ms
        funding_pages = 0
        max_funding_pages = 8
        seen_funding_rows = set()
        while funding_cursor <= end_ms:
            page = self._public_get(
                "/fapi/v1/fundingRate",
                {
                    "startTime": funding_cursor,
                    "endTime": end_ms,
                    "limit": funding_limit,
                },
            )
            funding_pages += 1
            if not isinstance(page, list):
                raise OperationalExchangeError(
                    "VIRTUAL_COST_EVIDENCE_BULK_SCHEMA_INVALID"
                )
            if not page:
                break

            page_times = []
            for row in page:
                if not isinstance(row, dict):
                    funding_parse_errors += 1
                    continue
                try:
                    funding_time = int(row.get("fundingTime"))
                except (TypeError, ValueError):
                    funding_parse_errors += 1
                    continue
                page_times.append(funding_time)
                identity = (
                    str(row.get("symbol") or "").upper(),
                    funding_time,
                    str(row.get("fundingRate") or ""),
                    str(row.get("markPrice") or ""),
                    str(row.get("rateType") or ""),
                )
                if identity in seen_funding_rows:
                    continue
                seen_funding_rows.add(identity)
                funding.append(row)

            if len(page) < funding_limit:
                break
            if not page_times or funding_pages >= max_funding_pages:
                funding_history_complete = False
                break
            next_cursor = max(page_times)
            if next_cursor < funding_cursor:
                funding_history_complete = False
                break
            # Repeat the last timestamp rather than adding one millisecond so
            # a page boundary cannot skip other symbols funded at that exact
            # time. Exact duplicate rows are removed above.
            if next_cursor == funding_cursor and len(page) >= funding_limit:
                funding_history_complete = False
                break
            funding_cursor = next_cursor

        if not isinstance(books, list):
            raise OperationalExchangeError(
                "VIRTUAL_COST_EVIDENCE_BULK_SCHEMA_INVALID"
            )

        spread_by_symbol = {}
        for row in books:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol", "")).upper()
            if symbol not in requested:
                continue
            try:
                bid = float(row.get("bidPrice", 0))
                ask = float(row.get("askPrice", 0))
            except (TypeError, ValueError):
                continue
            if bid <= 0 or ask <= 0 or ask < bid:
                continue
            mid = (bid + ask) / 2.0
            spread_by_symbol[symbol] = ((ask - bid) / mid) * 100.0

        funding_events_by_symbol = {}
        for row in funding:
            if not isinstance(row, dict):
                funding_parse_errors += 1
                continue
            symbol = str(row.get("symbol", "")).upper()
            if symbol not in requested:
                continue
            try:
                rate = float(row.get("fundingRate"))
                funding_time = int(row.get("fundingTime"))
                mark_price = float(row.get("markPrice"))
            except (TypeError, ValueError):
                funding_parse_errors += 1
                continue
            if funding_time <= 0 or mark_price <= 0:
                funding_parse_errors += 1
                continue
            funding_events_by_symbol.setdefault(symbol, []).append({
                "funding_time": funding_time,
                "funding_rate": rate,
                "mark_price": mark_price,
                "rate_type": str(row.get("rateType") or "Regular"),
            })

        for events in funding_events_by_symbol.values():
            events.sort(key=lambda item: item["funding_time"])

        return {
            "spread_by_symbol": spread_by_symbol,
            "funding_events_by_symbol": funding_events_by_symbol,
            "funding_coverage_start_ms": start_ms,
            "funding_coverage_end_ms": end_ms,
            "funding_history_complete": (
                funding_history_complete and funding_parse_errors == 0
            ),
            "funding_rows_returned": len(funding),
            "funding_pages": funding_pages,
            "funding_parse_errors": funding_parse_errors,
        }

    def get_current_spread_pct(self, *, symbol: str) -> float:
        data = self._public_get("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        try:
            bid = float(data["bidPrice"])
            ask = float(data["askPrice"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OperationalExchangeError(
                f"BOOK_TICKER_SCHEMA_INVALID | symbol={symbol}"
            ) from exc
        if bid <= 0 or ask <= 0:
            return 999.0
        mid = (bid + ask) / 2.0
        return ((ask - bid) / mid) * 100.0

    def get_last_price(self, symbol: str) -> float:
        data = self._public_get("/fapi/v1/ticker/price", {"symbol": symbol})
        try:
            price = float(data["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OperationalExchangeError(
                f"LAST_PRICE_SCHEMA_INVALID | symbol={symbol}"
            ) from exc
        if price <= 0:
            raise OperationalExchangeError(
                f"LAST_PRICE_VALUE_INVALID | symbol={symbol}"
            )
        return price
