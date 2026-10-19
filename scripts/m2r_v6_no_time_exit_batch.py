#!/usr/bin/env python3
"""Nbot V6 finite, sequential and OFFLINE NATIVE no-time-limit A/B.

Original 8 library technical entry families; two exits:
- FIXED: +5% ROI or -2% initial stop; NO 60-minute custom_exit.
- TRAILING: same ROI/stop, plus original +2% activation, 1% trailing gap.
On finite historical data Freqtrade force-closes still-open positions at the
end of each backtest. Log those events explicitly. Monthly 3× comparisons
against original 60m same-family result PLUS full Jul-Sep continuous windows
which mitigate monthly terminal forced exits. 8×2×(3+1)=64 native jobs.

Offline only; never paper/live; original Stage1/2/3 files unchanged.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
from zipfile import ZipFile

ROOT=Path("/root/nbot-v6-m1-20261016")
SOURCE=ROOT/"global-next-source"
ORIGINAL=ROOT/"library-20261018"
HISTORY=ROOT/"january-2026-public-history-stage"
OUTPUT=ROOT/"no-time-exit-20261019"
BRANCH="prototype/v6-freqtrade-freqai-20261016"
OLD_ENTRY_COMMIT="aa97a32c9af73ae63503f5dbff63d98a7fe32200"
OPTIN="OWNER_AUTHORIZED_BACKTEST_ONLY"
IMAGE="freqtradeorg/freqtrade:stable_freqai"
FAMILIES={
    "ema_cross":"EmaCross",
    "donchian_breakout":"Donchian",
    "bollinger_reversion":"Bollinger",
    "rsi_reversion":"Rsi",
    "macd_momentum":"Macd",
    "stochastic_reversal":"Stochastic",
    "atr_breakout":"AtrBreakout",
    "volume_trend":"VolumeTrend",
}
POLICIES=("fixed","trailing")
PERIODS={
    "validation_july":"20260701-20260801",
    "replication_august":"20260801-20260901",
    "replication_september":"20260901-20261001",
    "full_july_september":"20260701-20261001",
}
MONTHS=tuple(k for k in PERIODS if k!="full_july_september")
STATUS=OUTPUT/"status.json"
EVENTS=OUTPUT/"events.jsonl"
LOCK=OUTPUT/"singleton.lock"
TOTAL=len(FAMILIES)*len(POLICIES)*len(PERIODS)

def now():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def sha_file(p):
    h=hashlib.sha256()
    with p.open("rb") as fd:
        for chunk in iter(lambda:fd.read(2*1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()
def cmd(*args):
    return subprocess.check_output(args,text=True).strip()
def require(cond,reason):
    if not cond:raise RuntimeError(reason)
def read(p):
    return json.loads(p.read_text())
def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_name(p.name+".tmp")
    temp.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")
    os.replace(temp,p)
def event(kind,**kw):
    e={"event":kind,"at_utc":now(),**kw}
    with EVENTS.open("a") as f:
        f.write(json.dumps(e,sort_keys=True)+"\n")
        f.flush();os.fsync(f.fileno())
    print(json.dumps(e,sort_keys=True),flush=True)

def original_audit(kind,family,period):
    record=ORIGINAL/kind/family/period/"native-economic-audit.json"
    require(record.is_file(),"ORIGINAL_MISSING_ECONOMIC_AUDIT")
    audit=read(record)
    z=ORIGINAL/kind/family/period/"backtest_results"/audit["archive_name"]
    require(z.is_file() and sha_file(z)==audit["native_zip_sha256"],
            "ORIGINAL_NATIVE_SHA256_MISMATCH")
    require(audit["trade_count_and_native_cost_audit_passed"] is True,
            "ORIGINAL_NATIVE_FEES_NOT_VERIFIED")
    return audit

def preflight():
    require(os.geteuid()==0,"ROOT_VPS_REQUIRED")
    require(os.environ.get("NBOT_V6_NO_TIME_OFFLINE")==OPTIN,
            "EXPLICIT_OFFLINE_ONLY_AUTHORIZATION_REQUIRED")
    require(SOURCE.is_dir() and (SOURCE/".git").is_dir(),"ISOLATED_CHECKOUT_MISSING")
    require(cmd("git","-C",str(SOURCE),"branch","--show-current")==BRANCH,
            "WRONG_BRANCH")
    require(not cmd("git","-C",str(SOURCE),"status","--porcelain=v1"),
            "DIRTY_RESEARCH_CHECKOUT")
    require(subprocess.run(["git","-C",str(SOURCE),"diff","--quiet",
                            OLD_ENTRY_COMMIT,"HEAD","--",
                            "user_data/strategies/NbotV6LibraryResearch.py"],
                            check=False).returncode==0,
            "ORIGINAL_LIBRARY_ENTRY_SIGNALS_CHANGED")
    require(not cmd("docker","ps","-q"),"RESEARCH_DOCKER_BUSY")
    for service in ("nbot-v6-library-recovery-20261018.service",
                    "nbot-v6-profit-protection-next-20261018.service",
                    "nbot-v6-global-20261018.service"):
        state=subprocess.run(["systemctl","is-active","--quiet",service],check=False)
        require(state.returncode!=0,"PRIOR_RESEARCH_SERVICE_STILL_RUNNING_"+service)
    st2=read(ORIGINAL/"profit-protection-next-phase/status.json")
    st3=read(ROOT/"global-25x8-20261018/progress.json")
    require(st2.get("new_native_archive_count")==120
            and st2.get("status")=="complete_offline_not_release_ready",
            "ORIGINAL_PROFIT_RESEARCH_NOT_COMPLETE")
    require(st3.get("jobs_completed")==12
            and st3.get("status")=="complete_research_only",
            "ORIGINAL_AI_RESEARCH_NOT_COMPLETE")
    cfg=read(SOURCE/"user_data/config.v6-library-native-offline.json")
    expected={
      "dry_run":True,"nbot_live_mode":False,"nbot_paper_research_mode":False,
      "nbot_v6_library_research_only":True,"max_open_trades":1,
      "stake_amount":1000,"force_entry_enable":False}
    for k,v in expected.items():
        require(cfg.get(k)==v,"UNSAFE_RESEARCH_CONFIG_"+k)
    require(cfg.get("exchange")=={"key":"","secret":""},
            "EXCHANGE_CREDENTIALS_NOT_EMPTY")
    require(cfg.get("freqai",{}).get("enabled") is False
            and cfg.get("api_server",{}).get("enabled") is False
            and cfg.get("telegram",{}).get("enabled") is False,
            "NOT_STRICT_OFFLINE_OR_FREQAI_ENABLED")
    p=read(SOURCE/"user_data/config.json")
    require(len(p["exchange"]["pair_whitelist"])==25
            and len(set(p["exchange"]["pair_whitelist"]))==25
            and p.get("trading_mode")=="futures"
            and p.get("margin_mode")=="isolated",
            "ORIGINAL_FUTURES_25_UNIVERSE_MISMATCH")
    for family in FAMILIES:
        for period in MONTHS:
            original_audit("native",family,period)
            original_audit("trailing",family,period)
    require((HISTORY/"futures").is_dir(),"HISTORICAL_DATA_MISSING")
    require((SOURCE/"user_data/strategies/NbotV6NoTimeLimitResearch.py").is_file(),
            "NO_TIME_STRATEGY_MISSING")
    return cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),cfg

def native_audit(folder,policy,family,period):
    zipfiles=list((folder/"backtest_results").glob("*.zip"))
    require(len(zipfiles)==1,"REQUIRE_ONE_NATIVE_ZIP")
    z=zipfiles[0]
    with ZipFile(z) as f:
        require(f.testzip() is None,"CORRUPT_NATIVE_ZIP")
        names=[n for n in f.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        require(len(names)==1,"AMBIGUOUS_NATIVE_JSON")
        doc=json.loads(f.read(names[0]))
    require(len(doc.get("strategy",{}))==1,"STRATEGY_COUNT_NOT_ONE")
    strategy,info=next(iter(doc["strategy"].items()))
    expect="NbotV6"+FAMILIES[family]+("NoTimeFixedResearch" if policy=="fixed" else "NoTimeTrailingResearch")
    require(strategy==expect,"STRATEGY_MISMATCH")
    require(info.get("trading_mode")=="futures"
            and info.get("max_open_trades")==1
            and info.get("timeframe")=="5m"
            and len(info.get("pairlist",[]))==25
            and abs(float(info.get("starting_balance",0))-100000)<1e-8
            and abs(float(info.get("stake_amount",0))-1000)<1e-8,
            "NATIVE_PORTFOLIO_MISMATCH")
    trades=info.get("trades",[])
    require(info.get("total_trades")==len(trades),"NATIVE_TRADE_COUNT_MISMATCH")
    pnl=float(info.get("profit_total_abs",0))
    require(abs(sum(float(t["profit_abs"]) for t in trades)-pnl)<0.002,
            "NATIVE_PNL_LEDGER_MISMATCH")
    reason={}; durations=[]; turnover=0
    for t in trades:
        require(abs(float(t["leverage"])-1)<1e-8
                and abs(float(t["fee_open"])-.0005)<1e-9
                and abs(float(t["fee_close"])-.0005)<1e-9
                and t["pair"] in info["pairlist"],
                "NATIVE_LEVERAGE_OR_FEE_OR_PAIR_MISMATCH")
        why=str(t.get("exit_reason","MISSING"))
        require(why!="v6_library_60m_exit" and why!="global_60m_limit",
                "TIME_EXIT_NOT_ACTUALLY_DISABLED")
        reason[why]=reason.get(why,0)+1
        turnover+=float(t["stake_amount"])
        import datetime
        start=datetime.datetime.fromisoformat(t["open_date"])
        end=datetime.datetime.fromisoformat(t["close_date"])
        require(end>=start,"INVALID_TRADE_TIMESTAMP")
        durations.append((end-start).total_seconds()/60)
    note={
     "schema":"nbot-v6-no-time-freqtrade-native-1",
     "family":family,"period":period,"policy":policy,
     "strategy":strategy,"source_commit":cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),
     "file":z.name,"native_zip_sha256":sha_file(z),
     "trades":len(trades),"winning_trades":sum(float(x["profit_abs"])>0 for x in trades),
     "native_net_usdt":round(pnl,6),
     "additional_25bp_stressed_net_usdt":round(pnl-.0025*turnover,6),
     "exit_reasons":reason,
     "force_exits_at_historical_end_count":reason.get("force_exit",0),
     "holding_minutes_mean":round(statistics.mean(durations),2) if durations else None,
     "holding_minutes_median":round(statistics.median(durations),2) if durations else None,
     "holding_minutes_p90":round(sorted(durations)[int((len(durations)-1)*.9)],2) if durations else None,
     "max_holding_minutes":round(max(durations),2) if durations else None,
     "native_fee_each_side":.0005,"additional_stress_is_hypothetical_not_spread":True,
     "native_one_slot_1000usdt_stake":True,
     "no_60minute_custom_exit":True,
     "historical_backtest_end_forced_exits_are_unavoidable":True,
     "no_paper_live_or_auto_promotion":True}
    save(folder/"native-audit.json",note)
    return note

def plan(source_sha):
    tasks=[(k,p,f,t) for f in FAMILIES for p in POLICIES
           for t in PERIODS for k in (["no_time_fixed"] if p=="fixed" else ["no_time_trailing"])]
    return tasks

def one_job(kind,policy,family,period,config):
    out=OUTPUT/kind/family/period
    name=f"{kind}/{family}/{period}"
    auditfile=out/"native-audit.json"
    if auditfile.exists():
        old=read(auditfile)
        z=out/"backtest_results"/old["file"]
        require(z.is_file() and sha_file(z)==old["native_zip_sha256"],
                "RESUMED_NATIVE_ZIP_CHANGED")
        event("resume",job=name)
        return old
    require(not out.exists(),"PARTIAL_NO_TIME_RESULT_MANUAL_REVIEW_"+name)
    out.mkdir(parents=True)
    os.chown(out,1000,1000)
    os.chmod(out,0o750)
    overlay=out/"exact-overlay.json"
    save(overlay,config)
    os.chmod(overlay,0o644)
    cls="NbotV6"+FAMILIES[family]+("NoTimeFixedResearch" if policy=="fixed" else "NoTimeTrailingResearch")
    command=[
     "timeout","-s","TERM","-k","60","14400",
     "docker","run","--rm","--name","nbot-v6-no-time-native-single-offline",
     "--network","bridge","--cpus=2","--memory=6g",
     "--cap-drop","ALL","--security-opt","no-new-privileges",
     "-v",str(SOURCE)+":/research:ro",
     "-v",str(HISTORY)+":/history:ro",
     "-v",str(out)+":/results",
     "--entrypoint","freqtrade","freqtradeorg/freqtrade:stable_freqai",
     "backtesting","-c","/research/user_data/config.json",
     "-c","/results/exact-overlay.json","--userdir","/results",
     "--datadir","/history",
     "--strategy",cls,"--strategy-path","/research/user_data/strategies",
     "--timerange",PERIODS[period],"--fee","0.0005",
     "--cache","none","--export","trades","--enable-protections"]
    event("start",job=name,strategy=cls)
    log=out/"native.log"
    with log.open("w") as fd:
        proc=subprocess.run(command,stdout=fd,stderr=subprocess.STDOUT,check=False)
    save(out/"run-state.json",{"exit_code":proc.returncode,"finished":now()})
    require(proc.returncode==0,"FREQTRADE_NATIVE_JOB_FAILED_"+str(proc.returncode)+"_"+name)
    obj=native_audit(out,policy,family,period)
    event("complete",job=name,trades=obj["trades"],native_net=obj["native_net_usdt"],
          stressed_net=obj["additional_25bp_stressed_net_usdt"],
          forced_end=obj["force_exits_at_historical_end_count"])
    return obj

def finalize(tasks):
    report={"schema":"nbot-v6-no-time-exit-ab-comparison-1",
            "source_commit":cmd("git","-C",str(SOURCE),"rev-parse","HEAD"),
            "unmodified_60m_baselines_proven_sha256":True,
            "same_entries_25coins_5m_stake_and_fee":True,
            "no_trading":True,"no_auto_promotion":True,
            "native_monthly_comparisons":[],"continuous_july_september":[]}
    for fam in FAMILIES:
        for pol in POLICIES:
            kind="no_time_fixed" if pol=="fixed" else "no_time_trailing"
            old_kind="native" if pol=="fixed" else "trailing"
            new=[];old=[]
            for period in MONTHS:
                old.append(original_audit(old_kind,fam,period))
                new.append(read(OUTPUT/kind/fam/period/"native-audit.json"))
            old_native=sum(x["native_profit_usdt"] for x in old)
            old_stress=sum(x["net_after_extra_25bps_usdt"] for x in old)
            new_native=sum(x["native_net_usdt"] for x in new)
            new_stress=sum(x["additional_25bp_stressed_net_usdt"] for x in new)
            report["native_monthly_comparisons"].append({
              "family":fam,"policy":pol,
              "original_60m_native_usdt":round(old_native,4),
              "unlimited_native_usdt":round(new_native,4),
              "delta_native_usdt":round(new_native-old_native,4),
              "original_60m_stressed_usdt":round(old_stress,4),
              "unlimited_stressed_usdt":round(new_stress,4),
              "delta_stressed_usdt":round(new_stress-old_stress,4),
              "original_60m_trade_count":sum(x["native_trade_count"] for x in old),
              "unlimited_trade_count":sum(x["trades"] for x in new),
              "unlimited_month_end_forced_count":sum(x["force_exits_at_historical_end_count"] for x in new),
              "all_three_months_same_25coin_stake_and_fees":True,
              "not_one_combined_strategy_portfolio":True})
            extended=read(OUTPUT/kind/fam/"full_july_september/native-audit.json")
            report["continuous_july_september"].append(extended)
    save(OUTPUT/"final-comparison.json",report)
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--execute",action="store_true")
    ap.add_argument("--status",action="store_true")
    args=ap.parse_args()
    if args.status:
        if STATUS.exists():print(STATUS.read_text())
        else:print("NOT_STARTED")
        if EVENTS.exists():
            print("LAST_EVENTS")
            print("".join(EVENTS.read_text().splitlines(True)[-6:]))
        return
    require(args.execute,"EXPLICIT_EXECUTE_REQUIRED")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with LOCK.open("w") as fd:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        sha,config=preflight()
        tasks=plan(sha)
        if STATUS.exists():
            state=read(STATUS)
            require(state.get("source_commit")==sha and state.get("status") in ("running","blocked"),
                    "CANNOT_RESUME_DIFFERENT_CODE_OR_COMPLETED_JOB")
        else:
            state={"schema":"nbot-v6-no-time-exit-progress-1",
                   "status":"running","jobs_total":TOTAL,"jobs_completed":0,
                   "source_commit":sha,"started":now(),
                   "paper_trading":False,"live_trading":False,
                   "one_global_1000usdt_position":True,
                   "no_auto_promotion":True,
                   "retains_original_60m_evidence":True}
            save(STATUS,state)
        try:
            for kind,pol,fam,period in tasks:
                one_job(kind,pol,fam,period,config)
                state.update(status="running",
                             jobs_completed=sum((OUTPUT/k/f/t/"native-audit.json").is_file() for k,p,f,t in tasks),
                             current_job=f"{kind}/{fam}/{period}",updated=now())
                save(STATUS,state)
            result=finalize(tasks)
            state.update(status="complete_research_only",
                         jobs_completed=TOTAL,
                         no_time_native_monthly_comparisons=len(result["native_monthly_comparisons"]),
                         no_time_continuous_native_backtests=len(result["continuous_july_september"]),
                         finished=now(),current_job=None)
            save(STATUS,state)
            event("finished",jobs=TOTAL)
        except BaseException as e:
            state.update(status="blocked",error=str(e),updated=now())
            save(STATUS,state)
            event("blocked",reason=str(e))
            raise

if __name__=="__main__":
    main()
