# ==========================================================
# Strategy Factory
# ==========================================================

from config import STRATEGY_MODE
from strategy.strategy import Strategy


def build_strategy(*, system_log):
    if STRATEGY_MODE != "STRUCTURE":
        raise RuntimeError(f"UNSUPPORTED_STRATEGY_MODE:{STRATEGY_MODE}")

    strategy = Strategy(system_log=system_log)
    if system_log:
        system_log.info(
            "STRATEGY_SELECTED | "
            f"mode={STRATEGY_MODE} | class={type(strategy).__name__}"
        )
    return strategy
