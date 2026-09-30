"""Stable mergeable moments with an explicit delayed-label training boundary.

The full aggregate supports training at the current mature-evidence cutoff.
The delayed aggregate supports historical decision-time scoring. Pending
entries contain per-event moments, not unbounded raw training examples.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import statistics

LABEL_HORIZON_MS = 48 * 300_000
STATISTICS_VERSION = "CENTERED_DELAYED_RIDGE_V2"


@dataclass
class CenteredMoments:
    dimension: int
    event_count: int = 0
    row_count: int = 0
    through_event_ms: int | None = None
    mean_y: float = 0.0
    mean_x: list[float] = field(default_factory=list)
    cross_xy: list[float] = field(default_factory=list)
    cross_xx: list[list[float]] = field(default_factory=list)

    def __post_init__(self):
        if not self.mean_x:
            self.mean_x = [0.0] * self.dimension
            self.cross_xy = [0.0] * self.dimension
            self.cross_xx = [[0.0] * self.dimension for _ in range(self.dimension)]

    @classmethod
    def event(cls, timestamp, vectors, targets):
        if not vectors or len(vectors) != len(targets):
            raise ValueError("RIDGE_EVENT_EMPTY_OR_INVALID")
        dimension = len(vectors[0])
        if any(len(row) != dimension for row in vectors):
            raise ValueError("RIDGE_DIMENSION_INVALID")
        if any(not math.isfinite(v) for row in vectors for v in row) or any(not math.isfinite(y) for y in targets):
            raise ValueError("RIDGE_NONFINITE_INPUT")
        result = cls(dimension, event_count=1, row_count=len(vectors), through_event_ms=int(timestamp))
        result.mean_x = [statistics.fmean(row[i] for row in vectors) for i in range(dimension)]
        result.mean_y = statistics.fmean(targets)
        centered = [[row[i] - result.mean_x[i] for i in range(dimension)] for row in vectors]
        result.cross_xy = [math.fsum(row[i] * (y - result.mean_y) for row, y in zip(centered, targets)) for i in range(dimension)]
        result.cross_xx = [[math.fsum(row[i] * row[j] for row in centered) for j in range(dimension)] for i in range(dimension)]
        return result

    def merge(self, other):
        if other.dimension != self.dimension or other.row_count <= 0:
            raise ValueError("RIDGE_MERGE_INVALID")
        if self.through_event_ms is not None and other.through_event_ms <= self.through_event_ms:
            raise ValueError("RIDGE_CHRONOLOGY_INVALID")
        count = self.row_count + other.row_count
        fraction = other.row_count / count
        weight = self.row_count * fraction
        dx = [b - a for a, b in zip(self.mean_x, other.mean_x)]
        dy = other.mean_y - self.mean_y
        for i in range(self.dimension):
            self.cross_xy[i] = math.fsum((self.cross_xy[i], other.cross_xy[i], dx[i] * dy * weight))
            for j in range(self.dimension):
                self.cross_xx[i][j] = math.fsum((self.cross_xx[i][j], other.cross_xx[i][j], dx[i] * dx[j] * weight))
            self.mean_x[i] += dx[i] * fraction
        self.mean_y += dy * fraction
        self.row_count = count
        self.event_count += other.event_count
        self.through_event_ms = other.through_event_ms

    def payload(self):
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def restore(cls, payload, dimension):
        obj = cls(**payload)
        if obj.dimension != dimension or len(obj.mean_x) != dimension or len(obj.cross_xy) != dimension or len(obj.cross_xx) != dimension or any(len(row) != dimension for row in obj.cross_xx):
            raise ValueError("RIDGE_DIMENSION_INVALID")
        values = [obj.mean_y, *obj.mean_x, *obj.cross_xy, *(v for row in obj.cross_xx for v in row)]
        if any(not math.isfinite(v) for v in values) or obj.row_count < 0 or obj.event_count < 0:
            raise ValueError("RIDGE_STATE_INVALID")
        if (obj.row_count == 0) != (obj.event_count == 0) or (obj.event_count == 0) != (obj.through_event_ms is None):
            raise ValueError("RIDGE_COUNTS_INVALID")
        return obj
