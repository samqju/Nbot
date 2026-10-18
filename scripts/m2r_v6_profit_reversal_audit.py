#!/usr/bin/env python3
"""Read-only, conservative MAE/MFE diagnostic for REAL saved Freqtrade ZIP trades.

For trades that ended at a loss, estimate whether the market had already
touched a +1%, +2% or +3% favorable price on a FULLY COMPLETED 5-minute candle
BEFORE the actual trade exit candle. This is not a synthetic trade or an
executable price quote; in-candle sequence / spreads / stop fills are unknown.

This script never creates strategy entries, never submits orders, and never
promotes a model. It requires an untouched native ZIP and original 25-pair
public 5m archive.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import hashlib,json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

LEVELS=(0.01,0.02,0.03)

def read_trades(archive:Path):
    with ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError("CORRUPTED_ORIGINAL_NATIVE_ARCHIVE")
        candidates=[n for n in z.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        if len(candidates)!=1:
            raise RuntimeError("AMBIGUOUS_NATIVE_ZIP")
        v=json.loads(z.read(candidates[0]))
    if len(v.get("strategy",{}))!=1:
        raise RuntimeError("REQUIRE_EXACT_ONE_NATIVE_STRATEGY")
    name,strategy=next(iter(v["strategy"].items()))
    if (len(strategy.get("pairlist",[]))!=25 or
        strategy.get("max_open_trades")!=1 or
        strategy.get("timeframe")!="5m" or
        strategy.get("trading_mode")!="futures" or
        len(strategy.get("trades",[]))!=strategy.get("total_trades")):
        raise RuntimeError("NATIVE_RISK_DATA_ENVELOPE_UNEXPECTED")
    trades=strategy["trades"]
    for t in trades:
        if (abs(float(t["fee_open"])-.0005)>1e-9 or
            abs(float(t["fee_close"])-.0005)>1e-9 or
            abs(float(t["leverage"])-1)>1e-9 or
            t["pair"] not in strategy["pairlist"]):
            raise RuntimeError("TRADE_NOT_IN_HISTORICAL_STUDY")
    return name,strategy,trades

def report(archive:Path,history:Path):
    name,portfolio,trades=read_trades(archive)
    grouped=defaultdict(list)
    for trade in trades:
        grouped[trade["pair"]].append(trade)
    counts=Counter()
    missing=[]
    exits=Counter()
    detailed=[]
    for pair,orders in sorted(grouped.items()):
        feather=history/(pair.replace("/","_").replace(":","_")+"-5m-futures.feather")
        if not feather.is_file():
            raise RuntimeError("MISSING_VERIFIED_5M_PAIR_FEATHER:"+pair)
        bars=pd.read_feather(feather,columns=["date","open","high","low","close"])
        bars["date"]=pd.to_datetime(bars["date"],utc=True)
        if bars["date"].isna().any() or not bars["date"].is_monotonic_increasing:
            raise RuntimeError("INVALID_5M_CHRONOLOGICAL_BARS")
        if bars["date"].duplicated().any():
            raise RuntimeError("DUPLICATE_ASOF_BARS")
        bars=bars.set_index("date")
        for t in orders:
            counts["native_total_trades"]+=1
            pnl=float(t["profit_abs"])
            if pnl>=0:
                counts["native_nonloss_trades"]+=1
                continue
            counts["native_loss_trades"]+=1
            exits[t.get("exit_reason","UNKNOWN")]+=1
            entry=pd.Timestamp(t["open_date"]).tz_convert("UTC")
            exit_dt=pd.Timestamp(t["close_date"]).tz_convert("UTC")
            if not entry<exit_dt:
                raise RuntimeError("REVERSE_DATE_IN_NATIVE_TRADE")
            # Exclude the native EXIT candle entirely so an intrabar
            # stop-vs-high ambiguity on the exit candle is not labeled as an
            # earlier recoverable profit. This undercounts opportunities.
            prior=bars.loc[(bars.index>=entry)&(bars.index<exit_dt)]
            if len(prior)==0:
                counts["losses_without_pre_exit_complete_candle"]+=1
                continue
            # Require uninterrupted closed five-minute candle timestamps for
            # trustworthy path classification, otherwise mark inconclusive.
            if (prior.index[0]!=entry or
                (prior.index.to_series().diff().dropna()!=pd.Timedelta(minutes=5)).any() or
                pd.isna(prior["high"]).any() or pd.isna(prior["low"]).any()):
                counts["losses_unverifiable_missing_path_history"]+=1
                missing.append({"pair":pair,"open":str(entry),"close":str(exit_dt)})
                continue
            entry_rate=float(t["open_rate"])
            if not entry_rate>0:raise RuntimeError("INVALID_ENTRY_PRICE")
            favorable=(entry_rate/prior["low"].min()-1) if t["is_short"] else (prior["high"].max()/entry_rate-1)
            # 1x unrealized favorable movement before modeled fees.
            # For short, (entry-low)/entry is consistent with short return
            # definition at 1x, unlike entry/low-1.
            if t["is_short"]:
                favorable=(entry_rate-float(prior["low"].min()))/entry_rate
            counts["losses_with_complete_pre_exit_path"]+=1
            for cutoff in LEVELS:
                if favorable>=cutoff:
                    counts[f"losses_had_reached_{int(cutoff*100)}pct_before_exit"]+=1
            detailed.append({
                "pair":pair,"open_utc":entry.isoformat(),
                "exit_utc":exit_dt.isoformat(),"short":bool(t["is_short"]),
                "actual_native_loss_usdt":round(pnl,6),
                "max_prior_complete_5m_candle_favorable_gross_pct":round(favorable*100,4),
                "exit_reason":t.get("exit_reason","UNKNOWN"),
                "evidence_is_not_realizable_exit":True
            })
    return {
        "schema":"nbot-v6-conservative-prior-candle-loss-retracement-audit-v1",
        "native_strategy":name,
        "original_native_zip_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
        "study_native_net_usdt":portfolio.get("profit_total_abs"),
        "thresholds_are_price_gross_before_fee_or_slippage":True,
        "only_candles_fully_before_native_exit_candle":True,
        "intra_candle_execution_order_unknown":True,
        "no_counterfactual_profit_or_execution_claim":True,
        "does_not_imply_trailing_stop_always_improves_net_portfolio":True,
        "counts":dict(counts),"loss_exit_reason_counts":dict(exits),
        "uncertain_because_ohlcv_gaps":missing,
        "losing_trades_with_prior_path":detailed
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--zip",required=True,type=Path)
    ap.add_argument("--history",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    if args.out.exists():
        raise RuntimeError("REFUSE_OVERWRITE_NATIVE_EVIDENCE")
    result=report(args.zip,args.history)
    args.out.write_text(json.dumps(result,indent=2)+"\n")
    print("HISTORICAL_NATIVE_LOSS_PATH_ANALYSIS_ONLY",json.dumps(result["counts"],sort_keys=True),flush=True)

if __name__=="__main__":
    main()
