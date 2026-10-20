#!/usr/bin/env python3
"""Fail-closed provenance + paired daily-block uplift audit for monthly FreqAI study.

All inputs are saved aftercost research *ledgers*. Does not fit/replay models
or use future outcomes as decision inputs. Never changes bot runtime.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import random
import statistics

from scripts.v7_three_coin_learning_audit import events


def digest(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):
            h.update(chunk)
    return h.hexdigest()


def load_trades(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(row) for row in f if row.strip()]


def daily(trades):
    buckets=defaultdict(float)
    for tr in trades:
        d=int(tr["exit_ms"])//86400000
        buckets[d]+=tr["net_after_cost"]*1000
    return buckets


def paired_moving_7d_bootstrap(tr_a,tr_b,start,end,*,n=2000,seed=72026):
    a,b=daily(tr_a),daily(tr_b)
    start_day=start//86400000
    end_day=end//86400000
    delta=[b.get(t,0.0)-a.get(t,0.0) for t in range(start_day,end_day)]
    if len(delta)<21:raise ValueError("TOO_FEW_DAYS_FOR_PAIRED_BLOCKS")
    rng=random.Random(seed)
    blocks=[delta[i:i+7] for i in range(len(delta)-6)]
    draws=[]
    for _ in range(n):
        resampled=[]
        while len(resampled)<len(delta):
            resampled.extend(blocks[rng.randrange(len(blocks))])
        draws.append(sum(resampled[:len(delta)]))
    draws.sort()
    return {
        "paired_uplift_usdt":round(sum(delta),4),
        "moving_block_days":7,
        "samples":n,
        "percentile_95_ci_usdt":[round(draws[int(.025*n)],4),round(draws[int(.975*n)-1],4)],
        "share_resampled_uplift_positive":round(sum(v>0 for v in draws)/n,4),
        "warning":"Exploratory dependent-block resampling on previously inspected proxy market; not a live-profit significance test",
    }


def audit(root):
    root=Path(root)
    summary=json.loads((root/"summary.json").read_text())
    if summary.get("experiment")!="V7_3COIN_FREQAI_REAL_FIT_180DAY_MONTHLY_COMPARATIVE_V1":
        raise ValueError("WRONG_EXPERIMENT_OR_DATASET")
    for relative,d in summary["artifact_receipts"].items():
        p=(root/relative).resolve()
        if not p.is_relative_to(root.resolve()) or not p.is_file() or digest(p)!=d:
            raise ValueError("HISTORIC_RESEARCH_ARTIFACT_HASH_MISMATCH:"+relative)
    for key,m in summary["model_manifests"].items():
        if digest(root/key/"actual_freqai_net_lgbm.joblib")!=m["model_sha256"]:
            raise ValueError("HISTORIC_FREQAI_MODEL_DIGEST_MISMATCH:"+key)
        if (m["train_last_label_ms"]>=m["fit_end_before_ms"]
                or m["calibration_last_label_ms"]>=m["cutoff_ms"]
                or m["fit_end_before_ms"]>=m["cutoff_ms"]):
            raise ValueError("HISTORIC_LABEL_LEAK_AT_MONTH_CUTOFF:"+key)
        if not (m["window_begin_ms"]<m["fit_end_before_ms"]):
            raise ValueError("BAD_MODEL_WINDOW:"+key)
    account_trades={}
    summary_rows={}
    for key,report in summary["portfolio_accounts"].items():
        trade_path=root/(key+"_trades.jsonl")
        ledger_path=root/(key+"_decisions.jsonl")
        count=Counter()
        for ev in events(ledger_path):
            if ev.get("event")=="decision":
                count[ev["reason"]]+=1
        trades=load_trades(trade_path)
        if len(trades)!=report["trades"] or not report["complete"]:
            raise ValueError("INCOMPLETE_ACCOUNT_OR_TRADE_COUNT_MISMATCH:"+key)
        pnl=round(sum(float(t["net_after_cost"])*1000 for t in trades),4)
        if abs(pnl-report["net_usdt"])>1e-3:
            raise ValueError("SAVED_MONTHLY_PORTFOLIO_PNL_MISMATCH:"+key)
        if abs(report["stressed_pnl_usdt"]-(report["net_usdt"]-2.5*len(trades)))>1e-3:
            raise ValueError("SAVED_MONTHLY_STRESS_MISMATCH:"+key)
        month_sums=defaultdict(lambda:[0,0.0])
        for trade in trades:
            if not summary["start"]<=trade["decision_ms"]<summary["end"]:
                raise ValueError("TRADE_OUTSIDE_EXAMINATION_WINDOW")
            month=datetime.fromtimestamp(trade["exit_ms"]/1000,timezone.utc).strftime("%Y-%m")
            month_sums[month][0]+=1
            month_sums[month][1]+=float(trade["net_after_cost"])*1000
        for mo,values in report["by_exit_month"].items():
            if month_sums[mo][0]!=values["trades"] or abs(month_sums[mo][1]-values["pnl_usdt"])>1e-3:
                raise ValueError("MONTH_BUCKET_RECONCILIATION_FAILED:"+key)
        account_trades[key]=trades
        summary_rows[key]={
            "count":len(trades),"net_usdt":report["net_usdt"],
            "stressed_net_usdt":report["stressed_pnl_usdt"],
            "by_exit_month":report["by_exit_month"],
            "decisions":sum(count.values()),
            "abstentions":count["BRAIN_ABSTAIN"],
            "slot_occupied_decisions":count["SLOT_OCCUPIED"],
        }
    start,end=summary["start"],summary["end"]
    comparisons={}
    for mode in ("RAW","UNCERTAINTY","STRESS"):
        frozen="FROZEN_JULY_"+mode
        for strategy in ("ROLLING","EXPANDING"):
            active=strategy+"_"+mode
            comparisons[active+"_vs_"+frozen]=paired_moving_7d_bootstrap(
                account_trades[frozen],account_trades[active],start,end
            )
    # Same start model July: frozen and rolling should match July choices.
    july="2026-07"
    a=summary_rows["FROZEN_JULY_RAW"]["by_exit_month"].get(july,{})
    b=summary_rows["ROLLING_RAW"]["by_exit_month"].get(july,{})
    if a!=b:
        raise ValueError("FROZEN_AND_ROLLING_JULY_START_MODEL_DIFFERENT")
    return {
        "audit":"SOURCE_HASHED_READ_ONLY_COMPLETE",
        "dataset_sha256":summary["original_dataset_sha256"],
        "summary_sha256":digest(root/"summary.json"),
        "models":{k:{"train_rows":v["fit_rows"],
                      "q75_bp":v["calibration_q75_bp"],
                      "cutoff_ms":v["cutoff_ms"],
                      "window_begin_ms":v["window_begin_ms"]}
                  for k,v in summary["model_manifests"].items()},
        "accounts":summary_rows,
        "paired_retraining_effects":comparisons,
        "learning_gate":"HOLD_EVEN_IF_RAW_PROFITABLE_UNDER_5M_PROXY",
        "limitations":summary["warnings"]
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    if a.out.exists():raise FileExistsError("REFUSE_OVERWRITE_PREVIOUS_AUDIT")
    report=audit(a.run)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
       "audit":report["audit"],
       "monthly_raw_uplift":report["paired_retraining_effects"]["ROLLING_RAW_vs_FROZEN_JULY_RAW"],
       "expanding_raw_uplift":report["paired_retraining_effects"]["EXPANDING_RAW_vs_FROZEN_JULY_RAW"]
    },indent=2))
if __name__=="__main__":
    main()
