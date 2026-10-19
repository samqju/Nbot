#!/usr/bin/env python3
"""Read-only all-four-window AI selection-rejection summary.

The native Freqtrade portfolio is the economic authority; these descriptive
statistics do not imply a model can execute favorable future price moves.
"""
from pathlib import Path
import argparse
import json
import pandas as pd

p=argparse.ArgumentParser()
p.add_argument("--root",type=Path,default=Path("/results"))
args=p.parse_args()
totals={}
for w in (30,60,90,180):
    folder=args.root/f"w{w}"
    f=pd.read_parquet(folder/"asof-forecasts-and-rejections.parquet")
    audit=json.loads((folder/"training-and-calibration-audit.json").read_text())
    counts={str(k):int(v) for k,v in f["reason"].value_counts().items()}
    probs=f["calibrated_positive_probability"]
    preds=f["predicted_net_fraction"]
    stress=f["extra_execution_stress_fraction"]
    score=(preds-f["uncertainty_fraction"]-stress-0.25*f["downside_fraction"])
    totals[str(w)]={
      "scored_candidates":len(f),
      "selected_trades":int(audit["decisions"]),
      "reasons":counts,
      "above_50pct_probability":int((probs>=.5).sum()),
      "median_positive_probability":round(float(probs.median()),6),
      "median_predicted_base_cost_net_fraction":round(float(preds.median()),8),
      "maximum_conservative_net_fraction_before_other_gates":round(float(score.max()),8),
      "above_one_tenth_pct_conservative_edge_before_other_gates":int((score>.001).sum()),
      "every_rejected_candidate_is_preserved":len(f)==sum(counts.values()) and
             int(audit["decisions"])==int(f["selected"].sum())
    }
print(json.dumps({"schema":"v6-global-four-window-selection-rejection-summary-1",
                  "windows":totals,"read_only":True,
                  "do_not_relax_thresholds_using_viewed_historical_windows":True},
                 sort_keys=True,indent=2))
