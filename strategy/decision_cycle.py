"""Five-minute decision-cycle coordination independent of paper exposure."""

from __future__ import annotations

import math
import time
from collections import defaultdict


class FiveMinuteDecisionCycleCoordinator:
    """Wait for broad symbol rollover, then release each candle bucket once."""

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
        self._rollovers: dict[int, set[str]] = defaultdict(set)
        self._first_seen: dict[int, float] = {}
        self._processed: set[int] = set()

    def set_symbols(self, symbols) -> None:
        normalized = {str(symbol).strip().upper() for symbol in symbols}
        normalized.discard("")
        if not normalized:
            raise ValueError("DECISION_CYCLE_SYMBOLS_EMPTY")
        self._symbols = normalized

    def mark_rollover(
        self,
        *,
        symbol: str,
        new_bucket: int,
        now_monotonic: float | None = None,
    ) -> None:
        symbol = str(symbol).strip().upper()
        bucket = int(new_bucket)
        if symbol not in self._symbols or bucket in self._processed:
            return
        self._rollovers[bucket].add(symbol)
        self._first_seen.setdefault(
            bucket,
            time.monotonic() if now_monotonic is None else float(now_monotonic),
        )

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
        ready = []
        for bucket in sorted(self._rollovers):
            if bucket in self._processed:
                continue
            count = len(self._rollovers[bucket] & self._symbols)
            age = max(0.0, now - self._first_seen[bucket])
            complete = count >= total
            settled = count >= minimum and age >= self.settle_seconds
            if not (complete or settled):
                continue
            ready.append(
                {
                    "candle_bucket": bucket,
                    "symbols_completed": count,
                    "symbols_expected": total,
                    "coverage": count / total,
                    "settled_seconds": age,
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
