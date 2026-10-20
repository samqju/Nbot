"""Pure, deterministic V5.1 observation primitives. NOT a source/trade validator.

Historical reference (behavior only, NOT imported):
feature/v5-observation-integrated-20261014 @ 1e7c090d05dc118b290c764d58c2944f56ad4b3b,
nbot/v5/observation_contract.py blob 99b9544fe32239e7b707b6ea09a87a452210034b.

No market data is fetched, stored, qualified, or traded here. A source digest is
an identity hint, not independently verified original-source custody or PnL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re

INTERVAL_MS = 300_000
CORE_SCHEMA_VERSION = "NBOT_V5_1_CORE_V1"
_DOMAINS = frozenset({"event", "evidence", "intent"})
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PREFIX = re.compile(r"[A-Z][A-Z0-9_]*\Z")
_ROUTE_STATES = frozenset({"HEALTHY", "GAP", "UNKNOWN"})


class ObservationAuthority(str, Enum):
    """No paper, real, testnet, or virtual order authority in G1-01."""

    NONE = "NONE"


class ObservationDisposition(str, Enum):
    """An observation or abstention is never an instruction to trade."""

    OBSERVE_ONLY = "OBSERVE_ONLY"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class FiveMinuteEvent:
    """A closed five-minute event evaluated at an explicit known-at time."""

    event_open_ms: int
    decision_at_ms: int

    def __post_init__(self) -> None:
        if (type(self.event_open_ms) is not int
                or self.event_open_ms < 0
                or self.event_open_ms % INTERVAL_MS != 0
                or type(self.decision_at_ms) is not int
                or self.decision_at_ms < self.event_open_ms + INTERVAL_MS):
            raise ValueError("V5_1_EVENT_NOT_CLOSED_OR_INVALID")

    @property
    def event_close_ms(self) -> int:
        return self.event_open_ms + INTERVAL_MS


@dataclass(frozen=True)
class SourceEvidence:
    """Untrusted source metadata, not proof of original exchange evidence."""

    last_closed_bar_open_ms: int
    source_max_bar_open_ms: int
    observed_at_ms: int
    source_digest: str | None
    source_epoch: int | None
    route_state: str
    quality_issues: tuple[str, ...] = ()


def evidence_hold_reasons(
    event: FiveMinuteEvent, evidence: SourceEvidence | None, *, prefix: str
) -> tuple[str, ...]:
    """Fail closed with deterministic reasons; do NOT qualify original data.

    Even an empty reason list only means *reported metadata* is internally
    consistent. Independent source custody, candle authenticity, complete
    economics, and trade admission require later separate validated stages.
    """
    if not isinstance(event, FiveMinuteEvent):
        raise TypeError("V5_1_EVENT_TYPE_INVALID")
    if type(prefix) is not str or _PREFIX.fullmatch(prefix) is None:
        raise ValueError("V5_1_REASON_PREFIX_INVALID")
    if evidence is None:
        return (f"{prefix}_MISSING",)
    if not isinstance(evidence, SourceEvidence):
        raise TypeError("V5_1_EVIDENCE_TYPE_INVALID")

    reasons: set[str] = set()
    if type(evidence.quality_issues) is not tuple:
        reasons.add("QUALITY_ISSUES_INVALID")
    else:
        for issue in evidence.quality_issues:
            if type(issue) is not str or _PREFIX.fullmatch(issue) is None:
                reasons.add("QUALITY_ISSUES_INVALID")
            else:
                reasons.add(issue)

    times = (
        evidence.last_closed_bar_open_ms,
        evidence.source_max_bar_open_ms,
        evidence.observed_at_ms,
    )
    if any(type(t) is not int or t < 0 for t in times):
        reasons.add("INVALID_TIMESTAMPS")
    else:
        if (evidence.last_closed_bar_open_ms % INTERVAL_MS != 0
                or evidence.source_max_bar_open_ms % INTERVAL_MS != 0):
            reasons.add("INVALID_TIMESTAMPS")
        if evidence.last_closed_bar_open_ms != event.event_open_ms:
            reasons.add("CANDLE_MISSING_OR_STALE")
            if evidence.last_closed_bar_open_ms > event.event_open_ms:
                reasons.add("CANDLE_FUTURE")
        if evidence.source_max_bar_open_ms != event.event_open_ms:
            reasons.add("SOURCE_NOT_ASOF_EVENT")
            if evidence.source_max_bar_open_ms > event.event_open_ms:
                reasons.add("SOURCE_FUTURE")
        if not event.event_close_ms <= evidence.observed_at_ms <= event.decision_at_ms:
            reasons.add("OBSERVATION_TIME_INVALID")

    if type(evidence.route_state) is not str or evidence.route_state not in _ROUTE_STATES:
        reasons.add("ROUTE_INVALID")
    elif evidence.route_state != "HEALTHY":
        reasons.add("ROUTE_UNHEALTHY")

    if evidence.source_digest is None:
        reasons.add("SOURCE_DIGEST_MISSING")
    elif type(evidence.source_digest) is not str or _DIGEST.fullmatch(evidence.source_digest) is None:
        reasons.add("SOURCE_DIGEST_INVALID")

    if type(evidence.source_epoch) is not int or evidence.source_epoch < 0:
        reasons.add("SOURCE_EPOCH_INVALID")

    return tuple(f"{prefix}_{reason}" for reason in sorted(reasons))


def _check_json(value: object, active: set[int]) -> None:
    """Reject ambiguous float encodings, objects and reference cycles."""
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) in (dict, list):
        identity = id(value)
        if identity in active:
            raise ValueError("V5_1_JSON_CIRCULAR")
        active.add(identity)
        try:
            if type(value) is dict:
                for key, item in value.items():
                    if type(key) is not str:
                        raise ValueError("V5_1_JSON_KEY_INVALID")
                    _check_json(item, active)
            else:
                for item in value:
                    _check_json(item, active)
        finally:
            active.remove(identity)
        return
    raise ValueError("V5_1_JSON_VALUE_INVALID")


def canonical_digest(domain: str, payload: object) -> str:
    """Version- and domain-separated stable ID, not a source authenticity proof.

    Only exact JSON primitives are permitted. Floats are rejected so unstable
    binary prices cannot silently become precision-dependent identity fields.
    """
    if type(domain) is not str or domain not in _DOMAINS:
        raise ValueError("V5_1_ID_DOMAIN_INVALID")
    _check_json(payload, set())
    encoded = json.dumps(
        {"schema": CORE_SCHEMA_VERSION, "domain": domain, "payload": payload},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

