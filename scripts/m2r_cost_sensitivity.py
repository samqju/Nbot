#!/usr/bin/env python3
"""After-cost extra execution sensitivity on actual Freqtrade trade ZIPs.

Hypothetical fixed-trade deductions: NOT real spread/slippage, not a new
backtest, and not indicative of how the bot's entry/exit path changes
when spreads and market impact are explicitly simulated.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from m2_funding_reconcile import archive_strategy

CASES=(0,5,10,11,15,20,25,50,100)  # EXTRA total roundtrip basis points


def sensitivity(stats: dict)->dict:
    trades=stats["trades"]
    notionals=[]
    for trade in trades:
        notional=float(trade["stake_amount"])*float(trade.get("leverage") or 1)
        if not 0<notional<100_000:
            raise ValueError("Unreasonable historical notional")
        notionals.append(notional)
    base=float(stats["profit_total_abs"])
    return {
        "trades":len(trades),
        "starting_net_usdt":round(base,3),
        "gross_stake_notional_sum_usdt":round(sum(notionals),3),
        "fixed_trade_scenario_adjusted_net_usdt":{
            str(bps):round(base-sum(notionals)*bps/10_000,3)
            for bps in CASES
        },
        "extra_roundtrip_cost_bps":list(CASES),
    }


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--combined",required=True,type=Path)
    p.add_argument("--breakout",type=Path)
    p.add_argument("--pullback",type=Path)
    p.add_argument("--original",type=Path)
    p.add_argument("--baseline",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    sources=(
        ("combined","NbotV6TradeOutcomeResearch"),
        ("breakout","NbotV6BreakoutResearch"),
        ("pullback","NbotV6PullbackResearch"),
        ("original","NbotV6"),
        ("baseline","NbotV6NoML"),
    )
    results={
        key:sensitivity(archive_strategy(getattr(args,key),strategy))
        for key,strategy in sources if getattr(args,key) is not None
    }
    if not results:
        raise ValueError("No official backtest archives")
    report={
        "method":"Freeze official already-completed trade paths, then subtract assumed ADDITIONAL roundtrip execution costs from each actual trade's stake x leverage.",
        "not_measured":True,
        "engine_initial_fee_side":0.0005,
        "notes":[
            "Never claim this estimates observed historical bid/ask or market impact.",
            "Freqtrade base fee and engine funding already reflected in starting net.",
            "A 10-basis-point EXTRA roundtrip haircut is about 1 USDT for a 1,000-USDT 1x trade.",
            "The after-cost learning labels already reserved a hypothetical 10bps roundtrip slippage plus 1bp funding; this extra-cost evaluation is an independent stress on engine accounting, not an added second model target.",
            "Fixed-trade stress does not replay exits, fill rejection, order timing or model switching.",
            "NO TRADE returns exactly zero and involves no trades."
        ],
        "NO_TRADE_USDT":0.0,
        "results":results,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v["fixed_trade_scenario_adjusted_net_usdt"] for k,v in results.items()}))
    print("REPORT",args.output)


if __name__=="__main__":
    main()
