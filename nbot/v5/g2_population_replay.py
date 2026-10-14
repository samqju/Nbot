"""G2 causal source replay for a bounded selection of complete observation events.

READ ONLY: reconstruct recorded patterns from timestamped, archived candle
source. No model, outcomes, recommendations or orders are created. Partial or
nonreproducible data always returns HOLD with explicit reasons. Candidate records
are observations, NEVER labels or modeled fills.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import hashlib
import json
import sqlite3
import time

from nbot.v5.observation_contract import INTERVAL_MS, SIDES
from nbot.v5.pattern_adapter import build_observations_from_closed_candles


class ReplayHold(ValueError):
    pass


def audit_replay(path: str | Path, *, max_events: int = 3,
                 now_ms: int | None = None) -> dict:
    if type(max_events) is not int or not 1 <= max_events <= 12:
        raise ReplayHold("G2_BAD_BOUNDED_SAMPLE")
    p=Path(path)
    if p.is_symlink() or not p.is_file():
        raise ReplayHold("G2_DB_MISSING_OR_SYMLINK")
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms <= 0:
        raise ReplayHold("G2_CLOCK_INVALID")
    problems=Counter()
    examined=0
    matched=0
    total_records=0
    times=[]
    try:
        with sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True,timeout=5) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ReplayHold("G2_DB_INTEGRITY_FAILURE")
            cohorts=db.execute(
                "SELECT cohort_digest,symbols_json FROM g1f_universe_snapshots"
            ).fetchall()
            if len(cohorts)!=1:
                raise ReplayHold("G2_FROZEN_COHORT_INVALID")
            cohort,json_symbols=cohorts[0]
            symbols=tuple(json.loads(json_symbols))
            if "BTCUSDT" not in symbols or not 1<=len(symbols)<=50:
                raise ReplayHold("G2_SYMBOL_COHORT_INVALID")
            for (event,committed,state) in db.execute(
                "SELECT event_open_ms,committed_ms,state FROM g1f_event_manifest "
                "WHERE state='OBSERVE_ONLY' ORDER BY event_open_ms DESC LIMIT ?",
                (max_events,)).fetchall():
                examined+=1
                times.append(event)
                if event+INTERVAL_MS>committed or committed>now_ms:
                    problems["EVENT_CLOCK_INVALID"]+=1
                    continue
                expected={
                    (r[0],r[1]):json.loads(r[2])
                    for r in db.execute(
                        "SELECT symbol,direction,record_json "
                        "FROM g1f_candidate_events WHERE event_open_ms=?",
                        (event,))
                }
                if len(expected)!=2*len(symbols):
                    problems["INCOMPLETE_EVENT_DENOMINATOR"]+=1
                    continue
                if any(expected.get((s,side),{}).get("status")!="OBSERVED"
                       for s in symbols for side in SIDES):
                    problems["EVENT_STATUS_INCONSISTENT"]+=1
                    continue
                decision_clocks={r.get("decision_at_ms") for r in expected.values()}
                if len(decision_clocks)!=1 or next(iter(decision_clocks))!=committed:
                    problems["NONUNIFORM_DECISION_CLOCK"]+=1
                    continue
                candles={}
                for s in symbols:
                    # Only prices received by the original commit may be used.
                    rows=db.execute(
                        "SELECT open_ms,candle_json,candle_sha,first_seen_ms "
                        "FROM candle_rows WHERE symbol=? AND open_ms<=? "
                        "ORDER BY open_ms DESC LIMIT 96",(s,event)
                    ).fetchall()
                    if len(rows)!=96:
                        problems["ARCHIVE_HISTORY_INCOMPLETE"]+=1
                        continue
                    rows.reverse()
                    if (rows[-1][0]!=event
                        or any(b[0]-a[0]!=INTERVAL_MS for a,b in zip(rows,rows[1:]))
                        or any(r[3]>committed or r[3]<0 for r in rows)):
                        problems["ARCHIVE_HISTORY_NOT_CAUSAL"]+=1
                        continue
                    source=[]
                    for open_ms,candle_json,candle_sha,_ in rows:
                        try:
                            bar=tuple(json.loads(candle_json))
                        except (TypeError,ValueError):
                            problems["ARCHIVE_CANDLE_JSON_INVALID"]+=1
                            break
                        if (len(bar)!=6 or bar[0]!=open_ms or
                                hashlib.sha256(candle_json.encode()).hexdigest()!=candle_sha):
                            problems["ARCHIVE_CANDLE_CLOCK_MISMATCH"]+=1
                            break
                        source.append(bar)
                    if len(source)==96:
                        candles[s]=source
                if len(candles)!=len(symbols):
                    continue
                reconstructed=build_observations_from_closed_candles(
                    event_open_ms=event,decision_at_ms=committed,
                    observed_at_ms=committed,
                    eligible_symbols=symbols,candles_by_symbol=candles,
                )
                if len(reconstructed)!=len(expected):
                    problems["DETECTOR_POPULATION_MISMATCH"]+=1
                    continue
                for r in reconstructed:
                    key=(r["symbol"],r["side"])
                    original=expected[key]
                    total_records+=1
                    # Only compare causally reconstructible and originally
                    # frozen detector/source feature evidence.
                    keys=("decision_id","source_digest","btc_source_digest",
                          "patterns","detector_version","status",
                          "reason_codes","universe_digest")
                    if all(original.get(k)==r.get(k) for k in keys):
                        matched+=1
                    else:
                        problems["REPLAY_FEATURE_MISMATCH"]+=1
    except (sqlite3.DatabaseError,TypeError,ValueError,KeyError) as exc:
        raise ReplayHold("G2_REPLAY_UNVERIFIABLE") from exc

    if examined==0:
        problems["NO_COMPLETE_EVENTS_TO_REPLAY"]+=1
    if total_records==0:
        problems["NO_REPRODUCIBLE_SOURCE_EVENTS"]+=1
    return {
        "audit":"PASS" if not problems else "HOLD",
        "violations":dict(sorted(problems.items())),
        "sampled_complete_events":examined,
        "event_opens_desc":times,
        "replayed_candidate_records":total_records,
        "exact_replay_matches":matched,
        "quote_snapshots_archived":False,
        "full_futures_population_verified":False,
        "matured_outcomes":0,
        "research_ready":False,
        "order_authority":"NONE",
    }


def main():
    import argparse
    p=argparse.ArgumentParser(description="G2 offline causal feature replay")
    p.add_argument("--db",default="/home/ubuntu/nbot_v5_data/g1f_observe.sqlite")
    p.add_argument("--events",type=int,default=3)
    args=p.parse_args()
    try:
        report=audit_replay(args.db,max_events=args.events)
    except (ReplayHold,OSError) as e:
        report={"audit":"HOLD","reason":str(e),"research_ready":False,
                "order_authority":"NONE"}
    print(json.dumps(report,sort_keys=True))
    return 0 if report["audit"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
