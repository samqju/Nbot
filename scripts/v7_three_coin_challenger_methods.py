#!/usr/bin/env python3
"""V7 LEARN-3C four-method feasibility experiment (offline, no new model promotion).

A was fitted Jan-Mar. We fit ONLY small calibration/action-policy overlays on
April 2026 labels that matured by May 1; compare with frozen A on May-June in
the identical one-slot simulation. This is development-only, NEVER unseen
economic proof: Jan-Sep 2026 was inspected already.

Methods:
- FreqAI-inspired rolling matured-label prediction bias and conservative margin;
- Qlib-inspired frozen fit/calibration/evaluation, model artifact tracking;
- FinRL-inspired *contextual reward gate*, NOT a full FinRL RL/PPO model;
- River ADWIN optional actual package drift monitor, diagnostic only.
No changes to V7 champion, executor, model artifacts, historical samples,
strategy families or numerical promotion gates.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import os
import sqlite3
import statistics
import sys

from nbot_v7.brain import Brain, MODEL_SCHEMA
from nbot_v7.decision import score
from nbot_v7.experiment import month_start, replay
from nbot_v7.lab import LABEL_POLICY


class FrozenGateBrain:
    """A's immutable ranker/watch heads; only trained abstention filter changes."""

    def __init__(self, baseline, name, *, bias=0.0, margin=0.0, q_by_regime=None):
        self.baseline=baseline
        self.version=name
        self.cutoff_ms=baseline.cutoff_ms
        self.bias=bias
        self.margin=margin
        self.q_by_regime=q_by_regime

    def score(self, rows, kind):
        original=self.baseline.score(rows,kind)
        if kind=="watch":
            return original
        scores=[]
        for r,(expected,rank) in zip(rows,original):
            if self.q_by_regime is None:
                # FreqAI-like after-cost expected-net calibration, not new return model.
                e=expected-self.bias-self.margin
            else:
                # Context-only enter vs abstain (zero reward) trained on April
                # conditional *proxy* outcome labels. A one-step FinRL idea,
                # NOT a calibrated RL policy or actual FinRL framework.
                q=self.q_by_regime.get(r["regime"])
                e=expected if q is not None and q>0 else -1.0
            scores.append((e,rank))
        return scores


def sha(path):
    h=sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(2**20),b""):
            h.update(block)
    return h.hexdigest()


def load_own_frozen_a(run):
    """Load ONLY self-generated, SHA-verified known V7 model artifacts."""
    import joblib
    folder=run/"A_3MONTH_FROZEN"
    manifest=json.loads((folder/"manifest.json").read_text())
    if manifest["brain_version"]!="A_3MONTH_FROZEN" or manifest["schema"]!=MODEL_SCHEMA:
        raise ValueError("WRONG_FROZEN_MODEL_SCHEMA")
    expected={"watch","trade"}
    if set(manifest["files_sha256"])!=expected:
        raise ValueError("UNEXPECTED_FROZEN_MODEL_COMPONENTS")
    for name,expected_sha in manifest["files_sha256"].items():
        if sha(folder/(name+".joblib"))!=expected_sha:
            raise ValueError("TRAINED_MODEL_HASH_MISMATCH")
    return Brain(manifest["brain_version"],joblib.load(folder/"watch.joblib"),
                 joblib.load(folder/"trade.joblib"),{},manifest["training_cutoff_ms"]),manifest


def calibration_april(conn,brain,first,last,*,sampling_step=12):
    """Strictly time-bounded as-of candidates and already-matured April labels.

    Samples whole common decision groups 1h apart to avoid treating an
    arbitrarily large number of almost identical 5m signals as independent.
    The chosen stride is fixed in code before running the experiment.
    """
    cursor=conn.execute(
        """SELECT c.*,o.net,o.label_available_ms
           FROM candidate c JOIN opportunity o
           ON c.decision_ms=o.decision_ms AND c.symbol=o.symbol
           AND c.side=o.side AND c.family=o.family
           WHERE c.decision_ms>=? AND c.decision_ms<?
           AND o.label_available_ms<?
           AND CAST((c.decision_ms-?)/300000 AS INTEGER)%?=0
           ORDER BY c.decision_ms,c.symbol,c.side,c.family""",
        (first,last,last,first,sampling_step))
    count=0
    total_residual=0.0
    residual_by_regime=defaultdict(list)
    score_by_regime=defaultdict(list)
    diffs=[]
    for _ in range(100000):
        rows=cursor.fetchmany(512)
        if not rows:break
        # score() STRICTLY whitelists entry-time fields before passing to model.
        predictions=score(brain,rows,"opportunity")
        for r,(predicted,_) in zip(rows,predictions):
            actual=float(r["net"])
            diff=predicted-actual
            diffs.append(diff)
            total_residual+=diff
            residual_by_regime[r["regime"]].append(diff)
            if predicted>0:
                score_by_regime[r["regime"]].append(actual)
            count+=1
    else:
        raise RuntimeError("EXCESSIVE_CALIBRATION_BATCHES")
    if count<1000:
        raise ValueError("TOO_FEW_MATURED_CALIBRATION_ROWS")
    biases={k:statistics.mean(v) for k,v in residual_by_regime.items()}
    q={k:statistics.mean(v) if len(v)>=50 else None
       for k,v in score_by_regime.items()}
    return {
        "n":count, "bias":total_residual/count,
        "raw_mean_abs_residual_bp":round(statistics.mean(abs(x) for x in diffs)*10000,4),
        "bias_by_regime":biases,
        "enter_reward_by_regime":q,
        "regime_counts":{k:len(v) for k,v in residual_by_regime.items()},
        "positive_prediction_counts":{k:len(v) for k,v in score_by_regime.items()},
        "sampling_policy":"one complete decision group per 12 x 5m bars / exactly 1h",
        "outcomes_matured_before_ms":last,
        "known_before_validation":True,
    }


def drift_selected_only(run, output, first_ms,last_ms, *,library_root=None):
    if library_root:
        sys.path.insert(0,str(library_root))
    try:
        import river
        from river.drift import ADWIN
    except ImportError as e:
        return {"status":"RIVER_NOT_INSTALLED","reason":str(e)[:180]}
    # Drift on frozen A selected-trade signed prediction error as trade outcomes mature.
    # Reading trade JSONL is OFFLINE ex-post diagnosis. Do not mutate current models.
    trades=[]
    with (run/"B_A_trades.jsonl").open() as f:
        for line in f:
            t=json.loads(line)
            if first_ms<=int(t["exit_ms"])<last_ms:
                trades.append(t)
    trades.sort(key=lambda x:(x["exit_ms"],x["decision_ms"]))
    detector=ADWIN(delta=.002)
    changes=[]
    for x in trades:
        err=(float(x["predicted_net"])-float(x["net_after_cost"]))*10000
        detector.update(err)
        if detector.drift_detected:
            changes.append({"available_at_exit_ms":x["exit_ms"],
                            "cumulative_trades":len(changes)+1,
                            "error_bp":round(err,3)})
    return {
        "status":"RIVER_ADWIN_DIAGNOSTIC_NOT_TRADING_SIGNAL",
        "river_version":getattr(river,"__version__", "UNKNOWN"),
        "observations":len(trades), "drift_alerts":len(changes),
        "events":changes[:30],
        "warnings":"ADWIN detects statistical changes in selected outcome errors; no proof of profitability, no model promotion and small dependent sample"
    }


def run(dataset, frozen_run, output, *, river_dir=None):
    if output.exists():raise FileExistsError("REFUSE_OVERWRITE")
    if not dataset.is_file():raise FileNotFoundError(dataset)
    model,manifest=load_own_frozen_a(frozen_run)
    apr=month_start("2026-04")
    may=month_start("2026-05")
    jul=month_start("2026-07")
    if model.cutoff_ms!=apr:
        raise ValueError("FROZEN_MODEL_TRAINING_CUTOFF_AFTER_APRIL")
    conn=sqlite3.connect(dataset.resolve().as_uri()+"?mode=ro",uri=True)
    conn.row_factory=sqlite3.Row
    try:
        meta=dict(conn.execute("SELECT k,v FROM meta"))
        if meta.get("build_complete")!="true" or meta.get("policy")!=LABEL_POLICY:
            raise ValueError("INVALID_MATURED_SOURCE_POLICY")
        assert int(meta["start_ms"])<=apr and int(meta["end_ms"])>=jul
        calibration=calibration_april(conn,model,apr,may)
        brain_set=[
          model,
          FrozenGateBrain(model,"FREQAI_STYLE_APRIL_RESIDUAL",bias=calibration["bias"]),
          FrozenGateBrain(model,"COST_STRESS_25BP_ABSTAIN",
                          bias=calibration["bias"],margin=.0025),
          FrozenGateBrain(model,"FINRL_STYLE_APRIL_CONTEXT_ACTION_Q",
                          q_by_regime=calibration["enter_reward_by_regime"]),
        ]
        scores={}
        for brain in brain_set:
            account=replay(conn,brain,may,jul)
            if not account["account_complete"]:
                raise ValueError("INCOMPLETE_EVALUATION_ACCOUNT_NO_RESULT")
            scores[brain.version]={
                k:v for k,v in account.items() if k!="trades"
            }
            scores[brain.version]["mean_realized_net_bp"]=round(
                account["net_pnl_usdt"]*10/len(account["trades"]),4
            ) if account["trades"] else None
        river=drift_selected_only(frozen_run,output,apr,jul,library_root=river_dir)
        result={
            "scope":"DEVELOPMENT_ONLY_APRIL_CALIBRATION_MAY_JUNE_EVALUATION_NO_PROMOTION",
            "method_labels":{
                "FreqAI":"FreqAI-inspired matured-label / rolling retrain contract; NO FreqAI installed or trained",
                "Qlib":"Qlib-inspired fixed chronological workflow with saved precommitted splits; NO Qlib dependency",
                "FinRL":"FinRL-inspired contextual enter/no-trade reward-gate; NOT FinRL RL/PPO and not wallet-correct off-policy reward training",
                "River":"actual River ADWIN package if installed; drift alerts diagnostic only",
            },
            "source_hashes":{
                "frozen_manifest":sha(frozen_run/"A_3MONTH_FROZEN"/"manifest.json"),
                "frozen_model_trade":manifest["files_sha256"]["trade"],
                "frozen_model_watch":manifest["files_sha256"]["watch"],
                "previous_replay_summary":sha(frozen_run/"summary.json"),
            },
            "cutoffs_ms":{
                "frozen_original_A_fit":apr,
                "new_calibration_evidence":[apr,may],
                "validation_replay":[may,jul]
            },
            "calibration":calibration,
            "replays":scores,
            "river_drift":river,
            "no_trade_baseline_usdt":0,
            "warnings":[
              "May-June development data from 2026 already used for V7 work; NOT pristine OOS.",
              "One-slot 5m OHLC proxy, not actual exchange fills; contract lifecycle not verified.",
              "Cost-stress 25bp margin is a policy sensitivity, not a validated optimum.",
              "Contextual bandit reward uses overlapping virtual offers, not independently executable exploration.",
              "Do not tune parameters retrospectively to improve these May-June results.",
              "All challengers remain research only. No replacement of champion A or live authority."
            ],
        }
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        return result
    finally:
        conn.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True,type=Path)
    p.add_argument("--frozen-run",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    p.add_argument("--river-dir",type=Path)
    a=p.parse_args()
    r=run(a.db,a.frozen_run,a.out,river_dir=a.river_dir)
    print(json.dumps({"status":r["scope"],"calibration":r["calibration"],
                      "replays":{k:{"trades":v["selected_trades"],
                                     "net_usdt":v["net_pnl_usdt"],
                                     "abstentions":v["stats"].get("brain_abstentions",0)}
                                 for k,v in r["replays"].items()},
                      "river_drift":r["river_drift"]},indent=2,sort_keys=True))
if __name__=="__main__":
    main()
