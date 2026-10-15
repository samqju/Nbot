"""G1-02 nontrading configuration, evidence grades, and always-veto guardian.

These are pure contracts only. No mode enables any network connection or order.
No declared evidence grade here is promoted to original verified custody.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from .core import (
    FiveMinuteEvent,
    ObservationAuthority,
    ObservationDisposition,
    SourceEvidence,
    evidence_hold_reasons,
)

FOUNDATION_SCHEMA_VERSION = "NBOT_V5_1_FOUNDATION_V1"
_SYMBOL = re.compile(r"[A-Z0-9]{3,24}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class RunMode(str, Enum):
    OFFLINE = "OFFLINE"
    OBSERVATION = "OBSERVATION"
    VIRTUAL_RESEARCH = "VIRTUAL_RESEARCH"
    CHAMPION_PAPER = "CHAMPION_PAPER"
    CHALLENGER_PAPER = "CHALLENGER_PAPER"
    REAL = "REAL"


class EvidenceGrade(str, Enum):
    UNKNOWN = "UNKNOWN"
    SYNTHETIC = "SYNTHETIC"
    METADATA_ONLY = "METADATA_ONLY"
    ORIGINAL_VERIFIED = "ORIGINAL_VERIFIED"  # vocabulary only; NOT attainable here
    AFTER_COST_QUALIFIED = "AFTER_COST_QUALIFIED"  # vocabulary only


class ProposalSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True)
class RunConfig:
    """A single safe in-process configuration. Not an exchange enablement API."""

    mode: RunMode = RunMode.OFFLINE
    network_enabled: bool = False
    order_enabled: bool = False

    def __post_init__(self) -> None:
        if type(self.mode) is not RunMode:
            raise ValueError("G1_MODE_INVALID")
        if type(self.network_enabled) is not bool or type(self.order_enabled) is not bool:
            raise ValueError("G1_CAPABILITY_TYPE_INVALID")
        if self.mode not in (RunMode.OFFLINE, RunMode.OBSERVATION):
            raise ValueError("G1_MODE_UNRELEASED")
        if self.network_enabled or self.order_enabled:
            raise ValueError("G1_CAPABILITY_LOCKED")


@dataclass(frozen=True)
class ProposalEnvelope:
    """A proposed observation identity, NOT a permission to trade."""

    event: FiveMinuteEvent
    symbol: str
    side: ProposalSide
    proposal_id: str
    proposed_at_ms: int
    expires_at_ms: int
    evidence_grade: EvidenceGrade = EvidenceGrade.UNKNOWN
    model_digest: str | None = None

    def __post_init__(self) -> None:
        if type(self.event) is not FiveMinuteEvent:
            raise ValueError("G1_EVENT_INVALID")
        if type(self.symbol) is not str or _SYMBOL.fullmatch(self.symbol) is None:
            raise ValueError("G1_SYMBOL_INVALID")
        if type(self.side) is not ProposalSide:
            raise ValueError("G1_SIDE_INVALID")
        if type(self.proposal_id) is not str or _SHA.fullmatch(self.proposal_id) is None:
            raise ValueError("G1_PROPOSAL_ID_INVALID")
        if (type(self.proposed_at_ms) is not int or type(self.expires_at_ms) is not int
                or self.proposed_at_ms < self.event.event_close_ms
                or self.proposed_at_ms > self.event.decision_at_ms
                or self.expires_at_ms < self.proposed_at_ms):
            raise ValueError("G1_PROPOSAL_TIME_INVALID")
        if type(self.evidence_grade) is not EvidenceGrade:
            raise ValueError("G1_GRADE_INVALID")
        if self.evidence_grade not in (EvidenceGrade.UNKNOWN, EvidenceGrade.SYNTHETIC,
                                       EvidenceGrade.METADATA_ONLY):
            raise ValueError("G1_EVIDENCE_UPGRADE_FORBIDDEN")
        if self.model_digest is not None and (type(self.model_digest) is not str
                                              or _SHA.fullmatch(self.model_digest) is None):
            raise ValueError("G1_MODEL_ID_INVALID")


@dataclass(frozen=True)
class GuardianVerdict:
    authority: ObservationAuthority
    disposition: ObservationDisposition
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        # No alternative authority can be constructed from this module's verdict.
        if self.authority is not ObservationAuthority.NONE:
            raise ValueError("G1_ORDER_AUTHORITY_FORBIDDEN")
        if self.disposition not in (ObservationDisposition.NO_TRADE,
                                    ObservationDisposition.HOLD):
            raise ValueError("G1_GUARDIAN_DISPOSITION_INVALID")
        if (type(self.reasons) is not tuple or not self.reasons
                or any(type(x) is not str for x in self.reasons)
                or tuple(sorted(set(self.reasons))) != self.reasons):
            raise ValueError("G1_REASONS_INVALID")


def inspect_proposal(
    config: RunConfig,
    proposal: ProposalEnvelope | None,
    *,
    btc: SourceEvidence | None = None,
    symbol: SourceEvidence | None = None,
) -> GuardianVerdict:
    """Always refuse a trade; source health is only checked for audit reasons.

    No model authentication, original-source custody or owner release mechanism
    exists in G1. A caller cannot transform a clean result into order authority.
    """
    if type(config) is not RunConfig:
        raise ValueError("G1_CONFIG_INVALID")
    reasons = {"G1_NONTRADING_ONLY", "ORDER_AUTHORITY_NONE"}
    if proposal is None:
        reasons.add("PROPOSAL_MISSING")
    elif type(proposal) is not ProposalEnvelope:
        reasons.add("PROPOSAL_INVALID")
    else:
        for prefix, evidence in (("BTC", btc), ("SYMBOL", symbol)):
            try:
                reasons.update(evidence_hold_reasons(proposal.event, evidence, prefix=prefix))
            except (TypeError, ValueError):
                # The guardian must veto malformed inputs rather than crash open.
                reasons.add(f"{prefix}_EVIDENCE_INVALID")
        if proposal.expires_at_ms < proposal.event.decision_at_ms:
            reasons.add("PROPOSAL_EXPIRED")
        if proposal.side is not ProposalSide.NO_TRADE:
            reasons.add("TRADE_PROPOSAL_VETOED")
        if proposal.model_digest is None:
            reasons.add("MODEL_UNAPPROVED")
        else:
            reasons.add("MODEL_ATTESTATION_UNAVAILABLE")
        if proposal.evidence_grade is EvidenceGrade.SYNTHETIC:
            reasons.add("SYNTHETIC_NOT_ORIGINAL")
        else:
            reasons.add("ORIGINAL_CUSTODY_UNVERIFIED")
    # The base veto remains even when all reported market metadata is healthy.
    return GuardianVerdict(ObservationAuthority.NONE, ObservationDisposition.NO_TRADE,
                           tuple(sorted(reasons)))
