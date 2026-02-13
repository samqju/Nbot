# ==========================================================
# Strategy — Alpha Oracle (Ranked Breakout v1, Bi-Directional)
# ==========================================================

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple
from strategy.trade_intent import TradeIntent


class Strategy:

    def __init__(self, max_history: int = 120):

        # Current forming 1m candle per symbol
        self._current_candle: Dict[str, dict] = {}

        # Completed candle history per symbol
        self._candle_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

        self._last_ts: Dict[str, int] = {}
        self._warmed_up = False
        self._universe = set()

        # -----------------------------
        # Parameters
        # -----------------------------
        self.COMPRESSION_LOOKBACK = 8
        self.COMPRESSION_MAX_PCT = 0.5
        self.SWEEP_BUFFER_PCT = 0.05
        self.IMPULSE_BODY_MIN_PCT = 0.25

        # -----------------------------
        # Volatility Regime Filter
        # -----------------------------
        self.ATR_SHORT_WINDOW = 6
        self.ATR_LONG_WINDOW = 30
        self.ATR_UPPER_CAP = 1.2      # reject extreme volatility
        self.ATR_PERCENTILE_FLOOR = 0.75  # 60% of long-term ATR

    # ------------------------------------------------------

    def on_price(self, symbol: str, price: float, timestamp: int) -> None:
        minute = timestamp // 60000

        candle = self._current_candle.get(symbol)

        # New candle
        if candle is None or candle["minute"] != minute:

            # Finalize previous candle
            if candle is not None:
                # Ensure history bucket exists
                _ = self._candle_history[symbol]
                self._candle_history[symbol].append(
                    (
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                    )
                )

            # Start new candle
            self._current_candle[symbol] = {
                "minute": minute,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }

        else:
            # Update forming candle
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price

        self._last_ts[symbol] = timestamp

        if (
            self._universe
            and all(
                len(self._candle_history[s]) >= self.COMPRESSION_LOOKBACK
                for s in self._universe
            )
        ):
            self._warmed_up = True

    # ------------------------------------------------------

    def set_universe(self, symbols):
        self._universe = set(symbols)

    # ------------------------------------------------------
    def _compute_atr_pct(self, candles, window: int):
        if len(candles) < window:
            return None

        recent = list(candles)[-window:]
        ranges = []

        for c in recent:
            high = c[1]
            low = c[2]
            close = c[3]
            if close > 0:
                ranges.append(((high - low) / close) * 100)

        if not ranges:
            return None

        return sum(ranges) / len(ranges)



    # ------------------------------------------------------

    def propose_intent(self) -> Optional[TradeIntent]:

        if not self._warmed_up:
            return None

        for symbol in self._universe:
            candles = self._candle_history.get(symbol)
            if not candles or len(candles) < self.COMPRESSION_LOOKBACK + 2:
                continue

            # ---------------------------------
            # Volatility Regime Filter
            # ---------------------------------
            atr_short = self._compute_atr_pct(
                candles, self.ATR_SHORT_WINDOW
            )
            atr_long = self._compute_atr_pct(
                candles, self.ATR_LONG_WINDOW
            )

            if atr_short is None or atr_long is None:
                continue

            if atr_short > self.ATR_UPPER_CAP:
                continue

            if atr_short < atr_long * self.ATR_PERCENTILE_FLOOR:
                continue

            window = list(candles)[-self.COMPRESSION_LOOKBACK-2:-2]

            highs = [c[1] for c in window]
            lows = [c[2] for c in window]

            range_high = max(highs)
            range_low = min(lows)

            current = candles[-1]
            prev = candles[-2]

            current_close = current[3]
            prev_close = prev[3]

            range_pct = ((range_high - range_low) / current_close) * 100
            if range_pct > self.COMPRESSION_MAX_PCT:
                continue

            # --- LONG Sweep + Reclaim ---
            if prev_close < range_low and current_close > range_low:
                body_pct = abs(current_close - prev_close) / prev_close * 100
                if body_pct >= self.IMPULSE_BODY_MIN_PCT:
                    return TradeIntent(
                        symbol=symbol,
                        direction="LONG",
                        pattern="IIE_V1_LONG",
                        entry_price=None,
                        generated_at=datetime.now(timezone.utc),
                    )

            # --- SHORT Sweep + Reclaim ---
            if prev_close > range_high and current_close < range_high:
                body_pct = abs(current_close - prev_close) / prev_close * 100
                if body_pct >= self.IMPULSE_BODY_MIN_PCT:
                    return TradeIntent(
                        symbol=symbol,
                        direction="SHORT",
                        pattern="IIE_V1_SHORT",
                        entry_price=None,
                        generated_at=datetime.now(timezone.utc),
                    )

        return None

    # ------------------------------------------------------

    def is_warmed_up(self) -> bool:
        return self._warmed_up
