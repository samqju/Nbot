#!/usr/bin/env python3
"""Daily-vs-monthly FreqAI-fitted V7 research. No running exchange services.

Freshly refit REAL FreqAI LightGBMRegressor head at each 00:00 UTC
Jul1-Sep30 using only prior matured labels. A *rolling 180-day* source
window includes 14-day late calibration partition, as in monthly research.
Daily lookback and model hyperparameters match the monthly runner exactly.

Uses one continuous Jul-Sep V7 one-slot wallet for the completed daily
forecast stream. Monthly/frozen scores live in separate earlier source-
hash verified run and are evaluated with identical forecast target and exit.
This is NOT native FreqAI continuous trade mode or validated positive alpha.

Run is checkpointable by per-day finished model manifest + prediction file;
a resume is permitted ONLY with hash-verified, date-bound artifacts.
"""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json
import os

from nbot_v7.experiment import month_start
from nbot_v7.artifacts import EventLog
from nbot_v7.freqai_research_bridge import FreqAINetResearchBrain
from research.freqai_v7_monthly_180d import fit_window,concat_month_files, evaluate, DAY
from research.freqai_v7_net_fit_and_replay import existing_source,prediction_export,digest,STRESS

START=month_start("2026-07")
END=month_start("2026-10")
SCHEMA="V7_3COIN_DAILY_180D_REAL_FREQAI_FIT_OFFLINE_RESEARCH_V1"


def daily_dates():
    return range(START,END,DAY)


def daystring(ms):
    return datetime.fromtimestamp(ms/1000,timezone.utc).strftime("%Y-%m-%d")


def compute(db,output, *,resume=False):
    if output.exists() and not resume:
        raise FileExistsError("REFUSE_OVERWRITE_EXISTING_DAILY_STUDY")
    if not output.exists():
        output.mkdir(parents=True)
    source=existing_source(db)
    try:
        manifests={}
        paths=[]
        for index,cutoff in enumerate(daily_dates()):
            day=daystring(cutoff)
            folder=output/day
            forecast=output/(day+"_forecast.jsonl")
            if folder.exists() or forecast.exists():
                if not resume or not folder.is_dir() or not forecast.is_file():
                    raise ValueError("INCOMPLETE_OR_UNAPPROVED_RESUME_DAY:"+day)
                manifest=json.loads((folder/"manifest.json").read_text())
                if (manifest["cutoff_ms"]!=cutoff
                        or manifest["window_policy"]!="ROLLING_180_CALENDAR_DAYS"
                        or digest(folder/"actual_freqai_net_lgbm.joblib")!=manifest["model_sha256"]):
                    raise ValueError("RESUMED_MODEL_MISMATCH:"+day)
                count=sum(1 for _ in forecast.open())
                if count<=0 or manifest.get("forecast_sha256")!=digest(forecast) or manifest.get("forecast_rows")!=count:
                    raise ValueError("RESUMED_PREDICTION_HASH_OR_COUNT_MISMATCH:"+day)
            else:
                manifest=fit_window(source,cutoff,folder)
                metadata=prediction_export(
                    source,folder/"actual_freqai_net_lgbm.joblib",
                    manifest,cutoff,cutoff+DAY,forecast,
                )
                manifest["forecast_sha256"]=metadata["sha256"]
                manifest["forecast_rows"]=metadata["records"]
                (folder/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
            manifests[day]=manifest
            paths.append(forecast)
            if (index+1)%7==0 or cutoff+DAY==END:
                print(json.dumps({"progress":"DAILY_FIT_CHECKPOINT",
                                  "days_complete":index+1,
                                  "total_days":len(list(daily_dates())),
                                  "last_fitted":day,
                                  "train_rows":manifest["fit_rows"]}),flush=True)
        combined=output/"DAILY_combined.jsonl"
        if combined.exists():
            if not resume:raise ValueError("UNEXPECTED_PREEXISTING_COMBINED_FILE")
            combined.unlink() # Only derivative of individually verified per-day logs.
        concatenated=concat_month_files(paths,combined)
        outcomes={}
        for policy in ("RAW","UNCERTAINTY","STRESS"):
            tag="DAILY_"+policy
            results=evaluate(source,combined,START,END,
                             name=tag,output_dir=output,mode=policy)
            outcomes[tag]=results
        evidence={}
        for path in sorted(output.rglob("*")):
            if path.is_file():
                evidence[str(path.relative_to(output))]=digest(path)
        report={
            "experiment":SCHEMA,"start":START,"end":END,
            "fit_cycle":"DAILY_00UTC","lookback_days":180,"calibration_days":14,
            "source_dataset_sha256":digest(db),
            "model_manifests":manifests,
            "forecasts":concatenated,
            "portfolios":outcomes,
            "source_receipts":evidence,
            "no_trade_baseline_net_usdt":0,
            "warnings":[
                "Original 2026 Jul-Sep data previously investigated many times; NEVER pristine or deployment-level proof.",
                "Each daily model trained FRESH with installed FreqAI LightGBMRegressor.fit API; not continued model weights.",
                "Not the official native FreqAI per-pair start_backtesting scheduler.",
                "Uses same V7 three coins/20 strategy families/2% stop/3% target/60m horizon/5m proxy and base modeled fees.",
                "Daily calibrated q75 absolute candidate error is NOT valid selected-top-trade confidence coverage.",
                "Any improvement must be robust vs frozen July, monthly rolling, expanding, NO TRADE and +25bp per trade stress.",
                "One wallet across all 92 days, without monthly capital resets.",
            ],
        }
        (output/"summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        print(json.dumps({"status":"COMPLETE",
                          "models":len(manifests),
                          "account_summary":{k:{"trades":v["trades"],
                                                 "net_usdt":v["net_usdt"],
                                                 "stressed_usdt":v["stressed_pnl_usdt"],
                                                 "by_month":v["by_exit_month"]}
                                             for k,v in outcomes.items()}},indent=2))
    finally:
        source.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--resume",action="store_true")
    args=p.parse_args()
    compute(args.db,args.output,resume=args.resume)
if __name__=="__main__":
    main()
