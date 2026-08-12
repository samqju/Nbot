"""Atomic model registry for Phase 5.8 and later lifecycle phases."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


MODEL_REGISTRY_SCHEMA_VERSION = 3
PAPER_CANARY_STAGES = (
    "PAPER_CANARY_10_PERCENT",
    "PAPER_CANARY_25_PERCENT",
    "PAPER_CANARY_50_PERCENT",
)
PAPER_CANARY_STAGE_ALLOCATION = {
    "PAPER_CANARY_10_PERCENT": 0.10,
    "PAPER_CANARY_25_PERCENT": 0.25,
    "PAPER_CANARY_50_PERCENT": 0.50,
}
PAPER_CANARY_STAGE_TRANSITIONS = {
    "PAPER_CANARY_10_PERCENT": "PAPER_CANARY_25_PERCENT",
    "PAPER_CANARY_25_PERCENT": "PAPER_CANARY_50_PERCENT",
    "PAPER_CANARY_50_PERCENT": "PAPER_CHAMPION",
}

MODEL_STATUSES = (
    "TRAINING",
    "INVALID",
    "OFFLINE_VALIDATED",
    "SHADOW",
    "PAPER_CANARY",
    "PAPER_CHAMPION",
    "REJECTED",
    "ROLLED_BACK",
    "ARCHIVED",
)

_ALLOWED_TRANSITIONS = {
    "TRAINING": {"INVALID", "OFFLINE_VALIDATED", "REJECTED"},
    "OFFLINE_VALIDATED": {"SHADOW", "REJECTED", "ARCHIVED"},
    "SHADOW": {"PAPER_CANARY", "REJECTED", "ARCHIVED"},
    "PAPER_CANARY": {"PAPER_CHAMPION", "ROLLED_BACK", "REJECTED"},
    "PAPER_CHAMPION": {"ROLLED_BACK", "ARCHIVED"},
    "ROLLED_BACK": {"ARCHIVED"},
    "INVALID": {"ARCHIVED"},
    "REJECTED": {"ARCHIVED"},
    "ARCHIVED": set(),
}


class ModelRegistryError(RuntimeError):
    pass


class ModelRegistry:
    """Persist model lifecycle metadata without changing runtime authority."""

    def __init__(
        self,
        *,
        path: str,
        environment: str,
        default_champion_model_id: str,
    ):
        self.path = Path(path)
        self.environment = str(environment or "").strip().upper()
        self.default_champion_model_id = str(
            default_champion_model_id or ""
        ).strip()
        if not self.environment:
            raise ValueError("MODEL_REGISTRY_ENVIRONMENT_REQUIRED")
        if not self.default_champion_model_id:
            raise ValueError("MODEL_REGISTRY_DEFAULT_CHAMPION_REQUIRED")

    def load(self) -> dict:
        if not self.path.exists():
            return self._empty()
        try:
            document = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_LOAD_FAILED | {exc}"
            ) from exc
        # Backward-compatible in-memory migration from the Phase 5.8-5.11
        # registry. The next atomic write persists schema v2.
        if document.get("schema_version") in {1, 2}:
            document["schema_version"] = MODEL_REGISTRY_SCHEMA_VERSION
        document.setdefault("current_paper_canary_model_id", None)
        document.setdefault("previous_champion_model_id", None)
        document.setdefault("rollback_history", [])
        canary_id = document.get("current_paper_canary_model_id")
        if canary_id:
            record = document.get("models", {}).get(str(canary_id))
            if isinstance(record, dict):
                record.setdefault(
                    "paper_canary_stage",
                    "PAPER_CANARY_10_PERCENT",
                )
                record.setdefault(
                    "paper_canary_allocation_fraction",
                    PAPER_CANARY_STAGE_ALLOCATION[
                        record["paper_canary_stage"]
                    ],
                )
                record["paper_canary_risk_multiplier"] = 1.0
        self._validate(document)
        return document

    def initialize(self) -> dict:
        document = self.load()
        if not self.path.exists():
            self._write(document)
        return document

    def register_training(self, entry: dict) -> dict:
        document = self.load()
        model_id = str(entry.get("model_id") or "").strip()
        if not model_id:
            raise ModelRegistryError("MODEL_REGISTRY_MODEL_ID_REQUIRED")
        if model_id in document["models"]:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_DUPLICATE_MODEL | model_id={model_id}"
            )
        now_ms = int(time.time() * 1000)
        record = dict(entry)
        record["model_id"] = model_id
        record["status"] = "TRAINING"
        record.setdefault("registered_at_ms", now_ms)
        record["updated_at_ms"] = now_ms
        document["models"][model_id] = record
        document["latest_model_id"] = model_id
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def update_model(
        self,
        model_id: str,
        *,
        status: str | None = None,
        updates: dict[str, Any] | None = None,
    ) -> dict:
        document = self.load()
        model_id = str(model_id or "").strip()
        record = document["models"].get(model_id)
        if record is None:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if status is not None:
            status = str(status).strip().upper()
            if status not in MODEL_STATUSES:
                raise ModelRegistryError(
                    f"MODEL_REGISTRY_STATUS_INVALID | status={status}"
                )
            current = record["status"]
            if status != current and status not in _ALLOWED_TRANSITIONS[current]:
                raise ModelRegistryError(
                    "MODEL_REGISTRY_TRANSITION_INVALID | "
                    f"model_id={model_id} | from={current} | to={status}"
                )
            record["status"] = status
        if updates:
            protected = {"model_id", "status"}
            if protected & set(updates):
                raise ModelRegistryError(
                    "MODEL_REGISTRY_PROTECTED_FIELD_UPDATE"
                )
            record.update(updates)
        now_ms = int(time.time() * 1000)
        record["updated_at_ms"] = now_ms
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def latest_completed_cutoff_ms(self) -> int:
        document = self.load()
        cutoffs = [
            int(record.get("data_cutoff_ms", 0) or 0)
            for record in document["models"].values()
            if record.get("status") in {
                "OFFLINE_VALIDATED",
                "SHADOW",
                "PAPER_CANARY",
                "PAPER_CHAMPION",
                "REJECTED",
            }
        ]
        return max(cutoffs, default=0)

    def current_champion_model_id(self) -> str:
        return str(
            self.load().get("current_champion_model_id")
            or self.default_champion_model_id
        )

    def current_shadow_model_id(self) -> str | None:
        value = self.load().get("current_shadow_model_id")
        return str(value) if value else None

    def current_paper_canary_model_id(self) -> str | None:
        value = self.load().get("current_paper_canary_model_id")
        return str(value) if value else None

    def previous_champion_model_id(self) -> str | None:
        value = self.load().get("previous_champion_model_id")
        return str(value) if value else None

    @staticmethod
    def paper_canary_stage(record: dict | None) -> str | None:
        if not isinstance(record, dict) or record.get("status") != "PAPER_CANARY":
            return None
        stage = str(
            record.get("paper_canary_stage")
            or "PAPER_CANARY_10_PERCENT"
        ).strip().upper()
        if stage not in PAPER_CANARY_STAGES:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_CANARY_STAGE_INVALID | stage={stage}"
            )
        return stage

    @staticmethod
    def paper_canary_allocation_fraction(record: dict | None) -> float:
        stage = ModelRegistry.paper_canary_stage(record)
        if stage is None:
            raise ModelRegistryError("MODEL_REGISTRY_CANARY_STAGE_REQUIRED")
        return PAPER_CANARY_STAGE_ALLOCATION[stage]

    def get_model(self, model_id: str) -> dict | None:
        record = self.load()["models"].get(str(model_id or "").strip())
        return dict(record) if isinstance(record, dict) else None

    def enable_paper_canary_routing(
        self,
        model_id: str,
        *,
        allocation_fraction: float,
        risk_multiplier: float,
        execution_mode: str,
    ) -> dict:
        """Atomically authorize controlled local-paper canary routing.

        This method refuses non-SHADOW execution and never changes the
        champion or grants real-order authority. Repeated calls with the same
        settings are idempotent.
        """
        execution_mode = str(execution_mode or "").strip().upper()
        if execution_mode != "SHADOW":
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_ROUTING_REQUIRES_SHADOW"
            )
        allocation_fraction = float(allocation_fraction)
        risk_multiplier = float(risk_multiplier)
        if not (0.0 < allocation_fraction <= 1.0):
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_ALLOCATION_INVALID"
            )
        if abs(risk_multiplier - 1.0) > 1e-12:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_RISK_MULTIPLIER_MUST_EQUAL_ONE"
            )

        document = self.load()
        model_id = str(model_id or "").strip()
        record = document["models"].get(model_id)
        if record is None:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if document.get("current_paper_canary_model_id") != model_id:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_NOT_CURRENT_SLOT | "
                f"model_id={model_id}"
            )
        if record.get("status") != "PAPER_CANARY":
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_STATUS_INVALID | "
                f"model_id={model_id} | status={record.get('status')}"
            )
        stage = self.paper_canary_stage(record)
        stage_fraction = PAPER_CANARY_STAGE_ALLOCATION[stage]
        if abs(allocation_fraction - stage_fraction) > 1e-12:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_ALLOCATION_STAGE_MISMATCH | "
                f"stage={stage} | expected={stage_fraction} | "
                f"actual={allocation_fraction}"
            )
        desired = {
            "runtime_activation": "PAPER_CANARY_ACTIVE_SHADOW_ONLY",
            "paper_authority": "CONTROLLED_SHADOW_PAPER_SELECTION",
            "real_order_authority": "NONE",
            "paper_canary_stage": stage,
            "paper_canary_allocation_fraction": stage_fraction,
            "paper_canary_risk_multiplier": 1.0,
        }
        if all(record.get(key) == value for key, value in desired.items()):
            return dict(record)
        now_ms = int(time.time() * 1000)
        record.update(desired)
        record.setdefault("paper_canary_routing_started_at_ms", now_ms)
        record["updated_at_ms"] = now_ms
        document["authority"]["paper_activation"] = (
            "CONTROLLED_SHADOW_PAPER_CANARY"
        )
        document["authority"]["real_order_authority"] = "NONE"
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def update_paper_canary_evidence(
        self,
        model_id: str,
        *,
        evidence: dict,
    ) -> dict:
        document = self.load()
        model_id = str(model_id or "").strip()
        record = document["models"].get(model_id)
        if record is None:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if (
            document.get("current_paper_canary_model_id") != model_id
            or record.get("status") != "PAPER_CANARY"
        ):
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_EVIDENCE_STATE_INVALID | "
                f"model_id={model_id}"
            )
        now_ms = int(time.time() * 1000)
        record["paper_canary_last_evidence"] = dict(evidence)
        record["paper_canary_last_evaluated_at_ms"] = now_ms
        record["updated_at_ms"] = now_ms
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def rollback_paper_canary(
        self,
        model_id: str,
        *,
        evidence: dict,
        reason_codes: list[str],
    ) -> dict:
        """Atomically clear canary routing and restore current champion."""
        document = self.load()
        model_id = str(model_id or "").strip()
        record = document["models"].get(model_id)
        if record is None:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if document.get("current_paper_canary_model_id") != model_id:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_ROLLBACK_NOT_CURRENT | "
                f"model_id={model_id}"
            )
        if record.get("status") != "PAPER_CANARY":
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_ROLLBACK_STATUS_INVALID | "
                f"model_id={model_id} | status={record.get('status')}"
            )
        now_ms = int(time.time() * 1000)
        record["status"] = "ROLLED_BACK"
        record["rolled_back_at_ms"] = now_ms
        record["rollback_reason_codes"] = list(reason_codes)
        record["rollback_evidence"] = dict(evidence)
        record["runtime_activation"] = "DISABLED"
        record["paper_authority"] = "RULE_CHAMPION_FALLBACK"
        record["real_order_authority"] = "NONE"
        record["updated_at_ms"] = now_ms
        document["current_paper_canary_model_id"] = None
        champion_id = str(
            document.get("current_champion_model_id")
            or self.default_champion_model_id
        )
        document["authority"]["paper_activation"] = (
            "RULE_CHAMPION_ONLY"
            if champion_id == self.default_champion_model_id
            else "PAPER_CHAMPION_MODEL_SELECTION"
        )
        document["authority"]["real_order_authority"] = "NONE"
        history = list(document.get("rollback_history") or [])
        history.append({
            "rolled_back_at_ms": now_ms,
            "model_id": model_id,
            "role": "PAPER_CANARY",
            "restored_champion_model_id": champion_id,
            "reason_codes": list(reason_codes),
            "real_order_authority": "NONE",
        })
        document["rollback_history"] = history[-100:]
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def advance_paper_canary_stage(
        self,
        model_id: str,
        *,
        target_stage: str,
        evidence: dict,
        reason_codes: list[str],
    ) -> dict:
        """Atomically advance 10% -> 25% -> 50% without changing risk."""
        document = self.load()
        model_id = str(model_id or "").strip()
        record = document["models"].get(model_id)
        if not isinstance(record, dict):
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if document.get("current_paper_canary_model_id") != model_id:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_ADVANCE_NOT_CURRENT"
            )
        current_stage = self.paper_canary_stage(record)
        target_stage = str(target_stage or "").strip().upper()
        expected = PAPER_CANARY_STAGE_TRANSITIONS.get(current_stage)
        if target_stage not in PAPER_CANARY_STAGES or target_stage != expected:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CANARY_STAGE_TRANSITION_INVALID | "
                f"from={current_stage} | to={target_stage}"
            )
        now_ms = int(time.time() * 1000)
        history = list(record.get("paper_canary_stage_history") or [])
        history.append({
            "from_stage": current_stage,
            "to_stage": target_stage,
            "advanced_at_ms": now_ms,
            "reason_codes": list(reason_codes),
            "evidence": dict(evidence),
        })
        record["paper_canary_stage_history"] = history[-20:]
        record["paper_canary_stage"] = target_stage
        record["paper_canary_stage_started_at_ms"] = now_ms
        record["paper_canary_allocation_fraction"] = (
            PAPER_CANARY_STAGE_ALLOCATION[target_stage]
        )
        record["paper_canary_risk_multiplier"] = 1.0
        record["runtime_activation"] = "PAPER_CANARY_ACTIVE_SHADOW_ONLY"
        record["paper_authority"] = "CONTROLLED_SHADOW_PAPER_SELECTION"
        record["real_order_authority"] = "NONE"
        record["updated_at_ms"] = now_ms
        document["authority"]["paper_activation"] = target_stage
        document["authority"]["real_order_authority"] = "NONE"
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def promote_paper_canary_to_champion(
        self,
        model_id: str,
        *,
        evidence: dict,
        reason_codes: list[str],
    ) -> dict:
        """Atomically promote the 50% canary and retain the old champion."""
        document = self.load()
        model_id = str(model_id or "").strip()
        record = document["models"].get(model_id)
        if not isinstance(record, dict):
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if document.get("current_paper_canary_model_id") != model_id:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CHAMPION_PROMOTION_NOT_CURRENT_CANARY"
            )
        if self.paper_canary_stage(record) != "PAPER_CANARY_50_PERCENT":
            raise ModelRegistryError(
                "MODEL_REGISTRY_CHAMPION_PROMOTION_REQUIRES_50_PERCENT"
            )
        previous = str(
            document.get("current_champion_model_id")
            or self.default_champion_model_id
        )
        now_ms = int(time.time() * 1000)
        record["status"] = "PAPER_CHAMPION"
        record["paper_canary_stage"] = "PAPER_CHAMPION"
        record["paper_champion_started_at_ms"] = now_ms
        record["previous_champion_model_id"] = previous
        record["champion_promotion_evidence"] = dict(evidence)
        record["champion_promotion_reason_codes"] = list(reason_codes)
        record["runtime_activation"] = "PAPER_CHAMPION_SHADOW_ONLY"
        record["paper_authority"] = "PAPER_CANDIDATE_SELECTION"
        record["real_order_authority"] = "NONE"
        record["updated_at_ms"] = now_ms
        document["previous_champion_model_id"] = previous
        document["current_champion_model_id"] = model_id
        document["current_paper_canary_model_id"] = None
        document["authority"]["paper_activation"] = (
            "PAPER_CHAMPION_MODEL_SELECTION"
        )
        document["authority"]["real_order_authority"] = "NONE"
        history = list(document.get("champion_history") or [])
        history.append({
            "promoted_at_ms": now_ms,
            "previous_champion_model_id": previous,
            "new_champion_model_id": model_id,
            "real_order_authority": "NONE",
        })
        document["champion_history"] = history[-50:]
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def rollback_paper_champion(
        self,
        model_id: str,
        *,
        restore_model_id: str,
        evidence: dict,
        reason_codes: list[str],
    ) -> dict:
        """Atomically disable an unsafe model champion and restore predecessor."""
        document = self.load()
        model_id = str(model_id or "").strip()
        restore_model_id = str(restore_model_id or "").strip()
        record = document["models"].get(model_id)
        if not isinstance(record, dict):
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if document.get("current_champion_model_id") != model_id:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CHAMPION_ROLLBACK_NOT_CURRENT"
            )
        if record.get("status") != "PAPER_CHAMPION":
            raise ModelRegistryError(
                "MODEL_REGISTRY_CHAMPION_ROLLBACK_STATUS_INVALID"
            )
        expected_previous = str(
            record.get("previous_champion_model_id")
            or document.get("previous_champion_model_id")
            or self.default_champion_model_id
        )
        if restore_model_id not in {
            expected_previous, self.default_champion_model_id
        }:
            raise ModelRegistryError(
                "MODEL_REGISTRY_CHAMPION_RESTORE_TARGET_INVALID | "
                f"expected={expected_previous} | actual={restore_model_id}"
            )
        if restore_model_id != self.default_champion_model_id:
            restored = document["models"].get(restore_model_id)
            if (
                not isinstance(restored, dict)
                or restored.get("status") != "PAPER_CHAMPION"
            ):
                raise ModelRegistryError(
                    "MODEL_REGISTRY_RESTORED_CHAMPION_INVALID | "
                    f"model_id={restore_model_id}"
                )
        now_ms = int(time.time() * 1000)
        record["status"] = "ROLLED_BACK"
        record["rolled_back_at_ms"] = now_ms
        record["rollback_reason_codes"] = list(reason_codes)
        record["rollback_evidence"] = dict(evidence)
        record["runtime_activation"] = "DISABLED"
        record["paper_authority"] = "PREVIOUS_CHAMPION_RESTORED"
        record["real_order_authority"] = "NONE"
        record["updated_at_ms"] = now_ms
        document["current_champion_model_id"] = restore_model_id
        if restore_model_id == self.default_champion_model_id:
            document["previous_champion_model_id"] = None
        else:
            restored = document["models"][restore_model_id]
            document["previous_champion_model_id"] = (
                restored.get("previous_champion_model_id")
                or self.default_champion_model_id
            )
        canary_id = document.get("current_paper_canary_model_id")
        if canary_id:
            canary = document["models"].get(str(canary_id))
            stage = self.paper_canary_stage(canary)
            document["authority"]["paper_activation"] = stage
        else:
            document["authority"]["paper_activation"] = (
                "RULE_CHAMPION_ONLY"
                if restore_model_id == self.default_champion_model_id
                else "PAPER_CHAMPION_MODEL_SELECTION"
            )
        document["authority"]["real_order_authority"] = "NONE"
        history = list(document.get("rollback_history") or [])
        history.append({
            "rolled_back_at_ms": now_ms,
            "model_id": model_id,
            "role": "PAPER_CHAMPION",
            "restored_champion_model_id": restore_model_id,
            "reason_codes": list(reason_codes),
            "real_order_authority": "NONE",
        })
        document["rollback_history"] = history[-100:]
        document["updated_at_ms"] = now_ms
        self._write(document)
        return {
            "rolled_back_model": dict(record),
            "restored_champion_model_id": restore_model_id,
            "current_paper_canary_model_id": canary_id,
        }

    def activate_next_shadow_challenger(self) -> dict | None:
        """Atomically attach one offline-validated challenger to shadow.

        Only one challenger may occupy the SHADOW slot. This method never
        changes the current champion or any paper-trading authority.
        """
        document = self.load()
        current_id = document.get("current_shadow_model_id")
        if current_id:
            current = document["models"].get(current_id)
            if isinstance(current, dict) and current.get("status") == "SHADOW":
                return dict(current)
            document["current_shadow_model_id"] = None

        eligible = [
            record
            for record in document["models"].values()
            if record.get("status") == "OFFLINE_VALIDATED"
            and str(record.get("artifact_path") or "").strip()
        ]
        if not eligible:
            if current_id:
                document["updated_at_ms"] = int(time.time() * 1000)
                self._write(document)
            return None

        selected = min(
            eligible,
            key=lambda record: (
                int(record.get("training_completed_at_ms", 0) or 0),
                int(record.get("registered_at_ms", 0) or 0),
                str(record.get("model_id")),
            ),
        )
        model_id = selected["model_id"]
        if "SHADOW" not in _ALLOWED_TRANSITIONS[selected["status"]]:
            raise ModelRegistryError(
                "MODEL_REGISTRY_SHADOW_TRANSITION_INVALID | "
                f"model_id={model_id} | status={selected['status']}"
            )
        now_ms = int(time.time() * 1000)
        selected["status"] = "SHADOW"
        selected["shadow_started_at_ms"] = now_ms
        selected["runtime_activation"] = "SHADOW_OBSERVATION_ONLY"
        selected["paper_authority"] = "UNCHANGED"
        selected["real_order_authority"] = "NONE"
        selected["updated_at_ms"] = now_ms
        document["current_shadow_model_id"] = model_id
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(selected)

    def apply_promotion_decision(
        self,
        model_id: str,
        *,
        decision: str,
        evidence: dict,
        gate_report: dict,
        reason_codes: list[str],
    ) -> dict:
        """Atomically apply one Phase 5.10 governance decision.

        HOLD and EXTEND_SHADOW preserve SHADOW status. REJECT clears the
        shadow slot. PROMOTE_TO_PAPER_CANARY reserves the registry canary
        slot but deliberately does not change paper-order routing.
        """
        decision = str(decision or "").strip().upper()
        if decision not in {
            "REJECT",
            "HOLD",
            "EXTEND_SHADOW",
            "PROMOTE_TO_PAPER_CANARY",
        }:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_PROMOTION_DECISION_INVALID | decision={decision}"
            )
        document = self.load()
        model_id = str(model_id or "").strip()
        record = document["models"].get(model_id)
        if record is None:
            raise ModelRegistryError(
                f"MODEL_REGISTRY_MODEL_NOT_FOUND | model_id={model_id}"
            )
        if document.get("current_shadow_model_id") != model_id:
            raise ModelRegistryError(
                "MODEL_REGISTRY_PROMOTION_NOT_CURRENT_SHADOW | "
                f"model_id={model_id}"
            )
        if record.get("status") != "SHADOW":
            raise ModelRegistryError(
                "MODEL_REGISTRY_PROMOTION_STATUS_INVALID | "
                f"model_id={model_id} | status={record.get('status')}"
            )
        if (
            decision == "PROMOTE_TO_PAPER_CANARY"
            and record.get("paper_promotion_allowed") is False
        ):
            raise ModelRegistryError(
                "MODEL_REGISTRY_PHASE7_PAPER_PROMOTION_LOCKED | "
                f"model_id={model_id}"
            )

        now_ms = int(time.time() * 1000)
        record["promotion_evaluation"] = dict(evidence)
        record["promotion_gate_report"] = dict(gate_report)
        record["promotion_reason_codes"] = list(reason_codes)
        record["last_promotion_decision"] = decision
        record["last_promotion_evaluated_at_ms"] = now_ms
        history = list(record.get("promotion_history") or [])
        history.append({
            "evaluated_at_ms": now_ms,
            "decision": decision,
            "reason_codes": list(reason_codes),
            "matched_candidate_outcomes": evidence.get(
                "matched_candidate_outcomes"
            ),
            "independent_decision_events": evidence.get(
                "independent_decision_events"
            ),
            "paired_disagreement_events": evidence.get(
                "paired_disagreement_events"
            ),
        })
        record["promotion_history"] = history[-100:]

        if decision == "REJECT":
            record["status"] = "REJECTED"
            record["rejected_at_ms"] = now_ms
            record["runtime_activation"] = "DISABLED"
            record["paper_authority"] = "UNCHANGED"
            document["current_shadow_model_id"] = None
        elif decision == "PROMOTE_TO_PAPER_CANARY":
            occupied = document.get("current_paper_canary_model_id")
            if occupied and occupied != model_id:
                raise ModelRegistryError(
                    "MODEL_REGISTRY_PAPER_CANARY_SLOT_OCCUPIED | "
                    f"model_id={occupied}"
                )
            record["status"] = "PAPER_CANARY"
            record["paper_canary_started_at_ms"] = now_ms
            record["paper_canary_stage"] = "PAPER_CANARY_10_PERCENT"
            record["paper_canary_stage_started_at_ms"] = now_ms
            record["paper_canary_allocation_fraction"] = 0.10
            record["paper_canary_risk_multiplier"] = 1.0
            record["runtime_activation"] = "PAPER_CANARY_REGISTRY_ONLY"
            record["paper_authority"] = (
                "CANARY_SLOT_RESERVED_NO_ORDER_ROUTING"
            )
            record["real_order_authority"] = "NONE"
            document["current_shadow_model_id"] = None
            document["current_paper_canary_model_id"] = model_id
            document["authority"]["paper_activation"] = (
                "PAPER_CANARY_REGISTRY_SLOT_ONLY"
            )
        else:
            record["status"] = "SHADOW"
            record["runtime_activation"] = "SHADOW_OBSERVATION_ONLY"
            record["paper_authority"] = "UNCHANGED"
            record["real_order_authority"] = "NONE"

        record["updated_at_ms"] = now_ms
        document["updated_at_ms"] = now_ms
        self._write(document)
        return dict(record)

    def _empty(self) -> dict:
        now_ms = int(time.time() * 1000)
        return {
            "schema_version": MODEL_REGISTRY_SCHEMA_VERSION,
            "environment": self.environment,
            "created_at_ms": now_ms,
            "updated_at_ms": now_ms,
            "current_champion_model_id": self.default_champion_model_id,
            "previous_champion_model_id": None,
            "current_shadow_model_id": None,
            "current_paper_canary_model_id": None,
            "latest_model_id": None,
            "models": {},
            "rollback_history": [],
            "authority": {
                "paper_activation": "UNCHANGED",
                "real_order_authority": "NONE",
            },
        }

    def _validate(self, document: Any) -> None:
        if not isinstance(document, dict):
            raise ModelRegistryError("MODEL_REGISTRY_DOCUMENT_INVALID")
        if document.get("schema_version") != MODEL_REGISTRY_SCHEMA_VERSION:
            raise ModelRegistryError("MODEL_REGISTRY_SCHEMA_INVALID")
        if document.get("environment") != self.environment:
            raise ModelRegistryError(
                "MODEL_REGISTRY_ENVIRONMENT_MISMATCH | "
                f"expected={self.environment} | "
                f"actual={document.get('environment')}"
            )
        models = document.get("models")
        if not isinstance(models, dict):
            raise ModelRegistryError("MODEL_REGISTRY_MODELS_INVALID")
        if not isinstance(document.get("rollback_history", []), list):
            raise ModelRegistryError("MODEL_REGISTRY_ROLLBACK_HISTORY_INVALID")
        champion_id = str(
            document.get("current_champion_model_id")
            or self.default_champion_model_id
        )
        if champion_id != self.default_champion_model_id:
            champion_record = models.get(champion_id)
            if (
                not isinstance(champion_record, dict)
                or champion_record.get("status") != "PAPER_CHAMPION"
            ):
                raise ModelRegistryError(
                    "MODEL_REGISTRY_CHAMPION_STATUS_INVALID | "
                    f"model_id={champion_id}"
                )
        previous_id = document.get("previous_champion_model_id")
        if (
            previous_id
            and str(previous_id) != self.default_champion_model_id
            and not isinstance(models.get(str(previous_id)), dict)
        ):
            raise ModelRegistryError(
                "MODEL_REGISTRY_PREVIOUS_CHAMPION_MISSING | "
                f"model_id={previous_id}"
            )
        shadow_id = document.get("current_shadow_model_id")
        canary_id = document.get("current_paper_canary_model_id")
        if shadow_id and shadow_id == canary_id:
            raise ModelRegistryError("MODEL_REGISTRY_SLOT_CONFLICT")
        for slot_id, expected_status, slot_name in (
            (shadow_id, "SHADOW", "SHADOW"),
            (canary_id, "PAPER_CANARY", "PAPER_CANARY"),
        ):
            if not slot_id:
                continue
            slot_record = models.get(slot_id)
            if not isinstance(slot_record, dict):
                raise ModelRegistryError(
                    f"MODEL_REGISTRY_{slot_name}_MODEL_MISSING | model_id={slot_id}"
                )
            if slot_record.get("status") != expected_status:
                raise ModelRegistryError(
                    f"MODEL_REGISTRY_{slot_name}_STATUS_INVALID | "
                    f"model_id={slot_id} | status={slot_record.get('status')}"
                )
            if slot_name == "PAPER_CANARY":
                stage = self.paper_canary_stage(slot_record)
                expected_fraction = PAPER_CANARY_STAGE_ALLOCATION[stage]
                actual_fraction = float(
                    slot_record.get(
                        "paper_canary_allocation_fraction",
                        expected_fraction,
                    )
                )
                if abs(actual_fraction - expected_fraction) > 1e-12:
                    raise ModelRegistryError(
                        "MODEL_REGISTRY_CANARY_STAGE_ALLOCATION_INVALID"
                    )
                if abs(float(slot_record.get(
                    "paper_canary_risk_multiplier", 1.0
                )) - 1.0) > 1e-12:
                    raise ModelRegistryError(
                        "MODEL_REGISTRY_CANARY_RISK_MUST_EQUAL_ONE"
                    )
        for model_id, record in models.items():
            if not isinstance(record, dict):
                raise ModelRegistryError(
                    f"MODEL_REGISTRY_RECORD_INVALID | model_id={model_id}"
                )
            if record.get("model_id") != model_id:
                raise ModelRegistryError(
                    f"MODEL_REGISTRY_ID_MISMATCH | model_id={model_id}"
                )
            if record.get("status") not in MODEL_STATUSES:
                raise ModelRegistryError(
                    f"MODEL_REGISTRY_RECORD_STATUS_INVALID | model_id={model_id}"
                )

    def _write(self, document: dict) -> None:
        self._validate(document)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
