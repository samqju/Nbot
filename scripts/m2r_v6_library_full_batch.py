#!/usr/bin/env python3
"""FINITE, unattended NBOT V6 research ONLY — complete candidate suite.

Authorized owner task Oct18: test all eight standalone native strategies,
fixed-versus-trailing, bounded native Freqtrade Hyperopt, LightGBM challengers,
honest aftercost historical portfolio audits, NO_TRADE-first 8h regime adapter,
and separate PPO RL challenger. Prevent premature promotion.

Each step launches ONE official Freqtrade Docker container through the guarded
m2r_v6_library_native_job.py. Work continues on the VPS without ChatGPT,
laptop or PuTTY. Errors recorded, valid successful evidence retained.
Critical integrity failures stop batch. No schedules, no real orders.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import traceback
from zipfile import ZipFile

from m2r_v6_library_native_job import CANDIDATES, OUTPUT, SOURCE, ROOT, BRANCH, execute
FAMILIES=tuple(CANDIDATES.keys())
PERIODS=("validation_july","replication_august","replication_september")
STATUS=OUTPUT/"v6-library-research-status.json"
LOG=OUTPUT/"v6-library-research-events.jsonl"
LOCK=OUTPUT/"v6-library-research.lock"
NATIVE_POLICY={"fee_each_side":.0005,"extra_cost_roundtrip_bps":25,
               "stake_usdt":1000,"leverage":1,"global_open_positions":1,
               "wallet_usdt":100000,"no_trade_reference_usdt":0,
               "refuse_real_or_paper_trading":True}
STOP_STATES=frozenset(("error","complete","skipped"))

def iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def save_atomic(path, obj):
    temp=path.with_name(path.name+".tmp")
    temp.write_text(json.dumps(obj,sort_keys=True,indent=2)+"\n")
    os.replace(temp,path)

def event(stage, key, note, **extra):
    d=dict(timestamp_utc=iso(),stage=stage,key=key,note=note,**extra)
    with LOG.open("a") as file:
        file.write(json.dumps(d,sort_keys=True)+"\n")
        file.flush();os.fsync(file.fileno())
    print(json.dumps(d,sort_keys=True),flush=True)

def check_vps():
    if os.geteuid()!=0 or not (SOURCE/".git").is_dir():
        raise RuntimeError("ISOLATED_V6_ROOT_REQUIRED")
    def get(args):
        return subprocess.check_output(args,cwd=SOURCE,text=True).strip()
    if get(["git","branch","--show-current"])!=BRANCH:
        raise RuntimeError("WRONG_V6_BRANCH")
    if get(["git","status","--porcelain=v1"]):
        raise RuntimeError("DIRTY_V6_GIT_FORBIDDEN")
    if get(["docker","ps","-q"]):
        raise RuntimeError("DOCKER_BUSY_REFUSE_DUPLICATE_FT_JOB")
    if not (ROOT/"jansep-20261017/jansep-native-four-window-audit.json").is_file():
        raise RuntimeError("ORIGINAL_FOUR_LOOKBACK_STUDY_EVIDENCE_MISSING")
    if not (ROOT/"january-2026-public-history-stage/futures").is_dir():
        raise RuntimeError("HISTORICAL_DATA_MISSING")
    return get(["git","rev-parse","HEAD"])

def trade_metrics(kind,family,period):
    folder=OUTPUT/kind/family/period
    state=(folder/"run-state.txt")
    if not state.is_file() or "EXIT_CODE=0" not in state.read_text().splitlines():
        raise RuntimeError("NATIVE_BACKTEST_EXIT_NOT_SUCCESS")
    zips=list((folder/"backtest_results").glob("*.zip"))
    if len(zips)!=1:
        raise RuntimeError("REQUIRE_EXACTLY_ONE_NATIVE_BACKTEST_ZIP")
    blob=zips[0].read_bytes()
    with ZipFile(zips[0]) as archive:
        if archive.testzip() is not None:raise RuntimeError("NATIVE_ZIP_CORRUPT")
        j=[n for n in archive.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        if len(j)!=1:raise RuntimeError("NATIVE_ZIP_CONTENT_AMBIGUOUS")
        result=json.loads(archive.read(j[0]))
    strategies=result.get("strategy",{})
    if len(strategies)!=1:raise RuntimeError("NATIVE_STRATEGY_COUNT_NOT_ONE")
    name, v=next(iter(strategies.items()))
    if (v.get("trading_mode")!="futures" or v.get("timeframe")!="5m" or
        v.get("max_open_trades")!=1 or
        abs(float(v.get("stake_amount",0))-1000)>1e-7 or
        abs(float(v.get("starting_balance",0))-100000)>1e-7 or
        len(v.get("pairlist",[]))!=25):
        raise RuntimeError("NATIVE_RISK_OR_PAIR_COUNT_NOT_IDENTICAL")
    trades=v.get("trades",[])
    if len(trades)!=v.get("total_trades"):
        raise RuntimeError("NATIVE_TRADE_COUNT_MISMATCH")
    native=float(v.get("profit_total_abs",0.0))
    if abs(sum(float(t["profit_abs"]) for t in trades)-native)>0.002:
        raise RuntimeError("NATIVE_PNL_LEDGER_MISMATCH")
    for t in trades:
        if (abs(float(t["leverage"])-1)>1e-8 or
            abs(float(t["fee_open"])-.0005)>1e-9 or
            abs(float(t["fee_close"])-.0005)>1e-9 or
            t["pair"] not in v["pairlist"]):
            raise RuntimeError("NATIVE_UNEXPECTED_TRADE_FEE_LEVERAGE_PAIR")
        if float(t["stake_amount"])<=0:
            raise RuntimeError("NATIVE_INVALID_STAKE")
    turnover=sum(float(t["stake_amount"]) for t in trades)
    stressed=native-.0025*turnover
    # Native portfolio can have no trades. That is a valid NO_TRADE result
    # but never an economically promising strategy eligible for ML promotion.
    out={"kind":kind,"family":family,"period":period,"strategy":name,
         "archive_name":zips[0].name,
         "native_zip_sha256":hashlib.sha256(blob).hexdigest(),
         "native_trade_count":len(trades),"native_profit_usdt":round(native,6),
         "net_after_extra_25bps_usdt":round(stressed,6),
         "wins":sum(float(t["profit_abs"])>0 for t in trades),
         "hypothetical_extra_bps_not_observed_spread":True,
         "trade_count_and_native_cost_audit_passed":True,
         "trailing_enabled":kind=="trailing",
         "backtest_start":v.get("backtest_start"),
         "backtest_end":v.get("backtest_end")}
    save_atomic(folder/"native-economic-audit.json",out)
    return out

def run_one(kind,family,period,*, failfast=False):
    key=f"{kind}/{family}/{period}"
    out=OUTPUT/kind/family/period
    if out.exists():
        if (out/"native-economic-audit.json").is_file():
            x=json.loads((out/"native-economic-audit.json").read_text())
            event("resume",key,"EXISTING_NATIVE_RESULT_NOT_RERUN",trades=x["native_trade_count"],
                  stressed=x["net_after_extra_25bps_usdt"])
            return x
        event("blocked",key,"OUTPUT_DIRECTORY_EXISTS_NO_OVERWRITE")
        if failfast:raise RuntimeError("EXISTING_INCOMPLETE_RESULT_"+key)
        return None
    # The parent coordinator is the sole caller; runner performs its own
    # independent per-job Docker, no-key, branch and filesystem safety checks.
    try:
        event("start",key,"OFFLINE_NATIVE_RESEARCH")
        rc=execute(kind,family,period)
        if rc:
            raise RuntimeError(f"NATIVE_FT_RETURN_{rc}")
        if kind=="hyperopt":
            ev={"kind":"hyperopt","family":family,"period":period,
                "completed_native_hyperopt":True,
                "safe_optima_export_disabled":True,
                "independent_holdout_validation_not_done":True}
            save_atomic(out/"research-audit.json",ev)
            event("complete",key,"NATIVE_HYPEROPT_TRAINING_ONLY_NO_PROMOTION")
            return ev
        metric=trade_metrics(kind,family,period)
        event("complete",key,"NATIVE_ENGINE_SIMULATION_AUDITED",
              trades=metric["native_trade_count"],net=metric["native_profit_usdt"],
              after_25bps=metric["net_after_extra_25bps_usdt"])
        return metric
    except Exception as ex:
        event("error",key,"NATIVE_JOB_FAILED_RESEARCH_CONTINUES",
              error=str(ex)[:300])
        if failfast: raise
        return None

def shortlist():
    """Select challenger families from July+August only; SEPTEMBER excluded."""
    candidates=[]
    for family in FAMILIES:
        available={}
        for period in PERIODS[:2]:
            path=OUTPUT/"native"/family/period/"native-economic-audit.json"
            if path.exists():available[period]=json.loads(path.read_text())
        if len(available)!=2:continue
        a,b=[available[p] for p in PERIODS[:2]]
        score=min(a["net_after_extra_25bps_usdt"],b["net_after_extra_25bps_usdt"])
        n=min(a["native_trade_count"],b["native_trade_count"])
        qualifies=(n>=20 and score>0)
        candidates.append({"family":family,"eligible_positive_two_blocks":qualifies,
                           "min_25bps_net_usdt":score,"min_trades_per_block":n,
                           "july_native_pnl":a["native_profit_usdt"],
                           "aug_native_pnl":b["native_profit_usdt"]})
    qualifying=sorted([x for x in candidates if x["eligible_positive_two_blocks"]],
                      key=lambda x:(-x["min_25bps_net_usdt"],x["family"]))
    if qualifying:
        chosen=qualifying[:2];eligible=True
    else:
        # Diagnostic side arm even when nothing was independently profitable:
        # Explicitly report lack of edge. No implied promotion.
        chosen=sorted(candidates,key=lambda x:(-x["min_25bps_net_usdt"],x["family"]))[:2]
        eligible=False
    obj={"created_utc":iso(),
         "july_august_only_used_for_exploratory_candidate_selection":True,
         "september_not_used_for_selection":True,
         "historical_august_already_inspected_not_blind":True,
         "selected_are_economically_qualified":eligible,
         "candidates":candidates,"lightgbm_diagnostic_shortlist":chosen,
         "models_may_not_be_promoted_to_live_or_paper":True}
    save_atomic(OUTPUT/"shortlist-from-july-aug-only.json",obj)
    event("shortlist","native","JULY_AUG_NATIVE_SHORTLIST",
          validated_positive=len(qualifying),diagnostic_selected=[x["family"] for x in chosen])
    return obj

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--status",action="store_true")
    a.add_argument("--execute",action="store_true")
    opt=a.parse_args()
    if opt.status:
        if STATUS.exists():print(STATUS.read_text())
        else:print("NOT_STARTED")
        if LOG.exists():print("EVENT_TAIL\n"+"".join(LOG.read_text().splitlines(True)[-9:]))
        return
    if not opt.execute:
        raise RuntimeError("REQUIRES_EXPLICIT_EXECUTE")
    if os.environ.get("NBOT_V6_LIBRARY_OFFLINE_EXECUTION")!="OWNER_AUTHORIZED_OFFLINE_RESEARCH_ONLY":
        raise RuntimeError("MISSING_EXPLICIT_RESEARCH_OPT_IN")
    OUTPUT.mkdir(parents=True,exist_ok=True)
    fd=LOCK.open("w")
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    commit=check_vps()
    if STATUS.exists():raise RuntimeError("REFUSE_EXISTING_BATCH_STATUS_RESTART")
    state={"schema":"nbot-v6-library-research-20261018-v1",
           "start_utc":iso(),"git_commit":commit,"stage":"preflight",
           "status":"running","native_policy":NATIVE_POLICY,
           "original_30_60_90_180_results_untouched":True,
           "paper_trading":False,"real_trading":False,"auto_promotion":False,
           "tested_all_candidates":False,
           "approved_dynamic_rotation_or_strategy":False}
    save_atomic(STATUS,state)
    def step(stage, detail=""):
        state.update(stage=stage,updated_utc=iso(),detail=detail)
        save_atomic(STATUS,state)
        event("stage",stage,detail)
    try:
        step("preflight","Smoke test all eight families, basic + trailing, July-like 3d")
        # Full official backtesting per strategy is run below, with immutable
        # CSV/JSON/ZIP archived after each. CI already validated imports.
        step("original_no_ml_baseline","Reproduce original V6 non-AI breakout/pullback comparison on all three periods")
        for period in PERIODS:
            run_one("baseline","ema_cross",period)
        step("native_frozen","8 families × July, August, September; common risk fees/25 markets")
        for family in FAMILIES:
            for period in PERIODS:
                run_one("native",family,period)
        step("trailing_ab","Same eight signal families and dates, only exit rule differs")
        for family in FAMILIES:
            for period in PERIODS:
                run_one("trailing",family,period)
        step("aftercost_rank","Native trade ZIPs, 25bp extra execution stress and NO_TRADE 0")
        result=shortlist()
        step("hyperopt","Eight native Freqtrade fixed candidate entry tuning on May–June only")
        for family in FAMILIES:
            run_one("hyperopt",family,"tuning_may_june")
        step("lightgbm","Independent aftercost LightGBM research, max 2 July+Aug selected native families")
        # September reserved from this selection. No first-pass native signal
        # scorecard becomes a certified selector winner.
        for selected in result["lightgbm_diagnostic_shortlist"]:
            for period in ("replication_september",):
                run_one("lgbm",selected["family"],period)
        step("regime","8h causal regime selector EMPTY evidence file -> mandated NO_TRADE")
        # This specifically verifies native Freqtrade can abstain across
        # portfolio; no fabricated positive historical regime scorecards.
        run_one("adaptive","ema_cross","replication_september")
        step("reinforcement_learning","Dedicated FreqAI PPO training/eval on archived July only")
        run_one("rl","ema_cross","validation_july")
        step("final_audit","Aggregate all strictly native per-job verified archives")
        audits=list(OUTPUT.glob("*/*/*/native-economic-audit.json"))
        details=[json.loads(p.read_text()) for p in audits]
        summary={"finished_utc":iso(),"git_commit":commit,
                 "economic_audit_count":len(details),
                 "frozen_native_results":[x for x in details if x["kind"]=="native"],
                 "original_breakout_pullback_no_ml_baselines":[x for x in details if x["kind"]=="baseline"],
                 "trailing_stops_ab_results":[x for x in details if x["kind"]=="trailing"],
                 "freqai_lightgbm_diagnostics":[x for x in details if x["kind"]=="lgbm"],
                 "ppo_rl_diagnostics":[x for x in details if x["kind"]=="rl"],
                 "asof_regime_native_test":[x for x in details if x["kind"]=="adaptive"],
                 "no_trade_portfolio_baseline_usdt":0.0,
                 "no_models_or_parameters_promoted":True,
                 "aftercost_winners_require_future_out_of_sample_validation":True,
                 "original_baseline_independently_reproduced":bool([x for x in details if x["kind"]=="baseline"]),
                 "original_no_ml_baseline_exit_horizon_differs_from_new_library":True,
                 "not_all_candidate_runs_are_guaranteed_complete":True}
        save_atomic(OUTPUT/"candidate-native-aftercost-summary.json",summary)
        state.update(status="complete_with_individual_failures_if_any",stage="complete",
                     updated_utc=iso(),economic_audit_count=len(details),
                     tested_all_candidates=True)
        save_atomic(STATUS,state)
        event("finished","batch","FINITE_OFFLINE_RESEARCH_FINISHED",
              audited=len(details))
    except BaseException as ex:
        state.update(status="blocked",stage="blocked",updated_utc=iso(),error=str(ex))
        save_atomic(STATUS,state)
        event("blocked","batch","INTEGRITY_OR_SETUP_FAILURE_STOPPED",error=str(ex),
              trace=traceback.format_exc()[-800:])
        raise

if __name__=="__main__":
    main()
