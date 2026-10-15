"""G2 bounded closed-five-minute Observation in memory, no network or trades.

Original trade/quote custody is NOT established by REST klines; this module
preserves a strict closed-only metadata grade and explicit incomplete HOLD.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from .core import INTERVAL_MS, FiveMinuteEvent, canonical_digest
from .universe import UniverseManifest, BTC

OBSERVATION_SCHEMA = "NBOT_V5_1_OBSERVATION_V1"
HISTORY_BARS = 96
MAX_SYMBOLS = 100
_MAX_REASON = re.compile(r"[A-Z][A-Z0-9_]*\Z")


def _decimal(v: object) -> Decimal:
    if type(v) is not str or len(v) > 70:
        raise ValueError("G2_PRICE_FORMAT_INVALID")
    try:
        d = Decimal(v)
    except InvalidOperation as e:
        raise ValueError("G2_PRICE_INVALID") from e
    if not d.is_finite():
        raise ValueError("G2_PRICE_NONFINITE")
    return d


@dataclass(frozen=True)
class ClosedBar:
    symbol: str
    open_ms: int
    close_ms: int
    opening: str
    high: str
    low: str
    closing: str
    volume: str
    received_at_ms: int
    epoch: int
    route: str
    closed: bool = True

    def __post_init__(self):
        if type(self.symbol) is not str or not re.fullmatch(r"[A-Z0-9]{3,24}", self.symbol):
            raise ValueError("G2_BAR_SYMBOL_INVALID")
        if (type(self.open_ms) is not int or self.open_ms < 0
                or self.open_ms % INTERVAL_MS != 0
                or type(self.close_ms) is not int
                or self.close_ms != self.open_ms + INTERVAL_MS - 1):
            raise ValueError("G2_BAR_BOUNDARY_INVALID")
        if (type(self.received_at_ms) is not int or
                self.received_at_ms < self.close_ms + 1 or
                type(self.epoch) is not int or self.epoch < 0 or
                type(self.route) is not str or
                not re.fullmatch(r"[a-z0-9_-]{1,40}", self.route) or
                type(self.closed) is not bool or not self.closed):
            raise ValueError("G2_BAR_SOURCE_NOT_FINAL")
        op, hi, lo, cl, vol = map(_decimal, (self.opening, self.high,
                                             self.low, self.closing, self.volume))
        if min(op, hi, lo, cl) <= 0 or vol < 0 or hi < max(op, cl) or lo > min(op, cl):
            raise ValueError("G2_BAR_OHLCV_INVALID")


def rest_closed_bar(symbol: str, row: object, *, known_at_ms: int, epoch: int,
                    route: str = "public_rest") -> ClosedBar:
    """Only finalized REST USD-M 5m bars; never silently treat last bar as final."""
    if type(row) not in (list, tuple) or len(row) < 7:
        raise ValueError("G2_KLINE_FORMAT_INVALID")
    return ClosedBar(symbol, row[0], row[6], row[1], row[2], row[3],
                     row[4], row[5], known_at_ms, epoch, route)


@dataclass(frozen=True)
class CoinObservation:
    symbol: str
    event_open_ms: int
    bar_open_ms: int | None
    source_epoch: int | None
    route: str | None
    history_count: int
    state: str
    reasons: tuple[str, ...]
    bar_hash: str | None

    def as_record(self) -> dict:
        return {"symbol": self.symbol, "open": self.event_open_ms,
                "last": self.bar_open_ms, "epoch": self.source_epoch,
                "route": self.route, "history": self.history_count,
                "state": self.state, "reasons": list(self.reasons),
                "bar_hash": self.bar_hash}


@dataclass(frozen=True)
class ObservationSnapshot:
    event_open_ms: int
    decision_at_ms: int
    universe_sha: str
    manifest_at_ms: int
    epoch_id: str
    rows: tuple[CoinObservation, ...]
    healthy_count: int
    hold_count: int
    btc_healthy: bool
    snapshot_id: str

    def as_record(self) -> dict:
        return {"schema": OBSERVATION_SCHEMA, "open": self.event_open_ms,
                "decision": self.decision_at_ms,
                "universe": self.universe_sha, "manifest_at": self.manifest_at_ms,
                "epoch": self.epoch_id,
                "rows": [r.as_record() for r in self.rows],
                "healthy": self.healthy_count, "held": self.hold_count,
                "btc_healthy": self.btc_healthy, "id": self.snapshot_id}


class ObservationBook:
    """Only 100 fixed manifest symbols x 96 finished 5m candles in bounded RAM."""

    def __init__(self, universe: UniverseManifest):
        if type(universe) is not UniverseManifest or len(universe.entries) > MAX_SYMBOLS:
            raise ValueError("G2_MANIFEST_INVALID")
        if len(universe.symbols) != len(set(universe.symbols)) or BTC not in universe.symbols:
            raise ValueError("G2_MANIFEST_DENOMINATOR_INVALID")
        self.manifest = universe
        self._buffers: dict[str, deque[ClosedBar]] = {
            s: deque(maxlen=HISTORY_BARS) for s in universe.symbols}
        self._holds: dict[str, set[str]] = {s: set() for s in universe.symbols}
        self._epochs: dict[str, int | None] = {s: None for s in universe.symbols}
        self._routes: dict[str, str | None] = {s: None for s in universe.symbols}

    def _name(self, symbol: str):
        if symbol not in self._buffers or type(symbol) is not str:
            raise ValueError("G2_SYMBOL_NOT_IN_MANIFEST")

    def mark_gap(self, symbol: str, *, reason: str = "SOURCE_GAP") -> None:
        self._name(symbol)
        if type(reason) is not str or not _MAX_REASON.fullmatch(reason):
            raise ValueError("G2_GAP_REASON_INVALID")
        self._holds[symbol].add(reason)

    def reconnect(self, symbol: str, *, next_epoch: int, route: str):
        """A new connection alone never joins or authenticates an old history."""
        self._name(symbol)
        if type(next_epoch) is not int or next_epoch < 0:
            raise ValueError("G2_EPOCH_INVALID")
        if type(route) is not str or not re.fullmatch(r"[a-z0-9_-]{1,40}", route):
            raise ValueError("G2_ROUTE_INVALID")
        if self._epochs[symbol] is not None and next_epoch <= self._epochs[symbol]:
            raise ValueError("G2_EPOCH_NOT_ADVANCED")
        self._buffers[symbol].clear()
        self._epochs[symbol] = next_epoch
        self._routes[symbol] = route
        self._holds[symbol] = {"REBOOTSTRAP_REQUIRED", "SOURCE_EPOCH_CHANGED"}

    def bootstrap(self, symbol: str, bars: list[ClosedBar], *, as_of_ms: int):
        """Replace a full contiguous 96-bar history after explicit gap validation.

        No cached older epoch is merged with new data. Bootstrap never claims
        original high-frequency custody, only basic closed kline continuity.
        """
        self._name(symbol)
        if type(as_of_ms) is not int or not bars or len(bars) < HISTORY_BARS:
            self.mark_gap(symbol, reason="HISTORY_SHORT")
            return False
        last = bars[-HISTORY_BARS:]
        epoch, route = last[0].epoch, last[0].route
        for i, b in enumerate(last):
            if (type(b) is not ClosedBar or b.symbol != symbol
                    or b.epoch != epoch or b.route != route or
                    b.received_at_ms > as_of_ms or b.close_ms + 1 > as_of_ms
                    or (i and b.open_ms != last[i-1].open_ms + INTERVAL_MS)):
                self.mark_gap(symbol, reason="BOOTSTRAP_UNVERIFIED")
                return False
        if self._epochs[symbol] is not None and epoch != self._epochs[symbol]:
            self.mark_gap(symbol, reason="EPOCH_MISMATCH")
            return False
        self._buffers[symbol] = deque(last, maxlen=HISTORY_BARS)
        self._epochs[symbol] = epoch
        self._routes[symbol] = route
        self._holds[symbol].clear()
        return True

    def ingest(self, bar: ClosedBar, *, decision_at_ms: int) -> bool:
        if type(bar) is not ClosedBar:
            raise ValueError("G2_BAR_TYPE_INVALID")
        self._name(bar.symbol)
        s = bar.symbol
        if type(decision_at_ms) is not int or bar.received_at_ms > decision_at_ms:
            self.mark_gap(s, reason="FUTURE_RECEIPT")
            return False
        if bar.close_ms + 1 > decision_at_ms:
            self.mark_gap(s, reason="NOT_CLOSED_ASOF")
            return False
        old_epoch = self._epochs[s]
        if old_epoch is not None and (old_epoch != bar.epoch or self._routes[s] != bar.route):
            self.mark_gap(s, reason="EPOCH_MISMATCH")
            return False
        if self._holds[s]:
            return False  # Require fully verified 96-bar bootstrap to exit HOLD.
        q = self._buffers[s]
        if q:
            prev = q[-1]
            if bar.open_ms == prev.open_ms:
                if bar == prev:
                    return False  # legitimate duplicate replay
                self.mark_gap(s, reason="DUPLICATE_CONFLICT")
                return False
            if bar.open_ms != prev.open_ms + INTERVAL_MS:
                self.mark_gap(s, reason="MISSING_CANDLE")
                return False
        self._epochs[s] = bar.epoch
        self._routes[s] = bar.route
        q.append(bar)
        return True

    def snapshot(self, event: FiveMinuteEvent) -> ObservationSnapshot:
        if type(event) is not FiveMinuteEvent:
            raise ValueError("G2_EVENT_INVALID")
        if self.manifest.selected_at_ms > event.decision_at_ms:
            raise ValueError("G2_FUTURE_UNIVERSE")
        rows: list[CoinObservation] = []
        for symbol in self.manifest.symbols:
            buf = self._buffers[symbol]
            last = buf[-1] if buf else None
            reasons = set(self._holds[symbol])
            if not last:
                reasons.add("NO_CANDLE")
            else:
                if last.open_ms != event.event_open_ms:
                    reasons.add("STALE_OR_FUTURE_CANDLE")
                if last.received_at_ms > event.decision_at_ms:
                    reasons.add("FUTURE_RECEIPT")
                if last.epoch != self._epochs[symbol]:
                    reasons.add("EPOCH_MISMATCH")
            if len(buf) < HISTORY_BARS:
                reasons.add("HISTORY_SHORT")
            bar_hash = canonical_digest("evidence", {
                "symbol": symbol, "open": last.open_ms, "close": last.close_ms,
                "ohlcv": [last.opening, last.high, last.low, last.closing,
                          last.volume], "epoch": last.epoch, "route": last.route,
            }) if last else None
            rows.append(CoinObservation(symbol, event.event_open_ms,
                       last.open_ms if last else None, self._epochs[symbol],
                       self._routes[symbol], len(buf),
                       "HOLD" if reasons else "METADATA_CLOSED",
                       tuple(sorted(reasons)), bar_hash))
        healthy = sum(r.state == "METADATA_CLOSED" for r in rows)
        btc = next(r for r in rows if r.symbol == BTC)
        payload = {"event": event.event_open_ms,
                   "decision": event.decision_at_ms,
                   "universe": self.manifest.selection_digest,
                   "rows": [r.as_record() for r in rows]}
        return ObservationSnapshot(event.event_open_ms, event.decision_at_ms,
                   self.manifest.selection_digest, self.manifest.selected_at_ms,
                   OBSERVATION_SCHEMA, tuple(rows), healthy, len(rows) - healthy,
                   btc.state == "METADATA_CLOSED",
                   canonical_digest("event", payload))

    @property
    def buffered_candles(self) -> int:
        return sum(len(q) for q in self._buffers.values())
