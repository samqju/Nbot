#!/usr/bin/env python3
"""Nbot V6 final owner-requested exact +1% activation, lock P-1 pp trailing A/B.

Eight original entry families, ONE continuous Jul-Sep native official Freqtrade
backtest per family, ONE $1000 1x global position among 25 original USDT
futures coins. Original +5% ROI, -2% initial stop, NO time exit. Compare to
immutable +2%-activation 1%-gap native historical ZIP baseline.

Standalone historical strategy result only (NOT global dynamic 25x8 AI).
No paper/live trading, no overwrite original research, no auto-promotion.
"""
from __future__ import annotations
import argparse,fcntl,hashlib,json,os,statistics,subprocess
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZipFile

ROOT=Path("/root/nbot-v6-m1-20261016")
SOURCE=ROOT/"global-next-source"
HISTORY=ROOT/"january-2026-public-history-stage"
OLD=ROOT/"no-time-exit-20261019"
OUTPUT=ROOT/"exact-one-trailing-20261019"
BRANCH="prototype/v6-freqtrade-freqai-20261016"
OLD_ENTRY_SHA="aa97a32c9af73ae63503f5dbff63d98a7fe32200"
FLAG="OFFLINE_OWNER_REQUESTED_EXACT_ONE_TRAIL_ONLY"
FAMILIES={"ema_cross":"EmaCross","donchian_breakout":"Donchian",
 "bollinger_reversion":"Bollinger","rsi_reversion":"Rsi",
 "macd_momentum":"Macd","stochastic_reversal":"Stochastic",
 "atr_breakout":"AtrBreakout","volume_trend":"VolumeTrend"}
STATUS=OUTPUT/"status.json"
EVENTS=OUTPUT/"events.jsonl"

def timestamp():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def require(a,why):
    if not a:raise RuntimeError(why)
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as fd:
        for x in iter(lambda:fd.read(1048576),b""):h.update(x)
    return h.hexdigest()
def load(p):return json.loads(p.read_text())
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    with t.open("x") as fd:
        json.dump(obj,fd,indent=2,sort_keys=True);fd.write("\n")
        fd.flush();os.fsync(fd.fileno())
    os.replace(t,p)
def event(kind,**args):
    e={"event":kind,"at_utc":timestamp(),**args}
    with EVENTS.open("a") as fd:
        fd.write(json.dumps(e,sort_keys=True)+"\n");fd.flush();os.fsync(fd.fileno())
    print(json.dumps(e,sort_keys=True),flush=True)
def cmd(*args):return subprocess.check_output(args,text=True).strip()
def reference(family):
    p=OLD/"no_time_trailing"/family/"full_july_september"
    a=load(p/"native-audit.json")
    z=p/"backtest_results"/a["file"]
    require(z.is_file() and sha(z)==a["native_zip_sha256"],"OLD_TRAILING_NATIVE_ZIP_CHANGED")
    require(a["family"]==family and a["policy"]=="trailing"
            and a["no_60minute_custom_exit"] is True
            and abs(a["native_fee_each_side"]-.0005)<1e-12,
            "OLD_TRAILING_NATIVE_AUDIT_INVALID")
    return a
def preflight():
    require(os.geteuid()==0,"VPS_ROOT_RESEARCH_REQUIRED")
    require(os.environ.get("NBOT_V6_EXACT_TRAIL_OPTIN")==FLAG,
            "OFFLINE_OWNER_OPTIN_REQUIRED")
    require(cmd("git","-C",str(SOURCE),"branch","--show-current")==BRANCH,
            "WRONG_V6_BRANCH")
    require(cmd("git","-C",str(SOURCE),"status","--porcelain=v1")=="",
            "DIRTY_V6_CHECKOUT")
    require(subprocess.run(["git","-C",str(SOURCE),"diff","--quiet",OLD_ENTRY_SHA,
                            "HEAD","--","user_data/strategies/NbotV6LibraryResearch.py"],
                            check=False).returncode==0,
            "FROZEN_ENTRY_LIBRARY_CHANGED")
    require(not cmd("docker","ps","-q"),"OTHER_DOCKER_RUNNING")
    for unit in ("nbot-v6-global-20261018.service",
                  "nbot-v6-no-time-exit-20261019.service",
                  "nbot-v6-stop-one-20261019.service"):
        require(subprocess.run(["systemctl","is-active","--quiet",unit],
            check=False).returncode!=0,"OTHER_V6_RESEARCH_RUNNING")
    require(load(OLD/"status.json").get("jobs_completed")==64 and
            load(OLD/"status.json").get("status")=="complete_research_only",
            "ORIGINAL_NO_TIME_BASELINE_INCOMPLETE")
    nativecfg=load(SOURCE/"user_data/config.v6-library-native-offline.json")
    envelope={
      "dry_run":True,"nbot_live_mode":False,"nbot_paper_research_mode":False,
      "nbot_v6_library_research_only":True,"max_open_trades":1,
      "stake_amount":1000,"force_entry_enable":False}
    for key,value in envelope.items():
        require(nativecfg.get(key)==value,"UNSAFE_NATIVE_CONFIG_"+key)
    require(nativecfg.get("exchange")=={"key":"","secret":""}
            and nativecfg.get("freqai",{}).get("enabled") is False
            and nativecfg.get("api_server",{}).get("enabled") is False
            and nativecfg.get("telegram",{}).get("enabled") is False,
            "NOT_OFFLINE_NO_CREDS")
    cfg=load(SOURCE/"user_data/config.json")
    whitelist=cfg["exchange"]["pair_whitelist"]
    require(len(whitelist)==25 and len(set(whitelist))==25
            and cfg["trading_mode"]=="futures"
            and cfg["margin_mode"]=="isolated",
            "NOT_FROZEN_25_PERPETUALS")
    require((HISTORY/"futures").is_dir()
            and (SOURCE/"user_data/strategies/NbotV6ExactOneTrailResearch.py").is_file(),
            "HISTORICAL_DATA_OR_STRATEGY_MISSING")
    for family in FAMILIES:reference(family)
    return cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),nativecfg

def inspect(folder,family):
    files=list((folder/"backtest_results").glob("*.zip"))
    require(len(files)==1,"NOT_EXACTLY_ONE_NATIVE_ZIP")
    z=files[0]
    with ZipFile(z) as fd:
        require(fd.testzip() is None,"CORRUPT_NATIVE_ZIP")
        names=[n for n in fd.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        require(len(names)==1,"BAD_NATIVE_ZIP_JSON_COUNT")
        payload=json.loads(fd.read(names[0]))
    require(len(payload.get("strategy",{}))==1,"BAD_STRATEGY_COUNT")
    strategy,info=next(iter(payload["strategy"].items()))
    expected="NbotV6"+FAMILIES[family]+"ExactOneTrailResearch"
    require(strategy==expected,"WRONG_STRATEGY_"+strategy)
    require(info.get("trading_mode")=="futures" and info.get("timeframe")=="5m"
            and info.get("max_open_trades")==1
            and len(info.get("pairlist",[]))==25
            and abs(float(info.get("stake_amount",0))-1000)<1e-8
            and abs(float(info.get("starting_balance",0))-100000)<1e-8,
            "NATIVE_25_ONE_SLOT_ENVELOPE_MISMATCH")
    require(abs(float(info.get("stoploss",0))+.02)<1e-12
            and abs(float(info.get("minimal_roi",{}).get("0",-1))-.05)<1e-12,
            "NATIVE_INITIAL_STOP_OR_ROI_INVALID")
    trades=info["trades"]
    require(len(trades)==info["total_trades"],"TRADE_COUNT_MISMATCH")
    native=float(info["profit_total_abs"])
    require(abs(sum(float(t["profit_abs"]) for t in trades)-native)<.002,
            "NATIVE_TRADE_LEDGER_DISAGREES_WITH_ECONOMICS")
    reasons={};turnover=0;duration=[]
    for tr in trades:
        require(abs(float(tr["leverage"])-1)<1e-10
                and abs(float(tr["fee_open"])-.0005)<1e-9
                and abs(float(tr["fee_close"])-.0005)<1e-9
                and tr["pair"] in info["pairlist"],
                "NATIVE_LEVERAGE_FEE_PAIR_INVALID")
        reason=tr["exit_reason"]
        require(reason not in ("v6_library_60m_exit","global_60m_limit"),
                "UNEXPECTED_TIME_EXIT")
        reasons[reason]=reasons.get(reason,0)+1
        turnover+=float(tr["stake_amount"])
        start=datetime.fromisoformat(tr["open_date"])
        end=datetime.fromisoformat(tr["close_date"])
        require(end>=start,"NONCHRONOLOGICAL_TRADE")
        duration.append((end-start).total_seconds()/60)
    res={
        "schema":"nbot-v6-exact-one-trail-native-1",
        "family":family,"strategy":strategy,
        "source_commit":cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),
        "native_zip_name":z.name,"native_zip_sha256":sha(z),
        "native_net_usdt":round(native,6),
        "stressed_25bp_net_usdt":round(native-.0025*turnover,6),
        "native_fees_per_side":.0005,
        "extra_cost_stress_roundtrip":.0025,
        "trades":len(trades),
        "winning_trades":sum(float(t["profit_abs"])>0 for t in trades),
        "losing_trades":sum(float(t["profit_abs"])<0 for t in trades),
        "exit_reasons":reasons,
        "historical_end_force_exits":reasons.get("force_exit",0),
        "median_holding_minutes":round(statistics.median(duration),2) if duration else None,
        "max_holding_minutes":round(max(duration),2) if duration else None,
        "exact_1pp_from_entry_trail_with_1pct_activation":True,
        "initial_stoploss":-.02,"native_roi":.05,
        "no_time_limit":True,"no_trading_or_auto_promotion":True}
    save(folder/"native-audit.json",res)
    return res

def run_one(family,cfg):
    out=OUTPUT/family
    require(not out.exists(),"REFUSE_RETRY_OR_OVERWRITE_PARTIAL_"+family)
    out.mkdir(parents=True)
    os.chown(out,1000,1000)
    os.chmod(out,0o750)
    overlay=out/"exact-overlay.json"
    save(overlay,cfg)
    os.chmod(overlay,0o644)
    name="NbotV6"+FAMILIES[family]+"ExactOneTrailResearch"
    args=[
      "timeout","-s","TERM","-k","60","14400",
      "docker","run","--rm","--name","nbot-v6-exact-one-native-single",
      "--network","bridge","--cpus=2","--memory=6g",
      "--cap-drop","ALL","--security-opt","no-new-privileges",
      "-v",str(SOURCE)+":/research:ro",
      "-v",str(HISTORY)+":/history:ro",
      "-v",str(out)+":/results",
      "--entrypoint","freqtrade","freqtradeorg/freqtrade:stable_freqai",
      "backtesting","-c","/research/user_data/config.json",
      "-c","/results/exact-overlay.json","--userdir","/results",
      "--datadir","/history","--strategy",name,
      "--strategy-path","/research/user_data/strategies",
      "--timerange","20260701-20261001",
      "--fee","0.0005","--cache","none","--export","trades",
      "--enable-protections"]
    event("start",family=family,strategy=name)
    with (out/"native.log").open("w") as fd:
        result=subprocess.run(args,stdout=fd,stderr=subprocess.STDOUT,check=False)
    save(out/"run-state.json",{"returncode":result.returncode,"utc":timestamp()})
    require(result.returncode==0,
            "NATIVE_DOCKER_FAILED_"+family+"_EXIT_"+str(result.returncode))
    outdata=inspect(out,family)
    event("complete",family=family,trades=outdata["trades"],
          native_pnl=outdata["native_net_usdt"],
          stressed_pnl=outdata["stressed_25bp_net_usdt"],
          trailing_exits=outdata["exit_reasons"].get("trailing_stop_loss",0))
    return outdata

def finalize():
    items=[]
    for fam in FAMILIES:
        old=reference(fam)
        new=load(OUTPUT/fam/"native-audit.json")
        items.append({
          "family":fam,
          "original_plus2_activation_trailing_net_native":old["native_net_usdt"],
          "new_plus1_activation_trailing_net_native":new["native_net_usdt"],
          "original_plus2_activation_trailing_after_25bp":old["additional_25bp_stressed_net_usdt"],
          "new_plus1_activation_trailing_after_25bp":new["stressed_25bp_net_usdt"],
          "net_change_after_stress":round(new["stressed_25bp_net_usdt"]-old["additional_25bp_stressed_net_usdt"],6),
          "old_trades":old["trades"],"new_trades":new["trades"],
          "old_trailing_exits":old["exit_reasons"].get("trailing_stop_loss",0),
          "new_trailing_exits":new["exit_reasons"].get("trailing_stop_loss",0),
          "source_new_zip_sha256":new["native_zip_sha256"],
          "source_original_zip_sha256":old["native_zip_sha256"]})
    report={
      "schema":"nbot-v6-exact-one-activation-versus-two-native-1",
      "comparison_window":"2026-07-01 through 2026-09-30",
      "source_commit":cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),
      "only_exit_rule_is_changed":True,
      "original_stop_minus_two_roi_plus_five_no_time":True,
      "same_25_pairs_1x_1000_stake_one_slot":True,
      "historically_seen_period_not_blind_holdout":True,
      "native_fee_each_way":.0005,"extra_hypothetical_25bp_roundtrip":True,
      "one_family_per_backtest_not_eight_family_ai_portfolio":True,
      "paper_live_auto_promotion_disabled":True,
      "results":items}
    save(OUTPUT/"final-comparison.json",report)
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--status",action="store_true")
    p.add_argument("--execute",action="store_true")
    args=p.parse_args()
    if args.status:
        print(STATUS.read_text() if STATUS.exists() else "NOT_STARTED")
        if EVENTS.exists():print("LAST_EVENTS\n"+"\n".join(EVENTS.read_text().splitlines()[-8:]))
        return
    require(args.execute,"NO_EXPLICIT_EXECUTE")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with (OUTPUT/"singleton.lock").open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        commit,cfg=preflight()
        require(not STATUS.exists(),"STUDY_ALREADY_EXISTS_NO_RESTART")
        state={"schema":"nbot-v6-exact-one-trailing-progress-1",
               "source_commit":commit,"status":"running",
               "jobs_total":8,"jobs_completed":0,"started":timestamp(),
               "trading_allowed":False,"paper_live":False}
        save(STATUS,state)
        try:
            for fam in FAMILIES:
                run_one(fam,cfg)
                state.update(current_job=fam,jobs_completed=state["jobs_completed"]+1,
                             updated=timestamp())
                save(STATUS,state)
            finalize()
            state.update(status="complete_research_only",current_job=None,finished=timestamp())
            save(STATUS,state)
            event("finished",jobs_completed=8)
        except BaseException as e:
            state.update(status="blocked",error=str(e),updated=timestamp())
            save(STATUS,state)
            event("blocked",reason=str(e))
            raise
if __name__=="__main__":main()
