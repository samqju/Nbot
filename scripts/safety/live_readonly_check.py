"""Controlled read-only Binance Futures mainnet verification.

This runner never starts TradingEngine and never invokes any write operation.
It is intended only to prove authenticated account observation, user-stream
readiness, and read-only reconciliation after Phase 2.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from config import (
    LIVE_ADAPTER_MODE,
    LIVE_ORDER_WRITES_ENABLED,
    LIVE_TRADING_ARM_FILE,
    LIVE_SNAPSHOT_PATH,
    TRADING_ENV,
)
from execution.live_exchange import LiveExchange
from execution.live_snapshot import LiveSnapshotStore
from utils.logger import system_logger


def _validate_runner_safety() -> None:
    if TRADING_ENV != "LIVE":
        raise RuntimeError(
            f"LIVE_READ_ONLY_CHECK_ENVIRONMENT_INVALID | configured={TRADING_ENV}"
        )
    if LIVE_ADAPTER_MODE != "READ_ONLY":
        raise RuntimeError(
            f"LIVE_READ_ONLY_CHECK_ADAPTER_MODE_INVALID | mode={LIVE_ADAPTER_MODE}"
        )
    if LIVE_ORDER_WRITES_ENABLED:
        raise RuntimeError("LIVE_READ_ONLY_CHECK_WRITES_REQUESTED")
    if Path(LIVE_TRADING_ARM_FILE).exists():
        raise RuntimeError("LIVE_READ_ONLY_CHECK_ARM_FILE_PRESENT")


def build_report(exchange: LiveExchange) -> dict:
    reconciliation = exchange.reconcile_read_only(
        local_position=None,
        require_safe=False,
    )
    store = LiveSnapshotStore(LIVE_SNAPSHOT_PATH)
    previous = store.load()
    snapshot = exchange.export_live_snapshot(
        path=LIVE_SNAPSHOT_PATH,
        reconciliation=reconciliation,
        previous_snapshot=previous,
    )
    return {
        "mode": "READ_ONLY",
        "real_orders": "BLOCKED",
        "user_stream_healthy": snapshot["user_stream_healthy"],
        "available_balance_usdt": snapshot["available_balance_usdt"],
        "positions": snapshot["positions"],
        "open_orders": snapshot["open_orders"],
        "protective_stops": snapshot["protective_stops"],
        "reconciliation": snapshot["reconciliation"],
        "drift": snapshot["drift"],
        "snapshot_path": LIVE_SNAPSHOT_PATH,
        "capabilities": snapshot["capabilities"],
    }


def main() -> int:
    log = system_logger()
    exchange = None
    try:
        _validate_runner_safety()
        log.info(
            "LIVE_READ_ONLY_CHECK_START | "
            "engine=NOT_STARTED | real_orders=BLOCKED"
        )
        exchange = LiveExchange(system_log=log)
        exchange.connect()
        report = build_report(exchange)
        print(json.dumps(report, indent=2, sort_keys=True))
        log.info(
            "LIVE_READ_ONLY_CHECK_COMPLETE | "
            f"reconciliation={report['reconciliation']['status']} | "
            f"positions={len(report['positions'])} | "
            f"open_orders={len(report['open_orders'])} | "
            f"protective_stops={len(report['protective_stops'])} | "
            "real_orders=BLOCKED"
        )
        return 0
    except Exception as exc:
        log.error(f"LIVE_READ_ONLY_CHECK_FAILED | error={exc}")
        print(f"LIVE_READ_ONLY_CHECK_FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if exchange is not None:
            try:
                exchange.disconnect()
            except Exception as exc:
                log.error(
                    f"LIVE_READ_ONLY_CHECK_DISCONNECT_FAILED | error={exc}"
                )


if __name__ == "__main__":
    raise SystemExit(main())
