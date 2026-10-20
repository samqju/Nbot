#!/usr/bin/env python3
"""Verify and summarize saved V7/FreqAI after-cost 3-coin experiment.

Never imports trained models or places orders. Uses only the *saved*
research result, SHA receipts, and the hash-chained decision/trade ledgers.
"""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import json
from hashlib import sha256
from statistics import mean
from scripts.v7_three_coin_learning_audit import events


def file_hash(path):
    h=sha256()
    with open(path,"rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path):
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]


def summary_evidence(directory):
    root=Path(directory)
    info=json.loads((root/"summary.json").read_text())
    for name,expected in info["artifact_sha256"].items():
        actual=file_hash(root/name)
        if actual!=expected:
            raise ValueError("EXPERIMENT_ARTIFACT_DIGEST_MISMATCH:"+name)
    for model in ("A","B"):
        manifest=json.loads((root/model/"manifest.json").read_text())
        if file_hash(root/model/"actual_freqai_net_lgbm.joblib")!=manifest["model_sha256"]:
            raise ValueError("FREQAI_MODEL_HASH_MISMATCH")
    reports={}
    for model,financial in info["replays"].items():
        chain=root/(model+"_decisions.jsonl")
        n_decisions=sum(event.get("event")=="decision" for event in events(chain))
        saved=read_jsonl(root/(model+"_trades.jsonl"))
        if n_decisions==0 or len(saved)!=financial["selected_trades"]:
            raise ValueError("INVALID_REPLAY_DECISION_LEDGER")
        if abs(sum(x["net_after_cost"]*financial["notional_each_usdt"] for x in saved)
               -financial["net_pnl_usdt"])>0.0001:
            raise ValueError("INCONSISTENT_AFTER_COST_ACCOUNTING")
        co=Counter(x["symbol"] for x in saved)
        fam=Counter(x["family"] for x in saved)
        reports[model]={
            "selected":len(saved),
            "net_pnl_usdt":financial["net_pnl_usdt"],
            "stressed_pnl_usdt":financial["stressed_pnl_usdt"],
            "max_drawdown_pct_of_sleeve":financial["max_drawdown_pct_of_sleeve"],
            "by_symbol":dict(co),
            "top_families":fam.most_common(8),
            "mean_predicted_net_bp":round(mean(x["predicted_net"] for x in saved)*10000,3) if saved else None,
            "mean_realized_net_bp":round(mean(x["net_after_cost"] for x in saved)*10000,3) if saved else None,
            "observed_decision_events":n_decisions,
        }
    return {
        "status":"VERIFIED_RESEARCH_ONLY_NOT_PROMOTION_EVIDENCE",
        "training_rows":{"A":info["training_A"]["training_rows"],
                         "B":info["training_B"]["training_rows"]},
        "models_sha256":{"A":info["training_A"]["model_sha256"],
                         "B":info["training_B"]["model_sha256"]},
        "research_aftercost_replays":reports,
        "warnings":info["warnings"]+[
            "No evidence that the observed small gains are persistent or statistically robust.",
            "Even B uncertainty Jul-Sep 5-trade +5.67 USDT becomes negative under additional 25bp cost stress.",
        ],
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--result-dir",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    if a.out.exists():raise FileExistsError("REFUSE_OVERWRITE")
    report=summary_evidence(a.result_dir)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({
        "A_training_rows":report["training_rows"]["A"],
        "B_training_rows":report["training_rows"]["B"],
        "jul_sep":{k:v for k,v in report["research_aftercost_replays"].items() if k.startswith("JUL_SEP")},
    },indent=2))


if __name__=="__main__":
    main()
