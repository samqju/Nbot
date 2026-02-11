# ==========================================================
# Strategy — Alpha Oracle (Ranked Breakout v1, Bi-Directional)
# ==========================================================

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, Optional, List

from strategy.trade_intent import TradeIntent


class Strategy:

    def __init__(self, max_history: int = 120):

        self._price_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

        self._last_ts: Dict[str, int] = {}
        self._warmed_up = False
        self._universe = set()

        # -----------------------------
        # Parameters
        # -----------------------------
        self.LOOKBACK = 20
        self.BREAKOUT_BUFFER_PCT = 0.05
        self.COMPRESSION_MAX_PCT = 1.2
        self.REL_STRENGTH_LOOKBACK = 10

    # ------------------------------------------------------

    def on_price(self, symbol: str, price: float, timestamp: int) -> None:

        self._price_history[symbol].append(price)
        self._last_ts[symbol] = timestamp

        if not self._warmed_up:
            if self._universe:
                if all(
                    s in self._price_history
                    and len(self._price_history[s]) >= self.LOOKBACK
                    for s in self._universe
                ):
                    self._warmed_up = True

    # ------------------------------------------------------

    def set_universe(self, symbols):
        self._universe = set(symbols)

    # ------------------------------------------------------

    def propose_intent(self) -> Optional[TradeIntent]:

        if not self._warmed_up:
            return None

        best_symbol = None
        best_direction = None
        best_score = None

        universe_returns: List[float] = []

        # ---------------------------------------
        # Relative strength baseline
        # ---------------------------------------

        for symbol in self._universe:
            prices = self._price_history.get(symbol)
            if not prices or len(prices) < self.REL_STRENGTH_LOOKBACK:
                continue

            past_price = prices[-self.REL_STRENGTH_LOOKBACK]
            current_price = prices[-1]

            if past_price <= 0:
                continue

            ret = (current_price - past_price) / past_price
            universe_returns.append(ret)

        if not universe_returns:
            return None

        median_return = sorted(universe_returns)[
            len(universe_returns) // 2
        ]

        # ---------------------------------------
        # Evaluate candidates
        # ---------------------------------------

        for symbol in self._universe:

            prices = self._price_history.get(symbol)
            if not prices or len(prices) < self.LOOKBACK:
                continue

            current_price = prices[-1]
            window = list(prices)[-self.LOOKBACK:]

            highest_high = max(window[:-1])
            lowest_low = min(window[:-1])

            if highest_high <= 0:
                continue

            range_pct = ((highest_high - lowest_low) / current_price) * 100.0
            if range_pct > self.COMPRESSION_MAX_PCT:
                continue

            if len(prices) < self.REL_STRENGTH_LOOKBACK:
                continue

            past_price = prices[-self.REL_STRENGTH_LOOKBACK]
            if past_price <= 0:
                continue

            symbol_return = (current_price - past_price) / past_price

            # ---------------------------
            # LONG breakout
            # ---------------------------

            long_breakout_level = highest_high * (
                1 + self.BREAKOUT_BUFFER_PCT / 100.0
            )

            if (
                current_price > long_breakout_level
                and symbol_return > median_return
            ):
                compression_score = 1.0 / max(range_pct, 0.0001)
                strength_score = symbol_return
                score = compression_score + strength_score

                if best_score is None or score > best_score:
                    best_score = score
                    best_symbol = symbol
                    best_direction = "LONG"

            # ---------------------------
            # SHORT breakdown
            # ---------------------------

            short_break_level = lowest_low * (
                1 - self.BREAKOUT_BUFFER_PCT / 100.0
            )

            if (
                current_price < short_break_level
                and symbol_return < median_return
            ):
                compression_score = 1.0 / max(range_pct, 0.0001)
                strength_score = abs(symbol_return)
                score = compression_score + strength_score

                if best_score is None or score > best_score:
                    best_score = score
                    best_symbol = symbol
                    best_direction = "SHORT"

        if best_symbol is None:
            return None

        return TradeIntent(
            symbol=best_symbol,
            direction=best_direction,
            pattern="RANKED_BREAKOUT_V1",
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------

    def is_warmed_up(self) -> bool:
        return self._warmed_up
