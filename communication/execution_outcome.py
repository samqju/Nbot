"""Execution -> Observation completed trade outcome contract."""

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
    validate_execution_mode,
    validate_json_object,
    validate_payload_keys,
    validate_protocol_version,
    validate_selection_authority,
    validate_symbol,
    validate_timestamp_ms,
)


@dataclass(frozen=True)
class ExecutionOutcome:
    protocol_version: str
    outcome_id: str
    proposal_id: str
    environment: str
    execution_mode: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    realized_pnl_usd: float
    initial_risk_usd: float
    r_multiple: float
    mae_usd: float
    mfe_usd: float
    mae_r: float
    mfe_r: float
    entry_timestamp: int
    closed_timestamp: int
    holding_seconds: int
    candidate_observation_id: str | None = None
    decision_batch_id: str | None = None
    market_event_id: str | None = None
    entry_order_id: str | None = None
    entry_client_order_id: str | None = None
    initial_stop_loss: float | None = None
    final_stop_loss: float | None = None
    exit_reason: str | None = None
    pattern: str | None = None
    strategy_version: str | None = None
    strategy_variant_id: str | None = None
    model_version: str | None = None
    selection_authority: str | None = None
    experiment_context: dict[str, Any] | None = None

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
            "proposal_id",
            require_nonempty_string(self.proposal_id, field="proposal_id"),
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
        object.__setattr__(self, "symbol", validate_symbol(self.symbol))
        object.__setattr__(
            self,
            "side",
            validate_direction(self.side, field="side"),
        )

        entry_price = finite_number(self.entry_price, field="entry_price")
        exit_price = finite_number(self.exit_price, field="exit_price")
        quantity = finite_number(self.quantity, field="quantity")
        if entry_price is None or entry_price <= 0:
            raise ProtocolValidationError("PROTOCOL_ENTRY_PRICE_INVALID")
        # Current reconciliation can preserve a degraded close with exit=0.0
        # when exchange close details are unavailable, so zero is intentional.
        if exit_price is None or exit_price < 0:
            raise ProtocolValidationError("PROTOCOL_EXIT_PRICE_INVALID")
        if quantity is None or quantity <= 0:
            raise ProtocolValidationError("PROTOCOL_QUANTITY_INVALID")
        object.__setattr__(self, "entry_price", entry_price)
        object.__setattr__(self, "exit_price", exit_price)
        object.__setattr__(self, "quantity", quantity)

        for field in (
            "realized_pnl_usd",
            "r_multiple",
            "mae_usd",
            "mfe_usd",
            "mae_r",
            "mfe_r",
        ):
            object.__setattr__(
                self,
                field,
                finite_number(getattr(self, field), field=field),
            )

        initial_risk = finite_number(
            self.initial_risk_usd,
            field="initial_risk_usd",
        )
        if initial_risk is None or initial_risk < 0:
            raise ProtocolValidationError("PROTOCOL_INITIAL_RISK_USD_INVALID")
        object.__setattr__(self, "initial_risk_usd", initial_risk)

        entry_timestamp = validate_timestamp_ms(
            self.entry_timestamp,
            field="entry_timestamp",
        )
        closed_timestamp = validate_timestamp_ms(
            self.closed_timestamp,
            field="closed_timestamp",
        )
        if closed_timestamp < entry_timestamp:
            raise ProtocolValidationError(
                "PROTOCOL_OUTCOME_TIMESTAMP_ORDER_INVALID"
            )
        object.__setattr__(self, "entry_timestamp", entry_timestamp)
        object.__setattr__(self, "closed_timestamp", closed_timestamp)

        if (
            isinstance(self.holding_seconds, bool)
            or not isinstance(self.holding_seconds, int)
            or self.holding_seconds < 0
        ):
            raise ProtocolValidationError("PROTOCOL_HOLDING_SECONDS_INVALID")

        for field in (
            "candidate_observation_id",
            "decision_batch_id",
            "market_event_id",
            "entry_order_id",
            "entry_client_order_id",
            "exit_reason",
            "pattern",
            "strategy_version",
            "strategy_variant_id",
            "model_version",
        ):
            object.__setattr__(
                self,
                field,
                optional_string(getattr(self, field), field=field),
            )

        for field in ("initial_stop_loss", "final_stop_loss"):
            stop = finite_number(
                getattr(self, field),
                field=field,
                allow_none=True,
            )
            if stop is not None and stop <= 0:
                raise ProtocolValidationError(
                    f"PROTOCOL_{field.upper()}_INVALID"
                )
            object.__setattr__(self, field, stop)

        if self.selection_authority is not None:
            object.__setattr__(
                self,
                "selection_authority",
                validate_selection_authority(self.selection_authority),
            )

        object.__setattr__(
            self,
            "experiment_context",
            validate_json_object(
                self.experiment_context,
                field="experiment_context",
            ),
        )

    @classmethod
    def create(cls, **kwargs: Any) -> "ExecutionOutcome":
        return cls(protocol_version=PROTOCOL_VERSION, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionOutcome":
        payload = require_mapping(payload)
        validate_payload_keys(
            payload,
            required={
                "protocol_version",
                "outcome_id",
                "proposal_id",
                "environment",
                "execution_mode",
                "symbol",
                "side",
                "entry_price",
                "exit_price",
                "quantity",
                "realized_pnl_usd",
                "initial_risk_usd",
                "r_multiple",
                "mae_usd",
                "mfe_usd",
                "mae_r",
                "mfe_r",
                "entry_timestamp",
                "closed_timestamp",
                "holding_seconds",
            },
            optional={
                "candidate_observation_id",
                "decision_batch_id",
                "market_event_id",
                "entry_order_id",
                "entry_client_order_id",
                "initial_stop_loss",
                "final_stop_loss",
                "exit_reason",
                "pattern",
                "strategy_version",
                "strategy_variant_id",
                "model_version",
                "selection_authority",
                "experiment_context",
            },
        )
        return cls(**dict(payload))
