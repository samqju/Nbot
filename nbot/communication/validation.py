"""Strict runtime-independent validation for the NBOT V3 control protocol.

This module intentionally imports only the Python standard library.  Both VPS
roles can validate wire messages without importing execution, observation,
research, exchange, or configuration runtimes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Iterable, Mapping


PROTOCOL_VERSION = "NBOT_V3_EXECUTION_V1"
PROPOSAL_SCHEMA_VERSION = "NBOT_V3_EXECUTION_PROPOSAL_V1"
OUTCOME_SCHEMA_VERSION = "NBOT_V3_EXECUTION_OUTCOME_V1"

VALID_RESPONSE_STATUSES = frozenset({"PROPOSAL", "NO_TRADE", "NOT_READY"})
VALID_ACK_STATUSES = frozenset({"RECORDED", "ALREADY_RECORDED"})
VALID_DIRECTIONS = frozenset({"LONG", "SHORT"})
VALID_EXECUTION_STATES = frozenset({"FLAT"})
VALID_PREVIOUS_PROPOSAL_RESULTS = frozenset({"REJECTED", "NOT_EXECUTED"})

# Duplicated here deliberately so communication contracts remain independent
# of nbot.config.  Any mismatch is therefore caught at the wire boundary.
PROFILE_CONTRACTS: dict[str, tuple[str, str, str]] = {
    "testnet-trade": ("TESTNET", "TRADE", "TESTNET_OPERATIONAL_ONLY"),
    "live-paper": ("LIVE", "PAPER", "LIVE_PAPER_OPERATIONAL"),
    "live-trade": ("LIVE", "TRADE", "LIVE_REAL_CAPITAL"),
}

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,30}$")
_HEX_RE = re.compile(r"^[0-9a-f]+$")


class ProtocolValidationError(ValueError):
    """A control-plane message violates the frozen V3 protocol."""


def require_mapping(value: Any, *, field: str = "payload") -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_NOT_OBJECT")
    return value


def validate_keys(
    payload: Mapping[str, Any],
    *,
    required: Iterable[str],
    optional: Iterable[str] = (),
) -> None:
    required_set = set(required)
    optional_set = set(optional)
    actual = set(payload)
    missing = sorted(required_set - actual)
    unknown = sorted(actual - required_set - optional_set)
    if missing:
        raise ProtocolValidationError("PROTOCOL_MISSING_FIELDS:" + ",".join(missing))
    if unknown:
        raise ProtocolValidationError("PROTOCOL_UNKNOWN_FIELDS:" + ",".join(unknown))


def text(value: Any, field: str, *, max_length: int = 256) -> str:
    if not isinstance(value, str):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    normalized = value.strip()
    if not normalized or normalized != value or len(normalized) > max_length:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in normalized):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return normalized


def optional_text(value: Any, field: str, *, max_length: int = 256) -> str | None:
    if value is None:
        return None
    return text(value, field, max_length=max_length)


def integer(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    if minimum is not None and value < minimum:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return value


def timestamp_ms(value: Any, field: str) -> int:
    return integer(value, field, minimum=1)


def number(
    value: Any,
    field: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
    allow_none: bool = False,
) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    if positive and result <= 0:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    if nonnegative and result < 0:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return 0.0 if result == 0.0 else result


def choice(value: Any, field: str, allowed: frozenset[str]) -> str:
    normalized = text(value, field).upper()
    if normalized not in allowed:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID:{normalized}")
    return normalized


def symbol(value: Any) -> str:
    normalized = text(value, "symbol", max_length=30).upper()
    if not normalized.endswith("USDT") or _SYMBOL_RE.fullmatch(normalized) is None:
        raise ProtocolValidationError(f"PROTOCOL_SYMBOL_INVALID:{normalized}")
    return normalized


def protocol_version(value: Any) -> str:
    version = text(value, "protocol_version")
    if version != PROTOCOL_VERSION:
        raise ProtocolValidationError(f"PROTOCOL_VERSION_UNSUPPORTED:{version}")
    return version


def proposal_schema_version(value: Any) -> str:
    version = text(value, "proposal_schema_version")
    if version != PROPOSAL_SCHEMA_VERSION:
        raise ProtocolValidationError(f"PROPOSAL_SCHEMA_VERSION_UNSUPPORTED:{version}")
    return version


def outcome_schema_version(value: Any) -> str:
    version = text(value, "outcome_schema_version")
    if version != OUTCOME_SCHEMA_VERSION:
        raise ProtocolValidationError(f"OUTCOME_SCHEMA_VERSION_UNSUPPORTED:{version}")
    return version


def git_sha(value: Any, field: str = "release_sha") -> str:
    sha = text(value, field, max_length=64).lower()
    if not (7 <= len(sha) <= 64) or _HEX_RE.fullmatch(sha) is None:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return sha


def digest(value: Any, field: str) -> str:
    result = text(value, field, max_length=64).lower()
    if len(result) != 64 or _HEX_RE.fullmatch(result) is None:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_INVALID")
    return result


def optional_digest(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return digest(value, field)


def json_object(value: Any, field: str, *, allow_none: bool = True) -> dict[str, Any] | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, dict):
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_NOT_OBJECT")
    canonical_json(value, field=field)
    return dict(value)


def canonical_json(value: Any, *, field: str = "payload") -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ProtocolValidationError(f"PROTOCOL_{field.upper()}_NOT_JSON_SAFE") from exc


def payload_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_profile_contract(
    *,
    profile: Any,
    market_environment: Any,
    execution_mode: Any,
    evidence_lineage: Any | None = None,
) -> tuple[str, str, str, str]:
    profile_name = text(profile, "profile", max_length=40).lower()
    try:
        expected_environment, expected_mode, expected_lineage = PROFILE_CONTRACTS[profile_name]
    except KeyError as exc:
        raise ProtocolValidationError(f"PROTOCOL_PROFILE_INVALID:{profile_name}") from exc
    environment = choice(
        market_environment,
        "market_environment",
        frozenset({"TESTNET", "LIVE"}),
    )
    mode = choice(execution_mode, "execution_mode", frozenset({"TRADE", "PAPER"}))
    if environment != expected_environment:
        raise ProtocolValidationError("PROTOCOL_PROFILE_ENVIRONMENT_MISMATCH")
    if mode != expected_mode:
        raise ProtocolValidationError("PROTOCOL_PROFILE_EXECUTION_MODE_MISMATCH")
    if evidence_lineage is None:
        lineage = expected_lineage
    else:
        lineage = text(evidence_lineage, "evidence_lineage", max_length=80)
        if lineage != expected_lineage:
            raise ProtocolValidationError("PROTOCOL_PROFILE_EVIDENCE_LINEAGE_MISMATCH")
    return profile_name, environment, mode, lineage
