"""Bias-aware V3 decision calibration helpers."""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class CalibrationRow:
    event_id: str
    decision_time_ms: int
    score_r: float
    outcome_r: float
    approved: bool
    sampling_probability: float = 1.0

    def __post_init__(self) -> None:
        if not self.event_id or self.decision_time_ms < 0 or not all(math.isfinite(x) for x in (self.score_r, self.outcome_r)):
            raise ValueError("CALIBRATION_ROW_INVALID")
        if not 0 < self.sampling_probability <= 1:
            raise ValueError("CALIBRATION_SAMPLING_INVALID")


@dataclass(frozen=True)
class ScoreBin:
    lower: float
    upper: float
    count: int
    weighted_count: float
    mean_score_r: float
    mean_outcome_r: float


def score_bins(rows: Iterable[CalibrationRow], *, boundaries: tuple[float, ...] = (-1, -.25, 0, .05, .08, .15, .3, 1)) -> tuple[ScoreBin, ...]:
    data = list(rows)
    if len(boundaries) < 2 or any(a >= b for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("CALIBRATION_BINS_INVALID")
    output = []
    for lo, hi in zip(boundaries, boundaries[1:]):
        chunk = [r for r in data if lo <= r.score_r < hi]
        if not chunk:
            continue
        weights = [1.0 / r.sampling_probability for r in chunk]
        total = sum(weights)
        output.append(ScoreBin(lo, hi, len(chunk), total,
                               sum(r.score_r*w for r,w in zip(chunk,weights))/total,
                               sum(r.outcome_r*w for r,w in zip(chunk,weights))/total))
    return tuple(output)


def chronological_split(rows: Iterable[CalibrationRow], *, train_fraction: float = .70) -> tuple[list[CalibrationRow], list[CalibrationRow]]:
    if not 0 < train_fraction < 1:
        raise ValueError("CALIBRATION_SPLIT_INVALID")
    data = sorted(rows, key=lambda r: (r.decision_time_ms, r.event_id))
    if len(data) < 2:
        raise ValueError("CALIBRATION_SPLIT_TOO_SMALL")
    cut = max(1, min(len(data)-1, int(len(data)*train_fraction)))
    return data[:cut], data[cut:]


def policy_metrics(rows: Iterable[CalibrationRow], *, threshold_r: float, edge_gap_r: float = 0.0) -> dict[str, float | int]:
    data = list(rows)
    selected = [r for r in data if r.score_r >= threshold_r + edge_gap_r]
    rejected = [r for r in data if r.score_r < threshold_r + edge_gap_r]
    by_event: dict[str, list[float]] = {}
    for r in selected:
        by_event.setdefault(r.event_id, []).append(r.outcome_r)
    event_means = [mean(v) for v in by_event.values()]
    return {
        "rows": len(data), "selected": len(selected), "rejected": len(rejected),
        "distinct_selected_events": len(event_means),
        "selected_mean_r": mean([r.outcome_r for r in selected]) if selected else 0.0,
        "event_weighted_mean_r": mean(event_means) if event_means else 0.0,
        "rejected_mean_r": mean([r.outcome_r for r in rejected]) if rejected else 0.0,
    }
