"""Mainnet runtime entry gating and recovery without network or credentials."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from nbot.communication.authorities import LIVE_LEARNED_AUTHORITY
import run_execution as runtime


class MainnetRuntimeTests(unittest.TestCase):
    def run_once(self, *, open_position=False, armed=False, enable=False, current_sha=True,
                 probe_enable=False, health_status="NOT_READY"):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exchange, client, worker, operator = [MagicMock() for _ in range(4)]
            client.health.return_value={"status":health_status,"recommendation_authority":LIVE_LEARNED_AUTHORITY}
            def make_surface(**kwargs):
                if probe_enable:
                    self.policy_result=kwargs["enable_policy"]()
                return operator
            exchange.guard.preflight.return_value = {
                "armed": armed, "session_entries": 0, "max_session_entries": 1}
            exchange.guard._parse_arm.return_value = {"sha": "a"*40 if current_sha else "b"*40}
            arm = root/"runtime/execution/real/LIVE_TRADING_ARMED"
            arm.parent.mkdir(parents=True)
            arm.write_text("test fixture")
            worker.prepare.return_value = SimpleNamespace(status="RECOVERED")
            worker.state.open_position = SimpleNamespace(symbol="BTCUSDT") if open_position else None
            worker.state.snapshot.entries_enabled = False
            worker.process_flat_cycle.return_value = "NO_TRADE"
            stop = {}
            def register(signum, handler):
                stop["handler"] = handler
            def sleep(_seconds):
                stop["handler"](None, None)
            with patch.object(runtime, "BinanceLiveExchange", return_value=exchange), \
                 patch.object(runtime.subprocess, "check_output", return_value="a"*40), \
                 patch.object(runtime, "build_integrated_control_client", return_value=client), \
                 patch.object(runtime, "build_execution_worker", return_value=worker) as builder, \
                 patch.object(runtime, "_operator_surface", side_effect=make_surface), \
                 patch.object(runtime, "operator_entries_blocked", return_value=not enable), \
                 patch.object(runtime.signal, "signal", side_effect=register), \
                 patch.object(runtime.time, "sleep", side_effect=sleep):
                result = runtime.run_learned_paper_runtime(
                    repo_root=root, profile_name="live-trade",
                    environment={"LIVE_API_KEY": "fixture", "LIVE_API_SECRET": "fixture"},
                    idle_poll_seconds=.01, open_poll_seconds=.01)
            self.assertEqual(result, 0)
            self.assertEqual(builder.call_args.kwargs["allowed_entry_authorities"],
                             frozenset({LIVE_LEARNED_AUTHORITY}))
            self.assertEqual(builder.call_args.kwargs["risk_config"].max_notional_usd, 25)
            worker.disable_new_entries.assert_called()
            exchange.disconnect.assert_called_once()
            return exchange, client, worker

    def test_disarmed_flat_runtime_cannot_enable(self):
        _, _, worker = self.run_once(enable=True)
        worker.enable_new_entries.assert_not_called()

    def test_telegram_real_money_enable_still_requires_arm_and_ready_learning(self):
        _, client, _ = self.run_once(probe_enable=True)
        self.assertFalse(self.policy_result[0])
        client.health.assert_not_called()
        self.run_once(armed=True, probe_enable=True)
        self.assertEqual(self.policy_result,(False,"LEARNED_NOT_READY"))
        self.run_once(armed=True, probe_enable=True, health_status="READY")
        self.assertEqual(self.policy_result,(True,"LEARNED_READY"))

    def test_armed_runtime_still_requires_operator_enable(self):
        _, _, worker = self.run_once(armed=True)
        worker.enable_new_entries.assert_not_called()

    def test_explicit_permission_enables_only_matching_release(self):
        _, _, worker = self.run_once(armed=True, enable=True)
        worker.enable_new_entries.assert_called_once()
        _, _, worker = self.run_once(armed=True, enable=True, current_sha=False)
        worker.enable_new_entries.assert_not_called()

    def test_disarmed_open_position_is_managed_without_observation(self):
        exchange, client, worker = self.run_once(open_position=True)
        exchange.quote.assert_called_once_with("BTCUSDT")
        worker.process_open_quote.assert_called_once()
        worker.enable_new_entries.assert_not_called()
        exchange.guard.preflight.assert_not_called()
        client.health.assert_not_called()
        client.request_proposal.assert_not_called()
