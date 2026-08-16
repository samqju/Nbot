from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping


PROTOCOL_VERSION = "NBOT_V2_EXECUTION_V1"
VALID_ENVIRONMENTS = frozenset({"TESTNET", "LIVE"})
VALID_DIRECTIONS = frozenset({"LONG", "SHORT"})
VALID_RESPONSE_STATUSES = frozenset({"PROPOSAL", "NO_TRADE", "NOT_READY"})
VALID_ACK_STATUSES = frozenset({"RECORDED", "ALREADY_RECORDED"})
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,30}$")


class ProtocolValidationError(ValueError):
    pass


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return value.strip()


def _choice(value: Any, field: str, allowed: frozenset[str]) -> str:
    normalized = _nonempty(value, field).upper()
    if normalized not in allowed:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID:{normalized}")
    return normalized


def _timestamp(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return value


def _number(value: Any, field: str, *, positive: bool = False, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return 0.0 if result == 0.0 else result


def _json_object(value: Any, field: str, *, allow_none: bool = True) -> dict[str, Any] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, dict):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_NOT_OBJECT")
    try:
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_NOT_JSON_SAFE") from exc
    return value


def _keys(payload: Mapping[str, Any], required: set[str], optional: set[str] | None = None) -> None:
    optional = optional or set()
    missing = sorted(required - set(payload))
    unknown = sorted(set(payload) - required - optional)
    if missing:
        raise ProtocolValidationError("PROTOCOL_MISSING_FIELDS:" + ",".join(missing))
    if unknown:
        raise ProtocolValidationError("PROTOCOL_UNKNOWN_FIELDS:" + ",".join(unknown))


def _version(value: Any) -> str:
    version = _nonempty(value, "protocol_version")
    if version != PROTOCOL_VERSION:
        raise ProtocolValidationError(f"PROTOCOL_VERSION_UNSUPPORTED:{version}")
    return version


def _symbol(value: Any) -> str:
    symbol = _nonempty(value, "symbol").upper()
    if not symbol.endswith("USDT") or _SYMBOL_RE.fullmatch(symbol) is None:
        raise ProtocolValidationError(f"PROTOCOL_SYMBOL_INVALID:{symbol}")
    return symbol


@dataclass(frozen=True)
class TradeRequest:
    protocol_version: str
    request_id: str
    requested_at_ms: int
    environment: str
    execution_state: str = "FLAT"
    previous_proposal_id: str | None = None
    previous_rejection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", _version(self.protocol_version))
        object.__setattr__(self, "request_id", _nonempty(self.request_id, "request_id"))
        object.__setattr__(self, "requested_at_ms", _timestamp(self.requested_at_ms, "requested_at_ms"))
        object.__setattr__(self, "environment", _choice(self.environment, "environment", VALID_ENVIRONMENTS))
        if self.execution_state != "FLAT":
            raise ProtocolValidationError("PROTOCOL_EXECUTION_STATE_INVALID")
        for field in ("previous_proposal_id", "previous_rejection_reason"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _nonempty(value, field))

    @classmethod
    def create(cls, **kwargs: Any) -> "TradeRequest":
        return cls(protocol_version=PROTOCOL_VERSION, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionProposal:
    protocol_version: str
    proposal_id: str
    environment: str
    symbol: str
    direction: str
    generated_at_ms: int
    expires_at_ms: int
    reference_price: float
    entry_authority: str
    model_version: str
    exit_policy_version: str
    feature_version: str
    data_generation_id: str
    market_event_id: str
    advisory_initial_risk: dict[str, Any] | None = None
    selection_score: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", _version(self.protocol_version))
        for field in (
            "proposal_id", "entry_authority", "model_version", "exit_policy_version",
            "feature_version", "data_generation_id", "market_event_id",
        ):
            object.__setattr__(self, field, _nonempty(getattr(self, field), field))
        object.__setattr__(self, "environment", _choice(self.environment, "environment", VALID_ENVIRONMENTS))
        object.__setattr__(self, "symbol", _symbol(self.symbol))
        object.__setattr__(self, "direction", _choice(self.direction, "direction", VALID_DIRECTIONS))
        generated = _timestamp(self.generated_at_ms, "generated_at_ms")
        expires = _timestamp(self.expires_at_ms, "expires_at_ms")
        if expires <= generated:
            raise ProtocolValidationError("PROTOCOL_PROPOSAL_EXPIRY_INVALID")
        object.__setattr__(self, "generated_at_ms", generated)
        object.__setattr__(self, "expires_at_ms", expires)
        object.__setattr__(self, "reference_price", _number(self.reference_price, "reference_price", positive=True))
        object.__setattr__(self, "advisory_initial_risk", _json_object(self.advisory_initial_risk, "advisory_initial_risk"))
        object.__setattr__(self, "selection_score", _number(self.selection_score, "selection_score", allow_none=True))

    @classmethod
    def create(cls, **kwargs: Any) -> "ExecutionProposal":
        return cls(protocol_version=PROTOCOL_VERSION, **kwargs)

    def is_expired(self, now_ms: int) -> bool:
        return _timestamp(now_ms, "now_ms") > self.expires_at_ms

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionProposal":
        if not isinstance(payload, Mapping):
            raise ProtocolValidationError("PROTOCOL_PAYLOAD_NOT_OBJECT")
        required = {
            "protocol_version", "proposal_id", "environment", "symbol", "direction",
            "generated_at_ms", "expires_at_ms", "reference_price", "entry_authority",
            "model_version", "exit_policy_version", "feature_version", "data_generation_id",
            "market_event_id",
        }
        _keys(payload, required, {"advisory_initial_risk", "selection_score"})
        return cls(**dict(payload))


@dataclass(frozen=True)
class TradeResponse:
    protocol_version: str
    status: str
    proposal: ExecutionProposal | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", _version(self.protocol_version))
        status = _choice(self.status, "status", VALID_RESPONSE_STATUSES)
        object.__setattr__(self, "status", status)
        if status == "PROPOSAL" and self.proposal is None:
            raise ProtocolValidationError("PROTOCOL_PROPOSAL_REQUIRED")
        if status != "PROPOSAL" and self.proposal is not None:
            raise ProtocolValidationError("PROTOCOL_PROPOSAL_NOT_ALLOWED")
        if self.reason is not None:
            object.__setattr__(self, "reason", _nonempty(self.reason, "reason"))

    @classmethod
    def proposal_response(cls, proposal: ExecutionProposal) -> "TradeResponse":
        return cls(PROTOCOL_VERSION, "PROPOSAL", proposal=proposal)

    @classmethod
    def no_trade(cls, reason: str | None = None) -> "TradeResponse":
        return cls(PROTOCOL_VERSION, "NO_TRADE", reason=reason)

    @classmethod
    def not_ready(cls, reason: str | None = None) -> "TradeResponse":
        return cls(PROTOCOL_VERSION, "NOT_READY", reason=reason)


@dataclass(frozen=True)
class ExecutionOutcome:
    protocol_version: str
    outcome_id: str
    proposal_id: str
    environment: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    initial_risk_usd: float
    realized_pnl_usd: float
    r_multiple: float
    mae_r: float
    mfe_r: float
    entry_timestamp_ms: int
    closed_timestamp_ms: int
    exit_reason: str
    entry_authority: str
    model_version: str
    exit_policy_version: str
    feature_version: str
    data_generation_id: str
    market_event_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "protocol_version", _version(self.protocol_version))
        for field in (
            "outcome_id", "proposal_id", "exit_reason", "entry_authority", "model_version",
            "exit_policy_version", "feature_version", "data_generation_id", "market_event_id",
        ):
            object.__setattr__(self, field, _nonempty(getattr(self, field), field))
        object.__setattr__(self, "environment", _choice(self.environment, "environment", VALID_ENVIRONMENTS))
        object.__setattr__(self, "symbol", _symbol(self.symbol))
        object.__setattr__(self, "side", _choice(self.side, "side", VALID_DIRECTIONS))
        for field in ("entry_price", "exit_price", "quantity", "initial_risk_usd"):
            object.__setattr__(self, field, _number(getattr(self, field), field, positive=True))
        for field in ("realized_pnl_usd", "r_multiple", "mae_r", "mfe_r"):
            object.__setattr__(self, field, _number(getattr(self, field), field))
        entered = _timestamp(self.entry_timestamp_ms, "entry_timestamp_ms")
        closed = _timestamp(self.closed_timestamp_ms, "closed_timestamp_ms")
        if closed < entered:
            raise ProtocolValidationError("PROTOCOL_OUTCOME_TIMESTAMP_ORDER_INVALID")
        object.__setattr__(self, "entry_timestamp_ms", entered)
        object.__setattr__(self, "closed_timestamp_ms", closed)

    @classmethod
    def create(cls, **kwargs: Any) -> "ExecutionOutcome":
        return cls(protocol_version=PROTOCOL_VERSION, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionOutcome":
        if not isinstance(payload, Mapping):
            raise ProtocolValidationError("PROTOCOL_PAYLOAD_NOT_OBJECT")
        required = set(cls.__dataclass_fields__)
        _keys(payload, required)
        return cls(**dict(payload))
