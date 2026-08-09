import tempfile
import unittest
from pathlib import Path

from execution.paper_account import PaperAccount
from state.state import StateManager
from utils.execution_health import ExecutionHealthMonitor


class Log:
    def __init__(self):
        self.infos = []

    def info(self, message):
        self.infos.append(message)


class MonitorProbe:
    def __init__(self):
        self.values = []

    def observe_ms(self, name, value):
        self.values.append((name, float(value)))


class ExecutionHealthMonitorTests(unittest.TestCase):
    def test_periodic_summary_aggregates_without_per_tick_logging(self):
        log = Log()
        monitor = ExecutionHealthMonitor(
            system_log=log,
            interval_seconds=5.0,
        )
        monitor.increment("total_ticks", 10)
        monitor.increment("position_symbol_ticks", 2)
        monitor.observe_ms("internal_tick_age_ms", 3.0)
        monitor.observe_ms("internal_tick_age_ms", 7.0)
        monitor.observe_ms("position_manage_ms", 2.5)

        monitor.maybe_log(position_symbol="BTCUSDT")
        self.assertEqual(log.infos, [])

        monitor._last_log -= 5.1
        monitor._period_started -= 5.1
        monitor.maybe_log(position_symbol="BTCUSDT")

        self.assertEqual(len(log.infos), 1)
        line = log.infos[0]
        self.assertIn("EXECUTION_HEALTH", line)
        self.assertIn("position_symbol=BTCUSDT", line)
        self.assertIn("total_ticks=10", line)
        self.assertIn("position_symbol_ticks=2", line)
        self.assertIn("internal_tick_age_ms_count=2", line)
        self.assertIn("internal_tick_age_ms_avg=5.000", line)
        self.assertIn("internal_tick_age_ms_max=7.000", line)
        self.assertIn("position_manage_ms_count=1", line)

    def test_state_save_reports_timing_without_changing_state_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = StateManager(str(Path(tmp) / "state.json"))
            probe = MonitorProbe()
            state.execution_health_monitor = probe
            state.save()

            self.assertTrue(Path(state.filename).exists())
            self.assertTrue(
                any(name == "bot_state_save_ms" for name, _ in probe.values)
            )

    def test_paper_state_fsync_reports_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            account = PaperAccount(
                starting_balance_usd=10_000.0,
                state_path=str(Path(tmp) / "paper.json"),
                trades_path=str(Path(tmp) / "trades.jsonl"),
                source="PAPER_TESTNET",
            )
            probe = MonitorProbe()
            account.execution_health_monitor = probe
            account.load_or_create()

            self.assertTrue(
                any(name == "paper_state_save_ms" for name, _ in probe.values)
            )


if __name__ == "__main__":
    unittest.main()
