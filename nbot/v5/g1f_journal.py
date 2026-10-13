"""G1f append-only V5 research-*candidate* journal; never trade/train.

Current universe snapshots are point-in-time and never applied retrospectively.
All eligible LONG+SHORT slots are recorded even when unscorable. An observation
record is NOT a label, opportunity selection, recommendation or order.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Mapping, Sequence

from nbot.v5.observation_contract import INTERVAL_MS, PATTERN_IDS, SIDES
from nbot.v5.pattern_adapter import build_observations_from_closed_candles


class JournalHold(ValueError):
    pass


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


class CandidateJournal:
    def __init__(self, db: sqlite3.Connection):
        self.db=db
        db.executescript("""
            CREATE TABLE IF NOT EXISTS g1f_universe_snapshots (
                cohort_digest TEXT PRIMARY KEY,
                selected_at_ms INTEGER NOT NULL,
                selection_version TEXT NOT NULL,
                symbols_json TEXT NOT NULL,
                first_event_open_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS g1f_event_manifest (
                event_open_ms INTEGER PRIMARY KEY,
                cohort_digest TEXT NOT NULL,
                committed_ms INTEGER NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('OBSERVE_ONLY','HOLD')),
                verification_json TEXT NOT NULL,
                verification_sha TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS g1f_candidate_events (
                decision_id TEXT PRIMARY KEY,
                event_open_ms INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL CHECK(direction IN ('LONG','SHORT')),
                status TEXT NOT NULL CHECK(status IN ('OBSERVED','UNSCORABLE')),
                record_sha TEXT NOT NULL,
                record_json TEXT NOT NULL,
                UNIQUE(event_open_ms,symbol,direction)
            );
            CREATE TRIGGER IF NOT EXISTS g1f_cohort_no_update BEFORE UPDATE
                ON g1f_universe_snapshots BEGIN SELECT RAISE(ABORT,'G1F_IMMUTABLE'); END;
            CREATE TRIGGER IF NOT EXISTS g1f_cohort_no_delete BEFORE DELETE
                ON g1f_universe_snapshots BEGIN SELECT RAISE(ABORT,'G1F_IMMUTABLE'); END;
            CREATE TRIGGER IF NOT EXISTS g1f_manifest_no_update BEFORE UPDATE
                ON g1f_event_manifest BEGIN SELECT RAISE(ABORT,'G1F_IMMUTABLE'); END;
            CREATE TRIGGER IF NOT EXISTS g1f_manifest_no_delete BEFORE DELETE
                ON g1f_event_manifest BEGIN SELECT RAISE(ABORT,'G1F_IMMUTABLE'); END;
            CREATE TRIGGER IF NOT EXISTS g1f_candidate_no_update BEFORE UPDATE
                ON g1f_candidate_events BEGIN SELECT RAISE(ABORT,'G1F_IMMUTABLE'); END;
            CREATE TRIGGER IF NOT EXISTS g1f_candidate_no_delete BEFORE DELETE
                ON g1f_candidate_events BEGIN SELECT RAISE(ABORT,'G1F_IMMUTABLE'); END;
        """)

    def begin_cohort(self, symbols: Sequence[str], *, selected_ms: int,
                     event_open_ms: int) -> str:
        from nbot.v5.ws_contract import stream_urls
        if type(selected_ms) is not int or type(event_open_ms) is not int:
            raise JournalHold("G1F_COHORT_TIMESTAMPS_INVALID")
        stream_urls(symbols,quote_mode="depth5@500ms")
        if "BTCUSDT" not in symbols:
            raise JournalHold("G1F_BTC_NOT_IN_RANKED_COHORT")
        if event_open_ms % INTERVAL_MS:
            raise JournalHold("G1F_COHORT_EVENT_INVALID")
        normalized=tuple(sorted(symbols))
        existing=self.db.execute(
            "SELECT cohort_digest,symbols_json FROM g1f_universe_snapshots "
            "ORDER BY selected_at_ms LIMIT 1"
        ).fetchone()
        identity=digest({"selection_version":"USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
                         "symbols":normalized})
        if existing:
            if existing!=(identity,canonical(normalized)):
                raise JournalHold("G1F_COHORT_ROTATION_REQUIRES_REVIEW")
            return identity
        if self.db.execute("SELECT COUNT(*) FROM g1f_event_manifest").fetchone()[0]:
            raise JournalHold("G1F_EVENTS_WITHOUT_COHORT")
        with self.db:
            self.db.execute("""
                INSERT INTO g1f_universe_snapshots
                (cohort_digest,selected_at_ms,selection_version,
                 symbols_json,first_event_open_ms) VALUES (?,?,?,?,?)
            """,(identity,selected_ms,"USDM_PERPETUAL_24H_QUOTE_VOLUME_V1",
                  canonical(normalized),event_open_ms))
        return identity

    def latest_event(self) -> int | None:
        return self.db.execute(
            "SELECT MAX(event_open_ms) FROM g1f_event_manifest"
        ).fetchone()[0]

    def commit_event(self, *, cohort_digest: str, event_open_ms: int,
                     observed_ms: int, eligible_symbols: Sequence[str],
                     candles_by_symbol: Mapping[str,Sequence[tuple]],
                     quarantine: Mapping[str,Sequence[str]],
                     health_holds: Mapping[str,Sequence[str]],
                     btc_valid: bool, coverage_valid: bool) -> dict:
        if (type(event_open_ms) is not int or event_open_ms % INTERVAL_MS
                or type(observed_ms) is not int
                or observed_ms < event_open_ms+INTERVAL_MS):
            raise JournalHold("G1F_EVENT_NOT_FINAL")
        cohort=self.db.execute(
            "SELECT symbols_json FROM g1f_universe_snapshots "
            "WHERE cohort_digest=?",(cohort_digest,)
        ).fetchone()
        if not cohort or tuple(sorted(eligible_symbols)) != tuple(json.loads(cohort[0])):
            raise JournalHold("G1F_COHORT_SOURCE_MISMATCH")
        existing=self.latest_event()
        if existing is not None and event_open_ms <= existing:
            raise JournalHold("G1F_EVENT_REPLAY_OR_REWIND")
        # A crash gap never manufactures intermediate opportunities.
        gap=existing is not None and event_open_ms != existing+INTERVAL_MS
        active={}
        reasons={}
        for symbol in eligible_symbols:
            issues=list(quarantine.get(symbol,()))+list(health_holds.get(symbol,()))
            if not btc_valid:
                issues.append("BTC_SOURCE_NOT_VERIFIED")
            if not coverage_valid:
                issues.append("COHORT_COVERAGE_NOT_VERIFIED")
            if gap:
                issues.append("EVENT_CURSOR_GAP")
            if issues:
                reasons[symbol]=sorted(set(issues))
            elif symbol in candles_by_symbol:
                active[symbol]=candles_by_symbol[symbol]
        if "BTCUSDT" not in active:
            active.clear()
            for symbol in eligible_symbols:
                reasons.setdefault(symbol,[]).append("BTC_CONTEXT_UNAVAILABLE")
        records=build_observations_from_closed_candles(
            event_open_ms=event_open_ms,decision_at_ms=observed_ms,
            observed_at_ms=observed_ms,eligible_symbols=eligible_symbols,
            candles_by_symbol=active,
        )
        final=[]
        for record in records:
            if record["symbol"] in reasons:
                record={**record,
                        "status":"UNSCORABLE",
                        "reason_codes":sorted(set(
                            record["reason_codes"]+reasons[record["symbol"]]
                        )),
                        "patterns":{k:"UNAVAILABLE" for k in PATTERN_IDS},
                        "source_digest":None}
            if record["action"]!="OBSERVE_ONLY" or record["order_authority"]!="NONE":
                raise JournalHold("G1F_UNAUTHORIZED_RECORD")
            final.append(record)
        state="OBSERVE_ONLY" if all(r["status"]=="OBSERVED" for r in final) else "HOLD"
        summary={"cohort_digest":cohort_digest,"event_open_ms":event_open_ms,
                 "status":state,
                 "observed":sum(r["status"]=="OBSERVED" for r in final),
                 "unscorable":sum(r["status"]=="UNSCORABLE" for r in final),
                 "btc_valid":btc_valid,"coverage_valid":coverage_valid,
                 "gap":gap,"research_ready":False,
                 "training_labels_created":0,"order_authority":"NONE"}
        with self.db:
            for record in final:
                packed=canonical(record)
                self.db.execute("""
                    INSERT INTO g1f_candidate_events
                    (decision_id,event_open_ms,symbol,direction,status,record_sha,record_json)
                    VALUES (?,?,?,?,?,?,?)
                """,(record["decision_id"],event_open_ms,
                     record["symbol"],record["side"],record["status"],
                     hashlib.sha256(packed.encode()).hexdigest(),packed))
            self.db.execute("""
                INSERT INTO g1f_event_manifest
                (event_open_ms,cohort_digest,committed_ms,state,
                 verification_json,verification_sha)
                VALUES (?,?,?,?,?,?)
            """,(event_open_ms,cohort_digest,observed_ms,state,
                  canonical(summary),digest(summary)))
        return summary

    def inspect(self):
        last=self.latest_event()
        rows=self.db.execute(
            "SELECT COUNT(*),SUM(status='OBSERVED'),SUM(status='UNSCORABLE') "
            "FROM g1f_candidate_events"
        ).fetchone()
        state=self.db.execute("PRAGMA quick_check").fetchone()[0]
        if state!="ok":
            raise JournalHold("G1F_SQLITE_INTEGRITY_FAILED")
        return {"last_event_open_ms":last,"candidate_rows":rows[0] or 0,
                "observed_rows":rows[1] or 0,"unscorable_rows":rows[2] or 0,
                "research_ready":False,"training_labels_created":0,
                "order_authority":"NONE"}
