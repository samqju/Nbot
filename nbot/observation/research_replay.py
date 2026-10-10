"""Capital-uncapped research-only counterfactual book.

Tick-policy hypotheses are evaluated incrementally: each market event updates a
small state object and is then discarded. This keeps memory bounded even when a
high-volume symbol produces millions of aggregate trades during a four-hour
research horizon. Bar-close hypotheses retain the shared-buffer fallback because
they need bar-boundary replay semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import threading
from typing import Any

from .chronological_replay import TradeEvent
from .counterfactual import EvidenceQuality, PolicyOutcome, ReplayCosts, TrailPolicy, replay_policy

AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"


@dataclass(frozen=True)
class ReplayHypothesis:
    decision_id: str
    symbol: str
    side: str
    entry_price: float
    one_r_price: float
    entry_time_ms: int
    policy: TrailPolicy
    horizon_ms: int = 4 * 60 * 60 * 1000
    costs: ReplayCosts = ReplayCosts()


@dataclass
class _TickState:
    hypothesis: ReplayHypothesis
    stop_r: int = -1
    peak_r: float = 0.0
    trough_r: float = 0.0
    seen: int = 0
    last_id: int | None = None
    last_time_ms: int | None = None
    last_price: float | None = None
    first_trade_ms: int | None = None
    exit_time_ms: int | None = None
    exit_price: float | None = None
    exit_reason: str = "HORIZON"
    gap_unresolved: bool = False
    digest: Any = field(default_factory=hashlib.sha256)

    def ingest(self, event: TradeEvent) -> None:
        h = self.hypothesis
        if event.symbol != h.symbol or self.exit_price is not None or self.gap_unresolved:
            return
        if event.trade_time_ms < h.entry_time_ms:
            return
        if event.trade_time_ms > h.entry_time_ms + h.horizon_ms:
            return
        if (event.trade_id == self.last_id and event.trade_time_ms == self.last_time_ms
                and event.price == self.last_price):
            return  # retransmission is not a missing or reversed path

        canonical = json.dumps(
            [event.symbol, event.trade_id, event.trade_time_ms, event.price],
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        self.digest.update(canonical)
        if self.last_time_ms is not None:
            if event.trade_time_ms < self.last_time_ms or event.trade_id <= int(self.last_id):
                self.gap_unresolved = True
                return
            if event.trade_id != int(self.last_id) + 1:
                self.gap_unresolved = True
                return

        self.last_id = event.trade_id
        if self.first_trade_ms is None:
            self.first_trade_ms = event.trade_time_ms
        self.last_time_ms = event.trade_time_ms
        self.last_price = event.price
        self.seen += 1
        direction = 1 if h.side == "LONG" else -1
        r_value = direction * (event.price - h.entry_price) / h.one_r_price
        self.peak_r = max(self.peak_r, r_value)
        self.trough_r = min(self.trough_r, r_value)
        if r_value <= self.stop_r:
            self.exit_time_ms = event.trade_time_ms
            self.exit_price = event.price
            self.exit_reason = "STOP"
            return
        if self.peak_r >= 1:
            self.stop_r = max(self.stop_r, math.floor(self.peak_r) - 1)

    def outcome(self, *, now_ms: int) -> PolicyOutcome | None:
        h = self.hypothesis
        if self.exit_price is None and not self.gap_unresolved and now_ms < h.entry_time_ms + h.horizon_ms:
            return None
        digest = self.digest.hexdigest()
        if self.gap_unresolved or self.seen == 0:
            return PolicyOutcome(
                h.policy.value, EvidenceQuality.GAP_UNRESOLVED, "GAP_UNRESOLVED",
                None, None, None, None, self.peak_r, self.trough_r, self.stop_r,
                self.seen, False, digest,
            )

        exit_time = self.exit_time_ms
        exit_price = self.exit_price
        exit_reason = self.exit_reason
        if exit_price is None:
            exit_time = self.last_time_ms
            exit_price = self.last_price
            exit_reason = "HORIZON"
        direction = 1 if h.side == "LONG" else -1
        gross_r = direction * (float(exit_price) - h.entry_price) / h.one_r_price
        fee_r = 2.0 * h.costs.taker_fee_rate * h.entry_price / h.one_r_price
        slip_r = (
            (h.costs.entry_slippage_bps + h.costs.exit_slippage_bps)
            / 10000.0 * h.entry_price / h.one_r_price
        )
        net_r = gross_r - fee_r - slip_r - h.costs.funding_r
        return PolicyOutcome(
            h.policy.value, EvidenceQuality.AGGTRADE_RESOLVED, exit_reason,
            exit_time, exit_price, gross_r, net_r, self.peak_r, self.trough_r,
            self.stop_r, self.seen, False, digest,
        )


@dataclass
class _BufferedState:
    hypothesis: ReplayHypothesis
    events: list[TradeEvent] = field(default_factory=list)


class ResearchReplayBook:
    """Overlapping hypotheses with streaming tick evaluation and thread safety."""

    def __init__(self) -> None:
        self._active: dict[str, _TickState | _BufferedState] = {}
        self._by_symbol: dict[str, set[str]] = {}
        self._results: dict[str, PolicyOutcome] = {}
        self._lock = threading.RLock()

    def add(self, hypothesis: ReplayHypothesis) -> None:
        with self._lock:
            if hypothesis.decision_id in self._active or hypothesis.decision_id in self._results:
                raise ValueError("REPLAY_DECISION_ALREADY_EXISTS")
            state: _TickState | _BufferedState
            if hypothesis.policy is TrailPolicy.TICK_INTEGER_R:
                state = _TickState(hypothesis)
            else:
                state = _BufferedState(hypothesis)
            self._active[hypothesis.decision_id] = state
            self._by_symbol.setdefault(hypothesis.symbol, set()).add(hypothesis.decision_id)

    def ingest(self, event: TradeEvent) -> None:
        with self._lock:
            for decision_id in tuple(self._by_symbol.get(event.symbol, ())):
                state = self._active[decision_id]
                if isinstance(state, _TickState):
                    state.ingest(event)
                else:
                    h = state.hypothesis
                    if h.entry_time_ms <= event.trade_time_ms <= h.entry_time_ms + h.horizon_ms:
                        state.events.append(event)

    def _mature_unlocked(
        self, decision_id: str, *, now_ms: int, force: bool = False
    ) -> PolicyOutcome | None:
        state = self._active.get(decision_id)
        if state is None:
            return self._results.get(decision_id)
        h = state.hypothesis
        if isinstance(state, _TickState):
            outcome = state.outcome(
                now_ms=(h.entry_time_ms + h.horizon_ms if force else now_ms)
            )
        else:
            if not force and now_ms < h.entry_time_ms + h.horizon_ms:
                return None
            outcome = replay_policy(
                state.events, symbol=h.symbol, side=h.side, entry_price=h.entry_price,
                one_r_price=h.one_r_price, entry_time_ms=h.entry_time_ms, policy=h.policy,
                costs=h.costs, horizon_ms=h.horizon_ms,
            )
        if outcome is None:
            return None
        self._results[decision_id] = outcome
        del self._active[decision_id]
        self._by_symbol[h.symbol].discard(decision_id)
        if not self._by_symbol[h.symbol]:
            del self._by_symbol[h.symbol]
        return outcome

    def invalidate_paths(self, symbols) -> None:
        """Disconnected transport cannot prove uninterrupted chronology."""
        with self._lock:
            for symbol in symbols:
                for decision_id in self._by_symbol.get(symbol, ()):
                    state = self._active[decision_id]
                    if isinstance(state, _TickState):
                        state.gap_unresolved = True

    def evidence(self, decision_id):
        with self._lock:
            state = self._active.get(decision_id)
            if not isinstance(state, _TickState):
                return {}
            return {"first_trade_ms": state.first_trade_ms, "continuous": not state.gap_unresolved}

    def forget_result(self, decision_id):
        with self._lock:
            self._results.pop(decision_id, None)

    def mature(self, decision_id: str, *, now_ms: int, force: bool = False) -> PolicyOutcome | None:
        with self._lock:
            return self._mature_unlocked(decision_id, now_ms=now_ms, force=force)

    def mature_due(self, *, now_ms: int) -> dict[str, PolicyOutcome]:
        with self._lock:
            matured = {}
            for decision_id, state in tuple(self._active.items()):
                h = state.hypothesis
                early_exit = isinstance(state, _TickState) and (
                    state.exit_price is not None or state.gap_unresolved
                )
                if early_exit or now_ms >= h.entry_time_ms + h.horizon_ms:
                    outcome = self._mature_unlocked(
                        decision_id, now_ms=now_ms, force=early_exit
                    )
                    if outcome is not None:
                        matured[decision_id] = outcome
            return matured

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    @property
    def active_ids(self):
        with self._lock:
            return tuple(self._active)

    @property
    def active_symbols(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(symbol for symbol, ids in self._by_symbol.items() if ids))

    def active_decisions_for_symbol(self, symbol: str) -> int:
        with self._lock:
            return len(self._by_symbol.get(symbol, ()))

    def buffered_event_count(self, symbol: str | None = None) -> int:
        with self._lock:
            states = list(self._active.values())
            if symbol is not None:
                states = [
                    state for state in states if state.hypothesis.symbol == symbol
                ]
            return sum(
                len(state.events) for state in states if isinstance(state, _BufferedState)
            )
