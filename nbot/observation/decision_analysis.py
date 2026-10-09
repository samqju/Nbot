"""Out-of-sample V3 decision-policy evaluation; never changes live thresholds."""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class DecisionEvaluationRow:
    event_id: str
    decision_time_ms: int
    ridge_score_r: float
    ml_lower_r: float
    conservative_score_r: float
    outcome_r: float
    approved: bool

    def __post_init__(self):
        if not self.event_id or self.decision_time_ms < 0 or not all(math.isfinite(x) for x in (
            self.ridge_score_r, self.ml_lower_r, self.conservative_score_r, self.outcome_r
        )):
            raise ValueError("DECISION_EVALUATION_ROW_INVALID")


def disagreement_report(rows: Iterable[DecisionEvaluationRow], *, threshold_r: float = .08) -> dict[str, float | int]:
    data = list(rows)
    disagree = [r for r in data if (r.ridge_score_r >= threshold_r) != (r.ml_lower_r >= threshold_r)]
    ridge_only = [r for r in disagree if r.ridge_score_r >= threshold_r]
    ml_only = [r for r in disagree if r.ml_lower_r >= threshold_r]
    return {
        "rows": len(data), "disagreements": len(disagree), "ridge_only": len(ridge_only), "ml_only": len(ml_only),
        "disagreement_mean_r": mean([r.outcome_r for r in disagree]) if disagree else 0.0,
        "ridge_only_mean_r": mean([r.outcome_r for r in ridge_only]) if ridge_only else 0.0,
        "ml_only_mean_r": mean([r.outcome_r for r in ml_only]) if ml_only else 0.0,
    }


def compare_thresholds(rows: Iterable[DecisionEvaluationRow], *, thresholds=(.05, .08, .10),
                       edge_gaps=(0.0, .05)) -> tuple[dict, ...]:
    data = list(rows)
    reports = []
    for threshold in thresholds:
        for gap in edge_gaps:
            selected = [r for r in data if r.conservative_score_r >= threshold + gap]
            events = {r.event_id for r in selected}
            reports.append({
                "threshold_r": threshold, "edge_gap_r": gap, "selected": len(selected),
                "distinct_events": len(events),
                "mean_outcome_r": mean([r.outcome_r for r in selected]) if selected else 0.0,
                "authority": "RESEARCH_EVALUATION_ONLY_NO_AUTO_DEPLOY",
            })
    return tuple(reports)
