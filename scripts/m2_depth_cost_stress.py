#!/usr/bin/env python3
"""M2 stress each fill using matched (or unavailable) public 30s depth data.

All execution costs here are illustrative assumptions in EXTRA bps per
entry/exit; NOT observed bid/ask spread or fill price. Orders, events and
model selections stay fixed. A missing/stale depth snapshot is never
treated as zero slippage. Uses actual per-event stake and base net P&L.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

# Per SIDE, not per roundtrip. Bps: 100 = 1% of position notional.
SCENARIOS = {
    "no_additional_cost": {"MATCH": 0, "UNVERIFIED": 0},
    "low": {"MATCH": 5, "UNVERIFIED": 25},
    "medium": {"MATCH": 10, "UNVERIFIED": 50},
    "severe": {"MATCH": 20, "UNVERIFIED": 100},
    "extreme": {"MATCH": 40, "UNVERIFIED": 200},
}
BASE_PNL = {"AI_V6": -135.640, "NO_ML": 169.849}

def calculate(report: dict) -> dict:
    if len(report["trade_events"]) != 65:
        raise ValueError("Expected exactly 65 historical trades")
    result = {}
    for name in BASE_PNL:
        subset = [x for x in report["trade_events"] if x["strategy"] == name]
        if not subset:
            raise ValueError(f"Missing {name} trades")
        scenario = {}
        for label, assumptions in SCENARIOS.items():
            cost = 0.0
            states = Counter()
            for trade in subset:
                stake = float(trade["stake_notional_usdt"])
                if not 0 < stake <= 2000:
                    raise ValueError("Unexpected stake_notional")
                for event in trade["sides"]:
                    state = event["state"]
                    states[state] += 1
                    surcharge = (assumptions["MATCH"] if state == "MATCH"
                                 else assumptions["UNVERIFIED"])
                    cost += stake * surcharge / 10_000
            scenario[label] = {
                "additional_cost_usdt": round(cost, 3),
                "adjusted_net_usdt": round(BASE_PNL[name] - cost, 3),
                "entry_exit_snapshot_quality": dict(states),
                "assumed_extra_bps_each_side": assumptions,
            }
        result[name] = {"trades": len(subset), "scenarios": scenario}
    return {
        "study":"M2 actual Binance 30s depth match + hypothetical fill penalty scenarios",
        "depth_data_quality": report["status_counts"],
        "fully_observed_top_of_book_bid_ask": False,
        "assumptions":[
            "The 'MATCH' label means a 30s depth snapshot <=45s old, and aggregate quote notional within 0.2% >= size.",
            "The match only screens liquidity and does NOT establish the spread, queue position, fill price or impact.",
            "Missing/stale snapshots receive a larger assumed incremental cost, not zero.",
            "Costs are additive to Freqtrade's base simulated 0.05% per side fee and historical funding.",
            "All hypothetical execution costs are charged on unchanged original trades, not a new order-level simulation.",
            "A single seven-day period is not enough to approve profit or strategy adaptation."
        ],
        "comparisons":result,
        "no_trade_pnl_usdt":0.0
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--depth",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=calculate(json.loads(args.depth.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    for name,r in report["comparisons"].items():
        print(name,{k:v["adjusted_net_usdt"] for k,v in r["scenarios"].items()})
    print("REPORT",args.output)


if __name__=="__main__":
    main()
