#!/usr/bin/env python3
"""NBOT V6 isolated, offline 25x8 LightGBM opportunity forecasting.

Runs ONLY inside the official FreqAI research Docker image. Training labels use
a conservative 5m OHLCV *proxy* exit path, NOT an executable Freqtrade fill.
The subsequent native full-engine one-slot backtest is the economic authority.
All signals are frozen library_signals, not reimplemented or hindsight winners.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/research/user_data/strategies")
from NbotV6LibraryResearch import FAMILIES, library_indicators, library_signals

FIRST="2026-07-15T00:00:00Z"
LAST="2026-10-01T00:00:00Z"
WINDOWS=(30,60,90,180)
FEE=0.001                 # 5bps per side; NOT including future funding
EXTRA_COST=0.0025          # execution stress, NOT observed spread
STOP=.02
ROI=.05
HORIZON=12
BASE_FEATURES=("trend","atr_pct","rsi","macd_norm","volume_ratio",
               "body","range","past_3","past_12")
FAMILIES=tuple(FAMILIES)
START=pd.Timestamp(FIRST)
END=pd.Timestamp(LAST)

def safe_json(path, obj):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(obj,sort_keys=True,indent=2,default=str)+"\n")
    t.replace(p)

def compute_features(v):
    c=v.close.replace(0,np.nan)
    out=pd.DataFrame(index=v.index)
    out["trend"]=(v.nb_ema_20-v.nb_ema_50)/c
    out["atr_pct"]=v.nb_atr/c
    out["rsi"]=v.nb_rsi/100
    out["macd_norm"]=(v.nb_macd-v.nb_macd_signal)/c
    out["volume_ratio"]=(v.volume/v.nb_volume_baseline.replace(0,np.nan)).clip(0,50)
    out["body"]=(v.close-v.open)/c
    out["range"]=(v.high-v.low)/c
    out["past_3"]=c.pct_change(3,fill_method=None)
    out["past_12"]=c.pct_change(12,fill_method=None)
    return out.replace([np.inf,-np.inf],np.nan)

def proxy_label(v, idx, side):
    """Next-open entry; stop-first if both stop and target hit in same candle.
    No claim about intrabar path, spread, funding or exact tradable fill.
    """
    j=idx+1
    if j>=len(v):
        return None
    enter=float(v.open.iloc[j])
    if not np.isfinite(enter) or enter<=0:return None
    polarity=1 if side=="long" else -1
    stop=enter*(1-polarity*STOP)
    take=enter*(1+polarity*ROI)
    final=min(idx+HORIZON,len(v)-1)
    if final<idx+HORIZON:return None
    for k in range(j,final+1):
        bar=v.iloc[k]
        hi,lo=float(bar.high),float(bar.low)
        if polarity==1:
            loss=lo<=stop
            win=hi>=take
        else:
            loss=hi>=stop
            win=lo<=take
        # Conservatively assumes adverse level executes first if ambiguous.
        if loss or win:
            px=stop if loss else take
            return (polarity*(px/enter-1)-FEE,v.date.iloc[k]+pd.Timedelta(minutes=5))
    px=float(v.close.iloc[final])
    return (polarity*(px/enter-1)-FEE,v.date.iloc[final]+pd.Timedelta(minutes=5))

def pair_events(pair, directory):
    filename=pair.replace("/","_").replace(":","_")+"-5m-futures.feather"
    path=Path(directory)/filename
    if not path.is_file():raise RuntimeError("HISTORICAL_5M_MISSING_"+pair)
    original=pd.read_feather(path)
    for col in ("date","open","high","low","close","volume"):
        if col not in original:raise RuntimeError("OHLCV_COLUMN_MISSING_"+col)
    original["date"]=pd.to_datetime(original.date,utc=True)
    original=original.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if original.date.diff().dropna().gt(pd.Timedelta(minutes=5)).any():
        # Don't silently bridge missing bar intervals in forward labels.
        raise RuntimeError("GAPPED_5M_HISTORY_"+pair)
    v=library_indicators(original)
    features=compute_features(v)
    rows=[]
    lower=START-pd.Timedelta(days=max(WINDOWS)+20)
    for family in FAMILIES:
        sig=library_signals(v,family)
        for side in ("long","short"):
            indices=np.flatnonzero(sig[side].to_numpy(dtype=bool))
            for i in indices:
                date=v.date.iloc[int(i)]
                if date<lower or date>=END:continue
                feat=features.iloc[int(i)]
                if feat.isna().any():continue
                target=proxy_label(v,int(i),side)
                if target is None:continue
                actual,observed=target
                if not np.isfinite(actual):continue
                row={"pair":pair,"family":family,"side":side,
                     "date":date,"label_observed_at":observed,
                     "net_proxy":float(actual)}
                row.update({col:float(feat[col]) for col in BASE_FEATURES})
                row["liquidity_turnover_proxy_usdt"]=max(0.0,float(v.close.iloc[int(i)]*v.volume.iloc[int(i)])*.01)
                rows.append(row)
    return rows,hashlib.sha256(path.read_bytes()).hexdigest()

def numeric_matrix(df,pairlist):
    # All encodings are explicit to stop train/eval column mismatches.
    cols=[df[c].to_numpy(dtype=np.float32) for c in BASE_FEATURES]
    cols += [(df.family==f).to_numpy(dtype=np.float32) for f in FAMILIES]
    cols += [(df.side=="short").to_numpy(dtype=np.float32)]
    cols += [(df.pair==p).to_numpy(dtype=np.float32) for p in pairlist]
    return np.column_stack(cols)

def build(raw, pairlist, directory):
    allrows=[]
    hashes={}
    for n,p in enumerate(pairlist,1):
        rows,h=pair_events(p,directory)
        hashes[p]=h
        allrows.extend(rows)
        print(f"DATASET_PROGRESS_PAIR={n}/25 {p} eligible={len(rows)}",flush=True)
    if not allrows:raise RuntimeError("EMPTY_CANDIDATE_UNIVERSE")
    df=pd.DataFrame(allrows).sort_values(["date","pair","family","side"]).reset_index(drop=True)
    if df.duplicated(["date","pair","family","side"]).any():raise RuntimeError("DUPLICATE_CANDIDATE")
    safe_json(raw,{"schema":"v6-global-25x8-candidates-1","pairs":pairlist,
       "candidates":len(df),"history_sha256_by_pair":hashes,
       "proxy_labels_are_not_native_fills":True,
       "funding_in_proxy_labels":False,
       "base_fee_fraction_roundtrip":FEE,
       "additional_execution_stress_fraction":EXTRA_COST})
    return df

def learn_and_rank(df, days, start, stop, outdir, pairlist):
    from lightgbm import LGBMRegressor,LGBMClassifier
    from sklearn.isotonic import IsotonicRegression
    from m2r_v6_global_opportunity_ranker import Opportunity,RankPolicy,choose_global_opportunity
    start=pd.Timestamp(start)
    stop=pd.Timestamp(stop)
    # Entire training label has to have become observable 65min before fit.
    cutoff=start-pd.Timedelta(minutes=65)
    training=df[(df.date>=start-pd.Timedelta(days=days))&
                (df.label_observed_at<=cutoff)].copy()
    # Distinct time-block calibration; NEVER fitted on calibration rows.
    split=start-pd.Timedelta(days=max(5,min(10,days//5)))
    core=training[training.label_observed_at<=split-pd.Timedelta(minutes=65)]
    calib=training[training.date>=split]
    if len(core)<100 or len(calib)<30:
        return {"status":"insufficient_training_or_calibration",
                "window_days":days,"from":str(start),"train":len(core),"calib":len(calib)},[],[]
    X=numeric_matrix(core,pairlist)
    y=core.net_proxy.to_numpy(float)
    reg=LGBMRegressor(n_estimators=90,learning_rate=.04,num_leaves=15,
                     max_depth=5,min_child_samples=50,verbosity=-1,n_jobs=1,
                     random_state=20261018)
    reg.fit(X,y)
    if (core.net_proxy>0).nunique()==2:
        clf=LGBMClassifier(n_estimators=90,learning_rate=.04,num_leaves=15,
                           max_depth=5,min_child_samples=50,verbosity=-1,n_jobs=1,
                           random_state=20261018)
        clf.fit(X,(y>0).astype(int))
    else:clf=None
    predicted=reg.predict(numeric_matrix(calib,pairlist))
    error=float(np.quantile(abs(calib.net_proxy.to_numpy()-predicted),.75))
    # Conservative empirical calibration; don't claim independent net-PnL proof.
    if not np.isfinite(error):raise RuntimeError("UNCALIBRATED_RESIDUAL")
    observed= df[(df.date>=start)&(df.date<stop)].copy()
    if observed.empty:return {"status":"no_valid_signals","window_days":days,"from":str(start)},[],[]
    observed["prediction"]=reg.predict(numeric_matrix(observed,pairlist))
    if clf is not None:
        calibration_raw=clf.predict_proba(numeric_matrix(calib,pairlist))[:,1]
        calibration_truth=(calib.net_proxy.to_numpy()>0).astype(int)
        if len(set(calibration_truth))>1:
            isotonic=IsotonicRegression(out_of_bounds="clip")
            isotonic.fit(calibration_raw,calibration_truth)
            observed["win_probability"]=isotonic.predict(
                clf.predict_proba(numeric_matrix(observed,pairlist))[:,1])
        else:
            observed["win_probability"]=float(np.mean(calibration_truth))
    else:
        observed["win_probability"]=0.0
    # Dynamic overall candidate downside reserve from earlier calibration only.
    worst=float(np.quantile(calib.net_proxy.to_numpy(),.10))
    downside=max(0.0,-worst)
    # Predict at 5m bar close; native engine enters on next candle open.
    policy=RankPolicy(minimum_conservative_edge_fraction=0.001,
        max_model_age_hours=24*15,maximum_uncertainty_fraction=1.0,
        maximum_downside_risk_fraction=1.0,maximum_additional_cost_fraction=.02,
        downside_penalty_weight=.25,allow_exploratory_unvalidated=True)
    decisions=[]
    forecast_rows=[]
    for date,rows in observed.groupby("date",sort=True):
        after=date+pd.Timedelta(minutes=5)
        opportunities=[]
        for x in rows.itertuples(index=False):
            if x.win_probability<0.50:
                continue  # Explicit calibrated probability gate, no fabricated forecast.
            opportunities.append(Opportunity(
                pair=x.pair,family=x.family,side=x.side,
                regime=("trend_up" if x.trend>0.003 else
                        "trend_down" if x.trend< -0.003 else "range"),
                signal_candle_closed_utc=after.isoformat(),
                prediction_generated_utc=after.isoformat(),
                model_training_last_feature_utc=(split-pd.Timedelta(minutes=70)).isoformat(),
                model_fitted_utc=(start-pd.Timedelta(minutes=5)).isoformat(),
                exit_policy="frozen_60m_exit_after_2pct_stop",
                prediction_target="net_return_fraction_after_base_costs",
                predicted_net_return_fraction=float(x.prediction),
                uncertainty_fraction=error,
                additional_execution_cost_fraction=EXTRA_COST,
                downside_risk_fraction=downside,
                # Last closed 5m traded notional / 100 is an explicitly
                # hypothetical liquidity capacity proxy, NOT book depth.
                available_market_depth_usdt=float(x.liquidity_turnover_proxy_usdt),
                intended_stake_usdt=1000,
                has_valid_signal=True,historical_oos_approved=False,
                calibrated_same_target_and_exit=True,valid_model_prediction=True,
                historical_market_eligible=True,training_label_embargo_verified=True))
        result=choose_global_opportunity(opportunities,
            decision_at_utc=after.isoformat(),
            original_25_pairs=pairlist,portfolio_has_open_position=False,policy=policy)
        if result.action=="SELECT":
            p,f,side,exitname=result.winner
            scored=rows[(rows.pair==p)&(rows.family==f)&(rows.side==side)].iloc[0]
            decisions.append({"date":date.isoformat(),"pair":p,"family":f,
                "side":side,"score":result.winning_risk_adjusted_after_cost_fraction,
                "predicted_net":float(scored.prediction),
                "prob_positive":float(scored.win_probability),
                "model_train_cutoff":str(cutoff)})
        rejection=dict(result.rejected_reasons)
        selected_identity=result.winner
        for x in rows.itertuples(index=False):
            identity=(x.pair,x.family,x.side,"frozen_60m_exit_after_2pct_stop")
            key="|".join(identity)
            is_selected=bool(result.action=="SELECT" and identity==selected_identity)
            reason=("SELECTED" if is_selected else
                    "PROBABILITY_BELOW_PREDECLARED_MINIMUM" if x.win_probability<.50
                    else rejection.get(key,"BEATEN_BY_BETTER_OPPORTUNITY"))
            forecast_rows.append({
                "date":date.isoformat(),"pair":x.pair,"family":x.family,
                "side":x.side,"predicted_net_fraction":float(x.prediction),
                "calibrated_positive_probability":float(x.win_probability),
                "uncertainty_fraction":error,"downside_fraction":downside,
                "extra_execution_stress_fraction":EXTRA_COST,
                "exploratory_not_economically_validated":True,
                "selected":is_selected,"reason":reason,
                "model_train_cutoff":str(cutoff)})
    info={"status":"complete","window_days":days,"from":str(start),"to":str(stop),
          "train_samples":len(core),"calibration_samples":len(calib),
          "candidate_count":len(observed),"selected_decisions":len(decisions),
          "calibration_absolute_residual_75pct":error,"calibration_downside_10pct":downside,
          "uses_proxy_labels_without_future_funding":True,
          "calibrated_probability_gate":0.50,
          "liquidity_is_bar_volume_capacity_proxy_not_measured_depth":True,
          "signal_universe_exactly_eight_families":True,
          "model_trained_on_pre_calibration_chronology":True}
    return info,decisions,forecast_rows

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--history",required=True)
    p.add_argument("--config",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--lookback",type=int,required=True,choices=WINDOWS)
    a=p.parse_args()
    out=Path(a.out)
    if out.exists():raise RuntimeError("OUTPUT_EXISTS_NO_OVERWRITE")
    out.mkdir(parents=True)
    config=json.loads(Path(a.config).read_text())
    pairs=config["exchange"]["pair_whitelist"]
    if len(pairs)!=25 or len(set(pairs))!=25:raise RuntimeError("REQUIRE_FIXED_25")
    manifest=out/"historical-data-and-proxy-manifest.json"
    df=build(manifest,pairs,a.history)
    # Future labels are saved for OFFLINE inspection only. Ranking sees strictly
    # historical features from numeric_matrix, never the net_proxy outcome.
    df.to_parquet(out/"all-valid-opportunities-and-research-labels.parquet",index=False)
    all_decisions=[]
    all_forecasts=[]
    audit=[]
    for start in pd.date_range(START,END,freq="7D",inclusive="left"):
        stop=min(start+pd.Timedelta(days=7),END)
        info,decisions,forecasts=learn_and_rank(df,a.lookback,start,stop,out,pairs)
        audit.append(info)
        all_decisions.extend(decisions)
        all_forecasts.extend(forecasts)
        print(f"RANK_PROGRESS lookback={a.lookback} start={start} {info['status']} decisions={len(decisions)}",flush=True)
    # A distinct row per shared completed candle; never select two competing trades.
    d=pd.DataFrame(all_decisions,columns=["date","pair","family","side","score",
                               "predicted_net","prob_positive","model_train_cutoff"])
    if d.duplicated(["date"]).any():raise RuntimeError("MULTIPLE_GLOBAL_WINNERS")
    d.to_csv(out/"global_decisions.csv",index=False)
    pd.DataFrame(all_forecasts).to_parquet(out/"asof-forecasts-and-rejections.parquet",index=False)
    safe_json(out/"training-and-calibration-audit.json",{
        "schema":"v6-global-eight-20261018","window_days":a.lookback,
        "stages":audit,"decisions":len(d),"scored_valid_candidates":len(all_forecasts),
        "all_candidate_rows_saved_for_owner_review":len(df),"historically_viewed_months_not_blind":True,
        "fee_and_exit_proxy_not_native_execution":True,"no_paper_or_live":True,
        "native_portfolio_test_required":True})
    print("OFFLINE_FORECAST_OUTPUT_OK decisions="+str(len(d)),flush=True)

if __name__=="__main__":
    main()
