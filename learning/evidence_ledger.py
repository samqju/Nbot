"""Phase 7.5C compact, durable qualified-evidence ledger.

The live Observation worker decides learning eligibility once, when evidence
becomes complete.  Automatic training reads this ledger directly and never
rescans the raw candidate-observation/outcome archives.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

from learning.context_features import is_complete_market_context, market_context_from_row
from learning.cost_evidence import has_complete_cost_evidence
from learning.dataset_builder import TrainingDatasetBuilder
from strategy.experiment_contract import EXPERIMENT_CONTRACT_VERSION


PHASE7_EVIDENCE_LEDGER_SCHEMA_VERSION = 1
LEDGER_SOURCE_MODE = "QUALIFIED_EVIDENCE_LEDGER_V1"


class EvidenceLedgerError(RuntimeError):
    pass


class Phase7EvidenceLedger:
    """Store only compact Phase-7 candidate facts and qualified outcomes."""

    def __init__(
        self,
        *,
        path: str,
        generation: str,
        training_outcome_type: str,
        environment: str | None = None,
        pending_retention_hours: float = 24.0,
        rejection_retain_rows: int = 10000,
    ):
        self.path = Path(path)
        self.generation = str(generation or "").strip().upper()
        self.training_outcome_type = str(training_outcome_type or "").strip().upper()
        self.environment = str(environment or "").strip().upper() or None
        self.pending_retention_ms = max(
            60_000, int(float(pending_retention_hours) * 3600 * 1000)
        )
        self.rejection_retain_rows = max(100, int(rejection_retain_rows))
        if not self.generation:
            raise ValueError("PHASE7_EVIDENCE_GENERATION_INVALID")
        if not self.training_outcome_type:
            raise ValueError("PHASE7_EVIDENCE_OUTCOME_TYPE_INVALID")
        self._lock = threading.RLock()
        self._connection: sqlite3.Connection | None = None
        self._builder = TrainingDatasetBuilder(
            observations_path="unused",
            outcomes_path="unused",
            dataset_path="unused",
            report_path="unused",
        )
        self._initialize()

    def close(self) -> None:
        with self._lock:
            connection = self._connection
            self._connection = None
            if connection is not None:
                connection.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.path), timeout=15.0, check_same_thread=False
            )
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.execute("PRAGMA foreign_keys=ON")
            self._connection = connection
        return self._connection

    def _initialize(self) -> None:
        with self._lock:
            connection = self._connect()
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candidate_facts (
                    candidate_id TEXT PRIMARY KEY,
                    observed_at_ms INTEGER NOT NULL,
                    market_event_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    row_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_candidate_facts_observed
                    ON candidate_facts(observed_at_ms);
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_key TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    outcome_type TEXT NOT NULL,
                    outcome_variant_id TEXT NOT NULL,
                    market_event_id TEXT NOT NULL,
                    observed_at_ms INTEGER NOT NULL,
                    recorded_at_ms INTEGER NOT NULL,
                    row_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS terminal_decisions (
                    evidence_key TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    outcome_type TEXT NOT NULL,
                    outcome_variant_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    recorded_at_ms INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_evidence_recorded
                    ON evidence(recorded_at_ms);
                CREATE INDEX IF NOT EXISTS idx_evidence_market_event
                    ON evidence(market_event_id);
                CREATE TABLE IF NOT EXISTS rejections (
                    rejection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id TEXT,
                    outcome_type TEXT,
                    outcome_variant_id TEXT,
                    recorded_at_ms INTEGER NOT NULL,
                    reason TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rejections_reason
                    ON rejections(reason);
                CREATE TABLE IF NOT EXISTS rejection_counts (
                    reason TEXT PRIMARY KEY,
                    total_count INTEGER NOT NULL,
                    last_recorded_at_ms INTEGER NOT NULL
                );
                """
            )
            expected = {
                "schema_version": str(PHASE7_EVIDENCE_LEDGER_SCHEMA_VERSION),
                "generation": self.generation,
                "training_outcome_type": self.training_outcome_type,
                "source_mode": LEDGER_SOURCE_MODE,
            }
            existing = dict(connection.execute("SELECT key, value FROM metadata"))
            if existing:
                for key, value in expected.items():
                    if existing.get(key) != value:
                        raise EvidenceLedgerError(
                            "PHASE7_EVIDENCE_LEDGER_METADATA_MISMATCH | "
                            f"key={key} | expected={value} | actual={existing.get(key)}"
                        )
            else:
                connection.executemany(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    sorted(expected.items()),
                )
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    ("created_at_ms", str(int(time.time() * 1000))),
                )
            connection.commit()

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _evidence_key(candidate_id: str, outcome_type: str, variant_id: str) -> str:
        return json.dumps(
            (candidate_id, outcome_type, variant_id),
            separators=(",", ":"),
        )

    def _reject(
        self,
        connection: sqlite3.Connection,
        *,
        reason: str,
        candidate_id: str | None = None,
        outcome_type: str | None = None,
        outcome_variant_id: str | None = None,
        recorded_at_ms: int | None = None,
        evidence_key: str | None = None,
        terminal: bool = False,
    ) -> dict:
        timestamp = int(recorded_at_ms or time.time() * 1000)
        connection.execute(
            "INSERT INTO rejections(candidate_id, outcome_type, "
            "outcome_variant_id, recorded_at_ms, reason) VALUES (?, ?, ?, ?, ?)",
            (candidate_id, outcome_type, outcome_variant_id, timestamp, str(reason)),
        )
        if terminal and evidence_key and candidate_id and outcome_type is not None:
            connection.execute(
                "INSERT OR IGNORE INTO terminal_decisions("
                "evidence_key, candidate_id, outcome_type, outcome_variant_id, "
                "decision, reason, recorded_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    evidence_key, candidate_id, outcome_type,
                    outcome_variant_id or "", "REJECTED", str(reason), timestamp,
                ),
            )
            connection.execute(
                "DELETE FROM candidate_facts WHERE candidate_id=?",
                (candidate_id,),
            )
        connection.execute(
            "INSERT INTO rejection_counts(reason, total_count, last_recorded_at_ms) "
            "VALUES (?, 1, ?) ON CONFLICT(reason) DO UPDATE SET "
            "total_count=total_count+1, last_recorded_at_ms=excluded.last_recorded_at_ms",
            (str(reason), timestamp),
        )
        connection.execute(
            "DELETE FROM rejections WHERE rejection_id IN ("
            "SELECT rejection_id FROM rejections ORDER BY rejection_id DESC "
            "LIMIT -1 OFFSET ?)",
            (self.rejection_retain_rows,),
        )
        connection.commit()
        return {"decision": "REJECTED", "reason": str(reason)}

    def register_candidate(self, observation: dict) -> dict:
        """Persist compact candidate facts once; reject unusable facts early."""
        with self._lock:
            connection = self._connect()
            candidate_id = self._text(observation.get("candidate_observation_id"))
            error = self._builder.validate_observation_record(observation)
            if error:
                return self._reject(
                    connection,
                    reason=f"INVALID_OBSERVATION:{error}",
                    candidate_id=candidate_id or None,
                )
            market_event_id = self._text(observation.get("market_event_id"))
            compact = self._compact_candidate(observation)
            try:
                connection.execute(
                    "INSERT INTO candidate_facts(candidate_id, observed_at_ms, "
                    "market_event_id, symbol, direction, row_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        candidate_id,
                        int(compact["observed_at_ms"]),
                        market_event_id,
                        compact["symbol"],
                        compact["direction"],
                        json.dumps(compact, sort_keys=True, separators=(",", ":")),
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError:
                return self._reject(
                    connection,
                    reason="DUPLICATE_CANDIDATE",
                    candidate_id=candidate_id,
                )
            self._prune_pending_locked(connection)
            return {"decision": "PENDING", "reason": None}

    def qualify_outcome(self, outcome: dict) -> dict:
        """Make the terminal Phase-7 qualification decision exactly once."""
        outcome_type = self._text(outcome.get("outcome_type")).upper()
        if outcome_type != self.training_outcome_type:
            return {"decision": "IGNORED", "reason": "OTHER_OUTCOME_TYPE"}
        candidate_id = self._text(outcome.get("candidate_observation_id"))
        variant_id = self._text(outcome.get("outcome_variant_id"))
        recorded_at_ms = int(outcome.get("recorded_at_ms", 0) or 0)
        with self._lock:
            connection = self._connect()
            error = self._builder.validate_outcome_record(outcome)
            if error:
                return self._reject(
                    connection,
                    reason=f"INVALID_OUTCOME:{error}",
                    candidate_id=candidate_id or None,
                    outcome_type=outcome_type or None,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                )
            evidence_key = self._evidence_key(candidate_id, outcome_type, variant_id)
            decided = connection.execute(
                "SELECT decision, reason FROM terminal_decisions WHERE evidence_key=?",
                (evidence_key,),
            ).fetchone()
            if decided is not None:
                return {"decision": "REJECTED", "reason": "DUPLICATE"}
            stored = connection.execute(
                "SELECT row_json FROM candidate_facts WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            if stored is None:
                return self._reject(
                    connection,
                    reason="CANDIDATE_FACT_MISSING",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            observation = json.loads(stored[0])
            if int(observation.get("experiment_contract_version", 0) or 0) != EXPERIMENT_CONTRACT_VERSION:
                return self._reject(
                    connection,
                    reason="NON_CURRENT_CONTRACT",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if not self._text(observation.get("market_event_id")):
                return self._reject(
                    connection,
                    reason="INVALID_EVENT",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if observation.get("eligible_for_training") is False:
                return self._reject(
                    connection,
                    reason="NOT_TRAINING_ELIGIBLE",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if not is_complete_market_context(market_context_from_row(observation)):
                return self._reject(
                    connection,
                    reason="INCOMPLETE_CONTEXT",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if self._text(outcome.get("symbol")).upper() != self._text(observation.get("symbol")).upper():
                return self._reject(
                    connection,
                    reason="SYMBOL_MISMATCH",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if self._text(outcome.get("direction")).upper() != self._text(observation.get("direction")).upper():
                return self._reject(
                    connection,
                    reason="DIRECTION_MISMATCH",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            link_error = self._builder.validate_contract_link(observation, outcome)
            if link_error:
                return self._reject(
                    connection,
                    reason=f"CONTRACT_LINK:{link_error}",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if not has_complete_cost_evidence(outcome):
                return self._reject(
                    connection,
                    reason="INCOMPLETE_COST",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            joined = self._builder.join_records(observation, outcome)
            if joined.get("label_profitable") not in {True, False}:
                return self._reject(
                    connection,
                    reason="INVALID_LABEL",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if not is_complete_market_context(market_context_from_row(joined)):
                return self._reject(
                    connection,
                    reason="INCOMPLETE_CONTEXT",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            if not has_complete_cost_evidence(joined):
                return self._reject(
                    connection,
                    reason="INCOMPLETE_COST",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            compact = self._compact_training_row(joined)
            try:
                connection.execute(
                    "INSERT INTO evidence(evidence_key, candidate_id, outcome_type, "
                    "outcome_variant_id, market_event_id, observed_at_ms, "
                    "recorded_at_ms, row_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        evidence_key,
                        candidate_id,
                        outcome_type,
                        variant_id,
                        self._text(compact.get("market_event_id")),
                        int(compact["observed_at_ms"]),
                        int(compact["recorded_at_ms"]),
                        json.dumps(compact, sort_keys=True, separators=(",", ":")),
                    ),
                )
                connection.execute(
                    "INSERT INTO terminal_decisions("
                    "evidence_key, candidate_id, outcome_type, outcome_variant_id, "
                    "decision, reason, recorded_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        evidence_key, candidate_id, outcome_type, variant_id,
                        "QUALIFIED", None, int(compact["recorded_at_ms"]),
                    ),
                )
                connection.execute(
                    "DELETE FROM candidate_facts WHERE candidate_id=?",
                    (candidate_id,),
                )
                connection.commit()
            except sqlite3.IntegrityError:
                return self._reject(
                    connection,
                    reason="DUPLICATE",
                    candidate_id=candidate_id,
                    outcome_type=outcome_type,
                    outcome_variant_id=variant_id or None,
                    recorded_at_ms=recorded_at_ms,
                    evidence_key=evidence_key,
                    terminal=True,
                )
            return {
                "decision": "QUALIFIED",
                "reason": None,
                "evidence_key": evidence_key,
            }

    def inventory(self, *, after_ms: int = 0) -> dict:
        with self._lock:
            connection = self._connect()
            row = connection.execute(
                "SELECT COUNT(*), COUNT(DISTINCT market_event_id), "
                "COALESCE(MAX(recorded_at_ms), ?) FROM evidence "
                "WHERE outcome_type=? AND recorded_at_ms>?",
                (int(after_ms), self.training_outcome_type, int(after_ms)),
            ).fetchone()
            total = connection.execute(
                "SELECT COUNT(*) FROM evidence WHERE outcome_type=?",
                (self.training_outcome_type,),
            ).fetchone()[0]
            pending = connection.execute(
                "SELECT COUNT(*) FROM candidate_facts"
            ).fetchone()[0]
            recent_rejections = connection.execute(
                "SELECT COUNT(*) FROM rejections"
            ).fetchone()[0]
            reasons = dict(
                connection.execute(
                    "SELECT reason, total_count FROM rejection_counts"
                ).fetchall()
            )
            rejections = sum(int(value) for value in reasons.values())
        return {
            "outcome_type": self.training_outcome_type,
            "after_ms": int(after_ms),
            "new_completed_outcomes": int(row[0]),
            "new_independent_market_events": int(row[1]),
            "latest_recorded_at_ms": int(row[2] or after_ms),
            "total_qualified_outcomes": int(total),
            "pending_candidate_facts": int(pending),
            "rejected_evidence": int(rejections),
            "recent_rejection_rows": int(recent_rejections),
            "rejection_reasons": dict(sorted(reasons.items())),
            "issues": {},
            "issue_count": 0,
            "scan_mode": LEDGER_SOURCE_MODE,
            "ledger_generation": self.generation,
            "ledger_path": str(self.path),
        }

    def export_dataset(self, destination: str | Path) -> dict:
        """Stream the immutable qualified ledger into a training snapshot."""
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            connection = self._connect()
            rows = 0
            events: set[str] = set()
            cutoff = 0
            schema_sets = {
                "experiment_contract_versions": set(),
                "strategy_versions": set(),
                "strategy_variant_ids": set(),
                "outcome_variant_ids": set(),
                "strategy_lab_catalog_versions": set(),
            }
            with path.open("w", encoding="utf-8") as handle:
                for market_event_id, recorded_at_ms, row_json in connection.execute(
                    "SELECT market_event_id, recorded_at_ms, row_json FROM evidence "
                    "WHERE outcome_type=? "
                    "ORDER BY observed_at_ms, recorded_at_ms, candidate_id, evidence_key",
                    (self.training_outcome_type,),
                ):
                    handle.write(row_json)
                    handle.write("\n")
                    row = json.loads(row_json)
                    rows += 1
                    events.add(str(market_event_id))
                    cutoff = max(cutoff, int(recorded_at_ms))
                    schema_sets["experiment_contract_versions"].add(
                        int(row.get("experiment_contract_version", 0) or 0)
                    )
                    schema_sets["strategy_versions"].add(
                        str(row.get("strategy_version") or "UNKNOWN")
                    )
                    schema_sets["strategy_variant_ids"].add(
                        str(row.get("strategy_variant_id") or "UNKNOWN")
                    )
                    schema_sets["outcome_variant_ids"].add(
                        str(row.get("outcome_variant_id") or "UNKNOWN")
                    )
                    schema_sets["strategy_lab_catalog_versions"].add(
                        str(
                            row.get("strategy_lab_catalog_version")
                            or "NOT_LAB_RECORD"
                        )
                    )
                handle.flush()
            return {
                "rows": rows,
                "independent_market_events": len(events),
                "data_cutoff_ms": cutoff,
                "source_mode": LEDGER_SOURCE_MODE,
                "ledger_generation": self.generation,
                "ledger_path": str(self.path),
                "strategy_schema": {
                    key: sorted(values) for key, values in schema_sets.items()
                },
            }

    def rejection_summary(self) -> dict:
        return self.inventory(after_ms=0)

    def _prune_pending_locked(self, connection: sqlite3.Connection) -> None:
        cutoff = int(time.time() * 1000) - self.pending_retention_ms
        connection.execute(
            "DELETE FROM candidate_facts WHERE observed_at_ms < ?",
            (cutoff,),
        )
        connection.commit()

    @staticmethod
    def _compact_candidate(row: dict) -> dict:
        keep = (
            "schema_version", "experiment_contract_version", "decision_batch_id",
            "market_event_id", "strategy_version", "strategy_variant_id",
            "model_version", "feature_schema_version", "observation_type",
            "observed_at_ms", "environment", "execution_mode",
            "candidate_observation_id", "symbol", "direction", "pattern",
            "bucket", "rule_score", "final_score", "reference_price", "rank",
            "selected", "execution_eligible", "selection_status",
            "rejection_reason", "eligible_for_training", "features",
            "market_context", "cost_model", "virtual_policy", "paper_policy",
            "experiment_context",
        )
        return {key: row.get(key) for key in keep}

    @staticmethod
    def _compact_training_row(row: dict) -> dict:
        # Preserve the exact fields consumed by Phase-7 split/train/evaluation;
        # omit raw score/risk/structure payloads that are retained in cold raw
        # segments but are not model inputs.
        drop = {
            "score_breakdown",
            "risk_plan",
            "structure_fingerprint",
            "paper_policy",
            "experiment_context",
        }
        return {key: value for key, value in row.items() if key not in drop}
