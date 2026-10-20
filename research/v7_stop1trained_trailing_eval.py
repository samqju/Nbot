#!/usr/bin/env python3
"""Same 1%-STOP-fitted 273 daily RAW FreqAI weights, fixed vs trailing stop.

This is a paired execution-policy ablation AFTER the 1% model re-fit has
already completed. It does not claim models were trained for the trailing
target, and never uses later-exit labels in model forecasts. No orders.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sqlite3
from hashlib import sha256
import json
from nbot_v7.experiment import replay,month_start
from nbot_v7.artifacts import EventLog
from nbot_v7.freqai_research_bridge import FreqAINetResearchBrain
from research.v7_stop1_daily_raw_counterfactual import POLICY,TRAILING_POLICY

START=month_start("2026-01")
END=month_start("2026-10")


def hashfile(path):
    h=sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1048576),b""):
            h.update(chunk)
    return h.hexdigest()


def perform(path,forecasts,folder,tag):
    c=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
    c.row_factory=sqlite3.Row
    try:
        brain=FreqAINetResearchBrain.from_jsonl(
            forecasts,cutoff_ms=START,version=tag,
            label_policy=POLICY,uncertainty_weight=0,cost_stress=0)
        log=EventLog(folder/(tag+"_decisions.jsonl"))
        try:
            res=replay(c,brain,START,END,event_sink=log.write)
        finally:
            log.close()
        if not res["account_complete"]:
            raise ValueError("INCOMPLETE_STOP1_MODEL_ACCOUNT")
        with (folder/(tag+"_trades.jsonl")).open("x") as out:
            for tr in res["trades"]:
                out.write(json.dumps(tr,sort_keys=True,allow_nan=False)+"\n")
        return {k:v for k,v in res.items() if k!="trades"}
    finally:c.close()


def main():
    p=argparse.ArgumentParser()
    for f in ("fixed1","trail1","predictions","out"):
        p.add_argument("--"+f,required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("REFUSE_OVERWRITE")
    for f,expected in ((a.fixed1,POLICY),(a.trail1,TRAILING_POLICY)):
        c=sqlite3.connect(f.resolve().as_uri()+"?mode=ro",uri=True)
        try:
            if dict(c.execute("SELECT k,v FROM meta"))["policy"]!=expected:
                raise ValueError("WRONG_TARGET_DB")
        finally:c.close()
    a.out.mkdir(parents=True)
    fixed=perform(a.fixed1,a.predictions,a.out,"STOP1_TRAINED_FIXED1_RAW")
    trail=perform(a.trail1,a.predictions,a.out,"STOP1_TRAINED_TRAILING1_RAW")
    report={
        "experiment":"SAME_1PCT_TRAINED_FREQAI_273_DAILY_FORECASTS_FIXED_VS_TRAILING1",
        "training_target":"FIXED_1PCT_STOP_LABELS_NOT_TRAILING_LABELS",
        "saved_pred_sha256":hashfile(a.predictions),
        "fixed_source_sha256":hashfile(a.fixed1),
        "trailing_source_sha256":hashfile(a.trail1),
        "accounts":{"fixed1":fixed,"trailing1":trail},
        "trailing_minus_fixed_pnl_usdt":round(trail["net_pnl_usdt"]-fixed["net_pnl_usdt"],4),
        "receipt_sha256":{f.name:hashfile(f) for f in a.out.glob("*.jsonl")},
        "warning":"Research-only 5-minute previous-bar trailing (not exchange-continuous), nine months previously studied, no live/paper order, no promotion."
    }
    (a.out/"summary.json").write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"experiment":report["experiment"],
       "fixed1":{k:fixed[k] for k in ("selected_trades","net_pnl_usdt","stressed_pnl_usdt","max_drawdown_pct_of_sleeve")},
       "trailing1":{k:trail[k] for k in ("selected_trades","net_pnl_usdt","stressed_pnl_usdt","max_drawdown_pct_of_sleeve")},
       "delta":report["trailing_minus_fixed_pnl_usdt"]},indent=2))


if __name__=="__main__":main()
