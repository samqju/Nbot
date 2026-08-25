"""V3.9.5 operational-regime evidence ledger.

This module is Observation-owned governance metadata only. It records which
operational regimes already have accepted historical evidence, which have safe
deterministic equivalents, and which cannot be proven until a Research/Paper
Champion authority actually exists. It never mutates recommendation or
Execution authority and never manufactures a PASS for a condition that has not
occurred.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .challengers import AUTHORITY
from .research_memory import ResearchMemoryStore


VERSION = "V39_OPERATIONAL_REGIME_LEDGER_V1"
CONTRACT_KEY = f"v39:operational-regime:contract:{VERSION}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class OperationalRegimeRequirement:
    regime_id: str
    roadmap_label: str
    evidence_class: str
    status: str
    evidence_reference: str
    paper_champion_treatment: str


REQUIREMENTS: tuple[OperationalRegimeRequirement, ...] = (
    OperationalRegimeRequirement(
        "OBSERVATION_RESTART", "Observation restart",
        "ACCEPTED_HISTORICAL_PHYSICAL", "EVIDENCE_ACCEPTED",
        "V3.7-C Observation dies while position OPEN; V3.8 Observation outage/recovery acceptance",
        "CARRY_FORWARD_AS_OPERATIONAL_EVIDENCE",
    ),
    OperationalRegimeRequirement(
        "EXECUTION_RESTART", "Execution restart",
        "ACCEPTED_HISTORICAL_PHYSICAL", "EVIDENCE_ACCEPTED",
        "V3.2.4 protected restart recovery and V3.7-G restart/reconcile-before-request",
        "CARRY_FORWARD_AS_OPERATIONAL_EVIDENCE",
    ),
    OperationalRegimeRequirement(
        "NETWORK_INTERRUPTION", "network interruption",
        "ACCEPTED_HISTORICAL_PHYSICAL", "EVIDENCE_ACCEPTED",
        "V3.7-D control-link loss while OPEN; flat-mode link failure remains fail-closed",
        "CARRY_FORWARD_AS_OPERATIONAL_EVIDENCE",
    ),
    OperationalRegimeRequirement(
        "PUBLIC_FEED_RECOVERY", "public-feed reconnect",
        "DETERMINISTIC_EQUIVALENT", "EQUIVALENT_AVAILABLE",
        "Current Observation feed is REST-cycle based: transient BinancePublicMarketError -> bounded wait -> successful next collection cycle",
        "REVERIFY_ON_CURRENT_RELEASE_BEFORE_PAPER_CHAMPION",
    ),
    OperationalRegimeRequirement(
        "LARGE_DB_GROWTH", "large DB growth",
        "ACCEPTED_HISTORICAL_PHYSICAL", "EVIDENCE_ACCEPTED",
        "V3.8.1R/V3.8.2/V3.8.3 scale defect, bounded lifecycle and V3.8.4 physical 96-event epoch acceptance",
        "CARRY_FORWARD_WITH_CURRENT_STORAGE_AUDIT",
    ),
    OperationalRegimeRequirement(
        "HEAVY_TRAINING_CPU", "heavy training CPU",
        "ACCEPTED_HISTORICAL_PHYSICAL", "EVIDENCE_ACCEPTED",
        "V3.7-U heavy Observation research-load independence plus V3.8.3/V3.8.4 high-CPU research with collector priority",
        "CARRY_FORWARD_WITH_CURRENT_RESOURCE_PRIORITY_AUDIT",
    ),
    OperationalRegimeRequirement(
        "DISK_PRESSURE_ALERT", "disk pressure alert",
        "DETERMINISTIC_EQUIVALENT", "EQUIVALENT_AVAILABLE",
        "Foundation doctor has explicit DISK_FREE_TOO_LOW warning gate; destructive disk-filling is not required",
        "REVERIFY_ALERT_PATH_ON_CURRENT_RELEASE",
    ),
    OperationalRegimeRequirement(
        "MODEL_PROMOTION", "model promotion",
        "DEFERRED_BY_AUTHORITY_BOUNDARY", "NOT_YET_APPLICABLE",
        "V3.9.2/.3 automatic promotion is disabled; no Research Champion exists",
        "MUST_BE_PROVEN_IF_AND_WHEN_PROMOTION_IS_ENABLED",
    ),
    OperationalRegimeRequirement(
        "MODEL_ROLLBACK", "model rollback",
        "DEFERRED_BY_AUTHORITY_BOUNDARY", "NOT_YET_APPLICABLE",
        "V3.9.2/.3 rollback state is DISABLED_NO_RESEARCH_CHAMPION",
        "MUST_BE_PROVEN_IF_AND_WHEN_ROLLBACK_IS_ENABLED",
    ),
    OperationalRegimeRequirement(
        "OPERATOR_TELEGRAM_FAILURE", "operator/Telegram failure",
        "ACCEPTED_HISTORICAL_RELEASE_REGRESSION", "EVIDENCE_ACCEPTED",
        "V3.8 operator/Telegram best-effort isolation, bounded polling backoff and stale-command discard on accepted release",
        "CARRY_FORWARD_AND_KEEP_REGRESSION_GREEN",
    ),
)


class OperationalRegimeLedger:
    """Immutable V3.9.5 requirement/evidence classification ledger."""

    def __init__(self, memory: ResearchMemoryStore) -> None:
        self.memory = memory

    def contract(self) -> dict[str, Any]:
        requirements = [
            {
                "regime_id": r.regime_id,
                "roadmap_label": r.roadmap_label,
                "evidence_class": r.evidence_class,
                "status": r.status,
                "evidence_reference": r.evidence_reference,
                "paper_champion_treatment": r.paper_champion_treatment,
            }
            for r in REQUIREMENTS
        ]
        return {
            "version": VERSION,
            "authority": AUTHORITY,
            "roadmap_scope": "V3.9.5_OPERATIONAL_REGIMES",
            "requirements": requirements,
            "requirement_count": len(requirements),
            "historical_evidence_rule": "ACCEPTED_PHYSICAL_EVIDENCE_IS_NOT_DESTRUCTIVELY_REPEATED_WITHOUT_A_NEW_REASON",
            "equivalent_rule": "SAFE_DETERMINISTIC_EQUIVALENTS_MUST_REMAIN_EXPLICITLY_DISTINGUISHED_FROM_PHYSICAL_EVIDENCE",
            "deferred_authority_rule": "PROMOTION_ROLLBACK_CANNOT_BE_PROVEN_BEFORE_THEIR_AUTHORITY_EXISTS",
            "paper_champion_rule": "NO_OPERATIONAL_LEDGER_RECORD_CREATES_RESEARCH_OR_PAPER_CHAMPION_AUTHORITY",
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    @property
    def contract_hash(self) -> str:
        return _digest(self.contract())

    def sync(self) -> dict[str, Any]:
        stored = self.memory.persist_artifact(CONTRACT_KEY, self.contract())
        return {
            "version": VERSION,
            "contract_hash": self.contract_hash,
            "contract_artifact_digest": stored["artifact_digest"],
            "status": self.status(),
        }

    def status(self) -> dict[str, Any]:
        record = self.memory.artifact(CONTRACT_KEY)
        contract = self.contract() if record is None else record["payload"]
        rows = list(contract["requirements"])
        accepted = [r for r in rows if r["status"] == "EVIDENCE_ACCEPTED"]
        equivalents = [r for r in rows if r["status"] == "EQUIVALENT_AVAILABLE"]
        deferred = [r for r in rows if r["status"] == "NOT_YET_APPLICABLE"]
        return {
            "version": VERSION,
            "authority": AUTHORITY,
            "contract_initialized": record is not None,
            "contract_hash": _digest(contract),
            "requirement_count": len(rows),
            "accepted_evidence_count": len(accepted),
            "deterministic_equivalent_count": len(equivalents),
            "deferred_authority_count": len(deferred),
            "accepted_regimes": [r["regime_id"] for r in accepted],
            "equivalent_regimes": [r["regime_id"] for r in equivalents],
            "deferred_regimes": [r["regime_id"] for r in deferred],
            "requirements": rows,
            "campaign_status": "PARTIAL_PENDING_CURRENT_RELEASE_RECHECKS_AND_FUTURE_AUTHORITY_EVENTS",
            "all_required_operational_regimes_proven": False,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    def audit(self) -> dict[str, Any]:
        report = {
            "version": VERSION,
            "healthy": True,
            "missing_contract": 0,
            "contract_hash_mismatch": 0,
            "requirement_count_mismatch": 0,
            "authority_violation": 0,
            "premature_operational_pass": 0,
        }
        record = self.memory.artifact(CONTRACT_KEY)
        if record is None:
            report["missing_contract"] = 1
        else:
            payload = record["payload"]
            if _digest(payload) != self.contract_hash:
                report["contract_hash_mismatch"] = 1
            if int(payload.get("requirement_count", -1)) != len(REQUIREMENTS):
                report["requirement_count_mismatch"] = 1
            if (
                payload.get("authority") != AUTHORITY
                or payload.get("automatic_promotion") is not False
                or payload.get("paper_champion_authority") is not False
                or payload.get("execution_authority") != "NONE"
            ):
                report["authority_violation"] = 1
        status = self.status()
        if status.get("all_required_operational_regimes_proven") is not False:
            report["premature_operational_pass"] = 1
        report["healthy"] = not any(
            int(value) for key, value in report.items()
            if key not in {"version", "healthy"}
        )
        return report
