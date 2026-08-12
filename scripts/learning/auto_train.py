"""Run the Phase 5.8 automatic training supervisor as a separate process."""

from __future__ import annotations

import argparse
import json
import os
import signal
import time

from config import (
    AUTO_TRAINING_ENABLED,
    AUTO_TRAINING_PRUNE_REJECTED_STORAGE,
    AUTO_TRAINING_LOCK_PATH,
    AUTO_TRAINING_MAX_BRIER_SCORE,
    AUTO_TRAINING_MAX_CALIBRATION_GAP,
    AUTO_TRAINING_MAX_FEATURE_PSI,
    AUTO_TRAINING_MIN_NEW_MARKET_EVENTS,
    AUTO_TRAINING_MIN_NEW_OUTCOMES,
    AUTO_TRAINING_MIN_ROC_AUC,
    AUTO_TRAINING_MODEL_ROOT,
    AUTO_TRAINING_OUTCOME_TYPE,
    AUTO_TRAINING_PARENT_MODEL_ID,
    AUTO_TRAINING_POLL_SECONDS,
    AUTO_TRAINING_SNAPSHOT_ROOT,
    AUTO_TRAINING_STATUS_PATH,
    BASELINE_MODEL_MIN_EVAL_ROWS,
    BASELINE_MODEL_MIN_TRAIN_ROWS,
    BASELINE_MODEL_RANDOM_STATE,
    CANDIDATE_OBSERVATIONS_PATH,
    CANDIDATE_OUTCOMES_PATH,
    LEARNING_HISTORY_ROTATE_MIN_MB,
    LEARNING_HISTORY_ROTATION_ENABLED,
    ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS,
    ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS,
    MODEL_EVALUATION_CALIBRATION_BINS,
    MODEL_EVALUATION_DRIFT_BINS,
    MODEL_REGISTRY_PATH,
    RELIABLE_EVALUATION_MIN_HOLDOUT_EVENTS,
    RELIABLE_EVALUATION_MIN_MARKET_EVENTS,
    TIME_SPLIT_EMBARGO_SECONDS,
    TIME_SPLIT_TEST_RATIO,
    TIME_SPLIT_TRAIN_RATIO,
    TIME_SPLIT_VALIDATION_RATIO,
    TRADING_ENV,
    VIRTUAL_TRADES_PATH,
)
from learning.training_orchestrator import AutomaticTrainingOrchestrator


_STOP = False


def _handle_stop(_signum, _frame):
    global _STOP
    _STOP = True


def build_orchestrator() -> AutomaticTrainingOrchestrator:
    return AutomaticTrainingOrchestrator(
        enabled=AUTO_TRAINING_ENABLED,
        environment=TRADING_ENV,
        observations_path=CANDIDATE_OBSERVATIONS_PATH,
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        snapshot_root=AUTO_TRAINING_SNAPSHOT_ROOT,
        model_root=AUTO_TRAINING_MODEL_ROOT,
        registry_path=MODEL_REGISTRY_PATH,
        status_path=AUTO_TRAINING_STATUS_PATH,
        lock_path=AUTO_TRAINING_LOCK_PATH,
        outcome_type=AUTO_TRAINING_OUTCOME_TYPE,
        default_parent_model_id=AUTO_TRAINING_PARENT_MODEL_ID,
        min_new_outcomes=AUTO_TRAINING_MIN_NEW_OUTCOMES,
        min_new_market_events=AUTO_TRAINING_MIN_NEW_MARKET_EVENTS,
        train_ratio=TIME_SPLIT_TRAIN_RATIO,
        validation_ratio=TIME_SPLIT_VALIDATION_RATIO,
        test_ratio=TIME_SPLIT_TEST_RATIO,
        embargo_seconds=TIME_SPLIT_EMBARGO_SECONDS,
        baseline_min_train_rows=BASELINE_MODEL_MIN_TRAIN_ROWS,
        baseline_min_eval_rows=BASELINE_MODEL_MIN_EVAL_ROWS,
        ensemble_min_train_rows=ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS,
        ensemble_min_eval_rows=ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS,
        random_state=BASELINE_MODEL_RANDOM_STATE,
        calibration_bins=MODEL_EVALUATION_CALIBRATION_BINS,
        drift_bins=MODEL_EVALUATION_DRIFT_BINS,
        min_roc_auc=AUTO_TRAINING_MIN_ROC_AUC,
        max_brier_score=AUTO_TRAINING_MAX_BRIER_SCORE,
        max_calibration_gap=AUTO_TRAINING_MAX_CALIBRATION_GAP,
        max_feature_psi=AUTO_TRAINING_MAX_FEATURE_PSI,
        virtual_trades_path=VIRTUAL_TRADES_PATH,
        history_rotation_enabled=LEARNING_HISTORY_ROTATION_ENABLED,
        history_rotate_min_bytes=int(
            LEARNING_HISTORY_ROTATE_MIN_MB * 1024 * 1024
        ),
        prune_rejected_storage=AUTO_TRAINING_PRUNE_REJECTED_STORAGE,
        min_train_market_events=RELIABLE_EVALUATION_MIN_MARKET_EVENTS,
        min_validation_market_events=RELIABLE_EVALUATION_MIN_HOLDOUT_EVENTS,
        min_test_market_events=RELIABLE_EVALUATION_MIN_HOLDOUT_EVENTS,
    )


def _lower_priority() -> None:
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Phase 5.8 automatic training process separately from "
            "the trading engine"
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="evaluate the trigger and run at most one training cycle",
    )
    mode.add_argument(
        "--watch",
        action="store_true",
        help="continue checking the data trigger",
    )
    args = parser.parse_args(argv)

    _lower_priority()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    orchestrator = build_orchestrator()

    watch = bool(args.watch)
    while True:
        try:
            result = orchestrator.run_once()
            print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "TRAINING_FAILED",
                        "error": f"{type(exc).__name__}:{exc}",
                        "trading_engine_effect": "NONE",
                        "champion_changed": False,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                flush=True,
            )
        if not watch or _STOP:
            break
        deadline = time.monotonic() + AUTO_TRAINING_POLL_SECONDS
        while not _STOP and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))
        if _STOP:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
