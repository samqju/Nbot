"""V6 saved-model lookahead trace decision-time validator.

The *stock native* Freqtrade lookahead has_bias flag is not overwritten.
This auditable supplemental check fails closed unless all columns of the
native indicator dataframes match through each trade's decision timestamp.
"""
from __future__ import annotations
import argparse
import csv
import json
from datetime import timedelta
from pathlib import Path
import pandas as pd


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--trace",required=True,type=Path)
    p.add_argument("--official-csv",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    d=json.loads(a.trace.read_text())
    native=list(csv.DictReader(a.official_csv.open()))
    if len(native)!=1:
        raise RuntimeError("REQUIRE_ONE_NATIVE_STRATEGY_ROW")
    n=native[0]
    observations=d["sampled_official_indicator_comparisons"]
    diff_columns=set()
    for sample in observations:
        ts=pd.Timestamp(sample["decision_time"])
        last=pd.Timestamp(sample["replay_last_candle"])
        if last != ts + timedelta(minutes=5):
            raise RuntimeError("INVALID_OFFICIAL_TRUNCATION_DECISION_BOUNDARY")
        if sample["native_full_data_rows_differing_at_or_before_decision"] or sample[
                "native_full_data_columns_changed_at_or_before_decision"]:
            raise RuntimeError("ACTUAL_DECISION_INDICATOR_DIFFERENCE")
        for x in sample["differences"]:
            diff_columns.add(x["column"])
            if x["differing_rows"] != 1 or len(x["first_three"])!=1:
                raise RuntimeError("NON_TERMINAL_OR_MULTIPLE_NATIVE_COLUMN_DIFFERENCES")
            if pd.Timestamp(x["first_three"][0]["row_date"]) != last:
                raise RuntimeError("DIFFERENCE_NOT_LIMITED_TO_TRUNCATED_TERMINAL_ROW")
    if (len(observations)!=6 or n["has_bias"].lower()!="true"
          or n["biased_entry_signals"]!="0" or n["biased_exit_signals"]!="0"
          or d["model_file_count_before"]!=25 or d["model_file_count_after"]!=25
          or d["model_hash_differences"] or d["retraining_attempts"]
          or not d["strict_fixed_model_integrity_pass"]
          or not d["all_sampled_trades_identical_through_decision_candle"]
          or not d["all_observed_replay_differences_exclusively_on_post_decision_terminal_row"]):
        raise RuntimeError("LIMITED_FROZEN_MODEL_ASSERTION_FAILED")
    result={
        "scope":"Freqtrade 2026.9 stock lookahead + guarded saved-model deletion, Oct 8-9 2026, original 25-model purged-FreqAI, 3 trades 6 entry/exit shortened comparisons",
        "saved_original_models_preserved":True,
        "identical_model_binaries":25,
        "retraining_attempt_count":0,
        "native_official_has_bias":True,
        "native_official_biased_entry_trade_signals":0,
        "native_official_biased_exit_trade_signals":0,
        "native_full_column_comparisons":len(observations),
        "all_columns_through_actual_trade_decision_equal":True,
        "all_observed_differences_exclusively_one_post_decision_terminal_candle":True,
        "post_decision_terminal_columns":sorted(diff_columns),
        "why_warning_stays":"FreqAI truncated native backtest has one missing prediction at last candle; FreqAI DataKitchen.fill_predictions uses fillna(0) and stock lookahead compares all indicator rows including this one candle after trade decision.",
        "does_not_clear_official_has_bias":True,
        "unsupported_extended_eight_trade_attempt":"A separate expanded diagnostic run failed on a DataFrame schema alignment error in the experimental tracing wrapper, so not counted as successful.",
        "actual_trading_lookahead_completely_certified":False,
        "cost_execution_proved":False,
        "release":"M2 NO-GO"
    }
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print("LIMITED_NATIVE_DECISION_BOUNDARY_PASS",len(observations),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
