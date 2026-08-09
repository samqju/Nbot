"""Low-overhead execution hot-path instrumentation for Phase 6A.

The monitor is observational only. It must never influence trading decisions,
raise into the execution path, or persist trading state. Metrics are retained
in memory and exposed on demand to the operator; normal operation does not
periodically write execution-health telemetry to ``system.txt``.
"""

from __future__ import annotations

import math
import threading
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

    def snapshot(self) -> dict[str, float | int]:
        return {
            "count": int(self.count),
            "avg": float(self.average()),
            "p95": float(self.p95()),
            "max": float(self.maximum),
        }


class ExecutionHealthMonitor:
    """Retain bounded execution diagnostics for on-demand operator queries."""

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

    def __init__(self, *, system_log=None, interval_seconds: float | None = None):
        # ``interval_seconds`` remains accepted for compatibility with older
        # tests/callers, but periodic logging is intentionally disabled.
        if interval_seconds is not None:
            interval = float(interval_seconds)
            if not math.isfinite(interval) or interval < 5.0:
                raise ValueError("EXECUTION_HEALTH_INTERVAL_INVALID")
        self.system_log = system_log
        self._started_monotonic = time.monotonic()
        self._last_activity_monotonic = self._started_monotonic
        self._lock = threading.Lock()
        self._counters = {name: 0 for name in self._COUNTERS}
        self._timings = {name: _TimingSeries() for name in self._TIMINGS}

    def increment(self, name: str, amount: int = 1) -> None:
        try:
            if name not in self._counters:
                return
            with self._lock:
                self._counters[name] += int(amount)
                if name in {"control_cycles", "total_ticks"}:
                    self._last_activity_monotonic = time.monotonic()
        except Exception:
            return

    def observe_ms(self, name: str, value_ms: float) -> None:
        try:
            with self._lock:
                series = self._timings.get(name)
                if series is not None:
                    series.add(float(value_ms))
        except Exception:
            return

    def snapshot(self, *, position_symbol: str | None = None) -> dict:
        """Return an in-memory diagnostic snapshot without logging or I/O."""
        try:
            now = time.monotonic()
            with self._lock:
                return {
                    "uptime_seconds": max(0.0, now - self._started_monotonic),
                    "activity_age_seconds": max(
                        0.0,
                        now - self._last_activity_monotonic,
                    ),
                    "position_symbol": position_symbol or "FLAT",
                    "counters": dict(self._counters),
                    "timings": {
                        name: series.snapshot()
                        for name, series in self._timings.items()
                    },
                }
        except Exception:
            return {
                "uptime_seconds": 0.0,
                "activity_age_seconds": 0.0,
                "position_symbol": position_symbol or "FLAT",
                "counters": {name: 0 for name in self._COUNTERS},
                "timings": {
                    name: {"count": 0, "avg": 0.0, "p95": 0.0, "max": 0.0}
                    for name in self._TIMINGS
                },
            }

    def maybe_log(self, *, position_symbol: str | None = None) -> None:
        """Backward-compatible no-op: health is operator-requested only."""
        return None
