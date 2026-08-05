"""Versioned candidate feature extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Sequence

import numpy as np


CANDIDATE_FEATURE_SCHEMA_VERSION = 3
CANDIDATE_FEATURE_NAMES = (
    "short_range",
    "long_range",
    "trend_score",
    "wick_ratio_recent",
    "body_ratio_recent",
    "range_acceleration",
    "dist_high",
    "dist_low",
    "directional_consistency",
)


@dataclass(frozen=True)
class CandidateFeatures:
    short_range: float
    long_range: float
    trend_score: float
    wick_ratio_recent: float
    body_ratio_recent: float
    range_acceleration: float
    dist_high: float
    dist_low: float
    directional_consistency: float

    def as_dict(self) -> dict:
        return {
            key: float(value)
            for key, value in asdict(self).items()
        }

    def as_numpy(self) -> np.ndarray:
        return np.array(
            [getattr(self, name) for name in CANDIDATE_FEATURE_NAMES],
            dtype=float,
        ).reshape(1, -1)


class CandidateFeatureExtractor:
    """Extract the existing nine strategy features deterministically."""

    def __init__(self, strategy):
        self.strategy = strategy

    def extract(self, candles: Sequence[tuple]) -> CandidateFeatures:
        s = self.strategy
        c = list(candles)
        if len(c) < 20:
            raise ValueError("FEATURE_HISTORY_INSUFFICIENT")

        last_close = float(c[-1][3])
        if last_close <= 0:
            raise ValueError("FEATURE_LAST_CLOSE_INVALID")

        short_range_abs = s._avg_range(candles, s.SHORT_WINDOW)
        long_range_abs = s._avg_range(candles, s.LONG_WINDOW)
        trend_score = s._trend_score(candles)

        recent = c[-5:]
        wick_ratios = []
        body_ratios = []
        for o, h, l, cl in recent:
            total = float(h) - float(l)
            if total <= 0:
                continue
            body = abs(float(cl) - float(o))
            wick = total - body
            wick_ratios.append(wick / total)
            body_ratios.append(body / total)

        short_range = (
            float(short_range_abs) / last_close
            if short_range_abs is not None else 0.0
        )
        long_range = (
            float(long_range_abs) / last_close
            if long_range_abs is not None else 0.0
        )
        range_acceleration = (
            float(short_range_abs) / float(long_range_abs)
            if short_range_abs and long_range_abs and long_range_abs > 0
            else 0.0
        )

        highs_20 = [float(row[1]) for row in c[-20:]]
        lows_20 = [float(row[2]) for row in c[-20:]]
        dist_high = (last_close - max(highs_20)) / last_close
        dist_low = (last_close - min(lows_20)) / last_close

        closes = [float(row[3]) for row in c[-6:]]
        up_moves = sum(
            1 for idx in range(1, len(closes))
            if closes[idx] > closes[idx - 1]
        )
        down_moves = sum(
            1 for idx in range(1, len(closes))
            if closes[idx] < closes[idx - 1]
        )

        return CandidateFeatures(
            short_range=short_range,
            long_range=long_range,
            trend_score=float(trend_score),
            wick_ratio_recent=(
                sum(wick_ratios) / len(wick_ratios)
                if wick_ratios else 0.0
            ),
            body_ratio_recent=(
                sum(body_ratios) / len(body_ratios)
                if body_ratios else 0.0
            ),
            range_acceleration=range_acceleration,
            dist_high=dist_high,
            dist_low=dist_low,
            directional_consistency=float(max(up_moves, down_moves)),
        )
