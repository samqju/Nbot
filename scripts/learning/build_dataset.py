"""Build the Phase 4.1 training corpus and integrity report."""

from __future__ import annotations

import json

from config import (
    CANDIDATE_OBSERVATIONS_PATH,
    CANDIDATE_OUTCOMES_PATH,
    DATASET_INTEGRITY_REPORT_PATH,
    TRAINING_DATASET_PATH,
)
from learning.dataset_builder import TrainingDatasetBuilder


def main() -> int:
    report = TrainingDatasetBuilder(
        observations_path=CANDIDATE_OBSERVATIONS_PATH,
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        dataset_path=TRAINING_DATASET_PATH,
        report_path=DATASET_INTEGRITY_REPORT_PATH,
    ).build()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
