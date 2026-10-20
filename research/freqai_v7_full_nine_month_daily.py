#!/usr/bin/env python3
"""Full 2026 Jan-Sep one-slot evaluation with pre-2026 warm-up.

Research-only actual upstream FreqAI LightGBMRegressor.fit daily 180-day
past-matured V7 net-outcome labels, 14-day past-only q75 uncertainty,
fixed BTC ETH SOL / existing families, one continuous 9-month wallet.

Three SAME-first-day baselines: daily, monthly (use daily model fitted on
month's first day for entire month), frozen January model for all 9 months.
This avoids inconsistent initial models and tests frequency itself.

Never reuse the already trained JULY 2026 model to trade JANUARY (leakage).
Uses prior year's PUBLIC checksum-verified archives. No online trades.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter
from hashlib import sha256

from nbot_v7.experiment import month_start, add_months
from research.freqai_v7_monthly_180d import fit_window, concat_month_files, evaluate, DAY
from research.freqai_v7_net_fit_and_replay import existing_source,prediction_export,digest

START=month_start("2026-01")
END=month_start("2026-10")
DAY_COUNT=(END-START)//DAY
EXPERIMENT="V7_FULL_2026_NINEMONTH_REAL_FREQAI_DAILY_180D_AFTERCOST_V1"
CUTS=[add_months(START,n) for n in range(9)]


def daily_cutoffs():
    return range(START,END,DAY)


def daystr(ts):
    return datetime.fromtimestamp(ts/1000,timezone.utc).strftime("%Y-%m-%d")


def first_day_model_key(ms):
    return daystr(max(t for t in CUTS if t<=ms))


def fit_and_export_day(conn,output,cutoff,*,resume):
    key=daystr(cutoff)
    modeldir=output/"models"/key
    forecast=output/"daily"/(key+".jsonl")
    if modeldir.exists() or forecast.exists():
        if not (resume and modeldir.is_dir() and forecast.exists()):
            raise ValueError("UNSAFE_PARTIAL_DAILY_CHECKPOINT:"+key)
        m=json.loads((modeldir/"manifest.json").read_text())
        if (m["cutoff_ms"]!=cutoff or
                m["window_policy"]!="ROLLING_180_CALENDAR_DAYS" or
                digest(modeldir/"actual_freqai_net_lgbm.joblib")!=m["model_sha256"] or
                m.get("forecast_sha256")!=digest(forecast)):
            raise ValueError("CHECKPOINT_MODEL_OR_FORECAST_TAMPERED:"+key)
    else:
        m=fit_window(conn,cutoff,modeldir)
        source=prediction_export(conn,modeldir/"actual_freqai_net_lgbm.joblib",
                                 m,cutoff,cutoff+DAY,forecast)
        m["forecast_rows"]=source["records"]
        m["forecast_sha256"]=source["sha256"]
        (modeldir/"manifest.json").write_text(json.dumps(m,indent=2,sort_keys=True)+"\n")
    return m,forecast


def research(db,output,*,resume=False):
    if output.exists() and not resume:
        raise FileExistsError("REFUSE_OVERWRITE_NINEMONTH_RESEARCH")
    output.mkdir(parents=True,exist_ok=True)
    (output/"models").mkdir(exist_ok=True)
    (output/"daily").mkdir(exist_ok=True)
    (output/"monthly").mkdir(exist_ok=True)
    conn=existing_source(db)
    try:
        scope=dict(conn.execute("SELECT k,v FROM meta"))
        if int(scope["start_ms"])>month_start("2025-07") or int(scope["end_ms"])<END:
            raise ValueError("180DAY_PREHISTORY_OR_END_OF_2026_MISSING")
        model_m={}
        daily_paths=[]
        for i,cutoff in enumerate(daily_cutoffs()):
            m,forecast=fit_and_export_day(conn,output,cutoff,resume=resume)
            model_m[daystr(cutoff)]=m
            daily_paths.append(forecast)
            if (i+1)%14==0 or cutoff+DAY==END:
                print(json.dumps({"progress":"NINE_MONTH_DAILY_MODEL_FITS",
                      "days_completed":i+1,"days_total":DAY_COUNT,
                      "asof":daystr(cutoff),"fit_rows":m["fit_rows"]}),
                      flush=True)
        # Daily sequence of 273 timestamp-aligned models.
        daily_file=output/"DAILY_273_combined.jsonl"
        if daily_file.exists():
            if not resume or digest(daily_file)!=json.loads((output/"concat_digests.json").read_text()).get("daily"):
                raise ValueError("DAILY_CONCAT_EXISTS_UNVERIFIED")
        else:
            concat_month_files(daily_paths,daily_file)
        # MONTHLY: 9 models are *exact same* as the daily first-of-month
        # model; applies for full calendar month. No monthly model refitting.
        monthly_parts=[]
        for t,nxt in zip(CUTS,CUTS[1:]+[END]):
            name=daystr(t)
            m=model_m[name]
            part=output/"monthly"/(name+".jsonl")
            if not part.exists():
                prediction_export(conn,output/"models"/name/"actual_freqai_net_lgbm.joblib",
                                  m,t,nxt,part)
            elif not resume:
                raise ValueError("PREEXISTING_MONTHLY_PREDICTIONS")
            monthly_parts.append(part)
        monthly_file=output/"MONTHLY_9_combined.jsonl"
        if not monthly_file.exists():
            concat_month_files(monthly_parts,monthly_file)
        # FROZEN JANUARY: same exact Jan1 model on all Jan-Sep candidates.
        frozen=output/"FROZEN_JAN1_combined.jsonl"
        if not frozen.exists():
            prediction_export(
                conn,output/"models"/daystr(START)/"actual_freqai_net_lgbm.joblib",
                model_m[daystr(START)],START,END,frozen)
        (output/"concat_digests.json").write_text(json.dumps({
            "daily":digest(daily_file),"monthly":digest(monthly_file),
            "frozen":digest(frozen)},indent=2,sort_keys=True)+"\n")
        account_reports={}
        for approach,file in (("DAILY",daily_file),("MONTHLY",monthly_file),
                              ("FROZEN_JAN1",frozen)):
            for mode in ("RAW","UNCERTAINTY","STRESS"):
                label=approach+"_"+mode
                report=evaluate(conn,file,START,END,name=label,output_dir=output,mode=mode)
                account_reports[label]=report
                print(json.dumps({"progress":"COMPLETE_ONE_SLOT_ACCOUNT",
                                  "account":label,"trades":report["trades"],
                                  "net_usdt":report["net_usdt"],
                                  "plus25bp_net_usdt":report["stressed_pnl_usdt"]}),
                                  flush=True)
        archive_receipts={}
        for p in sorted(output.rglob("*")):
            if p.is_file() and p.name!="summary.json":
                archive_receipts[str(p.relative_to(output))]=digest(p)
        summary={
            "experiment":EXPERIMENT,
            "source_dataset_sha256":digest(db),
            "start_ms":START,"end_ms":END,"total_days":DAY_COUNT,
            "daily_fresh_model_count":len(model_m),
            "monthly_frozen_model_count":9,
            "model_manifests":model_m,
            "accounts":account_reports,
            "archive_receipts":archive_receipts,
            "no_trade_net_usdt":0.0,
            "warnings":[
                "2025 July-Dec warmup archive presence does NOT attest contract tradeability.",
                "2026 Jan-Sep previously inspected; neither expanding research nor nominal profit is fresh holdout.",
                "Models trained from V7 conditional outcome labels on real FreqAI LightGBMRegressor.fit; not FreqAI native start_backtesting.",
                "All paper fills, fees/slippage and funding are 5m V7 proxy; no Binance executable order verification.",
                "Daily and monthly January initial model are literally the same model file, no later-data leakage.",
                "The global 14d q75 calibration is not a selection-conditioned uncertainty probability.",
                "Futures backtest result is not an investment or model-promotion authorization.",
            ]
        }
        (output/"summary.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        print(json.dumps({"status":"FULL_9MO_FINISHED",
           "models":len(model_m),
           "accounts":{k:{"trades":v["trades"],"pnl":v["net_usdt"],
               "stressed":v["stressed_pnl_usdt"],"months":v["by_exit_month"]}
               for k,v in account_reports.items()}},sort_keys=True,indent=2))
    finally:
        conn.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--resume",action="store_true")
    a=p.parse_args()
    research(a.db,a.out,resume=a.resume)

if __name__=="__main__":
    main()
