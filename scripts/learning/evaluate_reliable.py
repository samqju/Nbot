"""Generate the advisory Phase 5.7 reliable-evaluation report."""

from __future__ import annotations

import json

from config import (
    RELIABLE_EVALUATION_LIQUID_MAX_SPREAD_PCT,
    RELIABLE_EVALUATION_LIQUID_MIN_QUOTE_VOLUME_USD,
    RELIABLE_EVALUATION_MAX_DRAWDOWN_R,
    RELIABLE_EVALUATION_MIN_AVG_NET_R,
    RELIABLE_EVALUATION_MIN_HOLDOUT_EVENTS,
    RELIABLE_EVALUATION_MIN_MARKET_EVENTS,
    RELIABLE_EVALUATION_MIN_OUTCOMES,
    RELIABLE_EVALUATION_MIN_POSITIVE_FOLD_RATIO,
    RELIABLE_EVALUATION_MIN_REGIME_EVENTS,
    RELIABLE_EVALUATION_REPORT_PATH,
    RELIABLE_EVALUATION_WALK_FORWARD_FOLDS,
    TIME_SPLIT_EMBARGO_SECONDS,
    TIME_SPLIT_TEST_RATIO,
    TIME_SPLIT_TRAIN_RATIO,
    TIME_SPLIT_VALIDATION_RATIO,
    TRAINING_DATASET_PATH,
    VIRTUAL_LAB_CATALOG_VERSION,
)
from learning.reliable_evaluation import ReliableEvaluationEngine


def main() -> int:
    report = ReliableEvaluationEngine(
        dataset_path=TRAINING_DATASET_PATH,
        report_path=RELIABLE_EVALUATION_REPORT_PATH,
        catalog_version=VIRTUAL_LAB_CATALOG_VERSION,
        train_ratio=TIME_SPLIT_TRAIN_RATIO,
        validation_ratio=TIME_SPLIT_VALIDATION_RATIO,
        test_ratio=TIME_SPLIT_TEST_RATIO,
        embargo_seconds=TIME_SPLIT_EMBARGO_SECONDS,
        walk_forward_folds=(
            RELIABLE_EVALUATION_WALK_FORWARD_FOLDS
        ),
        min_outcomes=RELIABLE_EVALUATION_MIN_OUTCOMES,
        min_market_events=RELIABLE_EVALUATION_MIN_MARKET_EVENTS,
        min_holdout_events=RELIABLE_EVALUATION_MIN_HOLDOUT_EVENTS,
        min_regime_events=RELIABLE_EVALUATION_MIN_REGIME_EVENTS,
        min_avg_net_r=RELIABLE_EVALUATION_MIN_AVG_NET_R,
        min_positive_fold_ratio=(
            RELIABLE_EVALUATION_MIN_POSITIVE_FOLD_RATIO
        ),
        max_drawdown_r=RELIABLE_EVALUATION_MAX_DRAWDOWN_R,
        liquid_max_spread_pct=(
            RELIABLE_EVALUATION_LIQUID_MAX_SPREAD_PCT
        ),
        liquid_min_quote_volume_usd=(
            RELIABLE_EVALUATION_LIQUID_MIN_QUOTE_VOLUME_USD
        ),
    ).evaluate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
