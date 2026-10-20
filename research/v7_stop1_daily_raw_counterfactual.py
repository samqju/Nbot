#!/usr/bin/env python3
"""Offline 1% stop vs frozen 2% FreqAI daily RAW forecasts.

Recompute ALL three-coin matured V7 opportunity trade outcomes on original
source-verified 5m OHLCV and funding, under 1% stop and otherwise identical
RiskPolicy, using the shared PaperBroker. Keep prior 2% source DB and 273
model prediction artifacts untouched. The resulting new database is labeled
as COUNTERFACTUAL_1PCT, not as a training-certified 1%-target model.

The one-slot replay is executed again against this new outcome database:
shorter stop release times can lead to DIFFERENT subsequent entries.
Never mutate source models, trading runtime or place exchange orders.
"""
from __future__ import annotations
import argparse
from bisect import bisect_left
from collections import Counter
from pathlib import Path
import json
import sqlite3
from hashlib import sha256
from time import monotonic

from nbot_v7.data import BAR_MS, discover,discover_funding,load_bars,load_funding
from nbot_v7.experiment import replay,month_start
from nbot_v7.freqai_research_bridge import FreqAINetResearchBrain
from nbot_v7.runtime.risk import RiskPolicy
from nbot_v7.runtime.broker import PaperBroker
from research.v7_trailingstop1_broker import PreviousBarTrailingOnePercentBroker
from nbot_v7.lab import STOP_FRACTION,TAKE_FRACTION,HORIZON_BARS,LABEL_POLICY,con
from nbot_v7.artifacts import EventLog
from research.freqai_v7_net_fit_and_replay import digest

SYMBOLS=("BTCUSDT","ETHUSDT","SOLUSDT")
MONTHS={f"{y}-{m:02d}" for y,mm in ((2025,range(7,13)),(2026,range(1,10))) for m in mm}
STOP1=.01
START=month_start("2026-01")
END=month_start("2026-10")
POLICY="V7_5M_PAPER_BROKER_1STOP_3TAKE_60M_FEE10BP_SLIP2BP_PROXY_CF_V1"
TRAILING_POLICY="V7_5M_PREVIOUS_BAR_TRAILING_1STOP_3TAKE_60M_FEE10BP_SLIP2BP_PROXY_CF_V1"


def broker_outcome(bars,i,side,*,stop_fraction,funding,funding_times,trailing=False):
    if trailing and abs(stop_fraction-.01)>1e-12:
        raise ValueError('TRAILING_MUST_START_WITH_ONE_PERCENT_STOP')
    broker=PreviousBarTrailingOnePercentBroker() if trailing else PaperBroker()
    policy=RiskPolicy(stop_fraction=stop_fraction)
    pos=broker.submit({
        "id":"COUNTERFACTUAL_STOP_ONLY_RESEARCH",
        "symbol":"SHADOW","time_ms":bars[i+1].t,
        "side":side,"quote":bars[i+1].o
    },policy)
    sign=1 if side=="LONG" else -1
    quality="COARSE_5M_OHLC_PATH_PROXY"
    fill=None
    for j in range(i+1,i+HORIZON_BARS+1):
        bar=bars[j]
        stop=bar.l<=pos["stop"] if sign==1 else bar.h>=pos["stop"]
        target=bar.h>=pos["target"] if sign==1 else bar.l<=pos["target"]
        if stop and target:quality="AMBIGUOUS_5M_STOP_FIRST"
        fill,pos=broker.on_bar(pos,bar,bar.t+BAR_MS,policy)
        if fill is not None:break
    if fill is None:raise RuntimeError("COUNTERFACTUAL_PATH_NOT_MATURED")
    ex=int(fill["available_ms"])
    rates=funding[bisect_left(funding_times,bars[i+1].t):
                  bisect_left(funding_times,ex)]
    funding_net=-sign*sum(r for _,r in rates)
    return (
        float(fill["net_usdt"])/policy.notional_usdt+funding_net,
        ex,
        fill["reason"].removesuffix("_AMBIGUOUS"),
        quality,
    )


def build(original,archive,output,*,trailing=False):
    if not original.is_file() or not archive.is_dir():
        raise FileNotFoundError("REQUIRED_PREVIOUS_AUDITED_SOURCES_MISSING")
    if output.exists():
        raise FileExistsError("DO_NOT_OVERWRITE_OLD_1PCT_DATASET")
    output.parent.mkdir(parents=True,exist_ok=True)
    # SQLite backup is done read-only from the original, not an untrusted
    # raw OS byte-copy of a database that might still have WAL pages.
    a=sqlite3.connect(original.resolve().as_uri()+"?mode=ro",uri=True)
    a.row_factory=sqlite3.Row
    b=sqlite3.connect(output)
    try:
        meta=dict(a.execute("SELECT k,v FROM meta"))
        if meta.get("build_complete")!="true" or meta.get("policy")!=LABEL_POLICY:
            raise ValueError("MISMATCHED_OR_INCOMPLETE_2PCT_LABEL_SOURCE")
        a.backup(b)
        b.row_factory=sqlite3.Row
        files=discover(archive,MONTHS)
        funding_files=discover_funding(archive,MONTHS)
        if set(files)!=set(SYMBOLS) or set(funding_files)!=set(SYMBOLS):
            raise ValueError("REQUIRE_EXACT_THREE_SOURCE_SYMBOLS_WITH_FUNDING")
        count=Counter()
        checks=Counter()
        begin=monotonic()
        for symbol in SYMBOLS:
            # All candidate labels including July-Dec 2025 needed for
            # optional later re-fitting of 1%-stop target, not just 2026.
            bars,_=load_bars(files[symbol],month_start("2025-07"),END)
            ix={bar.t:i for i,bar in enumerate(bars)}
            funding,_=load_funding(funding_files[symbol],month_start("2025-07"),END)
            times=[t for t,_ in funding]
            query=b.execute(
                "SELECT decision_ms,side,family,net,exit_ms,exit_reason "
                "FROM opportunity WHERE symbol=? ORDER BY decision_ms,side,family",
                (symbol,))
            updates=[]
            for r in query:
                # decision_ms represents observed candle CLOSE, so candle open
                # timestamp = decision_ms - BAR_MS.
                i=ix.get(r["decision_ms"]-BAR_MS)
                if i is None or i+HORIZON_BARS>=len(bars):
                    raise ValueError("SOURCE_MISMATCH_OR_FUTURE_PATH_MISSING")
                if checks[symbol]<100:
                    original_result=broker_outcome(
                        bars,i,r["side"],stop_fraction=STOP_FRACTION,
                        funding=funding,funding_times=times)
                    if (abs(original_result[0]-float(r["net"]))>1e-9 or
                        original_result[1]!=int(r["exit_ms"]) or
                        original_result[2]!=r["exit_reason"]):
                        raise ValueError("SHARED_PAPER_BROKER_2PCT_PARITY_FAILED:"+symbol)
                    checks[symbol]+=1
                new_net,new_exit,new_why,quality=broker_outcome(
                    bars,i,r["side"],stop_fraction=STOP1,
                    funding=funding,funding_times=times,trailing=trailing)
                if new_exit>int(r["decision_ms"])+HORIZON_BARS*BAR_MS:
                    raise ValueError("COUNTERFACTUAL_EXCEEDED_60_MINUTES")
                updates.append((new_net,new_exit,new_exit,new_why,quality,
                                r["decision_ms"],symbol,r["side"],r["family"]))
            # Keep all changes transactional and reject any missing candidate.
            with b:
                b.executemany(
                    "UPDATE opportunity SET net=?,exit_ms=?,label_available_ms=?,"
                    "exit_reason=?,quality=? "
                    "WHERE decision_ms=? AND symbol=? AND side=? AND family=?", updates)
            count[symbol]=len(updates)
            print(json.dumps({"processed_symbol":symbol,"labels":len(updates),
                "original_2pct_fill_parity_checked":checks[symbol],
                "elapsed_s":round(monotonic()-begin,2)}),flush=True)
        with b:
            # Existing outcome_context/watch targets describe old 2%-stop
            # future outcomes. Remove them from this alternate result DB,
            # since replay/after-cost FreqAI only use causal watch_candidate
            # and candidate tables and the new opportunity table.
            b.execute("DELETE FROM outcome_context")
            b.execute("DELETE FROM watch")
            b.execute("UPDATE meta SET v=? WHERE k='policy'",
                      (TRAILING_POLICY if trailing else POLICY,))
            b.execute("INSERT OR REPLACE INTO meta VALUES('original_source_db_sha256',?)",
                      (digest(original),))
            b.execute("INSERT OR REPLACE INTO meta VALUES('counterfactual_stop_fraction','0.01')")
            b.execute("INSERT OR REPLACE INTO meta VALUES('counterfactual_trailing',?)",
                      ("true" if trailing else "false",))
            b.execute("INSERT OR REPLACE INTO meta VALUES('label_source_quality',"
                      "'STOP1_COUNTERFACTUAL_BINANCE_ARCHIVE_VERIFIED_5M_BROKER_PROXY')")
            b.execute("INSERT OR REPLACE INTO meta VALUES('note',"
                      "'Candidate and watch source hashes intentionally match original 2pct features; outcome targets are newly recomputed under stop1, and old outcome_context/watch LABEL tables cleared')")
        b.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print(json.dumps({"status":"ONE_PERCENT_OUTCOME_DB_COMPLETE",
                          "policy":TRAILING_POLICY if trailing else POLICY,
                          "trailing":trailing,"labels":dict(count),
                          "output":str(output),"source_db_sha":digest(original),
                          "new_db_sha":digest(output)}),flush=True)
    finally:
        b.close();a.close()


def evaluate(source_db,cf_db,forecasts,outdir,*,trailing=False,fixed1_db=None):
    if outdir.exists():
        raise FileExistsError("REFUSE_PREVIOUS_REPLAY_OVERWRITE")
    outdir.mkdir(parents=True)
    def examine(db,path,name):
        c=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
        c.row_factory=sqlite3.Row
        try:
            brain=FreqAINetResearchBrain.from_jsonl(
                forecasts,cutoff_ms=START,version=name,
                uncertainty_weight=0,cost_stress=0)
            log=EventLog(path/(name+"_decisions.jsonl"))
            try:
                res=replay(c,brain,START,END,event_sink=log.write)
            finally:
                log.close()
            with (path/(name+"_trades.jsonl")).open("x") as fh:
                for t in res["trades"]:
                    fh.write(json.dumps(t,sort_keys=True,allow_nan=False)+"\n")
            if not res["account_complete"]:
                raise ValueError("COUNTERFACTUAL_WALLET_HAS_INCOMPLETE_PATHS")
            return {k:v for k,v in res.items() if k!="trades"}
        finally:
            c.close()
    control=examine(source_db,outdir,"RAW_SAVED_FREQAI_STOP_2PCT_CONTROL")
    trial=examine(cf_db,outdir,"RAW_SAVED_FREQAI_TRAIL_1PCT_CF" if trailing else "RAW_SAVED_FREQAI_STOP_1PCT_CF")
    fixed1=examine(fixed1_db,outdir,"RAW_SAVED_FREQAI_STOP_1PCT_CONTROL") if fixed1_db else None
    artifacts={p.name:digest(p) for p in outdir.glob("*.jsonl")}
    report={
        "experiment":("EXACT_SAVED_273_FREQAI_MODEL_RAW_FORECASTS_TRAIL_1PCT_CF_V1"
            if trailing else "EXACT_SAVED_273_FREQAI_MODEL_RAW_FORECASTS_STOP1_ONLY_CF_V1"),
        "source_db_sha256":digest(source_db),
        "alternative_db_sha256":digest(cf_db),
        "original_saved_predictions_sha256":digest(forecasts),
        "stop2":control,"stop1":trial,
        "fixed1":fixed1,
        "trailing_previous_completed_5m_bar_only":trailing,
        "delta_stake_pnl_usdt":round(trial["net_pnl_usdt"]-control["net_pnl_usdt"],4),
        "receipts":artifacts,
        "not_a_retrained_stop1_target_model":True,
        "broker_exits_recomputed_including_funding":True,
        "model_prediction_thresholds_unchanged":True,
        "notes":[
            "Saved forecasts were trained on ORIGINAL 2% stop outcomes; this is controlled changed-risk-policy execution, not training-on-1%-labels.",
            "Trailing ratchet occurs AFTER a 5m bar closes and only if initial stop/target/horizon was not hit; never anticipates intrabar order.",
            "Same as-of daily predictions and candidate features; 1%-stop trades can exit sooner and change subsequent eligibility.",
            "Historical 5m coarse stop-first fill proxy, not native exchange orders.",
            "All 2026 months previously inspected, not fresh out-of-sample evidence.",
            "No trades or model promotions authorized."
        ]
    }
    (outdir/"summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"result":"ONE_PERCENT_STOP_SAME_DAILY_MODEL_9MONTH_REPLAY",
                      "stop2":{k:control[k] for k in ("selected_trades","net_pnl_usdt","stressed_pnl_usdt","max_drawdown_pct_of_sleeve")},
                      "stop1":{k:trial[k] for k in ("selected_trades","net_pnl_usdt","stressed_pnl_usdt","max_drawdown_pct_of_sleeve")},
                      "fixed1":{k:fixed1[k] for k in ("selected_trades","net_pnl_usdt","stressed_pnl_usdt","max_drawdown_pct_of_sleeve")} if fixed1 else None,
                      "delta_pnl_usdt":report["delta_stake_pnl_usdt"]},indent=2),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--step",choices=("build","evaluate"),required=True)
    p.add_argument("--source-db",required=True,type=Path)
    p.add_argument("--stop1-db",required=True,type=Path)
    p.add_argument("--archive",type=Path)
    p.add_argument("--forecasts",type=Path)
    p.add_argument("--out",type=Path)
    p.add_argument("--trailing",action="store_true")
    p.add_argument("--fixed1-db",type=Path)
    args=p.parse_args()
    if args.step=="build":
        if args.archive is None:raise ValueError("ARCHIVE_REQUIRED")
        build(args.source_db,args.archive,args.stop1_db,trailing=args.trailing)
    else:
        if args.forecasts is None or args.out is None:raise ValueError("FORECASTS_AND_OUTPUT_REQUIRED")
        evaluate(args.source_db,args.stop1_db,args.forecasts,args.out,
                 trailing=args.trailing,fixed1_db=args.fixed1_db)


if __name__=="__main__":
    main()
