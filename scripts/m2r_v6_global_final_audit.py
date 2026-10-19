#!/usr/bin/env python3
"""Read-only independent check of four reused forecasts + eight native ZIPs.

No training, native simulation, writes, service operations, or trading.
"""
from __future__ import annotations
from pathlib import Path
import json
import hashlib
import sys

ROOT=Path("/root/nbot-v6-m1-20261016")
OUT=ROOT/"global-25x8-20261018"
WINDOWS=(30,60,90,180)
POLICIES=("fixed","trailing")

def sha(p):
    digest=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            digest.update(b)
    return digest.hexdigest()
def require(x,msg):
    if not x:raise RuntimeError(msg)
def read(p):return json.loads(p.read_text())

def verify():
    status=read(OUT/"progress.json")
    require(status.get("status")=="complete_research_only"
            and status.get("jobs_completed")==12
            and status.get("jobs_failed")==0,
            "STAGE3_NOT_COMPLETED_CLEANLY")
    origin=read(OUT/"pre-guard-fix-blocked-progress.json")
    manifest=read(OUT/"native-guard-fix-recovery-manifest.json")
    require(sha(OUT/"pre-guard-fix-blocked-progress.json")
            ==manifest.get("original_progress_archived_sha256"),
            "ORIGINAL_FAILURE_STATUS_MUTATED")
    require(origin.get("status")=="blocked" and origin.get("jobs_completed")==4
            and manifest.get("original_source_commit")==origin.get("source_commit"),
            "REPAIR_PROVENANCE_INCONSISTENT")
    require(status.get("source_commit")==manifest.get("resume_source_commit"),
            "REPAIRED_SOURCE_COMMIT_MISMATCH")
    require(status.get("original_forecast_source_commit")==origin.get("source_commit"),
            "FORECAST_ORIGIN_NOT_PRESERVED")
    cache=read(OUT/"shared-candidate-universe/immutable-candidate-cache-audit.json")
    require(sha(OUT/"shared-candidate-universe/all-valid-opportunities-and-research-labels.parquet")
            ==cache.get("sha256")==manifest.get("shared_dataset_sha256"),
            "SAVED_CANDIDATE_CACHE_MUTATED")
    models=[];native=[]
    for w in WINDOWS:
        m=OUT/f"w{w}"
        info=read(m/"training-and-calibration-audit.json")
        require(info.get("window_days")==w and info.get("no_paper_or_live") is True,
                "BAD_MODEL_AUDIT")
        require(info.get("scored_valid_candidates",0)>0
                and info.get("decisions")==0,"UNEXPECTED_FORECAST_DECISIONS")
        original=manifest["four_window_file_sha256"][str(w)]
        rel={"audit":"training-and-calibration-audit.json",
             "decisions":"global_decisions.csv",
             "forecast_rejections":"asof-forecasts-and-rejections.parquet",
             "cache_reference":"shared-candidate-universe-reference.json"}
        for name,filename in rel.items():
            require(sha(m/filename)==original[name],
                    "FORECAST_ARTIFACT_CHANGED_"+str(w)+"_"+name)
        models.append({"window_days":w,"candidate_forecasts":info["scored_valid_candidates"],
                       "selected_opportunities":info["decisions"]})
        for policy in POLICIES:
            n=m/f"native-{policy}"
            a=read(n/"native-audit.json")
            z=list((n/"backtest_results").glob("*.zip"))
            require(len(z)==1 and sha(z[0])==a.get("native_zip_sha256"),
                    "NATIVE_ZIP_HASH_MISMATCH_"+str(w)+"_"+policy)
            require(a["days"]==w and a["exit_policy"]==policy
                    and a["trades"]==0
                    and a["native_net_usdt"]==0
                    and a["additional_25bp_stressed_net_usdt"]==0
                    and a["no_paper_or_live"] is True,
                    "NATIVE_PORTFOLIO_ECONOMICS_UNEXPECTED_"+str(w)+"_"+policy)
            native.append({"window_days":w,"policy":policy,
                           "native_trades":a["trades"],
                           "native_net_usdt":a["native_net_usdt"],
                           "native_zip_sha256":a["native_zip_sha256"]})
    owner=read(OUT/"owner-comparison.json")
    require(len(owner["audited_native_portfolios"])==8
            and owner["no_strategy_automatically_approved"] is True,
            "OWNER_COMPARISON_MISSING")
    return {
        "schema":"v6-stage3-final-independent-audit-1",
        "state":"all_twelve_jobs_completed_hash_verified",
        "models":models,"native_portfolios":native,
        "all_forecast_sha256s_preserved":True,
        "eight_native_zip_sha256s_verified":True,
        "total_candidate_snapshots":cache["rows"],
        "no_trade_reference_usdt":0,
        "no_positive_edge_or_proven_learned_profit":True,
        "repaired_old_failure_archived":True,
        "no_paper_live_or_promotion":True,
        "read_only":True}

if __name__=="__main__":
    print(json.dumps(verify(),indent=2,sort_keys=True))
