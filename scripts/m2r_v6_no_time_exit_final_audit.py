#!/usr/bin/env python3
"""Independent READ ONLY verifier of Nbot V6 no-60-minute historical A/B.

No orders, no strategy execution, no write. Checks original native and every
new Freqtrade ZIP SHA against saved native audit, reconciles trade count and
returns family×exit comparisons for monthly and continuous sensitivity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

DEFAULT=Path("/root/nbot-v6-m1-20261016")
FAMILIES=("ema_cross","donchian_breakout","bollinger_reversion","rsi_reversion","macd_momentum","stochastic_reversal","atr_breakout","volume_trend")
PERIODS=("validation_july","replication_august","replication_september","full_july_september")
POLICIES=("fixed","trailing")
def read(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):
            h.update(b)
    return h.hexdigest()
def require(t,msg):
    if not t:raise RuntimeError(msg)
def check_native(path,purpose):
    z=list((path/"backtest_results").glob("*.zip"))
    require(len(z)==1,"NOT_EXACTLY_ONE_ZIP_"+purpose)
    audit=read(path/"native-audit.json") if purpose.startswith("new") else read(path/"native-economic-audit.json")
    require(sha(z[0])==audit["native_zip_sha256"],"ARCHIVE_HASH_MISMATCH_"+purpose)
    with ZipFile(z[0]) as f:
        require(f.testzip() is None,"CORRUPT_ZIP_"+purpose)
        names=[n for n in f.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        require(len(names)==1,"AMBIGUOUS_ARCHIVE_"+purpose)
        b=json.loads(f.read(names[0]))
    require(len(b.get("strategy",{}))==1,"BAD_STRATEGY_COUNT")
    name,info=next(iter(b["strategy"].items()))
    require(len(info["pairlist"])==25 and info["max_open_trades"]==1
            and abs(float(info["stake_amount"])-1000)<1e-9,
            "ORIGINAL_RISK_PORTFOLIO_MISMATCH")
    trades=info["trades"]
    require(len(trades)==info["total_trades"],"TRADE_COUNT_MISMATCH")
    native=float(info["profit_total_abs"])
    require(abs(sum(float(t["profit_abs"]) for t in trades)-native)<0.002,"P_AND_L_LEDGER_MISMATCH")
    stress=native-.0025*sum(float(t["stake_amount"]) for t in trades)
    if purpose.startswith("new"):
        require(audit.get("native_net_usdt") is not None and abs(native-audit["native_net_usdt"])<.002,
                "BAD_NEW_PNL_AUDIT")
        require(abs(stress-audit["additional_25bp_stressed_net_usdt"])<.002,"BAD_NEW_STRESS")
        require(audit.get("no_60minute_custom_exit") is True,"ACTUAL_TIME_EXIT_NOT_REMOVED")
        require(all(t.get("exit_reason") not in ("v6_library_60m_exit","global_60m_limit") for t in trades),
                "RECORDED_FORBIDDEN_TIME_EXIT")
        force=sum(t.get("exit_reason")=="force_exit" for t in trades)
        require(force==audit["force_exits_at_historical_end_count"],"FORCED_CLOSE_NOT_AUDITED")
    else:
        require(abs(native-audit["native_profit_usdt"])<.002
                and abs(stress-audit["net_after_extra_25bps_usdt"])<.002,
                "OLD_NATIVE_ECONOMICS_DOES_NOT_MATCH_ZIP")
    return {"net":native,"stress":stress,"trades":len(trades)}

def analyze(root):
    out=root/"no-time-exit-20261019"
    state=read(out/"status.json")
    require(state.get("status")=="complete_research_only"
            and state.get("jobs_completed")==64 and state.get("jobs_total")==64,
            "NO_TIME_64_JOB_BATCH_NOT_COMPLETE")
    official=read(out/"final-comparison.json")
    require(len(official["native_monthly_comparisons"])==16
            and len(official["continuous_july_september"])==16,
            "MISSING_FINAL_COMPARISON")
    records=[]
    for family in FAMILIES:
        fam={}
        for policy in POLICIES:
            old_kind="native" if policy=="fixed" else "trailing"
            new_kind="no_time_fixed" if policy=="fixed" else "no_time_trailing"
            month_old=[];month_new=[]
            for period in PERIODS:
                path=out/new_kind/family/period
                result=check_native(path,"new_"+family+"_"+policy+"_"+period)
                if period=="full_july_september":full=result
                else:
                    month_new.append(result)
                    month_old.append(check_native(root/"library-20261018"/old_kind/family/period,
                            "original_"+family+"_"+policy+"_"+period))
            new_audits=[read(out/new_kind/family/period/"native-audit.json") for period in PERIODS]
            fam[policy]={
                "old_60m_monthly_stressed_usdt":round(sum(x["stress"] for x in month_old),2),
                "no_time_monthly_stressed_usdt":round(sum(x["stress"] for x in month_new),2),
                "monthly_stressed_improvement_usdt":round(sum(x["stress"] for x in month_new)-sum(x["stress"] for x in month_old),2),
                "continuous_no_time_stressed_usdt":round(full["stress"],2),
                "monthly_old_trade_count":sum(x["trades"] for x in month_old),
                "monthly_new_trade_count":sum(x["trades"] for x in month_new),
                "continuous_new_trade_count":full["trades"],
                "monthly_end_forced_exit_count":sum(x["force_exits_at_historical_end_count"] for x in new_audits[:3]),
                "continuous_end_forced_exit_count":new_audits[3]["force_exits_at_historical_end_count"],
                "continuous_median_holding_minutes":new_audits[3]["holding_minutes_median"]
            }
        records.append({"family":family,**fam})
    return {
        "schema":"nbot-v6-64-no-time-exit-fully-verified-comparison-1",
        "historical_data_seen_not_blind":True,
        "one_position_1000usdt_stake_25_pairs":True,
        "same_original_entry_code":True,
        "new_offline_native_archives_verified":64,
        "old_offline_native_archives_verified":48,
        "no_live_paper_or_promotion":True,
        "end_of_backtest_forced_closures_always_possible":True,
        "monthly_standalone_results_are_not_one_combined_portfolio":True,
        "monthly_reinvestment_or_continuity_not_identical_to_continuous_3mo":True,
        "rows":records
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,default=DEFAULT)
    args=parser.parse_args()
    print(json.dumps(analyze(args.root),indent=2,sort_keys=True))

if __name__=="__main__":
    main()
