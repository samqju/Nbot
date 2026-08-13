"""Append-only labels linked to candidate observation IDs."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from learning.evidence_ledger import Phase7EvidenceLedger
from utils.jsonl_history import append_jsonl_line, append_jsonl_line_bounded

from strategy.experiment_contract import (
    copy_experiment_context,
    experiment_projection,
)


CANDIDATE_OUTCOME_SCHEMA_VERSION = 2


class CandidateOutcomeWriter:
    def __init__(
        self,
        path: str,
        system_log=None,
        *,
        environment: str | None = None,
        execution_mode: str | None = None,
        evidence_ledger_path: str | None = None,
        evidence_generation: str | None = None,
        training_outcome_type: str = "VIRTUAL_TRADE",
        pending_fact_retention_hours: float = 24.0,
        raw_segment_max_bytes: int = 0,
        raw_retain_segments: int = 4,
    ):
        self.path = Path(path)
        self.system_log = system_log
        self.environment = (
            str(environment).strip().upper() if environment else None
        )
        self.execution_mode = (
            str(execution_mode).strip().upper() if execution_mode else None
        )
        self._lock = threading.Lock()
        self.raw_segment_max_bytes = max(0, int(raw_segment_max_bytes))
        self.raw_retain_segments = max(1, int(raw_retain_segments))
        self.evidence_ledger = (
            Phase7EvidenceLedger(
                path=evidence_ledger_path,
                generation=evidence_generation or "PHASE7_LEDGER_V1",
                training_outcome_type=training_outcome_type,
                environment=self.environment,
                pending_retention_hours=pending_fact_retention_hours,
            )
            if evidence_ledger_path
            else None
        )

    def append(
        self,
        *,
        observation_id: str,
        outcome_type: str,
        symbol: str,
        direction: str,
        payload: dict,
        experiment_context: dict | None = None,
        outcome_variant_id: str | None = None,
    ) -> None:
        observation_id = str(observation_id or "").strip()
        if not observation_id:
            raise ValueError("CANDIDATE_OUTCOME_OBSERVATION_ID_INVALID")

        normalized_context = copy_experiment_context(
            experiment_context
        )
        projection = experiment_projection(normalized_context)
        row = {
            "schema_version": CANDIDATE_OUTCOME_SCHEMA_VERSION,
            **projection,
            "observation_type": "CANDIDATE_OUTCOME",
            "recorded_at_ms": int(time.time() * 1000),
            "environment": self.environment,
            "execution_mode": self.execution_mode,
            "candidate_observation_id": observation_id,
            "outcome_type": str(outcome_type).strip().upper(),
            "symbol": str(symbol).strip().upper(),
            "direction": str(direction).strip().upper(),
            "outcome_variant_id": (
                str(outcome_variant_id).strip()
                if outcome_variant_id is not None else None
            ),
            "experiment_context": normalized_context,
            "payload": dict(payload),
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(row, default=str)

        with self._lock:
            if self.raw_segment_max_bytes > 0:
                append_jsonl_line_bounded(
                    self.path,
                    line,
                    max_bytes=self.raw_segment_max_bytes,
                    retain_segments=self.raw_retain_segments,
                    segment_tag="candidate-outcomes",
                )
            else:
                append_jsonl_line(self.path, line)

        ledger_result = None
        if self.evidence_ledger is not None:
            try:
                ledger_result = self.evidence_ledger.qualify_outcome(row)
            except Exception as exc:
                if self.system_log:
                    getattr(self.system_log, "error", lambda *_args, **_kwargs: None)(
                        "PHASE7_EVIDENCE_OUTCOME_FAILED | "
                        f"id={observation_id} | type={row['outcome_type']} | "
                        f"error={type(exc).__name__}:{exc}"
                    )

        if self.system_log:
            getattr(self.system_log, "debug", lambda *_args, **_kwargs: None)(
                "CANDIDATE_OUTCOME_WRITTEN | "
                f"id={observation_id} | "
                f"type={row['outcome_type']} | "
                f"symbol={row['symbol']} | "
                f"ledger={(ledger_result or {}).get('decision', 'DISABLED')}"
            )
