#!/usr/bin/env python3
"""Read-only, reproducible Stage 1 economic summary of saved native audits.

Aggregates ONLY actual Freqtrade portfolio ZIP audited result rows and
completed recovery job receipts. Each month/family is a separate backtest.
Never treats tuned hyperparameters or classifiers as profitable strategies.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import json

DEFAULT_ROOT=Path("/root/nbot-v6-m1-20261016")
FAMILIES=("ema_cross","donchian_breakout","bollinger_reversion","rsi_reversion",
          "macd_momentum","stochastic_reversal","atr_breakout","volume_trend")
MONTHS=("validation_july","replication_august","replication_september")
KINDS=("native","trailing")
STUDIES=(("native","frozen_native_results",24),
         ("trailing","trailing_stops_ab_results",24),
         ("baseline","original_breakout_pullback_no_ml_baselines",3))

def json_file(path):
    return json.loads(path.read_text())

def sha256(path):
    dig=hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda:inp.read(4*1024*1024),b""):
            dig.update(block)
    return dig.hexdigest()

def verify_row(base, row, kind):
    required=("kind","family","period","archive_name","native_zip_sha256",
              "native_profit_usdt","net_after_extra_25bps_usdt",
              "native_trade_count","wins")
    if any(k not in row for k in required):
        raise RuntimeError("MISSING_NATIVE_ECONOMIC_AUDIT_COLUMN")
    if row["kind"]!=kind or row["trade_count_and_native_cost_audit_passed"] is not True:
        raise RuntimeError("UNVERIFIED_ECONOMIC_RESULT")
    archive=base/row["kind"]/row["family"]/row["period"]/"backtest_results"/row["archive_name"]
    if not archive.is_file() or sha256(archive)!=row["native_zip_sha256"]:
        raise RuntimeError("MISSING_OR_MUTATED_NATIVE_ARCHIVE "+str(archive))
    if row["native_trade_count"]<0 or row["wins"]<0 or row["wins"]>row["native_trade_count"]:
        raise RuntimeError("INVALID_NATIVE_TRADE_COUNTS")
    return row

def summarize(root):
    lib=root/"library-20261018"
    recovery=root/"library-20261018-recovery"
    d=json_file(lib/"candidate-native-aftercost-summary.json")
    done=json_file(recovery/"verified-all-seven-and-original-56.json")
    state=json_file(recovery/"recovery-progress.json")
    if (state.get("status")!="finished" or state.get("completed")!=7 or state.get("failed")!=0
        or not done.get("all_recovered_native_audits_passed")
        or len(done.get("recovered_jobs",[]))!=7):
        raise RuntimeError("STAGE_1_RECOVERY_NOT_FULLY_AUDITED")
    rows={}
    for kind,key,total in STUDIES:
        batch=d.get(key,[])
        if len(batch)!=total:raise RuntimeError("INCOMPLETE_ORIGINAL_STAGE1_"+kind)
        selected={}
        for r in batch:
            verify_row(lib,r,kind)
            k=(r["family"],r["period"])
            if k in selected:raise RuntimeError("DUPLICATE_NATIVE_AUDIT")
            selected[k]=r
        rows[kind]=selected
    for kind in KINDS:
        if set(rows[kind])!={(f,m) for f in FAMILIES for m in MONTHS}:
            raise RuntimeError("INCOMPLETE_EIGHT_FAMILIES_THREE_MONTHS_"+kind)
    summary={
        "schema":"nbot-v6-stage1-readonly-audited-summary-v1",
        "source_stage1_status":json_file(lib/"v6-library-research-status.json")["status"],
        "recovery_status":state["status"],
        "jobs_total":63,
        "jobs_finished":63,
        "frozen_51_native_archives_verified":True,
        "recovery_job_names":done["recovered_jobs"],
        "economics":{},
        "monthly":{},
        "baseline":[],
        "no_trade_reference_usdt":0,
        "native_fee_each_side_fraction":.0005,
        "additional_cost_stress_round_trip_bps":25,
        "historical_periods_previously_inspected":True,
        "model_profits_future_unproven":True,
    }
    for m in MONTHS:
        r=rows["baseline"][("ema_cross",m)]
        summary["baseline"].append({
            "month":m,"native_profit_usdt":r["native_profit_usdt"],
            "stressed_profit_usdt":r["net_after_extra_25bps_usdt"],
            "trades":r["native_trade_count"]})
    for kind in KINDS:
        summary["economics"][kind]=[]
        good_count=0
        sum_native=sum_stressed=sum_trades=0
        for f in FAMILIES:
            mm=[rows[kind][(f,m)] for m in MONTHS]
            native=round(sum(x["native_profit_usdt"] for x in mm),2)
            stressed=round(sum(x["net_after_extra_25bps_usdt"] for x in mm),2)
            trades=sum(x["native_trade_count"] for x in mm)
            wins=sum(x["wins"] for x in mm)
            item={
                "family":f,"native_profit_3mo_usdt":native,
                "stress_25bp_profit_3mo_usdt":stressed,
                "trades_3mo":trades,"winning_trades":wins,
                "win_rate_pct":round(wins/trades*100,2) if trades else None,
                "monthly_stress":[round(x["net_after_extra_25bps_usdt"],2) for x in mm],
                "monthly_native":[round(x["native_profit_usdt"],2) for x in mm]}
            summary["economics"][kind].append(item)
            good_count+=stressed>0
            sum_native+=native
            sum_stressed+=stressed
            sum_trades+=trades
        summary["monthly"][kind]={
            "positive_stress_3mo_family_count":good_count,
            "sum_native_standalone_family_months":round(sum_native,2),
            "sum_stressed_standalone_family_months":round(sum_stressed,2),
            "sum_trades_standalone_family_months":sum_trades,
            "NOT_a_realisable_combined_portfolio":True}
    return summary

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    args=ap.parse_args()
    print(json.dumps(summarize(args.root),indent=2,sort_keys=True))

if __name__=="__main__":main()
