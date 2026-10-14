"""Read-only V5 integrated G1/G2/G3 operational health audit.

No network, collector starts, writes, labels, orders or file modification.
A single corrupt or missing G2/G3 witness fails readiness.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

from nbot.v5.g1f_preflight import LEGACY_UNITS
from nbot.v5.observation_contract import INTERVAL_MS

class IntegratedHealthHold(ValueError):
    pass

def audit(*,db_path:str,service:str,now_ms:int|None=None,
          runner=subprocess.run,min_events:int=2)->dict:
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    if type(now_ms) is not int or now_ms<=0 or min_events<2:
        raise IntegratedHealthHold("HEALTH_ARGUMENT_INVALID")
    if service!="nbot-v5-g1g2g3-observation.service":
        raise IntegratedHealthHold("UNKNOWN_PRODUCTION_SERVICE")
    out=runner(["systemctl","show",service,
                "-p","ActiveState","-p","UnitFileState",
                "-p","MemoryCurrent","-p","MemoryMax","-p","NRestarts"],
               capture_output=True,text=True,timeout=12)
    if out.returncode:
        raise IntegratedHealthHold("SERVICE_STATE_UNAVAILABLE")
    data={}
    for line in out.stdout.splitlines():
        if "=" in line:
            k,v=line.split("=",1)
            data[k]=v
    failures=[]
    if data.get("ActiveState")!="active" or data.get("UnitFileState")!="enabled":
        failures.append("INTEGRATED_SERVICE_NOT_RUNNING_ENABLED")
    try:
        mem=int(data["MemoryCurrent"]); limit=int(data["MemoryMax"])
        restarts=int(data["NRestarts"])
    except (ValueError,KeyError) as exc:
        raise IntegratedHealthHold("SYSTEMD_RESOURCES_NOT_VERIFIABLE") from exc
    if limit>200*1024*1024 or mem>=limit:
        failures.append("INTEGRATED_MEMORY_LIMIT_EXCEEDED")
    if restarts:
        # Any systemd restart requires explicit trace and separate review.
        failures.append("UNREVIEWED_SYSTEMD_RESTART")
    for unit in LEGACY_UNITS:
        legacy=runner(["systemctl","is-active",unit],
                      capture_output=True,text=True,timeout=12)
        if legacy.stdout.strip()!="inactive":
            failures.append("V4_LEGACY_ACTIVE_"+unit)
    loc=Path(db_path)
    if loc.is_symlink() or not loc.is_file():
        raise IntegratedHealthHold("PRODUCTION_DB_INVALID")
    with sqlite3.connect(loc.resolve().as_uri()+"?mode=ro",uri=True,timeout=8) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            failures.append("SQLITE_INTEGRITY_FAILED")
        cohorts=db.execute("SELECT symbols_json FROM g1f_universe_snapshots").fetchall()
        if len(cohorts)!=1:
            failures.append("COHORT_INVALID")
            n=0
        else:
            members=json.loads(cohorts[0][0])
            n=len(members)
            if n!=50 or "BTCUSDT" not in members:
                failures.append("COHORT_NOT_FIFTY_WITH_BTC")
        manifests=db.execute("SELECT event_open_ms,committed_ms,state "
                             "FROM g1f_event_manifest ORDER BY event_open_ms").fetchall()
        event_count=len(manifests)
        if event_count<min_events:
            failures.append("MIN_TWO_SOURCE_EVENTS_NOT_MATURE")
        if not manifests or now_ms-manifests[-1][0]>20*60_000:
            failures.append("LAST_EVENT_STALE")
        candidates=db.execute("SELECT COUNT(*) FROM g1f_candidate_events").fetchone()[0]
        if candidates!=2*n*event_count:
            failures.append("DIRECTIONAL_DENOMINATOR_MISMATCH")
        ctx=db.execute("SELECT event_open_ms,payload_sha,payload_json FROM g3_event_context "
                       "ORDER BY event_open_ms").fetchall()
        if len(ctx)!=event_count or [r[0] for r in ctx]!=[r[0] for r in manifests]:
            failures.append("G3_EVENT_CONTEXT_DENOMINATOR_MISSING")
        accepted=held=quote_rows=0
        for event,committed,state in manifests:
            source=db.execute(
                "SELECT COUNT(*) FROM g2_quote_witness WHERE event_open_ms=?",(event,)
            ).fetchone()[0]
            quote_rows+=source
            if source!=n:
                failures.append("G2_ORIGINAL_QUOTE_SOURCE_INCOMPLETE")
            if state=="OBSERVE_ONLY":
                accepted+=1
            elif state=="HOLD":
                held+=1
            else:
                failures.append("UNKNOWN_MANIFEST_STATE")
        for event,sha,payload in ctx:
            if hashlib.sha256(payload.encode()).hexdigest()!=sha:
                failures.append("G3_CONTEXT_DIGEST_INVALID")
                continue
            x=json.loads(payload)
            if (x.get("event_open_ms")!=event or
                    x.get("order_authority")!="NONE" or
                    x.get("recommendation_authority")!="NONE" or
                    x.get("training_labels_created")!=0):
                failures.append("G3_TRADING_AUTHORITY_OR_CLOCK_INVALID")
            if x.get("status")=="OBSERVE_ONLY":
                ev=x.get("feature_evidence") or {}
                if (ev.get("order_authority")!="NONE" or
                    not ev.get("btc",{}).get("valid") or
                    ev.get("unknown_coin_count") or
                    ev.get("candidate_cohort_size")!=n):
                    failures.append("G3_CONTEXT_NOT_VERIFIED")
            elif x.get("status")!="HOLD":
                failures.append("G3_CONTEXT_STATE_INVALID")
        rows=db.execute("SELECT COUNT(*) FROM g2_cohort_witness").fetchone()[0]
        if rows!=1:
            failures.append("SOURCE_SELECTION_WITNESS_MISSING")
    return {
        "status":"PASS" if not failures else "HOLD",
        "violations":sorted(set(failures)),
        "event_manifests":event_count,"candidate_rows":candidates,
        "g3_context_rows":len(ctx),"source_witness_rows":quote_rows,
        "accepted_events":accepted,"explicit_hold_events":held,
        "cohort_size":n,"memory_current_bytes":mem,
        "memory_max_bytes":limit,"service_restarts":restarts,
        "research_ready":False,"training_labels_created":0,
        "recommendation_authority":"NONE","order_authority":"NONE",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True)
    p.add_argument("--service",required=True)
    a=p.parse_args()
    try:
        report=audit(db_path=a.db,service=a.service)
    except (OSError,sqlite3.DatabaseError,ValueError,IntegratedHealthHold) as exc:
        report={"status":"HOLD","reason":str(exc),
                "order_authority":"NONE"}
    print(json.dumps(report,sort_keys=True),flush=True)
    return 0 if report["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
