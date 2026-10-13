"""Read-only two-window WSS-final and delayed REST finality diagnosis.

Disposable SQLite evidence, 50 public USDT futures coins, no account keys,
production service, trading, training, or permanent DB mutation.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import resource
import sqlite3
from tempfile import TemporaryDirectory
import time

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import public_get, select_universe, closed_event_from_server_time
from nbot.v5.ws_contract import decode_frame, stream_urls
from nbot.v5.finality_quarantine import FinalityQuarantine, STAGES, single_closed_rest

MAX_FRAMES=240000
DELAY_SECONDS=8


async def collect(symbols, target, seconds):
    from websockets.asyncio.client import connect
    uri=stream_urls(symbols, quote_mode="depth5@500ms")["market"]
    seen={}
    frames=0
    trades=0
    deadline=time.monotonic()+seconds
    async with connect(uri,open_timeout=10,close_timeout=2,
                       max_size=64000,max_queue=16,ping_interval=20,ping_timeout=20) as ws:
        while len(seen)<len(symbols) and time.monotonic()<deadline:
            if frames>=MAX_FRAMES:
                raise ValueError("V5_FINALITY_WSS_FRAME_CAP")
            try:
                data=await asyncio.wait_for(ws.recv(),timeout=min(2,max(.05,deadline-time.monotonic())))
            except asyncio.TimeoutError:
                continue
            frames+=1
            row=decode_frame("market",data,received_ms=int(time.time()*1000),
                             subscribed_symbols=symbols)
            if row["kind"]=="aggTrade":
                trades+=1
            elif row["kind"]=="kline_5m" and row["closed"] and row["candle"][0]==target:
                symbol=row["symbol"]
                if symbol in seen and seen[symbol]["candle"] != row["candle"]:
                    raise ValueError("V5_FINALITY_WSS_CLOSE_CHANGED")
                seen[symbol]=row
    return seen,{"frames":frames,"trades":trades}


async def rest_stage(audit, live, event, stage, getter):
    semaphore=asyncio.Semaphore(6)
    async def one(symbol):
        async with semaphore:
            params={
                "symbol":symbol,"interval":"5m",
                "startTime":str(event),
                "endTime":str(event+INTERVAL_MS-1),"limit":"1",
            }
            try:
                source=await asyncio.to_thread(getter,"/fapi/v1/klines",params)
                candle=single_closed_rest(source,event_open_ms=event)
                return audit.check(
                    symbol,event,stage,observed_ms=int(time.time()*1000),
                    wss_candle=live[symbol]["candle"],rest_candle=candle,
                )
            except Exception as exc:
                audit.quarantine(
                    symbol,event,"REST_STAGE_UNAVAILABLE_"+stage,
                    observed_ms=int(time.time()*1000),
                    evidence_sha="REST_UNAVAILABLE",
                )
                return {"symbol":symbol,"stage":stage,
                        "error":type(exc).__name__+":"+str(exc)[:75]}
    return await asyncio.gather(*(one(s) for s in sorted(live)))


async def run_probe(*,top=50,windows=2,seconds=338,getter=public_get):
    if (type(top) is not int or not 2<=top<=50
            or type(windows) is not int or not 1<=windows<=2
            or type(seconds) is not int or not 45<=seconds<=340):
        raise ValueError("V5_FINALITY_PROBE_BOUNDS")
    server=getter("/fapi/v1/time")["serverTime"]
    if abs(int(time.time()*1000)-server)>90000:
        raise ValueError("V5_FINALITY_CLOCK_SKEW")
    universe=select_universe(
        getter("/fapi/v1/exchangeInfo"),getter("/fapi/v1/ticker/24hr"),
        limit=top,
    )
    symbols=tuple(sorted(set(universe)|{"BTCUSDT"}))
    reports=[]
    with TemporaryDirectory(prefix="nbot_v5_finality_") as temp:
        filepath=Path(temp)/"audit.db"
        with sqlite3.connect(filepath) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            audit=FinalityQuarantine(db)
            previous_target=None
            for n in range(windows):
                server=getter("/fapi/v1/time")["serverTime"]
                if abs(int(time.time()*1000)-server)>90000:
                    raise ValueError("V5_FINALITY_CLOCK_SKEW")
                current,_=closed_event_from_server_time({"serverTime":server})
                target=current+INTERVAL_MS
                if previous_target is not None and target<=previous_target:
                    target=previous_target+INTERVAL_MS
                previous_target=target
                print("G1E_REMEDIATION_WINDOW",n+1,"of",windows,
                      "target_open_ms",target,flush=True)
                live,stats=await collect(symbols,target,seconds)
                missing=sorted(set(symbols)-set(live))
                for sym,row in live.items():
                    audit.record_wss_final(
                        sym,target,received_ms=row["received_ms"],
                        candle=row["candle"],
                    )
                for sym in missing:
                    audit.quarantine(sym,target,"WSS_FINAL_MISSING",
                                     observed_ms=int(time.time()*1000),
                                     evidence_sha="NO_FINAL")
                stages=[]
                if not missing:
                    for stage in STAGES:
                        if stage!="FIRST_REST":
                            await asyncio.sleep(DELAY_SECONDS)
                        results=await rest_stage(audit,live,target,stage,getter)
                        issues=[{
                            "symbol":x["symbol"],
                            "fields":x.get("changed_fields",[]),
                            "revised":x.get("rest_revised_since_previous",False),
                            "error":x.get("error"),
                        } for x in results if x.get("changed_fields") or "error" in x]
                        stages.append({
                            "stage":stage,
                            "matched":sum(x.get("changed_fields")==[] and "error" not in x
                                          for x in results),
                            "issues":issues,
                        })
                        print("G1E_REMEDIATION_STAGE",n+1,stage,
                              "matching",stages[-1]["matched"],
                              "issues",len(issues),flush=True)
                status=audit.evidence_status(symbols,target)
                if not missing and not any(
                    any(x.get("error") for x in stage["issues"]) for stage in stages
                ):
                    status=audit.finalize_directional_observations(symbols,target)
                # Export immutable source digests and exact REST observation
                # timestamps for discrepant symbols before ephemeral DB cleanup.
                timelines={}
                for disputed in status["quarantined_symbols"]:
                    checks=db.execute("""
                        SELECT stage,observed_ms,wss_sha,rest_sha,changed_fields_json
                        FROM v5_finality_checks
                        WHERE symbol=? AND event_open_ms=? ORDER BY check_id
                    """,(disputed,target)).fetchall()
                    timelines[disputed]=[
                        {"stage":stage_name,"observed_ms":seen,
                         "wss_sha":wss_digest,"rest_sha":rest_digest,
                         "changed_fields":json.loads(fields)}
                        for stage_name,seen,wss_digest,rest_digest,fields in checks
                    ]
                stage_times={}
                for stage_name in STAGES:
                    bounds=db.execute("""
                        SELECT MIN(observed_ms),MAX(observed_ms)
                        FROM v5_finality_checks
                        WHERE event_open_ms=? AND stage=?
                    """,(target,stage_name)).fetchone()
                    if bounds[0] is not None:
                        stage_times[stage_name]={
                            "first_ms":bounds[0],"last_ms":bounds[1],
                        }
                reports.append({
                    "window":n+1,"event_open_ms":target,
                    "wss_final_count":len(live),"missing_final":missing,
                    "wss_market":stats,"rest_stages":stages,
                    "rest_observation_time_bounds":stage_times,
                    "quarantine_timelines":timelines,"evidence":status,
                })
                if db.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                    raise ValueError("V5_FINALITY_SQLITE_QUICK_CHECK")
                print("G1E_REMEDIATION_WINDOW_RESULT",n+1,
                      "verified",len(status["verified_symbols"]),
                      "quarantined",len(status["quarantined_symbols"]),
                      "BTC_verified",status["btc_verified"],flush=True)
        with sqlite3.connect(filepath) as check:
            copy=FinalityQuarantine(check)
            proof_rows=check.execute("SELECT COUNT(*) FROM v5_wss_final_proof").fetchone()[0]
            stage_rows=check.execute("SELECT COUNT(*) FROM v5_finality_checks").fetchone()[0]
            direction_rows=check.execute("SELECT COUNT(*) FROM v5_directional_evidence").fetchone()[0]
            if check.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("V5_FINALITY_REOPEN_BAD")
            for report in reports:
                verify=copy.evidence_status(symbols,report["event_open_ms"])
                if verify["verified_symbols"]!=report["evidence"]["verified_symbols"]:
                    raise ValueError("V5_FINALITY_RESTART_EVIDENCE_CHANGED")
    passed=all(
        w["wss_final_count"]==len(symbols)
        and len(w["rest_stages"])==3
        and not any(x.get("error") for s in w["rest_stages"] for x in s["issues"])
        and w["evidence"]["evidence_cohort_eligible_for_future_review"]
        for w in reports
    ) and len(reports)==windows
    return {
        "result":"PASS_WITH_QUARANTINE" if passed else "HOLD",
        "symbols":len(symbols),"windows":reports,
        "reopen":{"wss_proofs":proof_rows,"rest_checks":stage_rows,
                  "directional_observations":direction_rows,
                  "temporary_db_removed":not filepath.exists()},
        "peak_rss_mib_approx":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2),
        "research_ready":False,"training_labels_created":0,
        "order_authority":"NONE","persistent_service_started":False,
    }


def main():
    p=argparse.ArgumentParser(description="One-shot finality discrepancy audit; no orders")
    p.add_argument("--top",type=int,default=50)
    p.add_argument("--windows",type=int,default=2)
    p.add_argument("--seconds",type=int,default=338)
    args=p.parse_args()
    try:
        report=asyncio.run(run_probe(top=args.top,windows=args.windows,seconds=args.seconds))
    except Exception as exc:
        print("V5_G1E_REMEDIATION_HOLD",type(exc).__name__,str(exc)[:220],flush=True)
        return 2
    print(json.dumps(report,indent=2,sort_keys=True),flush=True)
    return 0 if report["result"]=="PASS_WITH_QUARANTINE" else 2

if __name__=="__main__":
    raise SystemExit(main())
