"""Lower-fidelity 1m/5m counterfactual fallback with explicit ambiguity."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .counterfactual import EvidenceQuality, PolicyOutcome, TrailPolicy


@dataclass(frozen=True)
class OhlcBar:
    open_time_ms: int
    interval_ms: int
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self):
        if self.open_time_ms < 0 or self.interval_ms not in {60_000, 300_000}:
            raise ValueError("COARSE_BAR_TIME_INVALID")
        if not all(math.isfinite(x) and x > 0 for x in (self.open, self.high, self.low, self.close)):
            raise ValueError("COARSE_BAR_PRICE_INVALID")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.low > self.high:
            raise ValueError("COARSE_BAR_OHLC_INVALID")


def replay_coarse_bars(bars: Iterable[OhlcBar], *, side: str, entry_price: float, one_r_price: float,
                       policy: TrailPolicy) -> PolicyOutcome:
    rows = list(bars)
    if side not in {"LONG", "SHORT"} or entry_price <= 0 or one_r_price <= 0 or not rows:
        raise ValueError("COARSE_REPLAY_CONFIG_INVALID")
    interval = rows[0].interval_ms
    if any(bar.interval_ms != interval for bar in rows):
        raise ValueError("COARSE_REPLAY_INTERVAL_MIXED")
    quality = EvidenceQuality.ONE_MINUTE_RESOLVED if interval == 60_000 else EvidenceQuality.FIVE_MINUTE_UNAMBIGUOUS
    sign = 1 if side == "LONG" else -1
    stop_r = -1
    peak = 0.0
    trough = 0.0
    ambiguous = False
    exit_time = None
    exit_price = None
    reason = "HORIZON"
    expected = rows[0].open_time_ms
    for bar in rows:
        if bar.open_time_ms != expected:
            return PolicyOutcome(policy.value, EvidenceQuality.GAP_UNRESOLVED, "GAP_UNRESOLVED", None, None,
                                 None, None, peak, trough, stop_r, 0, False, "COARSE")
        expected += interval
        favorable = sign * ((bar.high if sign == 1 else bar.low) - entry_price) / one_r_price
        adverse = sign * ((bar.low if sign == 1 else bar.high) - entry_price) / one_r_price
        peak = max(peak, favorable)
        trough = min(trough, adverse)
        stop_touched = adverse <= stop_r
        if policy is TrailPolicy.TICK_INTEGER_R:
            next_trigger = stop_r + 2
            if stop_touched and favorable >= next_trigger:
                ambiguous = True
                if interval == 300_000:
                    quality = EvidenceQuality.FIVE_MINUTE_AMBIGUOUS
                break
            if stop_touched:
                exit_time = bar.open_time_ms
                exit_price = entry_price + sign * stop_r * one_r_price
                reason = "STOP"
                break
            if peak >= 1:
                stop_r = max(stop_r, math.floor(peak) - 1)
        else:
            if stop_touched:
                exit_time = bar.open_time_ms
                exit_price = entry_price + sign * stop_r * one_r_price
                reason = "STOP"
                break
            if peak >= 1:
                stop_r = max(stop_r, math.floor(peak) - 1)
    gross = None if exit_price is None else sign * (exit_price - entry_price) / one_r_price
    if ambiguous:
        gross = None
        reason = "AMBIGUOUS"
    return PolicyOutcome(policy.value, quality, reason, exit_time, exit_price, gross, gross,
                         peak, trough, stop_r, len(rows), ambiguous, "COARSE")
