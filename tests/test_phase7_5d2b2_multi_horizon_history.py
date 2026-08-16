import importlib
import os
import unittest
from unittest.mock import Mock, patch

from observation.research_history import MultiHorizonResearchHistoryProvider


def bar(open_ms, close_ms, close=100.0, quote_volume=1_000_000.0):
    return {
        "open_time_ms": open_ms,
        "close_time_ms": close_ms,
        "open": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "close": close,
        "base_volume": 10.0,
        "quote_volume": quote_volume,
        "trade_count": 50,
    }


class FakeMarketClient:
    def __init__(self, rows_by_interval):
        self.rows_by_interval = rows_by_interval
        self.calls = []

    def get_historical_research_bars(self, *, symbol, interval, limit, end_time_ms):
        self.calls.append((symbol, interval, limit, end_time_ms))
        rows = [
            row for row in self.rows_by_interval[interval]
            if row["close_time_ms"] < end_time_ms
        ]
        return rows[-limit:]


class OpenBarFilteringFakeMarketClient:
    """Simulate Binance returning an open bar that the public client removes."""

    def __init__(self, rows_by_interval):
        self.rows_by_interval = rows_by_interval
        self.calls = []

    def get_historical_research_bars(self, *, symbol, interval, limit, end_time_ms):
        self.calls.append((symbol, interval, limit, end_time_ms))
        raw = [
            row for row in self.rows_by_interval[interval]
            if row["open_time_ms"] < end_time_ms
        ][-limit:]
        return [
            row for row in raw
            if row["close_time_ms"] < end_time_ms
        ]


class Phase75D2B2MultiHorizonHistoryTests(unittest.TestCase):
    def test_provider_paginates_backward_and_returns_only_closed_history(self):
        as_of = 10_000_000
        hourly = [bar(i * 1000 + 1, i * 1000 + 999) for i in range(1, 401)]
        daily = [bar(i * 5000 + 1, i * 5000 + 4999) for i in range(1, 61)]
        client = FakeMarketClient({"1h": hourly, "1d": daily})

        provider = MultiHorizonResearchHistoryProvider(
            market_client=client,
            hourly_required_bars=200,
            daily_required_bars=40,
            max_klines_per_request=75,
        )
        snapshot = provider.snapshot(symbol="btcusdt", as_of_ms=as_of)

        self.assertEqual(snapshot.symbol, "BTCUSDT")
        self.assertEqual(len(snapshot.hourly_bars), 200)
        self.assertEqual(len(snapshot.daily_bars), 40)
        self.assertTrue(all(row["close_time_ms"] < as_of for row in snapshot.hourly_bars))
        self.assertGreater(len([c for c in client.calls if c[1] == "1h"]), 1)

    def test_provider_continues_after_open_bar_filter_underfills_page(self):
        # The newest raw page contains one still-open row. The public market
        # client removes it, so the provider receives limit-1 rows even though
        # older history still exists. Pagination must continue backward.
        as_of = 500_500
        hourly = [bar(i * 1000 + 1, i * 1000 + 999) for i in range(1, 501)]
        daily = [bar(i * 5000 + 1, i * 5000 + 4999) for i in range(1, 101)]
        client = OpenBarFilteringFakeMarketClient({"1h": hourly, "1d": daily})

        snapshot = MultiHorizonResearchHistoryProvider(
            market_client=client,
            hourly_required_bars=200,
            daily_required_bars=40,
            max_klines_per_request=100,
        ).snapshot(symbol="BTCUSDT", as_of_ms=as_of)

        self.assertEqual(len(snapshot.hourly_bars), 200)
        self.assertEqual(len(snapshot.daily_bars), 40)
        self.assertEqual(snapshot.completeness, "COMPLETE_PHASE7_5D2B2")
        self.assertGreater(len([c for c in client.calls if c[1] == "1h"]), 2)

    def test_provider_marks_initial_benchmark_families_ready(self):
        as_of = 100_000_000
        hourly = [bar(i * 1000 + 1, i * 1000 + 999) for i in range(1, 250)]
        daily = [bar(i * 5000 + 1, i * 5000 + 4999) for i in range(1, 80)]
        client = FakeMarketClient({"1h": hourly, "1d": daily})

        snapshot = MultiHorizonResearchHistoryProvider(
            market_client=client,
            hourly_required_bars=200,
            daily_required_bars=40,
        ).snapshot(symbol="ETHUSDT", as_of_ms=as_of)

        self.assertTrue(snapshot.cross_sectional_ready)
        self.assertTrue(snapshot.time_series_momentum_ready)
        self.assertTrue(snapshot.intraday_ready)
        self.assertEqual(snapshot.completeness, "COMPLETE_PHASE7_5D2B2")

    def test_strategy_ready_does_not_mean_full_b2_history_complete(self):
        as_of = 100_000_000
        hourly = [bar(i * 1000 + 1, i * 1000 + 999) for i in range(1, 190)]
        daily = [bar(i * 5000 + 1, i * 5000 + 4999) for i in range(1, 36)]
        client = FakeMarketClient({"1h": hourly, "1d": daily})

        snapshot = MultiHorizonResearchHistoryProvider(
            market_client=client,
            hourly_required_bars=200,
            daily_required_bars=40,
        ).snapshot(symbol="NEWUSDT", as_of_ms=as_of)

        self.assertTrue(snapshot.cross_sectional_ready)
        self.assertTrue(snapshot.time_series_momentum_ready)
        self.assertTrue(snapshot.intraday_ready)
        self.assertEqual(len(snapshot.hourly_bars), 189)
        self.assertEqual(len(snapshot.daily_bars), 35)
        self.assertEqual(snapshot.completeness, "PARTIAL_PHASE7_5D2B2")

    def test_zero_recent_quote_volume_blocks_cross_sectional_readiness(self):
        as_of = 100_000_000
        hourly = [bar(i * 1000 + 1, i * 1000 + 999) for i in range(1, 250)]
        daily = [bar(i * 5000 + 1, i * 5000 + 4999) for i in range(1, 80)]
        daily[-1] = {**daily[-1], "quote_volume": 0.0}
        client = FakeMarketClient({"1h": hourly, "1d": daily})

        snapshot = MultiHorizonResearchHistoryProvider(
            market_client=client,
            hourly_required_bars=200,
            daily_required_bars=40,
        ).snapshot(symbol="ETHUSDT", as_of_ms=as_of)

        self.assertFalse(snapshot.cross_sectional_ready)
        self.assertEqual(snapshot.completeness, "PARTIAL_PHASE7_5D2B2")

    def test_public_client_exposes_quote_volume_and_respects_as_of(self):
        env = patch.dict(
            os.environ,
            {
                "TRADING_ENV": "LIVE",
                "EXECUTION_MODE": "SHADOW",
                "LIVE_BASE_URL": "https://fapi.binance.com",
                "LIVE_MARKET_WS_URL": "wss://fstream.binance.com/market/ws/!ticker@arr",
            },
            clear=False,
        )
        env.start()
        try:
            import config
            import execution.binance_market_client as module
            importlib.reload(config)
            module = importlib.reload(module)
            client = module.BinanceMarketClient(system_log=Mock())
            client._public_get = Mock(return_value=[
                [1, "100", "110", "90", "105", "12", 999, "1250", 7],
                [1000, "105", "111", "100", "108", "9", 2000, "1000", 5],
            ])

            rows = client.get_historical_research_bars(
                symbol="BTCUSDT",
                interval="1h",
                limit=2,
                end_time_ms=1500,
            )

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["quote_volume"], 1250.0)
            self.assertEqual(rows[0]["trade_count"], 7)
            params = client._public_get.call_args.args[1]
            self.assertEqual(params["endTime"], 1499)
        finally:
            env.stop()

    def test_public_client_rejects_request_over_binance_page_limit(self):
        env = patch.dict(
            os.environ,
            {
                "TRADING_ENV": "LIVE",
                "EXECUTION_MODE": "SHADOW",
                "LIVE_BASE_URL": "https://fapi.binance.com",
                "LIVE_MARKET_WS_URL": "wss://fstream.binance.com/market/ws/!ticker@arr",
            },
            clear=False,
        )
        env.start()
        try:
            import config
            import execution.binance_market_client as module
            importlib.reload(config)
            module = importlib.reload(module)
            client = module.BinanceMarketClient(system_log=Mock())
            with self.assertRaisesRegex(ValueError, "RESEARCH_KLINE_LIMIT_INVALID"):
                client.get_historical_research_bars(
                    symbol="BTCUSDT", interval="1h", limit=1501
                )
        finally:
            env.stop()


if __name__ == "__main__":
    unittest.main()
