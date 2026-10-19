#!/usr/bin/env python3
"""One-time fail-closed recovery of Stage3 native backtest guard failure.

Four previously completed 30/60/90/180 chronological LightGBM forecasting
jobs are NEVER recalculated. Exact SHA256s and original model-source comparison
are preserved. Moves only the explicitly failed first native folder and
blocked status to archival names, then arms its standard coordinator.

Does NOT submit orders, enable paper/live, or alter economic rank thresholds.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT=Path("/root/nbot-v6-m1-20261016")
OUT=ROOT/"global-25x8-20261018"
SRC=ROOT/"global-next-source"
OLD_COMMIT="8c458c8fda89da86355b5551688ad8cebef5c396"
RESEARCH_ENV="NBOT_V6_GLOBAL_NATIVE_RECOVERY"
RESEARCH_OPTIN="OWNER_AUTHORIZED_OFFLINE_STAGE3_NATIVE_GUARD_RECOVERY"
DATA_FILES=("scripts/m2r_v6_global_dataset.py",
            "scripts/m2r_v6_global_opportunity_ranker.py",
            "user_data/strategies/NbotV6LibraryResearch.py")
WINDOWS=(30,60,90,180)

def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as stream:
        for part in iter(lambda:stream.read(1024*1024),b""):
            h.update(part)
    return h.hexdigest()
def call(args):
    return subprocess.check_output(args,text=True).strip()
def guard(condition,message):
    if not condition:
        raise RuntimeError(message)
def save(path,data):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    os.replace(tmp,path)

def verify_recovery_preconditions():
    guard(os.geteuid()==0 and os.getenv(RESEARCH_ENV)==RESEARCH_OPTIN,
          "REQUIRE_EXPLICIT_OWNER_AUTHORIZED_OFFLINE_GUARD_FIX")
    guard(not call(["docker","ps","-q"]),"ANOTHER_NATIVE_DOCKER_JOB_RUNNING")
    guard(subprocess.run(["systemctl","is-active","--quiet",
                          "nbot-v6-global-20261018.service"],check=False).returncode!=0,
          "GLOBAL_SERVICE_ALREADY_ACTIVE")
    guard(call(["git","-C",str(SRC),"status","--porcelain=v1"])=="",
          "ISOLATED_SOURCE_DIRTY")
    guard(call(["git","-C",str(SRC),"branch","--show-current"])
          =="prototype/v6-freqtrade-freqai-20261016","WRONG_SOURCE_BRANCH")
    # Source code for original labels/scores must be EXACTLY unchanged.
    for p in DATA_FILES:
        proc=subprocess.run(["git","-C",str(SRC),"diff","--quiet",
                             OLD_COMMIT,"HEAD","--",p],check=False)
        guard(proc.returncode==0,"FORECAST_ALGORITHM_CHANGED_REFUSE_REUSE_"+p)
    guard((ROOT/"library-20261018/profit-protection-next-phase/status.json").is_file(),
          "PRIOR_PROFIT_STATUS_MISSING")
    p2=json.loads((ROOT/"library-20261018/profit-protection-next-phase/status.json").read_text())
    guard(p2.get("status")=="complete_offline_not_release_ready"
          and p2.get("new_native_archive_count")==120
          and p2.get("failed_native_archive_count")==0,
          "PRIOR_PROFIT_PROTECTION_NOT_VERIFIED")
    status=OUT/"progress.json"
    guard(status.is_file(),"ORIGINAL_FAILED_STATUS_MISSING")
    old=json.loads(status.read_text())
    guard(old.get("source_commit")==OLD_COMMIT and old.get("status")=="blocked"
          and old.get("jobs_completed")==4 and old.get("jobs_total")==12,
          "NOT_THE_APPROVED_STAGE3_FOUR_FORECAST_FAILURE")
    guard("OFFLINE_DOCKER_JOB_FAILED_2_" in old.get("error","")
          and "/w30/native-fixed/native-backtest.log" in old.get("error",""),
          "UNEXPECTED_FAILED_JOB_REFUSE_RECOVERY")
    guard(not (OUT/"owner-comparison.json").exists(),"GLOBAL_ALREADY_COMPLETED")
    guard(not (OUT/"pre-guard-fix-blocked-progress.json").exists(),
          "THIS_RECOVERY_ALREADY_PERFORMED")
    broken=OUT/"w30/native-fixed"
    guard(broken.is_dir(),"FAILED_FIRST_NATIVE_FOLDER_MISSING")
    guard((broken/"native-backtest.log").is_file()
          and "GLOBAL_V6_NATIVE_BACKTEST_ONLY_NO_ORDERS" in
          (broken/"native-backtest.log").read_text(),
          "ORIGINAL_FAILURE_NOT_GUARD_MISMATCH")
    guard(not list((broken/"backtest_results").glob("*.zip")),
          "FAILED_FIRST_NATIVE_ALREADY_HAS_RESULT_DO_NOT_REPLACE")
    guard(not (OUT/"failed-first-native-pre-guard-fix").exists(),
          "FAILED_NATIVE_ARCHIVE_ALREADY_EXISTS")
    shared=OUT/"shared-candidate-universe"
    info=json.loads((shared/"immutable-candidate-cache-audit.json").read_text())
    parq=shared/"all-valid-opportunities-and-research-labels.parquet"
    guard(digest(parq)==info.get("sha256"),"ORIGINAL_CANDIDATE_CACHE_HASH_MISMATCH")
    complete={}
    for days in WINDOWS:
        base=OUT/f"w{days}"
        paths={key:base/name for key,name in {
          "decisions":"global_decisions.csv",
          "audit":"training-and-calibration-audit.json",
          "forecast_rejections":"asof-forecasts-and-rejections.parquet",
          "cache_reference":"shared-candidate-universe-reference.json"}.items()}
        guard(all(f.is_file() for f in paths.values()),
              "FORECAST_SNAPSHOT_INCOMPLETE_"+str(days))
        model=json.loads(paths["audit"].read_text())
        guard(model.get("window_days")==days and model.get("decisions")==0
              and model.get("scored_valid_candidates",0)>0
              and model.get("no_paper_or_live") is True,
              "FORECAST_COMPLETION_NOT_PROVEN_"+str(days))
        guard((base/"global_decisions.csv").read_text().count("\n")==1,
              "UNEXPECTED_NONEMPTY_OR_BAD_DECISION_CSV_"+str(days))
        guard(not (base/"native-trailing").exists(),
              "TRAILING_ALREADY_STARTED_REQUIRE_MANUAL_REVIEW")
        complete[str(days)]={name:digest(file) for name,file in paths.items()}
    guard(not list(OUT.glob("w*/native-*/native-audit.json")),
          "NATIVE_ECONOMICS_ALREADY_PRESENT_DO_NOT_REPEAT")
    return old,info,complete,broken,status

def main():
    if len(sys.argv)!=2 or sys.argv[1] not in ("--check","--execute"):
        raise RuntimeError("EXPLICIT_EXECUTE_OR_PREFLIGHT_CHECK_REQUIRED")
    old,info,completed,broken,status=verify_recovery_preconditions()
    new_sha=call(["git","-C",str(SRC),"rev-parse","HEAD"])
    if sys.argv[1]=="--check":
        print(json.dumps({"verified":True,"read_only":True,"source_sha":new_sha,
                          "original_forecast_commit":OLD_COMMIT,
                          "four_forecasts_hash_verified":len(completed),
                          "reusable_existing_jobs":old["jobs_completed"],
                          "failed_native_archivable":True,"no_trades_or_threshold_changes":True},sort_keys=True))
        return
    record={
      "schema":"nbot-v6-stage3-native-guard-fix-recovery-v1",
      "when_utc":utc(),
      "original_source_commit":OLD_COMMIT,
      "resume_source_commit":new_sha,
      "original_status":old,
      "shared_dataset_sha256":info["sha256"],
      "four_window_file_sha256":completed,
      "original_forecast_code_unchanged":True,
      "regenerated_forecasts":False,
      "native_recovery_reason":"exact original guard rejected normalized offline Freqtrade config",
      "stage1_stage2_evidence_preserved":True,
      "no_policy_change_or_auto_promotion":True,
      "paper_live_disabled":True}
    oldprogress=OUT/"pre-guard-fix-blocked-progress.json"
    os.replace(status,oldprogress)
    os.replace(broken,OUT/"failed-first-native-pre-guard-fix")
    record["original_progress_archived_sha256"]=digest(oldprogress)
    save(OUT/"native-guard-fix-recovery-manifest.json",record)
    resumed={
      "schema":"nbot-v6-global-25x8-progress-1",
      "status":"resuming_verified_forecasts",
      "stage":"native_30_fixed",
      "started":old["started"],
      "source_commit":new_sha,
      "original_forecast_source_commit":OLD_COMMIT,
      "jobs_total":12,
      "jobs_completed":4,
      "jobs_failed":0,
      "native_failure_archived":True,
      "reused_forecasts_with_verified_sha256":True,
      "no_change_to_selection_policy":True,
      "trading_allowed":False,
      "owner_review_before_promotion":True,
      "recovery_manifest":"native-guard-fix-recovery-manifest.json",
      "last_heartbeat":utc()}
    save(status,resumed)
    print("FOUR_FORECASTS_RETAINED_VERIFIED_NEW_NATIVE_ONLY")
    print(json.dumps({"original_commit":OLD_COMMIT,"resumed_commit":new_sha,
                      "forecast_windows":list(completed),"jobs_completed":4,
                      "no_trades_selected_in_forecast":True,
                      "all_failed_evidence_archived":True},sort_keys=True))

if __name__=="__main__":
    main()
