#!/usr/bin/env python3
"""Offline, read-only prelaunch diagnostic: explain ZERO selected entries.

Must run with the official FreqAI image; reads saved candidate/forecast parquet
and audit JSON, prints distributions and model decision reasons only. Does not
fit models, change policies, restart jobs, or place orders.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import pandas as pd

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--root",type=Path,default=Path("/results"))
    a.add_argument("--w",type=int,default=30,choices=(30,60,90,180))
    args=a.parse_args()
    root=args.root
    w=root/f"w{args.w}"
    f=pd.read_parquet(w/"asof-forecasts-and-rejections.parquet")
    audit=json.loads((w/"training-and-calibration-audit.json").read_text())
    snap=json.loads((root/"shared-candidate-universe/immutable-candidate-cache-audit.json").read_text())
    print("WINDOW",args.w,"FORECAST_COUNT",len(f),"SAVED_CANDIDATE_COUNT",snap.get("rows"),"SELECTED",audit.get("decisions"))
    print("FORECAST_COLUMNS",list(f.columns))
    print("REJECTION_REASONS",dict(Counter(f["reason"])))
    print("SIGNAL_FAMILY_COUNTS",dict(Counter(f["family"])))
    print("CANDIDATES_PER_DATE",f.groupby("date").size().describe().to_dict())
    for col in ("predicted_net_fraction","calibrated_positive_probability","uncertainty_fraction","downside_fraction","extra_execution_stress_fraction"):
        print(col,"five_number",f[col].describe(percentiles=[.1,.25,.5,.75,.9,.95,.99]).to_dict())
    print("STAGE_AUDIT",[(x.get("from"),x.get("status"),x.get("candidate_count"),x.get("selected_decisions"),x.get("calibration_absolute_residual_75pct"),x.get("calibration_downside_10pct")) for x in audit.get("stages",[])])
    if len(f) and "predicted_net_fraction" in f:
        f["conservative_before_regime"]=f["predicted_net_fraction"]-f["uncertainty_fraction"]-f["extra_execution_stress_fraction"]-0.25*f["downside_fraction"]
        x=f.nlargest(10,"conservative_before_regime")
        print("TOP_RISK_ADJUSTED_PROXY_10",x[["date","pair","family","side","predicted_net_fraction","calibrated_positive_probability","uncertainty_fraction","downside_fraction","conservative_before_regime","reason"]].to_dict("records"))

if __name__=="__main__":main()
