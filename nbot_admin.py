#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from nbot.binance import BinancePublicClient, latest_closed_open_time_ms
from nbot.config import CONFIG
from nbot.db import EvidenceDB
from nbot.observer import MarketEvidenceObserver


def iso_ms(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def build_observer() -> MarketEvidenceObserver:
    db = EvidenceDB(CONFIG)
    db.initialize()
    return MarketEvidenceObserver(CONFIG, BinancePublicClient(CONFIG), db)


def cmd_init(_args: argparse.Namespace) -> int:
    db = EvidenceDB(CONFIG)
    db.initialize()
    print(f"INITIALIZED={db.path}")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    status = EvidenceDB(CONFIG).status()
    print(f"role                  : {CONFIG.role}")
    print(f"market                : {CONFIG.market_environment}")
    print(f"schema                : {CONFIG.schema_version}")
    print(f"database              : {status['database_path']}")
    print(f"events                : {status['events']}")
    print(f"complete_events       : {status['complete_events']}")
    print(f"partial_events        : {status['partial_events']}")
    print(f"research_ready_events : {status['research_ready_events']}")
    print(f"recovered_events      : {status['recovered_events']}")
    print(f"candles               : {status['candles']}")
    print(f"snapshots             : {status['snapshots']}")
    print(f"funding_events        : {status['funding_events']}")
    latest = status["latest_event"]
    if latest:
        print(
            "latest_event          : "
            f"{iso_ms(latest[0])} stored={latest[1]}/{latest[2]} "
            f"status={latest[3]} duration_ms={latest[4]} "
            f"mode={latest[5]} context_complete={latest[6]}"
        )
    else:
        print("latest_event          : NONE")
    return 0


def cmd_check_live(_args: argparse.Namespace) -> int:
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


def cmd_collect_once(_args: argparse.Namespace) -> int:
    result = build_observer().collect_once()
    print(json.dumps(result.__dict__, sort_keys=True))
    return 0 if result.status == "COMPLETE" else 2


def cmd_recover_gaps(args: argparse.Namespace) -> int:
    result = build_observer().recover_gaps(max_events=args.max_events)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["failed"] == 0 else 2


def cmd_sync_funding(_args: argparse.Namespace) -> int:
    result = build_observer().sync_funding_history(force=True)
    print(json.dumps(result, sort_keys=True))
    return 0


def cmd_audit(_args: argparse.Namespace) -> int:
    report = EvidenceDB(CONFIG).audit(record=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    failures = (
        report["integrity"] != "ok"
        or report["foreign_key_violations"] != 0
        or report["missing_membership_candles"] != 0
        or report["missing_point_in_time_snapshots"] != 0
        or report["incomplete_symbol_events"] != 0
        or report["duplicate_conflicts"] != 0
        or report["invalid_candles"] != 0
        or report["future_candles"] != 0
        or report["future_event_rows"] != 0
        or report["invalid_spreads"] != 0
        or report["late_point_in_time_snapshots"] != 0
        or report["missing_events"] != 0
    )
    return 2 if failures else 0


def cmd_checkpoint(_args: argparse.Namespace) -> int:
    busy, log_frames, checkpointed = EvidenceDB(CONFIG).checkpoint()
    print(f"WAL_CHECKPOINT busy={busy} log_frames={log_frames} checkpointed={checkpointed}")
    return 0 if busy == 0 else 2


def cmd_backup(args: argparse.Namespace) -> int:
    destination = None if args.output is None else Path(args.output)
    path = EvidenceDB(CONFIG).backup(destination)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"BACKUP={path}")
    print(f"BYTES={path.stat().st_size}")
    print(f"SHA256={digest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="NBOT V2 administration")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "status", "check-live", "collect-once", "sync-funding", "audit", "checkpoint"):
        sub.add_parser(name)

    recover = sub.add_parser("recover-gaps")
    recover.add_argument("--max-events", type=int, default=CONFIG.gap_recovery_max_events_per_cycle)

    backup = sub.add_parser("backup")
    backup.add_argument("--output")

    args = parser.parse_args()
    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "check-live": cmd_check_live,
        "collect-once": cmd_collect_once,
        "recover-gaps": cmd_recover_gaps,
        "sync-funding": cmd_sync_funding,
        "audit": cmd_audit,
        "checkpoint": cmd_checkpoint,
        "backup": cmd_backup,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
