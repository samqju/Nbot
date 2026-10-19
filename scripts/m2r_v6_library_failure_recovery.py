#!/usr/bin/env python3
"""Finite fail-closed recovery of ONLY the seven interrupted V6 library jobs.

Preserves every successful historical/native/trailing archive and the aborted
4-hour stochastic attempt. Uses original pinned source for reproducibility.
On complete verification it rearms stage2 and stage3 systemd handoffs, but
NEVER enables paper/live trading or promotes any candidate.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys

ROOT=Path("/root/nbot-v6-m1-20261016")
SOURCE=ROOT/"source"
PREV=ROOT/"library-20261018"
OUT=ROOT/"library-20261018-recovery"
GIT_SHA="aa97a32c9af73ae63503f5dbff63d98a7fe32200"
BRANCH="prototype/v6-freqtrade-freqai-20261016"
OPTIN="NBOT_V6_LIBRARY_OFFLINE_EXECUTION"
OPTINVAL="OWNER_AUTHORIZED_OFFLINE_RESEARCH_ONLY"
JOBS=(
    ("hyperopt","stochastic_reversal","tuning_may_june"),
    ("hyperopt","atr_breakout","tuning_may_june"),
    ("hyperopt","volume_trend","tuning_may_june"),
    ("lgbm","ema_cross","replication_september"),
    ("lgbm","volume_trend","replication_september"),
    ("adaptive","ema_cross","replication_september"),
    ("rl","ema_cross","validation_july"),
)
NEXT="nbot-v6-profit-protection-next-20261018.service"
GLOBAL="nbot-v6-global-20261018.service"

sys.path.insert(0,str(SOURCE/"scripts"))
import m2r_v6_library_native_job as native
import m2r_v6_library_full_batch as full

def now():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def process(args,**kwargs):return subprocess.run(args,check=False,text=True,**kwargs)
def check(args):return subprocess.check_output(args,text=True).strip()
def save(path,body):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(body,sort_keys=True,indent=2)+"\n")
    os.replace(tmp,path)
def log(event,name,**kwargs):
    datum={"when_utc":now(),"event":event,"name":name,**kwargs}
    with (OUT/"recovery-events.jsonl").open("a") as f:
        f.write(json.dumps(datum,sort_keys=True)+"\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(datum,sort_keys=True),flush=True)
def name_for(job):return "/".join(job)
def folder_for(job):return OUT.joinpath(*job)

def successful(job):
    path=folder_for(job)
    state=path/"run-state.txt"
    if not state.is_file() or "EXIT_CODE=0" not in state.read_text().splitlines():
        return False
    if job[0]=="hyperopt":
        m=path/"research-audit.json"
        j=json.loads(m.read_text()) if m.exists() else {}
        return j.get("completed_native_hyperopt") is True and bool(
            list((path/"hyperopt_results").glob("*.fthypt")))
    p=path/"native-economic-audit.json"
    if not p.is_file():return False
    audit=json.loads(p.read_text())
    zipfile=path/"backtest_results"/audit.get("archive_name","")
    if not zipfile.is_file():return False
    with zipfile.open("rb") as f:
        digest=hashlib.file_digest(f,"sha256").hexdigest()
    return (audit.get("trade_count_and_native_cost_audit_passed") is True
            and audit.get("native_zip_sha256")==digest
            and audit.get("family")==job[1] and audit.get("period")==job[2]
            and audit.get("kind")==job[0])

def preflight():
    if os.geteuid()!=0 or os.environ.get(OPTIN)!=OPTINVAL:
        raise RuntimeError("OWNER_AUTHORIZED_OFFLINE_ROOT_CONSENT_REQUIRED")
    if check(["git","-C",str(SOURCE),"rev-parse","HEAD"])!=GIT_SHA:
        raise RuntimeError("PRESERVE_ORIGINAL_FIXED_LIBRARY_SOURCE_COMMIT")
    if check(["git","-C",str(SOURCE),"branch","--show-current"])!=BRANCH:
        raise RuntimeError("V6_RESEARCH_BRANCH_REQUIRED")
    if check(["git","-C",str(SOURCE),"status","--porcelain=v1"]):
        raise RuntimeError("ORIGINAL_RESEARCH_SOURCE_DIRTY")
    if check(["docker","ps","-q"]):
        raise RuntimeError("DOCKER_BUSY_DO_NOT_COMPETE")
    for unit in ("nbot-v6-library-20261018.service",NEXT,GLOBAL):
        if process(["systemctl","is-active","--quiet",unit]).returncode==0:
            raise RuntimeError("PREDECESSOR_OR_SUCCESSOR_ALREADY_ACTIVE_"+unit)
    p=json.loads((PREV/"v6-library-research-status.json").read_text())
    if p.get("status")!="complete_with_individual_failures_if_any" or p.get("stage")!="complete":
        raise RuntimeError("ORIGINAL_LIBRARY_NOT_TERMINATED")
    summary=json.loads((PREV/"candidate-native-aftercost-summary.json").read_text())
    if (len(summary.get("frozen_native_results",[]))!=24 or
        len(summary.get("trailing_stops_ab_results",[]))!=24 or
        len(summary.get("original_breakout_pullback_no_ml_baselines",[]))!=3):
        raise RuntimeError("ORIGINAL_NATIVE_RESULTS_NOT_COMPLETE_DO_NOT_REPEAT")
    if (PREV/"profit-protection-next-phase/status.json").exists():
        raise RuntimeError("FOLLOWUP_ALREADY_STARTED_NO_REARM")
    if (ROOT/"global-25x8-20261018/progress.json").exists():
        raise RuntimeError("GLOBAL_ALREADY_STARTED_NO_REARM")
    if not (ROOT/"jansep-20261017/jansep-native-four-window-audit.json").exists():
        raise RuntimeError("ORIGINAL_HISTORICAL_4_WINDOW_AUDIT_MISSING")
    for job in JOBS:
        _=native._safe_overrides(job[0],job[1])
    return True

def execute(job):
    kind,family,period=job
    key=name_for(job)
    path=folder_for(job)
    if successful(job):
        log("resume",key,detail="VALIDATED_COMPLETED_RECOVERY_EVIDENCE_REUSED")
        return
    if path.exists():
        raise RuntimeError("PARTIAL_RECOVERY_OUTPUT_REQUIRES_REVIEW_"+str(path))
    if check(["docker","ps","-q"]):
        raise RuntimeError("DOCKER_ACTIVE_BEFORE_RECOVERY_JOB")
    path.mkdir(parents=True)
    os.chown(path,1000,1000)
    os.chmod(path,0o750)
    override=native._safe_overrides(kind,family)
    cfg=path/"exact-overlay.json"
    cfg.write_text(json.dumps(override,indent=2)+"\n")
    os.chmod(cfg,0o644)
    st=path/"run-state.txt"
    st.write_text(
        f"START_UTC={now()}\nGIT_COMMIT={GIT_SHA}\n"
        f"RESEARCH_KIND={kind}\nFAMILY={family}\nPERIOD={period}\n")
    command=native.plan(kind,family,period)
    old="/root/nbot-v6-m1-20261016/library-20261018/"+key
    new=str(path)
    command=[x.replace(old,new) for x in command]
    if command.count("14400")!=1:
        raise RuntimeError("UNEXPECTED_NATIVE_TIMEOUT_CLI")
    command[command.index("14400")]="36000"  # bound single job at 10h, not 4h
    if new not in " ".join(command) or old in " ".join(command):
        raise RuntimeError("DOCKER_OUTPUT_NOT_ISOLATED")
    if check(["docker","ps","-q"]):
        raise RuntimeError("DOCKER_BECAME_BUSY_RACE")
    log("start",key,timeout_seconds=36000,original_source_sha=GIT_SHA)
    with (path/"native.log").open("w") as out:
        code=process(command,stdout=out,stderr=subprocess.STDOUT).returncode
    with st.open("a") as state:
        state.write(f"EXIT_CODE={code}\nFINISH_UTC={now()}\n")
    if code!=0:
        raise RuntimeError(f"RECOVERY_NATIVE_FAILED_{key}_EXIT_{code}")
    if kind=="hyperopt":
        completed=list((path/"hyperopt_results").glob("*.fthypt"))
        if not completed:
            raise RuntimeError("HYPEROPT_RESULT_MISSING_"+key)
        save(path/"research-audit.json",{
            "kind":kind,"family":family,"period":period,
            "completed_native_hyperopt":True,
            "safe_optima_export_disabled":True,
            "independent_holdout_validation_not_done":True,
            "hyperopt_archive_count":len(completed)})
    else:
        # Identical native ZIP/fee/funding/one-slot reconciliation to stage 1.
        full.OUTPUT=OUT
        a=full.trade_metrics(kind,family,period)
        if a["kind"]!=kind or a["trade_count_and_native_cost_audit_passed"] is not True:
            raise RuntimeError("NATIVE_AUDIT_FAIL_"+key)
    if not successful(job):
        raise RuntimeError("POST_EXEC_RECOVERY_EVIDENCE_FAIL_"+key)
    log("complete",key)

def rearm():
    if not all(successful(j) for j in JOBS):
        raise RuntimeError("REFUSE_SUCCESSOR_WITHOUT_ALL_7_VALIDATED")
    # Existing two future services only; no new bot or trading service.
    # Persistent profit service unit is installed by owner-authorized deploy.
    if check(["docker","ps","-q"]):
        raise RuntimeError("DOCKER_NOT_IDLE_AT_HANDOFF")
    log("verified","first_research_recovery",
        recovered_jobs=len(JOBS),original_56_successes_preserved=True)
    save(OUT/"verified-all-seven-and-original-56.json",{
        "verified_utc":now(),"original_source_sha":GIT_SHA,
        "recovered_jobs":[name_for(j) for j in JOBS],
        "all_recovered_native_audits_passed":True,
        "preserved_original_56_jobs":True,
        "handoff_authorized_for_offline_research_only":True,
        "paper":False,"live":False,"models_promoted":False})
    for unit in (NEXT,GLOBAL):
        process(["systemctl","reset-failed",unit])
    # Start stage 2 waiter. Stage 3 will observe stage2 ACTIVE and remain waiting.
    a=process(["systemctl","start",NEXT])
    if a.returncode:raise RuntimeError("PROFIT_PROTECTION_REARM_FAILED")
    b=process(["systemctl","start",GLOBAL])
    if b.returncode:raise RuntimeError("GLOBAL_SELECTOR_REARM_FAILED")
    log("rearmed","two_followup_services",profit=NEXT,global_research=GLOBAL)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--status",action="store_true")
    ap.add_argument("--execute",action="store_true")
    a=ap.parse_args()
    if a.status:
        print(json.dumps({
            "recovery_jobs_total":len(JOBS),
            "recovery_jobs_completed":sum(successful(j) for j in JOBS),
            "jobs":[{"job":name_for(j),"completed":successful(j)}
                    for j in JOBS],
            "read_only":True},indent=2))
        return
    if not a.execute:raise RuntimeError("EXPLICIT_EXECUTE_OR_STATUS_REQUIRED")
    preflight()
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"recovery.lock").open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        statefile=OUT/"recovery-progress.json"
        state={"schema":"v6-library-recovery-20261018-v1",
               "source_sha":GIT_SHA,"status":"running",
               "started_utc":now(),"total":len(JOBS),"completed":0,
               "failed":0,"no_paper":True,"no_live":True,"no_auto_promotion":True}
        if statefile.exists():
            prev=json.loads(statefile.read_text())
            if prev["source_sha"]!=GIT_SHA or prev["status"]=="finished":
                raise RuntimeError("RECOVERY_RESTART_NOT_ALLOWED")
            state=prev
        else:save(statefile,state)
        try:
            for job in JOBS:
                execute(job)
                state.update(current=name_for(job),
                             completed=sum(successful(j) for j in JOBS),
                             updated_utc=now())
                save(statefile,state)
            rearm()
            state.update(status="finished",completed=len(JOBS),finished_utc=now())
            save(statefile,state)
        except BaseException as ex:
            state.update(status="blocked",failed=state["failed"]+1,
                         updated_utc=now(),error=str(ex))
            save(statefile,state)
            log("blocked","recovery",error=str(ex))
            raise

if __name__=="__main__":main()
