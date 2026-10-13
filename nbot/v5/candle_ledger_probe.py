"""Manual real REST 5m -> temporary V5 SQLite -> restart verification.

One-shot only. The temporary DB is removed when the diagnostic exits.
No persistent collector, orders, research labels, execution, credentials.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from typing import Callable, Mapping, Sequence

from nbot.v5.candle_ledger import CandleEvidenceLedger, EvidenceHold
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import (
    HISTORY, PublicMarketDataError, closed_event_from_server_time,
    public_get, select_universe,
)


def smoke_once(*, top: int = 3, getter: Callable = public_get,
               clock_ms: Callable[[], int] | None = None) -> dict:
    """Small, bounded live bootstrap verification; never a ready-to-trade gate."""
    if type(top) is not int or not 1 <= top <= 12:
        raise EvidenceHold("V5_LEDGER_SMOKE_UNIVERSE_BOUNDS")
    clock_ms = clock_ms or (lambda: int(time.time() * 1000))
    event, server = closed_event_from_server_time(getter("/fapi/v1/time"))
    if abs(clock_ms() - server) > 90_000:
        raise EvidenceHold("V5_LEDGER_SMOKE_CLOCK_SKEW")
    exchange = getter("/fapi/v1/exchangeInfo")
    ticker = getter("/fapi/v1/ticker/24hr")
    selected = select_universe(exchange, ticker, limit=top)
    symbols = tuple(sorted(set(selected) | {"BTCUSDT"}))
    report = {}
    with TemporaryDirectory(prefix="nbot_v5_ledger_smoke_") as directory:
        path = Path(directory) / "new_v5_candles.db"
        with CandleEvidenceLedger(path) as ledger:
            for symbol in symbols:
                payload = getter("/fapi/v1/klines", {
                    "symbol": symbol, "interval": "5m",
                    "startTime": str(event - (HISTORY - 1) * INTERVAL_MS),
                    "endTime": str(event + INTERVAL_MS - 1),
                    "limit": str(HISTORY),
                })
                seen = clock_ms()
                if not server <= seen < event + 2 * INTERVAL_MS:
                    raise EvidenceHold("V5_LEDGER_SMOKE_EVENT_EXPIRED")
                written = ledger.bootstrap_rest(
                    symbol, payload, event_open_ms=event, observed_ms=seen,
                )
                if written != HISTORY:
                    raise EvidenceHold("V5_LEDGER_SMOKE_INCOMPLETE_WRITE")
            # SQLite FULL-sync rows must survive a new database connection.
        with CandleEvidenceLedger(path) as reopened:
            for symbol in symbols:
                checked = reopened.inspect(symbol)
                if (checked["closed_bar_count"] != HISTORY
                        or checked["last_event_open_ms"] != event
                        or not checked["candle_contiguous"]
                        or checked["research_ready"]):
                    raise EvidenceHold("V5_LEDGER_SMOKE_RESTART_MISMATCH")
                report[symbol] = {
                    "closed_bars_after_restart": checked["closed_bar_count"],
                    "last_event_open_ms": checked["last_event_open_ms"],
                    "research_ready": checked["research_ready"],
                }
        # TemporaryDirectory removes DB + SQLite WAL/SHM sidecars on exit.
    return {
        "result": "PASS",
        "mode": "TEMPORARY_SQLITE_REST_BOOTSTRAP_NO_ORDERS",
        "eligible_now": selected,
        "btc_context_included": "BTCUSDT" in symbols,
        "validated_symbols": len(symbols),
        "validated_candles": len(symbols) * HISTORY,
        "reopened_check": report,
        "temporary_database_removed": not path.exists(),
        "live_final_wss_candle_confirmed": False,
        "durable_production_ingestion_enabled": False,
        "research_ready": False,
        "training_labels_created": 0,
        "order_authority": "NONE",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V5 temporary REST candle ledger smoke; no trading")
    parser.add_argument("--top", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        report = smoke_once(top=args.top)
    except (EvidenceHold, PublicMarketDataError, OSError, ValueError) as exc:
        print("V5_LEDGER_SMOKE_HOLD:", type(exc).__name__ + ":", str(exc))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
