"""Run Phase 7.5 strict champion-challenger governance separately."""

from __future__ import annotations

import argparse
import json
import os
import signal
import time

from config import (
    AUTOMATIC_PROMOTION_ENABLED,
    AUTOMATIC_PROMOTION_EVIDENCE_REPORT_PATH,
    AUTOMATIC_PROMOTION_EXTEND_EVIDENCE_RATIO,
    AUTOMATIC_PROMOTION_LOCK_PATH,
    AUTOMATIC_PROMOTION_MAX_BRIER_SCORE,
    AUTOMATIC_PROMOTION_MAX_CALIBRATION_GAP,
    AUTOMATIC_PROMOTION_MAX_FEATURE_PSI,
    AUTOMATIC_PROMOTION_MAX_WIN_RATE_DETERIORATION,
    AUTOMATIC_PROMOTION_MIN_AFTER_COST_EXPECTANCY,
    AUTOMATIC_PROMOTION_MIN_AVERAGE_R_LIFT,
    AUTOMATIC_PROMOTION_MIN_DISAGREEMENT_EVENTS,
    AUTOMATIC_PROMOTION_MIN_INDEPENDENT_EVENTS,
    AUTOMATIC_PROMOTION_MIN_MATCHED_OUTCOMES,
    AUTOMATIC_PROMOTION_MIN_RECENT_EXPECTANCY,
    AUTOMATIC_PROMOTION_MIN_REGIME_AFTER_COST_EXPECTANCY,
    AUTOMATIC_PROMOTION_MIN_REGIME_AVERAGE_R_LIFT,
    AUTOMATIC_PROMOTION_MIN_REGIME_EVENTS,
    AUTOMATIC_PROMOTION_MIN_DISTINCT_MARKET_REGIMES,
    AUTOMATIC_PROMOTION_POLL_SECONDS,
    AUTOMATIC_PROMOTION_RECENT_EVENT_WINDOW,
    AUTOMATIC_PROMOTION_STATUS_PATH,
    CANDIDATE_OUTCOMES_PATH,
    MODEL_REGISTRY_PATH,
    RULE_MODEL_VERSION,
    SHADOW_DECISIONS_PATH,
    SHADOW_DECISION_OUTCOME_TYPE,
    TRADING_ENV,
)
from learning.promotion_controller import AutomaticPromotionController


_STOP = False


def _handle_stop(_signum, _frame):
    global _STOP
    _STOP = True


def build_controller() -> AutomaticPromotionController:
    return AutomaticPromotionController(
        enabled=AUTOMATIC_PROMOTION_ENABLED,
        environment=TRADING_ENV,
        decisions_path=SHADOW_DECISIONS_PATH,
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        evidence_report_path=AUTOMATIC_PROMOTION_EVIDENCE_REPORT_PATH,
        registry_path=MODEL_REGISTRY_PATH,
        status_path=AUTOMATIC_PROMOTION_STATUS_PATH,
        lock_path=AUTOMATIC_PROMOTION_LOCK_PATH,
        default_champion_model_id=RULE_MODEL_VERSION,
        outcome_type=SHADOW_DECISION_OUTCOME_TYPE,
        min_matched_outcomes=AUTOMATIC_PROMOTION_MIN_MATCHED_OUTCOMES,
        min_independent_events=AUTOMATIC_PROMOTION_MIN_INDEPENDENT_EVENTS,
        min_disagreement_events=AUTOMATIC_PROMOTION_MIN_DISAGREEMENT_EVENTS,
        min_average_r_lift=AUTOMATIC_PROMOTION_MIN_AVERAGE_R_LIFT,
        min_after_cost_expectancy=(
            AUTOMATIC_PROMOTION_MIN_AFTER_COST_EXPECTANCY
        ),
        max_win_rate_deterioration=(
            AUTOMATIC_PROMOTION_MAX_WIN_RATE_DETERIORATION
        ),
        max_brier_score=AUTOMATIC_PROMOTION_MAX_BRIER_SCORE,
        max_calibration_gap=AUTOMATIC_PROMOTION_MAX_CALIBRATION_GAP,
        max_feature_psi=AUTOMATIC_PROMOTION_MAX_FEATURE_PSI,
        min_recent_expectancy=AUTOMATIC_PROMOTION_MIN_RECENT_EXPECTANCY,
        recent_event_window=AUTOMATIC_PROMOTION_RECENT_EVENT_WINDOW,
        extend_evidence_ratio=AUTOMATIC_PROMOTION_EXTEND_EVIDENCE_RATIO,
        phase7_strict_evidence=True,
        min_regime_events=AUTOMATIC_PROMOTION_MIN_REGIME_EVENTS,
        min_distinct_market_regimes=(
            AUTOMATIC_PROMOTION_MIN_DISTINCT_MARKET_REGIMES
        ),
        min_regime_average_r_lift=(
            AUTOMATIC_PROMOTION_MIN_REGIME_AVERAGE_R_LIFT
        ),
        min_regime_after_cost_expectancy=(
            AUTOMATIC_PROMOTION_MIN_REGIME_AFTER_COST_EXPECTANCY
        ),
    )


def _lower_priority() -> None:
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Phase 7.5 promotion governance separately from the "
            "trading engine"
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="evaluate the current shadow challenger once",
    )
    mode.add_argument(
        "--watch",
        action="store_true",
        help="continue evaluating fresh completed shadow evidence",
    )
    args = parser.parse_args(argv)

    _lower_priority()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    controller = build_controller()
    watch = bool(args.watch)

    while True:
        try:
            result = controller.run_once()
            print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "PROMOTION_CONTROLLER_FAILED",
                        "error": f"{type(exc).__name__}:{exc}",
                        "champion_changed": False,
                        "paper_order_routing_changed": False,
                        "real_order_authority": "NONE",
                    },
                    indent=2,
                    sort_keys=True,
                ),
                flush=True,
            )
        if not watch or _STOP:
            break
        deadline = time.monotonic() + AUTOMATIC_PROMOTION_POLL_SECONDS
        while not _STOP and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))
        if _STOP:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
