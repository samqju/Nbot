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

        # Universe symbols (set by engine)
        self._universe = set()

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
            if self._universe:
                if all(
                    symbol in self._price_history
                    and len(self._price_history[symbol]) >= 10
                    for symbol in self._universe
                ):
                    self._warmed_up = True

    # ------------------------------------------------------
    # Universe injection (called by engine)
    # ------------------------------------------------------

    def set_universe(self, symbols):
        """
        Inform strategy which symbols are tradable.
        Warmup logic is scoped strictly to this universe.
        """
        self._universe = set(symbols)

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
