#!/usr/bin/env python3
"""Audit real FreqAI daily re-fit source, decisions, costs, and paired uplift.

Reads saved historical research only; no model loading, model training,
orders, exchange connections or inference. All gains are hypothetical.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json

from scripts.v7_three_coin_learning_audit import events
from research.freqai_v7_monthly_audit import (
    digest,load_trades,paired_moving_7d_bootstrap,
)
from research.freqai_v7_daily_180d import (
    SCHEMA,START,END,DAY,daystring
)


def audit(daily_folder,monthly_folder):
    root=Path(daily_folder).resolve()
    monthly=Path(monthly_folder).resolve()
    with (root/"summary.json").open() as fp:
        entry=json.load(fp)
    if entry.get("experiment")!=SCHEMA or entry["start"]!=START or entry["end"]!=END:
        raise ValueError("DAILY_RUN_SCHEMA_OR_EVALUATION_MISMATCH")
    if len(entry["model_manifests"])!=92:
        raise ValueError("MISSING_DAILY_RETRAIN_MODEL")
    for rel,h in entry["source_receipts"].items():
        p=(root/rel).resolve()
        if not p.is_relative_to(root) or not p.is_file() or digest(p)!=h:
            raise ValueError("DAILY_SOURCE_ARTIFACT_HASH_MISMATCH:"+rel)
    actual_days=set(entry["model_manifests"])
    expected_days={daystring(x) for x in range(START,END,DAY)}
    if actual_days!=expected_days:
        raise ValueError("DAILY_MODEL_DATES_NOT_COMPLETE")
    model_sha=[]
    for day,info in entry["model_manifests"].items():
        expected_ms=int(datetime.strptime(day,"%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()*1000)
        if info["cutoff_ms"]!=expected_ms:
            raise ValueError("MODEL_WRONG_DAY:"+day)
        if (info["window_begin_ms"]!=expected_ms-180*DAY
                or info["fit_end_before_ms"]!=expected_ms-14*DAY
                or info["train_last_label_ms"]>=info["fit_end_before_ms"]
                or info["calibration_last_label_ms"]>=expected_ms):
            raise ValueError("FUTURE_TRAINING_LABEL_OR_WRONG_HISTORIC_WINDOW:"+day)
        if digest(root/day/"actual_freqai_net_lgbm.joblib")!=info["model_sha256"]:
            raise ValueError("MISSING_MODEL_HASH_MATCH:"+day)
        model_sha.append(info["model_sha256"])
    if len(set(model_sha))<90:
        raise ValueError("MOST_DAILY_MODELS_IDENTICAL_SUSPECT_SCHEDULER")
    day_accounts={}
    all_trades={}
    for mode in ("RAW","UNCERTAINTY","STRESS"):
        name="DAILY_"+mode
        account=entry["portfolios"][name]
        if not account["complete"]:
            raise ValueError("INCOMPLETE_DAILY_ACCOUNT")
        tradefile=root/(name+"_trades.jsonl")
        trades=load_trades(tradefile)
        n_events=sum(e.get("event")=="decision" for e in events(root/(name+"_decisions.jsonl")))
        if n_events<1000 or len(trades)!=account["trades"]:
            raise ValueError("MISSING_DAILY_DECISIONS_OR_TRADES")
        actual=sum(t["net_after_cost"]*1000 for t in trades)
        if abs(actual-account["net_usdt"])>1e-3:
            raise ValueError("PNL_SUM_MISMATCH:"+name)
        if abs(account["stressed_pnl_usdt"]-(account["net_usdt"]-2.5*len(trades)))>1e-3:
            raise ValueError("STRESS_NOT_RECONCILED:"+name)
        day_accounts[name]={
            "completed_trades":len(trades),
            "net_usdt":account["net_usdt"],
            "stressed_net_usdt":account["stressed_pnl_usdt"],
            "decisions":n_events,
            "by_month":account["by_exit_month"],
        }
        all_trades[name]=trades
    mm=json.loads((monthly/"summary.json").read_text())
    if mm["original_dataset_sha256"]!=entry["source_dataset_sha256"]:
        raise ValueError("DAILY_MONTHLY_SOURCE_MISMATCH")
    results={}
    for mode in ("RAW","UNCERTAINTY","STRESS"):
        daily=all_trades["DAILY_"+mode]
        for benchmark in ("FROZEN_JULY","ROLLING","EXPANDING"):
            key=benchmark+"_"+mode
            base=load_trades(monthly/(key+"_trades.jsonl"))
            if len(base)!=mm["portfolio_accounts"][key]["trades"]:
                raise ValueError("BENCHMARK_LEDGER_MISSING_OR_INCONSISTENT")
            results["DAILY_"+mode+"_vs_"+key]=paired_moving_7d_bootstrap(
                base,daily,START,END,n=2000,seed=72026
            )
    return {
        "result":"PASSED_READ_ONLY_92_MODEL_FUTURE_BOUNDARY_AUDIT",
        "daily_source_sha":entry["source_dataset_sha256"],
        "daily_summary_sha":digest(root/"summary.json"),
        "monthly_summary_sha":digest(monthly/"summary.json"),
        "verified_daily_models":len(model_sha),
        "accounts":day_accounts,
        "paired_uplift_vs_frozen_monthly_expanding":results,
        "verdict":"LEARN_3C_HOLD_NO_NOVEL_OOS_OR_NATIVE_FILL_PROOF",
        "limitations":entry["warnings"],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--daily",type=Path,required=True)
    p.add_argument("--monthly",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("DO_NOT_CLOBBER_PREVIOUS_AUDIT")
    r=audit(a.daily,a.monthly)
    a.out.write_text(json.dumps(r,sort_keys=True,indent=2)+"\n")
    print(json.dumps({
        "status":r["result"],
        "accounts":r["accounts"],
        "raw_uplift_vs_rolling":r["paired_uplift_vs_frozen_monthly_expanding"]["DAILY_RAW_vs_ROLLING_RAW"]
    },sort_keys=True,indent=2))
if __name__=="__main__":
    main()
