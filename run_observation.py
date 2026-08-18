#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from nbot.binance import BinancePublicClient
from nbot.champion import CHAMPION_CONFIG, WalkForwardChampionEvaluator
from nbot.config import CONFIG, POLICY_CONFIG
from nbot.db import EvidenceDB
from nbot.observer import MarketEvidenceObserver
from nbot.policies import ExitPolicyLab
from nbot.runtime_ops import TelegramOperator, configure_role_logging, telegram_escape_plain
from nbot.selection import EntrySelectionLab, SELECTION_CONFIG


DEFAULT_OBSERVATION_LOG_PATH = Path("logs/observation.log")


def _observation_status_text(db: EvidenceDB) -> str:
    status = db.status()
    latest = status.get("latest_event")
    latest_text = "NONE"
    if latest:
        latest_text = (
            f"open_ms={latest[0]} stored={latest[1]}/{latest[2]} "
            f"status={latest[3]} context_complete={latest[6]}"
        )
    return (
        f"Role: {CONFIG.role}\n"
        f"Market: {CONFIG.market_environment}\n"
        f"Events: {status['events']}\n"
        f"Complete: {status['complete_events']}\n"
        f"Partial: {status['partial_events']}\n"
        f"Research-ready: {status['research_ready_events']}\n"
        f"Recovered: {status['recovered_events']}\n"
        f"Candles: {status['candles']}\n"
        f"Snapshots: {status['snapshots']}\n"
        f"Funding rows: {status['funding_events']}\n"
        f"Latest: {latest_text}"
    )


def _champion_status_text(db: EvidenceDB) -> str:
    ExitPolicyLab(CONFIG, POLICY_CONFIG, db).initialize()
    EntrySelectionLab(CONFIG, SELECTION_CONFIG, db).initialize()
    report = WalkForwardChampionEvaluator(CONFIG, CHAMPION_CONFIG, db).status()
    evaluation = report.get("evaluation")
    champion = report.get("champion")
    return (
        f"Authority: {report.get('authority')}\n"
        f"Candidate scored events: {report.get('candidate_scored_events')}\n"
        f"Validation: {report.get('available_validation_events')}/{report.get('required_validation_events')}\n"
        f"Test: {report.get('available_test_events')}/{report.get('required_test_events')}\n"
        f"Evaluation: {telegram_escape_plain(evaluation)}\n"
        f"Champion: {telegram_escape_plain(champion)}"
    )


def _observation_operator_command(db: EvidenceDB, operator: TelegramOperator, logger, text: str) -> None:
    parts = str(text or "").strip().split()
    if not parts:
        return
    command = parts[0].split("@", 1)[0].lower()
    try:
        if command in {"/status", "/observation"}:
            operator.info("OBSERVATION STATUS", _observation_status_text(db))
        elif command in {"/champion", "/learning"}:
            operator.info("RESEARCH CHAMPION", _champion_status_text(db))
        elif command == "/audit":
            report = db.audit(record=False)
            body = (
                f"Integrity: {report.get('integrity')}\n"
                f"Missing events: {report.get('missing_events')}\n"
                f"Candle gaps: {report.get('candle_gaps')}\n"
                f"Duplicate conflicts: {report.get('duplicate_conflicts')}\n"
                f"Spread coverage: {report.get('spread_coverage_pct')}%\n"
                f"Funding coverage: {report.get('funding_coverage_pct')}%"
            )
            operator.info("OBSERVATION AUDIT", body)
        elif command == "/help":
            operator.info(
                "OBSERVATION COMMANDS",
                "/status — evidence collector status\n"
                "/champion — walk-forward champion/evidence status\n"
                "/audit — read-only evidence integrity summary\n"
                "/help — show commands\n\n"
                "Observation Telegram is read-only and has no order authority.",
            )
        else:
            operator.warning("UNKNOWN OBSERVATION COMMAND", f"{telegram_escape_plain(command)}\nUse /help.")
    except Exception as exc:
        logger.error("OBSERVATION_TELEGRAM_COMMAND_FAILED command=%s error=%s:%s", command, type(exc).__name__, exc)
        operator.warning("OBSERVATION COMMAND FAILED", f"{telegram_escape_plain(type(exc).__name__)}")


def main() -> int:
    log_path = Path(os.getenv("NBOT_OBSERVATION_LOG_PATH", str(DEFAULT_OBSERVATION_LOG_PATH)))
    logger, _ = configure_role_logging("OBSERVATION", log_path=log_path, stderr=True)
    logger.info("NBOT_OBSERVATION_START role=%s market=%s", CONFIG.role, CONFIG.market_environment)
    db = EvidenceDB(CONFIG)
    db.initialize()
    operator = TelegramOperator.from_env("OBSERVATION", logger)
    if operator is not None:
        operator.start_listener(lambda text: _observation_operator_command(db, operator, logger, text))
        operator.info("OBSERVATION WORKER STARTED", _observation_status_text(db))
    client = BinancePublicClient(CONFIG)
    MarketEvidenceObserver(CONFIG, client, db).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
