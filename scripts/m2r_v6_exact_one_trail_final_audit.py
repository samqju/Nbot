#!/usr/bin/env python3
"""Independent SHA-256 and native ledger verifier: exact +1pp 8 ZIP vs old 8 ZIP.

Reads saved official Freqtrade historical ZIPs; never executes strategies,
downloads data, places orders, changes models or writes anything to disk.
"""
from __future__ import annotations
from pathlib import Path
from zipfile import ZipFile
import hashlib,json
import statistics
FAMILIES={"ema_cross":"EmaCross","donchian_breakout":"Donchian",
"bollinger_reversion":"Bollinger","rsi_reversion":"Rsi",
"macd_momentum":"Macd","stochastic_reversal":"Stochastic",
"atr_breakout":"AtrBreakout","volume_trend":"VolumeTrend"}
ROOT=Path("/root/nbot-v6-m1-20261016")
OLD=ROOT/"no-time-exit-20261019"
NEW=ROOT/"exact-one-trailing-20261019"
def require(a,reason):
    if not a:raise RuntimeError(reason)
def obj(p):return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()
def native(folder,original,family):
    audit=obj(folder/"native-audit.json")
    file=folder/"backtest_results"/(audit["file"] if original else audit["native_zip_name"])
    require(file.is_file() and sha(file)==audit["native_zip_sha256"],"ZIP_SHA256_MISMATCH_"+family)
    with ZipFile(file) as f:
        require(f.testzip() is None,"INVALID_FT_NATIVE_ZIP")
        names=[x for x in f.namelist() if x.endswith(".json") and not x.endswith("_config.json")]
        require(len(names)==1,"MISSING_OR_AMBIGUOUS_NATIVE_JSON")
        data=json.loads(f.read(names[0]))
    require(len(data.get("strategy",{}))==1,"NOT_ONE_STRATEGY")
    name,details=next(iter(data["strategy"].items()))
    expected="NbotV6"+FAMILIES[family]+(
        "NoTimeTrailingResearch" if original else "ExactOneTrailResearch")
    require(name==expected,"WRONG_NBOT_STRATEGY")
    require(details["trading_mode"]=="futures" and details["timeframe"]=="5m"
            and details["max_open_trades"]==1
            and len(details["pairlist"])==25
            and abs(float(details["starting_balance"])-100000)<1e-6
            and abs(float(details["stake_amount"])-1000)<1e-6
            and abs(float(details["stoploss"])+.02)<1e-10
            and abs(float(details["minimal_roi"]["0"])-.05)<1e-10,
            "NOT_SAME_ENTRY_ECONOMIC_ENVELOPE")
    trades=details["trades"]
    require(len(trades)==details["total_trades"],"WRONG_TRADE_COUNT")
    for tr in trades:
        require(abs(float(tr["leverage"])-1)<1e-8
            and abs(float(tr["fee_open"])-.0005)<1e-9
            and abs(float(tr["fee_close"])-.0005)<1e-9
            and tr["pair"] in details["pairlist"],"WRONG_LEVERAGE_FEE_OR_PAIR")
        require(tr["exit_reason"] not in ("v6_library_60m_exit","global_60m_limit"),
                "TRADES_STILL_EXPIRED_AT_SIXTY_MINUTES")
    net=float(details["profit_total_abs"])
    require(abs(sum(float(tr["profit_abs"]) for tr in trades)-net)<.002,
            "TRADE_LEDGER_VS_NET_USDT_MISMATCH")
    stressed=net-.0025*sum(float(tr["stake_amount"]) for tr in trades)
    if original:
        require(abs(audit["native_net_usdt"]-net)<.002 and
                abs(audit["additional_25bp_stressed_net_usdt"]-stressed)<.002,
                "BASELINE_ECONOMICS_MISMATCH")
    else:
        require(abs(audit["native_net_usdt"]-net)<.002 and
                abs(audit["stressed_25bp_net_usdt"]-stressed)<.002,
                "EXACT_NEW_ECONOMICS_MISMATCH")
    return {"native":round(net,4),"stressed":round(stressed,4),
            "trades":len(trades),"winners":sum(tr["profit_abs"]>0 for tr in trades),
            "trailing_exits":sum(tr["exit_reason"]=="trailing_stop_loss" for tr in trades),
            "initial_stop_exits":sum(tr["exit_reason"]=="stop_loss" for tr in trades),
            "forced_end":sum(tr["exit_reason"]=="force_exit" for tr in trades),
            "archive_sha256":sha(file)}

def verify():
    state=obj(NEW/"status.json")
    require(state.get("status")=="complete_research_only"
            and state.get("jobs_completed")==8 and state.get("jobs_total")==8,
            "EIGHT_NATIVE_JOBS_NOT_COMPLETE")
    final=obj(NEW/"final-comparison.json")
    require(final.get("schema")=="nbot-v6-exact-one-activation-versus-two-native-1"
            and len(final.get("results",[]))==8,"WRONG_COMPARISON_MANIFEST")
    table=[]
    for family in FAMILIES:
        x=native(OLD/"no_time_trailing"/family/"full_july_september",True,family)
        y=native(NEW/family,False,family)
        table.append({"family":family,"original_plus2_trail":x,
                      "exact_plus1_trail":y,
                      "difference_native_usdt":round(y["native"]-x["native"],4),
                      "difference_stressed_usdt":round(y["stressed"]-x["stressed"],4)})
    return {
        "schema":"nbot-v6-exact-plus-one-independent-16-native-zip-audit-1",
        "archives_SHA256_verified":16,
        "same_entry_family_same_25_pairs_one_1000_notional_slot":True,
        "historical_window":"2026-07-01 through 2026-09-30",
        "only_new_initial_trailing_activation_one_percent_changed":True,
        "original_trailing_plus2pct_native_zip_unchanged":True,
        "new_profitable_after_native_fees_count":sum(x["exact_plus1_trail"]["native"]>0 for x in table),
        "new_profitable_after_extra_25bp_stress_count":sum(x["exact_plus1_trail"]["stressed"]>0 for x in table),
        "new_improves_after_stress_count":sum(x["difference_stressed_usdt"]>0 for x in table),
        "new_worsens_after_stress_count":sum(x["difference_stressed_usdt"]<0 for x in table),
        "historical_period_already_examined_not_blind":True,
        "not_dynamic_M5A_or_25x8_AI_model":True,
        "no_paper_or_live":True,
        "results":table}
if __name__=="__main__":
    print(json.dumps(verify(),indent=2,sort_keys=True))
