"""Build chronological Phase 4.2 train/validation/test splits."""

from __future__ import annotations

import json

from config import (
    TEST_SPLIT_PATH,
    TIME_SPLIT_EMBARGO_SECONDS,
    TIME_SPLIT_REPORT_PATH,
    TIME_SPLIT_TEST_RATIO,
    TIME_SPLIT_TRAIN_RATIO,
    TIME_SPLIT_VALIDATION_RATIO,
    TRAINING_DATASET_PATH,
    TRAIN_SPLIT_PATH,
    VALIDATION_SPLIT_PATH,
)
from learning.time_split import TimeAwareDatasetSplitter


def main() -> int:
    report = TimeAwareDatasetSplitter(
        dataset_path=TRAINING_DATASET_PATH,
        train_path=TRAIN_SPLIT_PATH,
        validation_path=VALIDATION_SPLIT_PATH,
        test_path=TEST_SPLIT_PATH,
        report_path=TIME_SPLIT_REPORT_PATH,
        train_ratio=TIME_SPLIT_TRAIN_RATIO,
        validation_ratio=TIME_SPLIT_VALIDATION_RATIO,
        test_ratio=TIME_SPLIT_TEST_RATIO,
        embargo_seconds=TIME_SPLIT_EMBARGO_SECONDS,
    ).split()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
