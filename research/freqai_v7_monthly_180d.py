#!/usr/bin/env python3
"""Compare FreqAI monthly re-fitting against a SAME-JULY-model frozen control.

Exact fixed Jul/Aug/Sep 2026 three-coin cohort. 180-day *lookback* includes
last 14 days reserved for score-error calibration; model fit on preceding
166 days of mature outcomes. All model heads are trained afresh by REAL
FreqAI LightGBMRegressor.fit, no warm starting or sequential contamination.

Each policy gets one continuous Jul-Sep V7 single-slot replay. Changing
month does not reset wallet capital or slot. The official FreqAI example and
true full FreqAI start_backtesting scheduler are NOT invoked. This is a
V7-native research adaptation, NOT an economically validated strategy.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json
import math
import sqlite3

from nbot_v7.experiment import month_start, replay
from nbot_v7.lab import LABEL_POLICY
from nbot_v7.artifacts import EventLog
from nbot_v7.freqai_research_bridge import FreqAINetResearchBrain
from research.freqai_v7_net_fit_and_replay import (
    CAL_DAYS, MAX_ROWS, STRESS, digest, existing_source, actual_freqai_fit,
    matrix, prediction_export,
)
import numpy as np
import joblib

DAY = 86400000
LOOKBACK_DAYS = 180
MONTHS = ("2026-07", "2026-08", "2026-09")
POLICIES = ("RAW", "UNCERTAINTY", "STRESS")
EXPERIMENT = "V7_3COIN_FREQAI_REAL_FIT_180DAY_MONTHLY_COMPARATIVE_V1"


def training_bounds(cutoff_ms: int, *, expanding: bool=False):
    """Historical data never extends past 14-day prior-only calibration."""
    first = month_start("2026-01") if expanding else cutoff_ms-LOOKBACK_DAYS*DAY
    calibration_begin = cutoff_ms-CAL_DAYS*DAY
    if first >= calibration_begin:
        raise ValueError("INVALID_RESEARCH_WINDOW")
    return first, calibration_begin, cutoff_ms


def fit_window(conn, cutoff_ms, output_dir, *, expanding=False,
               label_policy=LABEL_POLICY):
    first,cal_begin,cutoff = training_bounds(cutoff_ms,expanding=expanding)
    # Do not use the old group stride that accidentally made Brain A/B sample
    # approximately the same count after adding 3 months of historical data.
    rows=conn.execute(
        "SELECT * FROM opportunity WHERE decision_ms>=? AND decision_ms<? "
        "AND label_available_ms<? ORDER BY decision_ms,symbol,side,family",
        (first,cutoff,cutoff),
    ).fetchall()
    if len(rows)>MAX_ROWS:
        raise RuntimeError("HISTORIC_MODEL_TRAINING_ROW_BUDGET_EXCEEDED")
    train=[r for r in rows if r["decision_ms"]<cal_begin
           and r["label_available_ms"]<cal_begin]
    calibration=[r for r in rows if r["decision_ms"]>=cal_begin
                 and r["label_available_ms"]<cutoff]
    if len(train)<15000 or len(calibration)<500:
        raise ValueError("INSUFFICIENT_MATURED_TRAIN_OR_CALIBRATION_SAMPLES")
    if max(int(r["label_available_ms"]) for r in train)>=cal_begin:
        raise ValueError("TRAINING_FUTURE_LABEL_AT_CALIBRATION_BOUNDARY")
    output_dir.mkdir(parents=True,exist_ok=False)
    model=actual_freqai_fit(matrix(train),[float(r["net"]) for r in train],output_dir)
    predicted=np.asarray(model.predict(matrix(calibration))).reshape(-1)
    actual=np.asarray([float(r["net"]) for r in calibration])
    residual=predicted-actual
    q75=float(np.quantile(np.abs(residual),.75))
    path=output_dir/"actual_freqai_net_lgbm.joblib"
    joblib.dump(model,path)
    manifest={
        "trainer":"REAL_UPSTREAM_FREQAI_LIGHTGBMREGRESSOR_FIT_CUSTOM_RESEARCH_HARNESS",
        "uses_freqai_native_start_backtesting":False,
        "rolling_monthly":True,
        "window_policy":"EXPANDING_FROM_2026_JAN_01" if expanding else "ROLLING_180_CALENDAR_DAYS",
        "window_begin_ms":first,"fit_end_before_ms":cal_begin,
        "model_available_at_ms":cutoff,
        "training_labels_before_ms":cal_begin,
        "calibration_label_available_before_ms":cutoff,
        "fit_rows":len(train),"calibration_rows":len(calibration),
        "train_last_label_ms":max(int(r["label_available_ms"]) for r in train),
        "calibration_last_label_ms":max(int(r["label_available_ms"]) for r in calibration),
        "calibration_q75_abs_residual_net":q75,
        "calibration_q75_bp":round(q75*10000,4),
        "mean_calibration_error_bp":round(float(np.mean(residual))*10000,4),
        "uncertainty_net":q75,
        "cutoff_ms":cutoff,
        "model_sha256":digest(path),
        "source_policy":label_policy,
    }
    (output_dir/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest


def concat_month_files(paths, destination):
    with destination.open("x",encoding="utf-8") as out:
        prev=-1
        count=0
        for fp in paths:
            with fp.open("r",encoding="utf-8") as inp:
                for line in inp:
                    if not line.strip():continue
                    # chronological, sorted inside each monthly sequence
                    obj=json.loads(line)
                    t=int(obj["decision_ms"])
                    if t<prev:
                        raise ValueError("FORECAST_MONTHS_OUT_OF_ORDER")
                    prev=t
                    out.write(line)
                    count+=1
    return {"rows":count,"sha256":digest(destination)}


def evaluate(conn,forecast_file,start,end,*,name,output_dir,mode,
             label_policy=LABEL_POLICY):
    brain=FreqAINetResearchBrain.from_jsonl(
        forecast_file,cutoff_ms=start,version=name,
        label_policy=label_policy,
        uncertainty_weight=0 if mode=="RAW" else 1.0,
        cost_stress=STRESS if mode=="STRESS" else 0,
    )
    chain=EventLog(output_dir/(name+"_decisions.jsonl"))
    try:
        result=replay(conn,brain,start,end,event_sink=chain.write)
    finally:
        chain.close()
    if not result["account_complete"]:
        raise ValueError("INCOMPLETE_CHRONOLOGICAL_ACCOUNT")
    path=output_dir/(name+"_trades.jsonl")
    with path.open("x",encoding="utf-8") as out:
        for t in result["trades"]:
            out.write(json.dumps(t,sort_keys=True,allow_nan=False)+"\n")
    by_month=defaultdict(lambda:{"trades":0,"pnl_usdt":0.0})
    for trade in result["trades"]:
        close=datetime.fromtimestamp(int(trade["exit_ms"])/1000,timezone.utc).strftime("%Y-%m")
        bucket=by_month[close]
        bucket["trades"]+=1
        bucket["pnl_usdt"]+=float(trade["net_after_cost"])*1000
    return {
        "trades":result["selected_trades"],
        "net_usdt":result["net_pnl_usdt"],
        "stressed_pnl_usdt":result["stressed_pnl_usdt"],
        "complete":result["account_complete"],
        "max_drawdown_pct_of_sleeve":result["max_drawdown_pct_of_sleeve"],
        "by_exit_month":{k:{"trades":v["trades"],"pnl_usdt":round(v["pnl_usdt"],4)}
                         for k,v in sorted(by_month.items())},
        "slot_conflict_count":result["stats"].get("occupied_slot_decisions"),
        "model_cutoff_ms":start,
    }


def research(db,output):
    if output.exists():raise FileExistsError("REFUSE_OVERWRITE_PRIOR_MONTHLY_EXPERIMENT")
    output.mkdir(parents=True)
    conn=existing_source(db)
    start=month_start("2026-07")
    end=month_start("2026-10")
    try:
        manifest={}
        cuts=[month_start(x) for x in MONTHS]
        # THREE fitted rolling heads, July common to all approaches.
        for month,cutoff in zip(MONTHS,cuts):
            name="ROLLING_"+month
            manifest[name]=fit_window(conn,cutoff,output/name)
        # Expanding has a DISTINCT Aug and Sep refit; reuse July model as both
        # have same first-date Jan1 within one day of rolling Jul1.
        # Fit a true expanding-July head for a fair expanding model group.
        for month,cutoff in zip(MONTHS,cuts):
            name="EXPANDING_"+month
            manifest[name]=fit_window(conn,cutoff,output/name,expanding=True)
        policy_input={}
        month_bounds=list(zip(MONTHS,cuts,cuts[1:]+[end]))
        for strategy in ("ROLLING","EXPANDING"):
            source_parts=[]
            for month,lo,hi in month_bounds:
                model_key=strategy+"_"+month
                f=output/(model_key+"_forecasts.jsonl")
                m=manifest[model_key]
                stats=prediction_export(
                    conn,output/model_key/"actual_freqai_net_lgbm.joblib",m,
                    lo,hi,f,
                )
                source_parts.append(f)
                manifest[model_key]["forecast_rows"]=stats["records"]
            policy_input[strategy]=concat_month_files(source_parts,output/(strategy+"_combined.jsonl"))
        # Freeze baseline: exact same ROLLING July model as first monthly
        # model, but DO NOT let August/September forecasts change.
        frozen=output/"FROZEN_JULY_combined.jsonl"
        frozen_stats=prediction_export(
            conn,output/"ROLLING_2026-07"/"actual_freqai_net_lgbm.joblib",
            manifest["ROLLING_2026-07"],start,end,frozen,
        )
        policy_input["FROZEN_JULY"]=frozen_stats
        accounts={}
        for strategy in ("FROZEN_JULY","ROLLING","EXPANDING"):
            for mode in POLICIES:
                name=strategy+"_"+mode
                accounts[name]=evaluate(
                    conn,output/(strategy+"_combined.jsonl"),
                    start,end,name=name,output_dir=output,mode=mode,
                )
        receipts={}
        for f in sorted(output.rglob("*")):
            if f.is_file() and f.name!="summary.json":
                receipts[str(f.relative_to(output))]=digest(f)
        result={
            "experiment":EXPERIMENT,
            "authority":"OFFLINE_RESEARCH_ONLY_NO_REAL_ORDERS_NO_MODEL_PROMOTION",
            "start":start,"end":end,
            "original_dataset_sha256":digest(db),
            "window_days":LOOKBACK_DAYS,"calibration_days":CAL_DAYS,
            "model_manifests":manifest,
            "predictions":policy_input,
            "portfolio_accounts":accounts,
            "flat_baseline_usdt":0.0,
            "artifact_receipts":receipts,
            "warnings":[
                "Full Jul-Sep 2026 previously studied; NOT pristine unseen holdout.",
                "Uses real upstream FreqAI LightGBMRegressor.fit, not FreqAI native scheduler.",
                "180-day lookback includes last 14 days calibration; fit uses preceding 166 days.",
                "Models freshly trained every first calendar day; NOT an after-each-executed-trade learner.",
                "Realized PnL from V7 5m OHLC stop-first/fees/slippage/funding proxies; not actual exchange fills.",
                "Selection-conditioned net prediction calibration NOT demonstrated; all-candidate q75 is just a diagnostic.",
                "Monthly expanding and rolling vs July frozen compared with identical policy/one-slot capital and 3 coins.",
                "Trade-count changes alone are not learning; test significance, cost stress and external forward data.",
            ],
        }
        (output/"summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        print(json.dumps({
            "months":{k:{"train_rows":v["fit_rows"],"calibration_rows":v["calibration_rows"],
                          "q75_bp":v["calibration_q75_bp"]} for k,v in manifest.items()},
            "accounts":{k:{"trades":v["trades"],"net":v["net_usdt"],
                            "extra25bp_stress_net":v["stressed_pnl_usdt"],
                            "monthly":v["by_exit_month"]} for k,v in accounts.items()},
        },indent=2))
    finally:
        conn.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    research(args.db,args.output)


if __name__=="__main__":
    main()
