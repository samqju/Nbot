import logging
import tempfile
import unittest
from pathlib import Path

from execution.paper_account import PaperAccount
from state.state import StateManager
from utils.execution_health import ExecutionHealthMonitor
from utils.logger import restrict_info_to_prefixes


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


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append((record.levelname, record.getMessage()))


class ExecutionHealthMonitorTests(unittest.TestCase):
    def test_health_is_retained_on_demand_without_periodic_logging(self):
        log = Log()
        monitor = ExecutionHealthMonitor(system_log=log)
        monitor.increment("total_ticks", 10)
        monitor.increment("position_symbol_ticks", 2)
        monitor.observe_ms("internal_tick_age_ms", 3.0)
        monitor.observe_ms("internal_tick_age_ms", 7.0)
        monitor.observe_ms("position_manage_ms", 2.5)

        monitor.maybe_log(position_symbol="BTCUSDT")
        self.assertEqual(log.infos, [])

        snapshot = monitor.snapshot(position_symbol="BTCUSDT")
        self.assertEqual(snapshot["position_symbol"], "BTCUSDT")
        self.assertEqual(snapshot["counters"]["total_ticks"], 10)
        self.assertEqual(snapshot["counters"]["position_symbol_ticks"], 2)
        self.assertEqual(
            snapshot["timings"]["internal_tick_age_ms"]["count"],
            2,
        )
        self.assertEqual(
            snapshot["timings"]["internal_tick_age_ms"]["avg"],
            5.0,
        )
        self.assertEqual(
            snapshot["timings"]["internal_tick_age_ms"]["max"],
            7.0,
        )

    def test_execution_log_filter_keeps_only_approved_info_and_warnings(self):
        logger = logging.Logger("phase6a-test")
        logger.setLevel(logging.DEBUG)
        handler = ListHandler()
        logger.addHandler(handler)
        restrict_info_to_prefixes(
            logger,
            (
                "EXECUTION_STARTED",
                "OPERATOR_",
                "PUBLIC_POSITION_WS_RECOVERED",
                "POSITION_OPENED",
                "SL_UPDATE_ATTEMPT",
                "SL_UPDATE_VERIFIED",
                "POSITION_CLOSED_CONFIRMED",
                "POSITION_CLOSE_DETAILS",
            ),
        )

        logger.info("NOISY_ROUTINE_INFO")
        logger.debug("NOISY_DEBUG")
        logger.info("EXECUTION_STARTED | position=FLAT")
        logger.info("OPERATOR_EXECUTION_STATUS | position=FLAT")
        logger.info("POSITION_OPENED | symbol=BTCUSDT")
        logger.info("SL_UPDATE_ATTEMPT | symbol=BTCUSDT")
        logger.info("SL_UPDATE_VERIFIED | symbol=BTCUSDT")
        logger.info("POSITION_CLOSED_CONFIRMED")
        logger.info("POSITION_CLOSE_DETAILS | symbol=BTCUSDT")
        logger.warning("REAL_WARNING")
        logger.error("REAL_ERROR")

        self.assertEqual(
            handler.messages,
            [
                ("INFO", "EXECUTION_STARTED | position=FLAT"),
                ("INFO", "OPERATOR_EXECUTION_STATUS | position=FLAT"),
                ("INFO", "POSITION_OPENED | symbol=BTCUSDT"),
                ("INFO", "SL_UPDATE_ATTEMPT | symbol=BTCUSDT"),
                ("INFO", "SL_UPDATE_VERIFIED | symbol=BTCUSDT"),
                ("INFO", "POSITION_CLOSED_CONFIRMED"),
                ("INFO", "POSITION_CLOSE_DETAILS | symbol=BTCUSDT"),
                ("WARNING", "REAL_WARNING"),
                ("ERROR", "REAL_ERROR"),
            ],
        )

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
