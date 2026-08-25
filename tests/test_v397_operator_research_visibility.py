from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from nbot.communication.client import RemoteObservationClient
from nbot.communication.server import ObservationControlServer
from nbot.operator.execution import EXECUTION_TELEGRAM_COMMANDS, ExecutionOperatorSurface
from nbot.operator.observation import OBSERVATION_TELEGRAM_COMMANDS, ObservationOperatorSurface
from nbot.operator.status_proxy import ObservationReadOnlyStatusProvider
from nbot.operator.telegram import TelegramClient, TelegramConfig
from tests.test_v386_operator_observability import FakeWorker


TOKEN = "control-token-" + "x" * 32
SHA = "a" * 40


class FakeDatabase:
    def integrity_check(self):
        return {"quick_check": "ok", "foreign_key_errors": 0}


class FakeTarget:
    def __init__(self):
        self.database = FakeDatabase()

    def health_snapshot(self):
        return {
            "status": "READY",
            "reason": None,
            "profile": "live-paper",
            "market_environment": "LIVE",
            "recommendation_authority": "LIVE_PAPER_OPERATIONAL_CANARY_V1",
            "release_sha": SHA,
            "order_authority": "NONE",
        }


class CaptureDispatcher:
    def __init__(self):
        self.info = []
        self.warning = []

    def send_info(self, title, body=""):
        self.info.append((title, body))
        return True

    def send_warning(self, title, body=""):
        self.warning.append((title, body))
        return True


class V397OperatorResearchVisibilityTests(unittest.TestCase):
    def _logger(self, name):
        logger = logging.getLogger(name)
        logger.handlers[:] = [logging.NullHandler()]
        logger.propagate = False
        return logger

    def _telegram(self):
        return TelegramClient(
            TelegramConfig("token", "123", "456", 1.0),
            requester=lambda *_args: None,
        )

    def test_remote_operator_status_roundtrip_is_authenticated_and_read_only(self):
        def provider(view):
            return {
                "status": "OK",
                "view": view,
                "order_authority": "NONE",
                "telegram_body": "Research Champion: NONE",
                "document": {"decision": "WAIT_FOR_FROZEN_RESEARCH_ELIGIBILITY"},
            }

        server = ObservationControlServer(
            target=object(),
            auth_token=TOKEN,
            port=0,
            operator_status_provider=provider,
        )
        host, port = server.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="testnet-trade",
                    auth_token=TOKEN,
                    receipt_directory=Path(td),
                    execution_release_sha=SHA,
                )
                payload = client.operator_status("research")
                self.assertEqual(payload["view"], "research")
                self.assertEqual(payload["order_authority"], "NONE")
                self.assertEqual(
                    payload["document"]["decision"],
                    "WAIT_FOR_FROZEN_RESEARCH_ELIGIBILITY",
                )
        finally:
            server.stop()

    def test_operator_status_uses_separate_bounded_timeout(self):
        def provider(view):
            time.sleep(0.2)
            return {
                "status": "OK",
                "view": view,
                "order_authority": "NONE",
                "telegram_body": "slow read-only report",
                "document": {},
            }

        server = ObservationControlServer(
            target=object(),
            auth_token=TOKEN,
            port=0,
            operator_status_provider=provider,
        )
        host, port = server.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="testnet-trade",
                    auth_token=TOKEN,
                    receipt_directory=Path(td),
                    execution_release_sha=SHA,
                    timeout_seconds=0.1,
                )
                self.assertEqual(client.timeout_seconds, 0.1)
                payload = client.operator_status("learning")
                self.assertEqual(payload["view"], "learning")
                self.assertEqual(payload["order_authority"], "NONE")
                self.assertEqual(client.timeout_seconds, 0.1)
        finally:
            server.stop()

    def test_server_rejects_operator_status_when_provider_claims_authority(self):
        def provider(view):
            return {
                "status": "OK",
                "view": view,
                "order_authority": "LIVE_TRADE",
                "telegram_body": "bad",
                "document": {},
            }

        server = ObservationControlServer(
            target=object(),
            auth_token=TOKEN,
            port=0,
            operator_status_provider=provider,
        )
        host, port = server.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                client = RemoteObservationClient(
                    base_url=f"http://{host}:{port}",
                    profile="testnet-trade",
                    auth_token=TOKEN,
                    receipt_directory=Path(td),
                    execution_release_sha=SHA,
                )
                with self.assertRaisesRegex(Exception, "OBSERVATION_HTTP_ERROR"):
                    client.operator_status("research")
        finally:
            server.stop()

    def test_provider_uses_only_fixed_read_only_admin_commands(self):
        provider = ObservationReadOnlyStatusProvider(
            repo_root=Path("/repo"), target=FakeTarget()
        )
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(tuple(argv))
            command = argv[-1]
            payload = {
                "research-memory-status": {
                    "memory_version": "M",
                    "epochs": 1,
                    "events": 96,
                    "authority": "RESEARCH_ONLY_NO_EXECUTION",
                },
                "research-epoch-status": {
                    "authority": "RESEARCH_ONLY_NO_EXECUTION",
                    "plan": {"status": "WAIT"},
                },
                "champion-status": {
                    "authority": "RESEARCH_ONLY_NO_EXECUTION",
                    "decision": "REJECT_RESEARCH_CHAMPION",
                },
                "learning-status": {
                    "status": "V3_9_CONTINUOUS_CHALLENGER_LEARNING_ENABLED",
                    "challengers": {},
                    "governance": {},
                    "research_champion_promotion": {},
                    "paper_champion": {},
                },
                "governance-status": {
                    "research_champion_eligibility": {},
                    "champion_pointer": {},
                    "challenger_states": [],
                },
                "research-champion-review": {
                    "decision": "WAIT_FOR_FROZEN_RESEARCH_ELIGIBILITY",
                    "execution_authority": "NONE",
                    "paper_champion_authority": False,
                },
                "paper-champion-status": {
                    "decision": "WAIT_FOR_RESEARCH_CHAMPION",
                    "thresholds": {},
                    "execution_authority": "NONE",
                    "paper_champion_authority": False,
                },
                "market-regime-status": {"coverage": {}},
                "operational-regime-status": {},
                "challenger-status": {
                    "active_challenger": {},
                    "active_future_evidence": {},
                    "passed_windows": 0,
                    "rejected_windows": 1,
                },
            }[command]
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

        with patch("nbot.operator.status_proxy.subprocess.run", side_effect=fake_run):
            for view in (
                "memory",
                "epoch",
                "champion",
                "learning",
                "governance",
                "research",
                "paper",
                "market-regimes",
                "operational-regimes",
            ):
                result = provider.status(view)
                self.assertEqual(result["order_authority"], "NONE")
            provider.status("challenger")

        allowed = {
            "research-memory-status",
            "research-epoch-status",
            "champion-status",
            "learning-status",
            "challenger-status",
            "governance-status",
            "research-champion-review",
            "paper-champion-status",
            "market-regime-status",
            "operational-regime-status",
        }
        self.assertTrue(calls)
        self.assertTrue(all(call[-1] in allowed for call in calls))
        with self.assertRaisesRegex(ValueError, "VIEW_INVALID"):
            provider.status("regimes")
        with self.assertRaisesRegex(ValueError, "VIEW_INVALID"):
            provider.status("research-champion-promote")

    def test_challenger_view_shows_latest_pass_or_reject_and_current_evidence(self):
        provider = ObservationReadOnlyStatusProvider(
            repo_root=Path("/repo"), target=FakeTarget()
        )
        challenger = {
            "active_challenger": {
                "challenger_version": "CH-3",
                "model_version": "MODEL-3",
            },
            "active_future_evidence": {
                "available_future_events": 4,
                "required_future_events": 40,
                "available_validation_events": 4,
                "available_test_events": 0,
            },
            "passed_windows": 1,
            "rejected_windows": 1,
        }
        governance = {
            "challenger_states": [
                {"challenger_version": "CH-1", "state": "REJECT_RESEARCH_GATE"},
                {"challenger_version": "CH-2", "state": "PASS_RESEARCH_GATE"},
                {"challenger_version": "CH-3", "state": "ACTIVE_WAITING_FUTURE_EVIDENCE"},
            ]
        }
        with patch.object(
            provider,
            "_admin_json",
            side_effect=[challenger, governance],
        ):
            result = provider.status("challenger")
        body = result["telegram_body"]
        self.assertIn("Latest finalized: CH-2", body)
        self.assertIn("Latest result: PASS_RESEARCH_GATE", body)
        self.assertIn("PASS windows: 1", body)
        self.assertIn("REJECT windows: 1", body)
        self.assertIn("Future evidence: 4/40", body)

    def test_execution_learning_command_is_display_only_even_while_open(self):
        with tempfile.TemporaryDirectory() as td:
            worker = FakeWorker()
            sentinel_position = SimpleNamespace(symbol="BTCUSDT", side="LONG")
            worker.state.open_position = sentinel_position
            calls = []

            def reader(view):
                calls.append(view)
                return {
                    "status": "OK",
                    "view": view,
                    "order_authority": "NONE",
                    "telegram_body": "Research Champion: NONE",
                    "document": {},
                }

            surface = ExecutionOperatorSurface(
                repo_root=Path(td),
                profile="live-paper",
                worker=worker,
                telegram=self._telegram(),
                system_log=self._logger("v397.exec.info"),
                trade_log=self._logger("v397.exec.trade"),
                enable_policy=lambda: (False, "BLOCKED"),
                observation_status_reader=reader,
            )
            capture = CaptureDispatcher()
            surface.dispatcher = capture
            surface.handle_command("/learning")

            self.assertEqual(calls, ["learning"])
            self.assertEqual(worker.disable_calls, 0)
            self.assertEqual(worker.enable_calls, 0)
            self.assertIs(worker.state.open_position, sentinel_position)
            self.assertEqual(capture.info[0][0], "V3.9 LEARNING STATUS")

    def test_execution_remote_status_failure_does_not_mutate_capital_state(self):
        with tempfile.TemporaryDirectory() as td:
            worker = FakeWorker()
            sentinel_position = SimpleNamespace(symbol="ETHUSDT", side="SHORT")
            worker.state.open_position = sentinel_position

            def broken(_view):
                raise RuntimeError("observation offline")

            surface = ExecutionOperatorSurface(
                repo_root=Path(td),
                profile="live-paper",
                worker=worker,
                telegram=self._telegram(),
                system_log=self._logger("v397.exec.fail"),
                trade_log=self._logger("v397.exec.fail.trade"),
                enable_policy=lambda: (False, "BLOCKED"),
                observation_status_reader=broken,
            )
            capture = CaptureDispatcher()
            surface.dispatcher = capture
            surface.handle_command("/research")

            self.assertEqual(worker.disable_calls, 0)
            self.assertEqual(worker.enable_calls, 0)
            self.assertIs(worker.state.open_position, sentinel_position)
            self.assertEqual(capture.warning[0][0], "OBSERVATION STATUS UNAVAILABLE")
            self.assertIn("unchanged", capture.warning[0][1])

    def test_execution_help_lists_v39_read_only_views(self):
        with tempfile.TemporaryDirectory() as td:
            worker = FakeWorker()
            surface = ExecutionOperatorSurface(
                repo_root=Path(td),
                profile="live-paper",
                worker=worker,
                telegram=self._telegram(),
                system_log=self._logger("v397.help"),
                trade_log=self._logger("v397.help.trade"),
                enable_policy=lambda: (False, "BLOCKED"),
            )
            capture = CaptureDispatcher()
            surface.dispatcher = capture
            surface.handle_command("/help")
            body = capture.info[0][1]
            for command in (
                "/observation",
                "/challenger",
                "/governance",
                "/research",
                "/paper",
                "/learning",
            ):
                self.assertIn(command, body)
            self.assertNotIn("/" + "regimes", body)

    def test_telegram_role_menus_include_all_supported_commands_without_regimes(self):
        execution_names = {name for name, _description in EXECUTION_TELEGRAM_COMMANDS}
        observation_names = {name for name, _description in OBSERVATION_TELEGRAM_COMMANDS}

        self.assertEqual(
            execution_names,
            {
                "status", "position", "health", "recent", "pnl",
                "observation", "recommendation", "memory", "epoch", "champion",
                "challenger", "governance", "research", "paper", "learning", "db",
                "disable", "enable", "help",
            },
        )
        self.assertEqual(
            observation_names,
            {
                "status", "recommendation", "memory", "epoch", "champion",
                "challenger", "governance", "research", "paper", "learning", "db", "help",
            },
        )
        self.assertNotIn("regimes", execution_names)
        self.assertNotIn("regimes", observation_names)

    def test_observation_surface_exposes_full_v39_read_only_views(self):
        target = FakeTarget()
        surface = ObservationOperatorSurface(
            repo_root=Path("/repo"),
            target=target,
            telegram=self._telegram(),
            logger=self._logger("v397.obs.commands"),
        )
        capture = CaptureDispatcher()
        surface.dispatcher = capture
        with patch.object(
            surface.status_provider,
            "status",
            return_value={
                "status": "OK",
                "order_authority": "NONE",
                "telegram_body": "read-only",
                "document": {},
            },
        ) as status:
            for command in (
                "/status", "/recommendation", "/memory", "/epoch", "/champion",
                "/challenger", "/governance", "/research", "/paper", "/learning", "/db",
            ):
                surface.handle_command(command)
        self.assertEqual(status.call_count, 11)
        self.assertEqual(len(capture.info), 11)

        surface.handle_command("/" + "regimes")
        self.assertEqual(capture.warning[-1][0], "UNKNOWN COMMAND")


if __name__ == "__main__":
    unittest.main()
