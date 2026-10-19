#!/usr/bin/env python3
"""Read-only: inspect original Freqtrade entry/exit evidence for +2% trailing.

Reads saved ZIP files only; never models hypothetical fills, places orders,
changes trade selection, or changes any research state.
"""
from __future__ import annotations
import collections
import glob
import json
from pathlib import Path
from zipfile import ZipFile

BASE=Path("/root/nbot-v6-m1-20261016/library-20261018")
FAMILIES=("ema_cross","donchian_breakout","bollinger_reversion","rsi_reversion",
          "macd_momentum","stochastic_reversal","atr_breakout","volume_trend")
PERIODS=("validation_july","replication_august","replication_september")

def trades(kind,family,period):
    paths=list((BASE/kind/family/period/"backtest_results").glob("*.zip"))
    if len(paths)!=1:raise RuntimeError("REQUIRE_EXACT_ONE_NATIVE_ZIP")
    with ZipFile(paths[0]) as z:
        if z.testzip() is not None:raise RuntimeError("CORRUPT_NATIVE_ARCHIVE")
        names=[x for x in z.namelist() if x.endswith(".json") and not x.endswith("_config.json")]
        if len(names)!=1:raise RuntimeError("AMBIGUOUS_NATIVE_ZIP")
        data=json.loads(z.read(names[0]))
    values=list(data["strategy"].values())
    if len(values)!=1:raise RuntimeError("REQUIRE_ONE_NATIVE_STRATEGY")
    return values[0]["trades"]

result={}
for kind in ("native","trailing"):
    total=0; reasons=collections.Counter(); samples=[]; profitable=0; loss=0; pnl_by_reason=collections.defaultdict(list)
    max_favorable_measured=collections.Counter()
    for family in FAMILIES:
        exits=collections.Counter()
        for month in PERIODS:
            for t in trades(kind,family,month):
                total+=1
                profit=float(t["profit_abs"])
                profitable+=profit>0
                loss+=profit<0
                reason=str(t.get("exit_reason","UNKNOWN"))
                reasons[reason]+=1
                pnl_by_reason[reason].append(profit)
                exits[reason]+=1
                if not samples:samples.append({k:t.get(k) for k in ("open_rate","max_rate","min_rate","close_rate","exit_reason","is_short","profit_ratio","profit_abs","open_date","close_date")})
                if t.get("max_rate") is not None and t.get("min_rate") is not None:
                    enter=float(t["open_rate"])
                    favorable=((enter-float(t["min_rate"]))/enter if t["is_short"]
                               else (float(t["max_rate"])-enter)/enter)
                    for pct in (1,2,3,5):
                        if favorable>=pct/100:
                            max_favorable_measured[str(pct)]+=1
        print(kind,family,"count",sum(exits.values()),"exit_reasons",json.dumps(exits),flush=True)
    result[kind]={
        "total_trades":total,
        "winning_trades":profitable,
        "losing_trades":loss,
        "exit_reasons":dict(reasons),
        "pnl_summary_by_exit_reason":{reason:{"trades":len(nums),"winning_exits":sum(n>0 for n in nums),"losing_exits":sum(n<0 for n in nums),"native_net_usdt":round(sum(nums),2)} for reason,nums in pnl_by_reason.items()},
        "recorded_max_favorable_gross_1_2_3_5pct_counts":dict(max_favorable_measured),
        "recorded_max_favorable_is_not_safe_intra_candle_order":True,
        "sample_trade":samples[0] if samples else None}
print("SUMMARY",json.dumps(result,sort_keys=True,indent=2),flush=True)
