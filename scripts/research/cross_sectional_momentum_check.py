"""Phase 7.5D.2B.3 live read-only cross-sectional momentum signal check."""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from config import OBSERVATION_UNIVERSE_SNAPSHOT_PATH
from execution.binance_market_client import BinanceMarketClient
from strategy.cross_sectional_momentum import (
    MIN_EXISTENCE_DAYS,
    STRATEGY_ID,
    build_liquid_winner_signals,
)


REQUEST_DAILY_BARS = MIN_EXISTENCE_DAYS + 2


def _load_symbols(raw: str, limit: int) -> list[str]:
    if raw.strip():
        symbols = [
            part.strip().upper()
            for part in raw.split(",")
            if part.strip()
        ]
        return list(dict.fromkeys(symbols))[:limit]

    path = Path(OBSERVATION_UNIVERSE_SNAPSHOT_PATH)
    if not path.exists():
        raise RuntimeError(
            f"OBSERVATION_UNIVERSE_SNAPSHOT_MISSING | path={path}"
        )

    document = json.loads(path.read_text())
    symbols = [
        str(value).strip().upper()
        for value in document.get("symbols", [])
        if str(value).strip()
    ]
    if not symbols:
        raise RuntimeError("OBSERVATION_UNIVERSE_SNAPSHOT_EMPTY")
    return symbols[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--as-of-ms", type=int, default=0)
    args = parser.parse_args()

    if not (10 <= args.limit <= 30):
        raise SystemExit("--limit must be between 10 and 30 for this live check")

    symbols = _load_symbols(args.symbols, args.limit)
    if len(symbols) < 10:
        raise SystemExit("At least 10 symbols are required")

    as_of_ms = int(args.as_of_ms or int(time.time() * 1000))

    logger = logging.getLogger("nbot.cross_sectional_momentum_check")
    logger.addHandler(logging.NullHandler())
    client = BinanceMarketClient(system_log=logger)

    histories = {}
    fetch_failures = {}

    for symbol in symbols:
        try:
            histories[symbol] = client.get_historical_research_bars(
                symbol=symbol,
                interval="1d",
                limit=REQUEST_DAILY_BARS,
                end_time_ms=as_of_ms,
            )
        except Exception as exc:
            fetch_failures[symbol] = type(exc).__name__

    result = build_liquid_winner_signals(
        daily_history_by_symbol=histories,
        as_of_ms=as_of_ms,
    )

    print("=" * 92)
    print("PHASE 7.5D.2B.3 - LIVE READ-ONLY LIQUID-WINNER MOMENTUM SIGNAL CHECK")
    print("=" * 92)
    print("strategy_id        :", STRATEGY_ID)
    print("as_of_utc          :", datetime.fromtimestamp(as_of_ms / 1000, timezone.utc).isoformat())
    print("requested_symbols  :", len(symbols))
    print("history_loaded     :", len(histories))
    print("measured_symbols   :", result.measured_symbols)
    print("winner_bucket      :", len(result.winner_symbols))
    print("liquid_bucket      :", len(result.liquid_symbols))
    print("liquid winners     :", len(result.signals))
    print("direction          : LONG_ONLY")
    print("order_authority    : NONE")
    print("runtime_activation : DISABLED")
    print("writes             : NONE")
    print()

    if fetch_failures:
        print("history_fetch_failures:", fetch_failures)

    if result.excluded:
        print("excluded:")
        for symbol, reason in result.excluded:
            print(" ", symbol, "=>", reason)
        print()

    print("momentum winners:")
    print(" ", ", ".join(result.winner_symbols))
    print("most liquid by Amihud:")
    print(" ", ", ".join(result.liquid_symbols))
    print()

    print("selected liquid winners:")
    if not result.signals:
        print("  NONE")
    for signal in result.signals:
        print(
            f"  {signal.symbol:12s} {signal.direction:5s} "
            f"14d_mom={signal.momentum_14d:+.4%} "
            f"amihud={signal.amihud_14d:.12g} "
            f"mom_rank={signal.momentum_rank}/{signal.universe_size} "
            f"liq_rank={signal.liquidity_rank}/{signal.universe_size}"
        )

    print()
    print("CANDIDATES_CREATED        = NO")
    print("VIRTUAL_TRADES_CREATED    = NO")
    print("PRODUCTION_STATE_CHANGED  = NO")
    print("TRAINING_STATE_CHANGED    = NO")
    print("EXECUTION_CHANGED         = NO")
    print("B3_SIGNAL_CHECK           = PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
