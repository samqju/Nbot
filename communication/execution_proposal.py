"""Observation -> Execution advisory trade proposal contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from communication.protocol import (
    PROTOCOL_VERSION,
    ProtocolValidationError,
    finite_number,
    optional_string,
    require_mapping,
    require_nonempty_string,
    validate_direction,
    validate_environment,
    validate_json_object,
    validate_payload_keys,
    validate_protocol_version,
    validate_selection_authority,
    validate_symbol,
    validate_timestamp_ms,
)


@dataclass(frozen=True)
class ExecutionProposal:
    protocol_version: str
    proposal_id: str
    generated_at: int
    expires_at: int
    environment: str
    symbol: str
    direction: str
    pattern: str
    entry_reference_price: float | None = None
    candidate_score: float | None = None
    candidate_observation_id: str | None = None
    decision_batch_id: str | None = None
    market_event_id: str | None = None
    strategy_version: str | None = None
    strategy_variant_id: str | None = None
    model_version: str | None = None
    selection_authority: str = "RULES"
    structure_fingerprint: dict[str, Any] | None = None
    advisory_risk_plan: dict[str, Any] | None = None
    experiment_context: dict[str, Any] | None = None
    paper_canary_model_id: str | None = None
    paper_risk_multiplier: float = 1.0
    paper_allocation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "protocol_version",
            validate_protocol_version(self.protocol_version),
        )
        object.__setattr__(
            self,
            "proposal_id",
            require_nonempty_string(self.proposal_id, field="proposal_id"),
        )
        generated_at = validate_timestamp_ms(
            self.generated_at,
            field="generated_at",
        )
        expires_at = validate_timestamp_ms(
            self.expires_at,
            field="expires_at",
        )
        if expires_at <= generated_at:
            raise ProtocolValidationError("PROTOCOL_PROPOSAL_EXPIRY_INVALID")
        object.__setattr__(self, "generated_at", generated_at)
        object.__setattr__(self, "expires_at", expires_at)
        object.__setattr__(
            self,
            "environment",
            validate_environment(self.environment),
        )
        object.__setattr__(self, "symbol", validate_symbol(self.symbol))
        object.__setattr__(
            self,
            "direction",
            validate_direction(self.direction),
        )
        object.__setattr__(
            self,
            "pattern",
            require_nonempty_string(self.pattern, field="pattern"),
        )

        reference_price = finite_number(
            self.entry_reference_price,
            field="entry_reference_price",
            allow_none=True,
        )
        if reference_price is not None and reference_price <= 0:
            raise ProtocolValidationError(
                "PROTOCOL_ENTRY_REFERENCE_PRICE_INVALID"
            )
        object.__setattr__(self, "entry_reference_price", reference_price)

        score = finite_number(
            self.candidate_score,
            field="candidate_score",
            allow_none=True,
        )
        if score is not None and not (0.0 <= score <= 1.0):
            raise ProtocolValidationError("PROTOCOL_CANDIDATE_SCORE_INVALID")
        object.__setattr__(self, "candidate_score", score)

        for field in (
            "candidate_observation_id",
            "decision_batch_id",
            "market_event_id",
            "strategy_version",
            "strategy_variant_id",
            "model_version",
        ):
            object.__setattr__(
                self,
                field,
                optional_string(getattr(self, field), field=field),
            )

        authority = validate_selection_authority(self.selection_authority)
        object.__setattr__(self, "selection_authority", authority)

        object.__setattr__(
            self,
            "structure_fingerprint",
            validate_json_object(
                self.structure_fingerprint,
                field="structure_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "advisory_risk_plan",
            validate_json_object(
                self.advisory_risk_plan,
                field="advisory_risk_plan",
            ),
        )
        object.__setattr__(
            self,
            "experiment_context",
            validate_json_object(
                self.experiment_context,
                field="experiment_context",
            ),
        )

        multiplier = finite_number(
            self.paper_risk_multiplier,
            field="paper_risk_multiplier",
        )
        if multiplier is None or not (0.0 < multiplier <= 1.0):
            raise ProtocolValidationError(
                "PROTOCOL_PAPER_RISK_MULTIPLIER_INVALID"
            )
        object.__setattr__(self, "paper_risk_multiplier", multiplier)

        model_id = optional_string(
            self.paper_canary_model_id,
            field="paper_canary_model_id",
        )
        allocation_id = optional_string(
            self.paper_allocation_id,
            field="paper_allocation_id",
        )

        if authority in {"PAPER_CANARY", "PAPER_CHAMPION"}:
            if abs(multiplier - 1.0) > 1e-12:
                raise ProtocolValidationError(
                    "PROTOCOL_MODEL_RISK_MUST_EQUAL_ONE"
                )
            if model_id is None:
                raise ProtocolValidationError(
                    "PROTOCOL_PAPER_MODEL_ID_REQUIRED"
                )
            if authority == "PAPER_CANARY" and allocation_id is None:
                raise ProtocolValidationError(
                    "PROTOCOL_PAPER_ALLOCATION_ID_REQUIRED"
                )

        object.__setattr__(self, "paper_canary_model_id", model_id)
        object.__setattr__(self, "paper_allocation_id", allocation_id)

    @classmethod
    def create(cls, **kwargs: Any) -> "ExecutionProposal":
        return cls(protocol_version=PROTOCOL_VERSION, **kwargs)

    def is_expired(self, *, now_ms: int) -> bool:
        validate_timestamp_ms(now_ms, field="now_ms")
        return now_ms > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionProposal":
        payload = require_mapping(payload)
        validate_payload_keys(
            payload,
            required={
                "protocol_version",
                "proposal_id",
                "generated_at",
                "expires_at",
                "environment",
                "symbol",
                "direction",
                "pattern",
            },
            optional={
                "entry_reference_price",
                "candidate_score",
                "candidate_observation_id",
                "decision_batch_id",
                "market_event_id",
                "strategy_version",
                "strategy_variant_id",
                "model_version",
                "selection_authority",
                "structure_fingerprint",
                "advisory_risk_plan",
                "experiment_context",
                "paper_canary_model_id",
                "paper_risk_multiplier",
                "paper_allocation_id",
            },
        )
        return cls(**dict(payload))
