"""G1e remediation: immutable, per-symbol WSS/REST finality audit and quarantine.

One source conflict quarantines BOTH directions for that symbol and five-minute
event. BTC conflict blocks the whole cohort. Delayed REST agreement does NOT
retroactively forgive any earlier mismatch. Separate evidence states must
never confer production research, training, order, or portfolio authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import sqlite3
from typing import Sequence

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.candle_ledger import _row

POLICY = "V5_FINALITY_PER_SYMBOL_QUARANTINE_V1"
FIELDS = ("open", "high", "low", "close", "volume")
STAGES = ("FIRST_REST", "DELAYED_REST", "CONFIRM_REST")


def fingerprint(candle: Sequence) -> str:
    return hashlib.sha256(
        json.dumps(_row(candle), separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def single_closed_rest(payload: object, *, event_open_ms: int) -> tuple:
    """Validate exactly one explicit historical *closed* Binance 5m bar."""
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError("V5_FINALITY_REST_COUNT_INVALID")
    rec = payload[0]
    if not isinstance(rec, list) or len(rec) < 7:
        raise ValueError("V5_FINALITY_REST_SHAPE_INVALID")
    if (type(rec[0]) is not int or rec[0] != event_open_ms
            or type(rec[6]) is not int
            or rec[6] != event_open_ms + INTERVAL_MS - 1):
        raise ValueError("V5_FINALITY_REST_EVENT_INVALID")
    values = []
    for v in rec[1:6]:
        if isinstance(v, bool):
            raise ValueError("V5_FINALITY_REST_VALUE_INVALID")
        try:
            number = float(v)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("V5_FINALITY_REST_VALUE_INVALID") from exc
        if not math.isfinite(number):
            raise ValueError("V5_FINALITY_REST_VALUE_INVALID")
        values.append(number)
    return _row((event_open_ms, *values))


class FinalityQuarantine:
    """Append-only independent per-event proof in an existing V5 SQLite DB."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        db.executescript("""
            CREATE TABLE IF NOT EXISTS v5_finality_checks (
                check_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                event_open_ms INTEGER NOT NULL,
                stage TEXT NOT NULL
                  CHECK(stage IN ('FIRST_REST','DELAYED_REST','CONFIRM_REST')),
                observed_ms INTEGER NOT NULL,
                wss_sha TEXT NOT NULL,
                rest_sha TEXT NOT NULL,
                changed_fields_json TEXT NOT NULL,
                policy TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS v5_finality_unique
                ON v5_finality_checks(symbol,event_open_ms,stage);
            CREATE TABLE IF NOT EXISTS v5_quarantine_events (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                event_open_ms INTEGER NOT NULL,
                reason TEXT NOT NULL,
                observed_ms INTEGER NOT NULL,
                evidence_sha TEXT NOT NULL,
                policy TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS v5_quarantine_unique
                ON v5_quarantine_events(symbol,event_open_ms,reason);
            CREATE TRIGGER IF NOT EXISTS v5_finality_no_update
                BEFORE UPDATE ON v5_finality_checks BEGIN
                    SELECT RAISE(ABORT,'V5_FINALITY_IMMUTABLE');
                END;
            CREATE TRIGGER IF NOT EXISTS v5_finality_no_delete
                BEFORE DELETE ON v5_finality_checks BEGIN
                    SELECT RAISE(ABORT,'V5_FINALITY_IMMUTABLE');
                END;
            CREATE TRIGGER IF NOT EXISTS v5_quarantine_no_update
                BEFORE UPDATE ON v5_quarantine_events BEGIN
                    SELECT RAISE(ABORT,'V5_QUARANTINE_IMMUTABLE');
                END;
            CREATE TRIGGER IF NOT EXISTS v5_quarantine_no_delete
                BEFORE DELETE ON v5_quarantine_events BEGIN
                    SELECT RAISE(ABORT,'V5_QUARANTINE_IMMUTABLE');
                END;
        """)

    def quarantine(self, symbol: str, event_open_ms: int, reason: str,
                   *, observed_ms: int, evidence_sha: str) -> None:
        if not symbol or not reason or len(reason) > 100:
            raise ValueError("V5_FINALITY_QUARANTINE_INVALID")
        with self.db:
            self.db.execute("""
                INSERT OR IGNORE INTO v5_quarantine_events
                (symbol,event_open_ms,reason,observed_ms,evidence_sha,policy)
                VALUES (?,?,?,?,?,?)
            """, (symbol,event_open_ms,reason,observed_ms,evidence_sha,POLICY))

    def check(self, symbol: str, event_open_ms: int, stage: str,
              *, observed_ms: int, wss_candle: Sequence,
              rest_candle: Sequence) -> dict:
        if stage not in STAGES:
            raise ValueError("V5_FINALITY_STAGE_INVALID")
        if (type(observed_ms) is not int
                or observed_ms < event_open_ms + INTERVAL_MS):
            raise ValueError("V5_FINALITY_CHECK_TOO_EARLY")
        wss, rest = _row(wss_candle), _row(rest_candle)
        if wss[0] != event_open_ms or rest[0] != event_open_ms:
            raise ValueError("V5_FINALITY_CROSS_EVENT")
        if self.db.execute("""
            SELECT 1 FROM v5_finality_checks
            WHERE symbol=? AND event_open_ms=? AND stage=?
        """, (symbol,event_open_ms,stage)).fetchone():
            raise ValueError("V5_FINALITY_DUPLICATE_STAGE")
        stages = [x[0] for x in self.db.execute("""
            SELECT stage FROM v5_finality_checks
            WHERE symbol=? AND event_open_ms=? ORDER BY check_id
        """, (symbol,event_open_ms))]
        if stages != list(STAGES[:len(stages)]) or stage != STAGES[len(stages)]:
            raise ValueError("V5_FINALITY_STAGE_ORDER_INVALID")
        # No simulated delayed snapshot at the same timestamp as previous.
        if stages:
            last_ms = self.db.execute("""
                SELECT observed_ms FROM v5_finality_checks
                WHERE symbol=? AND event_open_ms=?
                ORDER BY check_id DESC LIMIT 1
            """, (symbol,event_open_ms)).fetchone()[0]
            if observed_ms <= last_ms:
                raise ValueError("V5_FINALITY_NONMONOTONIC_CHECK_TIME")
        changed = tuple(FIELDS[i-1] for i in range(1,6) if wss[i] != rest[i])
        ws_sha, rs_sha = fingerprint(wss), fingerprint(rest)
        prior_rest = self.db.execute("""
            SELECT rest_sha FROM v5_finality_checks
            WHERE symbol=? AND event_open_ms=?
            ORDER BY check_id DESC LIMIT 1
        """, (symbol,event_open_ms)).fetchone()
        revised = prior_rest is not None and prior_rest[0] != rs_sha
        with self.db:
            self.db.execute("""
                INSERT INTO v5_finality_checks
                (symbol,event_open_ms,stage,observed_ms,wss_sha,rest_sha,
                 changed_fields_json,policy) VALUES (?,?,?,?,?,?,?,?)
            """, (symbol,event_open_ms,stage,observed_ms,ws_sha,rs_sha,
                  json.dumps(changed), POLICY))
            if changed:
                self.db.execute("""
                    INSERT OR IGNORE INTO v5_quarantine_events
                    (symbol,event_open_ms,reason,observed_ms,evidence_sha,policy)
                    VALUES (?,?,?,?,?,?)
                """, (symbol,event_open_ms,"WSS_REST_MISMATCH",observed_ms,
                      rs_sha,POLICY))
            if revised:
                self.db.execute("""
                    INSERT OR IGNORE INTO v5_quarantine_events
                    (symbol,event_open_ms,reason,observed_ms,evidence_sha,policy)
                    VALUES (?,?,?,?,?,?)
                """, (symbol,event_open_ms,"REST_REVISED",observed_ms,
                      rs_sha,POLICY))
        return {
            "symbol": symbol, "stage": stage,
            "changed_fields": list(changed),
            "rest_revised_since_previous": revised,
            "wss_sha": ws_sha, "rest_sha": rs_sha,
            "quarantined": bool(self.reasons(symbol, event_open_ms)),
        }

    def reasons(self, symbol: str, event_open_ms: int) -> tuple[str,...]:
        return tuple(x[0] for x in self.db.execute("""
            SELECT reason FROM v5_quarantine_events
            WHERE symbol=? AND event_open_ms=? ORDER BY reason
        """, (symbol,event_open_ms)))

    def evidence_status(self, symbols: Sequence[str], event_open_ms: int,
                        *, min_valid: int = 10,
                        min_fraction: float = 0.8) -> dict:
        if not symbols or len(symbols) != len(set(symbols)):
            raise ValueError("V5_FINALITY_COHORT_INVALID")
        if not 0 < min_fraction <= 1 or min_valid < 1:
            raise ValueError("V5_FINALITY_COVERAGE_INVALID")
        verified, quarantined, unverified = [], [], []
        for symbol in symbols:
            states = self.db.execute("""
                SELECT stage,changed_fields_json FROM v5_finality_checks
                WHERE symbol=? AND event_open_ms=?
                ORDER BY check_id
            """, (symbol,event_open_ms)).fetchall()
            reasons = self.reasons(symbol,event_open_ms)
            if reasons:
                quarantined.append(symbol)
            elif (len(states)==len(STAGES)
                  and [x[0] for x in states] == list(STAGES)
                  and all(not json.loads(x[1]) for x in states)):
                verified.append(symbol)
            else:
                unverified.append(symbol)
        btc_ok = "BTCUSDT" in verified
        qualifies_for_later_review = (
            btc_ok and len(verified) >= min_valid
            and len(verified)/len(symbols) >= min_fraction
        )
        return {
            "policy": POLICY, "event_open_ms": event_open_ms,
            "verified_symbols": verified,
            "quarantined_symbols": quarantined,
            "unverified_symbols": unverified,
            "coverage_ratio": len(verified)/len(symbols),
            "btc_verified": btc_ok,
            "evidence_cohort_eligible_for_future_review":
                qualifies_for_later_review,
            "directional_observation_states": {
                "verified_observe_only": len(verified)*2,
                "quarantined_unscorable": len(quarantined)*2,
                "unverified_unscorable": len(unverified)*2,
            },
            "research_ready": False, "training_labels_created": 0,
            "order_authority": "NONE",
        }
