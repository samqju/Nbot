"""Integrated research-only V3 decision -> replay -> ledger pipeline."""
from __future__ import annotations

from pathlib import Path

from .chronological_replay import TradeEvent
from .counterfactual import EvidenceQuality
from .decision_ledger import DecisionLedger, FrozenDecision, MaturedOutcome
from .research_replay import ReplayHypothesis, ResearchReplayBook

AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"


class V3ResearchRuntime:
    def __init__(self, research_memory_path: str | Path) -> None:
        self.ledger = DecisionLedger(research_memory_path)
        self.replays = ResearchReplayBook()
        self.ledger.initialize()

    def submit(self, decision: FrozenDecision, hypothesis: ReplayHypothesis, *, extras=None) -> None:
        if decision.decision_id != hypothesis.decision_id:
            raise ValueError("V3_DECISION_REPLAY_ID_MISMATCH")
        if (decision.symbol, decision.side) != (hypothesis.symbol, hypothesis.side):
            raise ValueError("V3_DECISION_REPLAY_MARKET_MISMATCH")
        self.ledger.record_decision(decision, extras=extras)
        self.replays.add(hypothesis)

    def ingest_trade(self, event: TradeEvent) -> None:
        self.replays.ingest(event)

    def mature_due(self, *, now_ms: int) -> dict[str, MaturedOutcome]:
        results = {}
        for decision_id, outcome in self.replays.mature_due(now_ms=now_ms).items():
            if outcome.quality is EvidenceQuality.GAP_UNRESOLVED or outcome.net_r is None:
                self.ledger.record_unresolved(
                    decision_id, outcome.policy_id, now_ms, outcome.exit_reason,
                    {"source_digest": outcome.source_digest, "events_seen": outcome.events_seen},
                )
                continue
            matured = MaturedOutcome(
                decision_id, outcome.policy_id, now_ms, outcome.quality.value, outcome.exit_reason,
                outcome.net_r, outcome.mfe_r, outcome.mae_r, outcome.source_digest,
            )
            self.ledger.record_outcome(matured)
            results[decision_id] = matured
        return results

    def record_actual_execution(self, outcome: MaturedOutcome) -> None:
        if not outcome.actual_execution:
            raise ValueError("V3_ACTUAL_EXECUTION_FLAG_REQUIRED")
        self.ledger.record_outcome(outcome)

    def submit_order(self, *args, **kwargs):
        raise RuntimeError("RESEARCH_ONLY_NO_EXECUTION")
