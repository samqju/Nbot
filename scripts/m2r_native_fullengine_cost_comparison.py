"""V6-only retrospective two-day engine controls + break-even slippage stress.

All numbers derive from actual OFFLINE Freqtrade historical backtest trade
archives, not hypothetical overlapping opportunity table. Extra charges
are what-if deductions on frozen trades, NOT real bid/ask fills or retrained
decisions. NO strategy selection from 2 days.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from zipfile import ZipFile

CHARGE_EXTRA_ROUNDTRIP_BPS=(0,5,10,15,20,25,50)


def source(path:Path,name:str):
    with ZipFile(path) as z:
        data=[n for n in z.namelist() if n.endswith(".json")
              and not n.endswith("_config.json") and not n.endswith(".meta.json")]
        if len(data)!=1:
            raise RuntimeError("INCOMPATIBLE_ENGINE_RESULT_ZIP")
        v=json.loads(z.read(data[0]))
        d=v["strategy"][name]
        return d


def research_score(stats):
    trades=stats["trades"]
    stakes=[float(t["stake_amount"])*float(t.get("leverage") or 1) for t in trades]
    if any(not 0<n<100000 for n in stakes):
        raise RuntimeError("INVALID_STAKES")
    pnl=float(stats["profit_total_abs"])
    t=sum(stakes)
    return {
        "trades":len(trades),
        "closed_trade_engine_pnl_usdt":round(pnl,6),
        "sum_levered_stakes_usdt":round(t,6),
        "wins":sum(float(t["profit_abs"])>0 for t in trades),
        "after_EXTRA_roundtrip_execution_cost_usdt":{
            str(bp):round(pnl-t*bp/10000,6) for bp in CHARGE_EXTRA_ROUNDTRIP_BPS
        },
        "break_even_additional_roundtrip_bps_if_initially_positive":
            round(pnl/t*10000,4) if t>0 and pnl>0 else None,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--unpurged-original",type=Path,required=True)
    p.add_argument("--purged-original",type=Path,required=True)
    p.add_argument("--funding-aware-purged",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    variants={
        "original_native_unpurged":research_score(source(a.unpurged_original,"NbotV6")),
        "original_native_12candle_internal_purged":research_score(source(a.purged_original,"NbotV6")),
        "experimental_event_funding_target_internal_purged":research_score(
            source(a.funding_aware_purged,"NbotV6TradeOutcomeFundingResearch")),
        "NO_TRADE":{"trades":0,"closed_trade_engine_pnl_usdt":0},
    }
    r={"scope":"Only Oct 8-9 UTC, 2026, originally reviewed region; full engine 25 pairs, global 1x 1000 stake, one position, Binance futures 0.05pct fee per side",
       "assume_equal_research_windows":True,
       "interpretation":"Limited in-sample short retrospective score of research variants ONLY. No valid model-selection conclusion or blind-period economic evidence.",
       "extra_slippage_is_hypothetical":True,
       "observed_bid_ask_spreads":False,"observed_stop_market_fills":False,
       "no_trade_usdt":0,
       "M2_RELEASE":"NO-GO",
       "variants":variants}
    a.output.write_text(json.dumps(r,indent=2)+"\n")
    for k,v in variants.items():
        print(k,v["trades"],v["closed_trade_engine_pnl_usdt"],flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
