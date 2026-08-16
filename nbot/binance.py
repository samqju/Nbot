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


def latest_closed_open_time_ms(server_time_ms: int, interval_ms: int = 300_000) -> int:
    if server_time_ms < interval_ms:
        raise ValueError("server_time_ms is too small")
    return ((int(server_time_ms) // interval_ms) - 1) * interval_ms


def spread_pct(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ValueError("invalid bid/ask")
    mid = (bid + ask) / 2.0
    return ((ask - bid) / mid) * 100.0


class BinancePublicClient:
    """Credential-free USD-M Futures public REST client used by V2.0."""

    def __init__(self, config: ObserverConfig):
        self.config = config

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urlencode(params or {})
        url = f"{self.config.binance_base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers={"User-Agent": "NBOT-V2-Observer/1"})
        with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)

    def server_time_ms(self) -> int:
        return int(self._get("/fapi/v1/time")["serverTime"])

    def _exchange_info(self) -> dict[str, Any]:
        return dict(self._get("/fapi/v1/exchangeInfo"))

    def _ticker_24h(self) -> list[dict[str, Any]]:
        return list(self._get("/fapi/v1/ticker/24hr"))

    def _book_tickers(self) -> list[dict[str, Any]]:
        return list(self._get("/fapi/v1/ticker/bookTicker"))

    def _premium_index(self) -> list[dict[str, Any]]:
        return list(self._get("/fapi/v1/premiumIndex"))

    def eligible_universe(self) -> list[UniverseRow]:
        info = self._exchange_info()
        tickers = {str(x["symbol"]): x for x in self._ticker_24h() if "symbol" in x}
        books = {str(x["symbol"]): x for x in self._book_tickers() if "symbol" in x}
        premium = {str(x["symbol"]): x for x in self._premium_index() if "symbol" in x}

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
        return result

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
        row = payload[0]
        if int(row[0]) != open_time_ms:
            raise RuntimeError(f"unexpected candle open for {symbol}: {row[0]} != {open_time_ms}")
        return Candle(
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

    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)
