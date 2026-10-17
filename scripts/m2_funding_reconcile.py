#!/usr/bin/env python3
"""M2 independent USDT-M Binance funding sanity check against exported trades.

Reads Freqtrade backtest ZIPs and Binance's PUBLIC fundingRate history.
This is a reconciliation TEST, not execution, and requires zero credentials.

Funding estimate: + for short, - for long, multiplied by actual quantity *
Binance settlement mark price * exchange funding rate at settlement timestamps.
Compares to Freqtrade's trade funding_fees field; rounding, direction, precise
event inclusion and exchange-specific trade accounting may differ.

Intentionally refuses non-Binance-USDT perpetual pair names and non-200 APIs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

BINANCE = "https://fapi.binance.com/fapi/v1/fundingRate"


def archive_strategy(path: Path, strategy: str) -> dict:
    with ZipFile(path) as z:
        matches = [m for m in z.namelist()
                   if m.endswith(".json") and not m.endswith("_config.json")
                   and not m.endswith(".meta.json")]
        if len(matches) != 1:
            raise ValueError("Expected one Freqtrade result JSON")
        data = json.loads(z.read(matches[0]))
        if strategy not in data.get("strategy", {}):
            raise ValueError(f"Missing strategy: {strategy}")
        return data["strategy"][strategy]


def symbol_from_pair(pair: str) -> str:
    if not pair.endswith("/USDT:USDT"):
        raise ValueError(f"Unsupported non-USDT future: {pair}")
    base = pair.split("/")[0]
    if not base.isascii() or not base.isalnum() or not base.isupper():
        raise ValueError(f"Invalid pair: {pair}")
    return base + "USDT"


def timestamp_ms(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp must have explicit timezone")
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def public_funding(symbol: str, start_ms: int, end_ms: int) -> list[dict]:
    if not symbol.isascii() or not symbol.endswith("USDT") or not symbol.isalnum():
        raise ValueError("Bad symbol")
    if not 0 < start_ms < end_ms:
        raise ValueError("Bad start/end time")
    url = BINANCE + "?" + urlencode({
        "symbol": symbol, "startTime": start_ms,
        "endTime": end_ms, "limit": 1000,
    })
    with urlopen(Request(url, headers={"User-Agent": "NBOT-V6-M2-funding-audit"}),
                 timeout=30) as result:
        data = json.load(result)
    if not isinstance(data, list):
        raise ValueError(f"Funding API did not return list for {symbol}")
    if len(data) >= 1000:
        raise ValueError("1000-record cap reached: pagination required")
    return data


def expected_funding(trade: dict, records: list[dict]) -> dict:
    opened = timestamp_ms(trade["open_date"])
    closed = timestamp_ms(trade["close_date"])
    amount = float(trade["amount"])
    if amount <= 0 or opened >= closed:
        raise ValueError("Invalid trade size/times")
    direction = 1 if trade.get("is_short") else -1
    valid = [r for r in records if opened < int(r["fundingTime"]) <= closed]
    charge = sum(direction * amount * float(r["markPrice"]) *
                 float(r["fundingRate"]) for r in valid)
    return {"event_count": len(valid), "calculated_usdt": round(charge, 6),
            "engine_usdt": round(float(trade.get("funding_fees") or 0), 6),
            "delta_usdt": round(charge - float(trade.get("funding_fees") or 0), 6)}


def reconcile(archives: dict[str, dict], getter=public_funding) -> dict:
    datasets = {}
    trades_by_source = {}
    earliest, latest = [], []
    for label, stats in archives.items():
        trades = stats["trades"]
        trades_by_source[label] = trades
        for t in trades:
            datasets[t["pair"]] = None
            earliest.append(timestamp_ms(t["open_date"]))
            latest.append(timestamp_ms(t["close_date"]))
    if not earliest:
        raise ValueError("No closed trades")
    start, end = min(earliest) - 86400000, max(latest) + 86400000
    observations = {}
    for pair in sorted(datasets):
        symbol = symbol_from_pair(pair)
        records = getter(symbol, start, end)
        observations[pair] = records
    results = {}
    for label, trades in trades_by_source.items():
        diffs = [expected_funding(t, observations[t["pair"]]) for t in trades]
        abs_diff = sum(abs(x["delta_usdt"]) for x in diffs)
        flagged = sum(abs(x["delta_usdt"]) > 0.05 for x in diffs)
        results[label] = {
            "trades": len(trades),
            "total_external_estimate_usdt": round(sum(x["calculated_usdt"] for x in diffs), 6),
            "total_engine_funding_field_usdt": round(sum(x["engine_usdt"] for x in diffs), 6),
            "absolute_delta_sum_usdt": round(abs_diff, 6),
            "max_trade_abs_delta_usdt": round(max(abs(x["delta_usdt"]) for x in diffs), 6),
            "trades_disagreeing_by_over_0_05_usdt": flagged,
            "settlement_events_in_trade_windows": sum(x["event_count"] for x in diffs),
            "trade_differences": [
                {"pair": t["pair"], "open_date": t["open_date"],
                 "close_date": t["close_date"], **diff}
                for t, diff in zip(trades, diffs)
            ],
        }
    return {
        "status": "diagnostic, not certification",
        "source": "public Binance USD-M /fapi/v1/fundingRate",
        "endpoint_window_utc": [
            datetime.fromtimestamp(start/1000, timezone.utc).isoformat(),
            datetime.fromtimestamp(end/1000, timezone.utc).isoformat(),
        ],
        "symbols_queried": len(observations),
        "method": "Sum signed quantity * settlement mark price * exchange fundingRate"
                  " for settlement open<time<=close. Gross quote estimate;",
        "possible_differences": [
            "Freqtrade may include partial settlement periods, synthetic rate interpolation or inverse funding fee sign.",
            "Trade lifecycle timestamps and Binance event timestamps can have boundary effects.",
            "This only tests reported funding fields; not whether resulting order fills are realistic.",
        ],
        "results": results,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ai", type=Path, required=True)
    p.add_argument("--no-ml", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = reconcile({
        "AI_V6": archive_strategy(args.ai, "NbotV6"),
        "NO_ML": archive_strategy(args.no_ml, "NbotV6NoML"),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for name, result in report["results"].items():
        print(name, "events:", result["settlement_events_in_trade_windows"],
              "estimated USDT:", result["total_external_estimate_usdt"],
              "engine USDT:", result["total_engine_funding_field_usdt"],
              "difference > 0.05 USDT:",
              result["trades_disagreeing_by_over_0_05_usdt"])
    print("Report:", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
