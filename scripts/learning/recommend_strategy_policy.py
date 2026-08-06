"""Generate the automatic approved strategy-policy recommendation once."""

from __future__ import annotations

import json

from config import (
    CANDIDATE_OUTCOMES_PATH,
    STRATEGY_POLICY_MIN_AVERAGE_NET_R,
    STRATEGY_POLICY_MIN_INDEPENDENT_EVENTS,
    STRATEGY_POLICY_RECOMMENDATION_PATH,
    VIRTUAL_LAB_CATALOG_VERSION,
    VIRTUAL_STRATEGY_VARIANT_ID,
    VIRTUAL_TRADE_MAX_CANDLES,
    VIRTUAL_TRADE_TARGET_R,
)
from learning.strategy_policy import StrategyPolicyRecommender
from strategy.strategy_lab import build_approved_variant_catalog


def main() -> int:
    report = StrategyPolicyRecommender(
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
    ).refresh()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
