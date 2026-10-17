#!/usr/bin/env python3
"""M2R compare actual official Freqtrade FreqAI backtest trades.

This script never fits models or runs trading. It reads trusted Freqtrade
backtest ZIP exports and reports one-position historical net PnL, risk
and actual decisions alongside NO TRADE. Different strategy exit rules
mean this is not a causal attribution of PnL to AI alone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from m2_funding_reconcile import archive_strategy, timestamp_ms

STRATEGIES = {
    "original_price_AI": "NbotV6",
    "simple_non_AI": "NbotV6NoML",
    "after_cost_combined_AI": "NbotV6TradeOutcomeResearch",
    "after_cost_breakout_AI": "NbotV6BreakoutResearch",
    "after_cost_pullback_AI": "NbotV6PullbackResearch",
    "matched_no_AI_combined": "NbotV6MatchedNoMLResearch",
    "matched_no_AI_breakout": "NbotV6MatchedBreakoutNoMLResearch",
    "matched_no_AI_pullback": "NbotV6MatchedPullbackNoMLResearch",
}


def examine(stats:dict, name:str, start_ms:int, end_ms:int)->dict:
    trades=stats["trades"]
    if any(
        timestamp_ms(t["open_date"])<start_ms or timestamp_ms(t["close_date"])>end_ms
        for t in trades
    ):
        raise ValueError(f"Trade outside comparison window: {name}")
    periods=sorted((timestamp_ms(t["open_date"]),timestamp_ms(t["close_date"])) for t in trades)
    overlaps=sum(a<periods[i-1][1] for i,(a,b) in enumerate(periods) if i)
    if overlaps:
        raise ValueError(f"Global slot overlap: {name}: {overlaps}")
    winning=sum(float(t["profit_abs"])>0 for t in trades)
    value=float(stats["profit_total_abs"])
    return {
        "trades":len(trades),
        "wins":winning,
        "losses_or_breakevens":len(trades)-winning,
        "win_pct":round(100*winning/len(trades),2) if trades else None,
        "net_usdt":round(value,3),
        "fee_rate_entry":stats.get("fee_open"),
        "fee_rate_exit":stats.get("fee_close"),
        "max_drawdown_usdt":round(float(stats.get("max_drawdown_abs") or 0),3),
        "profit_factor":stats.get("profit_factor"),
        "longs":sum(not bool(t["is_short"]) for t in trades),
        "shorts":sum(bool(t["is_short"]) for t in trades),
        "zero_duration_trades":sum(a==b for a,b in periods),
        "time_in_position_hours":round(sum(b-a for a,b in periods)/3_600_000,3),
        "percent_time_in_position":round(100*sum(b-a for a,b in periods)/(end_ms-start_ms),3),
        "overlapping_global_positions":0
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start",required=True,help="UTC YYYY-MM-DD")
    p.add_argument("--end",required=True,help="UTC YYYY-MM-DD, exclusive")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--expected-fee-side",type=float,default=.0005)
    for key in STRATEGIES:
        p.add_argument("--"+key.replace("_","-"),dest=key,type=Path)
    args=p.parse_args()
    start_ms=timestamp_ms(args.start+"T00:00:00+00:00")
    end_ms=timestamp_ms(args.end+"T00:00:00+00:00")
    if not start_ms<end_ms:
        raise ValueError("Invalid date range")
    results={}
    for name,strat in STRATEGIES.items():
        path=getattr(args,name)
        if path is None:
            continue
        stats=archive_strategy(path,strat)
        if abs(float(stats.get("fee_open",args.expected_fee_side))-args.expected_fee_side)>1e-9:
            raise ValueError("Fee entry does not match comparator "+name)
        results[name]=examine(stats,name,start_ms,end_ms)
    if len(results)<2:
        raise ValueError("Provide >=2 real historical strategy archives")
    report={
        "window":[args.start,args.end],
        "source":"Official Freqtrade backtest-result ZIP archives",
        "simulation_only":True,
        "max_simultaneous_positions":1,
        "assumed_entry_and_exit_fee_side":args.expected_fee_side,
        "NO_TRADE":{"trades":0,"net_usdt":0.0},
        "strategies":results,
        "limitations":[
            "Different exit rules and model candidate universes mean profit differences are not purely attributable to AI.",
            "Original NbotV6 and non-ML use a different exit strategy than the new 60-minute after-cost models.",
            "Use trade-level periods, not directly summing overlapping training opportunities as PnL.",
            "Exchange actual bid/ask, slippage and stop fills are unverified and outcomes are simulated.",
            "One out-of-sample window is not proof of durable profitability.",
            "FreqAI lookahead indicator warnings and full training-boundary purge are NOT certified."
        ]
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print("COMPARISON",json.dumps({
        k:{"trades":v["trades"],"net_usdt":v["net_usdt"],"win_pct":v["win_pct"]}
        for k,v in results.items()
    }))
    print("REPORT",args.output)


if __name__=="__main__":
    main()
