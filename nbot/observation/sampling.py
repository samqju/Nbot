"""Deterministic, bias-aware candidate sampling for V3 counterfactual research."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable


@dataclass(frozen=True)
class SamplingCandidate:
    decision_id: str
    event_id: str
    symbol: str
    side: str
    setup_id: str
    conservative_score_r: float
    threshold_r: float
    ridge_score_r: float | None = None
    ml_score_r: float | None = None
    volatility_bucket: str = "UNKNOWN"

    def __post_init__(self) -> None:
        if not all((self.decision_id, self.event_id, self.symbol, self.setup_id)):
            raise ValueError("SAMPLING_IDENTITY_INVALID")
        if self.side not in {"LONG", "SHORT"}:
            raise ValueError("SAMPLING_SIDE_INVALID")
        vals = (self.conservative_score_r, self.threshold_r, self.ridge_score_r, self.ml_score_r)
        if any(v is not None and not math.isfinite(v) for v in vals):
            raise ValueError("SAMPLING_SCORE_INVALID")

    @property
    def near_threshold(self) -> bool:
        return abs(self.conservative_score_r - self.threshold_r) <= 0.03

    @property
    def model_disagreement(self) -> bool:
        return self.ridge_score_r is not None and self.ml_score_r is not None and (
            (self.ridge_score_r >= self.threshold_r) != (self.ml_score_r >= self.threshold_r)
        )


def _stable_rank(seed: str, decision_id: str) -> int:
    return int(hashlib.sha256(f"{seed}:{decision_id}".encode()).hexdigest(), 16)


def stratified_sample(candidates: Iterable[SamplingCandidate], *, capacity: int | None,
                      seed: str = "NBOT_V3") -> dict[str, float]:
    """Return sampled decision IDs -> recorded inclusion probability."""
    rows = list(candidates)
    if capacity is None or capacity >= len(rows):
        return {r.decision_id: 1.0 for r in rows}
    if capacity <= 0:
        return {}
    selected: dict[str, float] = {}
    strata = [
        [r for r in rows if r.model_disagreement],
        [r for r in rows if r.near_threshold],
    ]
    by_setup: dict[str, list[SamplingCandidate]] = {}
    by_vol: dict[str, list[SamplingCandidate]] = {}
    for row in rows:
        by_setup.setdefault(row.setup_id, []).append(row)
        by_vol.setdefault(row.volatility_bucket, []).append(row)
    strata.extend(by_setup.values())
    strata.extend(by_vol.values())
    for group in strata:
        if len(selected) >= capacity:
            break
        remaining = [r for r in group if r.decision_id not in selected]
        if not remaining:
            continue
        remaining.sort(key=lambda r: _stable_rank(seed, r.decision_id))
        pick = remaining[0]
        selected[pick.decision_id] = min(1.0, capacity / max(1, len(rows)))
    if len(selected) < capacity:
        rest = [r for r in rows if r.decision_id not in selected]
        rest.sort(key=lambda r: _stable_rank(seed, r.decision_id))
        need = capacity - len(selected)
        probability = min(1.0, need / max(1, len(rest)))
        for row in rest[:need]:
            selected[row.decision_id] = probability
    return selected
