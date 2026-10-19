#!/usr/bin/env python3
"""Independently verify 16 -1% vs 16 earlier -2% JUL-SEP continuous native ZIPs.

Read-only, with no remote actions or model training. Verifies official Freqtrade
trades, SHA256 archive hashes, actual stop config, fees, one-slot, stresses,
and no 60-minute exit. Distinguishes per-1000-stake returns from 100k-wallet.
"""
from pathlib import Path
import hashlib,json,sys
from zipfile import ZipFile

ROOT=Path("/root/nbot-v6-m1-20261016")
NEW=ROOT/"stop-one-percent-20261019"
OLD=ROOT/"no-time-exit-20261019"
FAMILIES=("ema_cross","donchian_breakout","bollinger_reversion","rsi_reversion","macd_momentum","stochastic_reversal","atr_breakout","volume_trend")
POLICIES=("fixed","trailing")

def j(p):return json.loads(p.read_text())
def require(b,reason):
    if not b:raise RuntimeError(reason)
def hash_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):h.update(b)
    return h.hexdigest()
def inspect(folder,expected_stop,expected_strategy,earlier):
    a=j(folder/("native-audit.json"))
    f=folder/"backtest_results"/(a["file"] if earlier else a["archive_name"])
    require(f.is_file() and hash_file(f)==a["native_zip_sha256"],"NATIVE_ZIP_HASH_MISMATCH_"+str(f))
    with ZipFile(f) as z:
        require(z.testzip() is None,"CORRUPT_ZIP")
        names=[n for n in z.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        require(len(names)==1,"MULTIPLE_MAIN_NATIVE_JSON")
        data=json.loads(z.read(names[0]))
    require(len(data.get("strategy",{}))==1,"NOT_ONE_NATIVE_STRATEGY")
    strategy,obj=next(iter(data["strategy"].items()))
    require(strategy==expected_strategy,"WRONG_NATIVE_STRATEGY_"+strategy)
    require(abs(float(obj.get("stoploss",0))-expected_stop)<1e-9,
            "REAL_STRATEGY_STOPLOSS_MISMATCH_"+strategy)
    require(float(obj.get("minimal_roi",{}).get("0",-1))==.05,
            "REAL_STRATEGY_ROI_MISMATCH")
    require(obj.get("trading_mode")=="futures" and obj.get("timeframe")=="5m"
            and obj.get("max_open_trades")==1
            and len(obj.get("pairlist",[]))==25
            and abs(float(obj.get("stake_amount",0))-1000)<1e-8
            and abs(float(obj.get("starting_balance",0))-100000)<1e-8,
            "BACKTEST_WRONG_PORTFOLIO")
    trades=obj["trades"]
    require(len(trades)==obj["total_trades"],"BAD_TRADE_COUNT")
    net=float(obj["profit_total_abs"])
    require(abs(sum(float(t["profit_abs"]) for t in trades)-net)<.002,
            "BAD_NATIVE_TRADE_LEDGER")
    reasons={}
    for t in trades:
        require(abs(float(t["leverage"])-1)<1e-8
                and abs(float(t["fee_open"])-.0005)<1e-9
                and abs(float(t["fee_close"])-.0005)<1e-9
                and t["pair"] in obj["pairlist"],
                "NATIVE_LEVERAGE_FEES_OR_PAIR_MISMATCH")
        what=t["exit_reason"]
        require(what not in ("v6_library_60m_exit","global_60m_limit"),
                "TIME_EXIT_NOT_DISABLED")
        reasons[what]=reasons.get(what,0)+1
    stress=net-.0025*sum(float(t["stake_amount"]) for t in trades)
    if earlier:
        require(abs(a["native_net_usdt"]-net)<.002
                and abs(a["additional_25bp_stressed_net_usdt"]-stress)<.002,
                "OLD_ECONOMIC_AUDIT_MISMATCH")
    else:
        require(abs(a["native_net_usdt"]-net)<.002
                and abs(a["stress_25bp_net_usdt"]-stress)<.002,
                "NEW_ECONOMIC_AUDIT_MISMATCH")
    return {"native":round(net,2),"stress":round(stress,2),
            "trades":len(trades),"win":sum(float(t["profit_abs"])>0 for t in trades),
            "exit_reasons":reasons}

def main():
    state=j(NEW/"status.json")
    require(state.get("status")=="complete_research_only"
            and state.get("jobs_completed")==16,"MINUS_ONE_STUDY_NOT_COMPLETE")
    prior=j(OLD/"status.json")
    require(prior.get("status")=="complete_research_only"
            and prior.get("jobs_completed")==64,"MINUS_TWO_CONTROL_INCOMPLETE")
    results=[]
    for fam in FAMILIES:
        for p in POLICIES:
            short={"ema_cross":"EmaCross","donchian_breakout":"Donchian",
                   "bollinger_reversion":"Bollinger","rsi_reversion":"Rsi",
                   "macd_momentum":"Macd","stochastic_reversal":"Stochastic",
                   "atr_breakout":"AtrBreakout","volume_trend":"VolumeTrend"}[fam]
            old=inspect(OLD/("no_time_"+p)/fam/"full_july_september",
                        -.02,"NbotV6"+short+"NoTime"+p.capitalize()+"Research",True)
            new=inspect(NEW/fam/p,-.01,
                        "NbotV6"+short+"StopOne"+p.capitalize()+"Research",False)
            results.append({"family":fam,"policy":p,
                "two_percent":old,"one_percent":new,
                "stress_improvement_usdt":round(new["stress"]-old["stress"],2)})
    newpos=sum(r["one_percent"]["stress"]>0 for r in results)
    oldpos=sum(r["two_percent"]["stress"]>0 for r in results)
    better=sum(r["stress_improvement_usdt"]>0 for r in results)
    report={"schema":"nbot-v6-minus-one-stop-independently-audited-1",
            "source_commit":state["source_commit"],
            "official_native_zip_archives_verified":32,
            "same_25coin_one_slot_1000stake_no_time_plus5roi":True,
            "comparison_window":"2026-07-01 through 2026-09-30",
            "no_new_untouched_holdout":True,
            "one_percent_improves_number":better,
            "one_percent_worsens_number":len(results)-better,
            "one_percent_positive_after_extra_cost":newpos,
            "two_percent_positive_after_extra_cost":oldpos,
            "no_paper_live_or_autotrading":True,
            "read_only":True,
            "results":results}
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=="__main__":main()
