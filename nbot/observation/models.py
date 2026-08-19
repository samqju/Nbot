from __future__ import annotations

from dataclasses import dataclass
import math


CANONICAL_CANDLE_INTERVAL_MS = 5 * 60 * 1000


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(float(value)):
        raise ValueError(f"NBOT_OBSERVATION_{name}_NOT_FINITE")


def _require_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if not value or value != str(symbol):
        raise ValueError("NBOT_OBSERVATION_SYMBOL_INVALID")
    return value


def spread_pct(bid_price: float, ask_price: float) -> float:
    bid = float(bid_price)
    ask = float(ask_price)
    _require_finite("BID_PRICE", bid)
    _require_finite("ASK_PRICE", ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        raise ValueError("NBOT_OBSERVATION_BID_ASK_INVALID")
    midpoint = (bid + ask) / 2.0
    return ((ask - bid) / midpoint) * 100.0


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

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        if self.open_time_ms < 0:
            raise ValueError("NBOT_OBSERVATION_CANDLE_OPEN_TIME_INVALID")
        if self.close_time_ms != self.open_time_ms + CANONICAL_CANDLE_INTERVAL_MS - 1:
            raise ValueError("NBOT_OBSERVATION_CANDLE_INTERVAL_INVALID")
        prices = {
            "OPEN_PRICE": self.open_price,
            "HIGH_PRICE": self.high_price,
            "LOW_PRICE": self.low_price,
            "CLOSE_PRICE": self.close_price,
        }
        for name, value in prices.items():
            _require_finite(name, value)
            if value <= 0:
                raise ValueError(f"NBOT_OBSERVATION_{name}_INVALID")
        if self.high_price < max(self.open_price, self.close_price, self.low_price):
            raise ValueError("NBOT_OBSERVATION_CANDLE_HIGH_INVALID")
        if self.low_price > min(self.open_price, self.close_price, self.high_price):
            raise ValueError("NBOT_OBSERVATION_CANDLE_LOW_INVALID")
        for name, value in (
            ("BASE_VOLUME", self.base_volume),
            ("QUOTE_VOLUME", self.quote_volume),
            ("TAKER_BUY_BASE_VOLUME", self.taker_buy_base_volume),
            ("TAKER_BUY_QUOTE_VOLUME", self.taker_buy_quote_volume),
        ):
            _require_finite(name, value)
            if value < 0:
                raise ValueError(f"NBOT_OBSERVATION_{name}_INVALID")
        if self.trade_count < 0:
            raise ValueError("NBOT_OBSERVATION_TRADE_COUNT_INVALID")


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

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        if self.universe_rank <= 0:
            raise ValueError("NBOT_OBSERVATION_UNIVERSE_RANK_INVALID")
        _require_finite("QUOTE_VOLUME_24H", self.quote_volume_24h_usd)
        if self.quote_volume_24h_usd < 0:
            raise ValueError("NBOT_OBSERVATION_QUOTE_VOLUME_24H_INVALID")
        expected_spread = spread_pct(self.bid_price, self.ask_price)
        _require_finite("SPREAD_PCT", self.spread_pct)
        if self.spread_pct < 0 or not math.isclose(
            self.spread_pct,
            expected_spread,
            rel_tol=1e-9,
            abs_tol=1e-12,
        ):
            raise ValueError("NBOT_OBSERVATION_SPREAD_PCT_INCONSISTENT")
        for name, value in (
            ("MARK_PRICE", self.mark_price),
            ("INDEX_PRICE", self.index_price),
        ):
            if value is None:
                continue
            _require_finite(name, value)
            if value <= 0:
                raise ValueError(f"NBOT_OBSERVATION_{name}_INVALID")
        if self.funding_rate is not None:
            _require_finite("FUNDING_RATE", self.funding_rate)
        if self.next_funding_time_ms is not None and self.next_funding_time_ms < 0:
            raise ValueError("NBOT_OBSERVATION_NEXT_FUNDING_TIME_INVALID")


@dataclass(frozen=True)
class SourceCapture:
    source: str
    started_at_ms: int
    finished_at_ms: int

    def __post_init__(self) -> None:
        if not str(self.source).strip():
            raise ValueError("NBOT_OBSERVATION_SOURCE_NAME_INVALID")
        if self.started_at_ms < 0 or self.finished_at_ms < self.started_at_ms:
            raise ValueError("NBOT_OBSERVATION_SOURCE_CAPTURE_TIME_INVALID")


@dataclass(frozen=True)
class UniverseCapture:
    rows: tuple[UniverseRow, ...]
    source_captures: tuple[SourceCapture, ...]

    def __post_init__(self) -> None:
        symbols = [row.symbol for row in self.rows]
        if len(symbols) != len(set(symbols)):
            raise ValueError("NBOT_OBSERVATION_UNIVERSE_SYMBOL_DUPLICATE")
        ranks = [row.universe_rank for row in self.rows]
        if ranks != list(range(1, len(self.rows) + 1)):
            raise ValueError("NBOT_OBSERVATION_UNIVERSE_RANK_NONDETERMINISTIC")
        sources = [capture.source for capture in self.source_captures]
        if len(sources) != len(set(sources)):
            raise ValueError("NBOT_OBSERVATION_SOURCE_CAPTURE_DUPLICATE")


@dataclass(frozen=True)
class FundingEvent:
    symbol: str
    funding_time_ms: int
    funding_rate: float
    mark_price: float | None

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        if self.funding_time_ms < 0:
            raise ValueError("NBOT_OBSERVATION_FUNDING_TIME_INVALID")
        _require_finite("FUNDING_RATE", self.funding_rate)
        if self.mark_price is not None:
            _require_finite("MARK_PRICE", self.mark_price)
            if self.mark_price <= 0:
                raise ValueError("NBOT_OBSERVATION_MARK_PRICE_INVALID")
