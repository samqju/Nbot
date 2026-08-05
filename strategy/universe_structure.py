"""Pure 5-minute market-structure analysis for universe selection."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import mean


@dataclass(frozen=True)
class UniverseStructure:
    regime: tuple[str, ...]
    category: str
    structure_score: float
    volatility_score: float
    candle_quality_score: float
    directional_score: float
    setup_readiness: dict[str, float]
    best_setup: str
    best_setup_score: float
    features: dict[str, float]

    def as_dict(self) -> dict:
        document = asdict(self)
        document["regime"] = list(self.regime)
        return document


class UniverseStructureAnalyzer:
    """Analyze completed Binance 5-minute klines deterministically."""

    MIN_CANDLES = 60

    def analyze(self, raw_candles) -> UniverseStructure:
        candles = self._normalize(raw_candles)
        if len(candles) < self.MIN_CANDLES:
            raise ValueError("STRUCTURE_HISTORY_INSUFFICIENT")

        recent = candles[-60:]
        closes = [row[3] for row in recent]
        highs = [row[1] for row in recent]
        lows = [row[2] for row in recent]
        ranges = [max(0.0, row[1] - row[2]) for row in recent]
        last_close = closes[-1]
        if last_close <= 0:
            raise ValueError("STRUCTURE_LAST_CLOSE_INVALID")

        short_range = mean(ranges[-10:]) / last_close
        long_range = mean(ranges) / last_close
        range_acceleration = (
            short_range / long_range if long_range > 0 else 0.0
        )

        recent_20 = recent[-20:]
        body_ratios = []
        wick_ratios = []
        for open_, high, low, close in recent_20:
            total = high - low
            if total <= 0:
                continue
            body = abs(close - open_)
            body_ratios.append(body / total)
            wick_ratios.append(max(0.0, total - body) / total)

        body_ratio = mean(body_ratios) if body_ratios else 0.0
        wick_ratio = mean(wick_ratios) if wick_ratios else 1.0

        slope = self._normalized_slope(closes[-30:])
        directional = self._directional_consistency(closes[-12:])
        swing_up, swing_down = self._swing_structure(recent[-30:])
        high_20 = max(highs[-20:])
        low_20 = min(lows[-20:])
        span_20 = max(high_20 - low_20, last_close * 1e-9)
        distance_high = (high_20 - last_close) / last_close
        distance_low = (last_close - low_20) / last_close
        location = (last_close - low_20) / span_20
        compression = self._compression_score(ranges)
        expansion = self._expansion_score(range_acceleration)
        rejection = self._rejection_score(recent_20)
        displacement = self._displacement_score(recent_20)
        mean_deviation = self._mean_deviation(closes[-20:])
        triangle = self._triangle_score(recent[-20:])

        trend_strength = self._clamp(
            abs(slope) * 35.0
            + directional * 0.35
            + max(swing_up, swing_down) * 0.30
        )
        structure_clarity = self._clamp(
            trend_strength * 0.45
            + (1.0 - min(1.0, wick_ratio)) * 0.20
            + max(compression, expansion) * 0.20
            + displacement * 0.15
        )
        volatility_quality = self._volatility_quality(
            long_range,
            range_acceleration,
        )
        candle_quality = self._clamp(
            body_ratio * 0.65
            + (1.0 - min(1.0, wick_ratio)) * 0.35
        )

        readiness = {
            "pullback_continuation": self._clamp(
                trend_strength * 0.55
                + (1.0 - abs(location - 0.55) * 2.0) * 0.20
                + candle_quality * 0.15
                + volatility_quality * 0.10
            ),
            "mean_reversion": self._clamp(
                (1.0 - trend_strength) * 0.35
                + mean_deviation * 0.35
                + rejection * 0.20
                + volatility_quality * 0.10
            ),
            "fake_breakout": self._clamp(
                max(rejection, wick_ratio) * 0.45
                + min(
                    1.0,
                    max(
                        0.0,
                        -distance_high / max(long_range, 1e-9),
                        -distance_low / max(long_range, 1e-9),
                    ),
                ) * 0.30
                + compression * 0.25
            ),
            "liquidity_sweep": self._clamp(
                rejection * 0.45
                + max(0.0, 1.0 - min(distance_high, distance_low)
                      / max(long_range * 2.0, 1e-9)) * 0.35
                + displacement * 0.20
            ),
            "support_bounce": self._clamp(
                max(0.0, 1.0 - distance_low
                    / max(long_range * 3.0, 1e-9)) * 0.50
                + rejection * 0.30
                + max(0.0, slope * 20.0) * 0.20
            ),
            "resistance_rejection": self._clamp(
                max(0.0, 1.0 - distance_high
                    / max(long_range * 3.0, 1e-9)) * 0.50
                + rejection * 0.30
                + max(0.0, -slope * 20.0) * 0.20
            ),
            "momentum_exhaustion": self._clamp(
                trend_strength * 0.35
                + rejection * 0.30
                + max(0.0, range_acceleration - 1.2) * 0.20
                + mean_deviation * 0.15
            ),
            "triangle_breakout": self._clamp(
                triangle * 0.50
                + compression * 0.30
                + directional * 0.20
            ),
            "range_breakout": self._clamp(
                compression * 0.35
                + max(
                    0.0,
                    1.0 - min(distance_high, distance_low)
                    / max(long_range * 3.0, 1e-9),
                ) * 0.35
                + displacement * 0.20
                + volatility_quality * 0.10
            ),
            "trend_reversal": self._clamp(
                trend_strength * 0.30
                + rejection * 0.30
                + mean_deviation * 0.20
                + displacement * 0.20
            ),
        }
        best_setup = max(readiness, key=readiness.get)
        category = self._category(best_setup)

        regimes = []
        if slope > 0.0005 and swing_up >= swing_down:
            regimes.append("TRENDING_UP")
        elif slope < -0.0005 and swing_down >= swing_up:
            regimes.append("TRENDING_DOWN")
        else:
            regimes.append("RANGING")
        if compression >= 0.60:
            regimes.append("COMPRESSING")
        if expansion >= 0.60:
            regimes.append("EXPANDING")
        if rejection >= 0.65 and trend_strength >= 0.55:
            regimes.append("EXHAUSTED")
        if (
            long_range > 0.04
            or range_acceleration > 4.0
            or wick_ratio > 0.88
        ):
            regimes.append("UNSTABLE")

        return UniverseStructure(
            regime=tuple(regimes),
            category=category,
            structure_score=structure_clarity,
            volatility_score=volatility_quality,
            candle_quality_score=candle_quality,
            directional_score=directional,
            setup_readiness={
                key: round(value, 8)
                for key, value in readiness.items()
            },
            best_setup=best_setup,
            best_setup_score=readiness[best_setup],
            features={
                "short_range": short_range,
                "long_range": long_range,
                "range_acceleration": range_acceleration,
                "normalized_slope": slope,
                "directional_consistency": directional,
                "wick_ratio_recent": wick_ratio,
                "body_ratio_recent": body_ratio,
                "distance_high": distance_high,
                "distance_low": distance_low,
                "compression_score": compression,
                "expansion_score": expansion,
                "rejection_score": rejection,
                "displacement_score": displacement,
                "mean_deviation": mean_deviation,
                "triangle_score": triangle,
            },
        )

    @staticmethod
    def _normalize(raw):
        normalized = []
        for row in raw:
            if len(row) >= 5:
                open_, high, low, close = (
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                )
            elif len(row) == 4:
                open_, high, low, close = map(float, row)
            else:
                raise ValueError("STRUCTURE_CANDLE_SCHEMA_INVALID")
            if not all(
                math.isfinite(value)
                for value in (open_, high, low, close)
            ):
                raise ValueError("STRUCTURE_CANDLE_VALUE_INVALID")
            if high < low or min(open_, high, low, close) <= 0:
                raise ValueError("STRUCTURE_CANDLE_OHLC_INVALID")
            normalized.append((open_, high, low, close))
        return normalized

    @staticmethod
    def _normalized_slope(closes):
        if len(closes) < 2 or closes[-1] <= 0:
            return 0.0
        n = len(closes)
        x_mean = (n - 1) / 2.0
        y_mean = mean(closes)
        numerator = sum(
            (idx - x_mean) * (value - y_mean)
            for idx, value in enumerate(closes)
        )
        denominator = sum(
            (idx - x_mean) ** 2 for idx in range(n)
        )
        return (
            numerator / denominator / closes[-1]
            if denominator > 0 else 0.0
        )

    @staticmethod
    def _directional_consistency(closes):
        moves = [
            closes[idx] - closes[idx - 1]
            for idx in range(1, len(closes))
        ]
        nonzero = [move for move in moves if move != 0]
        if not nonzero:
            return 0.0
        dominant = max(
            sum(move > 0 for move in nonzero),
            sum(move < 0 for move in nonzero),
        )
        return dominant / len(nonzero)

    @staticmethod
    def _swing_structure(candles):
        highs = [row[1] for row in candles]
        lows = [row[2] for row in candles]
        swing_highs = []
        swing_lows = []
        for idx in range(2, len(candles) - 2):
            if highs[idx] == max(highs[idx - 2:idx + 3]):
                swing_highs.append(highs[idx])
            if lows[idx] == min(lows[idx - 2:idx + 3]):
                swing_lows.append(lows[idx])
        up = down = 0.0
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            up = (
                float(swing_highs[-1] > swing_highs[-2])
                + float(swing_lows[-1] > swing_lows[-2])
            ) / 2.0
            down = (
                float(swing_highs[-1] < swing_highs[-2])
                + float(swing_lows[-1] < swing_lows[-2])
            ) / 2.0
        return up, down

    @staticmethod
    def _compression_score(ranges):
        long_avg = mean(ranges)
        short_avg = mean(ranges[-10:])
        if long_avg <= 0:
            return 0.0
        return UniverseStructureAnalyzer._clamp(
            (1.0 - short_avg / long_avg) / 0.45
        )

    @staticmethod
    def _expansion_score(ratio):
        return UniverseStructureAnalyzer._clamp(
            (ratio - 1.0) / 1.25
        )

    @staticmethod
    def _rejection_score(candles):
        scores = []
        for open_, high, low, close in candles[-8:]:
            total = high - low
            if total <= 0:
                continue
            body = abs(close - open_)
            scores.append(max(0.0, total - body) / total)
        return mean(scores) if scores else 0.0

    @staticmethod
    def _displacement_score(candles):
        ranges = [row[1] - row[2] for row in candles]
        average = mean(ranges)
        if average <= 0:
            return 0.0
        recent = []
        for open_, high, low, close in candles[-5:]:
            recent.append(abs(close - open_) / average)
        return UniverseStructureAnalyzer._clamp(
            max(recent, default=0.0) / 1.5
        )

    @staticmethod
    def _mean_deviation(closes):
        average = mean(closes)
        if average <= 0:
            return 0.0
        deviations = [
            abs(value - average) / average for value in closes
        ]
        scale = max(mean(deviations), 1e-9)
        return UniverseStructureAnalyzer._clamp(
            abs(closes[-1] - average) / average / (scale * 2.0)
        )

    @staticmethod
    def _triangle_score(candles):
        half = len(candles) // 2
        first_high = max(row[1] for row in candles[:half])
        first_low = min(row[2] for row in candles[:half])
        second_high = max(row[1] for row in candles[half:])
        second_low = min(row[2] for row in candles[half:])
        first_width = first_high - first_low
        second_width = second_high - second_low
        if first_width <= 0:
            return 0.0
        narrowing = max(0.0, 1.0 - second_width / first_width)
        converging = float(
            second_high <= first_high and second_low >= first_low
        )
        return UniverseStructureAnalyzer._clamp(
            narrowing * 0.70 + converging * 0.30
        )

    @staticmethod
    def _volatility_quality(long_range, acceleration):
        range_score = 1.0 - min(
            1.0,
            abs(long_range - 0.012) / 0.025,
        )
        stability = 1.0 - min(
            1.0,
            abs(acceleration - 1.0) / 2.0,
        )
        return UniverseStructureAnalyzer._clamp(
            range_score * 0.65 + stability * 0.35
        )

    @staticmethod
    def _category(setup):
        if setup in {
            "pullback_continuation",
            "momentum_exhaustion",
            "trend_reversal",
        }:
            return "TREND"
        if setup in {
            "triangle_breakout",
            "range_breakout",
            "fake_breakout",
            "liquidity_sweep",
        }:
            return "BREAKOUT"
        return "REVERSION"

    @staticmethod
    def _clamp(value):
        return max(0.0, min(1.0, float(value)))
