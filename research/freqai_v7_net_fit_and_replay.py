#!/usr/bin/env python3
"""Research-only: real FreqAI LightGBMRegressor.fit on V7 after-cost opportunities.

This is NOT FreqAI's native per-pair start_backtesting orchestration.
It calls the REAL FreqAI v2026.9 LightGBMRegressor.fit API with causal V7
candidate features and already-matured V7 trade-net labels, then uses V7's
single-slot replay to compare cross-coin / cross-family predictions.
DO NOT activate a live exchange or use this code for model promotion.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from collections import Counter
import json
import math
import os
import sqlite3
import statistics

import numpy as np
import pandas as pd
import joblib

from freqtrade.freqai.prediction_models.LightGBMRegressor import LightGBMRegressor
from nbot_v7.brain import vector
from nbot_v7.experiment import month_start, replay
from nbot_v7.lab import LABEL_POLICY
from nbot_v7.data import BAR_MS
from nbot_v7.freqai_research_bridge import (
    TARGET, KNOWN_SYMBOLS, FreqAINetResearchBrain, NetForecast
)

FEATURES = tuple([f"past_{i}" for i in range(len(vector({
    "features":json.dumps({k:1.0 for k in (
        "r3","r12","r48","atr","volume_ratio","range_12","body",
        "btc_r3","btc_r12","btc_r48","btc_atr","vs_btc","utc_hour")}),
    "side":"LONG","family":"momentum_3"
},"opportunity")))] + ["coin_btc","coin_eth","coin_sol"])
CAL_DAYS = 14
MAX_ROWS = 350000  # Three-coin cohort only; no time-stride or group thinning
STRESS = 0.0025  # Predeclared extra 25bps notional roundtrip, never optimized on test.


class FreqAIResearchNetRegressor(LightGBMRegressor):
    def get_init_model(self, pair):
        # Prevent any model from borrowing a fitted state from a later window.
        return None


def feature_vector(row):
    base=vector(row,"opportunity")
    if row["symbol"] not in KNOWN_SYMBOLS:
        raise ValueError("OUTSIDE_THREE_COIN_RESEARCH_COHORT")
    return base+[float(row["symbol"]==s) for s in ("BTCUSDT","ETHUSDT","SOLUSDT")]


def matrix(rows):
    return pd.DataFrame(
        np.asarray([feature_vector(row) for row in rows], dtype="float32"),
        columns=FEATURES,
    )


def digest(path):
    h=sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(2**20),b""):
            h.update(block)
    return h.hexdigest()


def existing_source(db):
    if not Path(db).is_file():
        raise FileNotFoundError("EXISTING_THREE_COIN_LABELS_REQUIRED")
    c=sqlite3.connect(Path(db).resolve().as_uri()+"?mode=ro",uri=True)
    c.row_factory=sqlite3.Row
    meta=dict(c.execute("SELECT k,v FROM meta"))
    if meta.get("build_complete")!="true" or meta.get("policy")!=LABEL_POLICY:
        c.close()
        raise ValueError("INCOMPLETE_OR_INCOMPATIBLE_V7_LABELS")
    coins=set(json.loads(meta["coverage"])["symbols"])
    if coins!=KNOWN_SYMBOLS:
        c.close()
        raise ValueError("COHORT_NOT_EXACTLY_BTC_ETH_SOL")
    return c


def actual_freqai_fit(training_features, training_net, artifact_dir):
    """Invoke upstream FreqAI's own LightGBMRegressor.fit(), not V7 fit_head."""
    official=object.__new__(FreqAIResearchNetRegressor)
    official.freqai_info={
        "data_split_parameters":{"test_size":0},
        "activate_tensorboard":False,
    }
    official.model_training_parameters={
        "n_estimators":120,"learning_rate":.04,"max_depth":5,"num_leaves":15,
        "min_child_samples":20,"reg_lambda":2,"n_jobs":1,
        "random_state":72026,"verbosity":-1,
    }
    features=training_features
    labels=pd.DataFrame({TARGET: np.asarray(training_net,dtype="float32")})
    dataset={
        "train_features":features,
        "train_labels":labels,
        "train_weights":np.ones(len(features),dtype="float32"),
        "test_features":features.iloc[:0],
        "test_labels":labels.iloc[:0],
        "test_weights":np.empty(0,dtype="float32"),
    }
    dk=SimpleNamespace(pair="BTC_ETH_SOL_GROUPED_RESEARCH",data_path=artifact_dir)
    return official.fit(dataset,dk)


def fit_at(conn, cutoff, output_dir):
    output_dir.mkdir(parents=True,exist_ok=False)
    # The old group-size-capped helper yielded ~39k rows for BOTH 3m and
    # 6m fits, accidentally hiding most new evidence. For this fixed three-
    # coin sample, read ALL prior-matured opportunity labels; fail closed if
    # the capacity budget would be exceeded instead of silently resampling.
    rows=conn.execute(
        "SELECT * FROM opportunity WHERE decision_ms<? AND label_available_ms<? "
        "ORDER BY decision_ms,symbol,side,family",(cutoff,cutoff)
    ).fetchall()
    if len(rows)>MAX_ROWS:
        raise RuntimeError("THREE_COIN_TRAINING_CAPACITY_REQUIRES_EXPLICIT_REDESIGN")
    hold_start=cutoff-CAL_DAYS*86400000
    # Calibrator never touches future labels from the training cutoff.
    training=[r for r in rows
              if r["decision_ms"]<hold_start and r["label_available_ms"]<hold_start]
    calibration=[r for r in rows
                 if hold_start<=r["decision_ms"]<cutoff and r["label_available_ms"]<cutoff]
    if len(training)<5000 or len(calibration)<500:
        raise ValueError("INSUFFICIENT_CHRONOLOGICAL_TRAIN_AND_CALIBRATION_ROWS")
    m=actual_freqai_fit(matrix(training),[float(x["net"]) for x in training],output_dir)
    # This uncertainty estimator is a development-only *global* prediction
    # residual quantile, not yet selection-conditional model uncertainty.
    pred=np.asarray(m.predict(matrix(calibration))).reshape(-1)
    actual=np.asarray([float(r["net"]) for r in calibration])
    abs_err=np.abs(pred-actual)
    q75=float(np.quantile(abs_err,.75))
    model_path=output_dir/"actual_freqai_net_lgbm.joblib"
    joblib.dump(m,model_path)
    info={
        "trainer":"REAL_FREQAI_LIGHTGBMREGRESSOR_FIT_CUSTOM_RESEARCH_HARNESS",
        "freqai_native_time_series_start_backtesting_used":False,
        "cutoff_ms":cutoff, "max_matured_train_label_ms":max(int(r["label_available_ms"]) for r in training),
        "max_matured_calibration_label_ms":max(int(r["label_available_ms"]) for r in calibration),
        "calibration_start_ms":hold_start,
        "training_rows":len(training),"calibration_rows":len(calibration),
        "all_source_rows_selected_by_group_sampler":len(rows),
        "calibration_pred_minus_realized_bp":round(float(np.mean(pred-actual))*1e4,3),
        "calibration_abs_error_q75_bp":round(q75*1e4,3),
        "uncertainty_net":q75,
        "feature_names":FEATURES,
        "model_sha256":digest(model_path),
        "target":TARGET,"policy":LABEL_POLICY,
        "source_grade":"UNVERIFIED_ARCHIVE_LIFECYCLE_OFFLINE_5M_PROXY",
    }
    (output_dir/"manifest.json").write_text(json.dumps(info,indent=2,sort_keys=True)+"\n")
    return info


def prediction_export(conn,model_path,manifest,start_ms,end_ms,path):
    if digest(model_path)!=manifest["model_sha256"]:
        raise ValueError("MODEL_ARTIFACT_SHA256_MISMATCH")
    # Joblib load only for artifact created by THIS explicit local experiment.
    model=joblib.load(model_path)
    total=0
    with path.open("x",encoding="utf-8") as f:
        cursor=conn.execute(
            "SELECT * FROM candidate WHERE decision_ms>=? AND decision_ms<? ORDER BY decision_ms,symbol,side,family",
            (start_ms,end_ms))
        while True:
            rows=cursor.fetchmany(2048)
            if not rows:
                break
            scores=np.asarray(model.predict(matrix(rows))).reshape(-1)
            for row,expected in zip(rows,scores):
                ms=int(row["decision_ms"])
                record={
                    "decision_ms":ms,
                    "symbol":row["symbol"],"side":row["side"],"family":row["family"],
                    "source_hash":row["source_hash"],
                    "feature_bar_open_ms":ms,"features_ready_ms":ms+BAR_MS,
                    "training_labels_available_before_ms":manifest["cutoff_ms"],
                    "model_sha256":manifest["model_sha256"],
                    "target":TARGET,"label_policy":LABEL_POLICY,
                    "expected_net":float(expected),
                    "uncertainty_net":manifest["uncertainty_net"],
                }
                NetForecast.from_mapping(record)
                f.write(json.dumps(record,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
                total+=1
    return {"records":total,"sha256":digest(path)}


def evaluate(conn,forecast_file,start,end,cutoff,scenario):
    model=FreqAINetResearchBrain.from_jsonl(
        forecast_file,cutoff_ms=cutoff,
        version=scenario,
        uncertainty_weight=0 if scenario.endswith("RAW") else 1,
        cost_stress=STRESS if scenario.endswith("STRESS") else 0,
    )
    return replay(conn,model,start,end)


def slim(report):
    return {k:v for k,v in report.items() if k!="trades"}


def run(db,output):
    if output.exists():raise FileExistsError("REFUSE_EXISTING_CHALLENGER_DIRECTORY")
    output.mkdir(parents=True)
    c=existing_source(db)
    a=month_start("2026-04")
    b=month_start("2026-07")
    end=month_start("2026-10")
    try:
        ma=fit_at(c,a,output/"A")
        mb=fit_at(c,b,output/"B")
        if mb["training_rows"] < ma["training_rows"]*1.3:
            raise RuntimeError("SIX_MONTH_BRAIN_NOT_USING_MEANINGFULLY_MORE_TRAINING_EVIDENCE")
        for name,manifest,start,stop in (("A_PERIOD2",ma,a,b),
                                          ("A_PERIOD3",ma,b,end),
                                          ("B_PERIOD3",mb,b,end)):
            model_dir=output/("A" if name.startswith("A") else "B")
            prediction_export(c,model_dir/"actual_freqai_net_lgbm.joblib",
                              manifest,start,stop,output/(name+"_net_forecasts.jsonl"))
        reports={}
        for period,start,stop,models in (
            ("APR_JUN",a,b,("A",)),("JUL_SEP",b,end,("A","B"))
        ):
            for model_key in models:
                path=output/(
                    ("A_PERIOD2" if period=="APR_JUN" else model_key+"_PERIOD3")+
                    "_net_forecasts.jsonl"
                )
                cutoff=a if model_key=="A" else b
                for policy,suffix in (("RAW","RAW"),("UNCERTAINTY","UNCERTAINTY"),
                                      ("UNCERTAINTY_STRESS","STRESS")):
                    brain_name=f"{period}_{model_key}_{suffix}"
                    reports[brain_name]=slim(evaluate(c,path,start,stop,cutoff,brain_name))
        report={
            "experiment":"REAL_FREQAI_FIT_AFTERCOST_MULTISTRATEGY_3COIN_EXPLORATORY_V1",
            "original_v7_champion_untouched":True,
            "native_freqai_whole_trade_backtest":False,
            "training_A":ma,"training_B":mb,
            "replays":reports,
            "NO_TRADE_BASELINE_USDT":0.0,
            "warnings":[
                "Original July-Sep 2026 already inspected: NOT PRISTINE HOLDOUT.",
                "Real FreqAI LightGBMRegressor.fit called; full per-pair FreqAI start_backtesting NOT used.",
                "Source labels are V7 5m paper stop-first proxy, NOT actual Binance fills.",
                "Global uncertainty estimated on calibration candidates, NOT selected top trades.",
                "No optimizer hyperparameter search, promotion, live/paper orders, or universe growth.",
            ],
        }
        (output/"summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        print(json.dumps({
            "A_train":ma["training_rows"],"B_train":mb["training_rows"],
            "A_cal_bp":ma["calibration_abs_error_q75_bp"],
            "B_cal_bp":mb["calibration_abs_error_q75_bp"],
            "replays":{k:{"trades":v["selected_trades"],"pnl":v["net_pnl_usdt"],
                           "complete":v["account_complete"]}
                       for k,v in reports.items()}
        },indent=2))
    finally:
        c.close()


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--db",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    run(args.db,args.output)
