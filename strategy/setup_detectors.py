"""Independent deterministic setup detectors for Phase 3.6A."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SetupSignal:
    pattern: str
    direction: str
    rule_score: float

    def __post_init__(self):
        direction = str(self.direction).upper()
        if direction not in {"LONG", "SHORT"}:
            raise ValueError("SETUP_SIGNAL_DIRECTION_INVALID")
        score = max(0.0, min(1.0, float(self.rule_score)))
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "rule_score", score)


def _body(c):
    return abs(float(c[3]) - float(c[0]))


def _range(c):
    return max(0.0, float(c[1]) - float(c[2]))


def _upper_wick(c):
    return float(c[1]) - max(float(c[0]), float(c[3]))


def _lower_wick(c):
    return min(float(c[0]), float(c[3])) - float(c[2])


def _avg(values):
    return sum(values) / len(values) if values else 0.0


class SetupDetectorRegistry:
    """Run all independent detectors and return de-duplicated signals."""

    DETECTOR_NAMES = (
        "PULLBACK_CONTINUATION",
        "MEAN_REVERSION",
        "FAKE_BREAKOUT",
        "LIQUIDITY_SWEEP",
        "SUPPORT_BOUNCE",
        "RESISTANCE_REJECTION",
        "MOMENTUM_EXHAUSTION",
        "TRIANGLE_BREAKOUT",
        "RANGE_BREAKOUT",
        "TREND_REVERSAL",
    )

    def detect_all(self, candles: Iterable[tuple]) -> list[SetupSignal]:
        c = list(candles)
        if len(c) < 30:
            return []

        signals = []
        for method in (
            self._pullback_continuation,
            self._mean_reversion,
            self._fake_breakout,
            self._liquidity_sweep,
            self._support_bounce,
            self._resistance_rejection,
            self._momentum_exhaustion,
            self._triangle_breakout,
            self._range_breakout,
            self._trend_reversal,
        ):
            signal = method(c)
            if signal is not None:
                signals.append(signal)

        best = {}
        for signal in signals:
            key = (signal.pattern, signal.direction)
            current = best.get(key)
            if current is None or signal.rule_score > current.rule_score:
                best[key] = signal
        return list(best.values())

    @staticmethod
    def _trend(c):
        closes = [x[3] for x in c[-10:]]
        return sum(
            1 if closes[i] > closes[i - 1] else -1
            if closes[i] < closes[i - 1] else 0
            for i in range(1, len(closes))
        )

    def _pullback_continuation(self, c):
        trend = self._trend(c)
        last = c[-1]
        recent = c[-4:]
        if trend >= 5 and min(x[2] for x in recent[:-1]) < c[-5][3]:
            if last[3] > last[0] and last[3] > c[-2][3]:
                return SetupSignal("PULLBACK_CONTINUATION", "LONG", 0.72)
        if trend <= -5 and max(x[1] for x in recent[:-1]) > c[-5][3]:
            if last[3] < last[0] and last[3] < c[-2][3]:
                return SetupSignal("PULLBACK_CONTINUATION", "SHORT", 0.72)

    def _mean_reversion(self, c):
        closes = [x[3] for x in c[-20:]]
        mean = _avg(closes)
        avg_range = _avg([_range(x) for x in c[-20:]])
        if avg_range <= 0:
            return None
        deviation = (closes[-1] - mean) / avg_range
        if deviation <= -2.0:
            return SetupSignal("MEAN_REVERSION", "LONG", min(0.9, 0.55 + abs(deviation) * 0.08))
        if deviation >= 2.0:
            return SetupSignal("MEAN_REVERSION", "SHORT", min(0.9, 0.55 + abs(deviation) * 0.08))

    def _fake_breakout(self, c):
        prior_high = max(x[1] for x in c[-21:-1])
        prior_low = min(x[2] for x in c[-21:-1])
        last = c[-1]
        if last[1] > prior_high and last[3] < prior_high:
            return SetupSignal("FAKE_BREAKOUT", "SHORT", 0.76)
        if last[2] < prior_low and last[3] > prior_low:
            return SetupSignal("FAKE_BREAKOUT", "LONG", 0.76)

    def _liquidity_sweep(self, c):
        prior_high = max(x[1] for x in c[-11:-1])
        prior_low = min(x[2] for x in c[-11:-1])
        last = c[-1]
        total = _range(last)
        if total <= 0:
            return None
        if last[1] > prior_high and _upper_wick(last) / total >= 0.45:
            return SetupSignal("LIQUIDITY_SWEEP", "SHORT", 0.78)
        if last[2] < prior_low and _lower_wick(last) / total >= 0.45:
            return SetupSignal("LIQUIDITY_SWEEP", "LONG", 0.78)

    def _support_bounce(self, c):
        support = min(x[2] for x in c[-20:-1])
        last = c[-1]
        tolerance = max(_avg([_range(x) for x in c[-10:]]) * 0.35, support * 0.001)
        if last[2] <= support + tolerance and last[3] > last[0]:
            if _lower_wick(last) >= _body(last):
                return SetupSignal("SUPPORT_BOUNCE", "LONG", 0.70)

    def _resistance_rejection(self, c):
        resistance = max(x[1] for x in c[-20:-1])
        last = c[-1]
        tolerance = max(_avg([_range(x) for x in c[-10:]]) * 0.35, resistance * 0.001)
        if last[1] >= resistance - tolerance and last[3] < last[0]:
            if _upper_wick(last) >= _body(last):
                return SetupSignal("RESISTANCE_REJECTION", "SHORT", 0.70)

    def _momentum_exhaustion(self, c):
        last = c[-1]
        avg_body = _avg([_body(x) for x in c[-10:-1]])
        total = _range(last)
        if total <= 0 or avg_body <= 0:
            return None
        trend = self._trend(c)
        if trend >= 6 and _upper_wick(last) / total > 0.5 and _body(last) < avg_body:
            return SetupSignal("MOMENTUM_EXHAUSTION", "SHORT", 0.67)
        if trend <= -6 and _lower_wick(last) / total > 0.5 and _body(last) < avg_body:
            return SetupSignal("MOMENTUM_EXHAUSTION", "LONG", 0.67)

    def _triangle_breakout(self, c):
        recent = c[-12:]
        highs_first = max(x[1] for x in recent[:6])
        highs_last = max(x[1] for x in recent[6:-1])
        lows_first = min(x[2] for x in recent[:6])
        lows_last = min(x[2] for x in recent[6:-1])
        last = recent[-1]
        contracting = highs_last < highs_first and lows_last > lows_first
        if not contracting:
            return None
        if last[3] > highs_last:
            return SetupSignal("TRIANGLE_BREAKOUT", "LONG", 0.74)
        if last[3] < lows_last:
            return SetupSignal("TRIANGLE_BREAKOUT", "SHORT", 0.74)

    def _range_breakout(self, c):
        prior = c[-21:-1]
        high = max(x[1] for x in prior)
        low = min(x[2] for x in prior)
        last = c[-1]
        if last[3] > high:
            return SetupSignal("RANGE_BREAKOUT", "LONG", 0.75)
        if last[3] < low:
            return SetupSignal("RANGE_BREAKOUT", "SHORT", 0.75)

    def _trend_reversal(self, c):
        older = c[-16:-6]
        recent = c[-6:]
        older_closes = [x[3] for x in older]
        recent_closes = [x[3] for x in recent]
        older_move = older_closes[-1] - older_closes[0]
        recent_move = recent_closes[-1] - recent_closes[0]
        if older_move < 0 and recent_move > 0 and recent[-1][3] > max(x[1] for x in recent[:-1]):
            return SetupSignal("TREND_REVERSAL", "LONG", 0.73)
        if older_move > 0 and recent_move < 0 and recent[-1][3] < min(x[2] for x in recent[:-1]):
            return SetupSignal("TREND_REVERSAL", "SHORT", 0.73)
