import numpy as np
from .structure_types import *

class StructureClassifier:

    def avg_range(self, candles):
        ranges = [c[1] - c[2] for c in candles]
        return sum(ranges) / len(ranges)

    def trend_score(self, candles):
        closes = [c[3] for c in candles]
        score = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i-1]:
                score += 1
            else:
                score -= 1
        return score

    def compression(self, candles):
        ranges = [c[1] - c[2] for c in candles]
        recent = np.mean(ranges[-5:])
        long = np.mean(ranges)
        return recent < long * 0.7

    def classify(self, candles):

        if len(candles) < 2:
            return None

        # Candle format from strategy:
        # (open, high, low, close)
        ranges = []
        closes = []

        for c in candles:
            o, h, l, cl = c
            ranges.append(h - l)
            closes.append(cl)
        avg_range = np.mean(ranges)
        recent_range = np.mean(ranges[-3:])
        trend = self.trend_score(candles)

        highs = []
        lows = []

        for c in candles[:-1]:
            o, h, l, cl = c
            highs.append(h)
            lows.append(l)

        high = max(highs)
        low = min(lows)

        last_close = closes[-1]
        prev_close = closes[-2]

        # 1 TREND CONTINUATION
        if abs(trend) > 6 and recent_range > avg_range:
            return TREND_CONTINUATION

        # 2 COMPRESSION BREAKOUT
        if self.compression(candles) and last_close > high:
            return COMPRESSION_BREAKOUT

        # 3 LIQUIDITY SWEEP
        if candles[-1][1] > high and last_close < prev_close:
            return LIQUIDITY_SWEEP

        # 4 RANGE EXPANSION
        if recent_range > avg_range * 1.8:
            return RANGE_EXPANSION

        # 5 TREND EXHAUSTION
        if abs(trend) > 8 and recent_range < avg_range * 0.5:
            return TREND_EXHAUSTION

        # 6 BREAKOUT FAILURE
        if last_close < high and prev_close > high:
            return BREAKOUT_FAILURE

        # 7 VOLATILITY EXPANSION
        if recent_range > avg_range * 2:
            return VOLATILITY_EXPANSION

        # 8 MEAN REVERSION
        deviation = abs(last_close - np.mean(closes))
        if deviation > avg_range * 2:
            return MEAN_REVERSION

        return None

    # --------------------------------------------------
    # STRUCTURE FINGERPRINT (STEP 2)
    # --------------------------------------------------

    def fingerprint(self, candles):

        # Momentum and structure comparisons require at least five candles.
        # Return no fingerprint instead of calling max/min on empty history.
        if len(candles) < 5:
            return None

        ranges = []
        closes = []

        for c in candles:
            o, h, l, cl = c
            ranges.append(h - l)
            closes.append(cl)

        avg_range = np.mean(ranges)
        recent_range = np.mean(ranges[-5:])

        trend = self.trend_score(candles)

        # Volatility level
        if recent_range > avg_range * 1.8:
            volatility = "HIGH"
        elif recent_range < avg_range * 0.7:
            volatility = "LOW"
        else:
            volatility = "NORMAL"

        # Trend direction
        if trend > 4:
            trend_dir = "UP"
        elif trend < -4:
            trend_dir = "DOWN"
        else:
            trend_dir = "FLAT"

        # Compression detection
        # NumPy comparisons may return numpy.bool_, which json cannot
        # serialize. Persist only a native Python bool.
        compression = bool(self.compression(candles))

        structure_type = self.classify(candles)

        # --------------------------------------------------
        # Momentum
        # --------------------------------------------------

        momentum = closes[-1] - closes[-5]

        if momentum > avg_range:
            momentum_dir = "RISING"
        elif momentum < -avg_range:
            momentum_dir = "FALLING"
        else:
            momentum_dir = "FLAT"

        # --------------------------------------------------
        # Wick ratio
        # --------------------------------------------------

        wick_ratios = []

        for c in candles[-5:]:
            o, h, l, cl = c

            body = abs(cl - o)
            full = h - l

            if full == 0:
                continue

            wick = full - body
            wick_ratios.append(wick / full)

        wick_ratio = np.mean(wick_ratios) if wick_ratios else 0.0

        # --------------------------------------------------
        # Compression level
        # --------------------------------------------------

        compression_level = recent_range / avg_range if avg_range else 1.0

        # --------------------------------------------------
        # Range expansion factor
        # --------------------------------------------------

        range_expansion = recent_range / avg_range if avg_range else 1.0

        trend_strength = abs(trend)

        return {
            "structure": structure_type,
            "trend": trend_dir,
            "volatility": volatility,
            "compression": compression,
            "trend_score": trend,
            "trend_strength": trend_strength,
            "momentum": momentum_dir,
            "wick_ratio": round(float(wick_ratio), 4),
            "compression_level": round(float(compression_level), 4),
            "range_expansion": round(float(range_expansion), 4),
        }
