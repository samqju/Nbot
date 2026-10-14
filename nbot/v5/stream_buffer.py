"""Bounded V5 WSS ingestion state: latest quote, trade cursor, closed candles.

No raw-quote archive, orders, model, account access, database or daemon.
A live WSS message is processed via the validated V5 WSS parser. Historical
candles may be seeded ONLY using audited closed Binance REST klines.
WSS disconnects do not silently repair trade or quote continuity.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from nbot.v5.observation_contract import INTERVAL_MS, MAX_SYMBOLS
from nbot.v5.public_market import decode_klines
from nbot.v5.ws_contract import FeedStatus, UnsafeStream, decode_frame, stream_urls

HISTORY = 96


@dataclass
class CoinWindow:
    """Strictly bounded per-coin data; no mutable raw-frame archive."""

    last_quote: dict | None = None
    last_quote_update_id: int | None = None
    last_trade: dict | None = None
    closed_candles: deque = field(default_factory=lambda: deque(maxlen=HISTORY))
    history_anchored: bool = False
    candle_gap: bool = False
    candle_conflict: bool = False
    statistics: Counter = field(default_factory=Counter)


class BoundedObservationBuffer:
    """In-memory prototype; strictly no automatic decision readiness.

    Maintains at most 51 symbol states and 96 candles per symbol. Full
    long-running health, persistent event/quote/provenance storage, and
    recovery approval are future, separately tested milestones.
    """

    def __init__(self, symbols: Sequence[str], *, quote_mode: str = "bookTicker") -> None:
        stream_urls(symbols, quote_mode=quote_mode)  # Validate 1..50, dedicated routes.
        self.quote_mode = quote_mode
        self.eligible = tuple(sorted(symbols))
        self.all_symbols = tuple(sorted(set(symbols) | {"BTCUSDT"}))
        if len(self.all_symbols) > MAX_SYMBOLS + 1:
            raise UnsafeStream("V5_BUFFER_CAPACITY_INVALID")
        self.coins = {symbol: CoinWindow() for symbol in self.all_symbols}
        self.health = FeedStatus()
        self.totals: Counter = Counter()

    def connect(self, route: str) -> None:
        self.health.connect(route)
        if route == "market":
            for coin in self.coins.values():
                # Already verified historical candles remain in memory, but
                # restart/reconnect invalidates all claim of continuous WSS.
                coin.history_anchored = False
                coin.last_trade = None
        else:
            for coin in self.coins.values():
                coin.last_quote = None
                coin.last_quote_update_id = None

    def disconnect(self, route: str) -> None:
        self.health.disconnect(route)
        if route == "market":
            for coin in self.coins.values():
                coin.history_anchored = False
                coin.last_trade = None
        else:
            for coin in self.coins.values():
                coin.last_quote = None
                coin.last_quote_update_id = None

    def seed_closed_candles(
        self, symbol: str, rows: Sequence[list], *, event_open_ms: int
    ) -> None:
        """Seed exactly 96 contiguous fully closed REST bars; no trade repair.

        Only after a separate historical REST request specifically tied to an
        as-of event. Do not convert this action to a quote/trade recovery.
        """
        if symbol not in self.coins:
            raise UnsafeStream("V5_BUFFER_SYMBOL_NOT_ELIGIBLE")
        try:
            bars = decode_klines(rows, event_open_ms=event_open_ms)
        except ValueError as exc:
            raise UnsafeStream("V5_BUFFER_BOOTSTRAP_INVALID") from exc
        coin = self.coins[symbol]
        if coin.candle_gap or coin.candle_conflict:
            raise UnsafeStream("V5_BUFFER_MANUAL_REPAIR_REQUIRED")
        if coin.closed_candles:
            last = coin.closed_candles[-1][0]
            if last > event_open_ms:
                raise UnsafeStream("V5_BUFFER_BOOTSTRAP_REWIND")
            overlap = {bar[0]: bar for bar in coin.closed_candles}
            for b in bars:
                if b[0] in overlap and overlap[b[0]] != b:
                    coin.candle_conflict = True
                    raise UnsafeStream("V5_BUFFER_REST_WSS_CONFLICT")
        coin.closed_candles = deque(bars, maxlen=HISTORY)
        coin.history_anchored = True

    def consume(self, route: str, frame: str | bytes, *, received_ms: int) -> str:
        """Ingest a frame without storing it. Return a bounded event category."""
        parsed = decode_frame(
            route, frame, received_ms=received_ms, subscribed_symbols=self.eligible,
        )
        return self.consume_decoded(parsed)

    def consume_decoded(self, parsed: Mapping[str, object]) -> str:
        """Consume an already verified frame without a second JSON decode.

        Only use after decode_frame has validated the exact frozen universe.
        This path makes no SQLite writes and retains only latest tick state.
        """
        if (parsed.get("route") not in ("market", "public")
                or parsed.get("symbol") not in self.coins
                or parsed.get("kind") not in ("aggTrade", "bookTicker",
                                             "depth5@500ms", "kline_5m")):
            raise UnsafeStream("V5_BUFFER_DECODED_FRAME_INVALID")
        symbol = parsed["symbol"]
        coin = self.coins[symbol]
        kind = parsed["kind"]
        if kind in ("bookTicker", "depth5@500ms"):
            if kind != self.quote_mode:
                raise UnsafeStream("V5_BUFFER_WRONG_QUOTE_SOURCE")
            if not self.health.public_connected:
                raise UnsafeStream("V5_BUFFER_QUOTE_SOCKET_DISCONNECTED")
            update_id = parsed["update_id"]
            if coin.last_quote_update_id is not None and update_id <= coin.last_quote_update_id:
                self.totals["out_of_order_quote"] += 1
                return "OUT_OF_ORDER_QUOTE"
            self.health.accept(parsed)
            # Replace the old quote; 2,000 messages still occupy ONE slot.
            coin.last_quote = parsed
            coin.last_quote_update_id = update_id
            self.totals["quote"] += 1
            return "QUOTE_LATEST_REPLACED"
        if kind == "aggTrade":
            if not self.health.market_connected:
                raise UnsafeStream("V5_BUFFER_MARKET_SOCKET_DISCONNECTED")
            previous = self.health.last_agg_id.get(symbol)
            self.health.accept(parsed)
            if previous is not None and parsed["aggregate_id"] <= previous:
                self.totals["out_of_order_trade"] += 1
                return "OUT_OF_ORDER_TRADE"
            coin.last_trade = parsed
            self.totals["trade"] += 1
            return "TRADE_CURSOR_ADVANCED"

        if not self.health.market_connected:
            raise UnsafeStream("V5_BUFFER_MARKET_SOCKET_DISCONNECTED")
        if not parsed["closed"]:
            self.totals["unclosed_kline_ignored"] += 1
            return "UNFINISHED_CANDLE_IGNORED"
        bar = parsed["candle"]
        opens = coin.closed_candles
        if opens:
            prior = opens[-1]
            if bar[0] == prior[0]:
                if bar != prior:
                    coin.candle_conflict = True
                    coin.history_anchored = False
                    self.totals["conflicting_close"] += 1
                    raise UnsafeStream("V5_BUFFER_CONFLICTING_FINAL_CANDLE")
                self.totals["duplicate_close"] += 1
                return "DUPLICATE_FINAL_CANDLE"
            if bar[0] < prior[0]:
                self.totals["old_close"] += 1
                return "OLD_FINAL_CANDLE"
            if bar[0] != prior[0] + INTERVAL_MS:
                coin.candle_gap = True
                coin.history_anchored = False
                self.health.cohort_valid = False
                self.totals["candle_gap"] += 1
                # Retain the last valid cursor so no later frame "repairs"
                # an unobserved interval by simply advancing the cursor.
                return "CANDLE_GAP_HOLD"
        self.health.accept(parsed)
        opens.append(bar)
        self.totals["closed_kline"] += 1
        return "CLOSED_CANDLE_ACCEPTED"

    def candle_readiness(self, *, symbol: str, event_open_ms: int,
                         now_ms: int) -> tuple[bool, tuple[str, ...]]:
        """Conservative closed-candle readiness, NOT trade authorization."""
        if symbol not in self.coins:
            raise UnsafeStream("V5_BUFFER_SYMBOL_NOT_ELIGIBLE")
        coin = self.coins[symbol]
        reasons = []
        if not self.health.market_connected:
            reasons.append("MARKET_DISCONNECTED")
        if not coin.history_anchored:
            reasons.append("HISTORY_NOT_ANCHORED")
        if coin.candle_gap:
            reasons.append("CANDLE_GAP_UNRESOLVED")
        if coin.candle_conflict:
            reasons.append("CANDLE_SOURCE_CONFLICT")
        if len(coin.closed_candles) != HISTORY:
            reasons.append("HISTORY_NOT_96_BARS")
        else:
            items = tuple(coin.closed_candles)
            if items[-1][0] != event_open_ms:
                reasons.append("EVENT_CLOSE_MISSING")
            if any(b[0] - a[0] != INTERVAL_MS for a, b in zip(items, items[1:])):
                reasons.append("HISTORY_GAP")
        if now_ms < event_open_ms + INTERVAL_MS:
            reasons.append("CANDLE_NOT_CLOSED_YET")
        return not reasons, tuple(reasons)

    def describe(self) -> dict:
        return {
            "mode": "RESEARCH_OBSERVATION_ONLY",
            "order_authority": "NONE",
            "symbol_count": len(self.all_symbols),
            "closed_candle_capacity_per_symbol": HISTORY,
            "total_candles_retained": sum(len(c.closed_candles) for c in self.coins.values()),
            "quote_mode": self.quote_mode,
            "latest_quotes_retained": sum(c.last_quote is not None for c in self.coins.values()),
            "latest_trades_retained": sum(c.last_trade is not None for c in self.coins.values()),
            "event_counts": dict(self.totals),
            "cohort_verified": self.health.cohort_valid,
        }
