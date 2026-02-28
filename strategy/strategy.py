
# ==========================================================
# Strategy — 5M Structured Conservative (Engine Compatible)
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
        # Trade Governor (UNCHANGED)
        # -----------------------------
        self._daily_trade_count = 0
        self._last_trade_minute = {}
        self._current_utc_day = None

        self.MAX_TRADES_PER_DAY = 30
        self.MIN_TRADE_SPACING_MINUTES = 6

        # -----------------------------
        # 5M Windows
        # -----------------------------
        self.SHORT_WINDOW = 10
        self.LONG_WINDOW = 30
        self.WARMUP_WINDOW = 50

    # ======================================================
    # Candle Builder (5M)
    # ======================================================

    def on_price(self, symbol: str, price: float, timestamp: int):

        bucket = timestamp // 300000  # 5m bucket

        candle = self._current_candle.get(symbol)

        if candle is None or candle["bucket"] != bucket:

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
                "bucket": bucket,
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
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        ):
            self._warmed_up = True

        # Daily reset (UNCHANGED)
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
    # Warmup Seeder (UNCHANGED CONTRACT)
    # ======================================================

    def seed_candle(
        self,
        symbol: str,
        o: float,
        h: float,
        l: float,
        c: float,
        timestamp: int,
    ):

        bucket = timestamp // 300000

        self._candle_history[symbol].append((o, h, l, c))

        self._current_candle[symbol] = {
            "bucket": bucket,
            "open": c,
            "high": c,
            "low": c,
            "close": c,
        }

        if (
            self._universe
            and all(
                len(self._candle_history[s]) >= self.WARMUP_WINDOW
                for s in self._universe
            )
        ):
            self._warmed_up = True

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

    def _trade_spacing_ok(self, symbol, bucket):
        last_bucket = self._last_trade_minute.get(symbol)
        if last_bucket is None:
            return True
        return (bucket - last_bucket) >= self.MIN_TRADE_SPACING_MINUTES

    def _avg_range(self, candles, window):
        if len(candles) < window:
            return None
        recent = list(candles)[-window:]
        ranges = [(c[1] - c[2]) for c in recent]
        return sum(ranges) / len(ranges)

    def _trend_score(self, candles):
        c_list = list(candles)
        closes = [c[3] for c in c_list[-10:]]
        score = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                score += 1
            elif closes[i] < closes[i - 1]:
                score -= 1
        return score

    def _strong_pullback(self, candles):
        if len(candles) < 5:
            return False

        last3 = list(candles)[-3:]
        r0 = last3[0][1] - last3[0][2]
        r1 = last3[1][1] - last3[1][2]
        r2 = last3[2][1] - last3[2][2]

        return r1 < r0 and r2 < r1

    def _breakout_score(self, candles):
        c_list = list(candles)

        highs = [c[1] for c in c_list[-20:]]
        lows = [c[2] for c in c_list[-20:]]
        last_close = c_list[-1][3]

        if last_close > max(highs[:-1]):
            return 4
        if last_close < min(lows[:-1]):
            return 4
        return 0

    def _is_compressing(self, candles):
        """
        Strong compression:
        - Last 8 candles tighter than prior 12
        - AND bodies shrinking
        """

        if len(candles) < 25:
            return False

        c = list(candles)

        recent = c[-8:]
        prior = c[-20:-8]

        recent_range = sum(x[1] - x[2] for x in recent) / len(recent)
        prior_range = sum(x[1] - x[2] for x in prior) / len(prior)

        if prior_range <= 0:
            return False

        # Volatility compression
        if recent_range >= (0.65 * prior_range):
            return False

        # Body contraction
        recent_body = sum(abs(x[3] - x[0]) for x in recent) / len(recent)
        prior_body = sum(abs(x[3] - x[0]) for x in prior) / len(prior)

        if recent_body >= prior_body:
            return False

        return True

    def _has_directional_bias(self, candles):
        """
        Require directional push before breakout.
        Prevents entering random spikes.
        """

        if len(candles) < 15:
            return False

        closes = [c[3] for c in list(candles)[-10:]]

        up_moves = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i-1])
        down_moves = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i-1])

        return max(up_moves, down_moves) >= 6

    # ======================================================
    # Main Proposal Logic
    # ======================================================

    def propose_intent(self) -> Optional[TradeIntent]:

        if not self._warmed_up:
            return None

        if self._daily_trade_count >= self.MAX_TRADES_PER_DAY:
            return None

        candidates = []

        for symbol in self._universe:

            candles = self._candle_history.get(symbol)
            if not candles or len(candles) < self.WARMUP_WINDOW:
                continue

            # --------------------------------------------------
            # STRUCTURE SAFETY FILTERS (NEW)
            # --------------------------------------------------

            last_close = candles[-1][3]

            # 1️⃣ Reject ultra low priced coins
            if last_close < 0.01:
                continue

            # 2️⃣ Reject dead structure (too small average range)
            short_range = self._avg_range(candles, self.SHORT_WINDOW)
            long_range = self._avg_range(candles, self.LONG_WINDOW)

            if short_range is None or long_range is None:
                continue

            # Require meaningful movement (at least 0.25% average range)
            if (short_range / last_close) < 0.0025:
                continue

            # 3️⃣ Reject volatility spikes (exhaustion move)
            if short_range > (2.5 * long_range):
                continue

            bucket = self._current_candle[symbol]["bucket"]

            if not self._trade_spacing_ok(symbol, bucket):
                continue

            trend_score = self._trend_score(candles)
            breakout_score = self._breakout_score(candles)

            direction = None
            total_score = 0

            # Strong continuation
            if abs(trend_score) >= 6 and self._strong_pullback(candles):
                direction = "LONG" if trend_score > 0 else "SHORT"
                total_score = abs(trend_score)

            # Breakout (allowed without prior trend)
            elif (
                breakout_score > 0
                and self._is_compressing(candles)
                and self._has_directional_bias(candles)
            ):
                last_close = candles[-1][3]
                prev_close = candles[-2][3]
                direction = "LONG" if last_close > prev_close else "SHORT"
                total_score = breakout_score + 2  # bonus for structured breakout

            if direction:
                candidates.append((symbol, direction, total_score))

        if not candidates:
            return None

        # Top 3 ranking
        candidates.sort(key=lambda x: x[2], reverse=True)
        best_symbol, best_direction, _ = candidates[0]

        # Governor update
        bucket = self._current_candle[best_symbol]["bucket"]
        self._daily_trade_count += 1
        self._last_trade_minute[best_symbol] = bucket

        return TradeIntent(
            symbol=best_symbol,
            direction=best_direction,
            pattern="STRUCTURE_5M",
            entry_price=None,
            generated_at=datetime.now(timezone.utc),
        )
