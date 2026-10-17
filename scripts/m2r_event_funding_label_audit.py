#!/usr/bin/env python3
"""V6 bounded historical label-cost audit on previously reviewed Oct8–15.

This is NOT a new backtest: each same-bar overlapping setup is hypothetical.
Event-rate history is used ONLY to compute future target labels/outcomes.
Compare static 1bp funding versus event rates; mark price from COMPLETED
hourly candle, NOT exact venue settlement mark. Actual spread/slippage
and bid/ask fills were never observed, so cost-certification still NO-GO.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"user_data"/"strategies"))
sys.path.insert(0,str(ROOT/"scripts"))
from nbot_trade_outcome import CostPolicy, setups, outcome, KINDS
from m2r_event_cost_labels import FundingSchedule, funding_adjusted_outcome

START=pd.Timestamp("2026-10-08T00:00:00Z")
END=pd.Timestamp("2026-10-16T00:00:00Z")
PENALTY_BPS=(0,5,10,15,25)

def main()->int:
    a=argparse.ArgumentParser()
    a.add_argument("--data",required=True,type=Path)
    a.add_argument("--config",required=True,type=Path)
    a.add_argument("--output",required=True,type=Path)
    z=a.parse_args()
    config=json.loads(z.config.read_text())
    assert not config["exchange"]["key"] and not config["exchange"]["secret"]
    pairs=config["exchange"]["pair_whitelist"]
    assert len(pairs)==25 and config["freqai"]["feature_parameters"]["label_period_candles"]==12
    cost=CostPolicy()
    result={
        "intent":"Read-only re-score of previously observed Oct 8-15 2026 hypothetical setups. NEVER an executed trade or untouched test",
        "pair_count":25,"labels_examined":0,"static_positive":0,"event_adjusted_positive":0,
        "positive_to_negative":0,"negative_to_positive":0,
        "funding_events_crossed_by_hypothetical_labels":0,
        "ambiguous_funding_event_exit_boundaries":0,
        "mean_static_net_fraction":0,"mean_event_net_fraction":0,
        "mean_estimated_signed_funding_paid_fraction":0,
        "positive_counts_by_added_roundtrip_execution_bps":{},
        "per_pair":[],
        "label_original_fee_bp_roundtrip":10,
        "label_original_slippage_bp_roundtrip_proxy":10,
        "label_flat_funding_bp_per_hypothetical_trade":1,
        "event_funding_mark_price_method":"last COMPLETED 1h mark close at event, not exact exchange settlement mark",
        "venue_spreads_observed":False,"stops_fill_observed":False,
        "releases_or_trades_permitted":False,"cost_gate_pass":False,
    }
    static_values=[]
    event_values=[]
    signed=[]
    for pair in pairs:
        token=pair.replace("/","_").replace(":","_")
        def load(suffix):
            frame=pd.read_feather(z.data/(token+suffix))
            frame["date"]=pd.to_datetime(frame["date"],utc=True)
            assert frame["date"].is_unique and frame["date"].is_monotonic_increasing
            return frame
        candles=load("-5m-futures.feather")
        funding=load("-1h-funding_rate.feather")
        mark=load("-1h-mark.feather")
        funding=funding.loc[funding.date>=START].reset_index(drop=True)
        sched=FundingSchedule.from_candles(funding,mark)
        signals=setups(candles)
        stamps=candles["date"]
        pair_static=[]
        pair_event=[]
        events=0
        ambiguous=0
        for i in np.flatnonzero(((stamps>=START)&(stamps<END)).to_numpy()):
            if i+cost.horizon>=len(candles):
                continue
            for kind in KINDS:
                if not bool(signals[kind].iloc[i]):
                    continue
                side=-1 if kind.endswith("_short") else 1
                old=outcome(candles,int(i),side,cost)
                if old is None:
                    continue
                new=funding_adjusted_outcome(candles,int(i),side,sched,cost)
                assert new is not None
                pair_static.append(float(old["net_return"]))
                pair_event.append(float(new["event_aware_label_net_return"]))
                signed.append(float(new["estimated_signed_funding_paid_fraction"]))
                events+=new["funding_events_crossed_estimate"]
                ambiguous+=int(new["funding_settlement_exit_boundary_ambiguous"])
        old=np.array(pair_static)
        new=np.array(pair_event)
        if not len(new):
            raise RuntimeError("NO_ELIGIBLE_LABELS_FOR_PAIR: "+pair)
        result["per_pair"].append({
            "pair":pair,"hypothetical_opportunities":len(new),
            "static_positive":int((old>0).sum()),
            "event_adjusted_positive":int((new>0).sum()),
            "funding_events_crossed_in_overlapping_opportunities":events,
            "ambiguous_settlement_boundaries":ambiguous,
            "mean_difference_bp":float(np.mean((new-old)*1e4)),
            "max_absolute_difference_bp":float(np.max(np.abs(new-old))*1e4),
        })
        static_values.extend(old.tolist())
        event_values.extend(new.tolist())
        result["funding_events_crossed_by_hypothetical_labels"]+=events
        result["ambiguous_funding_event_exit_boundaries"]+=ambiguous
        print("CHECK",pair,"hypothetical",len(new),"event_count",events,"ambiguous",ambiguous,flush=True)
    a1=np.array(static_values)
    b1=np.array(event_values)
    result.update({
        "labels_examined":len(a1),"static_positive":int((a1>0).sum()),
        "event_adjusted_positive":int((b1>0).sum()),
        "positive_to_negative":int(((a1>0)&(b1<=0)).sum()),
        "negative_to_positive":int(((a1<=0)&(b1>0)).sum()),
        "mean_static_net_fraction":float(a1.mean()),
        "mean_event_net_fraction":float(b1.mean()),
        "mean_estimated_signed_funding_paid_fraction":float(np.mean(signed)),
        "positive_counts_by_added_roundtrip_execution_bps":{
            str(bp):int((b1>bp/10000).sum()) for bp in PENALTY_BPS
        },
    })
    z.output.write_text(json.dumps(result,indent=2)+"\n")
    print("FINISHED",result["labels_examined"],"static wins",result["static_positive"],
          "event wins",result["event_adjusted_positive"],
          "ambiguous",result["ambiguous_funding_event_exit_boundaries"],flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
