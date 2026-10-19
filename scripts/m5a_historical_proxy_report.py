#!/usr/bin/env python3
"""Summarize a verified historical M5A sampled-universe OHLCV proxy replay.

NOT executable 25x8 Freqtrade PnL and NOT proof of valid historic spreads,
funding or model readiness; 24h labels from 8h reviews overlap in future.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

def formatted_rate(a):
    return "n/a" if a is None else f"{a:.1%}"

def result_text(data:dict)->str:
    if data.get("schema")!="m5a-historical-8h-ohlcv-proxy-replay-1":
        raise ValueError("UNVERIFIED_REPLAY_SCHEMA")
    lines=[
       "# Nbot V6 — Historical universe OHLCV proxy replay",
       "",
       f"**{data['reviews']}** eight-hour reviews using historical closed hourly candles of "
       f"**{data['sampled_current_symbols']}** candidate symbols.",
       "",
       "**LIMITATIONS:** Current-market October 19 candidate sampling introduces historical survivorship bias. "
       "No historic Binance order-book spread/depth, funding, contract listing status, freshly "
       "validated per-coin models, the original eight strategy entries or real Freqtrade native execution "
       "is present. The simple momentum first-touch labels overlap within 24h and cannot be "
       "summed into one-slot account P&L. No auto-trading or model activation.",
       "",
       "| Universe | Reviews | Coin swaps | Avg. public OHLCV quality proxy | +2% before −2% stop | +3% before −2% stop |",
       "|---|---:|---:|---:|---:|---:|"
    ]
    def row(name,stats):
        a=stats["target2"];b=stats["target3"]
        lines.append(f"| {name} | {stats['reviews']} | {stats['total_virtual_coin_rotations']} | "
                     f"{stats['mean_public_ohlcv_quality_proxy']:.4f} | "
                     f"{a['target_before_stop']}/{a['signals']} ({formatted_rate(a['target_first_rate_on_signals'])}) | "
                     f"{b['target_before_stop']}/{b['signals']} ({formatted_rate(b['target_first_rate_on_signals'])}) |")
    for k,v in data["summary_all"].items():row(k,v)
    for month,stats in data["summary_by_month"].items():
        lines.extend(["",f"## {month}","",
                      "| Universe | Reviews | Swaps | Avg. OHLCV quality proxy | +2% first | +3% first |",
                      "|---|---:|---:|---:|---:|---:|"])
        for k,v in stats.items():row(k,v)
    lines.extend(["","## Interpretation","",
      "The selector may improve the chosen historical quality metric without improving actual "
      "trade profits. Conditional hit rates are diagnostic, not executable returns. "
      "Before concluding alpha, verify exchange point-in-time universe membership and "
      "replay same coin/strategy/side/exit native Freqtrade portfolios on new untouched dates."])
    return "\n".join(lines)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--replay",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise SystemExit("REFUSE_OVERWRITE_REPORT")
    raw=json.loads(a.replay.read_text())
    md=result_text(raw)
    a.out.write_text(md)
    print(md)
if __name__=="__main__":
    main()
