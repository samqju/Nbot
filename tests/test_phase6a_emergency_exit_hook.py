import unittest
from types import SimpleNamespace
from unittest.mock import patch

from workers.execution_worker import ExecutionWorker


class _Log:
    def __init__(self):
        self.messages = []

    def __getattr__(self, level):
        def record(message, *args, **kwargs):
            self.messages.append((level, str(message)))
        return record


class _State:
    def __init__(self, *, engine_state="TRADING_DISABLED", open_position=None):
        self.engine_state = engine_state
        self.open_position = open_position

    def get_state(self):
        return {"engine_state": self.engine_state}

    def get_open_position(self):
        return self.open_position


class _Exchange:
    def __init__(self, position):
        self.position = position

    def get_position(self):
        return self.position


class _Emergency:
    def __init__(self, exchange):
        self.exchange = exchange
        self.reasons = []

    def execute(self, reason):
        self.reasons.append(reason)
        self.exchange.position = None


def _worker(*, engine_state="TRADING_DISABLED", open_position=None):
    worker = ExecutionWorker.__new__(ExecutionWorker)
    exchange_position = (
        SimpleNamespace(symbol=open_position["symbol"])
        if open_position is not None
        else None
    )
    worker.state = _State(
        engine_state=engine_state,
        open_position=open_position,
    )
    worker.exchange = _Exchange(exchange_position)
    worker.emergency = _Emergency(worker.exchange)
    worker.system_log = _Log()
    return worker


class EmergencyExitTestHookTests(unittest.TestCase):
    def test_shadow_disabled_open_position_runs_emergency_handler(self):
        worker = _worker(open_position={"symbol": "BTCUSDT"})
        with patch("workers.execution_worker.TRADING_ENV", "LIVE"), patch(
            "workers.execution_worker.EXECUTION_MODE", "SHADOW"
        ):
            worker._run_emergency_exit_test()

        self.assertEqual(
            worker.emergency.reasons,
            ["PHASE6A_EMERGENCY_EXIT_TEST:BTCUSDT"],
        )
        self.assertIsNone(worker.exchange.get_position())
        messages = "\n".join(message for _, message in worker.system_log.messages)
        self.assertIn("EMERGENCY_EXIT_TEST_REQUESTED", messages)
        self.assertIn("EMERGENCY_EXIT_TEST_CONFIRMED_FLAT", messages)

    def test_live_trade_is_forbidden(self):
        worker = _worker(open_position={"symbol": "BTCUSDT"})
        with patch("workers.execution_worker.TRADING_ENV", "LIVE"), patch(
            "workers.execution_worker.EXECUTION_MODE", "TRADE"
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "EMERGENCY_EXIT_TEST_FORBIDDEN_IN_LIVE_TRADE",
            ):
                worker._run_emergency_exit_test()

    def test_requires_trading_disabled(self):
        worker = _worker(
            engine_state="RUNNING",
            open_position={"symbol": "BTCUSDT"},
        )
        with patch("workers.execution_worker.TRADING_ENV", "LIVE"), patch(
            "workers.execution_worker.EXECUTION_MODE", "SHADOW"
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "EMERGENCY_EXIT_TEST_REQUIRES_TRADING_DISABLED",
            ):
                worker._run_emergency_exit_test()

    def test_requires_open_position(self):
        worker = _worker(open_position=None)
        with patch("workers.execution_worker.TRADING_ENV", "LIVE"), patch(
            "workers.execution_worker.EXECUTION_MODE", "SHADOW"
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "EMERGENCY_EXIT_TEST_REQUIRES_OPEN_POSITION",
            ):
                worker._run_emergency_exit_test()


if __name__ == "__main__":
    unittest.main()
