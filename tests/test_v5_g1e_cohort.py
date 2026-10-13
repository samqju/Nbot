"""G1e 50-market WSS/REST cohort and bounded reconnect safety tests."""
import asyncio
import json
import time
import unittest
from unittest.mock import patch

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.live_cohort_probe import run_probe, _get_96
from nbot.v5.reconnect_policy import ReconnectPolicy, FeedRecoveryHold
from nbot.v5.candle_ledger import EvidenceHold
from tests.test_v5_public_market import exchange, ticker, klines


class ReconnectPolicyTests(unittest.TestCase):
    def test_source_generations_do_not_auto_certify(self):
        state = ReconnectPolicy()
        self.assertEqual(state.on_connect("market"), 1)
        with self.assertRaises(FeedRecoveryHold):
            state.on_connect("market")
        state.record_gap("TRADE", "BTCUSDT")
        state.record_gap("CANDLE", "BTCUSDT")
        state.on_disconnect("market")
        self.assertEqual(state.retry_delay("market"), 2)
        self.assertEqual(state.on_connect("market"), 2)
        state.candle_reconciled("BTCUSDT")
        status = state.status()
        self.assertEqual(status["routes"]["market"]["generation"], 2)
        self.assertFalse(status["research_ready"])
        self.assertTrue(status["routes"]["market"]["reconciliation_required"])
        self.assertIn("BTCUSDT", status["trade_gap_symbols"])
        self.assertNotIn("BTCUSDT", status["candle_gap_symbols"])
        self.assertEqual(status["order_authority"], "NONE")

    def test_bounded_retry_policy_never_busy_loops(self):
        state = ReconnectPolicy()
        self.assertEqual(
            [state.retry_delay("public") for _ in range(3)], [2, 5, 12],
        )
        with self.assertRaisesRegex(FeedRecoveryHold, "RETRY_BUDGET"):
            state.retry_delay("public")
        with self.assertRaises(FeedRecoveryHold):
            state.on_connect("unknown")

    def test_reconnect_never_repairs_sticky_trade_gaps(self):
        state = ReconnectPolicy()
        state.on_connect("market")
        state.record_gap("TRADE", "ETHUSDT")
        for _ in range(2):
            state.on_disconnect("market")
            state.retry_delay("market")
            state.on_connect("market")
        self.assertIn("ETHUSDT", state.status()["trade_gap_symbols"])
        self.assertFalse(state.status()["research_ready"])


class FiftyMarketProofTests(unittest.TestCase):
    def test_rest_query_uses_exact_closed_event_96_window(self):
        found = []
        event = INTERVAL_MS * 1_000_000
        def get(path, params=None):
            found.append((path, params))
            return klines(event)
        result = _get_96("BTCUSDT", event, get)
        self.assertEqual(len(result), 96)
        self.assertEqual(found[0][0], "/fapi/v1/klines")
        self.assertEqual(found[0][1]["endTime"],
                         str(event + INTERVAL_MS - 1))
        self.assertEqual(found[0][1]["limit"], "96")

    def test_invalid_limits_and_duration_fail_before_network(self):
        for top,seconds in ((0, 335), (51, 335), (50, 40),
                            (50, 999), (True, 200)):
            with self.subTest(args=(top,seconds)), self.assertRaises(EvidenceHold):
                asyncio.run(run_probe(top=top, seconds=seconds,
                                      getter=lambda *a: self.fail("no network")))

    def _fake(self, *, skip_last=False, mismatch=False):
        # Construct a consistent real-format REST snapshot around the current
        # wall-clock event, then inject mock final WSS closes for every coin.
        now_ms = int(time.time()*1000)
        event = (now_ms//INTERVAL_MS - 1)*INTERVAL_MS
        calls = {}
        def get(path, params=None):
            if path == "/fapi/v1/time":
                return {"serverTime": now_ms}
            if path == "/fapi/v1/exchangeInfo":
                return exchange()
            if path == "/fapi/v1/ticker/24hr":
                return ticker()
            assert path == "/fapi/v1/klines"
            s = params["symbol"]
            calls[s] = calls.get(s,0)+1
            end_ms = int(params["endTime"])
            last_open = end_ms-INTERVAL_MS+1
            rows = klines(last_open)
            if mismatch and s=="BTCUSDT" and calls[s] == 2:
                rows[-1][4] = "100.75"
            return rows

        async def fake_listen(route,url,collector,policy,deadline,reached,faults,target):
            policy.on_connect(route)
            collector.connect(route)
            if route == "market":
                selected = collector.symbols[:-1] if skip_last else collector.symbols
                for symbol in selected:
                    data = json.dumps({
                        "stream": symbol.lower()+"@kline_5m",
                        "data": {
                            "e": "kline", "E": target+INTERVAL_MS+10, "s": symbol,
                            "k": {"t": target, "T": target+INTERVAL_MS-1,
                                  "s": symbol, "i": "5m", "x": True,
                                  "o": "100", "h": "101", "l": "99",
                                  "c": "100", "v": "10"},
                        },
                    })
                    collector.consume("market", data,
                                      received_ms=target+INTERVAL_MS+1000)
            collector.disconnect(route)
            policy.on_disconnect(route)

        with patch("nbot.v5.live_cohort_probe._listen",
                   side_effect=fake_listen):
            return asyncio.run(run_probe(top=50, seconds=110, getter=get))

    def test_50_market_synthetic_cross_source_exact_match_and_reopen(self):
        report = self._fake()
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["selected_symbol_count"], 50)
        self.assertEqual(report["rest_bootstrap_96_count"], 50)
        self.assertEqual(report["wss_final_symbol_count"], 50)
        self.assertEqual(report["cross_source_rest_match_count"], 50)
        self.assertEqual(report["sqlite_reopened_97_count"], 50)
        self.assertTrue(report["temporary_database_removed"])
        self.assertFalse(report["research_ready"])
        self.assertEqual(report["training_labels_created"], 0)
        self.assertEqual(report["order_authority"], "NONE")

    def test_missing_one_final_fails_whole_cohort(self):
        report = self._fake(skip_last=True)
        self.assertEqual(report["result"], "HOLD")
        self.assertEqual(report["wss_final_symbol_count"], 49)
        self.assertEqual(len(report["final_missing_symbols"]), 1)
        self.assertEqual(report["cross_source_rest_match_count"], 0)
        self.assertFalse(report["research_ready"])

    def test_single_rest_mismatch_holds_entire_cohort(self):
        report = self._fake(mismatch=True)
        self.assertEqual(report["result"], "HOLD")
        self.assertTrue(any("BTCUSDT" in x for x in report["cross_source_mismatch"]))
        self.assertLess(report["cross_source_rest_match_count"], 50)
        self.assertFalse(report["research_ready"])


if __name__ == "__main__":
    unittest.main()
