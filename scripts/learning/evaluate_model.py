"""Run offline Phase 4.4 evaluation and calibration."""

from __future__ import annotations

import json

from config import (
    BASELINE_MODEL_ARTIFACT_PATH,
    MODEL_CALIBRATION_REPORT_PATH,
    MODEL_EVALUATION_CALIBRATION_BINS,
    MODEL_EVALUATION_DRIFT_BINS,
    MODEL_EVALUATION_MIN_SUBGROUP_ROWS,
    MODEL_EVALUATION_REPORT_PATH,
    TEST_SPLIT_PATH,
    VALIDATION_SPLIT_PATH,
)
from learning.model_evaluator import BaselineModelEvaluator


def main() -> int:
    report = BaselineModelEvaluator(
        artifact_path=BASELINE_MODEL_ARTIFACT_PATH,
        validation_path=VALIDATION_SPLIT_PATH,
        test_path=TEST_SPLIT_PATH,
        evaluation_report_path=MODEL_EVALUATION_REPORT_PATH,
        calibration_report_path=MODEL_CALIBRATION_REPORT_PATH,
        min_subgroup_rows=MODEL_EVALUATION_MIN_SUBGROUP_ROWS,
        calibration_bins=MODEL_EVALUATION_CALIBRATION_BINS,
        drift_bins=MODEL_EVALUATION_DRIFT_BINS,
    ).evaluate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
