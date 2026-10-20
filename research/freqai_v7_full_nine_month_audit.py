#!/usr/bin/env python3
"""Independent read-only 273-model nine-month FreqAI after-cost research audit.

Verify source, file model digests, exact monthly/frozen weight provenance,
one-slot decision chains and trade PnL. Compute paired daily-block uplift
diagnostics. No model loading, fitting, API orders or forecast changes.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json

from scripts.v7_three_coin_learning_audit import events
from research.freqai_v7_monthly_audit import digest,load_trades,paired_moving_7d_bootstrap
from research.freqai_v7_full_nine_month_daily import START,END,DAY,EXPERIMENT,daystr,CUTS


def load(path):
    return json.loads(Path(path).read_text())


def audit(root):
    root=Path(root).resolve()
    obj=load(root/"summary.json")
    if (obj.get("experiment")!=EXPERIMENT or
        obj["start_ms"]!=START or obj["end_ms"]!=END or obj["total_days"]!=273 or
        obj["daily_fresh_model_count"]!=273):
        raise ValueError("INVALID_NINE_MONTH_EXPERIMENT_SCOPE")
    if len(obj["model_manifests"])!=273:
        raise ValueError("MISSING_ONE_OR_MORE_DAILY_MODELS")
    for name,expected in obj["archive_receipts"].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root) or not p.is_file() or digest(p)!=expected:
            raise ValueError("ARCHIVE_MISMATCH:"+name)
    model_ids=[]
    for cutoff in range(START,END,DAY):
        day=daystr(cutoff)
        m=obj["model_manifests"].get(day)
        if m is None or m["cutoff_ms"]!=cutoff:
            raise ValueError("DAILY_MODEL_DATE_OR_CUTOFF_MISMATCH:"+day)
        if (m["window_policy"]!="ROLLING_180_CALENDAR_DAYS"
            or m["window_begin_ms"]!=cutoff-180*DAY
            or m["fit_end_before_ms"]!=cutoff-14*DAY
            or m["train_last_label_ms"]>=m["fit_end_before_ms"]
            or m["calibration_last_label_ms"]>=cutoff):
            raise ValueError("FUTURE_TRAIN_LABEL_OR_WINDOW_MISMATCH:"+day)
        modelfile=root/"models"/day/"actual_freqai_net_lgbm.joblib"
        if digest(modelfile)!=m["model_sha256"]:
            raise ValueError("MODEL_SHA_MISMATCH:"+day)
        daily_prediction=root/"daily"/(day+".jsonl")
        if digest(daily_prediction)!=m["forecast_sha256"]:
            raise ValueError("DAILY_PREDICTION_SHA_MISMATCH:"+day)
        model_ids.append(m["model_sha256"])
    if len(set(model_ids))<268:
        raise ValueError("UNEXPECTED_DAILY_MODEL_DUPLICATION")
    start_str=daystr(START)
    # Model weight identity of monthly and frozen must derive from *exact*
    # same saved daily first-of-month weights, not separately retrained heads.
    monthly_sources={daystr(t):obj["model_manifests"][daystr(t)]["model_sha256"]
                     for t in CUTS}
    if len(monthly_sources)!=9 or monthly_sources[start_str]!=model_ids[0]:
        raise ValueError("NOT_SAME_JANUARY_FROZEN_MONTHLY_DAILY_START")
    # Certify which model made the prediction as-of cutoff by streaming JSONL.
    files={
        "DAILY":root/"DAILY_273_combined.jsonl",
        "MONTHLY":root/"MONTHLY_9_combined.jsonl",
        "FROZEN_JAN1":root/"FROZEN_JAN1_combined.jsonl",
    }
    candidate_stats={}
    for strategy,p in files.items():
        n=0
        previous=-1
        with p.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():continue
                r=json.loads(line)
                t=int(r["decision_ms"])
                if not START<=t<END or t<previous:
                    raise ValueError("PREDICTION_TIMESTAMP_ORDER_FAILURE")
                previous=t
                if strategy=="DAILY":
                    expected=obj["model_manifests"][daystr(t)]["model_sha256"]
                elif strategy=="MONTHLY":
                    asof=max(t0 for t0 in CUTS if t0<=t)
                    expected=monthly_sources[daystr(asof)]
                else:
                    expected=model_ids[0]
                if (r["model_sha256"]!=expected or
                    r["training_labels_available_before_ms"]>t or
                    r["features_ready_ms"]!=t+300000):
                    raise ValueError("LEAKED_OR_WRONG_MODEL_FOR_CANDIDATE:"+strategy)
                n+=1
        if n==0:raise ValueError("NO_PREDICTIONS:"+strategy)
        candidate_stats[strategy]=n
    by_policy={}
    trades={}
    for strategy in files:
        for mode in ("RAW","UNCERTAINTY","STRESS"):
            name=strategy+"_"+mode
            account=obj["accounts"][name]
            if not account["complete"]:
                raise ValueError("INCOMPLETE_ACCOUNT_"+name)
            t=load_trades(root/(name+"_trades.jsonl"))
            dcount=sum(ev.get("event")=="decision" for ev in events(root/(name+"_decisions.jsonl")))
            if dcount<50000 or len(t)!=account["trades"]:
                raise ValueError("ACCOUNT_DECISIONS_OR_TRADE_COUNT_WRONG:"+name)
            pnl=sum(float(row["net_after_cost"])*1000 for row in t)
            if abs(pnl-account["net_usdt"])>1e-3:
                raise ValueError("ACCOUNT_PNL_NOT_LEDGER_RECONCILED:"+name)
            if abs(account["stressed_pnl_usdt"]-(account["net_usdt"]-len(t)*2.5))>1e-3:
                raise ValueError("ACCOUNT_EXTRA_COST_STRESS_WRONG:"+name)
            monthly=defaultdict(lambda:[0,0.0])
            for tr in t:
                if not START<=tr["decision_ms"]<END:
                    raise ValueError("TRADE_OUTSIDE_NINE_MONTH_EVAL")
                mo=datetime.fromtimestamp(tr["exit_ms"]/1000,timezone.utc).strftime("%Y-%m")
                monthly[mo][0]+=1
                monthly[mo][1]+=tr["net_after_cost"]*1000
            for mo,stored in account["by_exit_month"].items():
                n,p=monthly[mo]
                if n!=stored["trades"] or abs(p-stored["pnl_usdt"])>1e-3:
                    raise ValueError("EXIT_MONTH_PNL_MISMATCH")
            by_policy[name]={
                "trades":len(t),"pnl_usdt":account["net_usdt"],
                "plus25bp_net_usdt":account["stressed_pnl_usdt"],
                "decision_count":dcount,
                "monthly":account["by_exit_month"],
            }
            trades[name]=t
    boot={}
    for policy in ("RAW","UNCERTAINTY","STRESS"):
        for challenger,baseline in (("DAILY","MONTHLY"),
                                    ("MONTHLY","FROZEN_JAN1"),
                                    ("DAILY","FROZEN_JAN1")):
            key=challenger+"_"+policy+"_vs_"+baseline+"_"+policy
            boot[key]=paired_moving_7d_bootstrap(
                trades[baseline+"_"+policy],
                trades[challenger+"_"+policy],
                START,END,n=2000,seed=72026,
            )
    return {
        "audited_status":"COMPLETE_273_SAVED_REAL_FREQAI_MODEL_RESULTS_VERIFIED",
        "source_sha256":obj["source_dataset_sha256"],
        "original_ninemonth_summary_sha256":digest(root/"summary.json"),
        "verified_model_count":273,
        "candidate_prediction_counts":candidate_stats,
        "wallet_accounts":by_policy,
        "paired_7day_moving_block_uplift":boot,
        "verdict":"LEARN_3C_HOLD_BECAUSE_PRIORLY_INSPECTED_2026_AND_5M_PROXY",
        "warnings":obj["warnings"],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("DO_NOT_OVERWRITE_OLD_AUDIT")
    report=audit(a.run)
    a.out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({
        "status":report["audited_status"],
        "models":report["verified_model_count"],
        "wallets":{k:{"trades":v["trades"],"net":v["pnl_usdt"],
                      "cost_stressed_net":v["plus25bp_net_usdt"]}
                  for k,v in report["wallet_accounts"].items()},
        "daily_uncertainty_vs_monthly_uncertainty":
             report["paired_7day_moving_block_uplift"]["DAILY_UNCERTAINTY_vs_MONTHLY_UNCERTAINTY"],
    },indent=2))
if __name__=="__main__":
    main()
