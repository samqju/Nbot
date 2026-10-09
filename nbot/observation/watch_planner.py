"""Dynamic two-tier research watch planning for V3.

Tier 1: broad, inexpensive 5-minute research scan (default target: 100 symbols).
Tier 2: expensive continuous high-resolution WSS watch (hard cap: 20 symbols).

Active high-resolution hypotheses are sticky: a watched symbol is not evicted
until all of its active hypotheses mature. This protects chronological path
integrity and prevents minute-by-minute rotation from creating missing paths.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable, Mapping

from .sampling import SamplingCandidate


BROAD_SCAN_TARGET = 100
HIGH_RES_SYMBOL_CAP = 20


@dataclass(frozen=True)
class WatchCandidate:
    symbol: str
    conservative_score_r: float
    threshold_r: float
    setup_id: str
    volatility_bucket: str = "UNKNOWN"
    ridge_score_r: float | None = None
    ml_score_r: float | None = None
    approved: bool = False

    def __post_init__(self) -> None:
        if not self.symbol or self.symbol != self.symbol.upper() or not self.setup_id:
            raise ValueError("WATCH_CANDIDATE_IDENTITY_INVALID")
        values = (
            self.conservative_score_r,
            self.threshold_r,
            self.ridge_score_r,
            self.ml_score_r,
        )
        if any(value is not None and not math.isfinite(value) for value in values):
            raise ValueError("WATCH_CANDIDATE_SCORE_INVALID")

    @property
    def distance_to_threshold(self) -> float:
        return abs(self.conservative_score_r - self.threshold_r)

    @property
    def near_threshold(self) -> bool:
        return self.distance_to_threshold <= 0.03

    @property
    def disagreement(self) -> bool:
        return (
            self.ridge_score_r is not None
            and self.ml_score_r is not None
            and ((self.ridge_score_r >= self.threshold_r) != (self.ml_score_r >= self.threshold_r))
        )


@dataclass(frozen=True)
class WatchPlan:
    broad_symbols: tuple[str, ...]
    high_res_symbols: tuple[str, ...]
    retained_active_symbols: tuple[str, ...]
    newly_admitted_symbols: tuple[str, ...]
    rejected_for_capacity: tuple[str, ...]
    reasons: Mapping[str, str]


def _stable(symbol: str, seed: str) -> int:
    return int(hashlib.sha256(f"{seed}:{symbol}".encode()).hexdigest(), 16)


def _best_by_symbol(candidates: Iterable[WatchCandidate]) -> dict[str, WatchCandidate]:
    grouped: dict[str, list[WatchCandidate]] = {}
    for row in candidates:
        grouped.setdefault(row.symbol, []).append(row)
    output = {}
    for symbol, rows in grouped.items():
        rows.sort(
            key=lambda row: (
                not row.approved,
                -row.conservative_score_r,
                row.distance_to_threshold,
                row.setup_id,
            )
        )
        output[symbol] = rows[0]
    return output


def plan_two_tier_watch(
    *,
    broad_symbols: Iterable[str],
    candidates: Iterable[WatchCandidate],
    active_high_res_symbols: Iterable[str] = (),
    broad_target: int = BROAD_SCAN_TARGET,
    high_res_cap: int = HIGH_RES_SYMBOL_CAP,
    seed: str = "NBOT_V3_HIGH_RES",
) -> WatchPlan:
    """Choose the broad 5m pool and sticky high-resolution WSS pool.

    Selection priority for free high-resolution slots:
      1. approved/strong current candidates,
      2. Ridge/ML disagreements,
      3. near-threshold cases,
      4. setup-family diversity,
      5. volatility-bucket diversity,
      6. deterministic control candidates.

    Already-active symbols are always retained. If callers somehow supply more
    active symbols than the configured cap, fail closed instead of silently
    dropping a live research path.
    """
    if not 1 <= broad_target <= 500 or not 1 <= high_res_cap <= broad_target:
        raise ValueError("WATCH_PLAN_CONFIG_INVALID")

    broad_unique = tuple(dict.fromkeys(str(s).upper() for s in broad_symbols))
    if any(not s for s in broad_unique):
        raise ValueError("WATCH_PLAN_SYMBOL_INVALID")
    broad = broad_unique[:broad_target]
    broad_set = set(broad)

    active = tuple(sorted(set(str(s).upper() for s in active_high_res_symbols)))
    if len(active) > high_res_cap:
        raise ValueError("WATCH_PLAN_ACTIVE_SYMBOLS_EXCEED_CAP")
    if any(symbol not in broad_set for symbol in active):
        raise ValueError("WATCH_PLAN_ACTIVE_SYMBOL_OUTSIDE_BROAD_POOL")

    best = {
        symbol: row
        for symbol, row in _best_by_symbol(candidates).items()
        if symbol in broad_set and symbol not in active
    }

    selected = list(active)
    reasons: dict[str, str] = {symbol: "ACTIVE_HYPOTHESIS_STICKY" for symbol in active}
    remaining_slots = high_res_cap - len(selected)

    def admit(rows: list[WatchCandidate], reason: str) -> None:
        nonlocal remaining_slots
        if remaining_slots <= 0:
            return
        rows = [row for row in rows if row.symbol not in selected]
        rows.sort(
            key=lambda row: (
                -row.conservative_score_r,
                row.distance_to_threshold,
                _stable(row.symbol, seed),
            )
        )
        for row in rows:
            if remaining_slots <= 0:
                break
            selected.append(row.symbol)
            reasons[row.symbol] = reason
            remaining_slots -= 1

    # Reserve a balanced mix instead of allowing the strongest-score bucket to
    # consume every slot. Unused quota naturally flows to the final backfill.
    initial_free = remaining_slots
    strong_quota = max(1, round(initial_free * 0.50)) if initial_free else 0
    disagreement_quota = max(1, round(initial_free * 0.20)) if initial_free >= 4 else 0
    threshold_quota = max(1, round(initial_free * 0.15)) if initial_free >= 6 else 0
    diversity_quota = max(1, round(initial_free * 0.10)) if initial_free >= 8 else 0
    control_quota = max(1, initial_free - strong_quota - disagreement_quota - threshold_quota - diversity_quota) if initial_free else 0

    def admit_limited(rows: list[WatchCandidate], reason: str, limit: int) -> None:
        nonlocal remaining_slots
        before = len(selected)
        if limit <= 0:
            return
        admit(rows, reason)
        overflow = len(selected) - before - limit
        if overflow > 0:
            # admit() is general-purpose; trim deterministic excess and restore slots.
            removed = selected[-overflow:]
            del selected[-overflow:]
            for symbol in removed:
                reasons.pop(symbol, None)
            remaining_slots += overflow

    admit_limited(
        [row for row in best.values() if row.approved or row.conservative_score_r >= row.threshold_r],
        "STRONG_OR_APPROVED",
        strong_quota,
    )
    admit_limited([row for row in best.values() if row.disagreement], "RIDGE_ML_DISAGREEMENT", disagreement_quota)
    admit_limited([row for row in best.values() if row.near_threshold], "NEAR_THRESHOLD", threshold_quota)

    diversity_used = 0
    seen_setups = {best[s].setup_id for s in selected if s in best}
    for setup_id in sorted({row.setup_id for row in best.values()} - seen_setups):
        if diversity_used >= diversity_quota or remaining_slots <= 0:
            break
        before = len(selected)
        admit_limited([row for row in best.values() if row.setup_id == setup_id], "SETUP_DIVERSITY", 1)
        diversity_used += len(selected) - before

    seen_vol = {best[s].volatility_bucket for s in selected if s in best}
    for bucket in sorted({row.volatility_bucket for row in best.values()} - seen_vol):
        if diversity_used >= diversity_quota or remaining_slots <= 0:
            break
        before = len(selected)
        admit_limited([row for row in best.values() if row.volatility_bucket == bucket], "VOLATILITY_DIVERSITY", 1)
        diversity_used += len(selected) - before

    controls = [row for row in best.values() if row.symbol not in selected]
    controls.sort(key=lambda row: _stable(row.symbol, seed))
    for row in controls[: min(control_quota, remaining_slots)]:
        selected.append(row.symbol)
        reasons[row.symbol] = "DETERMINISTIC_CONTROL"
        remaining_slots -= 1

    # Backfill unused category quotas with the best remaining candidates. This
    # keeps capacity useful without sacrificing the guaranteed mixture above.
    backfill = [row for row in best.values() if row.symbol not in selected]
    backfill.sort(
        key=lambda row: (
            not row.approved,
            -row.conservative_score_r,
            row.distance_to_threshold,
            _stable(row.symbol, seed),
        )
    )
    for row in backfill:
        if remaining_slots <= 0:
            break
        selected.append(row.symbol)
        reasons[row.symbol] = "BACKFILL"
        remaining_slots -= 1

    selected_tuple = tuple(selected)
    active_set = set(active)
    newly = tuple(symbol for symbol in selected_tuple if symbol not in active_set)
    rejected = tuple(
        sorted(symbol for symbol in best if symbol not in set(selected_tuple))
    )
    return WatchPlan(
        broad_symbols=broad,
        high_res_symbols=selected_tuple,
        retained_active_symbols=active,
        newly_admitted_symbols=newly,
        rejected_for_capacity=rejected,
        reasons=reasons,
    )


def sampling_candidates_to_watch(candidates: Iterable[SamplingCandidate], *, approved_ids: Iterable[str] = ()) -> tuple[WatchCandidate, ...]:
    approved = set(approved_ids)
    return tuple(
        WatchCandidate(
            symbol=row.symbol,
            conservative_score_r=row.conservative_score_r,
            threshold_r=row.threshold_r,
            setup_id=row.setup_id,
            volatility_bucket=row.volatility_bucket,
            ridge_score_r=row.ridge_score_r,
            ml_score_r=row.ml_score_r,
            approved=row.decision_id in approved,
        )
        for row in candidates
    )
