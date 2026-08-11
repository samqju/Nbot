"""Low-overhead Observation Worker instrumentation for Phase 6B.

The monitor is observational only. It must never influence recommendation
readiness, candidate selection, learning decisions, or execution authority.
Metrics are retained in memory and exposed only on demand.
"""

from __future__ import annotations

import os
import threading
import time


class ObservationHealthMonitor:
    """Retain bounded realtime Observation diagnostics in memory."""

    _COUNTERS = (
        "total_ticks",
        "selected_universe_ticks",
        "decision_cycles",
        "candidates_seen",
    )
    _TICK_FRESH_SECONDS = 5.0
    _TICK_STALE_SECONDS = 30.0
    _SYMBOL_SAMPLE_LIMIT = 20

    def __init__(self):
        self._started_monotonic = time.monotonic()
        self._last_activity_monotonic = self._started_monotonic
        self._last_decision_monotonic = None
        self._lock = threading.Lock()
        self._counters = {name: 0 for name in self._COUNTERS}
        self._execution_symbols: set[str] = set()
        self._observation_symbols: set[str] = set()
        self._observation_target_count = 0
        self._last_tick_monotonic: dict[str, float] = {}
        self._latest_cycle: dict = {}
        self._sample_monotonic = self._started_monotonic
        self._sample_cpu_seconds = time.process_time()
        self._sample_counters = dict(self._counters)
        self._peak_cpu_utilization_percent = 0.0

    def set_universes(
        self,
        *,
        execution_symbols,
        observation_symbols,
        observation_target_count: int,
    ) -> None:
        """Update current selected universes without resetting runtime counters."""
        try:
            execution = {
                str(symbol).strip().upper()
                for symbol in execution_symbols
                if str(symbol).strip()
            }
            observation = {
                str(symbol).strip().upper()
                for symbol in observation_symbols
                if str(symbol).strip()
            }
            target = max(0, int(observation_target_count))
            with self._lock:
                self._execution_symbols = execution
                self._observation_symbols = observation
                self._observation_target_count = target
                self._last_tick_monotonic = {
                    symbol: seen_at
                    for symbol, seen_at in self._last_tick_monotonic.items()
                    if symbol in observation
                }
        except Exception:
            return

    def record_tick(
        self,
        symbol: str,
        *,
        now_monotonic: float | None = None,
    ) -> None:
        """Record one incoming public-market tick."""
        try:
            symbol = str(symbol or "").strip().upper()
            now = (
                time.monotonic()
                if now_monotonic is None
                else float(now_monotonic)
            )
            with self._lock:
                self._counters["total_ticks"] += 1
                self._last_activity_monotonic = now
                if symbol in self._observation_symbols:
                    self._counters["selected_universe_ticks"] += 1
                    self._last_tick_monotonic[symbol] = now
        except Exception:
            return

    def record_decision_cycles(self, rows) -> None:
        """Record already-computed decision-cycle results."""
        try:
            if not rows:
                return
            now = time.monotonic()
            with self._lock:
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    self._counters["decision_cycles"] += 1
                    try:
                        candidates = max(
                            0,
                            int(row.get("candidate_count", 0) or 0),
                        )
                    except (TypeError, ValueError):
                        candidates = 0
                    self._counters["candidates_seen"] += candidates

                    coverage = row.get("cycle_coverage")
                    if not isinstance(coverage, dict):
                        coverage = {}

                    missing_sample = coverage.get("missing_symbols_sample")
                    if not isinstance(missing_sample, (list, tuple)):
                        missing_sample = []
                    missing_sample = [
                        str(symbol).strip().upper()
                        for symbol in missing_sample
                        if str(symbol).strip()
                    ][: self._SYMBOL_SAMPLE_LIMIT]

                    self._latest_cycle = {
                        "candle_bucket": int(
                            row.get("candle_bucket", 0) or 0
                        ),
                        "decision_batch_id": (
                            row.get("decision_batch_id")
                        ),
                        "candidate_count": candidates,
                        "symbols_completed": int(
                            coverage.get("symbols_completed", 0) or 0
                        ),
                        "symbols_expected": int(
                            coverage.get("symbols_expected", 0) or 0
                        ),
                        "coverage": float(
                            coverage.get("coverage", 0.0) or 0.0
                        ),
                        "settled_seconds": float(
                            coverage.get("settled_seconds", 0.0) or 0.0
                        ),
                        "missing_symbols_count": int(
                            coverage.get("missing_symbols_count", 0) or 0
                        ),
                        "missing_symbols_sample": missing_sample,
                        "execution_symbols_completed": int(
                            coverage.get(
                                "execution_symbols_completed", 0
                            ) or 0
                        ),
                        "execution_symbols_expected": int(
                            coverage.get(
                                "execution_symbols_expected", 0
                            ) or 0
                        ),
                        "execution_coverage": float(
                            coverage.get("execution_coverage", 0.0) or 0.0
                        ),
                        "missing_execution_symbols_count": int(
                            coverage.get(
                                "missing_execution_symbols_count", 0
                            ) or 0
                        ),
                        "missing_execution_symbols_sample": [
                            str(symbol).strip().upper()
                            for symbol in (
                                coverage.get(
                                    "missing_execution_symbols_sample", []
                                ) or []
                            )
                            if str(symbol).strip()
                        ][: self._SYMBOL_SAMPLE_LIMIT],
                        "missing_observation_only_symbols_count": int(
                            coverage.get(
                                "missing_observation_only_symbols_count", 0
                            ) or 0
                        ),
                        "missing_observation_only_symbols_sample": [
                            str(symbol).strip().upper()
                            for symbol in (
                                coverage.get(
                                    "missing_observation_only_symbols_sample",
                                    [],
                                ) or []
                            )
                            if str(symbol).strip()
                        ][: self._SYMBOL_SAMPLE_LIMIT],
                    }
                    self._last_decision_monotonic = now
                self._last_activity_monotonic = now
        except Exception:
            return

    def snapshot(
        self,
        *,
        virtual_metrics: dict | None = None,
        recommendation: dict | None = None,
        transport_metrics: dict | None = None,
        candle_metrics: dict | None = None,
        scale_metrics: dict | None = None,
        now_monotonic: float | None = None,
    ) -> dict:
        """Return a read-only diagnostic snapshot."""
        try:
            now = (
                time.monotonic()
                if now_monotonic is None
                else float(now_monotonic)
            )
            with self._lock:
                seen = (
                    set(self._last_tick_monotonic)
                    & self._observation_symbols
                )
                unseen = sorted(self._observation_symbols - seen)
                ages = {
                    symbol: max(
                        0.0,
                        now - self._last_tick_monotonic[symbol],
                    )
                    for symbol in seen
                }
                fresh = sorted(
                    symbol
                    for symbol, age in ages.items()
                    if age <= self._TICK_FRESH_SECONDS
                )
                delayed = sorted(
                    symbol
                    for symbol, age in ages.items()
                    if (
                        self._TICK_FRESH_SECONDS
                        < age
                        <= self._TICK_STALE_SECONDS
                    )
                )
                stale = sorted(
                    symbol
                    for symbol, age in ages.items()
                    if age > self._TICK_STALE_SECONDS
                )
                stale_by_age = sorted(
                    stale,
                    key=lambda symbol: ages[symbol],
                    reverse=True,
                )
                delayed_by_age = sorted(
                    delayed,
                    key=lambda symbol: ages[symbol],
                    reverse=True,
                )
                execution_seen = seen & self._execution_symbols
                execution_unseen = sorted(
                    self._execution_symbols - execution_seen
                )
                execution_fresh = sorted(
                    set(fresh) & self._execution_symbols
                )
                execution_delayed = sorted(
                    set(delayed) & self._execution_symbols
                )
                execution_stale = sorted(
                    set(stale) & self._execution_symbols
                )
                latest_cycle = dict(self._latest_cycle)
                cpu_seconds = max(0.0, time.process_time())
                sample_window = max(0.0, now - self._sample_monotonic)
                cpu_utilization_percent = 0.0
                rates = {
                    "window_seconds": sample_window,
                    "total_ticks_per_second": 0.0,
                    "selected_universe_ticks_per_second": 0.0,
                    "candidates_per_minute": 0.0,
                    "decision_cycles_per_minute": 0.0,
                }
                if sample_window > 0.0:
                    cpu_delta = max(
                        0.0,
                        cpu_seconds - self._sample_cpu_seconds,
                    )
                    cpu_utilization_percent = (
                        cpu_delta / sample_window
                    ) * 100.0
                    for name, rate_name, multiplier in (
                        ("total_ticks", "total_ticks_per_second", 1.0),
                        (
                            "selected_universe_ticks",
                            "selected_universe_ticks_per_second",
                            1.0,
                        ),
                        ("candidates_seen", "candidates_per_minute", 60.0),
                        (
                            "decision_cycles",
                            "decision_cycles_per_minute",
                            60.0,
                        ),
                    ):
                        delta = max(
                            0,
                            int(self._counters.get(name, 0) or 0)
                            - int(self._sample_counters.get(name, 0) or 0),
                        )
                        rates[rate_name] = (
                            delta / sample_window
                        ) * multiplier
                    self._sample_monotonic = now
                    self._sample_cpu_seconds = cpu_seconds
                    self._sample_counters = dict(self._counters)
                    self._peak_cpu_utilization_percent = max(
                        self._peak_cpu_utilization_percent,
                        cpu_utilization_percent,
                    )
                cpu_count = max(1, int(os.cpu_count() or 1))
                decision_age = (
                    None
                    if self._last_decision_monotonic is None
                    else max(
                        0.0,
                        now - self._last_decision_monotonic,
                    )
                )
                result = {
                    "uptime_seconds": max(
                        0.0,
                        now - self._started_monotonic,
                    ),
                    "activity_age_seconds": max(
                        0.0,
                        now - self._last_activity_monotonic,
                    ),
                    "process": {
                        "cpu_seconds": cpu_seconds,
                        "cpu_utilization_percent": cpu_utilization_percent,
                        "cpu_capacity_percent": (
                            cpu_utilization_percent / cpu_count
                        ),
                        "peak_cpu_utilization_percent": (
                            self._peak_cpu_utilization_percent
                        ),
                        "cpu_count": cpu_count,
                        "rss_mb": self._current_rss_mb(),
                        "peak_rss_mb": self._peak_rss_mb(),
                    },
                    "rates": rates,
                    "counters": dict(self._counters),
                    "universe": {
                        "execution_symbol_count": len(
                            self._execution_symbols
                        ),
                        "execution_symbols_seen": len(execution_seen),
                        "execution_symbols_unseen": len(execution_unseen),
                        "execution_symbols_fresh": len(execution_fresh),
                        "execution_symbols_delayed": len(execution_delayed),
                        "execution_symbols_stale": len(execution_stale),
                        "execution_unseen_symbols_sample": execution_unseen[
                            : self._SYMBOL_SAMPLE_LIMIT
                        ],
                        "execution_delayed_symbols_sample": (
                            execution_delayed[: self._SYMBOL_SAMPLE_LIMIT]
                        ),
                        "execution_stale_symbols_sample": (
                            execution_stale[: self._SYMBOL_SAMPLE_LIMIT]
                        ),
                        "observation_symbol_count": len(
                            self._observation_symbols
                        ),
                        "observation_target_count": (
                            self._observation_target_count
                        ),
                        "symbols_seen": len(seen),
                        "symbols_unseen": len(unseen),
                        "symbols_fresh": len(fresh),
                        "symbols_delayed": len(delayed),
                        "symbols_stale": len(stale),
                        "tick_fresh_seconds": self._TICK_FRESH_SECONDS,
                        "tick_stale_seconds": self._TICK_STALE_SECONDS,
                        "ticker_stream_semantics": "CHANGED_TICKERS_ONLY",
                        "symbol_silence_interpretation": (
                            "QUIET_OR_STALE_REQUIRES_TRANSPORT_CONTEXT"
                        ),
                        "newest_tick_age_seconds": (
                            min(ages.values()) if ages else None
                        ),
                        "oldest_tick_age_seconds": (
                            max(ages.values()) if ages else None
                        ),
                        "unseen_symbols_sample": unseen[
                            : self._SYMBOL_SAMPLE_LIMIT
                        ],
                        "delayed_symbols_sample": [
                            {
                                "symbol": symbol,
                                "age_seconds": ages[symbol],
                            }
                            for symbol in delayed_by_age[
                                : self._SYMBOL_SAMPLE_LIMIT
                            ]
                        ],
                        "stale_symbols_sample": [
                            {
                                "symbol": symbol,
                                "age_seconds": ages[symbol],
                            }
                            for symbol in stale_by_age[
                                : self._SYMBOL_SAMPLE_LIMIT
                            ]
                        ],
                    },
                    "market_data": {
                        "transport": dict(transport_metrics or {}),
                        "candles": dict(candle_metrics or {}),
                    },
                    "latest_decision_cycle": latest_cycle,
                    "latest_decision_age_seconds": decision_age,
                    "virtual": dict(virtual_metrics or {}),
                    "recommendation": dict(recommendation or {}),
                    "scale": dict(scale_metrics or {}),
                }
                return result
        except Exception:
            return {
                "uptime_seconds": 0.0,
                "activity_age_seconds": 0.0,
                "process": {
                    "cpu_seconds": 0.0,
                    "cpu_utilization_percent": 0.0,
                    "cpu_capacity_percent": 0.0,
                    "peak_cpu_utilization_percent": 0.0,
                    "cpu_count": max(1, int(os.cpu_count() or 1)),
                    "rss_mb": 0.0,
                    "peak_rss_mb": 0.0,
                },
                "rates": {
                    "window_seconds": 0.0,
                    "total_ticks_per_second": 0.0,
                    "selected_universe_ticks_per_second": 0.0,
                    "candidates_per_minute": 0.0,
                    "decision_cycles_per_minute": 0.0,
                },
                "counters": {
                    name: 0 for name in self._COUNTERS
                },
                "universe": {
                    "execution_symbol_count": 0,
                    "execution_symbols_seen": 0,
                    "execution_symbols_unseen": 0,
                    "execution_symbols_fresh": 0,
                    "execution_symbols_delayed": 0,
                    "execution_symbols_stale": 0,
                    "execution_unseen_symbols_sample": [],
                    "execution_delayed_symbols_sample": [],
                    "execution_stale_symbols_sample": [],
                    "observation_symbol_count": 0,
                    "observation_target_count": 0,
                    "symbols_seen": 0,
                    "symbols_unseen": 0,
                    "symbols_fresh": 0,
                    "symbols_delayed": 0,
                    "symbols_stale": 0,
                    "tick_fresh_seconds": self._TICK_FRESH_SECONDS,
                    "tick_stale_seconds": self._TICK_STALE_SECONDS,
                    "ticker_stream_semantics": "CHANGED_TICKERS_ONLY",
                    "symbol_silence_interpretation": (
                        "QUIET_OR_STALE_REQUIRES_TRANSPORT_CONTEXT"
                    ),
                    "newest_tick_age_seconds": None,
                    "oldest_tick_age_seconds": None,
                    "unseen_symbols_sample": [],
                    "delayed_symbols_sample": [],
                    "stale_symbols_sample": [],
                },
                "market_data": {
                    "transport": dict(transport_metrics or {}),
                    "candles": dict(candle_metrics or {}),
                },
                "latest_decision_cycle": {},
                "latest_decision_age_seconds": None,
                "virtual": dict(virtual_metrics or {}),
                "recommendation": dict(recommendation or {}),
                "scale": dict(scale_metrics or {}),
            }

    @staticmethod
    def _current_rss_mb() -> float:
        """Read current resident memory on Linux; return zero on failure."""
        try:
            with open("/proc/self/statm", "r", encoding="utf-8") as handle:
                resident_pages = int(handle.read().split()[1])
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            return (
                resident_pages * page_size
            ) / (1024.0 * 1024.0)
        except Exception:
            return 0.0

    @staticmethod
    def _peak_rss_mb() -> float:
        """Read Linux resident high-water mark; return zero on failure."""
        try:
            with open(
                "/proc/self/status",
                "r",
                encoding="utf-8",
            ) as handle:
                for line in handle:
                    if line.startswith("VmHWM:"):
                        return float(line.split()[1]) / 1024.0
        except Exception:
            return 0.0
        return 0.0
