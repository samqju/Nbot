#!/usr/bin/env python3
"""Finite NEXT PHASE after complete first eight-family V6 historical batch.

OWNER 2026-10-18: investigate a trader's preference for capturing smaller
+1/+2/+3 percent gross gains, versus a fixed +5% target and current 2%/1%
trailing exit, using 5m historical native Freqtrade trades and conservative
pre-exit OHLCV evidence. This is a SECOND research unit, not a repeating task.

STRICT PREREQUISITES: first finite batch must be COMPLETED, stopped, source
on isolated V6 research branch clean, no Docker, all 24 native and 24 current
trailing official ZIP/aftercost audits valid. No real or paper credentials.
No strategy/model/parameter auto-promotion. NO TRADE remains 0 comparator.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

from m2r_v6_library_native_job import (
    BRANCH, CANDIDATES, OUTPUT, PROFIT_PROTECTION_VARIANTS, ROOT, SOURCE,
    execute,
)
from m2r_v6_library_full_batch import trade_metrics

PERIODS=("validation_july","replication_august","replication_september")
FAMILIES=tuple(CANDIDATES)
FOLLOWUP=OUTPUT/"profit-protection-next-phase"
STATUS=FOLLOWUP/"status.json"
EVENTS=FOLLOWUP/"events.jsonl"
LOCK=FOLLOWUP/"singleton.lock"
ORIGINAL=OUTPUT/"v6-library-research-status.json"

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def save(p,data):
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n")
    os.replace(tmp,p)

def event(stage,name,info,**kw):
    d={"when_utc":now(),"stage":stage,"name":name,"note":info,**kw}
    with EVENTS.open("a") as file:
        file.write(json.dumps(d,sort_keys=True)+"\n")
        file.flush()
        os.fsync(file.fileno())
    print(json.dumps(d,sort_keys=True),flush=True)

def read_existing(kind,family,period):
    path=OUTPUT/kind/family/period/"native-economic-audit.json"
    if not path.is_file():
        raise RuntimeError("PREREQUISITE_NATIVE_AUDIT_MISSING "+str(path))
    obj=json.loads(path.read_text())
    if (obj.get("kind")!=kind or obj.get("family")!=family
        or obj.get("period")!=period or
        obj.get("trade_count_and_native_cost_audit_passed") is not True
        or obj.get("hypothetical_extra_bps_not_observed_spread") is not True
        or not isinstance(obj.get("net_after_extra_25bps_usdt"),(int,float))):
        raise RuntimeError("UNTRUSTED_NATIVE_ECONOMIC_AUDIT "+str(path))
    zipfile_path=OUTPUT/kind/family/period/"backtest_results"/obj["archive_name"]
    if not zipfile_path.is_file():
        raise RuntimeError("ACTUAL_NATIVE_ZIP_NOT_FOUND")
    if hashlib.sha256(zipfile_path.read_bytes()).hexdigest()!=obj["native_zip_sha256"]:
        raise RuntimeError("NATIVE_ZIP_HASH_DIVERGED")
    return obj

def checks():
    if os.geteuid()!=0:
        raise RuntimeError("ROOT_ISOLATED_VPS_REQUIRED")
    if os.environ.get("NBOT_V6_LIBRARY_OFFLINE_EXECUTION")!="OWNER_AUTHORIZED_OFFLINE_RESEARCH_ONLY":
        raise RuntimeError("OFFLINE_RESEARCH_CONSENT_REQUIRED")
    def cmd(a):
        return subprocess.check_output(a,cwd=SOURCE,text=True).strip()
    if cmd(["git","branch","--show-current"])!=BRANCH:
        raise RuntimeError("V6_RESEARCH_BRANCH_REQUIRED")
    if cmd(["git","status","--porcelain=v1"]):
        raise RuntimeError("DIRTY_SOURCE_DO_NOT_RUN")
    if cmd(["docker","ps","-q"]):
        raise RuntimeError("ANOTHER_NATIVE_DOCKER_JOB_ALREADY_RUNNING")
    if not ORIGINAL.exists():
        raise RuntimeError("CURRENT_BATCH_NOT_STARTED")
    status=json.loads(ORIGINAL.read_text())
    if status.get("status")!="complete_with_individual_failures_if_any" or status.get("stage")!="complete":
        raise RuntimeError("CURRENT_BATCH_NOT_SUCCESSFULLY_COMPLETE")
    if not (OUTPUT/"candidate-native-aftercost-summary.json").exists():
        raise RuntimeError("CURRENT_BATCH_FINAL_EVIDENCE_NOT_PRESENT")
    if not (ROOT/"jansep-20261017/jansep-native-four-window-audit.json").exists():
        raise RuntimeError("EARLIER_FOUR_WINDOW_EVIDENCE_NOT_PRESENT")
    for kind in ("native","trailing"):
        for family in FAMILIES:
            for period in PERIODS:
                read_existing(kind,family,period)
    # Exact original 25-coin July/Aug/Sep NoML benchmarks.
    for period in PERIODS:
        read_existing("baseline","ema_cross",period)
    return cmd(["git","rev-parse","HEAD"])

def audit_losing_trades():
    older=ROOT/"jansep-20261017"
    zips=list((older/"w30/backtest_results").glob("*.zip"))
    if len(zips)!=1:
        raise RuntimeError("REQUIRE_ONE_COMPLETE_30D_ORIGINAL_NATIVE_ZIP")
    out=FOLLOWUP/"original-30d-losses-prior-candle-paths.json"
    if out.exists():
        raise RuntimeError("PREVIOUS_LOSS_PATH_AUDIT_EXISTS_DO_NOT_OVERWRITE")
    # Official image has feather/pandas/pyarrow installed; host Python does not.
    command=[
        "timeout","-s","TERM","-k","15","600","docker","run","--rm",
        "--name","nbot-v6-profit-reversal-ohlcv-audit",
        "--network","none","--memory=2g","--cpus=1",
        "--cap-drop","ALL","--security-opt","no-new-privileges",
        "-v",str(SOURCE)+":/research:ro",
        "-v",str(ROOT/"january-2026-public-history-stage")+":/history:ro",
        "-v",str(older)+":/older:ro",
        "-v",str(FOLLOWUP)+":/results",
        "--entrypoint","python","freqtradeorg/freqtrade:stable_freqai",
        "/research/scripts/m2r_v6_profit_reversal_audit.py",
        "--zip","/older/w30/backtest_results/"+zips[0].name,
        "--history","/history/futures",
        "--out","/results/"+out.name,
    ]
    log=FOLLOWUP/"loss-path-analysis.log"
    with log.open("w") as f:
        response=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=False)
    if response.returncode:
        raise RuntimeError(f"ORIGINAL_MFE_READONLY_AUDIT_FAILED_{response.returncode}")
    if not out.is_file():
        raise RuntimeError("LOSS_PATH_EVIDENCE_MISSING")
    rows=json.loads(out.read_text())
    if rows.get("no_counterfactual_profit_or_execution_claim") is not True:
        raise RuntimeError("INVALID_RETRACEMENT_EVIDENCE")
    event("loss_path","original_30d","5m prior-to-exit complete candle analysis",
          loss_trade_counts=rows["counts"])
    return rows

def native_exit_study(commit):
    # 5 newly predefined candidate exits × 8 source-signal families ×
    # 3 already-inspected historical months. May/June tuning must not read
    # July/Aug/Sep. Select highest-scoring variant *only* July+Aug then
    # describe September replication separately; no blind test claim.
    metrics=[]
    state={"schema":"nbot-v6-profit-protection-v1","status":"running",
           "started_utc":now(),"git_commit":commit,
           "no_paper":True,"no_live":True,"no_model_promotion":True,
           "known_july_aug_september_not_pristine_blind":True,
           "stage":"preflight"}
    save(STATUS,state)
    def set_stage(name):
        state["stage"]=name;state["updated_utc"]=now();save(STATUS,state)
        event("stage",name,"FINITE_OWNER_APPROVED_EXIT_RULES_AB_TEST")
    try:
        set_stage("conservative_loss_path_analysis")
        try:
            audit_losing_trades()
        except Exception as e:
            # Missing historical OHLCV diagnostics must not fabricate
            # wins or block genuine independent official native exit trials.
            event("error","original_loss_path",
                  "READONLY_TRAJECTORY_AUDIT_FAILED_NO_CLAIM",error=str(e))
            state["loss_path_diagnostic_failed"]=True;save(STATUS,state)
        set_stage("five_pre_registered_exit_variants")
        for policy in PROFIT_PROTECTION_VARIANTS:
            for family in FAMILIES:
                for period in PERIODS:
                    key=f"{policy}/{family}/{period}"
                    if (OUTPUT/policy/family/period).exists():
                        raise RuntimeError("REFUSE_OVERWRITE_OR_RERUN_"+key)
                    event("start",key,"NATIVE_FREQTRADE_AFTERCOST_EXIT_RULE_AB")
                    code=execute(policy,family,period)
                    if code!=0:
                        raise RuntimeError("OFFLINE_NATIVE_STOP_ON_ERROR_"+key+f"_{code}")
                    metric=trade_metrics(policy,family,period)
                    if metric.get("kind")!=policy:
                        raise RuntimeError("NATIVE_AUDIT_POLICY_MISMATCH")
                    metrics.append(metric)
                    event("complete",key,"25PAIR_NATIVE_ZIP_FEE_FUNDING_25BPS_AUDITED",
                          trades=metric["native_trade_count"],
                          native=metric["native_profit_usdt"],
                          stressed=metric["net_after_extra_25bps_usdt"])
        set_stage("comparison_and_no_trade_gate")
        table=[]
        # Original trial + existing trailing2/1 + five new frozen alternatives
        # all have the same 25 market universe and calendar dates, but trades
        # can change when a different exit frees the one-slot wallet earlier.
        variants=("native","trailing",*PROFIT_PROTECTION_VARIANTS)
        for family in FAMILIES:
            scores={}
            for variant in variants:
                rows=[read_existing(variant,family,p) for p in PERIODS]
                july,aug,sep=rows
                scores[variant]={
                    "july":july,"august":aug,"september":sep,
                    "positive_after_25bp_both_july_and_aug":bool(
                        july["native_trade_count"]>=20 and
                        aug["native_trade_count"]>=20 and
                        july["net_after_extra_25bps_usdt"]>0 and
                        aug["net_after_extra_25bps_usdt"]>0),
                    "min_july_aug_net_after_25bp":min(
                        july["net_after_extra_25bps_usdt"],
                        aug["net_after_extra_25bps_usdt"]),
                }
            qualified=[
                (r["min_july_aug_net_after_25bp"],v)
                for v,r in scores.items()
                if r["positive_after_25bp_both_july_and_aug"]
            ]
            selection=(sorted(qualified,key=lambda x:(-x[0],x[1]))[0][1]
                       if qualified else "NO_TRADE")
            table.append({
                "family":family,
                "chronological_provisional_choice_from_july_and_august":selection,
                "september_economics_of_choice_not_used_for_selection":
                    None if selection=="NO_TRADE" else scores[selection]["september"],
                "all_seven_policy_economics":scores,
                "true_never_inspected_future_market_holdout_not_done":True,
            })
        output={
            "schema":"nbot-v6-fixed-vs-profit-protection-exit-policy-compare-v1",
            "original_study_completed_before_new_study":True,
            "native_25coin_true_trade_archives_per_policy":True,
            "new_exit_variant_native_archive_count":len(metrics),
            "additional_hypothetical_roundtrip_cost_bps":25,
            "no_trade_baseline_usdt":0,
            "single_1000usdt_one_x_global_slot":True,
            "fee_each_side_native":.0005,
            "native_execution_has_5m_intra_candle_path_uncertainty":True,
            "historical_validation_periods_already_previously_inspected":True,
            "no_live_or_paper_promotion":True,
            "selection_is_preliminary_only_not_evidence_of_future_profit":True,
            "comparisons":table
        }
        save(FOLLOWUP/"seven_exit_policies-native-aftercost-comparison.json",output)
        state.update(stage="finished",status="complete_offline_not_release_ready",
                     completed_utc=now(),
                     new_native_archive_count=len(metrics),
                     failed_native_archive_count=0)
        save(STATUS,state)
        event("finished","profit_protection",
              "FINITE_NATIVE_EXIT_AB_COMPLETED_NO_MODEL_PROMOTION",
              new_native_comparisons=len(metrics))
    except BaseException as e:
        state.update(stage="blocked",status="blocked",error=str(e),
                     updated_utc=now())
        save(STATUS,state)
        event("blocked","profit_protection",
              "UNSAFE_OR_INCOMPLETE_NATIVE_RESULT_STOPPED",
              error=str(e),trace=traceback.format_exc()[-500:])
        raise

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--execute",action="store_true")
    ap.add_argument("--status",action="store_true")
    args=ap.parse_args()
    if args.status:
        print(STATUS.read_text() if STATUS.exists() else "NOT_STARTED")
        if EVENTS.exists(): print("".join(EVENTS.read_text().splitlines(True)[-10:]))
        return
    if not args.execute:
        raise RuntimeError("EXPLICIT_EXECUTE_ONLY")
    if STATUS.exists():
        raise RuntimeError("PRIOR_NEXT_PHASE_ALREADY_STARTED_NO_RERUN")
    FOLLOWUP.mkdir(parents=True,exist_ok=True)
    os.chown(FOLLOWUP,1000,1000)
    os.chmod(FOLLOWUP,0o750)
    with LOCK.open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        commit=checks()
        native_exit_study(commit)

if __name__=="__main__":
    main()
