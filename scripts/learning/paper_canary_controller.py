"""Run the Phase 5.12 automatic paper rollback controller separately."""

from __future__ import annotations

import argparse
import json
import os
import signal
import time

from config import (
    EXECUTION_MODE,
    MODEL_REGISTRY_PATH,
    PAPER_CANARY_CONTROLLER_ENABLED,
    PAPER_CANARY_CONTROLLER_LOCK_PATH,
    PAPER_CANARY_CONTROLLER_POLL_SECONDS,
    PAPER_CANARY_MAX_DRAWDOWN_R,
    PAPER_CANARY_MAX_LOSING_STREAK,
    PAPER_CANARY_10_MIN_COMPLETED_TRADES,
    PAPER_CANARY_10_MIN_INDEPENDENT_EVENTS,
    PAPER_CANARY_25_MIN_COMPLETED_TRADES,
    PAPER_CANARY_25_MIN_INDEPENDENT_EVENTS,
    PAPER_CANARY_50_MIN_COMPLETED_TRADES,
    PAPER_CANARY_50_MIN_INDEPENDENT_EVENTS,
    PAPER_CANARY_ADVANCE_MIN_AVERAGE_NET_R,
    PAPER_CANARY_ADVANCE_MIN_RECENT_AVERAGE_NET_R,
    PAPER_CANARY_MIN_AVERAGE_NET_R,
    PAPER_CANARY_MIN_COMPLETED_TRADES,
    PAPER_CANARY_MIN_RECENT_AVERAGE_NET_R,
    PAPER_CANARY_RECENT_TRADE_WINDOW,
    PAPER_ROLLBACK_MIN_PAIRED_EVENTS,
    PAPER_ROLLBACK_MIN_AVERAGE_R_LIFT,
    PAPER_ROLLBACK_MIN_RUNTIME_DECISIONS,
    PAPER_ROLLBACK_MAX_PREDICTION_FAILURES,
    PAPER_ROLLBACK_MAX_PREDICTION_FAILURE_RATE,
    PAPER_ROLLBACK_MIN_CALIBRATION_OUTCOMES,
    PAPER_ROLLBACK_MAX_BRIER_SCORE,
    PAPER_ROLLBACK_MAX_CALIBRATION_GAP,
    PAPER_ROLLBACK_MIN_DRIFT_OBSERVATIONS,
    PAPER_ROLLBACK_MAX_FEATURE_PSI,
    PAPER_CANARY_STATUS_PATH,
    PAPER_TRADES_PATH,
    PAPER_CANARY_DECISIONS_PATH,
    CANDIDATE_OBSERVATIONS_PATH,
    CANDIDATE_OUTCOMES_PATH,
    STRATEGY_POLICY_RECOMMENDATION_PATH,
    STRATEGY_POLICY_MIN_INDEPENDENT_EVENTS,
    STRATEGY_POLICY_MIN_AVERAGE_NET_R,
    VIRTUAL_LAB_CATALOG_VERSION,
    VIRTUAL_STRATEGY_VARIANT_ID,
    VIRTUAL_TRADE_TARGET_R,
    VIRTUAL_TRADE_MAX_CANDLES,
    RULE_MODEL_VERSION,
    TRADING_ENV,
)
from learning.paper_canary import AutomaticPaperCanaryController
from learning.operator_status import build_configured_publisher
from learning.strategy_policy import StrategyPolicyRecommender
from strategy.strategy_lab import build_approved_variant_catalog


_STOP = False


def _handle_stop(_signum, _frame):
    global _STOP
    _STOP = True


def build_controller() -> AutomaticPaperCanaryController:
    strategy_policy = StrategyPolicyRecommender(
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        recommendation_path=STRATEGY_POLICY_RECOMMENDATION_PATH,
        catalog_version=VIRTUAL_LAB_CATALOG_VERSION,
        approved_catalog=build_approved_variant_catalog(
            baseline_variant_id=VIRTUAL_STRATEGY_VARIANT_ID,
            baseline_target_r=VIRTUAL_TRADE_TARGET_R,
            baseline_max_candles=VIRTUAL_TRADE_MAX_CANDLES,
        ),
        min_independent_events=STRATEGY_POLICY_MIN_INDEPENDENT_EVENTS,
        min_average_net_r=STRATEGY_POLICY_MIN_AVERAGE_NET_R,
    )
    return AutomaticPaperCanaryController(
        enabled=PAPER_CANARY_CONTROLLER_ENABLED,
        execution_mode=EXECUTION_MODE,
        environment=TRADING_ENV,
        registry_path=MODEL_REGISTRY_PATH,
        trades_path=PAPER_TRADES_PATH,
        status_path=PAPER_CANARY_STATUS_PATH,
        lock_path=PAPER_CANARY_CONTROLLER_LOCK_PATH,
        default_champion_model_id=RULE_MODEL_VERSION,
        min_completed_trades=PAPER_CANARY_MIN_COMPLETED_TRADES,
        max_drawdown_r=PAPER_CANARY_MAX_DRAWDOWN_R,
        max_losing_streak=PAPER_CANARY_MAX_LOSING_STREAK,
        min_average_net_r=PAPER_CANARY_MIN_AVERAGE_NET_R,
        recent_trade_window=PAPER_CANARY_RECENT_TRADE_WINDOW,
        min_recent_average_net_r=(
            PAPER_CANARY_MIN_RECENT_AVERAGE_NET_R
        ),
        stage_10_min_completed_trades=(
            PAPER_CANARY_10_MIN_COMPLETED_TRADES
        ),
        stage_10_min_independent_events=(
            PAPER_CANARY_10_MIN_INDEPENDENT_EVENTS
        ),
        stage_25_min_completed_trades=(
            PAPER_CANARY_25_MIN_COMPLETED_TRADES
        ),
        stage_25_min_independent_events=(
            PAPER_CANARY_25_MIN_INDEPENDENT_EVENTS
        ),
        stage_50_min_completed_trades=(
            PAPER_CANARY_50_MIN_COMPLETED_TRADES
        ),
        stage_50_min_independent_events=(
            PAPER_CANARY_50_MIN_INDEPENDENT_EVENTS
        ),
        advance_min_average_net_r=(
            PAPER_CANARY_ADVANCE_MIN_AVERAGE_NET_R
        ),
        advance_min_recent_average_net_r=(
            PAPER_CANARY_ADVANCE_MIN_RECENT_AVERAGE_NET_R
        ),
        strategy_policy_refresher=strategy_policy,
        decisions_path=PAPER_CANARY_DECISIONS_PATH,
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        observations_path=CANDIDATE_OBSERVATIONS_PATH,
        rollback_min_paired_events=PAPER_ROLLBACK_MIN_PAIRED_EVENTS,
        rollback_min_average_r_lift=PAPER_ROLLBACK_MIN_AVERAGE_R_LIFT,
        rollback_min_runtime_decisions=(
            PAPER_ROLLBACK_MIN_RUNTIME_DECISIONS
        ),
        rollback_max_prediction_failures=(
            PAPER_ROLLBACK_MAX_PREDICTION_FAILURES
        ),
        rollback_max_prediction_failure_rate=(
            PAPER_ROLLBACK_MAX_PREDICTION_FAILURE_RATE
        ),
        rollback_min_calibration_outcomes=(
            PAPER_ROLLBACK_MIN_CALIBRATION_OUTCOMES
        ),
        rollback_max_brier_score=PAPER_ROLLBACK_MAX_BRIER_SCORE,
        rollback_max_calibration_gap=(
            PAPER_ROLLBACK_MAX_CALIBRATION_GAP
        ),
        rollback_min_drift_observations=(
            PAPER_ROLLBACK_MIN_DRIFT_OBSERVATIONS
        ),
        rollback_max_feature_psi=PAPER_ROLLBACK_MAX_FEATURE_PSI,
    )


def _lower_priority() -> None:
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor staged paper canaries and model paper champions, then "
            "apply Phase 5.12 atomic rollback gates"
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--watch", action="store_true")
    args = parser.parse_args(argv)

    _lower_priority()
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    controller = build_controller()
    status_publisher = build_configured_publisher()
    watch = bool(args.watch)

    while True:
        try:
            result = controller.run_once()
        except Exception as exc:
            result = {
                "status": "PAPER_CANARY_CONTROLLER_FAILED",
                "error": f"{type(exc).__name__}:{exc}",
                "champion_changed": False,
                "real_order_authority": "NONE",
            }
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        try:
            operator_status = status_publisher.refresh()
            governance = operator_status.get("governance") or {}
            safety = operator_status.get("safety") or {}
            print(
                "AUTO_LEARNING_STATUS | "
                f"champion={operator_status.get('current_paper_champion')} | "
                f"challenger={operator_status.get('current_challenger')} | "
                f"stage={operator_status.get('challenger_stage')} | "
                f"verdict={governance.get('current_verdict')} | "
                f"next={governance.get('next_automatic_action')} | "
                f"real_orders={safety.get('real_order_execution')}",
                flush=True,
            )
        except Exception as exc:
            print(
                "AUTO_LEARNING_STATUS_FAILED | "
                f"error={type(exc).__name__}:{exc} | "
                "trading_authority=UNCHANGED | real_order_authority=NONE",
                flush=True,
            )
        if not watch or _STOP:
            break
        deadline = time.monotonic() + PAPER_CANARY_CONTROLLER_POLL_SECONDS
        while not _STOP and time.monotonic() < deadline:
            time.sleep(min(1.0, deadline - time.monotonic()))
        if _STOP:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
