"""Execution -> Observation request made only while Execution is flat."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from communication.protocol import (
    PROTOCOL_VERSION,
    ProtocolValidationError,
    optional_string,
    require_mapping,
    require_nonempty_string,
    validate_environment,
    validate_execution_mode,
    validate_payload_keys,
    validate_protocol_version,
    validate_timestamp_ms,
)


@dataclass(frozen=True)
class TradeRequest:
    protocol_version: str
    request_id: str
    requested_at: int
    environment: str
    execution_mode: str
    execution_state: str
    previous_proposal_id: str | None = None
    previous_proposal_result: str | None = None
    previous_rejection_reason: str | None = None

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
            "requested_at",
            validate_timestamp_ms(self.requested_at, field="requested_at"),
        )
        object.__setattr__(
            self,
            "environment",
            validate_environment(self.environment),
        )
        object.__setattr__(
            self,
            "execution_mode",
            validate_execution_mode(self.execution_mode),
        )

        execution_state = require_nonempty_string(
            self.execution_state,
            field="execution_state",
        ).upper()
        if execution_state != "FLAT":
            raise ProtocolValidationError(
                f"PROTOCOL_TRADE_REQUEST_REQUIRES_FLAT:{execution_state}"
            )
        object.__setattr__(self, "execution_state", execution_state)

        object.__setattr__(
            self,
            "previous_proposal_id",
            optional_string(
                self.previous_proposal_id,
                field="previous_proposal_id",
            ),
        )
        object.__setattr__(
            self,
            "previous_proposal_result",
            optional_string(
                self.previous_proposal_result,
                field="previous_proposal_result",
            ),
        )
        object.__setattr__(
            self,
            "previous_rejection_reason",
            optional_string(
                self.previous_rejection_reason,
                field="previous_rejection_reason",
            ),
        )

        if (
            self.previous_proposal_result is not None
            or self.previous_rejection_reason is not None
        ) and self.previous_proposal_id is None:
            raise ProtocolValidationError(
                "PROTOCOL_PREVIOUS_PROPOSAL_ID_REQUIRED"
            )

    @classmethod
    def create(
        cls,
        *,
        request_id: str,
        requested_at: int,
        environment: str,
        execution_mode: str,
        previous_proposal_id: str | None = None,
        previous_proposal_result: str | None = None,
        previous_rejection_reason: str | None = None,
    ) -> "TradeRequest":
        return cls(
            protocol_version=PROTOCOL_VERSION,
            request_id=request_id,
            requested_at=requested_at,
            environment=environment,
            execution_mode=execution_mode,
            execution_state="FLAT",
            previous_proposal_id=previous_proposal_id,
            previous_proposal_result=previous_proposal_result,
            previous_rejection_reason=previous_rejection_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TradeRequest":
        payload = require_mapping(payload)
        validate_payload_keys(
            payload,
            required={
                "protocol_version",
                "request_id",
                "requested_at",
                "environment",
                "execution_mode",
                "execution_state",
            },
            optional={
                "previous_proposal_id",
                "previous_proposal_result",
                "previous_rejection_reason",
            },
        )
        return cls(**dict(payload))
