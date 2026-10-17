"""Offline V6 full-engine frozen-native-model replay audit (DO NOT TRAIN / TRADE).

Compare all original full-window FreqAI prediction Feathers with the shorter
replay after verifying that fitted on-disk model binary SHA256 did not change.
Reports sampled prediction equality and ALL signal rows only if archive
contains compatible native exported signals. No pickle deserialization from
untrusted paths; limit to self-created V6 research ZIPs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True, type=Path)
    p.add_argument("--model-root", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--expected-pairs", type=int, default=25)
    args=p.parse_args()
    assert args.expected_pairs == 25
    model_files=sorted(args.model_root.glob("sub-train-*/*_model.joblib"))
    before_lines=args.snapshot.joinpath("model-sha256-before.txt").read_text().splitlines()
    before={path:sha for sha, path in [line.split(maxsplit=1) for line in before_lines]}
    assert len(before)==25 and len(model_files)==25
    changes=[]
    for path in model_files:
        exact=str(path)
        if exact not in before or digest(path)!=before[exact]:
            changes.append(exact)
    first=args.snapshot/"backtesting_predictions"
    second=args.model_root/"backtesting_predictions"
    prev=sorted(first.glob("*_prediction.feather"))
    now=sorted(second.glob("*_prediction.feather"))
    if len(prev)!=25 or len(now)!=25:
        raise RuntimeError(f"INCOMPLETE_PREDICTIONS first={len(prev)} replay={len(now)}")
    mismatches=[]
    rows_compared=0
    schema_inconsistencies=0
    per_pair=[]
    for original in prev:
        replay=second/original.name
        if not replay.exists():
            mismatches.append({"file":original.name,"reason":"MISSING_REPLAY_FILE"})
            continue
        a=pd.read_feather(original)
        b=pd.read_feather(replay)
        issues=[]
        if list(a.columns)!=list(b.columns):
            issues.append("DIFFERENT_COLUMNS")
            schema_inconsistencies+=1
        elif not (0 < len(b) <= len(a)):
            issues.append(f"INVALID_ROWS original={len(a)} replay={len(b)}")
        else:
            for col in a.columns:
                v=a[col].iloc[:len(b)].reset_index(drop=True)
                w=b[col].reset_index(drop=True)
                try:
                    if pd.api.types.is_numeric_dtype(v) and pd.api.types.is_numeric_dtype(w):
                        eq=np.allclose(v.astype(float).to_numpy(),w.astype(float).to_numpy(),
                                       rtol=1e-10,atol=1e-12,equal_nan=True)
                    else:
                        eq=v.equals(w)
                except (TypeError,ValueError):
                    eq=v.equals(w)
                if not eq:
                    issues.append(col)
            rows_compared+=len(b)
        per_pair.append({"file":original.name,"full_rows":len(a),
                         "replay_rows":len(b),"mismatch_columns":issues[:20]})
        if issues:
            mismatches.append({"file":original.name,"issues":issues[:20]})
    d={"scope":"Freqtrade 2026.9 full native engine using originally saved on-disk purged LightGBM model bundles, Oct8-Oct10 training and Oct8-Oct9 shortened replay",
       "model_count":len(model_files),"model_binary_sha_changes":len(changes),
       "model_changes":changes[:20],"prediction_file_count_before":len(prev),
       "prediction_file_count_after":len(now),
       "rows_of_replayed_predictions_compared":rows_compared,
       "prediction_files_with_mismatches":len(mismatches),
       "schema_mismatches":schema_inconsistencies,
       "details":per_pair,"mismatch_details":mismatches[:25],
       "all_native_prediction_cache_replay_checks_pass":len(model_files)==25 and not changes and not mismatches and rows_compared>0,
       "important_scope_limit":"This does not run lookahead-analysis, whose current official implementation wipes FreqAI model folder per replay. Neither profitability nor actual execution spreads proved."}
    args.output.write_text(json.dumps(d,indent=2)+"\n")
    print("NATIVE_ENGINE_SAVED_MODEL_REPLAY",d["all_native_prediction_cache_replay_checks_pass"],
          "unchanged_binary_models",25-len(changes),
          "prediction_files",len(prev),
          "matching_rows",rows_compared,
          "mismatch_files",len(mismatches),flush=True)
    if mismatches:
        print("FIRST_ERRORS",mismatches[:2],flush=True)
    return 0 if d["all_native_prediction_cache_replay_checks_pass"] else 2


if __name__=="__main__":
    raise SystemExit(main())
