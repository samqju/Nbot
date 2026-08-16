#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from nbot.binance import BinancePublicClient, latest_closed_open_time_ms
from nbot.config import CONFIG
from nbot.db import EvidenceDB
from nbot.observer import MarketEvidenceObserver


def iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def cmd_init() -> int:
    db = EvidenceDB(CONFIG)
    db.initialize()
    print(f"INITIALIZED={db.path}")
    return 0


def cmd_status() -> int:
    status = EvidenceDB(CONFIG).status()
    print(f"role            : {CONFIG.role}")
    print(f"market          : {CONFIG.market_environment}")
    print(f"database        : {status['database_path']}")
    print(f"events          : {status['events']}")
    print(f"complete_events : {status['complete_events']}")
    print(f"partial_events  : {status['partial_events']}")
    print(f"candles         : {status['candles']}")
    print(f"snapshots       : {status['snapshots']}")
    latest = status["latest_event"]
    if latest:
        print(
            "latest_event    : "
            f"{iso_ms(latest[0])} stored={latest[1]}/{latest[2]} "
            f"status={latest[3]} duration_ms={latest[4]}"
        )
    else:
        print("latest_event    : NONE")
    return 0


def cmd_check_live() -> int:
    client = BinancePublicClient(CONFIG)
    server_ms = client.server_time_ms()
    open_ms = latest_closed_open_time_ms(server_ms, CONFIG.candle_interval_ms)
    universe = client.eligible_universe()
    btc = client.closed_candle("BTCUSDT", open_ms)
    print("NBOT_V2_LIVE_CHECK=PASS")
    print("credentials=NONE")
    print("execution=DISABLED")
    print(f"server_time_utc={iso_ms(server_ms)}")
    print(f"latest_closed_5m_open_utc={iso_ms(open_ms)}")
    print(f"eligible_universe_count={len(universe)}")
    print(f"btc_close={btc.close_price}")
    print("top_symbols=" + ",".join(row.symbol for row in universe[:5]))
    return 0


def cmd_collect_once() -> int:
    db = EvidenceDB(CONFIG)
    db.initialize()
    result = MarketEvidenceObserver(CONFIG, BinancePublicClient(CONFIG), db).collect_once()
    print(json.dumps(result.__dict__, sort_keys=True))
    return 0 if result.status == "COMPLETE" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="NBOT V2 administration")
    parser.add_argument("command", choices=("init", "status", "check-live", "collect-once"))
    args = parser.parse_args()
    return {
        "init": cmd_init,
        "status": cmd_status,
        "check-live": cmd_check_live,
        "collect-once": cmd_collect_once,
    }[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
