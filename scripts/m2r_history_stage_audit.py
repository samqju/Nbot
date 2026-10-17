"""Read-only quality and overlap audit of staged public Binance V6 research history.

Runs in the official Freqtrade/FreqAI Docker image (pandas + pyarrow).
No exchange access, no model fitting, no paper/live trades. JSON to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


CANDLE_FILES = (
    ("5m", "futures", 5),
    ("1h", "futures", 60),
    ("1h", "mark", 60),
    ("1h", "funding_rate", None),
)


def audit_file(path: Path, original: Path | None, minute_step: int | None,
               start: pd.Timestamp, end: pd.Timestamp) -> dict:
    frame = pd.read_feather(path)
    dates = pd.to_datetime(frame["date"], utc=True)
    window = (dates >= start) & (dates < end)
    times = dates.loc[window]
    diffs = times.diff().dropna()
    row = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows_all": len(frame),
        "rows_in_requested_utc_range": int(window.sum()),
        "first_utc": str(dates.min()),
        "last_utc": str(dates.max()),
        "first_in_range_utc": str(times.min()),
        "last_in_range_utc": str(times.max()),
        "duplicate_timestamps_in_range": int(times.duplicated().sum()),
        "nonmonotonic_timestamp_steps_in_range": int((diffs <= pd.Timedelta(0)).sum()),
        "outside_requested_range": int((~window).sum()),
        "start_covered": bool(len(times) and times.iloc[0] == start),
        "last_day_covered": bool(len(times) and times.iloc[-1] >= end - pd.Timedelta(days=1)),
    }
    row["unexpected_time_step_count"] = (
        int((diffs != pd.Timedelta(minutes=minute_step)).sum())
        if minute_step is not None else None
    )
    if {"open", "high", "low", "close", "volume"}.issubset(frame):
        ohlcv = frame.loc[window, ["open", "high", "low", "close", "volume"]].to_numpy(dtype="float64")
        bad = (
            (~np.isfinite(ohlcv).all(axis=1))
            | (ohlcv[:, :4] <= 0).any(axis=1)
            | (ohlcv[:, 4] < 0)
            | (ohlcv[:, 1] < ohlcv[:, [0, 2, 3]].max(axis=1))
            | (ohlcv[:, 2] > ohlcv[:, [0, 1, 3]].min(axis=1))
        )
        row["bad_ohlcv_rows_in_range"] = int(bad.sum())
    else:
        row["bad_ohlcv_rows_in_range"] = None

    if original and original.exists():
        old = pd.read_feather(original)
        matching = frame.merge(old, how="inner", on="date", suffixes=("_new", "_old"))
        comparable = [key for key in ["open", "high", "low", "close", "volume"]
                      if key + "_new" in matching and key + "_old" in matching]
        differing = np.zeros(len(matching), dtype=bool)
        for key in comparable:
            new = matching[key + "_new"].to_numpy(dtype="float64")
            prior = matching[key + "_old"].to_numpy(dtype="float64")
            differing |= ~np.isclose(new, prior, rtol=1e-10, atol=1e-10, equal_nan=True)
        row["original_rows"] = len(old)
        row["original_matched_timestamps"] = len(matching)
        row["original_missing_timestamps"] = len(old) - len(matching)
        row["original_changed_ohlcv_rows"] = int(differing.sum())
    else:
        row["original_rows"] = None
        row["original_matched_timestamps"] = None
        row["original_missing_timestamps"] = None
        row["original_changed_ohlcv_rows"] = None
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--from-date", default="2026-01-01")
    parser.add_argument("--until-date", default="2026-10-17")
    args = parser.parse_args()

    pairs = json.loads(args.config.read_text())["exchange"]["pair_whitelist"]
    start, end = pd.Timestamp(args.from_date, tz="UTC"), pd.Timestamp(args.until_date, tz="UTC")
    result = {
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "V6 public Binance USDT-M history only, staged outside original dataset",
        "requested_from_inclusive_utc": str(start),
        "requested_until_exclusive_utc": str(end),
        "configured_pair_count": len(pairs),
        "expected_file_count": len(pairs) * len(CANDLE_FILES),
        "files": [],
        "missing_files": [],
    }
    for pair in pairs:
        token = pair.replace("/", "_").replace(":", "_")
        for timeframe, kind, minutes in CANDLE_FILES:
            name = f"{token}-{timeframe}-{kind}.feather"
            stage_file = args.stage / name
            if not stage_file.exists():
                result["missing_files"].append(name)
                continue
            result["files"].append(
                audit_file(stage_file, args.original / name, minutes, start, end)
            )
    result["existing_file_count"] = len(result["files"])
    result["total_files_missing"] = len(result["missing_files"])
    result["total_unexpected_interval_steps"] = sum(
        r["unexpected_time_step_count"] or 0 for r in result["files"]
    )
    result["total_duplicate_timestamps"] = sum(
        r["duplicate_timestamps_in_range"] for r in result["files"]
    )
    result["total_invalid_ohlcv"] = sum(
        r["bad_ohlcv_rows_in_range"] or 0 for r in result["files"]
    )
    result["original_mismatched_rows"] = sum(
        r["original_changed_ohlcv_rows"] or 0 for r in result["files"]
    )
    result["original_missing_timestamps"] = sum(
        r["original_missing_timestamps"] or 0 for r in result["files"]
    )
    result["all_covered_at_start"] = all(
        r["start_covered"] for r in result["files"]
    ) if result["files"] else False
    result["all_covered_near_end"] = all(
        r["last_day_covered"] for r in result["files"]
    ) if result["files"] else False
    result["integrity_pass"] = bool(
        not result["missing_files"]
        and not result["total_duplicate_timestamps"]
        and not result["total_unexpected_interval_steps"]
        and not result["total_invalid_ohlcv"]
        and not result["original_missing_timestamps"]
        and not result["original_mismatched_rows"]
        and result["all_covered_at_start"]
        and result["all_covered_near_end"]
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["integrity_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
