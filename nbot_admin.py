#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from nbot.binance import BinancePublicClient, latest_closed_open_time_ms
from nbot.config import CONFIG, OUTCOME_CONFIG, POLICY_CONFIG, RESEARCH_CONFIG
from nbot.db import EvidenceDB
from nbot.observer import MarketEvidenceObserver
from nbot.research import ResearchEngine
from nbot.outcomes import FuturePathEngine
from nbot.policies import ExitPolicyLab


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



def build_research() -> ResearchEngine:
    db = EvidenceDB(CONFIG)
    db.initialize()
    return ResearchEngine(CONFIG, RESEARCH_CONFIG, db)


def cmd_research_build(args: argparse.Namespace) -> int:
    result = build_research().build(max_events=args.max_events, rebuild=args.rebuild)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


def cmd_research_status(_args: argparse.Namespace) -> int:
    print(json.dumps(build_research().status(), indent=2, sort_keys=True))
    return 0


def cmd_research_audit(_args: argparse.Namespace) -> int:
    report = build_research().audit()
    print(json.dumps(report, indent=2, sort_keys=True))
    failures = (
        report["unbuilt_events"] != 0
        or report["feature_definition_mismatch"] != 0
        or report["signal_definition_mismatches"] != 0
        or report["context_incomplete_feature_rows"] != 0
        or report["feature_rows_without_snapshot"] != 0
        or report["future_source_rows"] != 0
        or report["invalid_percentiles"] != 0
        or report["feature_row_count_mismatches"] != 0
        or report["signal_rows_without_feature"] != 0
        or report["annotation_count_mismatches"] != 0
        or report["invalid_active_signals"] != 0
        or report["digest_mismatches"] != 0
    )
    return 2 if failures else 0



def build_outcomes() -> FuturePathEngine:
    db = EvidenceDB(CONFIG)
    db.initialize()
    return FuturePathEngine(CONFIG, OUTCOME_CONFIG, db, BinancePublicClient(CONFIG))


def cmd_outcome_build(args: argparse.Namespace) -> int:
    result = build_outcomes().build(max_events=args.max_events, rebuild=args.rebuild)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    failures = result.funding_incomplete_events != 0 or result.path_incomplete_events != 0
    return 2 if failures else 0


def cmd_outcome_status(_args: argparse.Namespace) -> int:
    print(json.dumps(build_outcomes().status(), indent=2, sort_keys=True))
    return 0


def cmd_outcome_audit(_args: argparse.Namespace) -> int:
    report = build_outcomes().audit()
    print(json.dumps(report, indent=2, sort_keys=True))
    failures = any(
        report[key] != 0
        for key in (
            "definition_mismatch",
            "paths_without_feature",
            "invalid_source_bounds",
            "invalid_path_values",
            "cost_version_mismatches",
            "risk_version_mismatches",
            "build_row_mismatches",
            "future_cache_conflicts",
            "unresolved_attempt_events",
            "json_errors",
            "path_digest_mismatches",
            "build_digest_mismatches",
            "source_candle_digest_mismatches",
            "funding_source_digest_mismatches",
        )
    )
    return 2 if failures else 0


def build_policy_lab() -> ExitPolicyLab:
    db = EvidenceDB(CONFIG)
    db.initialize()
    return ExitPolicyLab(CONFIG, POLICY_CONFIG, db)


def cmd_policy_build(args: argparse.Namespace) -> int:
    result = build_policy_lab().build(max_events=args.max_events, rebuild=args.rebuild)
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0


def cmd_policy_status(_args: argparse.Namespace) -> int:
    print(json.dumps(build_policy_lab().status(), indent=2, sort_keys=True))
    return 0


def cmd_policy_report(_args: argparse.Namespace) -> int:
    print(json.dumps(build_policy_lab().report(), indent=2, sort_keys=True))
    return 0


def cmd_policy_audit(_args: argparse.Namespace) -> int:
    report = build_policy_lab().audit()
    print(json.dumps(report, indent=2, sort_keys=True))
    failures = any(
        report[key] != 0
        for key in (
            "lab_definition_mismatch",
            "policy_definition_mismatches",
            "result_digest_mismatches",
            "invalid_results",
            "invalid_initial_risk",
            "source_path_mismatches",
            "risk_unit_version_mismatches",
            "annotation_count_mismatches",
            "build_row_mismatches",
            "build_digest_mismatches",
            "build_source_digest_mismatches",
        )
    )
    return 2 if failures else 0

def main() -> int:
    parser = argparse.ArgumentParser(description="NBOT V2 administration")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "status", "check-live", "collect-once", "sync-funding", "audit", "checkpoint"):
        sub.add_parser(name)

    recover = sub.add_parser("recover-gaps")
    recover.add_argument("--max-events", type=int, default=CONFIG.gap_recovery_max_events_per_cycle)

    backup = sub.add_parser("backup")
    backup.add_argument("--output")

    research_build = sub.add_parser("research-build")
    research_build.add_argument("--max-events", type=int, default=RESEARCH_CONFIG.max_events_per_build)
    research_build.add_argument("--rebuild", action="store_true")
    sub.add_parser("research-status")
    sub.add_parser("research-audit")

    outcome_build = sub.add_parser("outcome-build")
    outcome_build.add_argument("--max-events", type=int, default=OUTCOME_CONFIG.max_events_per_build)
    outcome_build.add_argument("--rebuild", action="store_true")
    sub.add_parser("outcome-status")
    sub.add_parser("outcome-audit")

    policy_build = sub.add_parser("policy-build")
    policy_build.add_argument("--max-events", type=int, default=POLICY_CONFIG.max_events_per_build)
    policy_build.add_argument("--rebuild", action="store_true")
    sub.add_parser("policy-status")
    sub.add_parser("policy-report")
    sub.add_parser("policy-audit")

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
        "research-build": cmd_research_build,
        "research-status": cmd_research_status,
        "research-audit": cmd_research_audit,
        "outcome-build": cmd_outcome_build,
        "outcome-status": cmd_outcome_status,
        "outcome-audit": cmd_outcome_audit,
        "policy-build": cmd_policy_build,
        "policy-status": cmd_policy_status,
        "policy-report": cmd_policy_report,
        "policy-audit": cmd_policy_audit,
    }
    return commands[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
