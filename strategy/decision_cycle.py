"""Five-minute decision-cycle coordination independent of paper exposure."""

from __future__ import annotations

import math
import time
from collections import defaultdict


class FiveMinuteDecisionCycleCoordinator:
    """Wait for broad symbol rollover, then release each candle bucket once."""

    _MISSING_SYMBOL_SAMPLE_LIMIT = 20
    _LATE_ROLLOVER_SAMPLE_LIMIT = 20

    def __init__(
        self,
        *,
        minimum_coverage: float,
        settle_seconds: float,
    ):
        self.minimum_coverage = float(minimum_coverage)
        self.settle_seconds = float(settle_seconds)
        if not (0.50 <= self.minimum_coverage <= 1.0):
            raise ValueError("DECISION_CYCLE_COVERAGE_INVALID")
        if not (0.0 <= self.settle_seconds <= 60.0):
            raise ValueError("DECISION_CYCLE_SETTLE_SECONDS_INVALID")
        self._symbols: set[str] = set()
        self._execution_symbols: set[str] = set()
        self._rollovers: dict[int, set[str]] = defaultdict(set)
        self._first_seen: dict[int, float] = {}
        self._processed: set[int] = set()

        # Phase 6B.2.2 diagnostics. A symbol that is absent when a broad
        # cycle releases may simply be quiet on Binance's changed-ticker
        # stream. Retain a small recent window so later natural rollovers can
        # be measured without changing cycle timing or candle construction.
        self._release_monotonic: dict[int, float] = {}
        self._release_missing: dict[int, set[str]] = {}
        self._latest_release: dict = {}
        self._late_rollover_events = 0
        self._late_rollover_by_symbol: dict[str, dict] = {}

    def set_symbols(self, symbols, *, execution_symbols=None) -> None:
        normalized = {str(symbol).strip().upper() for symbol in symbols}
        normalized.discard("")
        if not normalized:
            raise ValueError("DECISION_CYCLE_SYMBOLS_EMPTY")

        if execution_symbols is None:
            execution = set(normalized)
        else:
            execution = {
                str(symbol).strip().upper()
                for symbol in execution_symbols
                if str(symbol).strip()
            }
            if not execution:
                raise ValueError("DECISION_CYCLE_EXECUTION_SYMBOLS_EMPTY")
            if not execution.issubset(normalized):
                raise ValueError(
                    "DECISION_CYCLE_EXECUTION_NOT_SUBSET_OF_SYMBOLS"
                )

        self._symbols = normalized
        self._execution_symbols = execution
        self._late_rollover_by_symbol = {
            symbol: row
            for symbol, row in self._late_rollover_by_symbol.items()
            if symbol in normalized
        }

    def mark_rollover(
        self,
        *,
        symbol: str,
        new_bucket: int,
        now_monotonic: float | None = None,
    ) -> None:
        symbol = str(symbol).strip().upper()
        bucket = int(new_bucket)
        if symbol not in self._symbols:
            return
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)

        if bucket in self._processed:
            pending = self._release_missing.get(bucket)
            released_at = self._release_monotonic.get(bucket)
            if pending is not None and symbol in pending and released_at is not None:
                delay = max(0.0, now - float(released_at))
                pending.discard(symbol)
                self._late_rollover_events += 1
                row = dict(self._late_rollover_by_symbol.get(symbol) or {})
                count = int(row.get("late_rollover_count", 0) or 0) + 1
                previous_max = float(row.get("max_delay_seconds", 0.0) or 0.0)
                self._late_rollover_by_symbol[symbol] = {
                    "symbol": symbol,
                    "late_rollover_count": count,
                    "latest_delay_seconds": delay,
                    "max_delay_seconds": max(previous_max, delay),
                    "latest_bucket": bucket,
                    "execution_eligible": symbol in self._execution_symbols,
                }
            return

        self._rollovers[bucket].add(symbol)
        self._first_seen.setdefault(bucket, now)

    def ready_buckets(
        self,
        *,
        now_monotonic: float | None = None,
    ) -> list[dict]:
        if not self._symbols:
            return []
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        total = len(self._symbols)
        minimum = max(1, math.ceil(total * self.minimum_coverage))
        execution_total = len(self._execution_symbols)
        ready = []
        for bucket in sorted(self._rollovers):
            if bucket in self._processed:
                continue
            completed_symbols = self._rollovers[bucket] & self._symbols
            count = len(completed_symbols)
            age = max(0.0, now - self._first_seen[bucket])
            complete = count >= total
            settled = count >= minimum and age >= self.settle_seconds
            if not (complete or settled):
                continue

            missing_symbols = self._symbols - completed_symbols
            missing_execution = missing_symbols & self._execution_symbols
            missing_observation_only = (
                missing_symbols - self._execution_symbols
            )
            execution_completed = (
                self._execution_symbols & completed_symbols
            )

            # Record the exact release state once. This is diagnostic state
            # only; processing semantics remain unchanged.
            released_at = self._release_monotonic.setdefault(bucket, now)
            self._release_missing.setdefault(bucket, set(missing_symbols))
            self._latest_release = {
                "candle_bucket": bucket,
                "released_monotonic": released_at,
                "missing_symbols_count": len(missing_symbols),
                "missing_execution_symbols_count": len(missing_execution),
                "missing_observation_only_symbols_count": len(
                    missing_observation_only
                ),
            }

            sorted_missing = sorted(missing_symbols)
            sorted_missing_execution = sorted(missing_execution)
            sorted_missing_observation_only = sorted(
                missing_observation_only
            )
            ready.append(
                {
                    "candle_bucket": bucket,
                    "symbols_completed": count,
                    "symbols_expected": total,
                    "coverage": count / total,
                    "settled_seconds": age,
                    "missing_symbols_count": len(sorted_missing),
                    "missing_symbols_sample": sorted_missing[
                        : self._MISSING_SYMBOL_SAMPLE_LIMIT
                    ],
                    "execution_symbols_completed": len(execution_completed),
                    "execution_symbols_expected": execution_total,
                    "execution_coverage": (
                        len(execution_completed) / execution_total
                        if execution_total
                        else 0.0
                    ),
                    "missing_execution_symbols_count": len(
                        sorted_missing_execution
                    ),
                    "missing_execution_symbols_sample": (
                        sorted_missing_execution[
                            : self._MISSING_SYMBOL_SAMPLE_LIMIT
                        ]
                    ),
                    "missing_observation_only_symbols_count": len(
                        sorted_missing_observation_only
                    ),
                    "missing_observation_only_symbols_sample": (
                        sorted_missing_observation_only[
                            : self._MISSING_SYMBOL_SAMPLE_LIMIT
                        ]
                    ),
                }
            )
        return ready

    def mark_processed(self, bucket: int) -> None:
        bucket = int(bucket)
        self._processed.add(bucket)
        self._rollovers.pop(bucket, None)
        self._first_seen.pop(bucket, None)
        # Bound memory in long-running processes.
        floor = bucket - 12
        self._processed = {item for item in self._processed if item >= floor}
        for old_bucket in list(self._rollovers):
            if old_bucket < floor:
                self._rollovers.pop(old_bucket, None)
                self._first_seen.pop(old_bucket, None)
        for old_bucket in list(self._release_missing):
            if old_bucket < floor:
                self._release_missing.pop(old_bucket, None)
                self._release_monotonic.pop(old_bucket, None)

    def integrity_snapshot(self) -> dict:
        """Return bounded late-rollover diagnostics without changing state."""
        try:
            pending = sum(len(rows) for rows in self._release_missing.values())
            ranked = sorted(
                (dict(row) for row in self._late_rollover_by_symbol.values()),
                key=lambda row: (
                    -int(row.get("late_rollover_count", 0) or 0),
                    -float(row.get("max_delay_seconds", 0.0) or 0.0),
                    str(row.get("symbol") or ""),
                ),
            )
            latest = dict(self._latest_release)
            if latest:
                latest_bucket = int(latest.get("candle_bucket", 0) or 0)
                latest["pending_late_rollovers_count"] = len(
                    self._release_missing.get(latest_bucket, set())
                )
            return {
                "late_rollover_events": self._late_rollover_events,
                "late_rollover_symbols_count": len(
                    self._late_rollover_by_symbol
                ),
                "pending_late_rollovers_count": pending,
                "late_rollover_symbols_sample": ranked[
                    : self._LATE_ROLLOVER_SAMPLE_LIMIT
                ],
                "latest_cycle_release": latest,
            }
        except Exception:
            return {}
