"""Observation responses and outcome acknowledgements."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from communication.execution_proposal import ExecutionProposal
from communication.protocol import (
    PROTOCOL_VERSION,
    ProtocolValidationError,
    optional_string,
    require_mapping,
    require_nonempty_string,
    validate_outcome_ack_status,
    validate_payload_keys,
    validate_protocol_version,
    validate_timestamp_ms,
    validate_trade_response_status,
)


@dataclass(frozen=True)
class TradeResponse:
    protocol_version: str
    request_id: str
    status: str
    responded_at: int
    proposal: ExecutionProposal | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "protocol_version",
            validate_protocol_version(self.protocol_version),
        )
        object.__setattr__(
            self,
            "request_id",
            require_nonempty_string(self.request_id, field="request_id"),
        )
        object.__setattr__(
            self,
            "status",
            validate_trade_response_status(self.status),
        )
        object.__setattr__(
            self,
            "responded_at",
            validate_timestamp_ms(self.responded_at, field="responded_at"),
        )
        object.__setattr__(
            self,
            "reason",
            optional_string(self.reason, field="reason"),
        )

        if self.status == "PROPOSAL":
            if not isinstance(self.proposal, ExecutionProposal):
                raise ProtocolValidationError(
                    "PROTOCOL_TRADE_RESPONSE_PROPOSAL_REQUIRED"
                )
        elif self.proposal is not None:
            raise ProtocolValidationError(
                "PROTOCOL_TRADE_RESPONSE_PROPOSAL_NOT_ALLOWED"
            )

    @classmethod
    def proposal_response(
        cls,
        *,
        request_id: str,
        responded_at: int,
        proposal: ExecutionProposal,
    ) -> "TradeResponse":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            request_id=request_id,
            status="PROPOSAL",
            responded_at=responded_at,
            proposal=proposal,
        )

    @classmethod
    def no_trade(
        cls,
        *,
        request_id: str,
        responded_at: int,
        reason: str | None = None,
    ) -> "TradeResponse":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            request_id=request_id,
            status="NO_TRADE",
            responded_at=responded_at,
            reason=reason,
        )

    @classmethod
    def not_ready(
        cls,
        *,
        request_id: str,
        responded_at: int,
        reason: str,
    ) -> "TradeResponse":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            request_id=request_id,
            status="NOT_READY",
            responded_at=responded_at,
            reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.proposal is not None:
            payload["proposal"] = self.proposal.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TradeResponse":
        payload = require_mapping(payload)
        validate_payload_keys(
            payload,
            required={
                "protocol_version",
                "request_id",
                "status",
                "responded_at",
            },
            optional={"proposal", "reason"},
        )
        data = dict(payload)
        proposal_payload = data.get("proposal")
        if proposal_payload is not None:
            data["proposal"] = ExecutionProposal.from_dict(proposal_payload)
        return cls(**data)


@dataclass(frozen=True)
class OutcomeAcknowledgement:
    protocol_version: str
    outcome_id: str
    acknowledged_at: int
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "protocol_version",
            validate_protocol_version(self.protocol_version),
        )
        object.__setattr__(
            self,
            "outcome_id",
            require_nonempty_string(self.outcome_id, field="outcome_id"),
        )
        object.__setattr__(
            self,
            "acknowledged_at",
            validate_timestamp_ms(
                self.acknowledged_at,
                field="acknowledged_at",
            ),
        )
        object.__setattr__(
            self,
            "status",
            validate_outcome_ack_status(self.status),
        )

    @classmethod
    def create(
        cls,
        *,
        outcome_id: str,
        acknowledged_at: int,
        status: str,
    ) -> "OutcomeAcknowledgement":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            outcome_id=outcome_id,
            acknowledged_at=acknowledged_at,
            status=status,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "OutcomeAcknowledgement":
        payload = require_mapping(payload)
        validate_payload_keys(
            payload,
            required={
                "protocol_version",
                "outcome_id",
                "acknowledged_at",
                "status",
            },
        )
        return cls(**dict(payload))
