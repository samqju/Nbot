"""G2 independent read-only prospective source/witness acceptance verification.

This audit never starts a collector, never changes SQLite, cannot generate
labels/orders, and does not claim WSS transport messages are exchange-signed.
Only events with ORIGINAL at-event witness payloads can be accepted.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Sequence

from nbot.v5.g1f_journal import canonical, digest
from nbot.v5.g2_population_audit import audit_population
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import select_universe


class AcceptanceHold(ValueError):
    pass


def source_acceptance(path: str | Path, *, min_complete_events: int = 2,
                      now_ms: int | None = None) -> dict:
    if type(min_complete_events) is not int or not 1 <= min_complete_events <= 48:
        raise AcceptanceHold("G2_INVALID_REQUIRED_WINDOW")
    path=Path(path)
    if not path.is_file() or path.is_symlink():
        raise AcceptanceHold("G2_DB_MISSING_OR_LINK")
    base=audit_population(path,now_ms=now_ms)
    if base["audit"] != "PASS":
        raise AcceptanceHold("G2_POPULATION_INTEGRITY_NOT_PROVEN")
    errors=set()
    checked=0
    healthy_complete_events=0
    source_held=0
    verified=0
    src_status={}
    cohort_sha=None
    try:
        with sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=5) as db:
            c=db.execute(
                "SELECT cohort_digest,first_event_open_ms,received_ms,"
                "payload_json,payload_sha FROM g2_cohort_witness"
            ).fetchall()
            if len(c)!=1:
                raise AcceptanceHold("G2_WITNESSED_COHORT_NOT_UNIQUE")
            cohort,first,receive,raw,sha=c[0]
            cohort_sha=sha
            if cohort!=base["cohort_digest"] or hashlib.sha256(raw.encode()).hexdigest()!=sha:
                errors.add("SOURCE_COHORT_HASH_MISMATCH")
            data=json.loads(raw)
            ranked=select_universe(data["exchange"],data["ticker"],
                                   limit=len(data["ranked_selected"]))
            if (tuple(data["ranked_selected"])!=ranked
                    or len(ranked)!=base["cohort_size"]
                    or data["cohort_digest"]!=cohort
                    or data["first_event_open_ms"]!=first
                    or data["received_ms"]!=receive
                    or receive < first+INTERVAL_MS
                    or receive >= first+2*INTERVAL_MS
                    or data["server_ms"] > receive
                    or receive-data["server_ms"] > 90000):
                errors.add("COHORT_SNAPSHOT_NOT_REPRODUCIBLE")
            selected=set(ranked)
            frames=db.execute(
                "SELECT event_open_ms,committed_ms,state "
                "FROM g1f_event_manifest ORDER BY event_open_ms"
            ).fetchall()
            for event,committed,state in frames:
                checked+=1
                witness=db.execute(
                    "SELECT symbol,asof_ms,payload_json,payload_sha "
                    "FROM g2_quote_witness WHERE event_open_ms=?",
                    (event,)
                ).fetchall()
                if len(witness)!=len(selected) or {r[0] for r in witness}!=selected:
                    errors.add("WITNESS_EVENT_DENOMINATOR_MISSING")
                    continue
                candidate={
                    (row[0],row[1]):row[2]
                    for row in db.execute(
                        "SELECT symbol,direction,status FROM g1f_candidate_events "
                        "WHERE event_open_ms=?",(event,)
                    )
                }
                for symbol,asof,raw,sha in witness:
                    if (hashlib.sha256(raw.encode()).hexdigest()!=sha
                            or not event+INTERVAL_MS<=asof<=committed
                            or asof>=event+2*INTERVAL_MS):
                        errors.add("WITNESS_EVIDENCE_SHA_OR_CLOCK_INVALID")
                        continue
                    p=json.loads(raw)
                    x=p["source"]
                    reasons=[]
                    if not x["market_connected"] or not x["public_connected"]:
                        reasons.append("SOURCE_DISCONNECTED")
                    if (not isinstance(x["quote_received_ms"],int)
                            or not 0<=asof-x["quote_received_ms"]<=5000):
                        reasons.append("QUOTE_STALE_OR_MISSING")
                    if (not isinstance(x["trade_received_ms"],int)
                            or not 0<=asof-x["trade_received_ms"]<=15000):
                        reasons.append("TRADE_STALE_OR_MISSING")
                    if not isinstance(x["market_epoch"],int) or x["market_epoch"]<1:
                        reasons.append("SOURCE_EPOCH_UNKNOWN")
                    if not isinstance(x["public_epoch"],int) or x["public_epoch"]<1:
                        reasons.append("SOURCE_EPOCH_UNKNOWN")
                    # The writer applies additional quote bid/ask/spread tests.
                    # Require writer's captured grades to be reproducible.
                    from nbot.v5.g2_source_witness import MAX_SPREAD_FRAC
                    import math
                    bid,ask=x["bid"],x["ask"]
                    if (type(bid) not in (int,float) or type(ask) not in (int,float)
                            or not math.isfinite(bid) or not math.isfinite(ask)
                            or bid<=0 or ask<=bid or (ask-bid)/bid>MAX_SPREAD_FRAC):
                        reasons.append("QUOTE_UNSAFE")
                    reasons=tuple(sorted(set(reasons)))
                    if (p["cohort_digest"]!=cohort or p["symbol"]!=symbol
                            or p["event_open_ms"]!=event or p["asof_ms"]!=asof
                            or tuple(p["hold_reasons"])!=reasons
                            or p["status"]!=("HOLD" if reasons else "SOURCE_RECORDED")
                            or p["paper_fill_grade"]!="UNVERIFIED"
                            or p["order_authority"]!="NONE"):
                        errors.add("WITNESS_HEALTH_OR_AUTHORITY_MISMATCH")
                    if reasons:
                        source_held+=1
                        src_status[(event,symbol)]="HOLD"
                        if any(candidate.get((symbol,side))!="UNSCORABLE"
                               for side in ("LONG","SHORT")):
                            errors.add("HELD_SOURCE_WAS_ACCEPTED")
                    else:
                        verified+=1
                        src_status[(event,symbol)]="SOURCE_RECORDED"
                if src_status.get((event,"BTCUSDT"))=="HOLD" and state!="HOLD":
                    errors.add("BTC_HELD_BUT_EVENT_ACCEPTED")
                if (state=="OBSERVE_ONLY" and
                        all(src_status.get((event,s))=="SOURCE_RECORDED"
                            for s in selected)):
                    healthy_complete_events+=1
            orphan=db.execute(
                "SELECT COUNT(*) FROM g2_quote_witness "
                "WHERE event_open_ms NOT IN (SELECT event_open_ms FROM g1f_event_manifest)"
            ).fetchone()[0]
            if orphan:
                errors.add("ORPHAN_WITNESSED_EVENT")
    except AcceptanceHold:
        raise
    except (sqlite3.DatabaseError,ValueError,KeyError,TypeError) as exc:
        raise AcceptanceHold("G2_WITNESS_READ_OR_PARSE_FAILURE") from exc
    return {
        "audit":"PASS" if not errors and healthy_complete_events>=min_complete_events else "HOLD",
        "violations":sorted(errors),
        "cohort_witness_sha256":cohort_sha,
        "event_manifests":checked,
        "fully_source_verified_observation_events":healthy_complete_events,
        "required_verified_events":min_complete_events,
        "symbol_event_source_held":source_held,
        "symbol_event_source_recorded":verified,
        "complete_source_witness_rows":verified+source_held,
        "candidate_records":base["expected_directional_records"],
        "no_missing_event_slots":base["unrepresented_time_slots"]==0,
        "source_grade":"LOCAL_WSS_REST_EVIDENCE_NOT_EXCHANGE_SIGNED",
        "paper_fill_grade":"UNVERIFIED",
        "matured_outcomes":0,
        "research_ready":False,
        "order_authority":"NONE",
    }


def main() -> int:
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True)
    p.add_argument("--min-events",type=int,default=2)
    args=p.parse_args()
    try:
        r=source_acceptance(args.db,min_complete_events=args.min_events)
    except (AcceptanceHold,OSError) as exc:
        r={"audit":"HOLD","reason":str(exc),"research_ready":False,
           "order_authority":"NONE"}
    print(json.dumps(r,sort_keys=True))
    return 0 if r["audit"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(main())
