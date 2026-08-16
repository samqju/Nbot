from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import ObserverConfig


@dataclass(frozen=True)
class UniverseRow:
    symbol: str
    universe_rank: int
    quote_volume_24h_usd: float
    bid_price: float
    ask_price: float
    spread_pct: float
    mark_price: float | None
    index_price: float | None
    funding_rate: float | None
    next_funding_time_ms: int | None


@dataclass(frozen=True)
class Candle:
    symbol: str
    open_time_ms: int
    close_time_ms: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    base_volume: float
    quote_volume: float
    trade_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float


@dataclass(frozen=True)
class SourceCapture:
    source: str
    started_at_ms: int
    finished_at_ms: int


@dataclass(frozen=True)
class UniverseCapture:
    rows: tuple[UniverseRow, ...]
    source_captures: tuple[SourceCapture, ...]


@dataclass(frozen=True)
class FundingEvent:
    symbol: str
    funding_time_ms: int
    funding_rate: float
    mark_price: float | None


def latest_closed_open_time_ms(server_time_ms: int, interval_ms: int = 300_000) -> int:
    if server_time_ms < interval_ms:
        raise ValueError("server_time_ms is too small")
    return ((int(server_time_ms) // interval_ms) - 1) * interval_ms


def spread_pct(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ValueError("invalid bid/ask")
    mid = (bid + ask) / 2.0
    return ((ask - bid) / mid) * 100.0


def validate_candle(candle: Candle, interval_ms: int = 300_000) -> None:
    if candle.open_time_ms < 0:
        raise ValueError("negative candle open time")
    if candle.close_time_ms != candle.open_time_ms + interval_ms - 1:
        raise ValueError("candle close time does not match interval")
    prices = (candle.open_price, candle.high_price, candle.low_price, candle.close_price)
    if any(value <= 0 for value in prices):
        raise ValueError("candle prices must be positive")
    if candle.high_price < max(candle.open_price, candle.close_price, candle.low_price):
        raise ValueError("candle high is malformed")
    if candle.low_price > min(candle.open_price, candle.close_price, candle.high_price):
        raise ValueError("candle low is malformed")
    if candle.base_volume < 0 or candle.quote_volume < 0:
        raise ValueError("candle volume is negative")
    if candle.taker_buy_base_volume < 0 or candle.taker_buy_quote_volume < 0:
        raise ValueError("taker-buy volume is negative")
    if candle.trade_count < 0:
        raise ValueError("trade_count is negative")


class BinancePublicClient:
    """Credential-free USD-M Futures public REST client used by V2.1."""

    def __init__(self, config: ObserverConfig):
        self.config = config

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urlencode(params or {})
        url = f"{self.config.binance_base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers={"User-Agent": "NBOT-V2-Observer/2.1"})
        with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)

    def _get_timed(
        self,
        source: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, SourceCapture]:
        started_at_ms = self.now_ms()
        payload = self._get(path, params)
        finished_at_ms = self.now_ms()
        return payload, SourceCapture(source, started_at_ms, finished_at_ms)

    def server_time_ms(self) -> int:
        return int(self._get("/fapi/v1/time")["serverTime"])

    @staticmethod
    def _parse_candle(symbol: str, row: list[Any]) -> Candle:
        candle = Candle(
            symbol=symbol,
            open_time_ms=int(row[0]),
            close_time_ms=int(row[6]),
            open_price=float(row[1]),
            high_price=float(row[2]),
            low_price=float(row[3]),
            close_price=float(row[4]),
            base_volume=float(row[5]),
            quote_volume=float(row[7]),
            trade_count=int(row[8]),
            taker_buy_base_volume=float(row[9]),
            taker_buy_quote_volume=float(row[10]),
        )
        validate_candle(candle)
        return candle

    def eligible_universe_capture(self) -> UniverseCapture:
        info_raw, info_capture = self._get_timed("exchange_info", "/fapi/v1/exchangeInfo")
        ticker_raw, ticker_capture = self._get_timed("ticker_24h", "/fapi/v1/ticker/24hr")
        book_raw, book_capture = self._get_timed("book_ticker", "/fapi/v1/ticker/bookTicker")
        premium_raw, premium_capture = self._get_timed("premium_index", "/fapi/v1/premiumIndex")

        info = dict(info_raw)
        tickers = {str(x["symbol"]): x for x in list(ticker_raw) if "symbol" in x}
        books = {str(x["symbol"]): x for x in list(book_raw) if "symbol" in x}
        premium = {str(x["symbol"]): x for x in list(premium_raw) if "symbol" in x}

        permitted: set[str] = set()
        for item in info.get("symbols", []):
            if (
                item.get("status") == "TRADING"
                and item.get("contractType") == "PERPETUAL"
                and item.get("quoteAsset") == "USDT"
            ):
                permitted.add(str(item["symbol"]))

        rows: list[tuple[str, float, float, float, float, dict[str, Any]]] = []
        for symbol in permitted:
            ticker = tickers.get(symbol)
            book = books.get(symbol)
            if ticker is None or book is None:
                continue
            try:
                quote_volume = float(ticker.get("quoteVolume", 0.0))
                bid = float(book.get("bidPrice", 0.0))
                ask = float(book.get("askPrice", 0.0))
                sp = spread_pct(bid, ask)
            except (TypeError, ValueError):
                continue
            if quote_volume < self.config.min_quote_volume_24h_usd:
                continue
            if sp > self.config.max_spread_pct:
                continue
            rows.append((symbol, quote_volume, bid, ask, sp, premium.get(symbol, {})))

        rows.sort(key=lambda x: (-x[1], x[0]))
        selected = rows[: self.config.observation_universe_size]

        result: list[UniverseRow] = []
        for rank, (symbol, quote_volume, bid, ask, sp, px) in enumerate(selected, start=1):
            def opt_float(key: str) -> float | None:
                value = px.get(key)
                if value in (None, ""):
                    return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            def opt_int(key: str) -> int | None:
                value = px.get(key)
                if value in (None, ""):
                    return None
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            result.append(
                UniverseRow(
                    symbol=symbol,
                    universe_rank=rank,
                    quote_volume_24h_usd=quote_volume,
                    bid_price=bid,
                    ask_price=ask,
                    spread_pct=sp,
                    mark_price=opt_float("markPrice"),
                    index_price=opt_float("indexPrice"),
                    funding_rate=opt_float("lastFundingRate"),
                    next_funding_time_ms=opt_int("nextFundingTime"),
                )
            )
        return UniverseCapture(
            rows=tuple(result),
            source_captures=(info_capture, ticker_capture, book_capture, premium_capture),
        )

    def eligible_universe(self) -> list[UniverseRow]:
        return list(self.eligible_universe_capture().rows)

    def closed_candle(self, symbol: str, open_time_ms: int) -> Candle:
        end_time_ms = open_time_ms + self.config.candle_interval_ms - 1
        payload = self._get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": self.config.candle_interval,
                "startTime": open_time_ms,
                "endTime": end_time_ms,
                "limit": 1,
            },
        )
        if not isinstance(payload, list) or len(payload) != 1:
            raise RuntimeError(f"missing canonical candle for {symbol} at {open_time_ms}")
        candle = self._parse_candle(symbol, payload[0])
        if candle.open_time_ms != open_time_ms:
            raise RuntimeError(f"unexpected candle open for {symbol}: {candle.open_time_ms} != {open_time_ms}")
        return candle

    def closed_candles(
        self,
        symbols: Iterable[str],
        open_time_ms: int,
    ) -> tuple[dict[str, Candle], dict[str, str]]:
        candles: dict[str, Candle] = {}
        errors: dict[str, str] = {}
        symbols = list(symbols)
        with ThreadPoolExecutor(max_workers=self.config.candle_fetch_workers) as pool:
            futures = {pool.submit(self.closed_candle, symbol, open_time_ms): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    candles[symbol] = future.result()
                except Exception as exc:  # each symbol failure is evidence, not a process crash
                    errors[symbol] = f"{type(exc).__name__}: {exc}"
        return candles, errors

    def historical_candles(
        self,
        symbol: str,
        start_open_ms: int,
        end_open_ms: int,
    ) -> dict[int, Candle]:
        if start_open_ms > end_open_ms:
            return {}
        interval_ms = self.config.candle_interval_ms
        if start_open_ms % interval_ms or end_open_ms % interval_ms:
            raise ValueError("historical candle bounds must align to the decision interval")

        output: dict[int, Candle] = {}
        cursor = start_open_ms
        max_rows = 1500
        while cursor <= end_open_ms:
            remaining = ((end_open_ms - cursor) // interval_ms) + 1
            limit = min(max_rows, remaining)
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
            if not isinstance(payload, list):
                raise RuntimeError(f"invalid historical candle payload for {symbol}")
            if not payload:
                break
            latest_open = cursor - interval_ms
            for raw in payload:
                candle = self._parse_candle(symbol, raw)
                if start_open_ms <= candle.open_time_ms <= end_open_ms:
                    output[candle.open_time_ms] = candle
                latest_open = max(latest_open, candle.open_time_ms)
            next_cursor = latest_open + interval_ms
            if next_cursor <= cursor:
                raise RuntimeError(f"historical candle pagination stalled for {symbol}")
            cursor = next_cursor
        return output

    def historical_candles_for_symbols(
        self,
        symbols: Iterable[str],
        open_times: Iterable[int],
    ) -> tuple[dict[str, dict[int, Candle]], dict[str, str]]:
        requested = sorted(set(int(value) for value in open_times))
        if not requested:
            return {}, {}
        start_open_ms, end_open_ms = requested[0], requested[-1]
        requested_set = set(requested)
        output: dict[str, dict[int, Candle]] = {}
        errors: dict[str, str] = {}
        symbols = list(symbols)
        with ThreadPoolExecutor(max_workers=self.config.candle_fetch_workers) as pool:
            futures = {
                pool.submit(self.historical_candles, symbol, start_open_ms, end_open_ms): symbol
                for symbol in symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    rows = future.result()
                    missing = requested_set.difference(rows)
                    if missing:
                        raise RuntimeError(f"missing {len(missing)} requested candles")
                    output[symbol] = {open_ms: rows[open_ms] for open_ms in requested}
                except Exception as exc:
                    errors[symbol] = f"{type(exc).__name__}: {exc}"
        return output, errors

    def funding_history(self, start_time_ms: int, end_time_ms: int) -> list[FundingEvent]:
        if start_time_ms > end_time_ms:
            return []
        cursor = int(start_time_ms)
        output: dict[tuple[str, int], FundingEvent] = {}
        while cursor <= end_time_ms:
            payload = self._get(
                "/fapi/v1/fundingRate",
                {"startTime": cursor, "endTime": int(end_time_ms), "limit": 1000},
            )
            if not isinstance(payload, list):
                raise RuntimeError("invalid funding history payload")
            if not payload:
                break
            latest_time = cursor - 1
            for row in payload:
                funding_time_ms = int(row["fundingTime"])
                if funding_time_ms < start_time_ms or funding_time_ms > end_time_ms:
                    continue
                mark_raw = row.get("markPrice")
                mark_price = None if mark_raw in (None, "") else float(mark_raw)
                event = FundingEvent(
                    symbol=str(row["symbol"]),
                    funding_time_ms=funding_time_ms,
                    funding_rate=float(row["fundingRate"]),
                    mark_price=mark_price,
                )
                output[(event.symbol, event.funding_time_ms)] = event
                latest_time = max(latest_time, funding_time_ms)
            if len(payload) < 1000:
                break
            next_cursor = latest_time + 1
            if next_cursor <= cursor:
                raise RuntimeError("funding history pagination stalled")
            cursor = next_cursor
        return sorted(output.values(), key=lambda row: (row.funding_time_ms, row.symbol))

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)
