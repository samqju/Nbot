"""Generate the advisory Phase 5.6 strategy-laboratory report."""

from __future__ import annotations

import json

from config import (
    CANDIDATE_OUTCOMES_PATH,
    STRATEGY_LAB_MAX_DRAWDOWN_R,
    STRATEGY_LAB_MIN_AVG_NET_R,
    STRATEGY_LAB_MIN_MARKET_EVENTS,
    STRATEGY_LAB_MIN_OUTCOMES,
    STRATEGY_LAB_REPORT_PATH,
    VIRTUAL_LAB_CATALOG_VERSION,
)
from learning.strategy_lab import StrategyLabEvaluator


def main() -> int:
    report = StrategyLabEvaluator(
        outcomes_path=CANDIDATE_OUTCOMES_PATH,
        report_path=STRATEGY_LAB_REPORT_PATH,
        catalog_version=VIRTUAL_LAB_CATALOG_VERSION,
        min_outcomes=STRATEGY_LAB_MIN_OUTCOMES,
        min_market_events=STRATEGY_LAB_MIN_MARKET_EVENTS,
        min_avg_net_r=STRATEGY_LAB_MIN_AVG_NET_R,
        max_drawdown_r=STRATEGY_LAB_MAX_DRAWDOWN_R,
    ).evaluate()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
