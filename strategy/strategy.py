# ==========================================================
# Strategy — VEX-LR v2 (Hybrid Professional System)
# Volatility Expansion + Liquidity Reversal
# Balanced Mode (2–4 trades/day)
# ==========================================================

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, Optional
from strategy.trade_intent import TradeIntent


class Strategy:

    def __init__(self, max_history: int = 200):

        # -----------------------------
        # Candle Storage
        # -----------------------------
        self._current_candle: Dict[str, dict] = {}
        self._candle_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_history)
        )

        self._last_ts: Dict[str, int] = {}
        self._universe = set()
        self._warmed_up = False

        # -----------------------------
        # Trade Governor
        # -----------------------------
        self._daily_trade_count = 0
        self._last_trade_minute = {}
        self._current_utc_day = None

        self.MAX_TRADES_PER_DAY = 4
        self.MIN_TRADE_SPACING_MINUTES = 3

        # -----------------------------
        # Regime Parameters
        # -----------------------------
        self.SHORT_RANGE_WINDOW = 10
        self.LONG_RANGE_WINDOW = 30

        self.EXPANSION_MULTIPLIER = 1.4
        self.CLIMAX_MULTIPLIER = 3.0
        self.CLIMAX_MOVE_PCT = 1.5

        self.WICK_EXHAUSTION_RATIO = 0.35

    # ======================================================
    # Candle Builder
    # ======================================================

    def on_price(self, symbol: str, price: float, timestamp: int):

        minute = timestamp // 60000
        candle = self._current_candle.get(symbol)

        if candle is None or candle["minute"] != minute:

            if candle is not None:
                self._candle_history[symbol].append(
                    (
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                    )
                )

            self._current_candle[symbol] = {
                "minute": minute,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
            }

        else:
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price

        self._last_ts[symbol] = timestamp

        # Warmup check
        if (
            self._universe
            and all(
                len(self._candle_history[s]) >= self.LONG_RANGE_WINDOW
                for s in self._universe
            )
        ):
            self._warmed_up = True

        # Daily reset
        utc_day = datetime.fromtimestamp(
            timestamp / 1000, timezone.utc
        ).timetuple().tm_yday

        if self._current_utc_day is None:
            self._current_utc_day = utc_day
        elif utc_day != self._current_utc_day:
            self._current_utc_day = utc_day
            self._daily_trade_count = 0
            self._last_trade_minute.clear()

    # ======================================================
    # Universe
    # ======================================================

    def set_universe(self, symbols):
        self._universe = set(symbols)

    def is_warmed_up(self) -> bool:
        return self._warmed_up

    # ======================================================
    # Helpers
    # ======================================================

    def _avg_range(self, candles, window):
        if len(candles) < window:
            return None

        recent = list(candles)[-window:]
        ranges = [(c[1] - c[2]) for c in recent]
        return sum(ranges) / len(ranges)

    def _wick_ratio(self, candle):
        o, h, l, c = candle
        total_range = h - l
        if total_range <= 0:
            return 0
        body = abs(c - o)
        wick = total_range - body
        return wick / total_range

    def _directional_persistence(self, candles):
        if len(candles) < 3:
            return None

        last3 = list(candles)[-3:]
        closes = [c[3] for c in last3]

        if closes[2] > closes[1] > closes[0]:
            return "UP"
        if closes[2] < closes[1] < closes[0]:
            return "DOWN"

        return None

    def _three_min_move_pct(self, candles):
        if len(candles) < 3:
            return 0.0

        last3 = list(candles)[-3:]
        first = last3[0][3]
        last = last3[-1][3]

        if first <= 0:
            return 0.0

        return ((last - first) / first) * 100.0

    def _trade_spacing_ok(self, symbol, minute):
        last_min = self._last_trade_minute.get(symbol)
        if last_min is None:
            return True
        return (minute - last_min) >= self.MIN_TRADE_SPACING_MINUTES

    # ======================================================
    # Regime Detection
    # ======================================================

    def _classify_regime(self, candles):

        short_avg = self._avg_range(
            candles, self.SHORT_RANGE_WINDOW
        )
        long_avg = self._avg_range(
            candles, self.LONG_RANGE_WINDOW
        )

        if short_avg is None or long_avg is None:
            return None

        current = candles[-1]
        current_range = current[1] - current[2]
        wick_ratio = self._wick_ratio(current)

        move_pct = abs(self._three_min_move_pct(candles))

        # CLIMACTIC
        if (
            current_range > self.CLIMAX_MULTIPLIER * short_avg
            or move_pct > self.CLIMAX_MOVE_PCT
        ):
            if wick_ratio > self.WICK_EXHAUSTION_RATIO:
                return "CLIMACTIC"

        # EXPANSION
        persistence = self._directional_persistence(candles)

        if (
            short_avg > self.EXPANSION_MULTIPLIER * long_avg
            and persistence is not None
            and wick_ratio < self.WICK_EXHAUSTION_RATIO
        ):
            return "EXPANSION"

        return "QUIET"

    # ======================================================
    # Entry Engines
    # ======================================================

    def _check_expansion_entry(self, symbol, candles):

        persistence = self._directional_persistence(candles)
        if persistence is None:
            return None

        last = candles[-1]
        prev = candles[-2]

        # Pullback logic: last candle smaller than previous
        last_range = last[1] - last[2]
        prev_range = prev[1] - prev[2]

        if last_range >= prev_range:
            return None

        direction = "LONG" if persistence == "UP" else "SHORT"

        return TradeIntent(
            symbol=symbol,
            direction=direction,
            pattern="VEX_EXPANSION",
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
        )

    def _check_reversal_entry(self, symbol, candles):

        if len(candles) < 3:
            return None

        last = candles[-1]
        prev = candles[-2]

        wick_ratio = self._wick_ratio(prev)

        if wick_ratio < self.WICK_EXHAUSTION_RATIO:
            return None

        # Stall condition: small body after exhaustion
        prev_range = prev[1] - prev[2]
        last_range = last[1] - last[2]

        if last_range > prev_range * 0.7:
            return None

        direction = "LONG" if prev[3] < prev[0] else "SHORT"

        return TradeIntent(
            symbol=symbol,
            direction=direction,
            pattern="VEX_REVERSAL",
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
        )

    # ======================================================
    # Main Proposal Logic
    # ======================================================

    def propose_intent(self) -> Optional[TradeIntent]:

        if not self._warmed_up:
            return None

        if self._daily_trade_count >= self.MAX_TRADES_PER_DAY:
            return None

        for symbol in self._universe:

            candles = self._candle_history.get(symbol)
            if not candles or len(candles) < self.LONG_RANGE_WINDOW:
                continue

            regime = self._classify_regime(candles)
            current_minute = candles[-1][0] if isinstance(candles[-1], tuple) else None

            minute = self._current_candle[symbol]["minute"]

            if not self._trade_spacing_ok(symbol, minute):
                continue

            intent = None

            # Priority: CLIMACTIC first
            if regime == "CLIMACTIC":
                intent = self._check_reversal_entry(symbol, candles)

            elif regime == "EXPANSION":
                intent = self._check_expansion_entry(symbol, candles)

            if intent is not None:
                self._daily_trade_count += 1
                self._last_trade_minute[symbol] = minute
                return intent

        return None
