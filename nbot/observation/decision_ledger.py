"""Append-only V3 decision/outcome ledger for approved and rejected candidates."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Mapping


VERSION = "NBOT_V3_DECISION_LEDGER_V1"
AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenDecision:
    decision_id: str
    event_id: str
    decision_time_ms: int
    symbol: str
    side: str
    setup_id: str
    release_sha: str
    model_id: str
    feature_digest: str
    ridge_score_r: float | None
    ml_mean_r: float | None
    ml_lower_r: float | None
    conservative_score_r: float | None
    rank: int | None
    runner_up_score_r: float | None
    edge_gap_r: float | None
    approved: bool
    reason: str
    bid: float
    ask: float
    quote_source: str
    policy_id: str
    sampling_probability: float
    capacity_available: bool

    def __post_init__(self) -> None:
        if not self.decision_id or not self.event_id or not self.setup_id or not self.release_sha:
            raise ValueError("DECISION_IDENTITY_INVALID")
        if self.decision_time_ms < 0 or not self.symbol or self.symbol != self.symbol.upper():
            raise ValueError("DECISION_MARKET_IDENTITY_INVALID")
        if self.side not in {"LONG", "SHORT"}:
            raise ValueError("DECISION_SIDE_INVALID")
        if not self.reason or not self.policy_id or not self.quote_source:
            raise ValueError("DECISION_REASON_INVALID")
        if not all(math.isfinite(x) and x > 0 for x in (self.bid, self.ask)) or self.bid >= self.ask:
            raise ValueError("DECISION_QUOTE_INVALID")
        if not 0 < self.sampling_probability <= 1:
            raise ValueError("DECISION_SAMPLING_PROBABILITY_INVALID")
        for value in (self.ridge_score_r, self.ml_mean_r, self.ml_lower_r, self.conservative_score_r,
                      self.runner_up_score_r, self.edge_gap_r):
            if value is not None and not math.isfinite(value):
                raise ValueError("DECISION_SCORE_INVALID")


@dataclass(frozen=True)
class MaturedOutcome:
    decision_id: str
    policy_id: str
    matured_at_ms: int
    quality: str
    exit_reason: str
    net_r: float | None
    mfe_r: float | None
    mae_r: float | None
    source_digest: str
    actual_execution: bool = False
    execution_outcome_id: str | None = None

    def __post_init__(self) -> None:
        if not self.decision_id or not self.policy_id or self.matured_at_ms < 0:
            raise ValueError("OUTCOME_IDENTITY_INVALID")
        if not self.quality or not self.exit_reason or not self.source_digest:
            raise ValueError("OUTCOME_EVIDENCE_INVALID")
        for value in (self.net_r, self.mfe_r, self.mae_r):
            if value is not None and not math.isfinite(value):
                raise ValueError("OUTCOME_VALUE_INVALID")


SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS frozen_decisions(
 decision_id TEXT PRIMARY KEY,event_id TEXT NOT NULL,decision_time_ms INTEGER NOT NULL,
 symbol TEXT NOT NULL,side TEXT NOT NULL,approved INTEGER NOT NULL,
 reason TEXT NOT NULL,policy_id TEXT NOT NULL,payload_json TEXT NOT NULL,digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS frozen_decisions_event ON frozen_decisions(event_id,decision_time_ms);
CREATE INDEX IF NOT EXISTS frozen_decisions_symbol ON frozen_decisions(symbol,decision_time_ms);
CREATE TABLE IF NOT EXISTS matured_outcomes(
 decision_id TEXT NOT NULL,policy_id TEXT NOT NULL,matured_at_ms INTEGER NOT NULL,
 quality TEXT NOT NULL,actual_execution INTEGER NOT NULL,payload_json TEXT NOT NULL,digest TEXT NOT NULL,
 PRIMARY KEY(decision_id,policy_id,actual_execution),
 FOREIGN KEY(decision_id) REFERENCES frozen_decisions(decision_id)
);
CREATE TABLE IF NOT EXISTS unresolved_outcomes(
 decision_id TEXT NOT NULL,policy_id TEXT NOT NULL,recorded_at_ms INTEGER NOT NULL,
 reason TEXT NOT NULL,detail_json TEXT NOT NULL,digest TEXT NOT NULL,
 PRIMARY KEY(decision_id,policy_id),
 FOREIGN KEY(decision_id) REFERENCES frozen_decisions(decision_id)
);
CREATE TRIGGER IF NOT EXISTS frozen_decisions_no_update BEFORE UPDATE ON frozen_decisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_DECISION'); END;
CREATE TRIGGER IF NOT EXISTS frozen_decisions_no_delete BEFORE DELETE ON frozen_decisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_DECISION'); END;
CREATE TRIGGER IF NOT EXISTS matured_outcomes_no_update BEFORE UPDATE ON matured_outcomes BEGIN SELECT RAISE(ABORT,'IMMUTABLE_OUTCOME'); END;
CREATE TRIGGER IF NOT EXISTS matured_outcomes_no_delete BEFORE DELETE ON matured_outcomes BEGIN SELECT RAISE(ABORT,'IMMUTABLE_OUTCOME'); END;
"""


class DecisionLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute("INSERT OR IGNORE INTO ledger_metadata VALUES('version',?)", (VERSION,))
            conn.execute("INSERT OR IGNORE INTO ledger_metadata VALUES('authority',?)", (AUTHORITY,))

    def record_decision(self, decision: FrozenDecision, *, extras: Mapping[str, Any] | None = None) -> str:
        self.initialize()
        payload = asdict(decision)
        payload["authority"] = AUTHORITY
        payload["extras"] = dict(extras or {})
        encoded, digest = _json(payload), _digest(payload)
        with self._connect() as conn:
            row = conn.execute("SELECT digest FROM frozen_decisions WHERE decision_id=?", (decision.decision_id,)).fetchone()
            if row is not None:
                if row[0] != digest:
                    raise ValueError("DECISION_ID_REUSE_WITH_DIFFERENT_PAYLOAD")
                return digest
            conn.execute(
                "INSERT INTO frozen_decisions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (decision.decision_id, decision.event_id, decision.decision_time_ms, decision.symbol,
                 decision.side, int(decision.approved), decision.reason, decision.policy_id, encoded, digest),
            )
        return digest

    def record_outcome(self, outcome: MaturedOutcome) -> str:
        self.initialize()
        payload = asdict(outcome)
        payload["authority"] = AUTHORITY
        encoded, digest = _json(payload), _digest(payload)
        key = (outcome.decision_id, outcome.policy_id, int(outcome.actual_execution))
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM frozen_decisions WHERE decision_id=?", (outcome.decision_id,)).fetchone() is None:
                raise ValueError("OUTCOME_DECISION_UNKNOWN")
            row = conn.execute(
                "SELECT digest FROM matured_outcomes WHERE decision_id=? AND policy_id=? AND actual_execution=?", key
            ).fetchone()
            if row is not None:
                if row[0] != digest:
                    raise ValueError("OUTCOME_ID_REUSE_WITH_DIFFERENT_PAYLOAD")
                return digest
            conn.execute(
                "INSERT INTO matured_outcomes VALUES(?,?,?,?,?,?,?)",
                (outcome.decision_id, outcome.policy_id, outcome.matured_at_ms, outcome.quality,
                 int(outcome.actual_execution), encoded, digest),
            )
        return digest

    def record_unresolved(self, decision_id: str, policy_id: str, recorded_at_ms: int,
                          reason: str, detail: Mapping[str, Any] | None = None) -> str:
        self.initialize()
        payload = {"decision_id": decision_id, "policy_id": policy_id, "recorded_at_ms": int(recorded_at_ms),
                   "reason": str(reason), "detail": dict(detail or {}), "authority": AUTHORITY}
        digest = _digest(payload)
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM frozen_decisions WHERE decision_id=?", (decision_id,)).fetchone() is None:
                raise ValueError("OUTCOME_DECISION_UNKNOWN")
            row = conn.execute("SELECT digest FROM unresolved_outcomes WHERE decision_id=? AND policy_id=?",
                               (decision_id, policy_id)).fetchone()
            if row is not None and row[0] != digest:
                raise ValueError("UNRESOLVED_ID_REUSE_WITH_DIFFERENT_PAYLOAD")
            conn.execute("INSERT OR IGNORE INTO unresolved_outcomes VALUES(?,?,?,?,?,?)",
                         (decision_id, policy_id, int(recorded_at_ms), str(reason), _json(payload), digest))
        return digest

    def has_terminal_research_outcome(self, decision_id: str, policy_id: str) -> bool:
        self.initialize()
        with self._connect() as conn:
            matured = conn.execute(
                "SELECT 1 FROM matured_outcomes WHERE decision_id=? AND policy_id=? AND actual_execution=0",
                (decision_id, policy_id),
            ).fetchone()
            unresolved = conn.execute(
                "SELECT 1 FROM unresolved_outcomes WHERE decision_id=? AND policy_id=?",
                (decision_id, policy_id),
            ).fetchone()
        return matured is not None or unresolved is not None

    def pending_decisions(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as conn:
            rows = conn.execute("""SELECT d.payload_json FROM frozen_decisions d
                WHERE NOT EXISTS(SELECT 1 FROM matured_outcomes o WHERE o.decision_id=d.decision_id AND o.actual_execution=0)
                  AND NOT EXISTS(SELECT 1 FROM unresolved_outcomes u WHERE u.decision_id=d.decision_id)
                ORDER BY d.decision_time_ms,d.decision_id""").fetchall()
        return [json.loads(row[0]) for row in rows]

    def counts(self) -> dict[str, int]:
        self.initialize()
        with self._connect() as conn:
            approved, rejected = conn.execute(
                "SELECT SUM(approved),SUM(CASE WHEN approved=0 THEN 1 ELSE 0 END) FROM frozen_decisions"
            ).fetchone()
            matured = conn.execute("SELECT COUNT(*) FROM matured_outcomes WHERE actual_execution=0").fetchone()[0]
            actual = conn.execute("SELECT COUNT(*) FROM matured_outcomes WHERE actual_execution=1").fetchone()[0]
            unresolved = conn.execute("SELECT COUNT(*) FROM unresolved_outcomes").fetchone()[0]
        return {"approved": int(approved or 0), "rejected": int(rejected or 0), "matured_research": int(matured),
                "actual_execution": int(actual), "unresolved": int(unresolved)}
