"""Read-only Observation Telegram/operator surface for V3.8.

The listener is intended to run only in the standalone Observation control
process.  Collector/research processes may send notifications with the same
bot, but only one process consumes getUpdates.
"""

from __future__ import annotations

import html
import logging
from pathlib import Path

from nbot.observation.recommendation import ObservationControlTarget
from .status_proxy import ObservationReadOnlyStatusProvider
from .telegram import TelegramClient, TelegramCommandListener, TelegramDispatcher


OBSERVATION_TELEGRAM_COMMANDS: tuple[tuple[str, str], ...] = (
    ("status", "Observation control and health"),
    ("recommendation", "Recommendation readiness"),
    ("memory", "Compact research memory"),
    ("epoch", "Research epoch status"),
    ("champion", "Base Research Champion evaluator"),
    ("challenger", "Active and latest challenger"),
    ("governance", "Frozen Research Champion eligibility"),
    ("research", "Research Champion review"),
    ("paper", "Frozen Paper Champion gate"),
    ("learning", "Combined V3.9 learning status"),
    ("db", "LIVE evidence database integrity"),
    ("help", "Show all Observation commands"),
)

OBSERVATION_COMMAND_VIEWS: dict[str, tuple[str, str]] = {
    "/status": ("observation", "OBSERVATION STATUS"),
    "/recommendation": ("recommendation", "RECOMMENDATION STATUS"),
    "/memory": ("memory", "RESEARCH MEMORY"),
    "/epoch": ("epoch", "RESEARCH EPOCH"),
    "/champion": ("champion", "RESEARCH CHAMPION"),
    "/challenger": ("challenger", "CHALLENGER STATUS"),
    "/governance": ("governance", "RESEARCH GOVERNANCE"),
    "/research": ("research", "RESEARCH CHAMPION REVIEW"),
    "/paper": ("paper", "PAPER CHAMPION GATE"),
    "/learning": ("learning", "V3.9 LEARNING STATUS"),
    "/db": ("db", "OBSERVATION DATABASE"),
}


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
        self.status_provider = ObservationReadOnlyStatusProvider(
            repo_root=self.repo_root, target=self.target
        )
        self.listener = TelegramCommandListener(telegram, self.handle_command, logger=logger)

    def start(self) -> None:
        self.dispatcher.start()
        self.dispatcher.set_commands(OBSERVATION_TELEGRAM_COMMANDS)
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

    def handle_command(self, text: str) -> None:
        command = str(text or "").strip().split()[0].split("@", 1)[0].lower() if str(text or "").strip() else ""
        try:
            if command in OBSERVATION_COMMAND_VIEWS:
                view, title = OBSERVATION_COMMAND_VIEWS[command]
                payload = self.status_provider.status(view)
                if payload.get("order_authority") != "NONE":
                    raise RuntimeError("OBSERVATION_OPERATOR_AUTHORITY_INVALID")
                body = payload.get("telegram_body")
                if not isinstance(body, str) or not body.strip():
                    raise RuntimeError("OBSERVATION_OPERATOR_BODY_INVALID")
                self.dispatcher.send_info(title, body)
            elif command == "/help":
                self.dispatcher.send_info(
                    "OBSERVATION COMMANDS",
                    "/status — control/recommendation health\n"
                    "/recommendation — current recommendation readiness\n"
                    "/memory — compact research memory\n"
                    "/epoch — research epoch status\n"
                    "/champion — base Research Champion evaluator\n"
                    "/challenger — active/latest challenger + PASS/REJECT\n"
                    "/governance — frozen Research Champion eligibility\n"
                    "/research — Research Champion review/pointer\n"
                    "/paper — frozen Paper Champion gate\n"
                    "/learning — compact combined V3.9 learning status\n"
                    "/db — LIVE evidence DB integrity\n"
                    "/help — this list\n\nAll Observation commands are read-only; order authority is NONE.",
                )
            elif command:
                self.dispatcher.send_warning("UNKNOWN COMMAND", f"{html.escape(command)}\nUse /help.")
        except Exception as exc:
            self.logger.warning("OBSERVATION_OPERATOR_COMMAND_FAILED command=%s error=%s:%s", command, type(exc).__name__, exc)
            self.dispatcher.send_warning("COMMAND FAILED", "Observation remained read-only and collection was unaffected.")
