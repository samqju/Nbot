#!/usr/bin/env python3
"""M2: independent 25-pair decision-gate counts from actual FreqAI forecasts.

This reads the immutable historical Binance OHLCV and original FreqAI
backtesting_prediction feather files. No trading, downloads or ML fitting.
Matches actual predicted values/date to original EMA/breakout/pullback rules.
Counts every 5m-pair opportunity, do_predict rejection and score abstention.
Actual filled/rejected order counts still come from Freqtrade's original
exported signals and should NOT be equated with these eligible candidates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import math

import numpy as np
import pandas as pd

def model_decisions(candles: pd.DataFrame, pred: pd.DataFrame, limit: float=0.006) -> dict:
    if not 0 < limit < 1:
        raise ValueError("Expected a sensible normalized predicted return threshold")
    candles = candles.sort_values("date")
    pred = pred.sort_values("date")
    if candles["date"].duplicated().any() or pred["date"].duplicated().any():
        raise ValueError("Duplicate timestamp")
    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(candles.columns):
        raise ValueError("Incomplete candle data")
    required = {"date", "&-forward_return", "do_predict"}
    if not required.issubset(pred.columns):
        raise ValueError("Incomplete FreqAI predictions")
    close = candles["close"]
    ema_fast = close.ewm(span=20, adjust=False, min_periods=20).mean()
    ema_slow = close.ewm(span=50, adjust=False, min_periods=50).mean()
    hi = candles["high"].shift(1).rolling(20, min_periods=20).max()
    lo = candles["low"].shift(1).rolling(20, min_periods=20).min()
    pclose = close.shift(1)
    pfast = ema_fast.shift(1)
    uptrend = ema_fast > ema_slow
    downtrend = ema_fast < ema_slow
    long_setup = uptrend & ((close > hi) | ((pclose <= pfast) & (close > ema_fast)))
    short_setup = downtrend & ((close < lo) | ((pclose >= pfast) & (close < ema_fast)))
    df = candles[["date", "close", "volume"]].copy()
    df["technical_long"] = long_setup.to_numpy()
    df["technical_short"] = short_setup.to_numpy()
    df = df.merge(pred[["date", "&-forward_return", "do_predict"]], on="date",
                  validate="one_to_one", how="right", indicator=True)
    if (df["_merge"] != "both").any():
        raise ValueError("FreqAI prediction timestamps not matched to original candles")
    p = pd.to_numeric(df["&-forward_return"], errors="coerce")
    ok = (df["volume"] > 0) & (df["close"] > 0)
    tp = df["technical_long"] | df["technical_short"]
    model_ready = (df["do_predict"] == 1) & np.isfinite(p)
    aligned = ((df["technical_long"] & (p > limit)) |
               (df["technical_short"] & (p < -limit)))
    final = ok & model_ready & aligned
    totals = {
        "five_minute_decisions": int(len(df)),
        "valid_price_volume": int(ok.sum()),
        "technical_setups": int((tp & ok).sum()),
        "technical_long": int((df["technical_long"] & ok).sum()),
        "technical_short": int((df["technical_short"] & ok).sum()),
        "do_predict_values": {str(k): int(v) for k, v in
                              df["do_predict"].value_counts(dropna=False).to_dict().items()},
        "model_ready": int((model_ready & ok).sum()),
        "technical_setup_but_model_not_ready": int((tp & ok & ~model_ready).sum()),
        "technical_setup_model_ready": int((tp & ok & model_ready).sum()),
        "technical_setup_model_ready_but_prediction_wrong_size": int(
            (tp & ok & model_ready & ~aligned).sum()),
        "eligible_AI_candidate_signal_rows": int(final.sum()),
        "eligible_long": int((final & df["technical_long"]).sum()),
        "eligible_short": int((final & df["technical_short"]).sum()),
        "eligible_baseline_candidate_signal_rows": int((tp & ok).sum()),
    }
    assert (
        totals["technical_setup_but_model_not_ready"]
        + totals["technical_setup_model_ready_but_prediction_wrong_size"]
        + totals["eligible_AI_candidate_signal_rows"]
        == totals["technical_setups"]
    )
    return totals


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    config = json.loads(args.config.read_text())
    pairs = config["exchange"]["pair_whitelist"]
    results = {}
    for pair in pairs:
        stem = pair.replace("/", "_").replace(":", "_")
        # Match model naming from per-pair native training artifact.
        symbol = pair.split("/")[0].lower()
        predictions = sorted((args.models / "backtesting_predictions").glob(
            f"cb_{symbol}_*_prediction.feather"))
        if len(predictions) != 1:
            raise ValueError(f"Expected exactly one prediction archive for {pair}")
        candles = args.data / "binance" / "futures" / f"{stem}-5m-futures.feather"
        if not candles.is_file():
            raise ValueError(f"Missing 5m candle archive for {pair}: {candles}")
        result = model_decisions(pd.read_feather(candles),
                                 pd.read_feather(predictions[0]))
        results[pair] = result
        print(pair, "technical", result["technical_setups"],
              "model blocked", result["technical_setup_but_model_not_ready"],
              "score blocked", result["technical_setup_model_ready_but_prediction_wrong_size"],
              "AI eligible", result["eligible_AI_candidate_signal_rows"])
    summary = {}
    for item in next(iter(results.values())).keys():
        if item == "do_predict_values":
            counts = Counter()
            for row in results.values():
                counts.update(row[item])
            summary[item] = dict(sorted(counts.items()))
        else:
            summary[item] = sum(row[item] for row in results.values())
    report = {
        "source": "Original frozen FreqAI 25-pair backtesting_predictions/*.feather + Binance 5m futures candles",
        "window": "2026-10-01 00:00 UTC to 2026-10-08 00:00 UTC",
        "prediction_threshold_abs_fraction": 0.006,
        "pair_count": len(pairs),
        "method": "Rebuild original EMA20/50, previous-20-high/low and pullback on causal 5m candles; join original predictions by exact UTC date",
        "limitations": [
            "Eligible candidate signals are per-symbol per-candle possibilities, NOT fills or independent orders.",
            "Only one actual global position may be held, so many valid signals cannot be executed.",
            "Freqtrade native export confirms actual AI 34/68/34 and non-ML 31/6531/31 entry/rejection/exit rows.",
            "This does not independently establish out-of-sample model validity or eliminate lookahead diagnostic anomalies."
        ],
        "summary": summary,
        "pairs": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print("SUMMARY",json.dumps(summary))
    print("REPORT",args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
