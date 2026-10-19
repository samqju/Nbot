#!/usr/bin/env python3
"""Finite OFFLINE-only -1% initial-stop research vs frozen -2% no-time variants.

Exactly 8 technical strategies × fixed/old-trailing = 16 official native
Freqtrade JUL-SEP CONTINUOUS backtests, same original 25 markets, position and
fee assumptions. No changes to original profitable/losing research archives.
This is retrospective exploratory evidence, NOT a future holdout or release.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import fcntl,hashlib,json,os,subprocess
from pathlib import Path
from zipfile import ZipFile

ROOT=Path("/root/nbot-v6-m1-20261016")
SOURCE=ROOT/"global-next-source"
HISTORY=ROOT/"january-2026-public-history-stage"
BASE=ROOT/"no-time-exit-20261019"
OUTPUT=ROOT/"stop-one-percent-20261019"
STATUS=OUTPUT/"status.json"
EVENTS=OUTPUT/"events.jsonl"
BRANCH="prototype/v6-freqtrade-freqai-20261016"
OPTIN="OWNER_AUTHORIZED_OFFLINE_MINUS_ONE_STOP_AB_ONLY"
ORIGINAL_COMMIT="aa97a32c9af73ae63503f5dbff63d98a7fe32200"
FAMILIES={"ema_cross":"EmaCross","donchian_breakout":"Donchian",
          "bollinger_reversion":"Bollinger","rsi_reversion":"Rsi",
          "macd_momentum":"Macd","stochastic_reversal":"Stochastic",
          "atr_breakout":"AtrBreakout","volume_trend":"VolumeTrend"}
POLICIES=("fixed","trailing")
TASKS=tuple((f,p) for f in FAMILIES for p in POLICIES)
IMAGE="freqtradeorg/freqtrade:stable_freqai"

def utc():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def require(x,msg):
    if not x:raise RuntimeError(msg)
def cmd(*args):return subprocess.check_output(args,text=True).strip()
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as s:
        for ch in iter(lambda:s.read(1048576),b""):h.update(ch)
    return h.hexdigest()
def load(p):return json.loads(p.read_text())
def save(p,obj):
    t=p.with_name(p.name+".tmp")
    t.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
    os.replace(t,p)
def event(kind,**kwargs):
    item={"event":kind,"at_utc":utc(),**kwargs}
    with EVENTS.open("a") as fd:
        fd.write(json.dumps(item,sort_keys=True)+"\n")
        fd.flush();os.fsync(fd.fileno())
    print(json.dumps(item,sort_keys=True),flush=True)

def check_original(family,policy):
    folder=BASE/("no_time_"+policy)/family/"full_july_september"
    audit=load(folder/"native-audit.json")
    zipfile=folder/"backtest_results"/audit["file"]
    require(zipfile.is_file() and sha(zipfile)==audit["native_zip_sha256"],
            "MUTATED_OR_MISSING_2PCT_NATIVE_ZIP")
    require(audit["family"]==family and audit["policy"]==policy
            and audit["no_60minute_custom_exit"] is True,
            "UNTRUSTED_2PCT_REFERENCE")
    return audit

def preflight():
    require(os.geteuid()==0,"RESEARCH_VPS_ROOT_REQUIRED")
    require(os.environ.get("NBOT_V6_STOP_ONE_OPTIN")==OPTIN,
            "EXPLICIT_OFFLINE_RESEARCH_AUTHORIZATION_REQUIRED")
    require(not cmd("docker","ps","-q"),"DOCKER_BUSY")
    require(cmd("git","-C",str(SOURCE),"status","--porcelain=v1")=="",
            "DIRTY_ISOLATED_SOURCE_REFUSED")
    require(cmd("git","-C",str(SOURCE),"branch","--show-current")==BRANCH,
            "WRONG_RESEARCH_BRANCH")
    require(subprocess.run(["git","-C",str(SOURCE),"diff","--quiet",
                            ORIGINAL_COMMIT,"HEAD","--",
                            "user_data/strategies/NbotV6LibraryResearch.py"],
                            check=False).returncode==0,
            "FROZEN_ORIGINAL_ENTRIES_CHANGED")
    for service in ("nbot-v6-no-time-exit-20261019.service",
                    "nbot-v6-global-20261018.service",
                    "nbot-v6-profit-protection-next-20261018.service"):
        require(subprocess.run(["systemctl","is-active","--quiet",service],
                check=False).returncode!=0,"OTHER_RESEARCH_RUNNING")
    last=load(BASE/"status.json")
    require(last.get("status")=="complete_research_only"
            and last.get("jobs_completed")==64,"2PCT_BASELINE_INCOMPLETE")
    st=load(ROOT/"global-25x8-20261018/progress.json")
    require(st.get("status")=="complete_research_only"
            and st.get("jobs_completed")==12,"GLOBAL_RESEARCH_INCOMPLETE")
    basecfg=load(SOURCE/"user_data/config.v6-library-native-offline.json")
    expected={"dry_run":True,"nbot_live_mode":False,
              "nbot_paper_research_mode":False,
              "nbot_v6_library_research_only":True,
              "max_open_trades":1,"stake_amount":1000,
              "force_entry_enable":False}
    for k,v in expected.items():require(basecfg.get(k)==v,"UNSAFE_CONFIG_"+k)
    require(basecfg.get("exchange")=={"key":"","secret":""},"NONEMPTY_EXCHANGE_KEYS")
    require(basecfg["freqai"]["enabled"] is False
            and basecfg["api_server"]["enabled"] is False
            and basecfg["telegram"]["enabled"] is False,
            "OFFLINE_NATIVE_SAFETY_GUARD_MISMATCH")
    core=load(SOURCE/"user_data/config.json")
    require(core["trading_mode"]=="futures" and core["margin_mode"]=="isolated"
            and len(core["exchange"]["pair_whitelist"])==25,
            "NOT_25_COIN_ISOLATED_FUTURES")
    for family,policy in TASKS:check_original(family,policy)
    require((SOURCE/"user_data/strategies/NbotV6StopOneResearch.py").is_file()
            and (HISTORY/"futures").is_dir(),"SOURCE_OR_HISTORY_MISSING")
    return cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),basecfg

def audit_native(folder,family,policy):
    archives=list((folder/"backtest_results").glob("*.zip"))
    require(len(archives)==1,"NATIVE_ZIP_MISSING_OR_AMBIGUOUS")
    z=archives[0]
    with ZipFile(z) as f:
        require(f.testzip() is None,"ZIP_CORRUPT")
        files=[x for x in f.namelist() if x.endswith(".json") and not x.endswith("_config.json")]
        require(len(files)==1,"NATIVE_JSON_AMBIGUOUS")
        root=json.loads(f.read(files[0]))
    require(len(root.get("strategy",{}))==1,"STRATEGY_COUNT_MISMATCH")
    name,obj=next(iter(root["strategy"].items()))
    expected="NbotV6"+FAMILIES[family]+"StopOne"+policy.capitalize()+"Research"
    require(name==expected,"WRONG_BACKTEST_STRATEGY")
    require(obj.get("trading_mode")=="futures" and obj.get("timeframe")=="5m"
            and obj.get("max_open_trades")==1
            and len(obj.get("pairlist",[]))==25
            and abs(float(obj.get("starting_balance",0))-100000)<1e-8
            and abs(float(obj.get("stake_amount",0))-1000)<1e-8,
            "PORTFOLIO_NOT_IDENTICAL")
    trades=obj["trades"]
    require(len(trades)==obj["total_trades"],"NATIVE_TRADE_COUNT_INVALID")
    native=float(obj["profit_total_abs"])
    require(abs(sum(float(t["profit_abs"]) for t in trades)-native)<.002,
            "NATIVE_LEDGER_PNL_MISMATCH")
    reasons={}
    for t in trades:
        require(abs(float(t["leverage"])-1)<1e-8
                and abs(float(t["fee_open"])-.0005)<1e-9
                and abs(float(t["fee_close"])-.0005)<1e-9
                and t["pair"] in obj["pairlist"],
                "LEVERAGE_FEE_OR_PAIR_MISMATCH")
        why=str(t["exit_reason"])
        require(why not in ("v6_library_60m_exit","global_60m_limit"),
                "UNEXPECTED_TIME_EXIT")
        reasons[why]=reasons.get(why,0)+1
    stressed=native-.0025*sum(float(t["stake_amount"]) for t in trades)
    result={"schema":"nbot-v6-stop-one-percent-native-1",
            "source_commit":cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),
            "family":family,"policy":policy,"stoploss":-0.01,
            "native_zip_sha256":sha(z),"archive_name":z.name,
            "trades":len(trades),"winning_trades":sum(t["profit_abs"]>0 for t in trades),
            "native_net_usdt":round(native,6),
            "stress_25bp_net_usdt":round(stressed,6),
            "exit_reasons":reasons,
            "historical_end_forced":reasons.get("force_exit",0),
            "no_time_exit":True,
            "no_paper_live_or_auto_promotion":True}
    save(folder/"native-audit.json",result)
    return result

def run_one(family,policy,cfg):
    name=f"{family}/{policy}"
    out=OUTPUT/family/policy
    require(not out.exists(),"REFUSE_OVERWRITE_PREVIOUS_ATTEMPT_"+name)
    out.mkdir(parents=True)
    os.chown(out,1000,1000);os.chmod(out,0o750)
    overlay=out/"exact-overlay.json"
    save(overlay,cfg);os.chmod(overlay,0o644)
    strat="NbotV6"+FAMILIES[family]+"StopOne"+policy.capitalize()+"Research"
    command=[
        "timeout","-s","TERM","-k","60","14400",
        "docker","run","--rm","--name","nbot-v6-stop-one-single-native-offline",
        "--network","bridge","--cpus=2","--memory=6g",
        "--cap-drop","ALL","--security-opt","no-new-privileges",
        "-v",str(SOURCE)+":/research:ro",
        "-v",str(HISTORY)+":/history:ro",
        "-v",str(out)+":/results",
        "--entrypoint","freqtrade",IMAGE,
        "backtesting","-c","/research/user_data/config.json",
        "-c","/results/exact-overlay.json","--userdir","/results",
        "--datadir","/history","--strategy",strat,
        "--strategy-path","/research/user_data/strategies",
        "--timerange","20260701-20261001","--fee","0.0005",
        "--cache","none","--export","trades","--enable-protections"]
    event("start",job=name)
    with (out/"native.log").open("w") as f:
        p=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=False)
    save(out/"run-state.json",{"exit_code":p.returncode,"at":utc()})
    require(p.returncode==0,"OFFLINE_NATIVE_FAILED_"+name+"_"+str(p.returncode))
    summary=audit_native(out,family,policy)
    event("complete",job=name,trades=summary["trades"],
          base_net=summary["native_net_usdt"],net_stressed=summary["stress_25bp_net_usdt"],
          forced_end=summary["historical_end_forced"])
    return summary

def main():
    args=argparse.ArgumentParser()
    args.add_argument("--status",action="store_true")
    args.add_argument("--execute",action="store_true")
    a=args.parse_args()
    if a.status:
        print(STATUS.read_text() if STATUS.exists() else "NOT_STARTED")
        if EVENTS.exists():print("EVENT_TAIL\n"+"\n".join(EVENTS.read_text().splitlines()[-6:]))
        return
    require(a.execute,"EXPLICIT_EXECUTE_REQUIRED")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with (OUTPUT/"singleton.lock").open("w") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        commit,cfg=preflight()
        require(not STATUS.exists(),"BATCH_ALREADY_EXISTS_NO_RESTART")
        state={"schema":"nbot-v6-stop-one-ab-1",
               "status":"running","jobs_total":16,"jobs_completed":0,
               "started":utc(),"source_commit":commit,
               "stop_comparator":-0.02,"tested_stop":-0.01,
               "same_5pct_roi_no_60min":True,"trading_allowed":False,
               "paper_trading":False,"auto_promotion":False}
        save(STATUS,state)
        try:
            for family,policy in TASKS:
                r=run_one(family,policy,cfg)
                state["jobs_completed"]+=1
                state["current_job"]=family+"/"+policy
                state["last_heartbeat"]=utc()
                save(STATUS,state)
            result=[]
            for fam,pol in TASKS:
                prev=check_original(fam,pol)
                new=load(OUTPUT/fam/pol/"native-audit.json")
                result.append({"family":fam,"policy":pol,
                   "original_minus_2pct_stress_usdt":prev["additional_25bp_stressed_net_usdt"],
                   "tight_minus_1pct_stress_usdt":new["stress_25bp_net_usdt"],
                   "difference_usdt":round(new["stress_25bp_net_usdt"]-prev["additional_25bp_stressed_net_usdt"],6),
                   "original_trades":prev["trades"],"tight_trades":new["trades"],
                   "tight_initial_stop_exits":new["exit_reasons"].get("stop_loss",0),
                   "tight_end_forced":new["historical_end_forced"]})
            save(OUTPUT/"comparison.json",{
                "schema":"nbot-v6-stop-one-vs-two-original-native-1",
                "strict_same_25coin_three_month_no_time_comparison":True,
                "historic_study_not_new_holdout":True,
                "no_live_paper_or_automatic_promotion":True,
                "pairs":result})
            state.update(status="complete_research_only",finished=utc(),current_job=None)
            save(STATUS,state)
            event("finished",jobs=16)
        except BaseException as e:
            state.update(status="blocked",error=str(e),updated=utc())
            save(STATUS,state)
            event("blocked",reason=str(e))
            raise

if __name__=="__main__":main()
