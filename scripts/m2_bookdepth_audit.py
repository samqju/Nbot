#!/usr/bin/env python3
"""M2: match actual historical public Binance 30s depth snapshots to trades.

Uses Binance Vision USD-M futures /daily/bookDepth archives, never live quotes.
These are cumulative depth bands, NOT historical best bid/ask or a tick replay.
0.2% bid/ask-band volume is a liquidity screen; no exact fill is inferred.
Logs data quality and blocks false certainty about costs.
Requires no exchange credentials and places no orders.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import csv
import hashlib
import io
import json
from pathlib import Path
import statistics
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from m2_funding_reconcile import archive_strategy, symbol_from_pair, timestamp_ms

BASE = "https://data.binance.vision/data/futures/um/daily/bookDepth"
EXPECTED_BANDS = (-0.2, 0.2)
# 30-second archive intervals; at <=45s old we do not accidentally use future.
MAX_AGE_MS = 45_000
MIN_UNIQUE_FRAC = 0.10  # flag extreme frozen archive; not proof of accuracy


def archive_url(symbol: str, day: str) -> str:
    if len(day) != 10 or date.fromisoformat(day).isoformat() != day:
        raise ValueError("Bad day")
    if not symbol.isascii() or not symbol.isalnum() or not symbol.endswith("USDT"):
        raise ValueError("Bad symbol")
    return f"{BASE}/{symbol}/{symbol}-bookDepth-{day}.zip"


def read_depth(payload: bytes) -> dict:
    series = {band: {} for band in EXPECTED_BANDS}
    with ZipFile(io.BytesIO(payload)) as z:
        paths = [n for n in z.namelist() if n.endswith(".csv") and "/" not in n]
        if len(paths) != 1:
            raise ValueError("Expected one bookDepth CSV")
        with z.open(paths[0]) as f:
            rows = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
            for row in rows:
                pct = float(row["percentage"])
                if pct not in series:
                    continue
                ts = row["timestamp"]
                # Historical archive UTC time has no explicit offset.
                epoch = int(datetime.fromisoformat(ts).replace(
                    tzinfo=timezone.utc).timestamp() * 1000)
                liquidity = float(row["notional"])
                if liquidity < 0:
                    raise ValueError("Negative depth")
                series[pct][epoch] = liquidity
    output = {}
    for pct, pairs in series.items():
        times = sorted(pairs)
        amounts = [pairs[t] for t in times]
        uniq = len(set(round(x, 2) for x in amounts))
        output[pct] = {
            "times": times,
            "amounts": amounts,
            "count": len(times),
            "unique_values_rounded_2dp": uniq,
            "unique_fraction": round(uniq / len(times), 4) if times else 0,
            "looks_frozen": (uniq / len(times) < MIN_UNIQUE_FRAC) if times else True,
        }
    return output


def snapshot_at(series: dict, event_ms: int) -> dict:
    times = series["times"]
    index = bisect_right(times, event_ms) - 1
    if index < 0:
        return {"state": "NO_PRIOR_SNAPSHOT"}
    age = event_ms - times[index]
    if age > MAX_AGE_MS:
        return {"state": "STALE", "age_seconds": round(age / 1000, 3)}
    if series["looks_frozen"]:
        return {"state": "ARCHIVE_SUSPECT_FROZEN",
                "age_seconds": round(age / 1000, 3)}
    return {"state": "MATCH", "age_seconds": round(age / 1000, 3),
            "visible_notional_within_20bps_usdt": round(series["amounts"][index], 3)}


def requests_for_trades(trades: list[dict]) -> set[tuple[str, str]]:
    days = set()
    for t in trades:
        sym = symbol_from_pair(t["pair"])
        for event in ("open_date", "close_date"):
            ms = timestamp_ms(t[event])
            day = datetime.fromtimestamp(ms / 1000, timezone.utc).date().isoformat()
            days.add((sym, day))
            # The nearest prior snapshot could be yesterday near midnight.
            if datetime.fromtimestamp(ms / 1000, timezone.utc).hour == 0:
                days.add((sym, (date.fromisoformat(day) - timedelta(days=1)).isoformat()))
    return days


def evaluate(data: dict, archives: dict[tuple[str, str], dict]) -> dict:
    trades = [dict(t, strategy=label) for label, rows in data.items() for t in rows]
    per_trade = []
    for trade in trades:
        sym = symbol_from_pair(trade["pair"])
        leverage = float(trade.get("leverage", 1))
        notional = float(trade["stake_amount"]) * leverage
        side_buy_on_open = not bool(trade.get("is_short", False))
        fields = [("entry", "open_date", side_buy_on_open),
                  ("exit", "close_date", not side_buy_on_open)]
        sides = []
        for label, field, buying in fields:
            t = timestamp_ms(trade[field])
            day = datetime.fromtimestamp(t / 1000, timezone.utc).date().isoformat()
            band = 0.2 if buying else -0.2
            series = archives.get((sym, day), {}).get(band)
            if series is None or not series["times"] or t < series["times"][0]:
                prev_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
                series = archives.get((sym, prev_day), {}).get(band)
            match = snapshot_at(series, t) if series else {"state": "FILE_MISSING"}
            match["action"] = "BUY" if buying else "SELL"
            match["event"] = label
            match["band_pct"] = band
            if match["state"] == "MATCH":
                match["depth_multiple_of_order"] = round(
                    match["visible_notional_within_20bps_usdt"] / notional, 2
                )
                match["visible_liquidity_ge_order"] = (
                    match["visible_notional_within_20bps_usdt"] >= notional
                )
            sides.append(match)
        per_trade.append({
            "strategy": trade["strategy"], "pair": trade["pair"],
            "open_date": trade["open_date"], "close_date": trade["close_date"],
            "stake_notional_usdt": round(notional, 3), "is_short": trade.get("is_short"),
            "sides": sides,
        })
    events = [x for t in per_trade for x in t["sides"]]
    valid = [x for x in events if x["state"] == "MATCH"]
    status_counts = defaultdict(int)
    for x in events:
        status_counts[x["state"]] += 1
    known = [x["depth_multiple_of_order"] for x in valid]
    archives_report = []
    for (sym, day), bands in sorted(archives.items()):
        archives_report.append({
            "symbol": sym, "day": day,
            "band_0_2": {
                "count": bands.get(0.2, {}).get("count", 0),
                "unique_fraction": bands.get(0.2, {}).get("unique_fraction", 0),
                "looks_frozen": bands.get(0.2, {}).get("looks_frozen", True)
            },
            "band_minus_0_2": {
                "count": bands.get(-0.2, {}).get("count", 0),
                "unique_fraction": bands.get(-0.2, {}).get("unique_fraction", 0),
                "looks_frozen": bands.get(-0.2, {}).get("looks_frozen", True)
            },
        })
    return {
        "title": "M2 Binance Vision 30-second depth-band, historical trade-time match",
        "price_band_pct": 0.2, "snapshot_max_age_seconds": MAX_AGE_MS/1000,
        "note": "Cumulative depth within ±0.2% is NOT spread or a promised fill price.",
        "limits": [
            "No 2026 public historical best bid/ask bookTicker data: exact spread is unavailable.",
            "Depth-band values may be stale/frozen: flagged by per-day uniqueness.",
            "Depth may be canceled before execution and snapshots omit queue priority / latency.",
            "Without tick-level order replay, stop-market gaps and maker fills are NOT reconstructible.",
            "Exposure and market impact risk extend beyond order-notional vs one depth band.",
        ],
        "trades": len(per_trade),
        "entry_exit_events": len(events),
        "status_counts": dict(status_counts),
        "valid_liquidity_ge_order_count": sum(x["visible_liquidity_ge_order"] for x in valid),
        "matched_depth_multiple_of_order_min": round(min(known), 3) if known else None,
        "matched_depth_multiple_of_order_median": round(statistics.median(known), 3) if known else None,
        "archive_files_checked": len(archives),
        "archives": archives_report,
        "trade_events": per_trade
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ai", required=True, type=Path)
    p.add_argument("--baseline", required=True, type=Path)
    p.add_argument("--cache", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--execute", action="store_true", help="Fetch PUBLIC Binance Vision ZIP data")
    args = p.parse_args()
    labels = {
        "AI_V6": archive_strategy(args.ai, "NbotV6")["trades"],
        "NO_ML": archive_strategy(args.baseline, "NbotV6NoML")["trades"]
    }
    unique = sorted(requests_for_trades([t for rows in labels.values() for t in rows]))
    print(f"Dry plan: {len(unique)} public Binance Vision 30s bookDepth archives across {len(labels)} strategies")
    print(f"Cache directory: {args.cache}")
    if not args.execute:
        print("PLAN ONLY. To download public data, add --execute.")
        return 0
    args.cache.mkdir(parents=True, exist_ok=True)
    archives = {}
    missing = []
    for sym, day in unique:
        path = args.cache / (sym + "-" + day + ".zip")
        try:
            if not path.exists():
                url = archive_url(sym, day)
                with urlopen(Request(url, headers={"User-Agent": "NBOT-V6-M2-historical-depth-audit"}),
                             timeout=40) as response:
                    raw = response.read(5_000_001)
                    if len(raw) > 5_000_000:
                        raise ValueError("Oversized depth archive >5MB")
                path.write_bytes(raw)
            raw = path.read_bytes()
            with ZipFile(io.BytesIO(raw)) as z:
                z.testzip()
            archives[(sym, day)] = read_depth(raw)
            print("OK", sym, day, "bytes", len(raw))
        except (OSError, ValueError, KeyError, EOFError, URLError) as exc:
            missing.append({"symbol": sym, "day": day, "error": type(exc).__name__})
            print("MISSING/INVALID", sym, day, type(exc).__name__)
    report = evaluate(labels, archives)
    report["download_missing_files"] = missing
    report["archive_sources"] = [
        {"url": archive_url(sym, day),
         "sha256": hashlib.sha256((args.cache / (sym+"-"+day+".zip")).read_bytes()).hexdigest()}
        for sym, day in sorted(archives)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("SUMMARY:", report["status_counts"])
    print("MATCHED LIQUIDITY GE ORDER:",
          report["valid_liquidity_ge_order_count"], "/",
          report["status_counts"].get("MATCH", 0))
    print("REPORT:", args.output)
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
