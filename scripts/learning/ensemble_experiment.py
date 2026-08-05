"""Run the offline Phase 4.5 ensemble experiment."""

from __future__ import annotations

import json

from config import (
    ENSEMBLE_EXPERIMENT_ARTIFACT_PATH,
    ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS,
    ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS,
    ENSEMBLE_EXPERIMENT_OUTCOME_TYPE,
    ENSEMBLE_EXPERIMENT_RANDOM_STATE,
    ENSEMBLE_EXPERIMENT_REPORT_PATH,
    TEST_SPLIT_PATH,
    TRAIN_SPLIT_PATH,
    VALIDATION_SPLIT_PATH,
)
from learning.ensemble_experiment import OfflineEnsembleExperiment


def main() -> int:
    report = OfflineEnsembleExperiment(
        train_path=TRAIN_SPLIT_PATH,
        validation_path=VALIDATION_SPLIT_PATH,
        test_path=TEST_SPLIT_PATH,
        artifact_path=ENSEMBLE_EXPERIMENT_ARTIFACT_PATH,
        report_path=ENSEMBLE_EXPERIMENT_REPORT_PATH,
        outcome_type=ENSEMBLE_EXPERIMENT_OUTCOME_TYPE,
        min_train_rows=ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS,
        min_eval_rows=ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS,
        random_state=ENSEMBLE_EXPERIMENT_RANDOM_STATE,
    ).run()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
