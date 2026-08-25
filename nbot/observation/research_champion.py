"""V3.9.6B explicit Research Champion promotion boundary.

Promotion is Observation-only governance.  It may mutate the immutable Research
Champion pointer only after the already-frozen V3.9.3 eligibility gate passes.
It never grants Paper Champion, Execution, Binance-order, or real-capital
authority and it never auto-promotes a challenger.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .challengers import AUTHORITY, CHALLENGER_PREFIX, EVALUATION_PREFIX
from .governance import (
    CHALLENGER_REGISTRY_PREFIX,
    CHAMPION_POINTER_GENESIS_KEY,
    MODEL_REGISTRY_PREFIX,
    REGISTRY_VERSION,
    ROLLBACK_STATE_GENESIS_KEY,
    ModelGovernanceRegistry,
)
from .research_memory import ResearchMemoryStore


VERSION = "V39_RESEARCH_CHAMPION_PROMOTION_V1"
CONTRACT_KEY = f"v39:research-champion:contract:{VERSION}"
PROMOTION_PREFIX = "v39:research-champion:promotion:"
MODEL_ROLE_PREFIX = "v39:registry:model-role:"
CHAMPION_POINTER_PREFIX = "v39:registry:champion-pointer:"
ROLLBACK_STATE_PREFIX = "v39:registry:rollback-state:"
CONFIRMATION = "PROMOTE_ELIGIBLE_V39_RESEARCH_CHAMPION"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchChampionPromotionConfig:
    version: str = VERSION
    required_eligibility_decision: str = "ELIGIBLE_FOR_RESEARCH_CHAMPION_REVIEW"
    candidate_rule: str = "MODEL_ATTACHED_TO_LATEST_WINDOW_IN_FROZEN_ELIGIBILITY_BASIS"
    promotion_mode: str = "EXPLICIT_OPERATOR_AFTER_FROZEN_ELIGIBILITY"
    replacement_policy: str = "FIRST_RESEARCH_CHAMPION_ONLY_REPLACEMENT_DEFERRED"


CONFIG = ResearchChampionPromotionConfig()


class ResearchChampionPromotion:
    """Fail-closed first Research Champion activation."""

    def __init__(
        self,
        memory: ResearchMemoryStore,
        governance: ModelGovernanceRegistry,
        *,
        config: ResearchChampionPromotionConfig = CONFIG,
    ) -> None:
        self.memory = memory
        self.governance = governance
        self.config = config

    def contract(self) -> dict[str, Any]:
        return {
            "version": self.config.version,
            "authority": AUTHORITY,
            "required_eligibility_version": self.governance.config.eligibility_version,
            "required_eligibility_decision": self.config.required_eligibility_decision,
            "candidate_rule": self.config.candidate_rule,
            "promotion_mode": self.config.promotion_mode,
            "replacement_policy": self.config.replacement_policy,
            "confirmation": CONFIRMATION,
            "evidence_rule": "POINTER_MUTATION_REFERENCES_IMMUTABLE_ELIGIBILITY_BASIS_AND_LATEST_PASS_WINDOW",
            "historical_rejection_rule": "NEVER_REWRITE_OR_RECLASSIFY_PRIOR_FINAL_WINDOWS",
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
        }

    @property
    def contract_hash(self) -> str:
        return _digest(self.contract())

    def sync(self) -> dict[str, Any]:
        record = self.memory.persist_artifact(CONTRACT_KEY, self.contract())
        return {
            "version": VERSION,
            "contract_hash": self.contract_hash,
            "contract_artifact_digest": record["artifact_digest"],
            "review": self.review(),
        }

    def _latest_pointer(self) -> dict[str, Any] | None:
        records = self.memory.list_artifacts(prefix=CHAMPION_POINTER_PREFIX)
        if not records:
            genesis = self.memory.artifact(CHAMPION_POINTER_GENESIS_KEY)
            return None if genesis is None else genesis["payload"]
        records.sort(key=lambda row: (
            int(row["payload"].get("generation", -1)),
            int(row["recorded_at_ms"]),
            str(row["artifact_key"]),
        ))
        return records[-1]["payload"]

    def _candidate_from_eligibility(self, eligibility: dict[str, Any]) -> dict[str, Any] | None:
        if eligibility.get("decision") != self.config.required_eligibility_decision:
            return None
        if eligibility.get("eligible_for_research_champion_review") is not True:
            return None
        basis = [str(value) for value in eligibility.get("window_basis") or []]
        if len(basis) != int(self.governance.config.min_consecutive_pass_windows):
            raise RuntimeError("NBOT_V396B_ELIGIBILITY_BASIS_COUNT_INVALID")
        latest = basis[-1]
        challenger = self.memory.artifact(CHALLENGER_PREFIX + latest)
        evaluation = self.memory.artifact(EVALUATION_PREFIX + latest)
        if challenger is None or evaluation is None:
            raise RuntimeError("NBOT_V396B_ELIGIBLE_ARTIFACT_REFERENCE_MISSING")
        if str(evaluation["payload"].get("status")) != "PASS_RESEARCH_GATE":
            raise RuntimeError("NBOT_V396B_LATEST_WINDOW_NOT_PASS")
        model_version = str(challenger["payload"]["model_version"])
        if str(evaluation["payload"].get("model_version")) != model_version:
            raise RuntimeError("NBOT_V396B_MODEL_REFERENCE_MISMATCH")
        model_registry = self.memory.artifact(MODEL_REGISTRY_PREFIX + model_version)
        challenger_registry = self.memory.artifact(CHALLENGER_REGISTRY_PREFIX + latest)
        if model_registry is None or challenger_registry is None:
            raise RuntimeError("NBOT_V396B_REGISTRY_REFERENCE_MISSING")
        return {
            "challenger_version": latest,
            "model_version": model_version,
            "window_basis": basis,
            "model_registry_artifact_digest": model_registry["artifact_digest"],
            "challenger_registry_artifact_digest": challenger_registry["artifact_digest"],
            "final_evaluation_artifact_digest": evaluation["artifact_digest"],
            "final_evaluation_digest": evaluation["payload"].get("evaluation_digest"),
        }

    def review(self) -> dict[str, Any]:
        status = self.governance.status()
        eligibility = status["research_champion_eligibility"]
        candidate = self._candidate_from_eligibility(eligibility)
        pointer = self._latest_pointer()
        current = None if pointer is None else pointer.get("current_research_champion")
        if current is not None:
            decision = "RESEARCH_CHAMPION_ALREADY_ACTIVE"
        elif candidate is None:
            decision = "WAIT_FOR_FROZEN_RESEARCH_ELIGIBILITY"
        else:
            decision = "READY_FOR_EXPLICIT_RESEARCH_CHAMPION_PROMOTION"
        return {
            "version": VERSION,
            "contract_initialized": self.memory.artifact(CONTRACT_KEY) is not None,
            "contract_hash": self.contract_hash,
            "decision": decision,
            "eligibility": eligibility,
            "candidate": candidate,
            "current_research_champion": current,
            "confirmation_required": CONFIRMATION,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }

    def promote(self, *, confirm: str) -> dict[str, Any]:
        if str(confirm) != CONFIRMATION:
            raise ValueError("NBOT_V396B_RESEARCH_CHAMPION_CONFIRMATION_REQUIRED")
        self.memory.persist_artifact(CONTRACT_KEY, self.contract())
        # Synchronize derived registry/rolling records before the authority decision.
        self.governance.sync()
        review = self.review()
        candidate = review.get("candidate")
        current = review.get("current_research_champion")
        if current is not None:
            if candidate is not None and str(current) == str(candidate["model_version"]):
                return {"result": "ALREADY_PROMOTED", "review": review}
            raise RuntimeError("NBOT_V396B_RESEARCH_CHAMPION_REPLACEMENT_DEFERRED")
        if review.get("decision") != "READY_FOR_EXPLICIT_RESEARCH_CHAMPION_PROMOTION" or candidate is None:
            raise RuntimeError("NBOT_V396B_RESEARCH_CHAMPION_NOT_ELIGIBLE")

        eligibility = review["eligibility"]
        eligibility_digest = _digest(eligibility)
        model_version = str(candidate["model_version"])
        champion_id = f"RESEARCH_CHAMPION_{model_version}"
        promotion_payload = {
            "version": VERSION,
            "record_type": "RESEARCH_CHAMPION_PROMOTION",
            "research_champion_id": champion_id,
            "model_version": model_version,
            "source_challenger_version": candidate["challenger_version"],
            "eligibility_version": eligibility["eligibility_version"],
            "eligibility_digest": eligibility_digest,
            "window_basis": list(candidate["window_basis"]),
            "model_registry_artifact_digest": candidate["model_registry_artifact_digest"],
            "challenger_registry_artifact_digest": candidate["challenger_registry_artifact_digest"],
            "final_evaluation_artifact_digest": candidate["final_evaluation_artifact_digest"],
            "final_evaluation_digest": candidate["final_evaluation_digest"],
            "promotion_mode": self.config.promotion_mode,
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }
        promotion_key = PROMOTION_PREFIX + model_version + ":" + eligibility_digest[:16]
        promotion = self.memory.persist_artifact(promotion_key, promotion_payload)

        pointer_payload = {
            "registry_version": REGISTRY_VERSION,
            "record_type": "CHAMPION_POINTER",
            "generation": 1,
            "current_research_champion": model_version,
            "research_champion_id": champion_id,
            "previous_research_champion": None,
            "source_promotion_artifact_key": promotion_key,
            "source_promotion_artifact_digest": promotion["artifact_digest"],
            "reason": "FIRST_V39_RESEARCH_CHAMPION_PASSED_FROZEN_MULTI_WINDOW_GATE",
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }
        pointer_key = CHAMPION_POINTER_PREFIX + "000001-" + model_version
        pointer = self.memory.persist_artifact(pointer_key, pointer_payload)

        role_payload = {
            "registry_version": REGISTRY_VERSION,
            "record_type": "MODEL_ROLE",
            "generation": 1,
            "model_version": model_version,
            "status": "RESEARCH_CHAMPION",
            "source_champion_pointer_key": pointer_key,
            "source_champion_pointer_digest": pointer["artifact_digest"],
            "automatic_promotion": False,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }
        self.memory.persist_artifact(MODEL_ROLE_PREFIX + model_version + ":000001", role_payload)

        rollback_payload = {
            "registry_version": REGISTRY_VERSION,
            "record_type": "ROLLBACK_STATE",
            "generation": 1,
            "status": "DEFERRED_UNTIL_PAPER_STAGE_MATURE",
            "from_model_version": model_version,
            "to_model_version": None,
            "automatic_rollback": False,
            "operator_required_if_later_enabled": True,
            "reason": "FIRST_RESEARCH_CHAMPION_HAS_NO_PRIOR_RESEARCH_CHAMPION_AND_AUTOMATIC_ROLLBACK_IS_NOT_ENABLED",
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }
        self.memory.persist_artifact(
            ROLLBACK_STATE_PREFIX + "000001-" + model_version, rollback_payload
        )

        return {
            "result": "RESEARCH_CHAMPION_PROMOTED",
            "research_champion_id": champion_id,
            "model_version": model_version,
            "champion_pointer_key": pointer_key,
            "promotion_artifact_key": promotion_key,
            "paper_champion_authority": False,
            "execution_authority": "NONE",
            "authority": AUTHORITY,
        }

    def audit(self) -> dict[str, Any]:
        report = {
            "version": VERSION,
            "authority": AUTHORITY,
            "contract_missing_or_mismatch": 0,
            "promotion_reference_violation": 0,
            "pointer_reference_violation": 0,
            "premature_paper_authority": 0,
            "premature_execution_authority": 0,
            "automatic_promotion_violation": 0,
        }
        contract = self.memory.artifact(CONTRACT_KEY)
        if contract is None or contract["payload"] != self.contract():
            report["contract_missing_or_mismatch"] += 1
        promotions = self.memory.list_artifacts(prefix=PROMOTION_PREFIX)
        pointers = [
            row for row in self.memory.list_artifacts(prefix=CHAMPION_POINTER_PREFIX)
            if int(row["payload"].get("generation", 0)) > 0
        ]
        for promotion in promotions:
            payload = promotion["payload"]
            if (
                payload.get("authority") != AUTHORITY
                or payload.get("automatic_promotion") is not False
                or payload.get("paper_champion_authority") is not False
                or payload.get("execution_authority") != "NONE"
            ):
                report["promotion_reference_violation"] += 1
        for pointer in pointers:
            payload = pointer["payload"]
            source = self.memory.artifact(str(payload.get("source_promotion_artifact_key") or ""))
            model_version = str(payload.get("current_research_champion") or "")
            registry = self.memory.artifact(MODEL_REGISTRY_PREFIX + model_version)
            if (
                source is None
                or source["artifact_digest"] != payload.get("source_promotion_artifact_digest")
                or registry is None
                or payload.get("authority") != AUTHORITY
            ):
                report["pointer_reference_violation"] += 1
            if payload.get("automatic_promotion") is not False:
                report["automatic_promotion_violation"] += 1
            if payload.get("paper_champion_authority") is not False:
                report["premature_paper_authority"] += 1
            if payload.get("execution_authority") != "NONE":
                report["premature_execution_authority"] += 1
        report["healthy"] = all(
            int(value) == 0 for key, value in report.items()
            if key not in {"version", "authority", "healthy"}
        )
        return report
