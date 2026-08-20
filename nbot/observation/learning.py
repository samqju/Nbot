"""V3.4.7 continuous-learning foundation.

This module intentionally provides durable research bookkeeping only.  It has
no Execution imports, no exchange credentials, no order authority, and no
automatic promotion path.  Later V3.9 learning can schedule/produce challengers
against these registries without changing the capital boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any

from .database import EvidenceDatabase


FOUNDATION_VERSION = "CONTINUOUS_LEARNING_FOUNDATION_V1"
RESEARCH_AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"

MODEL_STATUSES = frozenset({"REGISTERED", "RETIRED"})
CHALLENGER_STATUSES = frozenset({"REGISTERED", "EVALUATED", "REJECTED", "RETIRED"})
TRAINING_STATES = frozenset({"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"})
EVALUATION_STATUSES = frozenset({"PASS_RESEARCH_GATE", "REJECT_RESEARCH_GATE", "INCOMPLETE"})

LEARNING_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_foundations (
    foundation_version TEXT PRIMARY KEY,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS model_registry (
    model_version TEXT PRIMARY KEY,
    foundation_version TEXT NOT NULL,
    model_family TEXT NOT NULL,
    selector_version TEXT,
    model_digest TEXT NOT NULL,
    training_data_digest TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('REGISTERED','RETIRED')),
    authority TEXT NOT NULL CHECK (authority='RESEARCH_ONLY_NO_EXECUTION'),
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (foundation_version) REFERENCES learning_foundations(foundation_version)
);

CREATE TABLE IF NOT EXISTS challenger_registry (
    challenger_version TEXT PRIMARY KEY,
    foundation_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('REGISTERED','EVALUATED','REJECTED','RETIRED')),
    source_champion_version TEXT,
    authority TEXT NOT NULL CHECK (authority='RESEARCH_ONLY_NO_EXECUTION'),
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (foundation_version) REFERENCES learning_foundations(foundation_version),
    FOREIGN KEY (model_version) REFERENCES model_registry(model_version)
);

CREATE TABLE IF NOT EXISTS training_jobs (
    job_id TEXT PRIMARY KEY,
    foundation_version TEXT NOT NULL,
    challenger_version TEXT,
    requested_at_ms INTEGER NOT NULL,
    started_at_ms INTEGER,
    completed_at_ms INTEGER,
    state TEXT NOT NULL CHECK (state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    training_cutoff_event_ms INTEGER,
    source_digest TEXT NOT NULL,
    output_model_version TEXT,
    detail_json TEXT NOT NULL,
    FOREIGN KEY (foundation_version) REFERENCES learning_foundations(foundation_version),
    FOREIGN KEY (challenger_version) REFERENCES challenger_registry(challenger_version),
    FOREIGN KEY (output_model_version) REFERENCES model_registry(model_version)
);

CREATE TABLE IF NOT EXISTS evaluation_ledger (
    evaluation_id TEXT PRIMARY KEY,
    foundation_version TEXT NOT NULL,
    challenger_version TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    evaluated_at_ms INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS_RESEARCH_GATE','REJECT_RESEARCH_GATE','INCOMPLETE')),
    evaluation_digest TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    authority TEXT NOT NULL CHECK (authority='RESEARCH_ONLY_NO_EXECUTION'),
    detail_json TEXT NOT NULL,
    FOREIGN KEY (foundation_version) REFERENCES learning_foundations(foundation_version),
    FOREIGN KEY (challenger_version) REFERENCES challenger_registry(challenger_version)
);

CREATE TABLE IF NOT EXISTS drift_reports (
    report_id TEXT PRIMARY KEY,
    foundation_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    window_start_ms INTEGER NOT NULL,
    window_end_ms INTEGER NOT NULL,
    recorded_at_ms INTEGER NOT NULL,
    source_digest TEXT NOT NULL,
    report_digest TEXT NOT NULL,
    report_json TEXT NOT NULL,
    authority TEXT NOT NULL CHECK (authority='RESEARCH_ONLY_NO_EXECUTION'),
    FOREIGN KEY (foundation_version) REFERENCES learning_foundations(foundation_version),
    FOREIGN KEY (model_version) REFERENCES model_registry(model_version)
);

CREATE TABLE IF NOT EXISTS rollback_records (
    rollback_id TEXT PRIMARY KEY,
    foundation_version TEXT NOT NULL,
    from_model_version TEXT NOT NULL,
    to_model_version TEXT NOT NULL,
    recorded_at_ms INTEGER NOT NULL,
    reason TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    operator_required INTEGER NOT NULL CHECK (operator_required=1),
    authority TEXT NOT NULL CHECK (authority='RESEARCH_ONLY_NO_EXECUTION'),
    detail_json TEXT NOT NULL,
    FOREIGN KEY (foundation_version) REFERENCES learning_foundations(foundation_version),
    FOREIGN KEY (from_model_version) REFERENCES model_registry(model_version),
    FOREIGN KEY (to_model_version) REFERENCES model_registry(model_version)
);

CREATE INDEX IF NOT EXISTS idx_learning_models_created
    ON model_registry(created_at_ms, model_version);
CREATE INDEX IF NOT EXISTS idx_learning_challengers_registered
    ON challenger_registry(registered_at_ms, challenger_version);
CREATE INDEX IF NOT EXISTS idx_learning_training_state
    ON training_jobs(state, requested_at_ms);
CREATE INDEX IF NOT EXISTS idx_learning_evaluations_challenger
    ON evaluation_ledger(challenger_version, evaluated_at_ms);
CREATE INDEX IF NOT EXISTS idx_learning_drift_model_window
    ON drift_reports(model_version, window_end_ms);
CREATE INDEX IF NOT EXISTS idx_learning_rollbacks_time
    ON rollback_records(recorded_at_ms);
"""

LEARNING_TABLES = (
    "learning_foundations",
    "model_registry",
    "challenger_registry",
    "training_jobs",
    "evaluation_ledger",
    "drift_reports",
    "rollback_records",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_id(name: str, value: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"NBOT_V347_{name}_REQUIRED")
    return result


@dataclass(frozen=True)
class LearningFoundationStatus:
    foundation_version: str
    models: int
    challengers: int
    training_jobs: int
    evaluations: int
    drift_reports: int
    rollback_records: int


class ContinuousLearningFoundation:
    """Durable research-only bookkeeping for later V3.9 automation."""

    def __init__(self, db: EvidenceDatabase):
        self.db = db

    def definition(self) -> dict[str, Any]:
        return {
            "foundation_version": FOUNDATION_VERSION,
            "authority": RESEARCH_AUTHORITY,
            "model_registry": "IMMUTABLE_MODEL_ID_DIGEST_AND_TRAINING_SOURCE_LINEAGE",
            "challenger_registry": "RESEARCH_CHALLENGERS_ONLY_NO_EXECUTION_PROMOTION",
            "training_job_state": sorted(TRAINING_STATES),
            "evaluation_ledger": "APPEND_ONLY_RESEARCH_GATE_EVIDENCE_BY_ID",
            "drift_reports": "IMMUTABLE_WINDOWED_RESEARCH_REPORTS",
            "rollback_records": "AUDIT_RECORD_ONLY_OPERATOR_REQUIRED",
            "automatic_execution_promotion": False,
            "execution_imports": False,
        }

    @property
    def definition_hash(self) -> str:
        return _digest(self.definition())

    def initialize(self) -> None:
        self.db.initialize()
        now_ms = int(time.time() * 1000)
        definition = self.definition()
        with self.db.connection() as conn:
            conn.executescript(LEARNING_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO learning_foundations("
                "foundation_version,definition_hash,definition_json,registered_at_ms"
                ") VALUES (?,?,?,?)",
                (
                    FOUNDATION_VERSION,
                    self.definition_hash,
                    _canonical_json(definition),
                    now_ms,
                ),
            )
            stored = conn.execute(
                "SELECT definition_hash,definition_json FROM learning_foundations "
                "WHERE foundation_version=?",
                (FOUNDATION_VERSION,),
            ).fetchone()
            expected = (self.definition_hash, _canonical_json(definition))
            if stored != expected:
                raise RuntimeError("NBOT_V347_FOUNDATION_DEFINITION_MISMATCH")

    def register_model(
        self,
        *,
        model_version: str,
        model_family: str,
        model_digest: str,
        training_data_digest: str,
        selector_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at_ms: int | None = None,
    ) -> None:
        self.initialize()
        model_version = _require_id("MODEL_VERSION", model_version)
        model_family = _require_id("MODEL_FAMILY", model_family)
        model_digest = _require_id("MODEL_DIGEST", model_digest)
        training_data_digest = _require_id("TRAINING_DATA_DIGEST", training_data_digest)
        now_ms = int(time.time() * 1000) if created_at_ms is None else int(created_at_ms)
        payload = _canonical_json(metadata or {})
        expected = (
            FOUNDATION_VERSION,
            model_family,
            selector_version,
            model_digest,
            training_data_digest,
            "REGISTERED",
            RESEARCH_AUTHORITY,
            payload,
        )
        with self.db.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO model_registry("
                "model_version,foundation_version,model_family,selector_version,model_digest,"
                "training_data_digest,created_at_ms,status,authority,metadata_json"
                ") VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    model_version,
                    FOUNDATION_VERSION,
                    model_family,
                    selector_version,
                    model_digest,
                    training_data_digest,
                    now_ms,
                    "REGISTERED",
                    RESEARCH_AUTHORITY,
                    payload,
                ),
            )
            stored = conn.execute(
                "SELECT foundation_version,model_family,selector_version,model_digest,"
                "training_data_digest,status,authority,metadata_json FROM model_registry "
                "WHERE model_version=?",
                (model_version,),
            ).fetchone()
            if stored != expected:
                raise RuntimeError("NBOT_V347_MODEL_IDENTITY_MISMATCH")

    def register_challenger(
        self,
        *,
        challenger_version: str,
        model_version: str,
        source_champion_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        registered_at_ms: int | None = None,
    ) -> None:
        self.initialize()
        challenger_version = _require_id("CHALLENGER_VERSION", challenger_version)
        model_version = _require_id("MODEL_VERSION", model_version)
        now_ms = int(time.time() * 1000) if registered_at_ms is None else int(registered_at_ms)
        payload = _canonical_json(metadata or {})
        expected = (
            FOUNDATION_VERSION,
            model_version,
            "REGISTERED",
            source_champion_version,
            RESEARCH_AUTHORITY,
            payload,
        )
        with self.db.connection() as conn:
            if conn.execute(
                "SELECT 1 FROM model_registry WHERE model_version=?", (model_version,)
            ).fetchone() is None:
                raise ValueError("NBOT_V347_CHALLENGER_MODEL_MISSING")
            conn.execute(
                "INSERT OR IGNORE INTO challenger_registry("
                "challenger_version,foundation_version,model_version,registered_at_ms,status,"
                "source_champion_version,authority,metadata_json"
                ") VALUES (?,?,?,?,?,?,?,?)",
                (
                    challenger_version,
                    FOUNDATION_VERSION,
                    model_version,
                    now_ms,
                    "REGISTERED",
                    source_champion_version,
                    RESEARCH_AUTHORITY,
                    payload,
                ),
            )
            stored = conn.execute(
                "SELECT foundation_version,model_version,status,source_champion_version,authority,"
                "metadata_json FROM challenger_registry WHERE challenger_version=?",
                (challenger_version,),
            ).fetchone()
            if stored != expected:
                raise RuntimeError("NBOT_V347_CHALLENGER_IDENTITY_MISMATCH")

    def record_training_job(
        self,
        *,
        job_id: str,
        state: str,
        source_digest: str,
        challenger_version: str | None = None,
        training_cutoff_event_ms: int | None = None,
        output_model_version: str | None = None,
        requested_at_ms: int | None = None,
        started_at_ms: int | None = None,
        completed_at_ms: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.initialize()
        job_id = _require_id("TRAINING_JOB_ID", job_id)
        if state not in TRAINING_STATES:
            raise ValueError("NBOT_V347_TRAINING_STATE_INVALID")
        source_digest = _require_id("SOURCE_DIGEST", source_digest)
        requested = int(time.time() * 1000) if requested_at_ms is None else int(requested_at_ms)
        payload = _canonical_json(detail or {})
        with self.db.connection() as conn:
            if challenger_version is not None and conn.execute(
                "SELECT 1 FROM challenger_registry WHERE challenger_version=?",
                (challenger_version,),
            ).fetchone() is None:
                raise ValueError("NBOT_V347_TRAINING_CHALLENGER_MISSING")
            if output_model_version is not None and conn.execute(
                "SELECT 1 FROM model_registry WHERE model_version=?",
                (output_model_version,),
            ).fetchone() is None:
                raise ValueError("NBOT_V347_TRAINING_OUTPUT_MODEL_MISSING")
            conn.execute(
                "INSERT OR REPLACE INTO training_jobs("
                "job_id,foundation_version,challenger_version,requested_at_ms,started_at_ms,completed_at_ms,"
                "state,training_cutoff_event_ms,source_digest,output_model_version,detail_json"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    job_id,
                    FOUNDATION_VERSION,
                    challenger_version,
                    requested,
                    started_at_ms,
                    completed_at_ms,
                    state,
                    training_cutoff_event_ms,
                    source_digest,
                    output_model_version,
                    payload,
                ),
            )

    def record_evaluation(
        self,
        *,
        evaluation_id: str,
        challenger_version: str,
        evaluator_version: str,
        status: str,
        source_digest: str,
        detail: dict[str, Any],
        evaluated_at_ms: int | None = None,
    ) -> str:
        self.initialize()
        evaluation_id = _require_id("EVALUATION_ID", evaluation_id)
        challenger_version = _require_id("CHALLENGER_VERSION", challenger_version)
        evaluator_version = _require_id("EVALUATOR_VERSION", evaluator_version)
        source_digest = _require_id("SOURCE_DIGEST", source_digest)
        if status not in EVALUATION_STATUSES:
            raise ValueError("NBOT_V347_EVALUATION_STATUS_INVALID")
        payload = {
            "evaluation_id": evaluation_id,
            "challenger_version": challenger_version,
            "evaluator_version": evaluator_version,
            "status": status,
            "source_digest": source_digest,
            "authority": RESEARCH_AUTHORITY,
            "detail": detail,
        }
        evaluation_digest = _digest(payload)
        now_ms = int(time.time() * 1000) if evaluated_at_ms is None else int(evaluated_at_ms)
        with self.db.connection() as conn:
            if conn.execute(
                "SELECT 1 FROM challenger_registry WHERE challenger_version=?",
                (challenger_version,),
            ).fetchone() is None:
                raise ValueError("NBOT_V347_EVALUATION_CHALLENGER_MISSING")
            conn.execute(
                "INSERT OR IGNORE INTO evaluation_ledger("
                "evaluation_id,foundation_version,challenger_version,evaluator_version,evaluated_at_ms,"
                "status,evaluation_digest,source_digest,authority,detail_json"
                ") VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    evaluation_id,
                    FOUNDATION_VERSION,
                    challenger_version,
                    evaluator_version,
                    now_ms,
                    status,
                    evaluation_digest,
                    source_digest,
                    RESEARCH_AUTHORITY,
                    _canonical_json(detail),
                ),
            )
            row = conn.execute(
                "SELECT challenger_version,evaluator_version,status,evaluation_digest,source_digest,"
                "authority,detail_json FROM evaluation_ledger WHERE evaluation_id=?",
                (evaluation_id,),
            ).fetchone()
            expected = (
                challenger_version,
                evaluator_version,
                status,
                evaluation_digest,
                source_digest,
                RESEARCH_AUTHORITY,
                _canonical_json(detail),
            )
            if row != expected:
                raise RuntimeError("NBOT_V347_EVALUATION_IDENTITY_MISMATCH")
        return evaluation_digest

    def record_drift_report(
        self,
        *,
        report_id: str,
        model_version: str,
        window_start_ms: int,
        window_end_ms: int,
        source_digest: str,
        report: dict[str, Any],
        recorded_at_ms: int | None = None,
    ) -> str:
        self.initialize()
        report_id = _require_id("DRIFT_REPORT_ID", report_id)
        model_version = _require_id("MODEL_VERSION", model_version)
        source_digest = _require_id("SOURCE_DIGEST", source_digest)
        if int(window_end_ms) < int(window_start_ms):
            raise ValueError("NBOT_V347_DRIFT_WINDOW_INVALID")
        payload = {
            "report_id": report_id,
            "model_version": model_version,
            "window_start_ms": int(window_start_ms),
            "window_end_ms": int(window_end_ms),
            "source_digest": source_digest,
            "report": report,
        }
        report_digest = _digest(payload)
        now_ms = int(time.time() * 1000) if recorded_at_ms is None else int(recorded_at_ms)
        with self.db.connection() as conn:
            if conn.execute(
                "SELECT 1 FROM model_registry WHERE model_version=?", (model_version,)
            ).fetchone() is None:
                raise ValueError("NBOT_V347_DRIFT_MODEL_MISSING")
            conn.execute(
                "INSERT OR IGNORE INTO drift_reports("
                "report_id,foundation_version,model_version,window_start_ms,window_end_ms,recorded_at_ms,"
                "source_digest,report_digest,report_json,authority"
                ") VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    report_id,
                    FOUNDATION_VERSION,
                    model_version,
                    int(window_start_ms),
                    int(window_end_ms),
                    now_ms,
                    source_digest,
                    report_digest,
                    _canonical_json(report),
                    RESEARCH_AUTHORITY,
                ),
            )
        return report_digest

    def record_rollback(
        self,
        *,
        rollback_id: str,
        from_model_version: str,
        to_model_version: str,
        reason: str,
        source_digest: str,
        detail: dict[str, Any] | None = None,
        recorded_at_ms: int | None = None,
    ) -> None:
        self.initialize()
        rollback_id = _require_id("ROLLBACK_ID", rollback_id)
        reason = _require_id("ROLLBACK_REASON", reason)
        source_digest = _require_id("SOURCE_DIGEST", source_digest)
        now_ms = int(time.time() * 1000) if recorded_at_ms is None else int(recorded_at_ms)
        with self.db.connection() as conn:
            for model in (from_model_version, to_model_version):
                if conn.execute(
                    "SELECT 1 FROM model_registry WHERE model_version=?", (model,)
                ).fetchone() is None:
                    raise ValueError("NBOT_V347_ROLLBACK_MODEL_MISSING")
            conn.execute(
                "INSERT OR IGNORE INTO rollback_records("
                "rollback_id,foundation_version,from_model_version,to_model_version,recorded_at_ms,"
                "reason,source_digest,operator_required,authority,detail_json"
                ") VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    rollback_id,
                    FOUNDATION_VERSION,
                    from_model_version,
                    to_model_version,
                    now_ms,
                    reason,
                    source_digest,
                    1,
                    RESEARCH_AUTHORITY,
                    _canonical_json(detail or {}),
                ),
            )

    def status(self) -> LearningFoundationStatus:
        self.initialize()
        with self.db.connection() as conn:
            counts = [
                int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in LEARNING_TABLES[1:]
            ]
        return LearningFoundationStatus(FOUNDATION_VERSION, *counts)

    def audit(self) -> dict[str, Any]:
        """Read-only definition/authority/integrity audit."""

        report: dict[str, Any] = {
            "foundation_version": FOUNDATION_VERSION,
            "authority": RESEARCH_AUTHORITY,
            "missing_tables": (),
            "foundation_definition_mismatch": 0,
            "non_research_authority_rows": 0,
            "invalid_operator_required_rows": 0,
            "orphan_challengers": 0,
            "orphan_training_outputs": 0,
            "orphan_evaluations": 0,
            "orphan_drift_reports": 0,
            "orphan_rollbacks": 0,
        }
        with self.db.connection() as conn:
            present = {
                str(row[0])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            missing = tuple(sorted(set(LEARNING_TABLES) - present))
            report["missing_tables"] = missing
            if missing:
                report["healthy"] = False
                return report
            foundation = conn.execute(
                "SELECT definition_hash,definition_json FROM learning_foundations "
                "WHERE foundation_version=?",
                (FOUNDATION_VERSION,),
            ).fetchone()
            expected = (self.definition_hash, _canonical_json(self.definition()))
            report["foundation_definition_mismatch"] = int(foundation != expected)
            authority_rows = 0
            for table in (
                "model_registry",
                "challenger_registry",
                "evaluation_ledger",
                "drift_reports",
                "rollback_records",
            ):
                authority_rows += int(conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE authority<>?",
                    (RESEARCH_AUTHORITY,),
                ).fetchone()[0])
            report["non_research_authority_rows"] = authority_rows
            report["invalid_operator_required_rows"] = int(conn.execute(
                "SELECT COUNT(*) FROM rollback_records WHERE operator_required<>1"
            ).fetchone()[0])
            report["orphan_challengers"] = int(conn.execute(
                "SELECT COUNT(*) FROM challenger_registry c LEFT JOIN model_registry m "
                "ON m.model_version=c.model_version WHERE m.model_version IS NULL"
            ).fetchone()[0])
            report["orphan_training_outputs"] = int(conn.execute(
                "SELECT COUNT(*) FROM training_jobs t LEFT JOIN model_registry m "
                "ON m.model_version=t.output_model_version "
                "WHERE t.output_model_version IS NOT NULL AND m.model_version IS NULL"
            ).fetchone()[0])
            report["orphan_evaluations"] = int(conn.execute(
                "SELECT COUNT(*) FROM evaluation_ledger e LEFT JOIN challenger_registry c "
                "ON c.challenger_version=e.challenger_version WHERE c.challenger_version IS NULL"
            ).fetchone()[0])
            report["orphan_drift_reports"] = int(conn.execute(
                "SELECT COUNT(*) FROM drift_reports d LEFT JOIN model_registry m "
                "ON m.model_version=d.model_version WHERE m.model_version IS NULL"
            ).fetchone()[0])
            report["orphan_rollbacks"] = int(conn.execute(
                "SELECT COUNT(*) FROM rollback_records r "
                "LEFT JOIN model_registry a ON a.model_version=r.from_model_version "
                "LEFT JOIN model_registry b ON b.model_version=r.to_model_version "
                "WHERE a.model_version IS NULL OR b.model_version IS NULL"
            ).fetchone()[0])
        counters = (
            "foundation_definition_mismatch",
            "non_research_authority_rows",
            "invalid_operator_required_rows",
            "orphan_challengers",
            "orphan_training_outputs",
            "orphan_evaluations",
            "orphan_drift_reports",
            "orphan_rollbacks",
        )
        report["healthy"] = all(int(report[key]) == 0 for key in counters)
        return report
