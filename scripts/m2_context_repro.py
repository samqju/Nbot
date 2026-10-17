#!/usr/bin/env python3
"""Compare frozen full-25 vs one-pair FreqAI predictions on the same timestamps.

A changed prediction may reflect pairlist-dependent training/data selection,
not automatically future leakage. This is a reproducibility test, not a
certificate of causal validity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

def compare(ref: pd.DataFrame, single: pd.DataFrame) -> dict:
    if ref["date"].duplicated().any() or single["date"].duplicated().any():
        raise ValueError("Duplicate prediction timestamp")
    cols = ["date", "&-forward_return", "&-forward_return_mean",
            "&-forward_return_std", "do_predict", "DI_values"]
    l = ref[cols].sort_values("date")
    r = single[cols].sort_values("date")
    d = l.merge(r, on="date", validate="one_to_one", suffixes=("_full", "_single"),
                how="outer", indicator=True)
    if not (d["_merge"] == "both").all():
        raise ValueError("Missing timestamps: must compare identical time periods")
    report = {"candles": len(d)}
    for col in cols[1:]:
        a = d[f"{col}_full"].to_numpy(dtype=float)
        b = d[f"{col}_single"].to_numpy(dtype=float)
        mask = np.isfinite(a) & np.isfinite(b)
        diffs = abs(a[mask] - b[mask])
        report[col] = {
            "changed_values_over_tolerance_1e-9": int(np.sum(diffs > 1e-9)),
            "max_absolute_diff": round(float(np.max(diffs)) if len(diffs) else 0, 10),
            "finite_pairs": int(mask.sum())
        }
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--full", required=True, type=Path)
    p.add_argument("--single", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--coins", nargs="+", default=["btc", "eth"])
    args=p.parse_args()
    result = {}
    for coin in args.coins:
        fulls=sorted((args.full/"backtesting_predictions").glob(f"cb_{coin}_*_prediction.feather"))
        singles=sorted((args.single/"backtesting_predictions").glob(f"cb_{coin}_*_prediction.feather"))
        if len(fulls)!=1 or len(singles)!=1:
            raise ValueError(f"{coin}: missing pair predictions full:{len(fulls)} single:{len(singles)}")
        result[coin]=compare(pd.read_feather(fulls[0]), pd.read_feather(singles[0]))
        print(coin.upper(),result[coin])
    report={"purpose":"Same history + model features; compare models fitted in 25-pair vs one-pair FreqAI context",
            "limitations":["Differences do not prove information leakage.",
                           "Equal predictions would not establish overall no-leakage.",
                           "Training must be separately audited for chronological label isolation."],
            "results":result}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
