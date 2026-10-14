"""G4 independent, append-only OFFLINE research ledger. NO production DB access.

Explicitly NOT a paper portfolio ledger. SCORED is allowed only for externally
source-verified quote-constrained simulation with a frozen complete after-cost
label; historical price-path grades never count toward model training.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import sqlite3
from typing import Mapping

LEDGER_CONTRACT_VERSION = "NBOT_V5_G4_RESEARCH_LEDGER_V1"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_TERMINALS = frozenset({"SCORED", "PATH_ONLY", "CENSORED", "UNRESOLVED"})


def _sha(v: object) -> bool:
    return isinstance(v,str) and bool(_SHA.fullmatch(v))


def _json(v: object) -> str:
    return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False)


def _hash(v: object) -> str:
    return hashlib.sha256(_json(v).encode()).hexdigest()


def _finite_decimal(v: object) -> bool:
    if not isinstance(v,str):
        return False
    try:
        return Decimal(v).is_finite()
    except (InvalidOperation, ValueError):
        return False


def init_offline_ledger(db: sqlite3.Connection) -> None:
    """Call only on a FRESH separate research SQLite or :memory: in testing.

    This function intentionally has no filename, production migration or schema
    upgrade support. Never run on the live G1/G2/G3 observation SQLite.
    """
    # Fail closed when accidentally pointed at ANY known observation/F0 DB.
    # Isolated research labels must never touch G1/G2/G3 schema or V4 ledgers.
    existing={row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    forbidden={"g1f_event_manifest","g1f_candidate_events","g2_quote_witness",
               "g3_event_context","candle_rows","v5_candidate_observations",
               "research_decisions","virtual_trades","paper_trades"}
    if existing & forbidden:
        raise ValueError("G4_LIVE_OR_HISTORICAL_DB_MUTATION_FORBIDDEN")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS g4_label_intents(
          label_id TEXT PRIMARY KEY,
          decision_id TEXT NOT NULL,
          policy_sha256 TEXT NOT NULL,
          event_open_ms INTEGER NOT NULL,
          decision_at_ms INTEGER NOT NULL,
          maturity_at_ms INTEGER NOT NULL,
          intent_sha256 TEXT NOT NULL,
          intent_json TEXT NOT NULL,
          UNIQUE(decision_id,policy_sha256)
        );
        CREATE TABLE IF NOT EXISTS g4_label_terminals(
          label_id TEXT PRIMARY KEY REFERENCES g4_label_intents(label_id),
          terminal_status TEXT NOT NULL CHECK(
            terminal_status IN ('SCORED','PATH_ONLY','CENSORED','UNRESOLVED')),
          source_grade TEXT NOT NULL,
          settled_at_ms INTEGER NOT NULL,
          terminal_sha256 TEXT NOT NULL,
          terminal_json TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS g4_intent_immutable_update
        BEFORE UPDATE ON g4_label_intents
        BEGIN SELECT RAISE(ABORT,'G4_IMMUTABLE_INTENT'); END;
        CREATE TRIGGER IF NOT EXISTS g4_intent_immutable_delete
        BEFORE DELETE ON g4_label_intents
        BEGIN SELECT RAISE(ABORT,'G4_IMMUTABLE_INTENT'); END;
        CREATE TRIGGER IF NOT EXISTS g4_terminal_immutable_update
        BEFORE UPDATE ON g4_label_terminals
        BEGIN SELECT RAISE(ABORT,'G4_IMMUTABLE_TERMINAL'); END;
        CREATE TRIGGER IF NOT EXISTS g4_terminal_immutable_delete
        BEFORE DELETE ON g4_label_terminals
        BEGIN SELECT RAISE(ABORT,'G4_IMMUTABLE_TERMINAL'); END;
    """)


def freeze_label_intent(db: sqlite3.Connection, candidate: Mapping,
                        frozen_policy: Mapping) -> str:
    if not isinstance(candidate,Mapping) or not isinstance(frozen_policy,Mapping):
        raise ValueError("G4_INTENT_SHAPE_INVALID")
    did=candidate.get("decision_id")
    policy_sha=frozen_policy.get("policy_sha256")
    event=candidate.get("event_open_ms")
    at=candidate.get("decision_at_ms")
    horizon=frozen_policy.get("horizon_ms")
    declared=frozen_policy.get("declared_at_ms")
    if (not _sha(did) or not _sha(policy_sha)
            or candidate.get("status")!="OBSERVED"
            or type(event) is not int or event<0 or event%300000
            or type(at) is not int or at<event+300000
            or type(horizon) is not int or horizon<=0 or horizon%300000
            or type(declared) is not int or declared>at):
        raise ValueError("G4_INTENT_NOT_PREDECLARED_OR_CAUSAL")
    label_id=_hash({"version":LEDGER_CONTRACT_VERSION,"decision_id":did,
                    "policy_sha256":policy_sha})
    payload={"version":LEDGER_CONTRACT_VERSION,"label_id":label_id,
             "decision_id":did,"policy_sha256":policy_sha,
             "event_open_ms":event,"decision_at_ms":at,"maturity_at_ms":at+horizon,
             "side":candidate.get("side"),"symbol":candidate.get("symbol"),
             "observation_source_sha":candidate.get("source_digest"),
             "btc_source_sha":candidate.get("btc_source_digest"),
             "frozen_policy":dict(frozen_policy)}
    canonical=_json(payload)
    sha=hashlib.sha256(canonical.encode()).hexdigest()
    with db:
        old=db.execute("SELECT intent_sha256,intent_json FROM g4_label_intents WHERE label_id=?",
                       (label_id,)).fetchone()
        if old:
            if old!=(sha,canonical):
                raise ValueError("G4_INTENT_CHANGED_SAME_ID")
            return label_id
        db.execute(
            "INSERT INTO g4_label_intents VALUES (?,?,?,?,?,?,?,?)",
            (label_id,did,policy_sha,event,at,at+horizon,sha,canonical))
    return label_id


def append_terminal(db: sqlite3.Connection, label_id: str, payload: Mapping) -> bool:
    """Return True on new terminal, False on exact idempotent replay.

    Terminal cannot be changed from UNRESOLVED to SCORED in place. A later
    evidence correction must be separately reviewed and versioned, never overwrite.
    """
    if not _sha(label_id) or not isinstance(payload,Mapping):
        raise ValueError("G4_TERMINAL_INPUT_INVALID")
    state=payload.get("status")
    grade=payload.get("source_grade")
    settled=payload.get("settled_at_ms")
    if state not in _TERMINALS or type(settled) is not int:
        raise ValueError("G4_TERMINAL_STATUS_OR_CLOCK_INVALID")
    if payload.get("order_authority")!="NONE":
        raise ValueError("G4_FINANCIAL_AUTHORITY_FORBIDDEN")
    with db:
        row=db.execute("SELECT decision_at_ms,maturity_at_ms FROM g4_label_intents "
                       "WHERE label_id=?", (label_id,)).fetchone()
        if row is None:
            raise ValueError("G4_UNDECLARED_INTENT")
        decision,maturity=row
        if settled<decision or (state in ("SCORED","PATH_ONLY") and settled<maturity):
            raise ValueError("G4_TERMINAL_PREMATURE")
        if state=="SCORED":
            if (grade!="QUOTE_CONSTRAINED_SIMULATION"
                    or payload.get("original_sources_independently_verified") is not True
                    or not _sha(payload.get("path_sha256"))
                    or not _sha(payload.get("quote_cost_sha256"))
                    or not _sha(payload.get("label_sha256"))
                    or not _finite_decimal(payload.get("net_r"))
                    or not _finite_decimal(payload.get("gross_r"))):
                raise ValueError("G4_SCORED_REQUIRES_INDEPENDENT_AFTER_COST_SOURCE")
        elif state=="PATH_ONLY":
            if (grade!="HISTORICAL_AGGTRADE_PATH"
                    or not _sha(payload.get("path_sha256"))
                    or not _finite_decimal(payload.get("gross_r"))
                    or payload.get("net_r") is not None):
                raise ValueError("G4_PATH_ONLY_NEVER_ECONOMIC_SCORE")
        else:
            if payload.get("net_r") is not None or payload.get("gross_r") is not None:
                raise ValueError("G4_UNRESOLVED_OR_CENSORED_CANNOT_SCORE")
            if not payload.get("reason_codes"):
                raise ValueError("G4_MISSING_TERMINAL_REASON")
        body={"contract_version":LEDGER_CONTRACT_VERSION,
              "label_id":label_id,**dict(payload)}
        canonical=_json(body)
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        prior=db.execute("SELECT terminal_sha256,terminal_json "
                         "FROM g4_label_terminals WHERE label_id=?",(label_id,)).fetchone()
        if prior is not None:
            if prior!=(digest,canonical):
                raise ValueError("G4_CONFLICTING_TERMINAL_REJECTED")
            return False
        db.execute("INSERT INTO g4_label_terminals VALUES (?,?,?,?,?,?)",
                   (label_id,state,grade or "NONE",settled,digest,canonical))
    return True


def qualified_economic_label_count(db: sqlite3.Connection) -> int:
    """Raw qualified scored row count ONLY; no independence or training readiness."""
    return db.execute("SELECT count(*) FROM g4_label_terminals "
                      "WHERE terminal_status='SCORED' "
                      "AND source_grade='QUOTE_CONSTRAINED_SIMULATION'").fetchone()[0]


def status_breakdown(db: sqlite3.Connection) -> dict[str,int]:
    rows=db.execute("SELECT terminal_status,count(*) FROM g4_label_terminals "
                    "GROUP BY terminal_status").fetchall()
    return dict(rows)
