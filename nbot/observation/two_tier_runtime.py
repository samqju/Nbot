"""Two-tier V3 research orchestration: broad scan + sticky high-res watch."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .decision_ledger import FrozenDecision
from .redesign_runtime import V3ResearchRuntime
from .research_replay import ReplayHypothesis
from .watch_planner import WatchCandidate, WatchPlan, plan_two_tier_watch


class TwoTierV3ResearchRuntime(V3ResearchRuntime):
    """Admission-controlled research runtime.

    Broad scoring may cover ~100 symbols cheaply. High-resolution replay is
    restricted to the current watch plan, with active symbols retained until
    all hypotheses on that symbol mature.
    """

    def __init__(self, research_memory_path: str | Path, *, broad_target: int = 100, high_res_cap: int = 20) -> None:
        if not 1 <= high_res_cap <= broad_target <= 500:
            raise ValueError("TWO_TIER_RUNTIME_CONFIG_INVALID")
        super().__init__(research_memory_path)
        self.broad_target = broad_target
        self.high_res_cap = high_res_cap
        self._plan: WatchPlan | None = None

    @property
    def watch_plan(self) -> WatchPlan | None:
        return self._plan

    def refresh_watch_plan(self, *, broad_symbols: Iterable[str], candidates: Iterable[WatchCandidate]) -> WatchPlan:
        plan = plan_two_tier_watch(
            broad_symbols=broad_symbols,
            candidates=candidates,
            active_high_res_symbols=self.replays.active_symbols,
            broad_target=self.broad_target,
            high_res_cap=self.high_res_cap,
        )
        self._plan = plan
        return plan

    def submit(self, decision: FrozenDecision, hypothesis: ReplayHypothesis, *, extras=None) -> None:
        if self._plan is None:
            raise ValueError("TWO_TIER_WATCH_PLAN_REQUIRED")
        if hypothesis.symbol not in set(self._plan.high_res_symbols):
            # Keep the immutable decision, but do not pretend we have a precise
            # high-resolution path for a symbol that was not admitted.
            self.ledger.record_decision(
                decision,
                extras={**dict(extras or {}), "high_res_admitted": False, "watch_reason": "CAPACITY_OR_PRIORITY"},
            )
            self.ledger.record_unresolved(
                decision.decision_id,
                hypothesis.policy.value,
                decision.decision_time_ms,
                "HIGH_RES_NOT_ADMITTED",
                {"symbol": hypothesis.symbol},
            )
            return
        self.ledger.record_decision(
            decision,
            extras={
                **dict(extras or {}),
                "high_res_admitted": True,
                "watch_reason": self._plan.reasons.get(hypothesis.symbol, "UNKNOWN"),
            },
        )
        self.replays.add(hypothesis)
