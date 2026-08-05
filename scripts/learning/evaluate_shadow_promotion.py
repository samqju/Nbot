"""Run Phase 4.7 shadow-outcome evaluation and promotion gate."""

from __future__ import annotations

import json

from config import (
    CANDIDATE_OUTCOMES_PATH,
    MODEL_EVALUATION_REPORT_PATH,
    SHADOW_MODEL_PREDICTIONS_PATH,
    SHADOW_PROMOTION_MAX_BRIER_SCORE,
    SHADOW_PROMOTION_MAX_CALIBRATION_GAP,
    SHADOW_PROMOTION_MAX_FEATURE_PSI,
    SHADOW_PROMOTION_MAX_WIN_RATE_DROP,
    SHADOW_PROMOTION_MIN_AVG_R_LIFT,
    SHADOW_PROMOTION_MIN_MATCHED_CANDIDATES,
    SHADOW_PROMOTION_MIN_PAIRED_BATCHES,
    SHADOW_PROMOTION_OUTCOME_TYPE,
    SHADOW_PROMOTION_REPORT_PATH,
)
from learning.shadow_promotion import ShadowPromotionEvaluator


def main() -> int:
    report = ShadowPromotionEvaluator(
        predictions_path=SHADOW_MODEL_PREDICTIONS_PATH,
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        model_evaluation_report_path=MODEL_EVALUATION_REPORT_PATH,
        report_path=SHADOW_PROMOTION_REPORT_PATH,
        outcome_type=SHADOW_PROMOTION_OUTCOME_TYPE,
        min_matched_candidates=(
            SHADOW_PROMOTION_MIN_MATCHED_CANDIDATES
        ),
        min_paired_batches=SHADOW_PROMOTION_MIN_PAIRED_BATCHES,
        min_avg_r_lift=SHADOW_PROMOTION_MIN_AVG_R_LIFT,
        max_win_rate_drop=SHADOW_PROMOTION_MAX_WIN_RATE_DROP,
        max_brier_score=SHADOW_PROMOTION_MAX_BRIER_SCORE,
        max_calibration_gap=(
            SHADOW_PROMOTION_MAX_CALIBRATION_GAP
        ),
        max_feature_psi=SHADOW_PROMOTION_MAX_FEATURE_PSI,
    ).evaluate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
