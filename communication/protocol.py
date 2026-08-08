"""Shared, runtime-independent protocol validation for NBOT workers.

This package is intentionally limited to the Python standard library so both
future workers can import the message contracts without importing config,
strategy, engine, learning, exchange, risk, or state modules.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Iterable, Mapping


PROTOCOL_VERSION = "NBOT_EXECUTION_V1"

VALID_ENVIRONMENTS = frozenset({"TESTNET", "LIVE"})
VALID_EXECUTION_MODES = frozenset({"SHADOW", "TRADE"})
VALID_DIRECTIONS = frozenset({"LONG", "SHORT"})
VALID_SELECTION_AUTHORITIES = frozenset(
    {"RULES", "PAPER_CANARY", "PAPER_CHAMPION"}
)
VALID_TRADE_RESPONSE_STATUSES = frozenset(
    {"PROPOSAL", "NO_TRADE", "NOT_READY"}
)
VALID_OUTCOME_ACK_STATUSES = frozenset(
    {"RECORDED", "ALREADY_RECORDED"}
)

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,30}$")


class ProtocolValidationError(ValueError):
    """Raised when a worker message violates the versioned protocol."""


def require_mapping(payload: Any, *, name: str = "payload") -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ProtocolValidationError(f"PROTOCOL_{name.upper()}_NOT_OBJECT")
    return payload


def validate_payload_keys(
    payload: Mapping[str, Any],
    *,
    required: Iterable[str],
    optional: Iterable[str] = (),
) -> None:
    required_set = set(required)
    optional_set = set(optional)
    actual = set(payload)

    missing = sorted(required_set - actual)
    if missing:
        raise ProtocolValidationError(
            "PROTOCOL_MISSING_FIELDS:" + ",".join(missing)
        )

    unknown = sorted(actual - required_set - optional_set)
    if unknown:
        raise ProtocolValidationError(
            "PROTOCOL_UNKNOWN_FIELDS:" + ",".join(unknown)
        )


def require_nonempty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    normalized = value.strip()
    if not normalized:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return normalized


def optional_string(value: Any, *, field: str) -> str | None:
    if value is None:
        return None
    return require_nonempty_string(value, field=field)


def validate_protocol_version(value: Any) -> str:
    version = require_nonempty_string(value, field="protocol_version")
    if version != PROTOCOL_VERSION:
        raise ProtocolValidationError(
            f"PROTOCOL_VERSION_UNSUPPORTED:{version}"
        )
    return version


def _normalize_choice(value: Any, *, field: str, allowed: frozenset[str]) -> str:
    normalized = require_nonempty_string(value, field=field).upper()
    if normalized not in allowed:
        raise ProtocolValidationError(
            f"PROTOCOL_{field.upper()}_INVALID:{normalized}"
        )
    return normalized


def validate_environment(value: Any) -> str:
    return _normalize_choice(
        value,
        field="environment",
        allowed=VALID_ENVIRONMENTS,
    )


def validate_execution_mode(value: Any) -> str:
    return _normalize_choice(
        value,
        field="execution_mode",
        allowed=VALID_EXECUTION_MODES,
    )


def validate_direction(value: Any, *, field: str = "direction") -> str:
    return _normalize_choice(value, field=field, allowed=VALID_DIRECTIONS)


def validate_selection_authority(value: Any) -> str:
    return _normalize_choice(
        value,
        field="selection_authority",
        allowed=VALID_SELECTION_AUTHORITIES,
    )


def validate_trade_response_status(value: Any) -> str:
    return _normalize_choice(
        value,
        field="trade_response_status",
        allowed=VALID_TRADE_RESPONSE_STATUSES,
    )


def validate_outcome_ack_status(value: Any) -> str:
    return _normalize_choice(
        value,
        field="outcome_ack_status",
        allowed=VALID_OUTCOME_ACK_STATUSES,
    )


def validate_timestamp_ms(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return value


def finite_number(
    value: Any,
    *,
    field: str,
    allow_none: bool = False,
) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return result


def validate_symbol(value: Any) -> str:
    symbol = require_nonempty_string(value, field="symbol").upper()
    if not symbol.endswith("USDT") or _SYMBOL_RE.fullmatch(symbol) is None:
        raise ProtocolValidationError(f"PROTOCOL_SYMBOL_INVALID:{symbol}")
    return symbol


def validate_json_object(
    value: Any,
    *,
    field: str,
    allow_none: bool = True,
) -> dict[str, Any] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, dict):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_NOT_OBJECT")
    ensure_json_safe(value, field=field)
    return value


def ensure_json_safe(value: Any, *, field: str = "payload") -> None:
    try:
        json.dumps(
            value,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolValidationError(
            f"PROTOCOL_{field.upper()}_NOT_JSON_SAFE"
        ) from exc
