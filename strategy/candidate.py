"""Strategy candidate value objects and deterministic ranking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import uuid

from strategy.features import CandidateFeatures


@dataclass(frozen=True)
class StrategyCandidate:
    symbol: str
    direction: str
    score: float
    pattern: str
    bucket: int
    features: CandidateFeatures
    structure_fingerprint: Any = None
    score_breakdown: Any = None
    reference_price: float | None = None
    risk_plan: Any = None
    observation_id: str = field(
        default_factory=lambda: uuid.uuid4().hex
    )
    decision_batch_id: str | None = None
    market_event_id: str | None = None
    strategy_version: str | None = None
    strategy_variant_id: str | None = None
    model_version: str | None = None
    execution_eligible: bool = True
    experiment_context: dict | None = None

    def __post_init__(self):
        symbol = str(self.symbol).strip().upper()
        direction = str(self.direction).strip().upper()
        pattern = str(self.pattern).strip()

        if not symbol:
            raise ValueError("CANDIDATE_SYMBOL_INVALID")
        if direction not in {"LONG", "SHORT"}:
            raise ValueError("CANDIDATE_DIRECTION_INVALID")
        if not pattern:
            raise ValueError("CANDIDATE_PATTERN_INVALID")
        if int(self.bucket) < 0:
            raise ValueError("CANDIDATE_BUCKET_INVALID")
        observation_id = str(self.observation_id).strip()
        if not observation_id:
            raise ValueError("CANDIDATE_OBSERVATION_ID_INVALID")

        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "pattern", pattern)
        object.__setattr__(self, "score", float(self.score))
        object.__setattr__(self, "bucket", int(self.bucket))
        object.__setattr__(self, "observation_id", observation_id)
        for field_name in (
            "decision_batch_id",
            "market_event_id",
            "strategy_version",
            "strategy_variant_id",
            "model_version",
        ):
            value = getattr(self, field_name)
            if value is not None:
                normalized = str(value).strip()
                if not normalized:
                    raise ValueError(
                        f"CANDIDATE_{field_name.upper()}_INVALID"
                    )
                object.__setattr__(self, field_name, normalized)
        object.__setattr__(
            self,
            "execution_eligible",
            bool(self.execution_eligible),
        )
        if self.experiment_context is not None:
            from strategy.experiment_contract import (
                copy_experiment_context,
            )
            object.__setattr__(
                self,
                "experiment_context",
                copy_experiment_context(self.experiment_context),
            )
        if self.reference_price is not None:
            reference_price = float(self.reference_price)
            if reference_price <= 0:
                raise ValueError("CANDIDATE_REFERENCE_PRICE_INVALID")
            object.__setattr__(self, "reference_price", reference_price)


def rank_candidates(
    candidates: Iterable[StrategyCandidate],
) -> list[StrategyCandidate]:
    """Rank deterministically by score, then symbol and direction."""
    return sorted(
        candidates,
        key=lambda item: (-item.score, item.symbol, item.direction),
    )
