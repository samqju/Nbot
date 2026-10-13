"""Isolated, append-only V5 research evidence foundation.

No import-time initialization, no V4 database access, no order authority,
no training or paper contest admission. All writes are opt-in via initialize().
"""
from __future__ import annotations

from dataclasses import asdict
from contextlib import contextmanager, nullcontext
import hashlib
import json
from pathlib import Path
import sqlite3

from .v5_accounting import TradeAccounting, VERSION as ACCOUNTING_VERSION

VERSION = "NBOT_V5_EVIDENCE_V1"
ORDER_AUTHORITY = "NONE"
DEFAULT_LEDGER = Path("data/observation/v5/evidence.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS v5_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS v5_decisions (
    decision_id TEXT PRIMARY KEY,
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('LONG','SHORT')),
    payload_json TEXT NOT NULL,
    digest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS v5_outcomes (
    decision_id TEXT NOT NULL,
    exit_policy_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('SCORED','UNSCORABLE')),
    payload_json TEXT NOT NULL,
    digest TEXT NOT NULL,
    PRIMARY KEY(decision_id,exit_policy_id),
    FOREIGN KEY(decision_id) REFERENCES v5_decisions(decision_id)
);
CREATE TRIGGER IF NOT EXISTS v5_decisions_no_update
BEFORE UPDATE ON v5_decisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_DECISION'); END;
CREATE TRIGGER IF NOT EXISTS v5_decisions_no_delete
BEFORE DELETE ON v5_decisions BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_DECISION'); END;
CREATE TRIGGER IF NOT EXISTS v5_outcomes_no_update
BEFORE UPDATE ON v5_outcomes BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_OUTCOME'); END;
CREATE TRIGGER IF NOT EXISTS v5_outcomes_no_delete
BEFORE DELETE ON v5_outcomes BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_OUTCOME'); END;
"""


def _encoded(payload: dict) -> tuple[str, str]:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


class V5EvidenceStore:
    def __init__(self, path: str | Path = DEFAULT_LEDGER) -> None:
        self.path = Path(path)
        if self.path.resolve().parent.name.lower() != "v5":
            raise ValueError("V5_LEDGER_MUST_LIVE_IN_V5_DIRECTORY")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.path), timeout=30)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA synchronous=FULL")
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS v5_observed_pairs (
                    decision_id TEXT PRIMARY KEY,
                    contract TEXT NOT NULL, authority_path TEXT NOT NULL,
                    payload_json TEXT NOT NULL, digest TEXT NOT NULL,
                    FOREIGN KEY(decision_id) REFERENCES v5_decisions(decision_id));
                CREATE TRIGGER IF NOT EXISTS v5_observed_no_update
                    BEFORE UPDATE ON v5_observed_pairs
                    BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_OBSERVATION'); END;
                CREATE TRIGGER IF NOT EXISTS v5_observed_no_delete
                    BEFORE DELETE ON v5_observed_pairs
                    BEGIN SELECT RAISE(ABORT,'IMMUTABLE_V5_OBSERVATION'); END;
            """)
            for key, value in (
                ("version", VERSION),
                ("accounting_version", ACCOUNTING_VERSION),
                ("order_authority", ORDER_AUTHORITY),
            ):
                conn.execute(
                    "INSERT OR IGNORE INTO v5_metadata(key,value) VALUES (?,?)",
                    (key, value),
                )
            stored = dict(conn.execute("SELECT key,value FROM v5_metadata"))
            if any(stored.get(k) != v for k, v in (
                ("version", VERSION),
                ("accounting_version", ACCOUNTING_VERSION),
                ("order_authority", ORDER_AUTHORITY),
            )):
                raise ValueError("V5_LEDGER_CONTRACT_MISMATCH")

    @staticmethod
    def _append(conn: sqlite3.Connection, *, table: str, key: tuple, columns: tuple,
                values: tuple, digest: str) -> None:
        if table not in {"v5_decisions", "v5_outcomes"}:
            raise ValueError("V5_TABLE_INVALID")
        column_sql = ",".join(columns)
        marks = ",".join("?" for _ in columns)
        conn.execute(
            f"INSERT OR IGNORE INTO {table} ({column_sql}) VALUES ({marks})", values
        )
        where = " AND ".join(f"{column}=?" for column in
                             (("decision_id",) if table == "v5_decisions"
                              else ("decision_id", "exit_policy_id")))
        stored = conn.execute(
            f"SELECT digest FROM {table} WHERE {where}", key
        ).fetchone()
        if stored is None or stored[0] != digest:
            raise ValueError("V5_IMMUTABLE_ID_REUSED_WITH_DIFFERENT_PAYLOAD")

    def record_decision(
        self, *, decision_id: str, event_open_ms: int, symbol: str, side: str,
        setup_id: str, qualified: bool, reason: str, feature_digest: str,
        selection_policy_id: str,
    ) -> None:
        if (not all((decision_id, symbol, setup_id, reason, feature_digest,
                     selection_policy_id))
                or symbol != symbol.upper() or side not in ("LONG", "SHORT")
                or type(event_open_ms) is not int or event_open_ms < 0
                or event_open_ms % 300_000):
            raise ValueError("V5_DECISION_INVALID")
        if type(qualified) is not bool:
            raise ValueError("V5_DECISION_QUALIFICATION_INVALID")
        payload = {
            "v": VERSION, "decision_id": decision_id, "event_open_ms": event_open_ms,
            "symbol": symbol, "side": side, "setup_id": setup_id,
            "qualified": qualified, "reason": reason,
            "feature_digest": feature_digest,
            "selection_policy_id": selection_policy_id,
        }
        raw, digest = _encoded(payload)
        with self._connect() as conn:
            self._append(
                conn, table="v5_decisions", key=(decision_id,),
                columns=("decision_id","event_open_ms","symbol","side","payload_json","digest"),
                values=(decision_id,event_open_ms,symbol,side,raw,digest), digest=digest,
            )

    def record_outcome(
        self, *, decision_id: str, exit_policy_id: str,
        evidence_digest: str, result: TradeAccounting | None,
        unscorable_reason: str | None = None,
        _connection=None,
    ) -> None:
        if not all((decision_id, exit_policy_id, evidence_digest)):
            raise ValueError("V5_OUTCOME_IDENTITY_INVALID")
        if result is None:
            if not unscorable_reason:
                raise ValueError("V5_UNSCORABLE_REASON_REQUIRED")
            status, accounting = "UNSCORABLE", None
        else:
            if not isinstance(result, TradeAccounting) or unscorable_reason:
                raise ValueError("V5_OUTCOME_INVALID")
            if result.policy_version != ACCOUNTING_VERSION:
                raise ValueError("V5_OUTCOME_ACCOUNTING_MISMATCH")
            status, accounting = "SCORED", asdict(result)
        payload = {
            "v": VERSION, "decision_id": decision_id,
            "exit_policy_id": exit_policy_id, "status": status,
            "evidence_digest": evidence_digest,
            "unscorable_reason": unscorable_reason,
            "accounting": accounting,
        }
        raw, digest = _encoded(payload)
        with (self._connect() if _connection is None else nullcontext(_connection)) as conn:
            self._append(
                conn, table="v5_outcomes",
                key=(decision_id,exit_policy_id),
                columns=("decision_id","exit_policy_id","status","payload_json","digest"),
                values=(decision_id,exit_policy_id,status,raw,digest), digest=digest,
            )

    def record_legacy_pair(self, results):
        """Atomic legacy mechanical fixture publication; not certified evidence."""
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for result in results:
                self.record_outcome(decision_id=result.decision_id,
                                    exit_policy_id=result.policy_id,
                                    evidence_digest=result.evidence_digest,
                                    result=result.accounting,
                                    unscorable_reason=result.reason if result.status=='UNSCORABLE' else None,
                                    _connection=conn)

    def status(self) -> dict:
        if not self.path.is_file():
            return {"version": VERSION, "decisions": 0, "scored": 0,
                    "unscorable": 0, "order_authority": ORDER_AUTHORITY}
        with self._connect() as conn:
            d = conn.execute("SELECT COUNT(*) FROM v5_decisions").fetchone()[0]
            results = dict(conn.execute(
                "SELECT status,COUNT(*) FROM v5_outcomes GROUP BY status"
            ))
        return {
            "version": VERSION, "decisions": d,
            "scored": results.get("SCORED",0),
            "legacy_scored": results.get("SCORED",0), "certified": 0,
            "unscorable": results.get("UNSCORABLE",0),
            "order_authority": ORDER_AUTHORITY,
        }

    def record_observed_pair(self, results, *, authority):
        """One atomic append for all arms; legacy outcomes are never rewritten."""
        from .v5_evidence_trust import CONTRACT
        from .v5_paired_exits import EXIT_POLICIES
        from .v5_live_evidence import LiveEvidenceBridge
        if (not isinstance(authority, LiveEvidenceBridge) or not authority.ready
                or authority.integrity_fault is not None or len(results) != 3
                or {r.policy_id for r in results} != set(EXIT_POLICIES)
                or len({r.decision_id for r in results}) != 1
                or len({r.evidence_digest for r in results}) != 1
                or len({r.status for r in results}) != 1
                or any(r.evidence_contract != CONTRACT or r.accounting is not None
                       or r.status not in {'OBSERVED_STREAM','UNSCORABLE','REVOKED'}
                       or r.evidence_class != r.status or r.proof is not None
                       for r in results)):
            raise ValueError('V5_OBSERVED_PAIR_CONTRACT_INVALID')
        decision = results[0].decision_id
        # Original immutable diagnostic survives later revocation. Consumers
        # resolve the append-only authority overlay on every read.
        with authority._lock:
            if tuple(results) != authority.lab._completed.get(decision):
                raise ValueError('V5_PAIR_NOT_CURRENT_FINALIZED_RESULT')
            raw, digest = authority.published_pair(decision)
            entry = authority.published_entry(decision)
            with self._connect() as conn:
                linked = conn.execute('SELECT symbol,side FROM v5_decisions WHERE decision_id=?',(decision,)).fetchone()
                if linked != (entry['symbol'],entry['side']):
                    raise ValueError('V5_PAIR_DECISION_PROVENANCE_MISMATCH')
                conn.execute('INSERT OR IGNORE INTO v5_observed_pairs VALUES(?,?,?,?,?)',
                             (decision, CONTRACT, str(authority.path.resolve()), raw, digest))
                old = conn.execute('SELECT digest FROM v5_observed_pairs WHERE decision_id=?',
                                   (decision,)).fetchone()
                if old[0] != digest:
                    raise ValueError('V5_IMMUTABLE_ID_REUSED_WITH_DIFFERENT_PAYLOAD')

    def observed_pairs(self, *, authority):
        """Diagnostic consumer: missing/wrong/faulted authority fails closed."""
        from .v5_evidence_trust import CONTRACT
        from .v5_live_evidence import LiveEvidenceBridge
        if (not isinstance(authority, LiveEvidenceBridge) or not authority.ready
                or authority.integrity_fault is not None):
            raise ValueError('V5_REVOCATION_AUTHORITY_UNAVAILABLE')
        output = []
        with authority._lock, self._connect() as conn:
            for decision, contract, path, raw, digest in conn.execute('SELECT * FROM v5_observed_pairs'):
                if contract != CONTRACT or path != str(authority.path.resolve()):
                    raise ValueError('V5_REVOCATION_AUTHORITY_MISMATCH')
                if hashlib.sha256(raw.encode()).hexdigest() != digest:
                    raise ValueError('V5_OBSERVED_PAIR_CORRUPT')
                if (raw,digest) != authority.published_pair(decision):
                    raise ValueError('V5_PAIR_PROVENANCE_MISMATCH')
                entry = authority.published_entry(decision)
                linked = conn.execute('SELECT symbol,side FROM v5_decisions WHERE decision_id=?',(decision,)).fetchone()
                if linked != (entry['symbol'],entry['side']):
                    raise ValueError('V5_PAIR_DECISION_PROVENANCE_MISMATCH')
                payload = json.loads(raw)
                revoked = authority.revocations(decision)
                payload['effective_class'] = 'REVOKED' if revoked else payload['arms'][0]['evidence_class']
                payload['revocations'] = revoked
                output.append(payload)
        return output

    def certified_pairs(self, *, purpose='TRAINING'):
        """No legacy SCORED or observed row qualifies for complete-path use."""
        from .v5_evidence_trust import require_certified_sample
        require_certified_sample(None, purpose=purpose)

    def submit_order(self, *_args, **_kwargs):
        raise RuntimeError("V5_HAS_NO_ORDER_AUTHORITY")
