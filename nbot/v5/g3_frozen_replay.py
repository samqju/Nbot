"""Read-only G3 replay against strictly accepted ORIGINAL G2 event witnesses.

Never starts source collection. No online API, label, model or order authority.
The availability at feature-valid-from commit and original quote sampling
clocks are tracked separately: REST finality MUST NOT retroactively improve
earlier bid/ask freshness. Incomplete/tampered evidence returns HOLD.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from nbot.v5.g2_source_acceptance import source_acceptance, AcceptanceHold
from nbot.v5.g3_market_context import BARS, FEATURE_VERSION, classify_event
from nbot.v5.observation_contract import INTERVAL_MS


class G3Hold(ValueError):
    pass


def _from_frozen_event(db: sqlite3.Connection, event:int,
                       committed:int, symbols:tuple[str,...]) -> dict:
    witnesses={}
    candles={}
    rows=db.execute(
        "SELECT symbol,asof_ms,payload_json,payload_sha FROM g2_quote_witness "
        "WHERE event_open_ms=?",(event,)
    ).fetchall()
    if len(rows)!=len(symbols) or {r[0] for r in rows}!=set(symbols):
        raise G3Hold("G3_INCOMPLETE_ORIGINAL_QUOTES")
    for symbol,sampled,raw,sha in rows:
        if hashlib.sha256(raw.encode()).hexdigest()!=sha:
            raise G3Hold("G3_QUOTE_PAYLOAD_CHANGED")
        evidence=json.loads(raw)
        if (evidence["symbol"]!=symbol
                or evidence["asof_ms"]!=sampled
                or evidence["event_open_ms"]!=event
                or evidence["paper_fill_grade"]!="UNVERIFIED"
                or evidence["order_authority"]!="NONE"):
            raise G3Hold("G3_QUOTE_SOURCE_PROOF_INVALID")
        witnesses[symbol]={"sampled_at_ms":sampled,"source":evidence["source"]}
        history=db.execute(
            "SELECT open_ms,candle_json,candle_sha,first_seen_ms "
            "FROM candle_rows WHERE symbol=? AND open_ms<=? "
            "ORDER BY open_ms DESC LIMIT ?",(symbol,event,BARS)
        ).fetchall()
        if len(history)!=BARS:
            raise G3Hold("G3_HISTORICAL_BARS_MISSING")
        history.reverse()
        bundle=[]
        for i,(bar_ms,raw_candle,sha,seen) in enumerate(history):
            expected=event-(BARS-1-i)*INTERVAL_MS
            if (bar_ms!=expected or type(seen) is not int or seen>committed
                    or seen<bar_ms+INTERVAL_MS
                    or hashlib.sha256(raw_candle.encode()).hexdigest()!=sha):
                raise G3Hold("G3_ASOF_BAR_EVIDENCE_INVALID")
            bar=json.loads(raw_candle)
            if not isinstance(bar,list) or len(bar)!=6 or bar[0]!=bar_ms:
                raise G3Hold("G3_CANDLE_PAYLOAD_SHAPE_INVALID")
            bundle.append(tuple(bar))
        candles[symbol]=tuple(bundle)
    result=classify_event(
        event_open_ms=event,decision_at_ms=committed,
        selected_symbols=symbols,candles=candles,witnesses=witnesses,
    )
    # Frozen source at a frozen clock must be exactly reproducible.
    assert_same=classify_event(
        event_open_ms=event,decision_at_ms=committed,
        selected_symbols=symbols,candles=candles,witnesses=witnesses,
    )
    if result!=assert_same:
        raise G3Hold("G3_NONDETERMINISTIC_FEATURES")
    return result


def audit_g3(path:str | Path, *, max_events:int=2,
             now_ms:int | None=None) -> dict:
    if type(max_events) is not int or not 1<=max_events<=12:
        raise G3Hold("G3_SAMPLE_WINDOW_INVALID")
    p=Path(path)
    if not p.is_file() or p.is_symlink():
        raise G3Hold("G3_SOURCE_DB_MISSING_OR_LINK")
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms<=0:
        raise G3Hold("G3_CLOCK_INVALID")
    try:
        g2=source_acceptance(p,min_complete_events=max_events,now_ms=now_ms)
    except (AcceptanceHold, OSError) as exc:
        raise G3Hold("G3_ORIGINAL_G2_SOURCE_UNQUALIFIED") from exc
    if g2["audit"]!="PASS":
        raise G3Hold("G3_ORIGINAL_G2_SOURCE_UNQUALIFIED")
    reports=[]
    regime_counts=Counter()
    structure_counts=Counter()
    unknowns=0
    try:
        with sqlite3.connect(p.resolve().as_uri()+"?mode=ro",uri=True,timeout=5) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise G3Hold("G3_DB_INTEGRITY_INVALID")
            cohorts=db.execute(
                "SELECT symbols_json FROM g1f_universe_snapshots").fetchall()
            if len(cohorts)!=1:
                raise G3Hold("G3_COHORT_NOT_FROZEN")
            selected=tuple(json.loads(cohorts[0][0]))
            events=db.execute(
                "SELECT event_open_ms,committed_ms FROM g1f_event_manifest "
                "WHERE state='OBSERVE_ONLY' ORDER BY event_open_ms DESC LIMIT ?",
                (max_events,)
            ).fetchall()
            if len(events)!=max_events:
                raise G3Hold("G3_NOT_ENOUGH_COMPLETE_SOURCE_EVENTS")
            for event,committed in reversed(events):
                x=_from_frozen_event(db,event,committed,selected)
                regime_counts[x["btc"]["regime"]]+=1
                unknowns+=x["unknown_coin_count"]
                structure_counts.update(v["structure"] for v in x["coins"].values())
                reports.append({
                    "event_open_ms":event,
                    "feature_valid_from_ms":committed,
                    "feature_sha256":x["feature_sha256"],
                    "btc_regime":x["btc"]["regime"],
                    "btc_confidence_score":x["btc"]["confidence_score"],
                    "btc_available":x["btc"]["valid"],
                    "breadth_available":x["breadth_available"],
                    "breadth_1h":x["breadth_1h"],
                    "available_coin_count":x["available_coin_count"],
                    "unknown_coin_count":x["unknown_coin_count"],
                    "btc_relative_long_matches":sum(
                        v["btc_relative_pattern_long"]=="MATCH"
                        for v in x["coins"].values()),
                    "btc_relative_short_matches":sum(
                        v["btc_relative_pattern_short"]=="MATCH"
                        for v in x["coins"].values()),
                })
    except (sqlite3.DatabaseError,TypeError,ValueError,KeyError,OverflowError) as exc:
        raise G3Hold("G3_FROZEN_REPLAY_UNVERIFIABLE") from exc
    return {
        "audit":"PASS" if not unknowns and len(reports)==max_events else "HOLD",
        "version":FEATURE_VERSION,
        "source_grade":"G2_LOCAL_PUBLIC_WSS_REST_WITNESS_NOT_SIGNED",
        "events_replayed":len(reports),
        "frozen_cohort_size":len(selected),
        "unknown_coin_events":unknowns,
        "regime_counts":dict(sorted(regime_counts.items())),
        "structure_counts":dict(sorted(structure_counts.items())),
        "event_evidence":reports,
        "conditional_feature_capability":"CLASSIFICATION_ONLY_NOT_ECONOMIC_EDGE",
        "model_labels_created":0,
        "recommendation_authority":"NONE",
        "order_authority":"NONE",
    }


def main() -> int:
    import argparse
    a=argparse.ArgumentParser(description="Read-only G3 frozen BTC/coin replay")
    a.add_argument("--db",required=True)
    a.add_argument("--events",type=int,default=2)
    args=a.parse_args()
    try:
        result=audit_g3(args.db,max_events=args.events)
    except (G3Hold,OSError) as exc:
        result={"audit":"HOLD","reason":str(exc),
                "recommendation_authority":"NONE","order_authority":"NONE"}
    print(json.dumps(result,sort_keys=True))
    return 0 if result["audit"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
