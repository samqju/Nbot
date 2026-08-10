import unittest
from unittest.mock import patch

from engine.daily_lifecycle import DailyLifecycle
from risk.risk import RiskManager
from workers.execution_worker import ExecutionWorker, TRADING_DISABLED


class Log:
    def __init__(self):
        self.rows = []

    def __getattr__(self, level):
        return lambda message, *args, **kwargs: self.rows.append(
            (level, str(message))
        )


class DailyState:
    def __init__(self, realized, peak):
        self.snapshot = {
            "daily_realized_pnl": realized,
            "daily_peak_pnl": peak,
        }
        self.floor = None

    def get_state(self):
        return dict(self.snapshot)

    def update_daily_loss_floor(self, value):
        self.floor = value

    def reset_daily(self, _day):
        pass

    def save(self):
        pass


class DailyExchange:
    def cancel_pending_entries(self):
        pass


class WorkerState:
    def __init__(self):
        self.state = {
            "engine_state": "RUNNING",
            "engine_halt_reason": None,
        }
        self.saved = 0

    def get_open_position(self):
        return None

    def get_state(self):
        return dict(self.state)

    def set_engine_state(self, value, reason=None):
        self.state["engine_state"] = value
        self.state["engine_halt_reason"] = reason

    def save(self):
        self.saved += 1


class Phase6PlanAuditSafetyCleanupTests(unittest.TestCase):
    def test_daily_loss_floor_breach_is_detected_without_halt_config_flag(self):
        risk = RiskManager(
            NOTIONAL_TARGET=1000.0,
            NOTIONAL_TOLERANCE_PCT=1.0,
            RISK_PER_TRADE_USD=10.0,
            RISK_TOLERANCE_PCT=10.0,
        )
        # Peak = +100R means only 3R giveback is allowed; +96R breaches +97R floor.
        state = DailyState(realized=960.0, peak=1000.0)
        log = Log()
        lifecycle = DailyLifecycle(
            state=state,
            risk=risk,
            exchange=DailyExchange(),
            system_log=log,
        )
        with self.assertRaisesRegex(RuntimeError, "DAILY_LOSS_FLOOR_BREACH"):
            lifecycle.handle(timestamp=1_800_000_000_000)
        self.assertEqual(state.floor, 970.0)
        self.assertTrue(any("DAILY_HALT" in row for _, row in log.rows))

    def test_execution_worker_fail_closes_after_daily_risk_halt(self):
        state = WorkerState()
        log = Log()
        worker = ExecutionWorker.__new__(ExecutionWorker)
        worker.state = state
        worker.system_log = log
        worker.control_loop_interval_seconds = 0.0
        worker._prepared = True
        worker.process_control_cycle = lambda: (_ for _ in ()).throw(
            RuntimeError(
                "DAILY_RISK_HALT | reason=DAILY_LOSS_FLOOR_BREACH"
            )
        )

        with patch("workers.execution_worker.send_critical"), patch(
            "workers.execution_worker.time.sleep",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                worker.run_forever()

        self.assertEqual(state.state["engine_state"], TRADING_DISABLED)
        self.assertIn("DAILY_RISK_HALT", state.state["engine_halt_reason"])
        self.assertGreaterEqual(state.saved, 1)

    def test_execution_lifecycles_cannot_trigger_observation_universe_reload(self):
        from pathlib import Path

        for filename in (
            "engine/position_lifecycle.py",
            "engine/reconciliation.py",
        ):
            source = Path(filename).read_text(encoding="utf-8")
            self.assertNotIn("self.universe", source)
            self.assertNotIn("maybe_reload", source)


if __name__ == "__main__":
    unittest.main()
