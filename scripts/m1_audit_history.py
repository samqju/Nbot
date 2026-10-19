#!/usr/bin/env python3
"""Audit downloaded Binance futures training/backtest candles WITHOUT fetching data.

Run with the official FreqAI Docker image, which bundles pandas/pyarrow:
  docker run --rm --entrypoint python -v "$PWD:/freqtrade/work" \
    freqtradeorg/freqtrade:stable_freqai \
    /freqtrade/work/scripts/m1_audit_history.py

Does not place orders, download data, train models or alter source.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "user_data" / "data" / "binance" / "futures"
TIMES = {"5m": pd.Timedelta(minutes=5), "1h": pd.Timedelta(hours=1)}


def summarize(path: Path, interval: str | None, requires_ohlcv: bool,
              warmup_start: pd.Timestamp, evaluation_end: pd.Timestamp) -> dict:
    if not path.is_file():
        return {"ok": False, "error": "MISSING_FILE"}
    try:
        data = pd.read_feather(path)
        if "date" not in data:
            return {"ok": False, "error": "NO_DATE_COLUMN"}
        dates = pd.to_datetime(data["date"], utc=True)
        if dates.isna().any() or len(dates) < 2:
            return {"ok": False, "error": "EMPTY_OR_BAD_DATES"}
        delta = dates.diff().dropna()
        duplicates = int(dates.duplicated().sum())
        backward = int((delta < pd.Timedelta(0)).sum())
        gaps = int((delta > TIMES[interval]).sum()) if interval else None
        irregular = int((delta != TIMES[interval]).sum()) if interval else None
        ok = duplicates == 0 and backward == 0
        if interval:
            ok = ok and irregular == 0
        if requires_ohlcv:
            cols = {"open", "high", "low", "close", "volume"}
            if not cols.issubset(data.columns):
                return {"ok": False, "error": "MISSING_OHLCV_FIELDS"}
            numbers = data[list(cols)].apply(pd.to_numeric, errors="coerce")
            if numbers.isna().any().any():
                return {"ok": False, "error": "NAN_OHLCV"}
            invalid = (
                (numbers["open"] <= 0) | (numbers["close"] <= 0)
                | (numbers["low"] <= 0) | (numbers["high"] < numbers[["open", "close"]].max(axis=1))
                | (numbers["low"] > numbers[["open", "close"]].min(axis=1))
                | (numbers["volume"] < 0)
            )
            ok = ok and not bool(invalid.any())
        ok = ok and dates.iloc[0] <= warmup_start and dates.iloc[-1] >= evaluation_end
        return {
            "ok": bool(ok),
            "records": int(len(data)),
            "first_utc": dates.iloc[0].isoformat(),
            "last_utc": dates.iloc[-1].isoformat(),
            "duplicate_timestamps": duplicates,
            "out_of_order": backward,
            "missing_intervals": irregular,
            "gap_intervals": gaps,
        }
    except (OSError, ValueError, TypeError, KeyError) as e:
        return {"ok": False, "error": type(e).__name__}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtest-start", default="20261001", help="UTC YYYYMMDD")
    parser.add_argument("--backtest-end", default="20261008", help="UTC YYYYMMDD")
    args = parser.parse_args()
    try:
        start = pd.Timestamp(datetime.strptime(args.backtest_start, "%Y%m%d"), tz="UTC")
        end = pd.Timestamp(datetime.strptime(args.backtest_end, "%Y%m%d"), tz="UTC")
    except ValueError as exc:
        parser.error(f"Dates must be YYYYMMDD: {exc}")
    if not start < end:
        parser.error("Backtest end must be later than start")
    config = json.loads((REPO / "user_data" / "config.json").read_text())
    train_days = int(config["freqai"]["train_period_days"])
    # 200 1h startup candles need 8.34 days before the rolling training window.
    warmup = start - pd.Timedelta(days=train_days + 9)
    pairs = config["exchange"]["pair_whitelist"]
    result = {"test_window_utc": [start.isoformat(), end.isoformat()],
              "required_warmup_start_utc": warmup.isoformat(),
              "data_directory": str(DATA), "pair_count": len(pairs), "pairs": {}}
    pass_pairs = 0
    for pair in pairs:
        stem = pair.replace("/", "_").replace(":", "_")
        reports = {
            "5m_futures": summarize(DATA / f"{stem}-5m-futures.feather", "5m", True, warmup, end),
            "1h_futures": summarize(DATA / f"{stem}-1h-futures.feather", "1h", True, warmup, end),
            "1h_mark": summarize(DATA / f"{stem}-1h-mark.feather", "1h", True, warmup, end),
            # Binance funding events are sparse, generally ~8h, not hourly.
            "funding": summarize(DATA / f"{stem}-1h-funding_rate.feather", None, False, warmup, end),
        }
        result["pairs"][pair] = reports
        passed = all(v["ok"] for v in reports.values())
        pass_pairs += int(passed)
        print(f"{'PASS' if passed else 'FAIL'} {pair}")
        if not passed:
            print(json.dumps({k: v for k, v in reports.items() if not v["ok"]}))
    result["passed_pairs"] = pass_pairs
    result["failed_pairs"] = len(pairs) - pass_pairs
    output = REPO / "user_data" / "backtest_results" / "m1-candle-audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Verified {pass_pairs}/{len(pairs)} pairs. Details: {output}")
    return 0 if pass_pairs == len(pairs) else 2


if __name__ == "__main__":
    sys.exit(main())
