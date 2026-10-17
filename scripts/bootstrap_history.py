#!/usr/bin/env python3
"""NBOT V6 candidate history bootstrap. Never edits the active watchlist.

This is a small wrapper around the official Freqtrade download-data/list-data
commands. By default it PRINTS the command plan without downloading anything.
Running a download does NOT train a model or make a candidate trade-eligible.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "user_data" / "config.json"
BTC = "BTC/USDT:USDT"
PAIR_PATTERN = re.compile(r"^[A-Z0-9]{2,20}/USDT:USDT$")
MAX_CANDIDATES = 10
DEFAULT_HISTORY_DAYS = 60


def normalize_pair(raw: str) -> str:
    """Accept e.g. SOL or SOL/USDT:USDT; reject unsafe/other-market forms."""
    token = raw.strip()
    if re.fullmatch(r"[A-Z0-9]{2,20}", token):
        token += "/USDT:USDT"
    if not PAIR_PATTERN.fullmatch(token):
        raise ValueError("Use an uppercase Binance USDT-M pair, e.g. SOL or SOL/USDT:USDT")
    return token


def candidate_pairs(raw_pairs: list[str]) -> list[str]:
    """Bound requests to 10 unique candidate symbols; always include BTC data."""
    if not raw_pairs:
        raise ValueError("At least one candidate pair must be specified")
    result: list[str] = []
    for raw in raw_pairs:
        pair = normalize_pair(raw)
        if pair not in result:
            result.append(pair)
    if len([p for p in result if p != BTC]) > MAX_CANDIDATES:
        raise ValueError("At most 10 non-BTC candidates may be prepared per review")
    if BTC not in result:
        result.append(BTC)
    return result


def minimum_history_days(config: dict) -> int:
    """Conservative training+1h startup+validation margin for current V6."""
    from math import ceil

    train = int(config["freqai"]["train_period_days"])
    # A 200-candle startup on 1h requires ~8.3 days before the 30d window.
    startup = 200
    if set(config["freqai"]["feature_parameters"]["include_timeframes"]) != {"5m", "1h"}:
        raise ValueError("Bootstrap supports only the V6 configured 5m+1h timeframes")
    return ceil(train + startup / 24 + 6)


def make_commands(pairs: list[str], days: int, config: dict) -> tuple[list[str], list[str]]:
    """Build safe argv, never shell=True or arbitrary command-line interpolation."""
    if days < minimum_history_days(config) or days > 180:
        raise ValueError(
            f"Requested history must be {minimum_history_days(config)} to 180 days "
            "for current training and startup settings"
        )
    prefix = ["docker", "compose", "--profile", "research", "run", "--rm", "paper-research"]
    common = ["--config", "/freqtrade/user_data/config.json", "--trading-mode", "futures"]
    download = prefix + [
        "download-data", *common, "--pairs", *pairs,
        "--timeframes", "5m", "1h", "--days", str(days),
    ]
    inspect = prefix + [
        "list-data", *common, "--pairs", *pairs, "--show-timerange",
    ]
    return download, inspect


def build_plan(raw_pairs: list[str], days: int, config: dict) -> dict:
    pairs = candidate_pairs(raw_pairs)
    if config.get("dry_run") is not True:
        raise ValueError("Base V6 configuration must remain dry_run=true")
    if config.get("exchange", {}).get("name") != "binance":
        raise ValueError("Bootstrap expects the configured Binance exchange")
    if config.get("trading_mode") != "futures":
        raise ValueError("Bootstrap expects USDT-M futures mode")
    if BTC not in config["freqai"]["feature_parameters"]["include_corr_pairlist"]:
        raise ValueError("FreqAI BTC correlation context is required")
    download, inspect = make_commands(pairs, days, config)
    return {
        "requested_pairs": pairs,
        "requested_history_days": days,
        "rolling_training_days": int(config["freqai"]["train_period_days"]),
        "commands": {"download": download, "inspect_local_ranges": inspect},
        "state": "PLAN_ONLY",
        "disclaimer": (
            "Download/inspection alone does NOT verify continuity, liquidity, "
            "model training or FreqAI prediction readiness. Do not modify the "
            "running 25-pair watchlist or enable live trading."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", action="append", required=True,
                        help="Repeat for 1-10 new candidates, e.g. --pair SOL")
    parser.add_argument("--days", type=int, default=DEFAULT_HISTORY_DAYS,
                        help="History request; default 60 days, 30-day model window unchanged")
    parser.add_argument("--execute", action="store_true",
                        help="Actually download using Freqtrade Docker; default is print-only")
    args = parser.parse_args(argv)
    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        plan = build_plan(args.pair, args.days, config)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    print("NBOT V6 candidate history preparation (no active watchlist changes)")
    print("Download:", shlex.join(plan["commands"]["download"]))
    print("Inspect: ", shlex.join(plan["commands"]["inspect_local_ranges"]))
    print("Model training remains 30 rolling days; extra data covers warmup/validation.")
    if not args.execute:
        print("PLAN ONLY. Pass --execute to run official Freqtrade commands.")
        return 0

    # Download request is explicitly opt-in. The only commands allowed are the
    # fixed download-data/list-data invocations constructed above.
    try:
        subprocess.run(plan["commands"]["download"], cwd=ROOT, check=True)
        subprocess.run(plan["commands"]["inspect_local_ranges"], cwd=ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"PREPARATION FAILED with process exit status {exc.returncode}.")
        return 1
    except OSError as exc:
        print(f"PREPARATION FAILED: {exc}")
        return 1

    plan["state"] = "DOWNLOADED_UNVERIFIED"
    plan["finished_utc"] = datetime.now(timezone.utc).isoformat()
    records = ROOT / "user_data" / "bootstrap_records"
    records.mkdir(parents=True, exist_ok=True)
    # Timestamp plus limited symbol count: audit-only local record, not a gate.
    filename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-history.json"
    out = records / filename
    out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(f"History command completed; record saved at {out}.")
    print("STATE: DOWNLOADED_UNVERIFIED (NOT HISTORY_READY or MODEL_READY).")
    print("Verify actual candle coverage, missing rows, BTC context, futures funding,")
    print("minimum market age and successful FreqAI training before any activation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
