"""G4 OFFLINE-ONLY source and time gate for prospective counterfactual research.

This module NEVER computes a trade return, creates a SCORED label, writes a DB,
uses an exchange connection, proposes a trade or grants financial authority.
REPLAY_READY means independently replayable source prerequisites, NOT that
a verified economic outcome exists. The live G1/G2/G3 collector does not import it.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from nbot.v5.observation_contract import INTERVAL_MS, PATTERN_IDS, SIDES

CONTRACT_VERSION = "NBOT_V5_G4_OFFLINE_SOURCE_GATE_V1"
DEFAULT_HORIZON_MS = 4 * 60 * 60 * 1_000
GRADES = ("HISTORICAL_AGGTRADE_PATH", "QUOTE_CONSTRAINED_SIMULATION")
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")


@dataclass(frozen=True)
class ReplayGate:
    decision_id: str
    state: str                 # PENDING, HOLD, or REPLAY_READY (not SCORED)
    reasons: tuple[str, ...]
    evidence_grade: str | None
    contract_version: str = CONTRACT_VERSION
    scored_outcomes: int = 0
    order_authority: str = "NONE"
    recommendation_authority: str = "NONE"
    training_authority: str = "NONE"


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def _clock(value: object) -> bool:
    return type(value) is int and value >= 0


def _hold(decision_id: str, reasons: list[str], grade: str | None) -> ReplayGate:
    return ReplayGate(decision_id, "HOLD", tuple(sorted(set(reasons))), grade)


def assess_replay_prerequisites(
    *,
    candidate: Mapping,
    g3_context: Mapping,
    frozen_policy: Mapping,
    path_witness: Mapping | None,
    cost_witness: Mapping | None,
    audit_at_ms: int,
) -> ReplayGate:
    """Fail closed on unqualified, non-causal, un-matured or incomplete input.

    Must receive actual original source digests, a policy frozen no later than
    decision time, and a separately witnessed complete post-decision path.
    Costed quote-grade replay additionally requires independently witnessed
    quote/fee/slippage/funding coverage. This is NOT a simulator or labeler.
    """
    if not all(isinstance(x, Mapping) for x in (candidate, g3_context, frozen_policy)):
        raise ValueError("G4_INVALID_INPUT_SHAPE")
    if not _clock(audit_at_ms):
        raise ValueError("G4_INVALID_AUDIT_CLOCK")
    did = candidate.get("decision_id")
    if not _sha(did):
        raise ValueError("G4_DECISION_ID_INVALID")
    reasons: list[str] = []
    event = candidate.get("event_open_ms")
    decision = candidate.get("decision_at_ms")
    if (not _clock(event) or event % INTERVAL_MS or not _clock(decision)
            or decision < event + INTERVAL_MS or decision > audit_at_ms):
        return _hold(did, ["G4_DECISION_CLOCK_INVALID"], None)

    if candidate.get("status") != "OBSERVED" or candidate.get("reason_codes"):
        reasons.append("G4_CANDIDATE_NOT_SOURCE_QUALIFIED")
    if candidate.get("action") != "OBSERVE_ONLY" or candidate.get("order_authority") != "NONE":
        reasons.append("G4_CANDIDATE_AUTHORITY_INVALID")
    if candidate.get("side") not in SIDES or not candidate.get("symbol"):
        reasons.append("G4_CANDIDATE_IDENTITY_INVALID")
    if not _sha(candidate.get("source_digest")) or not _sha(candidate.get("btc_source_digest")):
        reasons.append("G4_CANDIDATE_SOURCE_DIGEST_MISSING")
    if not candidate.get("detector_version"):
        reasons.append("G4_DETECTOR_VERSION_MISSING")
    patterns = candidate.get("patterns")
    if (not isinstance(patterns, Mapping) or set(patterns) != set(PATTERN_IDS)
            or any(v not in ("MATCH", "NO_MATCH") for v in patterns.values())):
        reasons.append("G4_PATTERN_DENOMINATOR_UNQUALIFIED")
    if (g3_context.get("event_open_ms") != event
            or not _sha(g3_context.get("feature_sha256"))):
        reasons.append("G4_G3_CONTEXT_NOT_MATCHED")
    known_at = g3_context.get("valid_from_ms")
    if not _clock(known_at) or known_at > decision:
        reasons.append("G4_G3_CONTEXT_FUTURE_OR_UNKNOWN")

    horizon = frozen_policy.get("horizon_ms")
    declared = frozen_policy.get("declared_at_ms")
    if not _clock(horizon) or horizon <= 0 or horizon % INTERVAL_MS:
        reasons.append("G4_HORIZON_NOT_PREDECLARED")
    if not _clock(declared) or declared > decision:
        reasons.append("G4_POLICY_NOT_FROZEN_ASOF_DECISION")
    if (not _sha(frozen_policy.get("policy_sha256"))
            or not frozen_policy.get("entry_convention")
            or not frozen_policy.get("exit_policy_id")
            or not frozen_policy.get("risk_policy_id")):
        reasons.append("G4_EXIT_ENTRY_RISK_POLICY_INCOMPLETE")
    if reasons:
        return _hold(did, reasons, None)

    mature_at = decision + horizon
    if audit_at_ms < mature_at:
        return ReplayGate(did, "PENDING", ("G4_HORIZON_NOT_MATURE",), None)

    if not isinstance(path_witness, Mapping):
        return _hold(did, ["G4_PATH_MISSING_AFTER_MATURITY"], None)
    grade = path_witness.get("grade")
    if grade not in GRADES:
        reasons.append("G4_UNSUPPORTED_PATH_GRADE")
        grade = None
    if not _sha(path_witness.get("path_sha256")):
        reasons.append("G4_PRICE_PATH_DIGEST_MISSING")
    start = path_witness.get("start_ms")
    end = path_witness.get("end_ms")
    captured = path_witness.get("captured_at_ms")
    if (not _clock(start) or not _clock(end) or not _clock(captured)
            or start > decision or end < mature_at
            or captured > audit_at_ms or captured < end):
        reasons.append("G4_PATH_CLOCK_OR_COVERAGE_INVALID")
    if path_witness.get("continuous") is not True:
        reasons.append("G4_PATH_GAPPED_OR_UNPROVEN")
    if path_witness.get("source_verified") is not True:
        reasons.append("G4_PATH_PROVENANCE_UNVERIFIED")

    if grade == "QUOTE_CONSTRAINED_SIMULATION":
        if not isinstance(cost_witness, Mapping):
            reasons.append("G4_EXECUTABLE_COST_WITNESS_MISSING")
        else:
            for field in ("quote_sha256", "fee_schedule_sha256",
                          "slippage_model_sha256", "funding_sha256"):
                if not _sha(cost_witness.get(field)):
                    reasons.append("G4_EXECUTABLE_" + field.upper() + "_MISSING")
            covered = cost_witness.get("coverage_end_ms")
            if not _clock(covered) or covered < mature_at:
                reasons.append("G4_COST_HORIZON_NOT_VERIFIED")
            if cost_witness.get("source_verified") is not True:
                reasons.append("G4_COST_PROVENANCE_UNVERIFIED")
    if reasons:
        return _hold(did, reasons, grade)
    return ReplayGate(did, "REPLAY_READY", (), grade)
