"""Frozen NBOT V3.5 JSON-safe control-plane contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .validation import (
    OUTCOME_SCHEMA_VERSION,
    PROPOSAL_SCHEMA_VERSION,
    PROTOCOL_VERSION,
    ProtocolValidationError,
    VALID_ACK_STATUSES,
    VALID_DIRECTIONS,
    VALID_EXECUTION_STATES,
    VALID_PREVIOUS_PROPOSAL_RESULTS,
    VALID_RESPONSE_STATUSES,
    choice,
    digest,
    git_sha,
    integer,
    json_object,
    number,
    optional_digest,
    optional_text,
    outcome_schema_version,
    proposal_schema_version,
    protocol_version,
    require_mapping,
    symbol,
    text,
    timestamp_ms,
    validate_keys,
    validate_profile_contract,
)


@dataclass(frozen=True, slots=True)
class TradeRequest:
    protocol_version: str
    request_id: str
    requested_at_ms: int
    profile: str
    market_environment: str
    execution_mode: str
    execution_state: str
    execution_instance_id: str
    supported_proposal_schema_version: str
    execution_release_sha: str
    previous_proposal_id: str | None = None
    previous_proposal_result: str | None = None
    previous_rejection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", protocol_version(self.protocol_version))
        object.__setattr__(self, "request_id", text(self.request_id, "request_id"))
        object.__setattr__(self, "requested_at_ms", timestamp_ms(self.requested_at_ms, "requested_at_ms"))
        profile, environment, mode, _ = validate_profile_contract(
            profile=self.profile,
            market_environment=self.market_environment,
            execution_mode=self.execution_mode,
        )
        object.__setattr__(self, "profile", profile)
        object.__setattr__(self, "market_environment", environment)
        object.__setattr__(self, "execution_mode", mode)
        object.__setattr__(
            self,
            "execution_state",
            choice(self.execution_state, "execution_state", VALID_EXECUTION_STATES),
        )
        object.__setattr__(
            self,
            "execution_instance_id",
            text(self.execution_instance_id, "execution_instance_id", max_length=128),
        )
        object.__setattr__(
            self,
            "supported_proposal_schema_version",
            proposal_schema_version(self.supported_proposal_schema_version),
        )
        object.__setattr__(
            self,
            "execution_release_sha",
            git_sha(self.execution_release_sha, "execution_release_sha"),
        )
        previous_id = optional_text(self.previous_proposal_id, "previous_proposal_id")
        previous_result = self.previous_proposal_result
        previous_reason = optional_text(self.previous_rejection_reason, "previous_rejection_reason")
        if previous_result is not None:
            previous_result = choice(
                previous_result,
                "previous_proposal_result",
                VALID_PREVIOUS_PROPOSAL_RESULTS,
            )
        if any(value is not None for value in (previous_id, previous_result, previous_reason)):
            if previous_id is None or previous_result is None:
                raise ProtocolValidationError("PROTOCOL_PREVIOUS_PROPOSAL_FEEDBACK_INCOMPLETE")
            if previous_result == "REJECTED" and previous_reason is None:
                raise ProtocolValidationError("PROTOCOL_PREVIOUS_REJECTION_REASON_REQUIRED")
        object.__setattr__(self, "previous_proposal_id", previous_id)
        object.__setattr__(self, "previous_proposal_result", previous_result)
        object.__setattr__(self, "previous_rejection_reason", previous_reason)

    @classmethod
    def create(cls, **kwargs: Any) -> "TradeRequest":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            supported_proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TradeRequest":
        payload = require_mapping(payload)
        validate_keys(
            payload,
            required={
                "protocol_version",
                "request_id",
                "requested_at_ms",
                "profile",
                "market_environment",
                "execution_mode",
                "execution_state",
                "execution_instance_id",
                "supported_proposal_schema_version",
                "execution_release_sha",
            },
            optional={
                "previous_proposal_id",
                "previous_proposal_result",
                "previous_rejection_reason",
            },
        )
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class ExecutionProposal:
    protocol_version: str
    proposal_schema_version: str
    proposal_id: str
    generated_at_ms: int
    expires_at_ms: int
    profile: str
    market_environment: str
    evidence_lineage: str
    symbol: str
    side: str
    market_event_id: str
    data_generation_id: str
    feature_version: str
    selector_version: str
    entry_authority: str
    exit_policy_version: str
    reference_price: float
    selection_score: float
    selection_rank: int
    expected_after_cost_net_r: float | None
    source_digest: str
    model_digest: str | None = None
    experiment_context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", protocol_version(self.protocol_version))
        object.__setattr__(self, "proposal_schema_version", proposal_schema_version(self.proposal_schema_version))
        object.__setattr__(self, "proposal_id", text(self.proposal_id, "proposal_id"))
        generated = timestamp_ms(self.generated_at_ms, "generated_at_ms")
        expires = timestamp_ms(self.expires_at_ms, "expires_at_ms")
        if expires <= generated:
            raise ProtocolValidationError("PROTOCOL_PROPOSAL_EXPIRY_INVALID")
        object.__setattr__(self, "generated_at_ms", generated)
        object.__setattr__(self, "expires_at_ms", expires)
        profile, environment, _mode, lineage = validate_profile_contract(
            profile=self.profile,
            market_environment=self.market_environment,
            execution_mode=("TRADE" if str(self.profile).strip().lower() != "live-paper" else "PAPER"),
            evidence_lineage=self.evidence_lineage,
        )
        object.__setattr__(self, "profile", profile)
        object.__setattr__(self, "market_environment", environment)
        object.__setattr__(self, "evidence_lineage", lineage)
        object.__setattr__(self, "symbol", symbol(self.symbol))
        object.__setattr__(self, "side", choice(self.side, "side", VALID_DIRECTIONS))
        for field in (
            "market_event_id",
            "data_generation_id",
            "feature_version",
            "selector_version",
            "entry_authority",
            "exit_policy_version",
        ):
            object.__setattr__(self, field, text(getattr(self, field), field, max_length=160))
        object.__setattr__(self, "reference_price", number(self.reference_price, "reference_price", positive=True))
        object.__setattr__(self, "selection_score", number(self.selection_score, "selection_score"))
        object.__setattr__(self, "selection_rank", integer(self.selection_rank, "selection_rank", minimum=1))
        object.__setattr__(
            self,
            "expected_after_cost_net_r",
            number(self.expected_after_cost_net_r, "expected_after_cost_net_r", allow_none=True),
        )
        object.__setattr__(self, "source_digest", digest(self.source_digest, "source_digest"))
        object.__setattr__(self, "model_digest", optional_digest(self.model_digest, "model_digest"))
        object.__setattr__(
            self,
            "experiment_context",
            json_object(self.experiment_context, "experiment_context"),
        )

    @classmethod
    def create(cls, **kwargs: Any) -> "ExecutionProposal":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            proposal_schema_version=PROPOSAL_SCHEMA_VERSION,
            **kwargs,
        )

    def is_expired(self, *, now_ms: int) -> bool:
        return timestamp_ms(now_ms, "now_ms") > self.expires_at_ms

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionProposal":
        payload = require_mapping(payload)
        validate_keys(
            payload,
            required={
                "protocol_version",
                "proposal_schema_version",
                "proposal_id",
                "generated_at_ms",
                "expires_at_ms",
                "profile",
                "market_environment",
                "evidence_lineage",
                "symbol",
                "side",
                "market_event_id",
                "data_generation_id",
                "feature_version",
                "selector_version",
                "entry_authority",
                "exit_policy_version",
                "reference_price",
                "selection_score",
                "selection_rank",
                "expected_after_cost_net_r",
                "source_digest",
            },
            optional={"model_digest", "experiment_context"},
        )
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class TradeResponse:
    protocol_version: str
    request_id: str
    status: str
    responded_at_ms: int
    proposal: ExecutionProposal | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", protocol_version(self.protocol_version))
        object.__setattr__(self, "request_id", text(self.request_id, "request_id"))
        status = choice(self.status, "status", VALID_RESPONSE_STATUSES)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "responded_at_ms", timestamp_ms(self.responded_at_ms, "responded_at_ms"))
        object.__setattr__(self, "reason", optional_text(self.reason, "reason", max_length=300))
        if status == "PROPOSAL":
            if not isinstance(self.proposal, ExecutionProposal):
                raise ProtocolValidationError("PROTOCOL_TRADE_RESPONSE_PROPOSAL_REQUIRED")
        elif self.proposal is not None:
            raise ProtocolValidationError("PROTOCOL_TRADE_RESPONSE_PROPOSAL_NOT_ALLOWED")

    @classmethod
    def proposal_response(cls, *, request_id: str, responded_at_ms: int, proposal: ExecutionProposal) -> "TradeResponse":
        return cls(PROTOCOL_VERSION, request_id, "PROPOSAL", responded_at_ms, proposal=proposal)

    @classmethod
    def no_trade(cls, *, request_id: str, responded_at_ms: int, reason: str | None = None) -> "TradeResponse":
        return cls(PROTOCOL_VERSION, request_id, "NO_TRADE", responded_at_ms, reason=reason)

    @classmethod
    def not_ready(cls, *, request_id: str, responded_at_ms: int, reason: str) -> "TradeResponse":
        return cls(PROTOCOL_VERSION, request_id, "NOT_READY", responded_at_ms, reason=reason)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.proposal is not None:
            payload["proposal"] = self.proposal.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TradeResponse":
        payload = require_mapping(payload)
        validate_keys(
            payload,
            required={"protocol_version", "request_id", "status", "responded_at_ms"},
            optional={"proposal", "reason"},
        )
        data = dict(payload)
        if data.get("proposal") is not None:
            data["proposal"] = ExecutionProposal.from_dict(data["proposal"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    protocol_version: str
    outcome_schema_version: str
    outcome_id: str
    proposal_id: str
    request_id: str
    profile: str
    market_environment: str
    execution_mode: str
    evidence_lineage: str
    symbol: str
    side: str
    market_event_id: str
    feature_version: str
    selector_version: str
    entry_authority: str
    exit_policy_version: str
    reference_price: float
    selection_score: float
    selection_rank: int
    expected_after_cost_net_r: float | None
    proposal_source_digest: str
    proposal_model_digest: str | None
    entry_price: float
    exit_price: float
    quantity: float
    initial_risk_usd: float
    realized_pnl_usd: float
    r_multiple: float
    mae_usd: float | None
    mfe_usd: float | None
    mae_r: float | None
    mfe_r: float | None
    entry_timestamp_ms: int
    closed_timestamp_ms: int
    holding_seconds: int
    exit_reason: str
    close_source: str
    execution_payload_digest: str
    entry_order_id: str | None = None
    entry_client_order_id: str | None = None
    final_stop_price: float | None = None
    final_stop_id: str | None = None
    experiment_context: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", protocol_version(self.protocol_version))
        object.__setattr__(self, "outcome_schema_version", outcome_schema_version(self.outcome_schema_version))
        for field in ("outcome_id", "proposal_id", "request_id"):
            object.__setattr__(self, field, text(getattr(self, field), field))
        profile, environment, mode, lineage = validate_profile_contract(
            profile=self.profile,
            market_environment=self.market_environment,
            execution_mode=self.execution_mode,
            evidence_lineage=self.evidence_lineage,
        )
        object.__setattr__(self, "profile", profile)
        object.__setattr__(self, "market_environment", environment)
        object.__setattr__(self, "execution_mode", mode)
        object.__setattr__(self, "evidence_lineage", lineage)
        object.__setattr__(self, "symbol", symbol(self.symbol))
        object.__setattr__(self, "side", choice(self.side, "side", VALID_DIRECTIONS))
        for field in (
            "market_event_id",
            "feature_version",
            "selector_version",
            "entry_authority",
            "exit_policy_version",
            "exit_reason",
            "close_source",
        ):
            object.__setattr__(self, field, text(getattr(self, field), field, max_length=200))
        object.__setattr__(self, "reference_price", number(self.reference_price, "reference_price", positive=True))
        object.__setattr__(self, "selection_score", number(self.selection_score, "selection_score"))
        object.__setattr__(self, "selection_rank", integer(self.selection_rank, "selection_rank", minimum=1))
        object.__setattr__(self, "expected_after_cost_net_r", number(self.expected_after_cost_net_r, "expected_after_cost_net_r", allow_none=True))
        object.__setattr__(self, "proposal_source_digest", digest(self.proposal_source_digest, "proposal_source_digest"))
        object.__setattr__(self, "proposal_model_digest", optional_digest(self.proposal_model_digest, "proposal_model_digest"))
        for field in ("entry_price", "exit_price", "quantity", "initial_risk_usd"):
            object.__setattr__(self, field, number(getattr(self, field), field, positive=True))
        for field in ("realized_pnl_usd", "r_multiple"):
            object.__setattr__(self, field, number(getattr(self, field), field))
        for field in ("mae_usd", "mfe_usd", "mae_r", "mfe_r"):
            object.__setattr__(self, field, number(getattr(self, field), field, allow_none=True))
        entered = timestamp_ms(self.entry_timestamp_ms, "entry_timestamp_ms")
        closed = timestamp_ms(self.closed_timestamp_ms, "closed_timestamp_ms")
        if closed < entered:
            raise ProtocolValidationError("PROTOCOL_OUTCOME_TIMESTAMP_ORDER_INVALID")
        object.__setattr__(self, "entry_timestamp_ms", entered)
        object.__setattr__(self, "closed_timestamp_ms", closed)
        holding = integer(self.holding_seconds, "holding_seconds", minimum=0)
        expected_holding = max(0, (closed - entered) // 1000)
        if abs(holding - expected_holding) > 1:
            raise ProtocolValidationError("PROTOCOL_OUTCOME_HOLDING_SECONDS_MISMATCH")
        object.__setattr__(self, "holding_seconds", holding)
        object.__setattr__(self, "execution_payload_digest", digest(self.execution_payload_digest, "execution_payload_digest"))
        for field in ("entry_order_id", "entry_client_order_id", "final_stop_id"):
            object.__setattr__(self, field, optional_text(getattr(self, field), field, max_length=200))
        stop = number(self.final_stop_price, "final_stop_price", positive=True, allow_none=True)
        object.__setattr__(self, "final_stop_price", stop)
        object.__setattr__(self, "experiment_context", json_object(self.experiment_context, "experiment_context"))

    @classmethod
    def create(cls, **kwargs: Any) -> "ExecutionOutcome":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            outcome_schema_version=OUTCOME_SCHEMA_VERSION,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionOutcome":
        payload = require_mapping(payload)
        required = set(cls.__dataclass_fields__)
        optional = {
            "mae_usd",
            "mfe_usd",
            "mae_r",
            "mfe_r",
            "proposal_model_digest",
            "entry_order_id",
            "entry_client_order_id",
            "final_stop_price",
            "final_stop_id",
            "experiment_context",
        }
        validate_keys(payload, required=required - optional, optional=optional)
        return cls(**dict(payload))


@dataclass(frozen=True, slots=True)
class OutcomeAcknowledgement:
    protocol_version: str
    outcome_id: str
    status: str
    recorded_at_ms: int
    observation_store_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", protocol_version(self.protocol_version))
        object.__setattr__(self, "outcome_id", text(self.outcome_id, "outcome_id"))
        object.__setattr__(self, "status", choice(self.status, "status", VALID_ACK_STATUSES))
        object.__setattr__(self, "recorded_at_ms", timestamp_ms(self.recorded_at_ms, "recorded_at_ms"))
        object.__setattr__(self, "observation_store_id", text(self.observation_store_id, "observation_store_id", max_length=160))

    @classmethod
    def create(cls, **kwargs: Any) -> "OutcomeAcknowledgement":
        return cls(protocol_version=PROTOCOL_VERSION, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OutcomeAcknowledgement":
        payload = require_mapping(payload)
        validate_keys(
            payload,
            required={"protocol_version", "outcome_id", "status", "recorded_at_ms", "observation_store_id"},
        )
        return cls(**dict(payload))
