"""Regression tests for WSS-first paper position management and REST recovery."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import run_execution as runtime
from nbot.exchange.binance_public import BinanceLivePublicMarketData, BinanceLivePublicMarketError
from nbot.exchange.binance_stream import BinanceLiveStreamError, QuoteUpdate
from nbot.exchange.contracts import Quote

NOW = 1800000000000


class PaperQuoteRecoveryTests(unittest.TestCase):
    def test_open_position_prefers_fresh_wss_quote(self):
        exchange = MagicMock()
        quote = Quote("MAGMAUSDT", 1.0, 1.01, NOW)
        exchange.wait_quote.return_value = QuoteUpdate(7, quote, NOW)
        seq, result, source = runtime._next_live_open_quote(
            exchange, "MAGMAUSDT", 6, .1
        )
        self.assertEqual(seq, 7)
        self.assertEqual(result, quote)
        self.assertEqual(source, "WSS")
        exchange.recovery_quote.assert_not_called()

    def test_wss_timeout_uses_explicit_rest_recovery_only_for_open_position_path(self):
        exchange = MagicMock()
        exchange.wait_quote.side_effect = BinanceLiveStreamError("NO_FRESH_BOOK_TICKER")
        recovered = Quote("MAGMAUSDT", .99, 1.02, NOW)
        exchange.recovery_quote.return_value = recovered
        seq, result, source = runtime._next_live_open_quote(
            exchange, "MAGMAUSDT", 4, .1
        )
        self.assertEqual(seq, 4)
        self.assertEqual(result, recovered)
        self.assertEqual(source, "REST_RECOVERY")
        exchange.recovery_quote.assert_called_once_with("MAGMAUSDT")

    def test_total_market_outage_keeps_paper_position_without_stale_tick(self):
        with tempfile.TemporaryDirectory() as td:
            exchange, market, client, worker, operator = [MagicMock() for _ in range(5)]
            position = SimpleNamespace(symbol="MAGMAUSDT")
            worker.state.open_position = position
            worker.prepare.return_value = SimpleNamespace(status="POSITION_RECONCILED")
            worker.state.snapshot.entries_enabled = False
            exchange.wait_quote.side_effect = BinanceLiveStreamError("WSS_DOWN")
            exchange.recovery_quote.side_effect = BinanceLivePublicMarketError("REST_DOWN")
            handlers = {}

            def register(_signum, handler):
                handlers["stop"] = handler

            def sleep(_seconds):
                handlers["stop"](None, None)

            with patch.object(runtime, "build_live_paper_exchange", return_value=(exchange, market)), \
                 patch.object(runtime, "build_integrated_control_client", return_value=client), \
                 patch.object(runtime, "build_execution_worker", return_value=worker), \
                 patch.object(runtime, "_operator_surface", return_value=operator), \
                 patch.object(runtime.signal, "signal", side_effect=register), \
                 patch.object(runtime.time, "sleep", side_effect=sleep), \
                 patch.object(runtime.time, "monotonic", return_value=100):
                result = runtime.run_learned_paper_runtime(
                    repo_root=Path(td), environment={},
                    idle_poll_seconds=.1, open_poll_seconds=.1,
                )

            self.assertEqual(result, 0)
            self.assertIs(worker.state.open_position, position)
            worker.process_open_quote.assert_not_called()
            worker.process_flat_cycle.assert_not_called()
            operator.runtime_error.assert_not_called()
            operator.system_log.warning.assert_called_once()
            market.disconnect.assert_called_once()

    def test_unexpected_market_bug_is_not_swallowed(self):
        exchange = MagicMock()
        exchange.wait_quote.side_effect = ValueError("bug")
        with self.assertRaisesRegex(ValueError, "bug"):
            runtime._next_live_open_quote(exchange, "MAGMAUSDT", 0, .1)

    def test_rest_adapter_rejects_old_future_missing_and_invalid_timestamps(self):
        client = BinanceLivePublicMarketData(now_ms_fn=lambda: NOW)
        client._connected = True
        for timestamp in (NOW-5001, NOW+5001, None, "", 0, "bad"):
            with self.subTest(timestamp=timestamp), patch.object(client, "_get", return_value={
                "symbol": "MAGMAUSDT", "bidPrice": "1", "askPrice": "1.01", "time": timestamp
            }):
                with self.assertRaises(BinanceLivePublicMarketError):
                    client.quote("MAGMAUSDT")

    def test_rest_adapter_retains_fresh_source_timestamp(self):
        client = BinanceLivePublicMarketData(now_ms_fn=lambda: NOW)
        client._connected = True
        with patch.object(client, "_get", return_value={
            "symbol": "MAGMAUSDT", "bidPrice": "1", "askPrice": "1.01", "time": NOW-50
        }):
            self.assertEqual(client.quote("MAGMAUSDT").timestamp_ms, NOW-50)


if __name__ == "__main__":
    unittest.main()
