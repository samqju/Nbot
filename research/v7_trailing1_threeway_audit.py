#!/usr/bin/env python3
"""Read-only, checksum verified same-FreqAI-model trailing-1% economic audit.

One 9-month portfolio, fixed 2%, fixed 1%, and trailing 1% after every prior
5m completed candle. Research only, no exchange/credentials/model fitting.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from scripts.v7_three_coin_learning_audit import events
from research.v7_stop1_daily_raw_counterfactual import POLICY,TRAILING_POLICY


def digest(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path):
    with Path(path).open("r",encoding="utf8") as f:
        return [json.loads(t) for t in f if t.strip()]


def audit(root,db2,db1,dbtrail,forecasts):
    root=Path(root).resolve()
    result=json.loads((root/"summary.json").read_text())
    if (result["experiment"]!="EXACT_SAVED_273_FREQAI_MODEL_RAW_FORECASTS_TRAIL_1PCT_CF_V1"
        or result["trailing_previous_completed_5m_bar_only"] is not True):
        raise ValueError("WRONG_TRAILING_RESEARCH_SCOPE")
    for key,path in (("source_db_sha256",db2),("alternative_db_sha256",dbtrail),
                     ("original_saved_predictions_sha256",forecasts)):
        if digest(path)!=result[key]:
            raise ValueError("SOURCE_SHA_MISMATCH:"+key)
    for k,h in result["receipts"].items():
        if digest(root/k)!=h:raise ValueError("HASH_CHAIN_OR_TRADE_LEDGER_SHA_MISMATCH:"+k)
    for path,grade in ((db1,POLICY),(dbtrail,TRAILING_POLICY)):
        c=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
        try:
            meta=dict(c.execute("SELECT k,v FROM meta"))
            if (meta.get("policy")!=grade or meta.get("build_complete")!="true"
                or int(c.execute("SELECT COUNT(*) FROM opportunity").fetchone()[0])!=436609):
                raise ValueError("HISTORIC_LABEL_SCOPE_MISMATCH")
            if grade==TRAILING_POLICY and meta.get("counterfactual_trailing")!="true":
                raise ValueError("TRAILING_NOT_RECOMPUTED")
        finally:c.close()
    accounts={
        "stop2":("RAW_SAVED_FREQAI_STOP_2PCT_CONTROL",db2),
        "stop1":("RAW_SAVED_FREQAI_STOP_1PCT_CONTROL",db1),
        "trailing1":("RAW_SAVED_FREQAI_TRAIL_1PCT_CF",dbtrail),
    }
    res={}
    selected={}
    for key,(label,source) in accounts.items():
        save=result["stop1"] if key=="trailing1" else result[key]
        ts=read_jsonl(root/(label+"_trades.jsonl"))
        if not save["account_complete"] or len(ts)!=save["selected_trades"]:
            raise ValueError("INCOMPLETE_ACCOUNT_OR_TRADE_COUNT")
        if abs(sum(x["net_after_cost"]*1000 for x in ts)-save["net_pnl_usdt"])>1e-3:
            raise ValueError("SAVED_PNL_NOT_RECONCILED")
        if abs(save["stressed_pnl_usdt"]-(save["net_pnl_usdt"]-2.5*len(ts)))>1e-3:
            raise ValueError("STRESS_ACCOUNTING_INCONSISTENT")
        reasons=Counter()
        months=defaultdict(lambda:{"count":0,"net":0.0})
        c=sqlite3.connect(source.resolve().as_uri()+"?mode=ro",uri=True)
        try:
            for t in ts:
                r=c.execute("SELECT exit_reason,net,exit_ms FROM opportunity "
                  "WHERE decision_ms=? AND symbol=? AND side=? AND family=?",
                  (t["decision_ms"],t["symbol"],t["side"],t["family"])).fetchone()
                if r is None or abs(t["net_after_cost"]-r[1])>1e-10 or int(t["exit_ms"])!=r[2]:
                    raise ValueError("LEDGER_NOT_MATCHING_PREDECLARED_SOURCE_OUTCOME")
                reasons[r[0]]+=1
                mo=datetime.fromtimestamp(t["exit_ms"]/1000,timezone.utc).strftime("%Y-%m")
                months[mo]["count"]+=1
                months[mo]["net"]+=t["net_after_cost"]*1000
        finally:c.close()
        n=sum(e.get("event")=="decision" for e in events(root/(label+"_decisions.jsonl")))
        if n!=53881:raise ValueError("MISSING_CANDIDATE_DECISION_COVERAGE")
        selected[key]={
            (t["decision_ms"],t["symbol"],t["side"],t["family"]):t for t in ts}
        res[key]={
            "trades":len(ts),"wins":sum(t["net_after_cost"]>0 for t in ts),
            "net_usdt":save["net_pnl_usdt"],
            "extra25bp_cost_net_usdt":save["stressed_pnl_usdt"],
            "max_drawdown_pct":save["max_drawdown_pct_of_sleeve"],
            "exit_reasons":dict(reasons),
            "monthly":{k:{"count":v["count"],"net_usdt":round(v["net"],4)}
                       for k,v in sorted(months.items())},
        }
    common=set(selected["stop1"])&set(selected["trailing1"])
    pair_differences=[(selected["trailing1"][key]["net_after_cost"]-
                      selected["stop1"][key]["net_after_cost"])*1000 for key in common]
    same=sum(abs(d)<1e-7 for d in pair_differences)
    return {
        "audit":"VERIFIED_STOPOUTCOMES_SOURCE_SHA_AND_3_MATCHED_WALLETS",
        "label_source_sha256":{
            "fixed2":digest(db2),"fixed1":digest(db1),"trailing1":digest(dbtrail)},
        "forecast_sha256":digest(forecasts),
        "summary_sha256":digest(root/"summary.json"),
        "portfolios":res,
        "matched_fixed1_trailing1":{
            "same_selected_identity":len(common),
            "same_executed_trade_net":same,
            "different_executed_trade_net":len(common)-same,
            "matched_trailing_minus_fixed_usdt":round(sum(pair_differences),4),
            "trailing_only_trades":len(set(selected["trailing1"])-common),
            "fixed1_only_trades":len(set(selected["stop1"])-common),
        },
        "interpretation":"EXPLORATORY_5M_PREVIOUS_BAR_TRAIL_NOT_NATIVE_EXCHANGE_NO_MODEL_PROMOTION",
    }


def main():
    p=argparse.ArgumentParser()
    for key in ("root","db2","db1","dbtrail","forecasts","out"):
        p.add_argument("--"+key,required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("REFUSE_OLD_AUDIT_REPLACE")
    summary=audit(a.root,a.db2,a.db1,a.dbtrail,a.forecasts)
    a.out.write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=="__main__":main()
