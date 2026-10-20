"""Independent two-way audit for original 1%-stop-target-trained FreqAI models."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter
import sqlite3
from scripts.v7_three_coin_learning_audit import events
from research.v7_trailing1_threeway_audit import digest,read_jsonl
from research.v7_stop1_daily_raw_counterfactual import POLICY,TRAILING_POLICY


def audit(root,training,stop1,trail,forecasts):
    root=Path(root).resolve()
    obj=json.loads((root/"summary.json").read_text())
    meta=json.loads((training/"summary.json").read_text())
    if (obj["experiment"]!="SAME_1PCT_TRAINED_FREQAI_273_DAILY_FORECASTS_FIXED_VS_TRAILING1"
        or obj["training_target"]!="FIXED_1PCT_STOP_LABELS_NOT_TRAILING_LABELS"
        or meta.get("label_policy")!=POLICY
        or meta.get("daily_fresh_model_count")!=273):
        raise ValueError("MISSING_SOURCE_TRAINED_ON_REAL_1PCT_TARGETS")
    if digest(forecasts)!=obj["saved_pred_sha256"]:
        raise ValueError("MODELED_FORECASTS_TAMPERED")
    original=meta["accounts"]["DAILY_RAW"]
    if not original["complete"]:raise ValueError("INCOMPLETE_TRAINED_DAILY_RAW_ACCOUNT")
    accounts={}
    for key,name,db,expected_policy in (
        ("fixed1","STOP1_TRAINED_FIXED1_RAW",stop1,POLICY),
        ("trailing1","STOP1_TRAINED_TRAILING1_RAW",trail,TRAILING_POLICY)
    ):
        if digest(db)!=obj["fixed_source_sha256" if key=="fixed1" else "trailing_source_sha256"]:
            raise ValueError("LABEL_DATABASE_HASH_MISMATCH")
        c=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
        try:
            if dict(c.execute("SELECT k,v FROM meta"))["policy"]!=expected_policy:
                raise ValueError("WRONG_STOP_POLICY")
            trs=read_jsonl(root/(name+"_trades.jsonl"))
            stats=obj["accounts"][key]
            if not stats["account_complete"] or len(trs)!=stats["selected_trades"]:
                raise ValueError("BAD_ACCOUNT_STATE")
            pnl=0.0
            reasons=Counter()
            for tr in trs:
                row=c.execute("SELECT net,exit_ms,exit_reason FROM opportunity WHERE "
                    "decision_ms=? AND symbol=? AND side=? AND family=?",
                    tuple(tr[k] for k in ("decision_ms","symbol","side","family"))).fetchone()
                if not row or abs(row[0]-tr["net_after_cost"])>1e-10 or row[1]!=tr["exit_ms"]:
                    raise ValueError("TRADE_NOT_FROM_ACTUAL_BACKTEST_LABEL")
                reasons[row[2]]+=1
                pnl+=tr["net_after_cost"]*1000
            if abs(pnl-stats["net_pnl_usdt"])>1e-3:
                raise ValueError("TRADE_LEDGER_PNL_MISMATCH")
            if abs(stats["stressed_pnl_usdt"]-(pnl-2.5*len(trs)))>0.0015:
                raise ValueError("TRADE_EXTRA_COST_STRESS_MISMATCH")
            if sum(ev.get("event")=="decision" for ev in events(root/(name+"_decisions.jsonl")))!=53881:
                raise ValueError("ACCOUNT_DECISION_HASHCHAIN_BAD")
            if key=="fixed1" and (abs(stats["net_pnl_usdt"]-original["net_usdt"])>1e-6
                or len(trs)!=original["trades"]):
                raise ValueError("BASELINE_1PCT_MODEL_REPLAY_DID_NOT_MATCH_ORIGINAL")
            accounts[key]={"trades":len(trs),"net_usdt":round(pnl,4),
                           "extra25bp_usdt":stats["stressed_pnl_usdt"],
                           "exits":dict(reasons)}
        finally:c.close()
    for name,sha in obj["receipt_sha256"].items():
        if digest(root/name)!=sha:raise ValueError("CHAIN_AND_TRADES_TAMPERED:"+name)
    return {
        "audit":"SAVED_273_ONE_PERCENT_TRAINED_MODELS_FIXED_VS_TRAILING_EXIT_VERIFIED",
        "result_sha256":digest(root/"summary.json"),
        "retrained_summary_sha256":digest(training/"summary.json"),
        "forecast_sha256":digest(forecasts),
        "accounts":accounts,
        "delta_trailing_minus_fixed_usdt":round(accounts["trailing1"]["net_usdt"]-accounts["fixed1"]["net_usdt"],4),
        "limitation":"5m previous-bar trailing not continuous exchange; 1%-fixed training labels NOT trailing-specific labels; same inspected market"
    }


def main():
    p=argparse.ArgumentParser()
    for k in ("root","training","stop1","trail","forecasts","out"):
        p.add_argument("--"+k,required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("REFUSE_OVERWRITE")
    result=audit(a.root,a.training,a.stop1,a.trail,a.forecasts)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
