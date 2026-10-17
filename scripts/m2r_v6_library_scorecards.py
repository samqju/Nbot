"""Derive regime-specific candidate evidence from REAL native Freqtrade ZIP trades.

Historical regime at each executed trade uses the LAST COMPLETED 5m candle,
never data available after the trade's entry. This tool cannot manufacture
trade wins from hypothetical future opportunity labels. It audits native
strategy/25 coins/one-slot/fees and produces *review-only* scorecards.

Independent native Freqtrade lookahead and fill-cost certification are not
obtained by this extractor. Blocks from this tool deliberately set
decision_boundary_passed=False and MUST NOT be fed to the live selector.
After external immutable lookahead, model-purge and cost certification,
separate review can build a scorecard manifest; no auto-promotion.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from m2r_v6_library_native_job import CANDIDATES
from m2r_strategy_library_selector import CandidateBlock, parse_utc

EXPECTED_V6_PAIRS=25

def asof_regime_on_candles(frame:pd.DataFrame) -> pd.Series:
    close=frame["close"]
    ema20=close.ewm(span=20, adjust=False, min_periods=20).mean()
    ema50=close.ewm(span=50, adjust=False, min_periods=50).mean()
    prior=close.shift(1)
    tr=pd.concat([(frame["high"]-frame["low"]),
                  (frame["high"]-prior).abs(),
                  (frame["low"]-prior).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    vol=atr / close
    baseline=vol.shift(1).rolling(96,min_periods=96).median()
    trend=ema20/ema50-1
    out=pd.Series("range",index=frame.index,dtype=object)
    up=(trend>0.0015) & (ema50>ema50.shift(6))
    down=(trend< -0.0015) & (ema50<ema50.shift(6))
    high=(vol>baseline*2.0)&(vol>0.012)
    out.loc[up]="trend_up"
    out.loc[down]="trend_down"
    out.loc[high]="high_volatility"
    out.loc[baseline.isna() | trend.isna()]="high_volatility"
    return out

def native_archive(path:Path,strategy:str):
    with ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError("ZIP_CRC_FAILED")
        names=[x for x in z.namelist()
               if x.endswith(".json") and not x.endswith("_config.json")]
        if len(names)!=1:
            raise ValueError("EXPECTED_SINGLE_NATIVE_FT_STRATEGY_JSON")
        v=json.loads(z.read(names[0]))
    if set(v.get("strategy",{}))!={strategy}:
        raise ValueError("UNEXPECTED_FT_NATIVE_STRATEGY")
    stats=v["strategy"][strategy]
    if not (stats.get("trading_mode")=="futures"
            and stats.get("timeframe")=="5m"
            and stats.get("max_open_trades")==1
            and abs(float(stats.get("stake_amount",0))-1000)<1e-7
            and abs(float(stats.get("starting_balance",0))-100000)<1e-7
            and len(stats.get("pairlist",[]))==EXPECTED_V6_PAIRS):
        raise ValueError("NATIVE_PORTFOLIO_ENVELOPE_MISMATCH")
    trades=stats["trades"]
    if stats["total_trades"]!=len(trades):
        raise ValueError("NATIVE_TRADE_COUNT_MISMATCH")
    if abs(sum(float(t["profit_abs"]) for t in trades)
           -float(stats["profit_total_abs"]))>0.001:
        raise ValueError("NATIVE_TRADE_PROFIT_SUM_MISMATCH")
    for t in trades:
        if abs(float(t["fee_open"])-.0005)>1e-12 or abs(float(t["fee_close"])-.0005)>1e-12:
            raise ValueError("NATIVE_FEE_MISMATCH")
        if abs(float(t["leverage"])-1)>1e-9 or not 900<=float(t["stake_amount"])<=1100:
            raise ValueError("NATIVE_STAKE_OR_LEVERAGE_OUT_OF_POLICY")
        if t["pair"] not in stats["pairlist"]:
            raise ValueError("UNEXPECTED_PAIR_IN_TRADE")
    return stats

def build_regime_blocks(
    *, archive:Path, family:str, history:Path, training_ended:str,
    extra_roundtrip_bps:int=25
) -> dict:
    if family not in CANDIDATES:
        raise ValueError("CANDIDATE_NOT_IN_FROZEN_LIBRARY")
    if extra_roundtrip_bps<25 or extra_roundtrip_bps>100:
        raise ValueError("AT_LEAST_25BP_HYPOTHETICAL_FILL_STRESS_REQUIRED")
    strategy=CANDIDATES[family][0]
    stats=native_archive(archive,strategy)
    start=parse_utc(stats["backtest_start"].replace(" ","T")+"Z")
    end=parse_utc(stats["backtest_end"].replace(" ","T")+"Z")
    trained=parse_utc(training_ended)
    if not trained<start<end:
        raise ValueError("TUNING_MUST_END_BEFORE_OOS_START")
    if (end-start).days>65:
        raise ValueError("ONE_BLOCK_MUST_NOT_COVER_MULTIPLE_MONTHS")
    native_sha=hashlib.sha256(archive.read_bytes()).hexdigest()
    feeds={}
    history_sha=hashlib.sha256()
    for pair in sorted(stats["pairlist"]):
        token=pair.replace("/","_").replace(":","_")
        source=history/(token+"-5m-futures.feather")
        if not source.is_file():
            raise RuntimeError("REQUIRED_5M_NATIVE_PRICE_HISTORY_NOT_FOUND "+pair)
        content=source.read_bytes()
        history_sha.update(pair.encode()+b"\x00"+hashlib.sha256(content).digest())
        data=pd.read_feather(source)
        data["date"]=pd.to_datetime(data["date"],utc=True)
        if (data["date"].duplicated().any() or not data["date"].is_monotonic_increasing
            or not (data["close"]>0).all()
            or not (data["volume"]>=0).all()):
            raise RuntimeError("INVALID_ASOF_PAIR_HISTORY "+pair)
        data=data.set_index("date")
        feeds[pair]=asof_regime_on_candles(data)
    history_fingerprint=history_sha.hexdigest()
    groups=defaultdict(list)
    for t in stats["trades"]:
        opened=parse_utc(str(t["open_date"]).replace(" ","T")+"Z")
        closed=parse_utc(str(t["close_date"]).replace(" ","T")+"Z")
        if not start<=opened<end or not opened<closed<=end+timedelta(minutes=5):
            raise ValueError("TRADE_OUTSIDE_FROZEN_NATIVE_BLOCK")
        if opened.minute%5 or opened.second or opened.microsecond:
            raise ValueError("INVALID_5M_TRADE_ENTRY_TIME")
        decision=pd.Timestamp(opened-timedelta(minutes=5))
        # Critical causality: Freqtrade entry at next-open uses the immediately
        # prior CLOSED 5m candle only. Never infer regimes from exit time.
        regime=feeds[t["pair"]].get(decision)
        if regime is None:
            raise RuntimeError("REQUIRES_ASOF_DECISION_CANDLE "+t["pair"])
        groups[regime].append(t)
    blocks=[]
    for regime,orders in sorted(groups.items()):
        closed=sorted(orders,key=lambda x:x["close_date"])
        equity=100000.
        peak=equity
        max_dd=0.
        for t in closed:
            equity+=float(t["profit_abs"])
            peak=max(peak,equity)
            max_dd=max(max_dd, (peak-equity)/peak)
        pnl=sum(float(t["profit_abs"]) for t in closed)
        turnover=sum(float(t["stake_amount"]) for t in closed)
        stressed=pnl-extra_roundtrip_bps*turnover/10000.
        block=CandidateBlock(
            family=family,regime=regime,
            evaluated_from=start.isoformat(),
            evaluated_until=end.isoformat(),
            model_trained_until=trained.isoformat(),
            native_zip_sha256=native_sha,market_history_sha256=history_fingerprint,
            trade_count=len(closed),pnl_net_usdt=round(pnl,6),
            stressed_net_usdt=round(stressed,6),
            max_drawdown_fraction=round(max_dd,8),
            native_audit_passed=True,
            decision_boundary_passed=False,
        )
        blocks.append(dict(block.__dict__))
    return {
        "schema":"nbot-v6-candidate-native-regime-review-v1",
        "candidate":family,
        "native_strategy":strategy,
        "original_native_zip_sha256":native_sha,
        "entire_pair_history_sha256":history_fingerprint,
        "source_native_trades":stats["total_trades"],
        "actual_fee_each_side":.0005,
        "additional_hypothetical_roundtrip_bps":extra_roundtrip_bps,
        "oos_start":start.isoformat(),
        "oos_end_exclusive":end.isoformat(),
        "model_or_parameters_train_ended":trained.isoformat(),
        "blocks":blocks,
        "native_engine_historical_fill_and_fee_logic_used":True,
        "real_order_book_and_stop_fills_observed":False,
        "independent_native_lookahead_and_retraining_splits_certified":False,
        "scorecard_selector_ready":False,
        "note":"Review-only evidence: decision_boundary_passed False until separate native lookahead/model-integrity verification. Do not copy these records into a selector manifest without that certification.",
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--zip",required=True,type=Path)
    p.add_argument("--family",required=True,choices=sorted(CANDIDATES))
    p.add_argument("--history",required=True,type=Path)
    p.add_argument("--training-ended",required=True,help="Strict UTC ISO date/time of frozen model/Hyperopt training cutoff")
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--extra-cost-bps",type=int,default=25)
    a=p.parse_args()
    out=build_regime_blocks(archive=a.zip,family=a.family,history=a.history,
                            training_ended=a.training_ended,extra_roundtrip_bps=a.extra_cost_bps)
    if a.output.exists():
        raise RuntimeError("DO_NOT_OVERWRITE_PREVIOUS_AUDIT")
    a.output.write_text(json.dumps(out,indent=2)+"\n")
    print("REVIEW_ONLY_NATIVE_REGIME_SCORECARDS",a.family,
          "trades",out["source_native_trades"],
          "groups",[(b["regime"],b["trade_count"],b["stressed_net_usdt"]) for b in out["blocks"]],
          "SELECTOR_READY",False)

if __name__=="__main__":
    main()
