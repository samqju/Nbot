"""Generate the Phase 5.9 champion-challenger evidence report."""

from __future__ import annotations

import json

from config import (
    CANDIDATE_OUTCOMES_PATH,
    SHADOW_DECISIONS_PATH,
    SHADOW_DECISION_OUTCOME_TYPE,
    SHADOW_DECISION_REPORT_PATH,
    AUTOMATIC_PROMOTION_RECENT_EVENT_WINDOW,
)
from learning.shadow_decision_testing import ShadowDecisionEvaluator


def main() -> int:
    report = ShadowDecisionEvaluator(
        decisions_path=SHADOW_DECISIONS_PATH,
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        report_path=SHADOW_DECISION_REPORT_PATH,
        outcome_type=SHADOW_DECISION_OUTCOME_TYPE,
        recent_event_window=AUTOMATIC_PROMOTION_RECENT_EVENT_WINDOW,
    ).evaluate()
    challenger = report["policies"]["CHALLENGER"]["TOP_ONE"]["summary"]
    comparison = report["pairwise"]["CHALLENGER_VS_CHAMPION"]["TOP_ONE"]
    print(
        json.dumps(
            {
                "status": report["status"],
                "valid_decision_cycles": report["valid_decision_cycles"],
                "challenger_completed_raw_batches": challenger[
                    "completed_raw_batches"
                ],
                "challenger_independent_market_events": challenger[
                    "independent_market_events"
                ],
                "challenger_vs_champion_disagreement_events": comparison[
                    "disagreement_events"
                ],
                "challenger_minus_champion_average_net_r": comparison[
                    "left_minus_right_average_net_r"
                ],
                "report_path": SHADOW_DECISION_REPORT_PATH,
                "paper_authority": "UNCHANGED",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
