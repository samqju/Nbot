import unittest
from unittest.mock import Mock, patch

from communication.responses import TradeResponse
from test_phase6a0_7_failure_duplicate_safety import (
    FakeClient,
    FakePublisher,
    worker_for,
)


class State:
    def __init__(self, *, engine_state="RUNNING", open_position=None):
        self.open_position = open_position
        self.state = {
            "engine_state": engine_state,
            "engine_halt_reason": (
                "OPERATOR_DISABLE" if engine_state == "TRADING_DISABLED" else None
            ),
            "balance": 10000.0,
            "daily_realized_pnl": 12.5,
        }
        self.saved = 0
        self.heartbeats = []

    def get_open_position(self):
        return self.open_position

    def get_state(self):
        return dict(self.state)

    def set_engine_state(self, engine_state, reason=None):
        self.state["engine_state"] = engine_state
        self.state["engine_halt_reason"] = reason

    def save(self):
        self.saved += 1

    def heartbeat(self, now_ms):
        self.heartbeats.append(now_ms)


class OperatorDiagnosticsTests(unittest.TestCase):
    def _worker(self, state=None):
        response = TradeResponse.no_trade(
            request_id="fake-request",
            responded_at=1,
            reason="NONE",
        )
        return worker_for(
            state=state or State(),
            client=FakeClient(response),
            publisher=FakePublisher(),
        )

    def test_disable_command_sends_exactly_one_telegram_response(self):
        worker = self._worker(State(engine_state="RUNNING"))
        with patch("workers.execution_worker.send_info") as info, patch(
            "workers.execution_worker.send_critical"
        ) as critical:
            worker._handle_operator_command("/disable")

        info.assert_called_once()
        critical.assert_not_called()
        self.assertEqual(
            worker.state.get_state()["engine_state"],
            "TRADING_DISABLED",
        )

    def test_execution_command_is_on_demand_and_logs_one_snapshot(self):
        worker = self._worker()
        worker.execution_health.increment("control_cycles", 3)
        worker.execution_health.observe_ms("position_manage_ms", 1.25)

        with patch("workers.execution_worker.send_info") as info:
            worker._handle_operator_command("/execution")

        info.assert_called_once()
        title, body = info.call_args.args
        self.assertEqual(title, "EXECUTION HEALTH")
        self.assertIn("Control cycles: 3", body)
        self.assertIn("Manage avg/p95/max: 1.25", body)
        self.assertTrue(
            any(
                level == "info" and message.startswith("OPERATOR_EXECUTION_STATUS")
                for level, message in worker.system_log.messages
            )
        )

    def test_heartbeat_command_uses_cached_state_without_exchange_network_call(self):
        position = {
            "symbol": "BTCUSDT",
            "side": "LONG",
            "qty": 2.0,
            "entry_price": 100.0,
            "stop_loss": 95.0,
        }
        worker = self._worker(State(open_position=position))
        worker.market_state.update(symbol="BTCUSDT", price=101.0, timestamp=1)
        worker.exchange.get_last_price = Mock(
            side_effect=AssertionError("network price lookup not allowed")
        )

        with patch("workers.execution_worker.send_info") as info:
            worker._handle_operator_command("/heartbeat")

        info.assert_called_once()
        self.assertIn("Observed price: 101.0", info.call_args.args[1])
        worker.exchange.get_last_price.assert_not_called()
        self.assertTrue(
            any(
                level == "info" and message.startswith("OPERATOR_HEARTBEAT_STATUS")
                for level, message in worker.system_log.messages
            )
        )

    def test_pnl_prefix_is_not_treated_as_pnl_command(self):
        worker = self._worker()
        with patch(
            "workers.execution_worker.generate_daily_pnl_summary"
        ) as pnl, patch("workers.execution_worker.send_warning") as warning:
            worker._handle_operator_command("/pnlanything")

        pnl.assert_not_called()
        warning.assert_called_once()
        self.assertIn("UNKNOWN COMMAND", warning.call_args.args[0])

    def test_help_lists_only_active_split_execution_commands(self):
        worker = self._worker()
        with patch("workers.execution_worker.send_info") as info:
            worker._handle_operator_command("/help")

        body = info.call_args.args[1]
        for command in (
            "/status",
            "/execution",
            "/heartbeat",
            "/learning",
            "/pnl",
            "/enable",
            "/disable",
        ):
            self.assertIn(command, body)
        self.assertEqual(body.count("/learning"), 1)
        self.assertEqual(body.count("/disable"), 1)

    def test_disabled_startup_sends_one_warning_not_two_messages(self):
        worker = self._worker(State(engine_state="TRADING_DISABLED"))
        with patch("workers.execution_worker.send_warning") as warning, patch(
            "workers.execution_worker.send_info"
        ) as info:
            worker._notify_started()

        warning.assert_called_once()
        info.assert_not_called()
        self.assertTrue(
            any(
                level == "info" and message.startswith("EXECUTION_STARTED")
                for level, message in worker.system_log.messages
            )
        )


if __name__ == "__main__":
    unittest.main()
