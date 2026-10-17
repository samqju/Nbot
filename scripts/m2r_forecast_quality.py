#!/usr/bin/env python3
"""Read official saved FreqAI forecasts and check whether they select better labels.

No training, no trading, no API calls. Uses model predictions at each decision
time and later hypothetical after-cost COMPLETE-trade outcomes for evaluation
only. NOT a Freqtrade portfolio backtest or actual exchange fill evidence.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"user_data"/"strategies"))
from nbot_trade_outcome import KINDS, CostPolicy, opportunity_table


def summarize(frame:pd.DataFrame)->dict:
    if frame.empty:
        return {"count":0,"winning_pct":None,"mean_hypothetical_net_pct":None}
    return {
        "count":int(len(frame)),
        "winning_pct":round(100*float((frame["net_return"]>0).mean()),3),
        "mean_hypothetical_net_pct":round(100*float(frame["net_return"].mean()),4)
    }


def audit(dataset:Path, models:Path, start:str, end:str, pairs:list[str],
          family:str, threshold:float)->dict:
    if family not in ("breakout","pullback","combined"):
        raise ValueError("Unsupported candidate model")
    start_at=pd.Timestamp(start,tz="UTC")
    end_at=pd.Timestamp(end,tz="UTC")
    if not start_at<end_at:
        raise ValueError("Bad window")
    results={}
    total_pred=0
    selected_examples=[]
    all_examples=[]
    for pair in pairs:
        coin=pair.split("/")[0].lower()
        files=sorted((models/"backtesting_predictions").glob(f"cb_{coin}_*_prediction.feather"))
        if not files:
            raise ValueError(f"Missing original saved FreqAI predictions {pair}")
        predictions=pd.concat((pd.read_feather(p) for p in files),ignore_index=True)
        predictions["date"]=pd.to_datetime(predictions["date"],utc=True)
        predictions=predictions.loc[
            (predictions["date"]>=start_at)&(predictions["date"]<end_at),
            ["date","&-trade_net_return","do_predict"]
        ].copy()
        if predictions["date"].duplicated().any():
            raise ValueError(f"Repeated as-of predictions {pair}")
        total_pred+=len(predictions)
        stem=pair.replace("/","_").replace(":","_")
        source=dataset/"binance"/"futures"/(stem+"-5m-futures.feather")
        candles=pd.read_feather(source)
        candles["date"]=pd.to_datetime(candles["date"],utc=True)
        # 200-bar indicator warmup; full labels require future bars which may
        # be outside evaluation end; no label = exclude, not a false win/loss.
        warmup=start_at-pd.Timedelta(minutes=5*350)
        extended_end=end_at+pd.Timedelta(minutes=5*12)
        candles=candles.loc[
            (candles["date"]>=warmup)&(candles["date"]<extended_end)
        ].reset_index(drop=True)
        opportunities=opportunity_table(candles,CostPolicy())
        if opportunities.empty:
            results[pair]={"raw":summarize(pd.DataFrame())}
            continue
        opportunities["date"]=candles.loc[opportunities["decision_index"],"date"].reset_index(drop=True)
        opportunities=opportunities.loc[
            (opportunities["date"]>=start_at)&(opportunities["date"]<end_at)
        ]
        if family!="combined":
            opportunities=opportunities.loc[
                opportunities["candidate"].str.startswith(family+"_")
            ]
        actual=opportunities.merge(predictions,on="date",how="left",validate="many_to_one",indicator=True)
        # Do not treat unknown model prediction as 0 or a NO TRADE success.
        ready=(actual["do_predict"]==1)&np.isfinite(
            pd.to_numeric(actual["&-trade_net_return"],errors="coerce")
        )
        selected=actual.loc[ready&(actual["&-trade_net_return"]>threshold)].copy()
        results[pair]={
            "raw":summarize(actual),
            "model_ready":int(ready.sum()),
            "model_predicted_good":summarize(selected),
            "unmatched_prediction":int((actual["_merge"]!="both").sum()),
        }
        all_examples.append(actual)
        selected_examples.append(selected)
    all_df=pd.concat(all_examples,ignore_index=True) if all_examples else pd.DataFrame()
    chosen=pd.concat(selected_examples,ignore_index=True) if selected_examples else pd.DataFrame()
    return {
        "window":[start,end],
        "family":family,
        "pairs":len(pairs),
        "saved_asof_predictions":total_pred,
        "prediction_threshold_after_cost_fraction":threshold,
        "all_hypothetical_candidates":summarize(all_df),
        "selected_model_positive_candidates":summarize(chosen),
        "selection_fraction_of_candidates":round(len(chosen)/len(all_df),5) if len(all_df) else None,
        "individual_pair_results":results,
        "notes":[
            "All candidate outcomes are hindsight labels for evaluation only; the model did not see these labels at prediction time if training slices are causal.",
            "These opportunities overlap; do NOT sum returns into portfolio PnL.",
            "Official Freqtrade one-slot backtesting ZIP alone represents portfolio trade PnL.",
            "The actual FreqAI train-cutoff label purging and prior has_bias=Yes are not independently resolved.",
            "All costs are original research assumed 0.21% roundtrip reserve, not measured order book.",
            "Future label must have twelve candles available; incomplete future bars are not fabricated."
        ]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--modeldir",type=Path,required=True)
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--family",choices=("combined","breakout","pullback"),required=True)
    p.add_argument("--threshold",type=float,default=.004)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    pairs=json.loads(args.config.read_text())["exchange"]["pair_whitelist"]
    result=audit(args.data,args.modeldir,args.start,args.end,pairs,args.family,args.threshold)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print("MODEL_AUDIT",json.dumps({
        "family":args.family,
        "all":result["all_hypothetical_candidates"],
        "selected":result["selected_model_positive_candidates"],
        "fraction":result["selection_fraction_of_candidates"]
    }))
    print("REPORT",args.output)


if __name__=="__main__":
    main()
