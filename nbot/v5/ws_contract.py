"""V5 USD-M Futures WSS stream routes and fail-closed event contract.

Public market-data only; no API keys, account/user stream, trade, order or
execution authority. This module defines and validates streams, not a daemon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
import re
from typing import Mapping, Sequence
from urllib.parse import urlencode

from nbot.v5.observation_contract import INTERVAL_MS, MAX_SYMBOLS

WSS_HOST = "wss://fstream.binance.com"
_MARKET = "/market/stream"
_PUBLIC = "/public/stream"
_SYMBOL = re.compile(r"^[A-Z0-9]{3,24}$")
_ALLOWED = {
    "market": frozenset({"aggTrade", "kline_5m"}),
    "public": frozenset({"bookTicker"}),
}
# Default maximum message time skew; actual source freshness gates are separate.
SKEW_TOLERANCE_MS = 90_000
MAX_FRAME_BYTES = 64_000


class UnsafeStream(ValueError):
    """Malformed, stale, mismatched or unapproved public WSS evidence."""


def stream_urls(eligible_symbols: Sequence[str]) -> dict[str, str]:
    """Dedicated MARKET and PUBLIC connections, including BTC context."""
    if (not 1 <= len(eligible_symbols) <= MAX_SYMBOLS
            or len(set(eligible_symbols)) != len(eligible_symbols)
            or any(not isinstance(s, str) or not _SYMBOL.fullmatch(s)
                   for s in eligible_symbols)):
        raise UnsafeStream("V5_WSS_UNIVERSE_INVALID")
    symbols = sorted(set(eligible_symbols) | {"BTCUSDT"})
    market = [f"{s.lower()}@{stream}"
              for s in symbols for stream in ("aggTrade", "kline_5m")]
    public = [f"{s.lower()}@bookTicker" for s in symbols]
    return {
        "market": WSS_HOST + _MARKET + "?" + urlencode({"streams": "/".join(market)}, safe="@/"),
        "public": WSS_HOST + _PUBLIC + "?" + urlencode({"streams": "/".join(public)}, safe="@/"),
    }


def _positive(value: object, *, zero: bool = False) -> float:
    if isinstance(value, bool):
        raise UnsafeStream("V5_WSS_NUMERIC_INVALID")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise UnsafeStream("V5_WSS_NUMERIC_INVALID") from exc
    if not math.isfinite(number) or number < 0 or (not zero and number == 0):
        raise UnsafeStream("V5_WSS_NUMERIC_INVALID")
    return number


def _timestamp(value: object, *, allow_zero: bool = False) -> int:
    if type(value) is not int or value < 0 or (not allow_zero and value == 0):
        raise UnsafeStream("V5_WSS_TIMESTAMP_INVALID")
    return value


def decode_frame(
    route: str, frame: str | bytes, *, received_ms: int,
    subscribed_symbols: Sequence[str],
) -> dict:
    """Validate a single combined WSS frame for the stated socket route.

    Closes are usable only when k.x is true. Do not grant trade authority.
    Connection-specific ping/pong and reconnect behavior belongs to the client.
    """
    if route not in _ALLOWED:
        raise UnsafeStream("V5_WSS_ROUTE_INVALID")
    _timestamp(received_ms)
    if isinstance(frame, bytes):
        if len(frame) > MAX_FRAME_BYTES:
            raise UnsafeStream("V5_WSS_OVERSIZED_FRAME")
        try:
            frame = frame.decode("utf-8")
        except UnicodeError as exc:
            raise UnsafeStream("V5_WSS_ENCODING_INVALID") from exc
    if not isinstance(frame, str) or len(frame.encode("utf-8")) > MAX_FRAME_BYTES:
        raise UnsafeStream("V5_WSS_OVERSIZED_FRAME")
    try:
        envelope = json.loads(frame)
    except (ValueError, TypeError) as exc:
        raise UnsafeStream("V5_WSS_JSON_INVALID") from exc
    if not isinstance(envelope, dict):
        raise UnsafeStream("V5_WSS_WRAPPER_INVALID")
    name, data = envelope.get("stream"), envelope.get("data")
    if not isinstance(name, str) or not isinstance(data, dict) or "@" not in name:
        raise UnsafeStream("V5_WSS_WRAPPER_INVALID")
    symbol_part, stream_kind = name.split("@", 1)
    symbol = symbol_part.upper()
    allowed = set(subscribed_symbols) | {"BTCUSDT"}
    if (not _SYMBOL.fullmatch(symbol) or symbol not in allowed
            or stream_kind not in _ALLOWED[route]
            or name != f"{symbol.lower()}@{stream_kind}"
            or data.get("s") != symbol):
        raise UnsafeStream("V5_WSS_STREAM_OR_SYMBOL_MISMATCH")
    expected_type = "kline" if stream_kind == "kline_5m" else stream_kind
    if data.get("e") != expected_type:
        raise UnsafeStream("V5_WSS_EVENT_TYPE_MISMATCH")
    event_ms = _timestamp(data.get("E"))
    if event_ms > received_ms + SKEW_TOLERANCE_MS or received_ms - event_ms > SKEW_TOLERANCE_MS:
        raise UnsafeStream("V5_WSS_EVENT_STALE_OR_FUTURE")

    common = {"route": route, "kind": stream_kind, "symbol": symbol,
              "event_ms": event_ms, "received_ms": received_ms,
              "order_authority": "NONE"}
    if stream_kind == "bookTicker":
        bid = _positive(data.get("b"))
        ask = _positive(data.get("a"))
        _positive(data.get("B"), zero=True)
        _positive(data.get("A"), zero=True)
        update_id = _timestamp(data.get("u"), allow_zero=True)
        if ask < bid:
            raise UnsafeStream("V5_WSS_CROSSED_BOOK")
        return {**common, "update_id": update_id, "bid": bid, "ask": ask}
    if stream_kind == "aggTrade":
        aggregate_id = _timestamp(data.get("a"), allow_zero=True)
        trade_ms = _timestamp(data.get("T"))
        if trade_ms > event_ms + SKEW_TOLERANCE_MS:
            raise UnsafeStream("V5_WSS_TRADE_FUTURE")
        return {**common, "aggregate_id": aggregate_id,
                "price": _positive(data.get("p")),
                "quantity": _positive(data.get("q")),
                "trade_ms": trade_ms}

    k = data.get("k")
    if not isinstance(k, dict) or k.get("s") != symbol or k.get("i") != "5m":
        raise UnsafeStream("V5_WSS_KLINE_INVALID")
    opened = _timestamp(k.get("t"), allow_zero=True)
    closed = _timestamp(k.get("T"))
    if opened % INTERVAL_MS or closed != opened + INTERVAL_MS - 1:
        raise UnsafeStream("V5_WSS_CANDLE_TIME_INVALID")
    o, h, l, c, v = (
        _positive(k.get("o")), _positive(k.get("h")),
        _positive(k.get("l")), _positive(k.get("c")),
        _positive(k.get("v"), zero=True),
    )
    if h < max(o, c) or l > min(o, c) or l > h:
        raise UnsafeStream("V5_WSS_CANDLE_PRICE_INVALID")
    if type(k.get("x")) is not bool:
        raise UnsafeStream("V5_WSS_CANDLE_FINALITY_INVALID")
    if k["x"] and closed >= received_ms:
        raise UnsafeStream("V5_WSS_CANDLE_NOT_YET_CLOSED")
    return {**common, "closed": k["x"], "candle": (opened, o, h, l, c, v)}


@dataclass
class FeedStatus:
    """Independently track quote/trade/kline, and make reconnect gaps explicit.

    This is a conservative in-memory status, NOT a certified historical
    recovery mechanism or complete live market-data daemon.
    """
    market_connected: bool = False
    public_connected: bool = False
    last_quote_ms: dict[str, int] = field(default_factory=dict)
    last_trade_ms: dict[str, int] = field(default_factory=dict)
    last_closed_ms: dict[str, int] = field(default_factory=dict)
    last_agg_id: dict[str, int] = field(default_factory=dict)
    trade_gaps: set[str] = field(default_factory=set)
    cohort_valid: bool = False

    def connect(self, route: str) -> None:
        if route not in _ALLOWED:
            raise UnsafeStream("V5_WSS_ROUTE_INVALID")
        if route == "market":
            self.market_connected = True
            self.last_trade_ms.clear()
            self.last_closed_ms.clear()
            self.last_agg_id.clear()
            self.cohort_valid = False
            self.trade_gaps.clear()  # New unproven cohort; old gaps NOT repaired.
        else:
            self.public_connected = True
            self.last_quote_ms.clear()
            self.cohort_valid = False

    def disconnect(self, route: str) -> None:
        if route not in _ALLOWED:
            raise UnsafeStream("V5_WSS_ROUTE_INVALID")
        if route == "market":
            self.market_connected = False
            self.last_trade_ms.clear()
            self.last_closed_ms.clear()
            self.last_agg_id.clear()
        else:
            self.public_connected = False
            self.last_quote_ms.clear()
        self.cohort_valid = False

    def accept(self, event: Mapping[str, object]) -> None:
        route, kind = event.get("route"), event.get("kind")
        if route not in _ALLOWED or kind not in _ALLOWED[route]:
            raise UnsafeStream("V5_WSS_EVENT_KIND_INVALID")
        if not (self.market_connected if route == "market" else self.public_connected):
            raise UnsafeStream("V5_WSS_DISCONNECTED_EVENT")
        symbol = event["symbol"]
        recv = event["received_ms"]
        if kind == "bookTicker":
            self.last_quote_ms[symbol] = recv
        elif kind == "aggTrade":
            aid = event["aggregate_id"]
            previous = self.last_agg_id.get(symbol)
            if previous is not None:
                if aid <= previous:
                    # Ignore duplicate or out-of-order evidence, do not mark healthy.
                    return
                if aid != previous + 1:
                    self.trade_gaps.add(symbol)
                    self.cohort_valid = False
            self.last_agg_id[symbol] = aid
            self.last_trade_ms[symbol] = recv
        elif event["closed"]:
            opened = event["candle"][0]
            previous = self.last_closed_ms.get(symbol)
            if previous is not None and opened != previous + INTERVAL_MS:
                self.cohort_valid = False
            if previous is not None and opened <= previous:
                return
            self.last_closed_ms[symbol] = opened

    def gate(self, *, symbol: str, now_ms: int,
             max_quote_age_ms: int = 5_000,
             max_trade_age_ms: int = 15_000) -> tuple[bool, tuple[str, ...]]:
        reasons = []
        if not self.public_connected:
            reasons.append("QUOTE_DISCONNECTED")
        if not self.market_connected:
            reasons.append("TRADE_DISCONNECTED")
        quote = self.last_quote_ms.get(symbol)
        trade = self.last_trade_ms.get(symbol)
        if quote is None or not 0 <= now_ms - quote <= max_quote_age_ms:
            reasons.append("QUOTE_STALE_OR_MISSING")
        if trade is None or not 0 <= now_ms - trade <= max_trade_age_ms:
            reasons.append("TRADE_STALE_OR_MISSING")
        if symbol in self.trade_gaps:
            reasons.append("TRADE_SEQUENCE_GAP")
        # Cohort approval requires additional continuity checks outside here.
        if not self.cohort_valid:
            reasons.append("COHORT_NOT_VERIFIED")
        return not reasons, tuple(reasons)
