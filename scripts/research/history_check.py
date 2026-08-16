"""Phase 7.5D.2B.2 live read-only multi-horizon history check."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from config import OBSERVATION_UNIVERSE_SNAPSHOT_PATH
from execution.binance_market_client import BinanceMarketClient
from observation.research_history import MultiHorizonResearchHistoryProvider


def _load_symbols(raw: str, limit: int) -> list[str]:
    if raw.strip():
        values = [part.strip().upper() for part in raw.split(",") if part.strip()]
        return list(dict.fromkeys(values))[:limit]

    path = Path(OBSERVATION_UNIVERSE_SNAPSHOT_PATH)
    if not path.exists():
        raise RuntimeError(f"OBSERVATION_UNIVERSE_SNAPSHOT_MISSING | path={path}")

    document = json.loads(path.read_text())
    symbols = [str(value).strip().upper() for value in document.get("symbols", [])]
    symbols = [value for value in symbols if value]
    if not symbols:
        raise RuntimeError("OBSERVATION_UNIVERSE_SNAPSHOT_EMPTY")
    return symbols[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--as-of-ms", type=int, default=0)
    args = parser.parse_args()

    if not (1 <= args.limit <= 20):
        raise SystemExit("--limit must be between 1 and 20 for the live check")

    symbols = _load_symbols(args.symbols, args.limit)
    as_of_ms = int(args.as_of_ms or int(time.time() * 1000))

    logger = logging.getLogger("nbot.research_history_check")
    logger.addHandler(logging.NullHandler())

    client = BinanceMarketClient(system_log=logger)
    provider = MultiHorizonResearchHistoryProvider(market_client=client)

    print("=" * 88)
    print("PHASE 7.5D.2B.2 - LIVE READ-ONLY MULTI-HORIZON HISTORY CHECK")
    print("=" * 88)
    print("as_of_utc       :", datetime.fromtimestamp(as_of_ms / 1000, timezone.utc).isoformat())
    print("symbols         :", ", ".join(symbols))
    print("order_authority : NONE")
    print("writes          : NONE")
    print()

    complete = 0
    for symbol in symbols:
        snapshot = provider.snapshot(symbol=symbol, as_of_ms=as_of_ms)
        summary = snapshot.to_summary()
        if snapshot.completeness == "COMPLETE_PHASE7_5D2B2":
            complete += 1

        daily = snapshot.daily_bars
        recent_quote_volumes = [float(row["quote_volume"]) for row in daily[-14:]]

        print(symbol)
        print("  completeness            :", snapshot.completeness)
        print("  hourly bars              :", len(snapshot.hourly_bars))
        print("  daily bars               :", len(snapshot.daily_bars))
        print("  cross-sectional ready    :", snapshot.cross_sectional_ready)
        print("  time-series mom ready    :", snapshot.time_series_momentum_ready)
        print("  intraday research ready  :", snapshot.intraday_ready)
        print("  latest hourly close UTC  :", datetime.fromtimestamp(summary["hourly_latest_close_ms"] / 1000, timezone.utc).isoformat())
        print("  latest daily close UTC   :", datetime.fromtimestamp(summary["daily_latest_close_ms"] / 1000, timezone.utc).isoformat())
        print("  14d quote-volume positive:", all(value > 0 for value in recent_quote_volumes))
        print()

    print("COMPLETE_SYMBOLS           =", f"{complete}/{len(symbols)}")
    print("PRODUCTION_STATE_CHANGED   = NO")
    print("TRAINING_STATE_CHANGED     = NO")
    print("EXECUTION_CHANGED          = NO")
    print("B2_MULTI_HORIZON_CHECK     =", "PASS" if complete == len(symbols) else "FAIL")
    return 0 if complete == len(symbols) else 2


if __name__ == "__main__":
    raise SystemExit(main())
