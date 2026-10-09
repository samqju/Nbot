"""Capital-uncapped research-only counterfactual book.

Unlike legacy shadow accounts this book deliberately does not reserve balance or
consume paper position slots. Trade events are stored once per symbol and shared
by every overlapping hypothesis for that symbol.
"""
from __future__ import annotations

from dataclasses import dataclass

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


class ResearchReplayBook:
    """Overlapping hypotheses backed by one chronological event buffer per symbol."""

    def __init__(self) -> None:
        self._active: dict[str, ReplayHypothesis] = {}
        self._by_symbol: dict[str, set[str]] = {}
        self._events: dict[str, list[TradeEvent]] = {}
        self._results: dict[str, PolicyOutcome] = {}

    def add(self, hypothesis: ReplayHypothesis) -> None:
        if hypothesis.decision_id in self._active or hypothesis.decision_id in self._results:
            raise ValueError("REPLAY_DECISION_ALREADY_EXISTS")
        self._active[hypothesis.decision_id] = hypothesis
        self._by_symbol.setdefault(hypothesis.symbol, set()).add(hypothesis.decision_id)
        self._events.setdefault(hypothesis.symbol, [])

    def ingest(self, event: TradeEvent) -> None:
        if event.symbol not in self._by_symbol or not self._by_symbol[event.symbol]:
            return
        rows = self._events.setdefault(event.symbol, [])
        if rows:
            previous = rows[-1]
            if event.trade_id == previous.trade_id:
                return
            if event.trade_id < previous.trade_id or event.trade_time_ms < previous.trade_time_ms:
                # replay_policy will fail closed on chronology; keep evidence once.
                rows.append(event)
                return
        rows.append(event)

    def _events_for(self, hypothesis: ReplayHypothesis) -> list[TradeEvent]:
        end_ms = hypothesis.entry_time_ms + hypothesis.horizon_ms
        return [
            event for event in self._events.get(hypothesis.symbol, ())
            if hypothesis.entry_time_ms <= event.trade_time_ms <= end_ms
        ]

    def _prune_symbol(self, symbol: str) -> None:
        ids = self._by_symbol.get(symbol, set())
        if not ids:
            self._events.pop(symbol, None)
            self._by_symbol.pop(symbol, None)
            return
        earliest = min(self._active[decision_id].entry_time_ms for decision_id in ids)
        rows = self._events.get(symbol, [])
        if rows:
            self._events[symbol] = [event for event in rows if event.trade_time_ms >= earliest]

    def mature(self, decision_id: str, *, now_ms: int, force: bool = False) -> PolicyOutcome | None:
        h = self._active.get(decision_id)
        if h is None:
            return self._results.get(decision_id)
        if not force and now_ms < h.entry_time_ms + h.horizon_ms:
            return None
        result = replay_policy(
            self._events_for(h), symbol=h.symbol, side=h.side, entry_price=h.entry_price,
            one_r_price=h.one_r_price, entry_time_ms=h.entry_time_ms, policy=h.policy,
            costs=h.costs, horizon_ms=h.horizon_ms,
        )
        self._results[decision_id] = result
        del self._active[decision_id]
        self._by_symbol[h.symbol].discard(decision_id)
        self._prune_symbol(h.symbol)
        return result

    def mature_due(self, *, now_ms: int) -> dict[str, PolicyOutcome]:
        matured = {}
        for decision_id, hypothesis in tuple(self._active.items()):
            if now_ms >= hypothesis.entry_time_ms + hypothesis.horizon_ms:
                outcome = self.mature(decision_id, now_ms=now_ms)
                if outcome is not None:
                    matured[decision_id] = outcome
        return matured

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def active_symbols(self) -> tuple[str, ...]:
        return tuple(sorted(symbol for symbol, ids in self._by_symbol.items() if ids))

    def active_decisions_for_symbol(self, symbol: str) -> int:
        return len(self._by_symbol.get(symbol, ()))

    def buffered_event_count(self, symbol: str | None = None) -> int:
        if symbol is not None:
            return len(self._events.get(symbol, ()))
        return sum(len(rows) for rows in self._events.values())
