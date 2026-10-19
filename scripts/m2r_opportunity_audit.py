#!/usr/bin/env python3
"""Summarize every hypothetical setup (executed or skipped) in fixed history.

NOT a backtest or portfolio PnL: simultaneous overlapping opportunities may
share the same future price path. Never combine this hypothetical sum into
a wallet return, nor claim it is an out-of-sample model score.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"user_data"/"strategies"))
from nbot_trade_outcome import CostPolicy, KINDS, opportunity_table


def summarize(df: pd.DataFrame) -> dict:
    if len(df)==0:
        return {"opportunities":0}
    return {
        "opportunities":len(df),
        "hypothetical_after_cost_win_pct":round(100*(df["net_return"]>0).mean(),3),
        "avg_hypothetical_net_pct":round(100*df["net_return"].mean(),4),
        "median_hypothetical_net_pct":round(100*df["net_return"].median(),4),
        "exit_reasons":{str(k):int(v) for k,v in df["exit_reason"].value_counts().to_dict().items()},
    }


def audit_period(datadir:Path, start:str, end:str, pairs:list[str]) -> dict:
    start_time=pd.Timestamp(start,tz="UTC")
    end_time=pd.Timestamp(end,tz="UTC")
    by_kind={name:[] for name in KINDS}
    per_pair={}
    all_rows=[]
    for pair in pairs:
        stem=pair.replace("/","_").replace(":","_")
        path=datadir/"binance"/"futures"/(stem+"-5m-futures.feather")
        if not path.exists():
            raise ValueError(f"Missing candles {pair}")
        src=pd.read_feather(path)
        candles=src.loc[(src["date"]>=start_time)&(src["date"]<end_time)].copy().reset_index(drop=True)
        required=int((end_time-start_time)/pd.Timedelta(minutes=5))
        if len(candles)!=required or candles["date"].duplicated().any():
            raise ValueError(f"Unusable coverage {pair} {len(candles)} vs {required}")
        opportunities=opportunity_table(candles,CostPolicy())
        per_pair[pair]=summarize(opportunities)
        if len(opportunities):
            opportunities["pair"]=pair
            all_rows.append(opportunities)
    if not all_rows:
        raise ValueError("No candidate opportunities")
    all_opportunities=pd.concat(all_rows,ignore_index=True)
    return {
        "pairs":len(pairs),"window_utc":[start,end],
        "total_market_candles":required*len(pairs),
        "all_four_setup_types_overlapping":summarize(all_opportunities),
        "by_setup":{
            kind:summarize(all_opportunities.loc[all_opportunities["candidate"]==kind])
            for kind in KINDS
        },
        "by_pair":per_pair,
        "caution":[
            "Training LABEL outcomes from future candles, not prices known when placing a trade.",
            "Every setup is a separate hypothetical opportunity; duplicate times across pairs overlap.",
            "Not executable positions, wallet returns or proof of investment edge.",
            "Stop-first intrabar assumption, next OPEN entry, after-cost reserve; no real order book.",
            "October and September are already examined research periods, NOT untouched final validation.",
            "Rolling 30-day training must purge labels whose exit times exceed its cutoff.",
        ],
    }


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",required=True,type=Path)
    parser.add_argument("--data",required=True,type=Path)
    parser.add_argument("--start",required=True)
    parser.add_argument("--end",required=True)
    parser.add_argument("--output",required=True,type=Path)
    opts=parser.parse_args()
    pairs=json.loads(opts.config.read_text())["exchange"]["pair_whitelist"]
    if len(pairs)!=25:
        raise ValueError("Expected original 25 pair universe")
    study=audit_period(opts.data,opts.start,opts.end,pairs)
    opts.output.parent.mkdir(parents=True,exist_ok=True)
    opts.output.write_text(json.dumps(study,indent=2)+"\n")
    print("CANDLE_DECISIONS",study["total_market_candles"])
    print("OPPORTUNITIES",study["all_four_setup_types_overlapping"])
    print("BY_SETUP",{key:v["opportunities"] for key,v in study["by_setup"].items()})
    print("REPORT",opts.output)


if __name__=="__main__":
    main()
