# ==========================================================
# Temporary Paper-Test Strategy
# Phase 1 execution smoke testing only. Never for TRADE mode.
# ==========================================================

from datetime import datetime, timezone
from typing import Optional

from config import PAPER_TEST_COOLDOWN_CANDLES, PAPER_TEST_MIN_MOVE_PCT
from strategy.strategy import Strategy
from strategy.trade_intent import TradeIntent


class PaperTestStrategy(Strategy):
    """Simple completed-candle momentum strategy for paper testing.

    It reuses Strategy's production candle builder and warm-up contract, but
    replaces the restrictive structure proposal logic. Three consecutively
    rising closes propose LONG; three falling closes propose SHORT. The
    strongest percentage move across the current universe is selected.
    """

    def __init__(self, max_history: int = 200, system_log=None):
        super().__init__(max_history=max_history, system_log=system_log)
        self._paper_test_last_trade_bucket = None

    def propose_intent(self) -> Optional[TradeIntent]:
        if not self._warmed_up:
            return None

        candidates = []
        newest_bucket = None

        for symbol in self._universe:
            candles = self._candle_history.get(symbol)
            current = self._current_candle.get(symbol)
            if not candles or len(candles) < 3 or current is None:
                continue

            bucket = int(current["bucket"])
            newest_bucket = bucket if newest_bucket is None else max(newest_bucket, bucket)

            if self._last_evaluated_bucket.get(symbol) == bucket:
                continue
            self._last_evaluated_bucket[symbol] = bucket

            c1 = float(candles[-3][3])
            c2 = float(candles[-2][3])
            c3 = float(candles[-1][3])
            if c1 <= 0:
                continue

            move_pct = abs(c3 - c1) / c1 * 100.0
            if move_pct < PAPER_TEST_MIN_MOVE_PCT:
                continue

            direction = None
            if c1 < c2 < c3:
                direction = "LONG"
            elif c1 > c2 > c3:
                direction = "SHORT"

            if direction is not None:
                candidates.append((move_pct, symbol, direction, bucket))

        if not candidates:
            return None

        candidates.sort(reverse=True)
        move_pct, symbol, direction, bucket = candidates[0]

        if (
            self._paper_test_last_trade_bucket is not None
            and bucket - self._paper_test_last_trade_bucket
            < PAPER_TEST_COOLDOWN_CANDLES
        ):
            return None

        self._paper_test_last_trade_bucket = bucket

        if self.system_log:
            self.system_log.warning(
                "PAPER_TEST_INTENT | "
                f"symbol={symbol} | direction={direction} | "
                f"three_close_move_pct={move_pct:.6f} | "
                "eligible_for_training=false"
            )

        return TradeIntent(
            symbol=symbol,
            direction=direction,
            pattern="PAPER_TEST_MOMENTUM",
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
            structure_fingerprint={
                "strategy_mode": "PAPER_TEST",
                "three_close_move_pct": move_pct,
                "eligible_for_training": False,
            },
        )
