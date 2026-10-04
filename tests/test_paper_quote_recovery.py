"""Regression tests for a public quote outage during paper position management."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import run_execution as runtime
from nbot.exchange.binance_public import BinanceLivePublicMarketData, BinanceLivePublicMarketError
from nbot.exchange.contracts import Quote

NOW = 1800000000000

class PaperQuoteRecoveryTests(unittest.TestCase):
    def run_quotes(self, quotes, *, stop_after=None, manage_error=None):
        with tempfile.TemporaryDirectory() as td:
            exchange, market, client, worker, operator = [MagicMock() for _ in range(5)]
            position = SimpleNamespace(symbol="MAGMAUSDT")
            worker.state.open_position = position
            worker.prepare.return_value = SimpleNamespace(status="POSITION_RECONCILED")
            exchange.quote.side_effect = quotes
            worker.process_open_quote.side_effect = manage_error
            handlers, sleeps = {}, []
            def register(signum, handler):
                handlers["stop"] = handler
            def sleep(seconds):
                sleeps.append(seconds)
                if len(sleeps) >= (stop_after or len(quotes)):
                    handlers["stop"](None, None)
            with patch.object(runtime, "build_live_paper_exchange", return_value=(exchange, market)), \
                 patch.object(runtime, "build_integrated_control_client", return_value=client), \
                 patch.object(runtime, "build_execution_worker", return_value=worker), \
                 patch.object(runtime, "_operator_surface", return_value=operator), \
                 patch.object(runtime.signal, "signal", side_effect=register), \
                 patch.object(runtime.time, "sleep", side_effect=sleep), \
                 patch.object(runtime.time, "monotonic", return_value=100):
                runtime.run_learned_paper_runtime(
                    repo_root=Path(td), environment={}, idle_poll_seconds=.1, open_poll_seconds=.1)
            self.assertIs(worker.state.open_position, position)
            worker.enable_new_entries.assert_not_called()
            worker.process_flat_cycle.assert_not_called()
            operator.runtime_error.assert_not_called()
            operator.start.assert_called_once()
            operator.stop.assert_called_once()
            market.disconnect.assert_called_once()
            return worker, operator, sleeps

    def test_repeated_stale_quotes_then_fresh_resume_without_restart(self):
        fresh = Quote("MAGMAUSDT", 1., 1.01, NOW)
        error = BinanceLivePublicMarketError("LIVE_PUBLIC_SOURCE_TIME_INVALID_OR_STALE")
        worker, operator, sleeps = self.run_quotes([error, error, fresh])
        worker.process_open_quote.assert_called_once_with(fresh)
        self.assertEqual(sleeps, [5., 5., .1])
        operator.system_log.warning.assert_called_once()
        operator.system_log.info.assert_called_once()

    def test_persistent_outage_keeps_position_and_can_stop(self):
        error = BinanceLivePublicMarketError("LIVE_PUBLIC_NETWORK_ERROR")
        worker, operator, sleeps = self.run_quotes([error] * 3)
        worker.process_open_quote.assert_not_called()
        self.assertEqual(sleeps, [5.] * 3)
        operator.system_log.warning.assert_called_once()
        operator.system_log.info.assert_not_called()

    def test_position_management_error_is_not_swallowed(self):
        with self.assertRaisesRegex(RuntimeError, "PERSIST_FAILED"):
            self.run_quotes([Quote("MAGMAUSDT", 1., 1.01, NOW)],
                            manage_error=RuntimeError("PERSIST_FAILED"))

    def test_unexpected_quote_bug_is_not_swallowed(self):
        with self.assertRaisesRegex(ValueError, "bug"):
            self.run_quotes([ValueError("bug")])

    def test_adapter_rejects_old_future_missing_and_invalid_timestamps(self):
        client = BinanceLivePublicMarketData(now_ms_fn=lambda: NOW)
        client._connected = True
        for timestamp in (NOW-5001, NOW+5001, None, "", 0, "bad"):
            with self.subTest(timestamp=timestamp), patch.object(client, "_get", return_value={
                "symbol": "MAGMAUSDT", "bidPrice": "1", "askPrice": "1.01", "time": timestamp}):
                with self.assertRaises(BinanceLivePublicMarketError):
                    client.quote("MAGMAUSDT")

    def test_adapter_retains_fresh_source_timestamp(self):
        client = BinanceLivePublicMarketData(now_ms_fn=lambda: NOW)
        client._connected = True
        with patch.object(client, "_get", return_value={
            "symbol": "MAGMAUSDT", "bidPrice": "1", "askPrice": "1.01", "time": NOW-50}):
            self.assertEqual(client.quote("MAGMAUSDT").timestamp_ms, NOW-50)
