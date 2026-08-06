"""Read-only Binance USD-M Futures market-data client.

This client uses public REST and public WebSocket endpoints only. It has no
API credentials, signing code, private user stream, or order methods.
"""

import json
import os
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
                self.system_log.info(
                    "PUBLIC_WS_CONNECT_ATTEMPT | "
                    f"environment={self.environment} | auth=NONE | "
                    f"url={self.market_ws_url}"
                )
                ws = websocket.create_connection(
                    self.market_ws_url,
                    timeout=PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS,
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
        for row in data:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("s", "")).upper()
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
        return ticks

    def _rest_fallback_ticks(
        self,
        *,
        poll_interval_seconds: float,
        retry_after_seconds: float,
    ):
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
                self.system_log.warning(
                    "PUBLIC_REST_POLL_FAILED | "
                    f"environment={self.environment} | error={exc}"
                )

            elapsed = time.monotonic() - started
            sleep_for = max(0.0, poll_interval_seconds - elapsed)
            if sleep_for:
                time.sleep(sleep_for)

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
