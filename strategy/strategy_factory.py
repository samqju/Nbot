# ==========================================================
# Strategy Factory
# ==========================================================

from config import EXECUTION_MODE, STRATEGY_MODE
from strategy.paper_test_strategy import PaperTestStrategy
from strategy.strategy import Strategy


def build_strategy(*, system_log):
    if STRATEGY_MODE == "STRUCTURE":
        strategy = Strategy(system_log=system_log)
    elif STRATEGY_MODE == "PAPER_TEST":
        if EXECUTION_MODE != "SHADOW":
            raise RuntimeError("PAPER_TEST_STRATEGY_REQUIRES_SHADOW")
        strategy = PaperTestStrategy(system_log=system_log)
    else:
        raise RuntimeError(f"UNSUPPORTED_STRATEGY_MODE:{STRATEGY_MODE}")

    if system_log:
        system_log.info(
            "STRATEGY_SELECTED | "
            f"mode={STRATEGY_MODE} | class={type(strategy).__name__}"
        )
    return strategy
