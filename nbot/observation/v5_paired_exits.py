"""V5 paired exit-policy *research lab*, driven by certified future trade+quote ticks.

One entry, one streaming chronological evidence digest, three independent
exit-policy states. No exchange client, no order authority, no background
services. The shared path MUST remain valid through the entire horizon,
even when all experimental policy arms exit early.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import threading
from typing import Iterable

from .v5_accounting import FundingSettlement, TradeAccounting, score_trade

VERSION = "NBOT_V5_PAIRED_EXIT_LAB_V1"
ORDER_AUTHORITY = "NONE"
HORIZON_MS = 4 * 60 * 60 * 1000
HORIZON_CLOSE_GRACE_MS = 5_000
MAX_QUOTE_AGE_MS = 2_000
MAX_RECEIPT_DELAY_MS = 2_000
MAX_ENTRY_ANCHOR_AGE_MS = 5_000
MAX_CONCURRENT = 100
MAX_PENDING_RESULTS = 100
EXIT_POLICIES = ("FIXED_2R_V1", "TIME_EXIT_V1", "INTEGER_TRAIL_V1")


def _positive(x: float) -> bool:
    try:
        y = float(x)
    except (ValueError, TypeError):
        return False
    return math.isfinite(y) and y > 0


def _encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class PairedEntry:
    decision_id: str
    symbol: str
    side: str
    entry_time_ms: int
    entry_bid: float
    entry_ask: float
    entry_quote_time_ms: int
    quantity: float
    initial_stop_price: float
    anchor_agg_id: int
    anchor_trade_time_ms: int
    horizon_ms: int = HORIZON_MS

    def __post_init__(self) -> None:
        if (not self.decision_id or not self.symbol
                or self.symbol != self.symbol.upper() or self.side not in ("LONG", "SHORT")):
            raise ValueError("V5_PAIRED_ENTRY_ID_INVALID")
        if (any(type(x) is not int for x in
                (self.entry_time_ms, self.entry_quote_time_ms,
                 self.anchor_agg_id, self.anchor_trade_time_ms, self.horizon_ms))
                or self.anchor_agg_id < 0 or self.horizon_ms != HORIZON_MS
                or self.anchor_trade_time_ms > self.entry_time_ms
                or self.entry_quote_time_ms > self.entry_time_ms
                or self.entry_time_ms - self.anchor_trade_time_ms > MAX_ENTRY_ANCHOR_AGE_MS
                or self.entry_time_ms - self.entry_quote_time_ms > MAX_QUOTE_AGE_MS
                or min(self.anchor_trade_time_ms, self.entry_quote_time_ms) < 0):
            raise ValueError("V5_PAIRED_ENTRY_CHRONOLOGY_INVALID")
        if (not all(_positive(v) for v in
                    (self.entry_bid, self.entry_ask, self.quantity,
                     self.initial_stop_price))
                or self.entry_bid >= self.entry_ask):
            raise ValueError("V5_PAIRED_ENTRY_PRICE_INVALID")
        entry = self.entry_ask if self.side == "LONG" else self.entry_bid
        if ((self.side == "LONG" and self.initial_stop_price >= entry)
                or (self.side == "SHORT" and self.initial_stop_price <= entry)):
            raise ValueError("V5_PAIRED_INITIAL_STOP_NOT_MINUS_1R")

    @property
    def entry_price(self) -> float:
        return self.entry_ask if self.side == "LONG" else self.entry_bid

    @property
    def one_r_price(self) -> float:
        return abs(self.entry_price - self.initial_stop_price)


@dataclass(frozen=True)
class PairedTick:
    symbol: str
    agg_id: int
    trade_time_ms: int
    receipt_time_ms: int
    trade_price: float
    quote_time_ms: int
    quote_update_id: int
    bid: float
    ask: float


@dataclass
class _Arm:
    policy_id: str
    stop_r: int = -1
    high_r: float = 0.0
    low_r: float = 0.0
    exit_time_ms: int | None = None
    exit_price: float | None = None
    exit_reason: str | None = None

    def apply(self, *, time_ms: int, price: float, entry: PairedEntry,
              horizon: bool) -> None:
        if self.exit_time_ms is not None:
            return
        direction = 1 if entry.side == "LONG" else -1
        r = direction * (price - entry.entry_price) / entry.one_r_price
        self.high_r = max(self.high_r, r)
        self.low_r = min(self.low_r, r)
        if horizon:
            self.exit_time_ms, self.exit_price, self.exit_reason = (
                time_ms, price, "HORIZON")
        elif r <= self.stop_r:
            # Stop trigger consumes the first actual executable quote crossing
            # the stop. Jumps may overshoot -1R; never manufacture a stop fill.
            self.exit_time_ms, self.exit_price, self.exit_reason = (
                time_ms, price, "STOP")
        elif self.policy_id == "FIXED_2R_V1" and r >= 2.0:
            self.exit_time_ms, self.exit_price, self.exit_reason = (
                time_ms, price, "TARGET")
        elif self.policy_id == "INTEGER_TRAIL_V1" and self.high_r >= 1.0:
            # The newly raised stop becomes active only for the *next* tick.
            self.stop_r = max(self.stop_r, math.floor(self.high_r) - 1)


@dataclass(frozen=True)
class ArmResult:
    decision_id: str
    policy_id: str
    status: str
    reason: str
    exit_time_ms: int | None
    exit_reason: str | None
    mfe_r: float
    mae_r: float
    final_stop_r: int
    events_seen: int
    evidence_digest: str
    accounting: TradeAccounting | None


@dataclass
class _Path:
    entry: PairedEntry
    arms: dict[str, _Arm] = field(default_factory=lambda: {
        name: _Arm(name) for name in EXIT_POLICIES
    })
    digest: object = field(default_factory=hashlib.sha256)
    last_agg_id: int | None = None
    last_trade_time_ms: int | None = None
    last_quote_update_id: int | None = None
    last_tick: PairedTick | None = None
    events_seen: int = 0
    horizon_witnessed: bool = False
    gap_reason: str | None = None

    def __post_init__(self) -> None:
        self.last_agg_id = self.entry.anchor_agg_id
        self.last_trade_time_ms = self.entry.anchor_trade_time_ms
        self.digest.update(_encode({"v": VERSION, "entry": asdict(self.entry)}))

    @property
    def deadline(self) -> int:
        return self.entry.entry_time_ms + self.entry.horizon_ms

    def invalidate(self, reason: str) -> None:
        if not self.horizon_witnessed and self.gap_reason is None:
            self.gap_reason = reason

    def ingest(self, tick: PairedTick) -> None:
        if self.gap_reason or self.horizon_witnessed:
            return
        e = self.entry
        if tick.symbol != e.symbol:
            self.invalidate("SYMBOL_MISMATCH")
            return
        if tick == self.last_tick:
            return  # Identical network retransmission is harmless.
        if (any(type(v) is not int for v in (
                tick.agg_id, tick.trade_time_ms, tick.receipt_time_ms,
                tick.quote_time_ms, tick.quote_update_id))
                or not all(_positive(v) for v in
                           (tick.trade_price, tick.bid, tick.ask))
                or tick.ask <= tick.bid):
            self.invalidate("TICK_MALFORMED")
            return
        if (tick.agg_id != self.last_agg_id + 1
                or tick.trade_time_ms < self.last_trade_time_ms
                or tick.trade_time_ms <= e.entry_time_ms
                or tick.receipt_time_ms < tick.trade_time_ms
                or tick.receipt_time_ms - tick.trade_time_ms > MAX_RECEIPT_DELAY_MS
                or tick.quote_update_id <= 0
                or tick.quote_time_ms > tick.trade_time_ms
                or tick.quote_time_ms < e.entry_quote_time_ms
                or tick.trade_time_ms - tick.quote_time_ms > MAX_QUOTE_AGE_MS
                or (self.last_quote_update_id is not None
                    and tick.quote_update_id < self.last_quote_update_id)):
            self.invalidate("TICK_GAP_OR_STALE_QUOTE")
            return
        if tick.trade_time_ms > self.deadline + HORIZON_CLOSE_GRACE_MS:
            self.invalidate("HORIZON_CLOSE_WITNESS_MISSING")
            return
        try:
            canonical = _encode(asdict(tick))
        except (ValueError, TypeError):
            self.invalidate("TICK_UNSERIALIZABLE")
            return
        self.digest.update(canonical)
        self.last_tick = tick
        self.last_agg_id = tick.agg_id
        self.last_trade_time_ms = tick.trade_time_ms
        self.last_quote_update_id = tick.quote_update_id
        self.events_seen += 1
        horizon = tick.trade_time_ms >= self.deadline
        px = tick.bid if e.side == "LONG" else tick.ask
        for arm in self.arms.values():
            arm.apply(time_ms=tick.trade_time_ms, price=px,
                      entry=e, horizon=horizon)
        if horizon:
            self.horizon_witnessed = True

    def ready(self, now_ms: int) -> bool:
        return (
            self.gap_reason is not None
            or (now_ms >= self.deadline and self.horizon_witnessed)
            or now_ms > self.deadline + HORIZON_CLOSE_GRACE_MS
        )

    def results(self, *, now_ms: int,
                funding_events: Iterable[FundingSettlement],
                funding_coverage_confirmed: bool) -> tuple[ArmResult, ...] | None:
        if not self.ready(now_ms):
            return None
        events = tuple(funding_events)
        reason = self.gap_reason
        if reason is None and not self.horizon_witnessed:
            reason = "HORIZON_CLOSE_WITNESS_MISSING"
        if reason is None and not funding_coverage_confirmed:
            reason = "FUNDING_COVERAGE_UNPROVEN"
        if reason is None and any(
                a.exit_price is None or a.exit_time_ms is None for a in self.arms.values()):
            reason = "EXIT_PATH_INCOMPLETE"
        digest = self.digest.hexdigest()
        # Either every arm has independently auditable accounting or none
        # can be used for a *paired* comparison. A funding-boundary ambiguity
        # in one policy must not preferentially discard just that arm.
        scored: dict[str, TradeAccounting] = {}
        if reason is None:
            try:
                for arm in self.arms.values():
                    scored[arm.policy_id] = score_trade(
                        symbol=self.entry.symbol, side=self.entry.side,
                        quantity=self.entry.quantity,
                        entry_fill_price=self.entry.entry_price,
                        exit_fill_price=arm.exit_price,
                        initial_stop_price=self.entry.initial_stop_price,
                        entry_time_ms=self.entry.entry_time_ms,
                        exit_time_ms=arm.exit_time_ms,
                        funding_events=events,
                        funding_coverage_confirmed=True,
                    )
            except (TypeError, ValueError):
                reason = "ACCOUNTING_OR_FUNDING_UNSCORABLE"
                scored.clear()
        outputs = [
            ArmResult(
                self.entry.decision_id, arm.policy_id,
                "UNSCORABLE" if reason else "SCORED",
                reason or "CONTIGUOUS_AGGTRADE_RESOLVED",
                arm.exit_time_ms if not reason else None,
                arm.exit_reason if not reason else None,
                arm.high_r, arm.low_r, arm.stop_r, self.events_seen,
                digest, scored.get(arm.policy_id),
            )
            for arm in self.arms.values()
        ]
        return tuple(outputs)


class PairedExitLab:
    """Bounded, synchronous research-only state: one position, three arms."""

    def __init__(self) -> None:
        self._paths: dict[str, _Path] = {}
        self._by_symbol: dict[str, set[str]] = {}
        self._completed: dict[str, tuple[ArmResult, ...]] = {}
        self._lock = threading.RLock()

    def add(self, entry: PairedEntry) -> None:
        if not isinstance(entry, PairedEntry):
            raise ValueError("V5_PAIRED_ENTRY_REQUIRED")
        with self._lock:
            if entry.decision_id in self._paths or entry.decision_id in self._completed:
                raise ValueError("V5_PAIRED_DECISION_REUSED")
            if len(self._paths) >= MAX_CONCURRENT:
                raise ValueError("V5_PAIRED_CAPACITY_EXCEEDED")
            if any(path.entry.symbol == entry.symbol and
                   path.entry.side == entry.side for path in self._paths.values()):
                raise ValueError("V5_PAIRED_SYMBOL_SIDE_ACTIVE")
            self._paths[entry.decision_id] = _Path(entry)
            self._by_symbol.setdefault(entry.symbol, set()).add(entry.decision_id)

    def ingest(self, tick: PairedTick) -> None:
        if not isinstance(tick, PairedTick):
            raise ValueError("V5_PAIRED_TICK_REQUIRED")
        with self._lock:
            for decision_id in tuple(self._by_symbol.get(tick.symbol, ())):
                self._paths[decision_id].ingest(tick)

    def invalidate_symbol(self, symbol: str, *, reason: str) -> None:
        if not reason or reason not in (
                "WSS_DISCONNECTED", "WSS_GAP", "PROCESS_RESTART",
                "QUOTE_GAP", "FEED_UNCERTAIN"):
            raise ValueError("V5_PAIRED_INVALIDATION_REASON_INVALID")
        with self._lock:
            for decision_id in self._by_symbol.get(symbol, ()):
                self._paths[decision_id].invalidate(reason)

    def finalize(
        self, decision_id: str, *, now_ms: int,
        funding_events: Iterable[FundingSettlement] = (),
        funding_coverage_confirmed: bool = False,
    ) -> tuple[ArmResult, ...] | None:
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError("V5_PAIRED_NOW_INVALID")
        with self._lock:
            if decision_id in self._completed:
                return self._completed[decision_id]
            path = self._paths[decision_id]
            rows = path.results(
                now_ms=now_ms, funding_events=funding_events,
                funding_coverage_confirmed=funding_coverage_confirmed)
            if rows is None:
                return None
            if len(self._completed) >= MAX_PENDING_RESULTS:
                # No unbounded in-RAM accumulation when SQLite is unavailable.
                # Keep the original path for safe retry after persistence frees room.
                raise RuntimeError("V5_PAIRED_PERSISTENCE_BACKPRESSURE")
            del self._paths[decision_id]
            members = self._by_symbol[path.entry.symbol]
            members.remove(decision_id)
            if not members:
                del self._by_symbol[path.entry.symbol]
            self._completed[decision_id] = rows
            return rows

    def acknowledge_persisted(self, decision_id: str) -> None:
        """Caller releases the bounded completion cache only after ledger commit."""
        with self._lock:
            if decision_id not in self._completed:
                raise ValueError("V5_PAIRED_NOT_FINALIZED")
            del self._completed[decision_id]

    @property
    def active_count(self) -> int:
        return len(self._paths)

    @property
    def pending_persistence(self) -> int:
        return len(self._completed)


def persist_to_v5_ledger(store: object, results: tuple[ArmResult, ...]) -> None:
    """Idempotent append per policy, using V5's immutable ledger contract.

    Caller must initialize the ledger and first record the frozen decision.
    A mid-write exception is retried using identical rows; this is NOT an
    atomic cross-policy transaction, so never acknowledge before all succeed.
    """
    from .v5_foundation import V5EvidenceStore
    if (not isinstance(store, V5EvidenceStore) or len(results) != len(EXIT_POLICIES)
            or {r.policy_id for r in results} != set(EXIT_POLICIES)
            or len({r.decision_id for r in results}) != 1
            or len({r.evidence_digest for r in results}) != 1
            or any(r.status not in ("SCORED", "UNSCORABLE")
                   or (r.status == "SCORED") != (r.accounting is not None)
                   for r in results)):
        raise ValueError("V5_PAIRED_PERSISTENCE_CONTRACT_INVALID")
    for result in results:
        store.record_outcome(
            decision_id=result.decision_id,
            exit_policy_id=result.policy_id,
            evidence_digest=result.evidence_digest,
            result=result.accounting,
            unscorable_reason=result.reason if result.status == "UNSCORABLE" else None,
        )


def submit_order(*_args, **_kwargs):
    raise RuntimeError("V5_HAS_NO_ORDER_AUTHORITY")
