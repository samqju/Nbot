from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest

from nbot.common.logging import execution_log_paths, observation_log_paths
from nbot.operator.execution import ExecutionOperatorSurface, operator_entries_blocked
from nbot.operator.telegram import TelegramClient, TelegramCommandListener, TelegramConfig, TelegramDispatcher
from deploy.execution.install_services import render_live_paper_unit


class FakeOutbox:
    def __init__(self):
        self.rows = []

    def pending(self):
        return list(self.rows)

    def pending_count(self):
        return len(self.rows)


class FakeHistory:
    def __init__(self):
        self.rows = []

    def records(self):
        return list(self.rows)


class FakeState:
    def __init__(self):
        self.open_position = None
        self.entry_inflight = None
        self.entries_enabled = False
        self.health = SimpleNamespace(
            prepare_calls=1,
            flat_cycles=0,
            open_position_ticks=0,
            stop_updates=0,
            stop_missing_events=0,
            stop_settlement_waits=0,
            stop_recoveries=0,
            emergency_exits=0,
            reconciliations=1,
            proposal_rejections=0,
            last_position_manage_ms=0.0,
            max_position_manage_ms=0.0,
            last_event="EXECUTION_PREPARED_FLAT",
        )
        self.daily_risk = SimpleNamespace(
            utc_day="2026-08-23",
            realized_pnl_usd=0.0,
            peak_realized_pnl_usd=0.0,
            loss_floor_usd=-100.0,
            highest_unrealized_usd=0.0,
            halted=False,
            halt_reason=None,
            trades_closed=0,
        )

    @property
    def snapshot(self):
        return SimpleNamespace(
            open_position=self.open_position,
            entry_inflight=self.entry_inflight,
            entries_enabled=self.entries_enabled,
            health=self.health,
            daily_risk=self.daily_risk,
        )


class FakeWorker:
    def __init__(self):
        self.state = FakeState()
        self.durable = SimpleNamespace(history=FakeHistory(), outbox=FakeOutbox())
        self.disable_calls = 0
        self.enable_calls = 0

    def disable_new_entries(self):
        self.disable_calls += 1
        self.state.entries_enabled = False

    def enable_new_entries(self):
        self.enable_calls += 1
        self.state.entries_enabled = True
        return SimpleNamespace(status="FLAT")


class OperatorObservabilityTests(unittest.TestCase):
    def _logger(self, name):
        logger = logging.getLogger(name)
        logger.handlers[:] = [logging.NullHandler()]
        logger.propagate = False
        return logger

    def _wait_for(self, predicate, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return bool(predicate())

    def test_telegram_send_edit_and_failure_are_best_effort(self):
        calls = []

        def requester(method, payload, timeout):
            calls.append((method, dict(payload), timeout))
            if method == "sendMessage":
                return {"ok": True, "result": {"message_id": 17}}
            return {"ok": True, "result": {}}

        client = TelegramClient(
            TelegramConfig("token", "123", "456", 1.0), requester=requester
        )
        self.assertEqual(client.send_message("hello"), 17)
        self.assertTrue(client.edit_message(17, "updated"))
        self.assertEqual([row[0] for row in calls], ["sendMessage", "editMessageText"])

        def broken(*_args):
            raise RuntimeError("telegram down")

        safe = TelegramClient(
            TelegramConfig("token", "123", "456", 1.0), requester=broken
        )
        self.assertIsNone(safe.send_message("never raises"))
        self.assertFalse(safe.edit_message(17, "never raises"))

    def test_dispatcher_keeps_telegram_network_latency_off_caller_thread(self):
        calls = []

        def slow_requester(method, payload, timeout):
            time.sleep(0.2)
            calls.append(method)
            return {"ok": True, "result": {"message_id": 23}}

        client = TelegramClient(
            TelegramConfig("token", "123", "456", 1.0), requester=slow_requester
        )
        dispatcher = TelegramDispatcher(client, logger=self._logger("test.dispatch"))
        started = time.monotonic()
        self.assertTrue(dispatcher.send_message("async"))
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.05)
        self.assertTrue(self._wait_for(lambda: calls == ["sendMessage"], timeout=1.0))
        dispatcher.stop()


    def test_get_updates_failure_is_not_treated_as_empty_success(self):
        client = TelegramClient(
            TelegramConfig("token", "123", "456", 1.0),
            requester=lambda *_args: None,
        )
        with self.assertRaisesRegex(RuntimeError, "TELEGRAM_GET_UPDATES_FAILED"):
            client.get_updates(offset=None, timeout_seconds=60)

    def test_listener_uses_exponential_backoff_instead_of_tight_retry_loop(self):
        delays = []

        class FailingClient:
            config = TelegramConfig("token", "123", "456", 1.0)

            def __init__(self):
                self.calls = 0

            def get_updates(self, *, offset, timeout_seconds):
                self.calls += 1
                raise RuntimeError("telegram restricted")

        client = FailingClient()
        listener = TelegramCommandListener(client, lambda _text: None)

        def controlled_sleep(delay):
            delays.append(delay)
            if len(delays) >= 4:
                listener._stop.set()

        listener.sleep = controlled_sleep
        listener._run()

        self.assertEqual(client.calls, 4)
        self.assertEqual(delays, [5.0, 10.0, 20.0, 40.0])

    def test_listener_authorizes_chat_and_user_and_discards_others(self):
        received = []
        client = TelegramClient(TelegramConfig("token", "123", "456", 1.0), requester=lambda *_: None)
        listener = TelegramCommandListener(client, received.append)
        listener._dispatch({"update_id": 1, "message": {"chat": {"id": 999}, "from": {"id": 456}, "text": "/status"}})
        listener._dispatch({"update_id": 2, "message": {"chat": {"id": 123}, "from": {"id": 999}, "text": "/status"}})
        listener._dispatch({"update_id": 3, "message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "/status"}})
        self.assertEqual(received, ["/status"])

    def test_trade_panel_open_stop_close_and_ack_use_same_message(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calls = []

            def requester(method, payload, timeout):
                calls.append((method, dict(payload)))
                if method == "sendMessage":
                    return {"ok": True, "result": {"message_id": 77}}
                return {"ok": True, "result": {}}

            worker = FakeWorker()
            worker.state.open_position = SimpleNamespace(
                proposal_id="PROP-1",
                symbol="BTCUSDT",
                side="LONG",
                entry_price=100.0,
                initial_stop_price=99.0,
                stop_price=99.0,
                quantity=10.0,
                initial_risk_usd=10.0,
                mfe_r=0.0,
                mae_r=0.0,
                entry_authority="PAPER_CHAMPION_V1",
                exit_policy_version="INTEGER_R_STEP_CONTROL",
            )
            surface = ExecutionOperatorSurface(
                repo_root=root,
                profile="live-paper",
                worker=worker,
                telegram=TelegramClient(TelegramConfig("token", "123", "456", 1.0), requester=requester),
                system_log=self._logger("test.operator.system"),
                trade_log=self._logger("test.operator.trade"),
                enable_policy=lambda: (False, "DRY"),
            )
            surface.sync()
            self.assertTrue(self._wait_for(lambda: len(calls) >= 1))
            self.assertEqual(calls[-1][0], "sendMessage")
            self.assertIn("TRADE OPEN", calls[-1][1]["text"])

            # Ordinary position ticks with unchanged protection must not touch
            # Telegram. The panel is event-driven, not tick-driven.
            before = len(calls)
            surface.sync()
            time.sleep(0.05)
            self.assertEqual(len(calls), before)

            worker.state.open_position.stop_price = 100.25
            worker.state.open_position.mfe_r = 1.3
            before = len(calls)
            surface.sync()
            self.assertTrue(self._wait_for(lambda: len(calls) > before))
            self.assertEqual(calls[-1][0], "editMessageText")
            self.assertEqual(calls[-1][1]["message_id"], 77)
            self.assertIn("100.25000000", calls[-1][1]["text"])

            worker.state.open_position = None
            outcome = {
                "outcome_id": "OUT-1",
                "proposal_id": "PROP-1",
                "profile": "live-paper",
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 100.0,
                "exit_price": 101.0,
                "quantity": 10.0,
                "initial_risk_usd": 10.0,
                "realized_pnl_usd": 10.0,
                "r_multiple": 1.0,
                "mfe_r": 1.3,
                "mae_r": -0.2,
                "entry_timestamp_ms": 1000,
                "closed_timestamp_ms": 61000,
                "final_stop_price": 100.25,
                "exit_reason": "PROTECTIVE_STOP_TRIGGERED",
            }
            worker.durable.history.rows = [{"record_id": "OUT-1", "payload": outcome}]
            worker.durable.outbox.rows = [{"record_id": "OUT-1", "payload": outcome}]
            before = len(calls)
            surface.sync()
            self.assertTrue(self._wait_for(lambda: len(calls) > before))
            self.assertEqual(calls[-1][0], "editMessageText")
            self.assertIn("Observation ACK: PENDING", calls[-1][1]["text"])

            # Repeated flat cycles while the same outcome is still pending are
            # not an operator event and must not re-edit the Telegram panel.
            before = len(calls)
            surface.sync()
            surface.sync()
            time.sleep(0.05)
            self.assertEqual(len(calls), before)

            worker.durable.outbox.rows = []
            before = len(calls)
            surface.sync()
            self.assertTrue(self._wait_for(lambda: len(calls) > before))
            self.assertEqual(calls[-1][0], "editMessageText")
            self.assertIn("Observation ACK: RECORDED", calls[-1][1]["text"])
            state = json.loads((root / "data/execution/paper/operator_state.json").read_text())
            self.assertIsNone(state["panel_message_id"])
            surface.stop()

    def test_live_paper_enable_cannot_bypass_dry_authority_but_disable_is_durable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sent = []

            def requester(method, payload, timeout):
                sent.append((method, dict(payload)))
                return {"ok": True, "result": {"message_id": 1}}

            worker = FakeWorker()
            surface = ExecutionOperatorSurface(
                repo_root=root,
                profile="live-paper",
                worker=worker,
                telegram=TelegramClient(TelegramConfig("token", "123", "456", 1.0), requester=requester),
                system_log=self._logger("test.operator.commands"),
                trade_log=self._logger("test.operator.commands.trade"),
                enable_policy=lambda: (False, "NON_PROMOTIONAL_DRY"),
            )
            surface.handle_command("/enable")
            self.assertEqual(worker.enable_calls, 0)
            surface.handle_command("/disable")
            self.assertEqual(worker.disable_calls, 1)
            self.assertTrue(operator_entries_blocked(root, "live-paper"))
            surface.stop()

    def test_log_paths_and_live_paper_systemd_env_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            exec_paths = execution_log_paths(root, "live-paper")
            self.assertEqual(exec_paths["execution"], root / "logs/execution/paper/execution.log")
            self.assertEqual(exec_paths["trades"], root / "logs/execution/paper/trades.log")
            obs = observation_log_paths(root)
            self.assertEqual(obs["collector"], root / "logs/observation/live/collector.log")
            # Render from a tiny copied source tree because the renderer requires the template.
            (root / "deploy/systemd").mkdir(parents=True)
            source = Path(__file__).resolve().parents[1] / "deploy/systemd/nbot-execution-live-paper.service.in"
            (root / "deploy/systemd/nbot-execution-live-paper.service.in").write_text(source.read_text())
            (root / ".venv/bin").mkdir(parents=True)
            python = root / ".venv/bin/python"
            python.write_text("#!/bin/sh\n")
            destination = root / "units"
            unit = render_live_paper_unit(repo=root, python=python, user="ubuntu", destination=destination)
            text = unit.read_text()
            self.assertIn("execution-live-paper.env", text)
            self.assertIn("control-link.env", text)
            self.assertIn("Restart=always", text)
            self.assertIn("--profile live-paper", text)


if __name__ == "__main__":
    unittest.main()
