"""Low-overhead execution hot-path instrumentation for Phase 6A.

The monitor is observational only.  It must never influence trading decisions,
raise into the execution path, or persist trading state.
"""

from __future__ import annotations

import math
import time
from collections import deque


class _TimingSeries:
    def __init__(self, *, sample_limit: int = 2048):
        self.count = 0
        self.total = 0.0
        self.maximum = 0.0
        self.samples = deque(maxlen=int(sample_limit))

    def add(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value) or value < 0:
            return
        self.count += 1
        self.total += value
        self.maximum = max(self.maximum, value)
        self.samples.append(value)

    def average(self) -> float:
        return self.total / self.count if self.count else 0.0

    def p95(self) -> float:
        if not self.samples:
            return 0.0
        ordered = sorted(self.samples)
        index = max(0, math.ceil(0.95 * len(ordered)) - 1)
        return float(ordered[index])


class ExecutionHealthMonitor:
    """Aggregate execution timings and emit one compact periodic summary."""

    _COUNTERS = (
        "control_cycles",
        "total_ticks",
        "open_position_ticks",
        "position_symbol_ticks",
        "irrelevant_open_ticks",
        "position_rest_fallback_success",
        "position_rest_fallback_failure",
        "position_ws_disconnects",
        "sl_update_attempts",
    )

    _TIMINGS = (
        "internal_tick_age_ms",
        "position_manage_ms",
        "exchange_get_position_ms",
        "bot_state_save_ms",
        "paper_state_save_ms",
        "position_rest_fallback_ms",
        "sl_update_ms",
        "sl_verify_ms",
        "sl_roundtrip_ms",
    )

    def __init__(self, *, system_log, interval_seconds: float = 60.0):
        interval = float(interval_seconds)
        if not math.isfinite(interval) or interval < 5.0:
            raise ValueError("EXECUTION_HEALTH_INTERVAL_INVALID")
        self.system_log = system_log
        self.interval_seconds = interval
        self._period_started = time.monotonic()
        self._last_log = self._period_started
        self._counters = {}
        self._timings = {}
        self._reset_period()

    def increment(self, name: str, amount: int = 1) -> None:
        try:
            if name not in self._counters:
                return
            self._counters[name] += int(amount)
        except Exception:
            return

    def observe_ms(self, name: str, value_ms: float) -> None:
        try:
            series = self._timings.get(name)
            if series is not None:
                series.add(float(value_ms))
        except Exception:
            return

    def maybe_log(self, *, position_symbol: str | None = None) -> None:
        """Emit at most once per interval; instrumentation failures are ignored."""
        try:
            now = time.monotonic()
            if now - self._last_log < self.interval_seconds:
                return

            period_seconds = max(0.0, now - self._period_started)
            fields = [
                "EXECUTION_HEALTH",
                f"period_seconds={period_seconds:.3f}",
                f"position_symbol={position_symbol or 'FLAT'}",
            ]

            for name in self._COUNTERS:
                fields.append(f"{name}={self._counters[name]}")

            for name in self._TIMINGS:
                series = self._timings[name]
                fields.extend(
                    (
                        f"{name}_count={series.count}",
                        f"{name}_avg={series.average():.3f}",
                        f"{name}_p95={series.p95():.3f}",
                        f"{name}_max={series.maximum:.3f}",
                    )
                )

            self.system_log.info(" | ".join(fields))
            self._last_log = now
            self._period_started = now
            self._reset_period()
        except Exception:
            return

    def _reset_period(self) -> None:
        self._counters = {name: 0 for name in self._COUNTERS}
        self._timings = {name: _TimingSeries() for name in self._TIMINGS}
