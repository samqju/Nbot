"""Audit native months of JAN-SEP 2026 rolling 7-day FreqAI research windows.

Read actual Freqtrade closed simulated trades ONLY. Does not transform
hypothetical opportunity labels into executed portfolio outcomes. Fail closed
unless all model fits and dates are present.
"""
from __future__ import annotations
import argparse,hashlib,json,re,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from zipfile import ZipFile


def extract_archive(folder:Path):
    x=list((folder/"backtest_results").glob("*.zip"))
    if len(x)!=1:
        raise RuntimeError(f"REQUIRE_ONE_NATIVE_ZIP_{folder} count={len(x)}")
    with ZipFile(x[0]) as z:
        j=[n for n in z.namelist() if n.endswith(".json") and not n.endswith("_config.json")]
        if len(j)!=1:
            raise RuntimeError("BAD_NATIVE_BACKTEST_ZIP_LAYOUT")
        v=json.loads(z.read(j[0]))
        if set(v["strategy"])!={"NbotV6TradeOutcomeFundingResearch"}:
            raise RuntimeError("UNEXPECTED_STRATEGY")
        return x[0],v["strategy"]["NbotV6TradeOutcomeFundingResearch"]


def inspect(root:Path,lookback:int,start:str,end:str):
    folder=root/f"w{lookback}"
    state=(folder/"run-state.txt").read_text()
    if ("EXIT_CODE=0" not in state
            and "NATIVE_ARCHIVE_VERIFIED_WITHOUT_LAUNCHER_EXIT=1" not in state):
        raise RuntimeError(f"NOT_COMPLETED_NATIVE_ARCHIVE_WINDOW {lookback}")
    archive,stats=extract_archive(folder)
    identifier=f"nbot-v6-m2r-jansep2026-{lookback}d-20261017"
    assert stats["freqai_identifier"]==identifier
    assert stats["backtest_start"]==f"{start[:4]}-{start[4:6]}-{start[6:]} 00:00:00"
    assert stats["backtest_end"]==f"{end[:4]}-{end[4:6]}-{end[6:]} 00:00:00"
    assert (stats["max_open_trades"]==1 and float(stats["stake_amount"])==1000
            and float(stats["starting_balance"])==100000)
    assert (len(stats["pairlist"])==25 and stats["trading_mode"]=="futures"
            and stats["timeframe"]=="5m")
    log_paths=([folder/"freqtrade.log"] if (folder/"freqtrade.log").is_file() else [])
    log_paths+=sorted(folder.glob("attempt-*.log"))
    text="\n".join(p.read_text(errors="replace") for p in log_paths)
    if "boundary_violations=" not in text:
        raise RuntimeError("TRAINING_BOUNDARY_EVIDENCE_MISSING")
    fitting=re.findall(r"boundary_violations=(\d+)",text)
    if not fitting or any(x!="0" for x in fitting):
        raise RuntimeError("NONZERO_SPLIT_OVERLAP")
    models=list((folder/"models"/identifier).glob("sub-train-*/*_model.joblib"))
    expected_segments=math.ceil((datetime.strptime(end,"%Y%m%d")-datetime.strptime(start,"%Y%m%d")).days/7)
    expected_fitted=25*expected_segments
    if len(models)!=expected_fitted:
        raise RuntimeError(f"FITTED_ARTIFACT_COUNT_MISMATCH found={len(models)} expected={expected_fitted}")
    # The original 30-day SSH parent disconnected while the native Freqtrade
    # container completed its 825 model fits. Its stdout log therefore covers
    # only a prefix of model-fits, despite all binaries and the native ZIP
    # being intact. Never assert zero violations for the UNLOGGED fits.
    if len(fitting)>len(models):
        raise RuntimeError(f"UNEXPECTED_DUPLICATED_PURGE_LOGGING fits={len(fitting)} models={len(models)}")
    if len(fitting)<len(models) and lookback!=30:
        raise RuntimeError(f"TRUNCATED_PURGE_LOGGING_UNEXPECTED lookback={lookback}")
    if len(fitting)<1:
        raise RuntimeError("MISSING_NATIVE_PURGE_EVIDENCE")
    trades=stats["trades"]
    if stats["total_trades"]!=len(trades):
        raise RuntimeError("ENGINE_TRADE_COUNT_MISMATCH")
    monthly=defaultdict(list)
    stake_total=0
    for t in trades:
        assert abs(float(t["fee_open"])-.0005)<1e-12
        assert abs(float(t["fee_close"])-.0005)<1e-12
        assert abs(float(t["leverage"])-1)<1e-7
        assert .90*1000<=float(t["stake_amount"])<=1.1*1000
        stake_total+=float(t["stake_amount"])
        stamp=t["close_date"]
        month=str(stamp)[:7]
        monthly[month].append(t)
    net=sum(float(t["profit_abs"]) for t in trades)
    assert abs(net-float(stats["profit_total_abs"]))<=.001
    result_months={}
    for m,rows in sorted(monthly.items()):
        turn=sum(float(t["stake_amount"]) for t in rows)
        pnl=sum(float(t["profit_abs"]) for t in rows)
        result_months[m]={
            "closed_trades":len(rows),
            "engine_pnl_after_fees_funding_usdt":round(pnl,6),
            "additional_execution_bps_roundtrip_stress_usdt":{
                str(bp):round(pnl-bp*turn/10000,6) for bp in (0,10,15,25)},
            "month_attribution":"Trade close month, not monthly NAV mark-to-market",
        }
    return {
        "lookback_days":lookback,
        "period":f"{start}-{end}",
        "native_fitted_models":len(models),
        "one_model_per_pair_every_7d_train_segments":len(models)//25,
        "chronological_embargo_fit_checks_evidenced_in_logs":len(fitting),
        "missing_embargo_fit_log_entries_due_to_disconnected_original_launcher":len(models)-len(fitting),
        "verified_logged_training_label_boundary_violations":0,
        "all_model_fit_embargo_logs_verified":len(fitting)==len(models),
        "native_portfolio_trades":len(trades),
        "native_pnl_after_engine_fees_funding_usdt":round(net,6),
        "max_native_drawdown_usdt":round(float(stats["max_drawdown_abs"]),6),
        "cost_stress_all_time":{str(bp):round(net-bp*stake_total/10000,6) for bp in (0,10,15,25)},
        "monthly_actual_native_closed_trades":result_months,
        "archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--completed-lookbacks",type=int,nargs="+",required=True)
    a=p.parse_args()
    starts={30:"20260215",60:"20260315",90:"20260415",180:"20260715"}
    rows=[inspect(a.root,w,starts[w],"20261001") for w in a.completed_lookbacks]
    result={
        "native_long_rolling_JanSep2026_offline_runs":rows,
        "precise_scope":"Only completed actual native rolling 7day FreqAI jobs, unequal feasible warmup periods",
        "common_matched_2026Jul15_Sep30_analysis_completed":False,
        "full_four_window_JanSep_study_complete":set(a.completed_lookbacks)==set(starts),
        "original_nonAI_full_year_comparison_completed":False,
        "data_is_preregistered_but_some_outcomes_previously_seen":True,
        "true_historical_spread_and_real_stop_fills_observed":False,
        "no_trade_baseline_usdt":0,
        "paper_trading_started":False,
        "approval":"M2 NO-GO",
    }
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print("CERTIFIED_NATIVE_LONG_HISTORY_JOBS",
          [(r["lookback_days"],r["native_fitted_models"],r["native_portfolio_trades"],r["native_pnl_after_engine_fees_funding_usdt"]) for r in rows],flush=True)


if __name__=="__main__":
    main()
