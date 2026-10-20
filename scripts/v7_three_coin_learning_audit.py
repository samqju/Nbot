#!/usr/bin/env python3
"""Read-only V7 three-coin learning autopsy. NEVER places orders or retrains.

Inspect saved decision/event/trade chains and the existing labeled SQLite data.
Selected-trade calibration is conditional on portfolio decisions; sampled
abstention hindsight is an *oracle diagnostic*, never realizable portfolio PnL.
No joblib model deserialization. Each input is hashed to retain provenance.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import sqlite3
from statistics import mean, median

BRAINS = ("C_A", "C_B1", "C_B")
COLS = ("symbol", "side", "family", "regime", "quality", "future_btc_status",
        "funding_status", "btc_entry_state")
BP = 10000.0


def file_sha(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def events(path: Path):
    previous = "0" * 64
    for i, line in enumerate(path.open(encoding="utf-8")):
        row = json.loads(line)
        assert row.get("sequence") == i and row.get("previous_sha256") == previous, (
            "BROKEN_EVENT_CHAIN_SEQUENCE", str(path), i)
        claimed = row["sha256"]
        body = {k: v for k, v in row.items() if k != "sha256"}
        expected = sha256(json.dumps(body, sort_keys=True, separators=(",",":"),
                                    allow_nan=False).encode()).hexdigest()
        assert claimed == expected, ("BROKEN_EVENT_CHAIN_HASH", str(path), i)
        previous = claimed
        yield row


def groups(records):
    out = {}
    for name in COLS:
        buckets = defaultdict(list)
        for r in records:
            buckets[str(r[name])].append(r)
        out[name] = {k: {
            "trades": len(arr),
            "net_usdt": round(sum(x["net_usdt"] for x in arr),4),
            "actual_mean_bp": round(mean(x["actual_net"] for x in arr)*BP,3),
            "predicted_mean_bp": round(mean(x["predicted_net"] for x in arr)*BP,3)
        } for k,arr in sorted(buckets.items(),key=lambda z:(-len(z[1]),z[0]))}
    return out


def prediction_bins(records):
    bounds = ((0,1),(1,3),(3,10),(10,30),(30,100),(100,math.inf))
    result = []
    for a,b in bounds:
        subset=[r for r in records if a <= r["predicted_net"]*BP < b]
        if not subset:
            continue
        result.append({
            "predicted_bp_range": [a, None if math.isinf(b) else b],
            "trades": len(subset),
            "predicted_mean_bp": round(mean(x["predicted_net"] for x in subset)*BP,3),
            "actual_mean_bp": round(mean(x["actual_net"] for x in subset)*BP,3),
            "realized_positive_rate": round(sum(x["actual_net"]>0 for x in subset)/len(subset),4),
            "net_usdt": round(sum(x["net_usdt"] for x in subset),4)
        })
    return result


def asof_bucket(row):
    btc12=row.get("btc_r12")
    if btc12 is None:return "UNKNOWN"
    return "BTC_UP_1H" if btc12 >= .005 else "BTC_DOWN_1H" if btc12 <= -.005 else "BTC_FLAT_1H"


def audit(db:Path, run:Path, *,max_abstain_sample=300):
    if not db.is_file() or not run.is_dir():
        raise FileNotFoundError("REQUIRED_EXISTING_DATASET_AND_RUN")
    summary_path=run/"summary.json"
    summary=json.loads(summary_path.read_text())
    if summary.get("experiment")!="NBOT_V7_NINE_MONTH_BRAIN_LEARNING_V1":
        raise ValueError("WRONG_EXPERIMENT")
    conn=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
    conn.row_factory=sqlite3.Row
    report={
        "schema":"V7_THREE_COIN_LEARNING_AUTOPSY_1",
        "authority":"OFFLINE_RESEARCH_DIAGNOSTIC_ONLY_NO_RETRAINING_NO_ORDERS",
        "dataset":str(db),"saved_run":str(run),
        "source_hashes":{"database_file_sha256":file_sha(db),
                         "summary_sha256":file_sha(summary_path),
                         "run_manifest_sha256":file_sha(run/"run_manifest.json")},
        "prior_experiment_unchanged":True,
        "periods":summary["periods"],
        "warnings":[
            "Historical BTC/ETH/SOL only; unverified historical lifecycle; 5m OHLC paper fill proxies.",
            "July-Sep was previously inspected in V6: exploratory, not independent clean OOS.",
            "Selected-trade calibration is selection-biased, not all-opportunity calibration.",
            "Abstention hindsight oracle ignores own wallet, liquidity, availability and watch restrictions.",
            "Sources are read-only; code does not deserialize models or initiate trading."
        ],
        "brain":{}
    }
    try:
        meta=dict(conn.execute("SELECT k,v FROM meta"))
        if meta.get("build_complete")!="true":
            raise ValueError("INCOMPLETE_DATASET")
        report["dataset_metadata"]={
            "label_policy":meta.get("policy"),
            "source_grade":json.loads(meta["coverage"]).get("registry_source_grades"),
            "symbol_count":len(json.loads(meta["coverage"]).get("symbols",{})),
            "candidate_total":conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0],
            "matured_outcomes_total":conn.execute("SELECT COUNT(*) FROM opportunity").fetchone()[0],
            "training_counts_by_cutoff":{}
        }
        for name, m in summary["model_manifests"].items():
            cutoff=m["training_cutoff_ms"]
            eligible=conn.execute(
                "SELECT COUNT(*) FROM opportunity WHERE decision_ms<? AND label_available_ms<?",
                (cutoff,cutoff)).fetchone()[0]
            report["dataset_metadata"]["training_counts_by_cutoff"][name]={
                "eligible_matured_opportunities":eligible,
                "reported_rows_fit":m["trade_train_rows"],
                "sampled_fit_share":round(m["trade_train_rows"]/eligible,5) if eligible else None,
                "rank_groups":m["grouped_rank_training_events"],
                "context_experts":m["has_context_experts"]
            }
        report["identical_base_heads"]={
            "B1_B_trade_sha_match":summary["model_manifests"]["B1_SAME_ARCH_MORE_DATA"]
                ["files_sha256"]["trade"]==summary["model_manifests"]["B_ADAPTIVE_6MONTH_FROZEN"]
                ["files_sha256"]["trade"],
            "B1_B_watch_sha_match":summary["model_manifests"]["B1_SAME_ARCH_MORE_DATA"]
                ["files_sha256"]["watch"]==summary["model_manifests"]["B_ADAPTIVE_6MONTH_FROZEN"]
                ["files_sha256"]["watch"]
        }
        event_by_brain={}
        saved_trades={}
        for idx,key in enumerate(BRAINS):
            decision_path=run/(key+"_decisions.jsonl")
            trade_path=run/(key+"_trades.jsonl")
            report["source_hashes"][key+"_decisions"]=file_sha(decision_path)
            report["source_hashes"][key+"_trades"]=file_sha(trade_path)
            e_by_t={}
            reasons=Counter()
            pred_selected={}
            for e in events(decision_path):
                if e.get("event")!="decision":continue
                t=int(e["time_ms"])
                if t in e_by_t:raise ValueError("DUPLICATE_DECISION_TIME:"+key)
                e_by_t[t]=e
                reasons[e["reason"]]+=1
                if e["reason"]=="SELECTED":
                    pred_selected[(t,e["symbol"],e["side"],e["family"])]=(
                        e["predicted_net"],e["rank_score"])
            event_by_brain[key]=e_by_t
            trades=[json.loads(x) for x in trade_path.read_text().splitlines() if x]
            saved_trades[key]=trades
            enriched=[]
            for t in trades:
                identity=(t["decision_ms"],t["symbol"],t["side"],t["family"])
                if identity not in pred_selected:raise ValueError("TRADE_MISSING_PRE_ENTRY_PREDICTION:"+str(identity))
                features=conn.execute(
                    "SELECT features,net,quality FROM opportunity WHERE decision_ms=? AND symbol=? AND side=? AND family=?",
                    identity).fetchone()
                ctx=conn.execute(
                    "SELECT future_btc_status,funding_status,funding_net_fraction,mfe_mae_time_quality FROM outcome_context WHERE decision_ms=? AND symbol=? AND side=? AND family=?",
                    identity).fetchone()
                if features is None or ctx is None:
                    raise ValueError("MISSING_SOURCE_TRADE_LABEL")
                if abs(float(features["net"])-t["net_after_cost"])>1e-10:
                    raise ValueError("SAVED_PORTFOLIO_OUTCOME_SOURCE_MISMATCH")
                ff=json.loads(features["features"])
                enriched.append({
                    **t,
                    "quality":features["quality"],
                    "future_btc_status":ctx["future_btc_status"],
                    "funding_status":ctx["funding_status"],
                    "funding_fraction":ctx["funding_net_fraction"],
                    "btc_entry_state":asof_bucket(ff),
                    "net_usdt":float(t["net_after_cost"])*1000.0,
                    "actual_net":float(t["net_after_cost"]),
                    "predicted_net":float(t["predicted_net"]),
                    "prediction_error_bp":(float(t["predicted_net"])-float(t["net_after_cost"]))*BP,
                })
            pnl=sum(z["net_usdt"] for z in enriched)
            st=summary["stage_c"][idx]
            if len(enriched)!=st["selected_trades"] or abs(pnl-st["net_pnl_usdt"])>1e-3:
                raise ValueError("SAVED_SUMMARY_ACCOUNTING_MISMATCH")
            if not st["account_complete"]:
                raise ValueError("INCOMPLETE_ACCOUNT_NO_LEARNING_INFERENCE")
            errors=[z["prediction_error_bp"] for z in enriched]
            br={
                "model":st["brain"],
                "saved_summary_net_usdt":st["net_pnl_usdt"],
                "closed_trades":len(enriched),
                "decision_reasons":dict(sorted(reasons.items())),
                "positive_prediction_trade_fraction":round(sum(x["predicted_net"]>0 for x in enriched)/len(enriched),4),
                "prediction_mean_bp":round(mean(z["predicted_net"] for z in enriched)*BP,4),
                "realized_mean_bp":round(mean(z["actual_net"] for z in enriched)*BP,4),
                "prediction_optimism_bp":round(mean(errors),4),
                "prediction_median_error_bp":round(median(errors),4),
                "prediction_rmse_bp":round(math.sqrt(mean(x*x for x in errors)),4),
                "win_fraction":round(sum(z["actual_net"]>0 for z in enriched)/len(enriched),4),
                "mean_mfe_pct":round(mean(z["mfe_pct"] for z in enriched),6),
                "mean_mae_pct":round(mean(z["mae_pct"] for z in enriched),6),
                "stressed_25bp_net_usdt":st["stressed_pnl_usdt"],
                "by_group":groups(enriched),
                "by_prediction_band":prediction_bins(enriched),
            }
            report["brain"][key]=br
            saved_trades[key]=enriched
        all_times=set().union(*(set(x) for x in event_by_brain.values()))
        intersection=set.intersection(*(set(x) for x in event_by_brain.values()))
        report["common_decision_times"]={"union":len(all_times),"intersection":len(intersection)}
        compare={}
        for key in ("C_B1","C_B"):
            cls=defaultdict(list)
            for trade in saved_trades[key]:
                t=trade["decision_ms"]
                before=event_by_brain["C_A"].get(t)
                cls[before["reason"] if before else "NO_MATCH"].append(trade["net_usdt"])
            compare[key+"_trades_at_A_reason"]={
                k:{"count":len(xs),"pnl_usdt":round(sum(xs),4)}
                for k,xs in sorted(cls.items(),key=lambda z:(-len(z[1]),z[0]))}
        report["brain_vs_A_same_timestamp_context"]=compare
        # Hindsight-only sampled diagnostics at abstention timestamps.
        # Not a claim these would have been actionable on the live one-slot wallet.
        abstain_samples={}
        for key,by_time in event_by_brain.items():
            abstentions=sorted(t for t,e in by_time.items() if e["reason"]=="BRAIN_ABSTAIN")
            stride=max(1,math.ceil(len(abstentions)/max_abstain_sample))
            sample=abstentions[::stride][:max_abstain_sample]
            oracle=[]
            for t in sample:
                rs=conn.execute(
                    "SELECT MAX(net) AS highest,COUNT(*) AS labels FROM opportunity WHERE decision_ms=?",
                    (t,)).fetchone()
                if rs["highest"] is not None:
                    oracle.append((float(rs["highest"]),int(rs["labels"])))
            abstain_samples[key]={
                "total_abstention_decision_times":len(abstentions),
                "sample_stride":stride,
                "sampled_with_any_matured_label":len(oracle),
                "fraction_sampled_times_any_positive_label":round(
                    sum(x[0]>0 for x in oracle)/len(oracle),4) if oracle else None,
                "avg_best_hindsight_net_bp":round(mean(x[0] for x in oracle)*BP,3) if oracle else None,
                "oracle_not_executable":True
            }
        report["hindsight_at_abstention"]=abstain_samples
        report["score_selection_contract"]={
            "rule":"Candidate must have predicted net >0; then max LambdaRank score among candidates, NO TRADE if none positive.",
            "prediction_positive_is_not_conservative_cost_or_uncertainty_margin":True,
            "ranking_score_is_not_predicted_net_return":True,
            "current_top20_watch_not_proven":"3 symbols only, no meaningful 20-of-N exclusion"
        }
        report["verified_read_only"]=True
        return report
    finally:
        conn.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",type=Path,required=True)
    p.add_argument("--run",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():
        raise FileExistsError("REFUSE_TO_OVERWRITE_EXISTING_AUDIT")
    r=audit(a.db,a.run)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(a.output),
          "summary_sha256":r["source_hashes"]["summary_sha256"],
          "brains":{k:{"trades":v["closed_trades"],"predicted_bp":v["prediction_mean_bp"],
                     "realized_bp":v["realized_mean_bp"],"optimism_bp":v["prediction_optimism_bp"]}
                    for k,v in r["brain"].items()},
          "brain_base_heads":r["identical_base_heads"]},indent=2,sort_keys=True))

if __name__=="__main__":
    main()
