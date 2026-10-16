#!/usr/bin/env python3
"""M1 public Binance USDT-M candidate/data preflight (no trading, no secrets).

Default prints a PLAN. --execute reads Binance's PUBLIC futures endpoints,
checks all 25 configured candidates, and writes a JSON report. This is NOT
a substitute for downloading all history or training a real FreqAI model.
No external packages required; never touches orders, wallets or V5 state.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "user_data" / "config.json"
FAPI = "https://fapi.binance.com"
HOUR_MS = 60 * 60 * 1000
INTERVAL_MS = {"5m": 5 * 60 * 1000, "1h": HOUR_MS}


def public_json(path: str, query: dict | None = None):
    if not path.startswith("/fapi/v1/") or "://" in path:
        raise ValueError("Only explicitly approved Binance public futures URLs are permitted")
    url = FAPI + path + ("?" + urlencode(query) if query else "")
    request = Request(url, headers={"User-Agent": "NBOT-V6-M1-public-preflight"})
    with urlopen(request, timeout=18) as response:
        return json.load(response)


def pair_symbol(pair: str) -> str:
    if not pair.endswith("/USDT:USDT"):
        raise ValueError("Only USDT-settled perpetual candidates are allowed")
    symbol = pair.split("/")[0]
    if not (2 <= len(symbol) <= 20 and symbol.isalnum() and symbol.isupper()):
        raise ValueError("Invalid Binance base asset")
    return symbol + "USDT"


def candle_check(rows: list, interval: str, now_ms: int) -> dict:
    delta = INTERVAL_MS[interval]
    closed = [r for r in rows if int(r[6]) < now_ms]
    invalid = 0
    for r in closed:
        try:
            o, hi, low, cl, vol = map(float, (r[1], r[2], r[3], r[4], r[5]))
            if o <= 0 or cl <= 0 or low <= 0 or hi < max(o, cl) or low > min(o, cl) or vol < 0:
                invalid += 1
        except (ValueError, IndexError, TypeError):
            invalid += 1
    opens = [int(r[0]) for r in closed]
    gaps = sum(b - a != delta for a, b in zip(opens, opens[1:]))
    fresh = bool(closed) and now_ms - int(closed[-1][6]) < delta * 4
    return {
        "recent_closed_candles": len(closed),
        "recent_gaps": gaps,
        "invalid_ohlcv": invalid,
        "fresh": fresh,
        "last_close_utc": (
            datetime.fromtimestamp(int(closed[-1][6]) / 1000, tz=timezone.utc).isoformat()
            if closed else None
        ),
    }


def review(config: dict, metadata: dict, fetch, now_ms: int) -> dict:
    assert config["dry_run"] is True and config["trading_mode"] == "futures"
    pairs = config["exchange"]["pair_whitelist"]
    details = {s["symbol"]: s for s in metadata["symbols"]}
    output = []
    cutoff_60 = now_ms - 60 * 24 * HOUR_MS
    for index, pair in enumerate(pairs):
        symbol = pair_symbol(pair)
        contract = details.get(symbol)
        errors = []
        if not contract:
            errors.append("NOT_LISTED")
        else:
            if contract.get("contractType") != "PERPETUAL":
                errors.append("NOT_PERPETUAL")
            if contract.get("status") != "TRADING":
                errors.append("NOT_TRADING")
            if contract.get("quoteAsset") != "USDT" or contract.get("marginAsset") != "USDT":
                errors.append("NOT_USDT_MARGINED")
            if int(contract.get("onboardDate", now_ms)) > cutoff_60:
                errors.append("LESS_THAN_60D_LISTED")

        entry = {"pair": pair, "symbol": symbol, "contract_checks": errors, "candles": {}}
        if not errors:
            for tf, delta in INTERVAL_MS.items():
                recent = fetch("/fapi/v1/klines",
                               {"symbol": symbol, "interval": tf, "limit": 500})
                # This confirms *some* 60-day-old candles, not full 60-day continuity.
                first = fetch("/fapi/v1/klines", {
                    "symbol": symbol, "interval": tf, "startTime": cutoff_60,
                    "limit": 1,
                })
                status = candle_check(recent, tf, now_ms)
                status["history_60d_probe"] = bool(
                    first and cutoff_60 <= int(first[0][0]) <= cutoff_60 + delta * 2
                )
                entry["candles"][tf] = status
                if not status["history_60d_probe"]:
                    errors.append(tf + "_OLDER_HISTORY_NOT_SEEN")
                if status["recent_gaps"] or status["invalid_ohlcv"] or not status["fresh"]:
                    errors.append(tf + "_RECENT_DATA_QUALITY")
        entry["eligible_for_history_download_preflight"] = not errors
        output.append(entry)
        if index % 5 == 4:
            time.sleep(0.25)

    return {
        "source": "Public Binance USD-M futures REST metadata and 5m/1h sample candles",
        "asof_utc": datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).isoformat(),
        "note": "This is a bounded data PRECHECK, not full 60-day candle continuity,"
                " data download, successful model fit or a FreqAI backtest.",
        "pairs_count": len(output),
        "preflight_pass": sum(x["eligible_for_history_download_preflight"] for x in output),
        "preflight_fail": sum(not x["eligible_for_history_download_preflight"] for x in output),
        "results": output,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Fetch public historical-market samples")
    parser.add_argument("--output", type=Path, default=ROOT / "user_data" / "m1-preflight.json")
    args = parser.parse_args(argv)
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert cfg["dry_run"] is True and cfg["exchange"]["name"] == "binance"
    print(f"NBOT V6 M1 preflight: {len(cfg['exchange']['pair_whitelist'])} public futures pairs.")
    if not args.execute:
        print("PLAN ONLY. --execute fetches PUBLIC Binance market and sample candle data.")
        return 0
    now = int(time.time() * 1000)
    meta = public_json("/fapi/v1/exchangeInfo")
    report = review(cfg, meta, public_json, now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"25-pair data preflight: {report['preflight_pass']} passed; "
          f"{report['preflight_fail']} failed; detailed report: {args.output}")
    for row in report["results"]:
        if row["contract_checks"]:
            print(row["pair"], ": ", ",".join(row["contract_checks"]))
    # Fail when any pair is not even suitable for full-history preparation.
    return 0 if report["preflight_fail"] == 0 else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"M1_PREFLIGHT_FAILED: {error}", file=sys.stderr)
        sys.exit(1)
