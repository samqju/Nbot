"""Credential-free Binance USD-M public REST client for NBOT V3.3.

This module is evidence-only.  It never accepts API credentials and never
calls private/account/order endpoints.  It implements the PublicMarketClient
contract using the canonical LIVE or Testnet/demo public base URL already
validated by ObservationConfig.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import ObservationConfig
from .models import Candle, FundingEvent, SourceCapture, UniverseCapture, UniverseRow, spread_pct


USER_AGENT = "NBOT-V3-Observer/3.3.2"
MAX_KLINE_ROWS = 1500
MAX_FUNDING_ROWS = 1000


class BinancePublicMarketError(RuntimeError):
    """Public market data could not be obtained or proven valid."""


class BinanceUsdMPublicClient:
    """Credential-free Binance USD-M Futures public REST implementation."""

    def __init__(
        self,
        config: ObservationConfig,
        *,
        urlopen_fn: Callable[..., Any] = urlopen,
        local_time_ms_fn: Callable[[], int] | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self._urlopen = urlopen_fn
        self._local_time_ms_fn = local_time_ms_fn or (lambda: int(time.time() * 1000))

    def local_time_ms(self) -> int:
        value = int(self._local_time_ms_fn())
        if value < 0:
            raise BinancePublicMarketError("NBOT_OBSERVATION_LOCAL_TIME_INVALID")
        return value

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        if not path.startswith("/fapi/"):
            raise BinancePublicMarketError("NBOT_OBSERVATION_PUBLIC_PATH_INVALID")
        query = urlencode(sorted((params or {}).items()))
        url = f"{self.config.binance_public_base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            raise BinancePublicMarketError(
                f"NBOT_OBSERVATION_PUBLIC_HTTP_ERROR:{path}:{exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise BinancePublicMarketError(
                f"NBOT_OBSERVATION_PUBLIC_NETWORK_ERROR:{path}:{type(exc).__name__}"
            ) from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BinancePublicMarketError(
                f"NBOT_OBSERVATION_PUBLIC_JSON_INVALID:{path}"
            ) from exc

    def _get_timed(
        self,
        source: str,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[Any, SourceCapture]:
        started_at_ms = self.local_time_ms()
        payload = self._get(path, params)
        finished_at_ms = self.local_time_ms()
        return payload, SourceCapture(source, started_at_ms, finished_at_ms)

    def server_time_ms(self) -> int:
        payload = self._get("/fapi/v1/time")
        if not isinstance(payload, dict) or "serverTime" not in payload:
            raise BinancePublicMarketError("NBOT_OBSERVATION_SERVER_TIME_PAYLOAD_INVALID")
        try:
            value = int(payload["serverTime"])
        except (TypeError, ValueError) as exc:
            raise BinancePublicMarketError("NBOT_OBSERVATION_SERVER_TIME_PAYLOAD_INVALID") from exc
        if value < 0:
            raise BinancePublicMarketError("NBOT_OBSERVATION_SERVER_TIME_PAYLOAD_INVALID")
        return value

    @staticmethod
    def _require_list(payload: Any, source: str) -> list[Any]:
        if not isinstance(payload, list):
            raise BinancePublicMarketError(f"NBOT_OBSERVATION_{source}_PAYLOAD_INVALID")
        return payload

    @staticmethod
    def _index_by_symbol(payload: Any, source: str) -> dict[str, dict[str, Any]]:
        rows = BinanceUsdMPublicClient._require_list(payload, source)
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = row.get("symbol")
            if not isinstance(symbol, str) or not symbol or symbol != symbol.strip().upper():
                continue
            result[symbol] = row
        return result

    @staticmethod
    def _optional_float(row: Mapping[str, Any], key: str) -> float | None:
        value = row.get(key)
        if value in (None, ""):
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) else None

    @staticmethod
    def _optional_int(row: Mapping[str, Any], key: str) -> int | None:
        value = row.get(key)
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def eligible_universe_capture(self) -> UniverseCapture:
        info_raw, info_capture = self._get_timed("exchange_info", "/fapi/v1/exchangeInfo")
        ticker_raw, ticker_capture = self._get_timed("ticker_24h", "/fapi/v1/ticker/24hr")
        book_raw, book_capture = self._get_timed("book_ticker", "/fapi/v1/ticker/bookTicker")
        premium_raw, premium_capture = self._get_timed("premium_index", "/fapi/v1/premiumIndex")

        if not isinstance(info_raw, dict) or not isinstance(info_raw.get("symbols"), list):
            raise BinancePublicMarketError("NBOT_OBSERVATION_EXCHANGE_INFO_PAYLOAD_INVALID")
        tickers = self._index_by_symbol(ticker_raw, "TICKER_24H")
        books = self._index_by_symbol(book_raw, "BOOK_TICKER")
        premium = self._index_by_symbol(premium_raw, "PREMIUM_INDEX")

        permitted: set[str] = set()
        for item in info_raw["symbols"]:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if (
                isinstance(symbol, str)
                and symbol == symbol.strip().upper()
                and item.get("status") == "TRADING"
                and item.get("contractType") == "PERPETUAL"
                and item.get("quoteAsset") == "USDT"
            ):
                permitted.add(symbol)

        candidates: list[tuple[str, float, float, float, float, Mapping[str, Any]]] = []
        for symbol in permitted:
            ticker = tickers.get(symbol)
            book = books.get(symbol)
            if ticker is None or book is None:
                continue
            try:
                quote_volume = float(ticker.get("quoteVolume", 0.0))
                bid = float(book.get("bidPrice", 0.0))
                ask = float(book.get("askPrice", 0.0))
                if not math.isfinite(quote_volume) or quote_volume < 0:
                    continue
                current_spread = spread_pct(bid, ask)
            except (TypeError, ValueError):
                continue
            if quote_volume < self.config.min_quote_volume_24h_usd:
                continue
            if current_spread > self.config.max_spread_pct:
                continue
            candidates.append(
                (symbol, quote_volume, bid, ask, current_spread, premium.get(symbol, {}))
            )

        candidates.sort(key=lambda row: (-row[1], row[0]))
        selected = candidates[: self.config.observation_universe_size]
        rows = tuple(
            UniverseRow(
                symbol=symbol,
                universe_rank=rank,
                quote_volume_24h_usd=quote_volume,
                bid_price=bid,
                ask_price=ask,
                spread_pct=current_spread,
                mark_price=self._optional_float(px, "markPrice"),
                index_price=self._optional_float(px, "indexPrice"),
                funding_rate=self._optional_float(px, "lastFundingRate"),
                next_funding_time_ms=self._optional_int(px, "nextFundingTime"),
            )
            for rank, (symbol, quote_volume, bid, ask, current_spread, px) in enumerate(
                selected, start=1
            )
        )
        return UniverseCapture(
            rows=rows,
            source_captures=(info_capture, ticker_capture, book_capture, premium_capture),
        )

    @staticmethod
    def _parse_candle(symbol: str, raw: Any) -> Candle:
        if not isinstance(raw, list) or len(raw) < 11:
            raise BinancePublicMarketError("NBOT_OBSERVATION_CANDLE_PAYLOAD_INVALID")
        try:
            return Candle(
                symbol=symbol,
                open_time_ms=int(raw[0]),
                close_time_ms=int(raw[6]),
                open_price=float(raw[1]),
                high_price=float(raw[2]),
                low_price=float(raw[3]),
                close_price=float(raw[4]),
                base_volume=float(raw[5]),
                quote_volume=float(raw[7]),
                trade_count=int(raw[8]),
                taker_buy_base_volume=float(raw[9]),
                taker_buy_quote_volume=float(raw[10]),
            )
        except (TypeError, ValueError, IndexError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("NBOT_OBSERVATION_"):
                raise
            raise BinancePublicMarketError("NBOT_OBSERVATION_CANDLE_PAYLOAD_INVALID") from exc

    def _closed_candle(self, symbol: str, open_time_ms: int) -> Candle:
        interval_ms = self.config.candle_interval_ms
        if open_time_ms < 0 or open_time_ms % interval_ms:
            raise ValueError("NBOT_OBSERVATION_CANDLE_OPEN_ALIGNMENT_INVALID")
        payload = self._get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": self.config.candle_interval,
                "startTime": open_time_ms,
                "endTime": open_time_ms + interval_ms - 1,
                "limit": 1,
            },
        )
        rows = self._require_list(payload, "KLINES")
        if len(rows) != 1:
            raise BinancePublicMarketError(
                f"NBOT_OBSERVATION_CANONICAL_CANDLE_MISSING:{symbol}:{open_time_ms}"
            )
        candle = self._parse_candle(symbol, rows[0])
        if candle.open_time_ms != open_time_ms:
            raise BinancePublicMarketError(
                f"NBOT_OBSERVATION_CANONICAL_CANDLE_WRONG_OPEN:{symbol}:{candle.open_time_ms}"
            )
        return candle

    @staticmethod
    def _normalized_symbols(symbols: Iterable[str]) -> tuple[str, ...]:
        values = tuple(sorted(set(str(symbol) for symbol in symbols)))
        for symbol in values:
            if not symbol or symbol != symbol.strip().upper():
                raise ValueError("NBOT_OBSERVATION_SYMBOL_INVALID")
        return values

    def closed_candles(
        self,
        symbols: Iterable[str],
        open_time_ms: int,
    ) -> tuple[Mapping[str, Candle], Mapping[str, str]]:
        requested = self._normalized_symbols(symbols)
        candles: dict[str, Candle] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.config.candle_fetch_workers) as pool:
            futures = {
                pool.submit(self._closed_candle, symbol, int(open_time_ms)): symbol
                for symbol in requested
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    candles[symbol] = future.result()
                except Exception as exc:  # explicit per-symbol evidence failure
                    errors[symbol] = f"{type(exc).__name__}: {exc}"
        return (
            {symbol: candles[symbol] for symbol in sorted(candles)},
            {symbol: errors[symbol] for symbol in sorted(errors)},
        )

    def _historical_candles(
        self,
        symbol: str,
        start_open_ms: int,
        end_open_ms: int,
    ) -> dict[int, Candle]:
        interval_ms = self.config.candle_interval_ms
        if start_open_ms > end_open_ms:
            return {}
        if start_open_ms < 0 or start_open_ms % interval_ms or end_open_ms % interval_ms:
            raise ValueError("NBOT_OBSERVATION_HISTORICAL_CANDLE_ALIGNMENT_INVALID")

        output: dict[int, Candle] = {}
        cursor = start_open_ms
        while cursor <= end_open_ms:
            remaining = ((end_open_ms - cursor) // interval_ms) + 1
            limit = min(MAX_KLINE_ROWS, remaining)
            page_end_open = cursor + (limit - 1) * interval_ms
            payload = self._get(
                "/fapi/v1/klines",
                {
                    "symbol": symbol,
                    "interval": self.config.candle_interval,
                    "startTime": cursor,
                    "endTime": page_end_open + interval_ms - 1,
                    "limit": limit,
                },
            )
            rows = self._require_list(payload, "KLINES")
            if not rows:
                break
            latest_open = cursor - interval_ms
            for raw in rows:
                candle = self._parse_candle(symbol, raw)
                if start_open_ms <= candle.open_time_ms <= end_open_ms:
                    output[candle.open_time_ms] = candle
                latest_open = max(latest_open, candle.open_time_ms)
            next_cursor = latest_open + interval_ms
            if next_cursor <= cursor:
                raise BinancePublicMarketError(
                    f"NBOT_OBSERVATION_HISTORICAL_CANDLE_PAGINATION_STALLED:{symbol}"
                )
            cursor = next_cursor
        return output

    def historical_candles_for_symbols(
        self,
        symbols: Iterable[str],
        open_times_ms: Iterable[int],
    ) -> tuple[Mapping[str, Mapping[int, Candle]], Mapping[str, str]]:
        requested_times = tuple(sorted(set(int(value) for value in open_times_ms)))
        if not requested_times:
            return {}, {}
        interval_ms = self.config.candle_interval_ms
        if requested_times[0] < 0 or any(value % interval_ms for value in requested_times):
            raise ValueError("NBOT_OBSERVATION_HISTORICAL_CANDLE_ALIGNMENT_INVALID")
        requested_set = set(requested_times)
        symbols_tuple = self._normalized_symbols(symbols)
        output: dict[str, dict[int, Candle]] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.config.candle_fetch_workers) as pool:
            futures = {
                pool.submit(
                    self._historical_candles,
                    symbol,
                    requested_times[0],
                    requested_times[-1],
                ): symbol
                for symbol in symbols_tuple
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    rows = future.result()
                    missing = requested_set.difference(rows)
                    if missing:
                        raise BinancePublicMarketError(
                            f"NBOT_OBSERVATION_HISTORICAL_CANDLES_MISSING:{symbol}:{len(missing)}"
                        )
                    output[symbol] = {value: rows[value] for value in requested_times}
                except Exception as exc:
                    errors[symbol] = f"{type(exc).__name__}: {exc}"
        return (
            {symbol: output[symbol] for symbol in sorted(output)},
            {symbol: errors[symbol] for symbol in sorted(errors)},
        )

    def _funding_history_range(
        self,
        start_time_ms: int,
        end_time_ms: int,
    ) -> dict[tuple[str, int], FundingEvent]:
        payload = self._get(
            "/fapi/v1/fundingRate",
            {
                "startTime": start_time_ms,
                "endTime": end_time_ms,
                "limit": MAX_FUNDING_ROWS,
            },
        )
        rows = self._require_list(payload, "FUNDING_HISTORY")
        if len(rows) >= MAX_FUNDING_ROWS:
            if start_time_ms >= end_time_ms:
                raise BinancePublicMarketError(
                    "NBOT_OBSERVATION_FUNDING_RANGE_TOO_DENSE"
                )
            midpoint = start_time_ms + ((end_time_ms - start_time_ms) // 2)
            left = self._funding_history_range(start_time_ms, midpoint)
            right = self._funding_history_range(midpoint + 1, end_time_ms)
            left.update(right)
            return left

        output: dict[tuple[str, int], FundingEvent] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise BinancePublicMarketError(
                    "NBOT_OBSERVATION_FUNDING_HISTORY_PAYLOAD_INVALID"
                )
            try:
                event = FundingEvent(
                    symbol=str(row["symbol"]),
                    funding_time_ms=int(row["fundingTime"]),
                    funding_rate=float(row["fundingRate"]),
                    mark_price=(
                        None
                        if row.get("markPrice") in (None, "")
                        else float(row["markPrice"])
                    ),
                )
            except (KeyError, TypeError, ValueError) as exc:
                if isinstance(exc, ValueError) and str(exc).startswith("NBOT_OBSERVATION_"):
                    raise
                raise BinancePublicMarketError(
                    "NBOT_OBSERVATION_FUNDING_HISTORY_PAYLOAD_INVALID"
                ) from exc
            if start_time_ms <= event.funding_time_ms <= end_time_ms:
                output[(event.symbol, event.funding_time_ms)] = event
        return output

    def funding_history(
        self,
        start_time_ms: int,
        end_time_ms: int,
    ) -> Iterable[FundingEvent]:
        start = int(start_time_ms)
        end = int(end_time_ms)
        if start > end:
            return ()
        if start < 0:
            raise ValueError("NBOT_OBSERVATION_FUNDING_RANGE_INVALID")
        output = self._funding_history_range(start, end)
        return tuple(sorted(output.values(), key=lambda row: (row.funding_time_ms, row.symbol)))
