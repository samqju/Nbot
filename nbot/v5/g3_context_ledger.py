"""V5 G3 append-only operational context ledger for independently witnessed G2 events.

Only V5 observation. Emits either reproducible BTC/coin classification or
explicit UNKNOWN/HOLD. Never makes execution proposals, labels, orders, or fills.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3

from nbot.v5.g1f_journal import canonical
from nbot.v5.g3_frozen_replay import _from_frozen_event, G3Hold

G3_LEDGER_VERSION="NBOT_V5_G3_EVENT_CONTEXT_V1"


class G3LedgerHold(ValueError):
    pass


class G3ContextLedger:
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.executescript("""
        CREATE TABLE IF NOT EXISTS g3_event_context(
          event_open_ms INTEGER PRIMARY KEY,
          payload_sha TEXT NOT NULL,
          payload_json TEXT NOT NULL
        );
        CREATE TRIGGER IF NOT EXISTS g3_context_no_update
          BEFORE UPDATE ON g3_event_context
          BEGIN SELECT RAISE(ABORT,'G3_IMMUTABLE'); END;
        CREATE TRIGGER IF NOT EXISTS g3_context_no_delete
          BEFORE DELETE ON g3_event_context
          BEGIN SELECT RAISE(ABORT,'G3_IMMUTABLE'); END;
        """)

    def record(self, *, event_open_ms:int, symbols:tuple[str,...]) -> dict:
        rows=self.db.execute(
            "SELECT committed_ms,state FROM g1f_event_manifest "
            "WHERE event_open_ms=?",(event_open_ms,)
        ).fetchall()
        if len(rows)!=1:
            raise G3LedgerHold("G3_SOURCE_EVENT_NOT_COMMITTED")
        commit,state=rows[0]
        if state=="OBSERVE_ONLY":
            try:
                features=_from_frozen_event(self.db,event_open_ms,commit,symbols)
            except G3Hold as exc:
                raise G3LedgerHold("G3_SOURCE_REPLAY_HOLD_"+str(exc)) from exc
            if (not features["btc"]["valid"]
                    or not features["breadth_available"]
                    or features["unknown_coin_count"]):
                classification="HOLD"
                reasons=["G3_UNKNOWN_OR_INCOMPLETE_CROSS_SECTION"]
            else:
                classification="OBSERVE_ONLY"
                reasons=[]
        else:
            features=None
            classification="HOLD"
            reasons=["G2_EVENT_HELD"]
        record={
            "version":G3_LEDGER_VERSION,
            "event_open_ms":event_open_ms,
            "valid_from_ms":commit,
            "cohort_size":len(symbols),
            "status":classification,
            "reasons":reasons,
            "feature_evidence":features,
            "research_ready":False,
            "training_labels_created":0,
            "recommendation_authority":"NONE",
            "order_authority":"NONE",
        }
        payload=canonical(record)
        sha=hashlib.sha256(payload.encode()).hexdigest()
        earlier=self.db.execute(
            "SELECT payload_sha,payload_json FROM g3_event_context "
            "WHERE event_open_ms=?",(event_open_ms,)
        ).fetchone()
        if earlier is not None:
            if earlier!=(sha,payload):
                raise G3LedgerHold("G3_EVENT_REPLAY_CONFLICT")
            return {"event_open_ms":event_open_ms,"status":classification,
                    "sha":sha,"idempotent":True}
        with self.db:
            self.db.execute(
                "INSERT INTO g3_event_context VALUES (?,?,?)",
                (event_open_ms,sha,payload)
            )
        return {"event_open_ms":event_open_ms,"status":classification,
                "sha":sha,"idempotent":False}
