"""Capital-uncapped research-only counterfactual book.

Unlike legacy shadow accounts this book deliberately does not reserve balance or
consume paper position slots. Every sampled candidate may mature independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .chronological_replay import TradeEvent
from .counterfactual import PolicyOutcome, ReplayCosts, TrailPolicy, replay_policy

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
class _Active:
    hypothesis: ReplayHypothesis
    events: list[TradeEvent] = field(default_factory=list)


class ResearchReplayBook:
    """Overlapping long/short hypotheses without capital or slot limits."""

    def __init__(self) -> None:
        self._active: dict[str, _Active] = {}
        self._by_symbol: dict[str, set[str]] = {}
        self._results: dict[str, PolicyOutcome] = {}

    def add(self, hypothesis: ReplayHypothesis) -> None:
        if hypothesis.decision_id in self._active or hypothesis.decision_id in self._results:
            raise ValueError("REPLAY_DECISION_ALREADY_EXISTS")
        self._active[hypothesis.decision_id] = _Active(hypothesis)
        self._by_symbol.setdefault(hypothesis.symbol, set()).add(hypothesis.decision_id)

    def ingest(self, event: TradeEvent) -> None:
        for decision_id in tuple(self._by_symbol.get(event.symbol, ())):
            active = self._active[decision_id]
            h = active.hypothesis
            if event.trade_time_ms >= h.entry_time_ms:
                active.events.append(event)

    def mature(self, decision_id: str, *, now_ms: int, force: bool = False) -> PolicyOutcome | None:
        active = self._active.get(decision_id)
        if active is None:
            return self._results.get(decision_id)
        h = active.hypothesis
        if not force and now_ms < h.entry_time_ms + h.horizon_ms:
            return None
        result = replay_policy(active.events, symbol=h.symbol, side=h.side, entry_price=h.entry_price,
                               one_r_price=h.one_r_price, entry_time_ms=h.entry_time_ms, policy=h.policy,
                               costs=h.costs, horizon_ms=h.horizon_ms)
        self._results[decision_id] = result
        del self._active[decision_id]
        self._by_symbol[h.symbol].discard(decision_id)
        return result

    def mature_due(self, *, now_ms: int) -> dict[str, PolicyOutcome]:
        matured = {}
        for decision_id, active in tuple(self._active.items()):
            if now_ms >= active.hypothesis.entry_time_ms + active.hypothesis.horizon_ms:
                outcome = self.mature(decision_id, now_ms=now_ms)
                if outcome is not None:
                    matured[decision_id] = outcome
        return matured

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def active_symbols(self) -> tuple[str, ...]:
        """Symbols that must remain on the high-resolution feed until maturity."""
        return tuple(sorted(symbol for symbol, ids in self._by_symbol.items() if ids))

    def active_decisions_for_symbol(self, symbol: str) -> int:
        return len(self._by_symbol.get(symbol, ()))
