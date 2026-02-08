# ==========================================================
# Strategy v2 — Alpha Oracle (Skeleton)
# ==========================================================
# Responsibilities:
# - Observe prices for multiple symbols
# - Maintain rolling state per symbol
# - Propose at most ONE TradeIntent when asked
#
# NON-responsibilities:
# - No trading
# - No execution
# - No risk logic
# - No timing control
# ==========================================================

import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, Optional

from strategy.trade_intent import TradeIntent


class Strategy:
    """
    Alpha Oracle (v0 skeleton).

    Silent by default.
    """

    def __init__(self, max_history: int = 100):
        self._sent_once = False
        # Per-symbol rolling price history
        self._price_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

        # Per-symbol last update timestamp
        self._last_ts: Dict[str, int] = {}

        # Warmup flag
        self._warmed_up = False

    # ------------------------------------------------------
    # Price fan-in (called by engine)
    # ------------------------------------------------------

    def on_price(self, symbol: str, price: float, timestamp: int) -> None:
        """
        Observe a price tick for a symbol.

        Called by engine fan-in.
        """

        self._price_history[symbol].append(price)
        self._last_ts[symbol] = timestamp

        # Warmup heuristic (simple placeholder)
        if not self._warmed_up:
            if all(len(v) >= 10 for v in self._price_history.values()):
                self._warmed_up = True

    # ------------------------------------------------------
    # Intent proposal (called by engine)
    # ------------------------------------------------------

    def propose_intent(self) -> Optional[TradeIntent]:
        """
        Propose at most ONE TradeIntent.

        Engine controls when this is called.
        Strategy remains silent unless confident.
        """

        if not self._warmed_up:
            return None

        # --------------------------------------------------
        # PLACEHOLDER — no alpha yet - strategy remains silent
        # --------------------------------------------------

        return None

    # ------------------------------------------------------
    # Diagnostics / Introspection (optional)
    # ------------------------------------------------------

    def is_warmed_up(self) -> bool:
        return self._warmed_up
