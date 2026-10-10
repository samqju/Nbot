"""V3 WSS-first public market state and reliability primitives.

Research/market-data only: this module has no credentials, account endpoints, or
order authority. A concrete socket runner may feed decoded Binance combined
stream messages into :class:`WssMarketState`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import random
from typing import Iterable, Mapping
from urllib.parse import quote


AUTHORITY = "RESEARCH_MARKET_DATA_ONLY_NO_EXECUTION"


class MarketDataUnavailable(RuntimeError):
    """Fresh executable market state cannot be proven."""


class StreamKind(str, Enum):
    BOOK_TICKER = "bookTicker"
    AGG_TRADE = "aggTrade"


@dataclass(frozen=True)
class BookQuote:
    symbol: str
    event_time_ms: int
    receipt_time_ms: int
    bid: float
    ask: float
    update_id: int | None = None

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("WSS_SYMBOL_INVALID")
        if min(self.event_time_ms, self.receipt_time_ms) < 0:
            raise ValueError("WSS_TIME_INVALID")
        if not all(math.isfinite(x) and x > 0 for x in (self.bid, self.ask)):
            raise ValueError("WSS_QUOTE_INVALID")
        if self.bid >= self.ask:
            raise ValueError("WSS_QUOTE_CROSSED")

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread_pct(self) -> float:
        return (self.ask - self.bid) / self.mid * 100.0


@dataclass(frozen=True)
class AggTrade:
    symbol: str
    aggregate_id: int
    event_time_ms: int
    trade_time_ms: int
    receipt_time_ms: int
    price: float
    quantity: float
    buyer_is_maker: bool

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("WSS_SYMBOL_INVALID")
        if min(self.aggregate_id, self.event_time_ms, self.trade_time_ms, self.receipt_time_ms) < 0:
            raise ValueError("WSS_TRADE_INVALID")
        if not all(math.isfinite(x) and x > 0 for x in (self.price, self.quantity)):
            raise ValueError("WSS_TRADE_INVALID")


@dataclass(frozen=True)
class SymbolHealth:
    symbol: str
    connected: bool
    quote_age_ms: int | None
    trade_age_ms: int | None
    gap_unresolved: bool
    duplicate_events: int
    out_of_order_events: int
    missing_aggregate_ids: int


class WssMarketState:
    """Symbol-local quote/trade state with fail-closed freshness semantics."""

    def __init__(self, symbols: Iterable[str], *, require_contiguous_agg_ids: bool = True) -> None:
        normalized = tuple(sorted(set(str(s).upper() for s in symbols)))
        if not normalized or any(not s for s in normalized):
            raise ValueError("WSS_SYMBOL_SET_INVALID")
        self.symbols = frozenset(normalized)
        self.require_contiguous_agg_ids = bool(require_contiguous_agg_ids)
        self._quotes: dict[str, BookQuote] = {}
        self._trades: dict[str, AggTrade] = {}
        self._connected: set[str] = set()
        self._gap: set[str] = set()
        self._duplicates = {s: 0 for s in normalized}
        self._out_of_order = {s: 0 for s in normalized}
        self._missing = {s: 0 for s in normalized}

    def mark_connected(self, symbols: Iterable[str] | None = None) -> None:
        values = self.symbols if symbols is None else set(symbols)
        unknown = set(values) - self.symbols
        if unknown:
            raise ValueError("WSS_UNKNOWN_SYMBOL")
        self._connected.update(values)

    def mark_disconnected(self, symbols: Iterable[str] | None = None) -> None:
        values = self.symbols if symbols is None else set(symbols)
        self._connected.difference_update(values)

    def mark_recovered(self, symbol: str, *, through_aggregate_id: int | None = None) -> None:
        if symbol not in self.symbols:
            raise ValueError("WSS_UNKNOWN_SYMBOL")
        prior = self._trades.get(symbol)
        if through_aggregate_id is not None and prior is not None and through_aggregate_id < prior.aggregate_id:
            raise ValueError("WSS_RECOVERY_RANGE_INVALID")
        self._gap.discard(symbol)

    def ingest_book_ticker(self, payload: Mapping[str, object], *, receipt_time_ms: int) -> BookQuote:
        try:
            symbol = str(payload["s"])
            quote_obj = BookQuote(
                symbol=symbol,
                event_time_ms=int(payload.get("E", receipt_time_ms)),
                receipt_time_ms=int(receipt_time_ms),
                bid=float(payload["b"]),
                ask=float(payload["a"]),
                update_id=int(payload["u"]) if payload.get("u") is not None else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("WSS_"):
                raise
            raise ValueError("WSS_BOOK_TICKER_PAYLOAD_INVALID") from exc
        if symbol not in self.symbols:
            raise ValueError("WSS_UNKNOWN_SYMBOL")
        previous = self._quotes.get(symbol)
        if previous is not None and quote_obj.event_time_ms < previous.event_time_ms:
            self._out_of_order[symbol] += 1
            raise MarketDataUnavailable("WSS_BOOK_TICKER_OUT_OF_ORDER")
        self._quotes[symbol] = quote_obj
        return quote_obj

    def ingest_agg_trade(self, payload: Mapping[str, object], *, receipt_time_ms: int) -> AggTrade:
        try:
            symbol = str(payload["s"])
            trade = AggTrade(
                symbol=symbol,
                aggregate_id=int(payload["a"]),
                event_time_ms=int(payload.get("E", payload["T"])),
                trade_time_ms=int(payload["T"]),
                receipt_time_ms=int(receipt_time_ms),
                price=float(payload["p"]),
                quantity=float(payload["q"]),
                buyer_is_maker=bool(payload["m"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("WSS_"):
                raise
            raise ValueError("WSS_AGG_TRADE_PAYLOAD_INVALID") from exc
        if symbol not in self.symbols:
            raise ValueError("WSS_UNKNOWN_SYMBOL")
        previous = self._trades.get(symbol)
        if previous is not None:
            if trade.aggregate_id == previous.aggregate_id:
                self._duplicates[symbol] += 1
                return previous
            if trade.aggregate_id < previous.aggregate_id or trade.trade_time_ms < previous.trade_time_ms:
                self._out_of_order[symbol] += 1
                self._gap.add(symbol)
                raise MarketDataUnavailable("WSS_AGG_TRADE_OUT_OF_ORDER")
            if self.require_contiguous_agg_ids and trade.aggregate_id != previous.aggregate_id + 1:
                self._missing[symbol] += trade.aggregate_id - previous.aggregate_id - 1
                self._gap.add(symbol)
        self._trades[symbol] = trade
        return trade

    def executable_quote(self, symbol: str, *, now_ms: int, max_age_ms: int) -> BookQuote:
        if max_age_ms <= 0:
            raise ValueError("WSS_MAX_AGE_INVALID")
        if symbol not in self.symbols:
            raise MarketDataUnavailable("WSS_SYMBOL_NOT_ELIGIBLE")
        if symbol not in self._connected:
            raise MarketDataUnavailable("WSS_STREAM_DISCONNECTED")
        if symbol in self._gap:
            raise MarketDataUnavailable("WSS_GAP_UNRESOLVED")
        quote_obj = self._quotes.get(symbol)
        if quote_obj is None:
            raise MarketDataUnavailable("WSS_BOOK_TICKER_MISSING")
        age = int(now_ms) - quote_obj.receipt_time_ms
        if age < 0 or age > max_age_ms:
            raise MarketDataUnavailable("WSS_BOOK_TICKER_STALE")
        return quote_obj

    def health(self, symbol: str, *, now_ms: int) -> SymbolHealth:
        if symbol not in self.symbols:
            raise ValueError("WSS_UNKNOWN_SYMBOL")
        q = self._quotes.get(symbol)
        t = self._trades.get(symbol)
        return SymbolHealth(
            symbol=symbol,
            connected=symbol in self._connected,
            quote_age_ms=None if q is None else max(0, int(now_ms) - q.receipt_time_ms),
            trade_age_ms=None if t is None else max(0, int(now_ms) - t.receipt_time_ms),
            gap_unresolved=symbol in self._gap,
            duplicate_events=self._duplicates[symbol],
            out_of_order_events=self._out_of_order[symbol],
            missing_aggregate_ids=self._missing[symbol],
        )


@dataclass(frozen=True)
class StreamShard:
    symbols: tuple[str, ...]
    streams: tuple[str, ...]
    combined_url: str


def plan_combined_streams(
    symbols: Iterable[str], *, max_streams_per_connection: int = 180,
    public_base_url: str = "wss://fstream.binance.com/public/stream?streams=",
    market_base_url: str = "wss://fstream.binance.com/market/stream?streams=",
) -> tuple[StreamShard, ...]:
    """Deterministically shard Binance 2026 public + market subscriptions.

    Binance USD-M Futures routes high-frequency public feeds such as
    bookTicker through /public and regular market feeds such as aggTrade
    through /market. Do not mix those categories on the legacy /stream
    endpoint: after Binance's 2026 migration the socket can stay connected
    while market-category messages stop arriving.
    """
    values = tuple(sorted(set(str(s).upper() for s in symbols)))
    if not values or max_streams_per_connection < 1:
        raise ValueError("WSS_SHARD_CONFIG_INVALID")

    shards: list[StreamShard] = []
    for base_url, suffix in (
        (public_base_url, "bookTicker"),
        (market_base_url, "aggTrade"),
    ):
        for start in range(0, len(values), max_streams_per_connection):
            chunk = values[start:start + max_streams_per_connection]
            streams = tuple(f"{symbol.lower()}@{suffix}" for symbol in chunk)
            shards.append(
                StreamShard(
                    chunk,
                    streams,
                    base_url + quote("/".join(streams), safe="/@"),
                )
            )
    return tuple(shards)

def reconnect_delay_seconds(attempt: int, *, base: float = 0.5, cap: float = 30.0, jitter: float = 0.20,
                            rng: random.Random | None = None) -> float:
    if attempt < 0 or base <= 0 or cap <= 0 or not 0 <= jitter <= 1:
        raise ValueError("WSS_BACKOFF_INVALID")
    raw = min(cap, base * (2 ** attempt))
    source = rng or random.Random()
    return max(0.0, raw * (1.0 + source.uniform(-jitter, jitter)))
