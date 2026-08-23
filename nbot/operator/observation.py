"""Read-only Observation Telegram/operator surface for V3.8.

The listener is intended to run only in the standalone Observation control
process.  Collector/research processes may send notifications with the same
bot, but only one process consumes getUpdates.
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path
import subprocess
from typing import Mapping

from nbot.observation.recommendation import ObservationControlTarget
from .telegram import TelegramClient, TelegramCommandListener, TelegramDispatcher


class ObservationOperatorSurface:
    def __init__(
        self,
        *,
        repo_root: Path,
        target: ObservationControlTarget,
        telegram: TelegramClient,
        logger: logging.Logger,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.target = target
        self.telegram = telegram
        self.dispatcher = TelegramDispatcher(telegram, logger=logger)
        self.logger = logger
        self.listener = TelegramCommandListener(telegram, self.handle_command, logger=logger)

    def start(self) -> None:
        self.dispatcher.start()
        health = self.target.health_snapshot()
        self.dispatcher.send_info(
            "OBSERVATION CONTROL STARTED",
            f"Profile: {html.escape(str(health['profile']))}\n"
            f"Status: {html.escape(str(health['status']))}\n"
            f"Reason: {html.escape(str(health.get('reason') or 'NONE'))}\n"
            "Order authority: NONE",
        )
        self.listener.start()

    def stop(self) -> None:
        self.listener.stop()
        self.dispatcher.send_info("OBSERVATION CONTROL STOPPED", "Order authority remained NONE.")
        self.dispatcher.stop()

    def _admin_json(self, *args: str) -> Mapping[str, object]:
        proc = subprocess.run(
            [str(self.repo_root / ".venv/bin/python"), str(self.repo_root / "nbot_admin.py"), *args],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"NBOT_ADMIN_FAILED:{' '.join(args)}:{proc.returncode}")
        data = json.loads(proc.stdout)
        if not isinstance(data, dict):
            raise RuntimeError("NBOT_ADMIN_RESPONSE_INVALID")
        return data

    @staticmethod
    def _lines(data: Mapping[str, object], keys: tuple[str, ...]) -> str:
        rows = []
        for key in keys:
            if key in data:
                rows.append(f"{key}: {html.escape(str(data.get(key)))}")
        return "\n".join(rows) or html.escape(json.dumps(dict(data), sort_keys=True)[:3500])

    def handle_command(self, text: str) -> None:
        command = str(text or "").strip().split()[0].split("@", 1)[0].lower() if str(text or "").strip() else ""
        try:
            if command in {"/status", "/recommendation"}:
                health = self.target.health_snapshot()
                self.dispatcher.send_info(
                    "OBSERVATION STATUS" if command == "/status" else "RECOMMENDATION STATUS",
                    self._lines(
                        health,
                        (
                            "status", "reason", "profile", "market_environment", "evidence_lineage",
                            "recommendation_authority", "order_authority", "release_sha", "store_id",
                        ),
                    ),
                )
            elif command == "/memory":
                data = self._admin_json("research-memory-status")
                ridge = data.get("ridge_state") if isinstance(data.get("ridge_state"), dict) else {}
                body = self._lines(data, ("memory_version", "epochs", "events", "latest_event_open_ms", "quick_check", "authority"))
                body += "\n" + self._lines(ridge, ("training_event_count", "training_row_count", "through_event_ms", "state_digest"))
                self.dispatcher.send_info("RESEARCH MEMORY", body)
            elif command == "/epoch":
                data = self._admin_json("research-epoch-status")
                plan = data.get("plan") if isinstance(data.get("plan"), dict) else {}
                self.dispatcher.send_info(
                    "RESEARCH EPOCH",
                    self._lines(plan, ("status", "target_start_ms", "target_end_ms", "memory_latest_event_ms", "latest_raw_event_ms")),
                )
            elif command == "/champion":
                data = self._admin_json("champion-status")
                body = (
                    f"authority: {html.escape(str(data.get('authority')))}\n"
                    f"source: {html.escape(str(data.get('source')))}\n"
                    f"research_champions: {html.escape(str(data.get('research_champions')))}\n"
                    f"evaluations: {html.escape(str(data.get('research_champion_evaluations')))}"
                )
                self.dispatcher.send_info("RESEARCH CHAMPION", body)
            elif command == "/learning":
                data = self._admin_json("learning-status")
                self.dispatcher.send_info("LEARNING STATUS", self._lines(data, ("status", "authority")))
            elif command == "/db":
                report = self.target.database.integrity_check()
                self.dispatcher.send_info("OBSERVATION DATABASE", html.escape(json.dumps(report, sort_keys=True, indent=2)[:3500]))
            elif command == "/help":
                self.dispatcher.send_info(
                    "OBSERVATION COMMANDS",
                    "/status — control/recommendation health\n"
                    "/memory — compact research memory\n"
                    "/epoch — next 96-event epoch plan\n"
                    "/champion — research Champion state\n"
                    "/learning — continuous-learning status\n"
                    "/db — LIVE evidence DB integrity\n"
                    "/recommendation — current recommendation readiness\n"
                    "/help — this list\n\nAll Observation commands are read-only; order authority is NONE.",
                )
            elif command:
                self.dispatcher.send_warning("UNKNOWN COMMAND", f"{html.escape(command)}\nUse /help.")
        except Exception as exc:
            self.logger.warning("OBSERVATION_OPERATOR_COMMAND_FAILED command=%s error=%s:%s", command, type(exc).__name__, exc)
            self.dispatcher.send_warning("COMMAND FAILED", "Observation remained read-only and collection was unaffected.")
