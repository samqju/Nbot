#!/usr/bin/env python3
"""Finite, restartable OFFLINE ONLY global 25x8 native research coordinator.

Never begins while existing finite library or profit-protection work is active,
failed or incomplete. Uses only an isolated source checkout, immutable original
history mounts, no exchange keys, no persistent bot and no paper/live orders.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
from pathlib import Path
import json
import os
import subprocess
import sys
import fcntl
import hashlib
from zipfile import ZipFile

ROOT=Path("/root/nbot-v6-m1-20261016")
SOURCE=ROOT/"global-next-source"
HISTORY=ROOT/"january-2026-public-history-stage"
PREV=ROOT/"library-20261018"
OUTPUT=ROOT/"global-25x8-20261018"
BRANCH="prototype/v6-freqtrade-freqai-20261016"
WINDOWS=(30,60,90,180)
PROFILES=("fixed","trailing")
STAGES=4+4*2
STATUS=OUTPUT/"progress.json"
EVENTS=OUTPUT/"events.jsonl"
ENV="NBOT_V6_GLOBAL_RESEARCH"
OFFLINE="OWNER_AUTHORIZED_OFFLINE_GLOBAL_V6_RESEARCH_ONLY"
IMAGE="freqtradeorg/freqtrade:stable_freqai"

def now():return datetime.now(timezone.utc).isoformat(timespec="seconds")

def cmd(args,**kw):
    return subprocess.check_output(args,text=True,**kw).strip()

def atomic_json(path,obj):
    t=path.with_suffix(path.suffix+".tmp")
    t.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
    t.replace(path)

def append_event(type_,name,**fields):
    d={"time":now(),"event":type_,"name":name,**fields}
    with EVENTS.open("a") as f:
        f.write(json.dumps(d,sort_keys=True)+"\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(d,sort_keys=True),flush=True)

def ensure_prerequisites():
    if os.geteuid()!=0 or os.environ.get(ENV)!=OFFLINE:
        raise RuntimeError("EXPLICIT_ISOLATED_OFFLINE_ROOT_CONSENT_REQUIRED")
    if subprocess.run(["systemctl","is-active","--quiet","nbot-v6-library-20261018.service"],check=False).returncode==0:
        raise RuntimeError("ORIGINAL_LIBRARY_STILL_RUNNING")
    # profit protector must *complete*, not merely stop/timeout.
    if subprocess.run(["systemctl","is-active","--quiet","nbot-v6-profit-protection-next-20261018.service"],check=False).returncode==0:
        raise RuntimeError("PROFIT_PROTECTION_STILL_RUNNING")
    if cmd(["docker","ps","-q"]):
        raise RuntimeError("OTHER_DOCKER_ACTIVITY_PROHIBITED")
    original=json.loads((PREV/"v6-library-research-status.json").read_text())
    if (original.get("status")!="complete_with_individual_failures_if_any"
        or original.get("stage")!="complete"
        or not (PREV/"candidate-native-aftercost-summary.json").is_file()):
        raise RuntimeError("LIBRARY_FINAL_EVIDENCE_NOT_COMPLETE")
    prior=json.loads((PREV/"profit-protection-next-phase/status.json").read_text())
    if (prior.get("status")!="complete_offline_not_release_ready"
        or prior.get("new_native_archive_count")!=120
        or prior.get("failed_native_archive_count")!=0
        or not (PREV/"profit-protection-next-phase/seven_exit_policies-native-aftercost-comparison.json").is_file()):
        raise RuntimeError("PROFIT_PROTECTION_120_ARCHIVES_NOT_VERIFIED")
    if not (ROOT/"jansep-20261017/jansep-native-four-window-audit.json").is_file():
        raise RuntimeError("HISTORICAL_BASELINE_AUDIT_MISSING")
    if not SOURCE.is_dir() or cmd(["git","-C",str(SOURCE),"branch","--show-current"])!=BRANCH:
        raise RuntimeError("ISOLATED_GLOBAL_GIT_CHECKOUT_REQUIRED")
    if cmd(["git","-C",str(SOURCE),"status","--porcelain=v1"]):
        raise RuntimeError("ISOLATED_GIT_CHECKOUT_DIRTY")
    for p in ("scripts/m2r_v6_global_dataset.py",
              "user_data/strategies/NbotV6GlobalOfflineResearch.py",
              "scripts/m2r_v6_global_batch.py",
              "scripts/m2r_v6_global_opportunity_ranker.py"):
        if not (SOURCE/p).is_file():raise RuntimeError("GLOBAL_CODE_MISSING_"+p)
    config=json.loads((SOURCE/"user_data/config.json").read_text())
    if len(set(config["exchange"]["pair_whitelist"]))!=25:
        raise RuntimeError("WRONG_PAIR_UNIVERSE")
    if config["exchange"].get("key") or config["exchange"].get("secret"):
        raise RuntimeError("EXCHANGE_CREDENTIALS_PROHIBITED")
    return cmd(["git","-C",str(SOURCE),"rev-parse","HEAD"])

def docker_run(args, logfile, timeout=14400):
    with logfile.open("w") as f:
        try:
            network="bridge" if len(args)>1 and args[1]=="freqtrade" else "none"
            p=subprocess.run(["timeout","-s","TERM","-k","60",str(timeout),
                              "docker","run","--rm","--network",network,
                              "--memory","6g","--cpus","2",
                              "--cap-drop","ALL","--security-opt","no-new-privileges",
                              "-v",str(SOURCE)+":/research:ro",
                              "-v",str(HISTORY)+":/history:ro",
                              "-v",str(OUTPUT)+":/results",
                              *args],
                             stdout=f,stderr=subprocess.STDOUT,check=False)
        except BaseException:
            append_event("error","docker_invocation",log=str(logfile))
            raise
    if p.returncode:
        raise RuntimeError(f"OFFLINE_DOCKER_JOB_FAILED_{p.returncode}_{logfile}")
    return p.returncode

def data_job(days):
    folder=OUTPUT/f"w{days}"
    marker=folder/"training-and-calibration-audit.json"
    csv=folder/"global_decisions.csv"
    if marker.is_file() and csv.is_file():
        append_event("resume",f"model_{days}",detail="existing_audit_and_decisions")
        return
    if folder.exists():
        raise RuntimeError("PARTIAL_FORECAST_RESULT_MANUAL_AUDIT_REQUIRED_"+str(folder))
    # Docker mounts output root writable as non-root image user.
    append_event("start",f"model_{days}")
    docker_run(["--entrypoint","python",IMAGE,
        "/research/scripts/m2r_v6_global_dataset.py",
        "--history","/history/futures",
        "--config","/research/user_data/config.json",
        "--out",f"/results/w{days}","--lookback",str(days)],
        OUTPUT/f"model_{days}.log",timeout=14400)
    if not marker.is_file() or not csv.is_file():
        raise RuntimeError("MISSING_VERIFIED_OFFLINE_MODEL_RESULT")
    info=json.loads(marker.read_text())
    if info.get("window_days")!=days or info.get("no_paper_or_live") is not True:
        raise RuntimeError("BAD_GLOBAL_MODEL_AUDIT")
    append_event("complete",f"model_{days}",decisions=info["decisions"])

def native_audit(folder,policy,days):
    zips=list((folder/"backtest_results").glob("*.zip"))
    if len(zips)!=1:raise RuntimeError("REQUIRE_EXACT_NATIVE_ZIP")
    blob=zips[0].read_bytes()
    with ZipFile(zips[0]) as z:
        if z.testzip() is not None:raise RuntimeError("CORRUPT_NATIVE_ARCHIVE")
        names=[n for n in z.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        if len(names)!=1:raise RuntimeError("AMBIGUOUS_NATIVE_ARCHIVE")
        data=json.loads(z.read(names[0]))
    strategies=data.get("strategy",{})
    if len(strategies)!=1:raise RuntimeError("REQUIRE_ONE_NATIVE_STRATEGY")
    name,info=next(iter(strategies.items()))
    expected=("NbotV6GlobalOfflineResearch" if policy=="fixed"
              else "NbotV6GlobalTrailingOfflineResearch")
    if name!=expected:raise RuntimeError("UNEXPECTED_NATIVE_STRATEGY")
    if (info.get("trading_mode")!="futures" or info.get("max_open_trades")!=1
        or len(info.get("pairlist",[]))!=25
        or abs(float(info.get("stake_amount",0))-1000)>.000001
        or abs(float(info.get("starting_balance",0))-100000)>.000001):
        raise RuntimeError("NATIVE_CAPITAL_OR_PAIR_MISMATCH")
    trades=info.get("trades",[])
    if len(trades)!=info.get("total_trades"):raise RuntimeError("TRADE_COUNT_MISMATCH")
    pnl=float(info.get("profit_total_abs",0))
    if abs(sum(float(t["profit_abs"]) for t in trades)-pnl)>.002:
        raise RuntimeError("LEDGER_DOES_NOT_RECONCILE")
    for t in trades:
        if abs(float(t["leverage"])-1)>1e-8:raise RuntimeError("LEVERAGE_MISMATCH")
        if abs(float(t["fee_open"])-.0005)>1e-8 or abs(float(t["fee_close"])-.0005)>1e-8:
            raise RuntimeError("NATIVE_FEE_MISMATCH")
        if not str(t.get("enter_tag","")).startswith("global_"):
            raise RuntimeError("UNFORECASTED_NATIVE_ENTRY")
        if t["pair"] not in info["pairlist"]:raise RuntimeError("WRONG_TRADE_PAIR")
    stress=pnl-.0025*sum(float(t["stake_amount"]) for t in trades)
    audit={"schema":"nbot-global-native-portfolio-1","days":days,"exit_policy":policy,
           "strategy":name,"trades":len(trades),"native_net_usdt":round(pnl,6),
           "additional_25bp_stressed_net_usdt":round(stress,6),
           "no_trade_usdt":0,"native_zip_sha256":hashlib.sha256(blob).hexdigest(),
           "funding_and_fee_execution_in_native_engine":True,
           "execution_stress_is_hypothetical_not_observed_spread":True,
           "one_global_slot":True,"no_paper_or_live":True}
    atomic_json(folder/"native-audit.json",audit)
    return audit

def native_job(days,policy):
    folder=OUTPUT/f"w{days}"/f"native-{policy}"
    auditfile=folder/"native-audit.json"
    if auditfile.is_file():
        a=json.loads(auditfile.read_text())
        if a["days"]!=days or a["exit_policy"]!=policy:raise RuntimeError("INVALID_RESUME_AUDIT")
        if len(list((folder/"backtest_results").glob("*.zip")))!=1:
            raise RuntimeError("MISSING_RESUME_ARCHIVE")
        append_event("resume",f"native_{days}_{policy}")
        return a
    if folder.exists():raise RuntimeError("PARTIAL_NATIVE_RESULT_MANUAL_AUDIT_REQUIRED")
    folder.mkdir(parents=True)
    os.chown(folder,1000,1000)
    options={"freqai":{"enabled":False},
       "nbot_v6_global_research_only":True,"nbot_live_mode":False,
       "nbot_paper_research_mode":False,
       "nbot_v6_global_decisions_csv":f"/results/w{days}/global_decisions.csv",
       "dry_run":True,"max_open_trades":1,"stake_amount":1000,
       "dry_run_wallet":100000,"force_entry_enable":False,
       "exchange":{"name":"binance","key":"","secret":""},
       "api_server":{"enabled":False},"telegram":{"enabled":False}}
    atomic_json(folder/"exact-overlay.json",options)
    # Freqtrade may need the output folder writable for ZIP export.
    os.chown(folder,1000,1000)
    model=("NbotV6GlobalOfflineResearch" if policy=="fixed"
           else "NbotV6GlobalTrailingOfflineResearch")
    append_event("start",f"native_{days}_{policy}")
    docker_run(["--entrypoint","freqtrade",IMAGE,
        "backtesting","-c","/research/user_data/config.json",
        "-c",f"/results/w{days}/native-{policy}/exact-overlay.json",
        "--userdir",f"/results/w{days}/native-{policy}",
        "--datadir","/history",
        "--strategy",model,"--strategy-path","/research/user_data/strategies",
        "--timerange","20260715-20261001","--fee","0.0005",
        "--cache","none","--export","trades","--enable-protections"],
        folder/"native-backtest.log",timeout=14400)
    a=native_audit(folder,policy,days)
    append_event("complete",f"native_{days}_{policy}",
                 trades=a["trades"],net=a["native_net_usdt"],stress=a["additional_25bp_stressed_net_usdt"])
    return a

def audited_completed_count():
    total=0
    for days in WINDOWS:
        base=OUTPUT/f"w{days}"
        if (base/"training-and-calibration-audit.json").is_file() and (base/"global_decisions.csv").is_file():
            total+=1
        for policy in PROFILES:
            p=base/f"native-{policy}"
            if (p/"native-audit.json").is_file() and len(list((p/"backtest_results").glob("*.zip")))==1:
                total+=1
    return total

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--execute",action="store_true")
    p.add_argument("--status",action="store_true")
    args=p.parse_args()
    if args.status:
        print(STATUS.read_text() if STATUS.exists() else "NOT_STARTED")
        if EVENTS.exists():print("".join(EVENTS.read_text().splitlines(True)[-10:]))
        return
    if not args.execute:raise RuntimeError("EXPLICIT_EXECUTE_REQUIRED")
    # Do not modify existing work when critical prerequisites fail.
    head=ensure_prerequisites()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    os.chown(OUTPUT,1000,1000)
    with (OUTPUT/"singleton.lock").open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state={"schema":"nbot-v6-global-25x8-progress-1","status":"running",
               "stage":"forecast","started":now(),"source_commit":head,
               "jobs_total":STAGES,"jobs_completed":0,"jobs_failed":0,
               "trading_allowed":False,"owner_review_before_promotion":True}
        if STATUS.exists():
            prior=json.loads(STATUS.read_text())
            if prior.get("source_commit")!=head:raise RuntimeError("RESUME_COMMIT_CHANGED")
            if prior.get("status")=="complete":raise RuntimeError("ALREADY_COMPLETE")
            state=prior
        else:atomic_json(STATUS,state)
        try:
            for days in WINDOWS:
                data_job(days)
                state.update(stage=f"forecast_{days}",
                             jobs_completed=audited_completed_count(),last_heartbeat=now())
                atomic_json(STATUS,state)
            reports=[]
            for days in WINDOWS:
                for profile in PROFILES:
                    reports.append(native_job(days,profile))
                    state.update(stage=f"native_{days}_{profile}",
                                 jobs_completed=state["jobs_completed"]+1,last_heartbeat=now())
                    atomic_json(STATUS,state)
            atomic_json(OUTPUT/"owner-comparison.json",{
                "schema":"v6-global-eight-research-outcome",
                "audited_native_portfolios":reports,
                "no_trade_baseline_usdt":0,
                "not_an_unseen_market_holdout":True,
                "no_strategy_automatically_approved":True})
            state.update(stage="finished",status="complete_research_only",
                         completed=now(),jobs_completed=STAGES)
            atomic_json(STATUS,state)
            append_event("complete","global_batch",jobs=STAGES)
        except BaseException as e:
            state.update(status="blocked",jobs_failed=state.get("jobs_failed",0)+1,
                         error=str(e),last_heartbeat=now())
            atomic_json(STATUS,state)
            append_event("blocked","global_batch",error=str(e))
            raise

if __name__=="__main__":main()
