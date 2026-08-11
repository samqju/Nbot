import unittest

from execution.binance_market_client import BinanceMarketClient
from observation.market_context import ObservationMarketContextProvider
from strategy.experiment_contract import build_experiment_context


class SilentLog:
    def debug(self, *_args, **_kwargs):
        pass


class FakeMarketClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def get_market_context_rows(self, *, symbols):
        self.calls += 1
        return {
            symbol: self.rows[symbol]
            for symbol in symbols
            if symbol in self.rows
        }


class Phase71MarketContextTests(unittest.TestCase):
    def test_provider_builds_btc_breadth_regime_and_liquidity(self):
        rows = {
            "BTCUSDT": {
                "price_change_pct_24h": 3.0,
                "spread_pct": 0.02,
                "quote_volume_usd": 1_000_000_000,
            },
            "ETHUSDT": {
                "price_change_pct_24h": 4.0,
                "spread_pct": 0.03,
                "quote_volume_usd": 500_000_000,
            },
            "SOLUSDT": {
                "price_change_pct_24h": 2.0,
                "spread_pct": 0.04,
                "quote_volume_usd": 200_000_000,
            },
            "XRPUSDT": {
                "price_change_pct_24h": -0.5,
                "spread_pct": 0.05,
                "quote_volume_usd": 100_000_000,
            },
            "ADAUSDT": {
                "price_change_pct_24h": 1.0,
                "spread_pct": 0.06,
                "quote_volume_usd": 50_000_000,
            },
        }
        client = FakeMarketClient(rows)
        snapshot = ObservationMarketContextProvider(
            market_client=client,
            system_log=SilentLog(),
        ).snapshot(symbols=rows, candle_bucket=123)

        self.assertEqual(client.calls, 1)
        self.assertEqual(snapshot["completeness"], "COMPLETE_PHASE7_1")
        self.assertEqual(snapshot["market_regime"], "BULLISH")
        self.assertEqual(snapshot["btc_regime"], "BULLISH")
        self.assertEqual(snapshot["volatility_regime"], "NORMAL")
        self.assertAlmostEqual(
            snapshot["market_breadth"]["advancing_fraction"],
            0.8,
        )
        self.assertEqual(
            snapshot["liquidity_by_symbol"]["SOLUSDT"]["spread_pct"],
            0.04,
        )


    def test_market_client_uses_two_bulk_public_reads(self):
        client = object.__new__(BinanceMarketClient)
        calls = []

        def public_get(path, params=None):
            calls.append((path, params))
            if path.endswith("/24hr"):
                return [
                    {
                        "symbol": "BTCUSDT",
                        "lastPrice": "100",
                        "priceChangePercent": "2.5",
                        "quoteVolume": "123456789",
                    },
                    {
                        "symbol": "ETHUSDT",
                        "lastPrice": "50",
                        "priceChangePercent": "-1.0",
                        "quoteVolume": "98765432",
                    },
                ]
            return [
                {"symbol": "BTCUSDT", "bidPrice": "99", "askPrice": "101"},
                {"symbol": "ETHUSDT", "bidPrice": "49.5", "askPrice": "50.5"},
            ]

        client._public_get = public_get
        rows = client.get_market_context_rows(
            symbols=["BTCUSDT", "ETHUSDT"]
        )
        self.assertEqual(
            [path for path, _ in calls],
            ["/fapi/v1/ticker/24hr", "/fapi/v1/ticker/bookTicker"],
        )
        self.assertEqual(rows["BTCUSDT"]["price_change_pct_24h"], 2.5)
        self.assertEqual(rows["BTCUSDT"]["quote_volume_usd"], 123456789.0)
        self.assertAlmostEqual(rows["BTCUSDT"]["spread_pct"], 2.0)

    def test_experiment_context_uses_broad_context_without_changing_symbol_structure(self):
        observed = {
            "completeness": "COMPLETE_PHASE7_1",
            "source": "BINANCE_BULK_24H_AND_BOOK_TICKER",
            "observed_at_ms": 123456789,
            "coverage": 1.0,
            "market_regime": "BEARISH",
            "trend_regime": "BEARISH",
            "volatility_regime": "HIGH",
            "btc_regime": "STRONG_BEARISH",
            "btc_change_pct_24h": -6.5,
            "market_breadth": {
                "coverage": 1.0,
                "advancing_fraction": 0.2,
                "declining_fraction": 0.8,
            },
            "liquidity_by_symbol": {
                "SOLUSDT": {
                    "spread_pct": 0.04,
                    "quote_volume_usd": 250_000_000,
                },
            },
        }
        context = build_experiment_context(
            decision_batch_id="batch-1",
            market_event_id="event-1",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=123,
            structure_fingerprint={
                "structure": "RANGE_BREAKOUT",
                "trend": "UP",
                "volatility": "NORMAL",
                "compression": False,
            },
            candidate_symbol="SOLUSDT",
            observed_market_context=observed,
            paper_taker_fee_rate=0.0005,
            paper_entry_slippage_pct=0.02,
            paper_exit_slippage_pct=0.02,
            virtual_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            virtual_target_r=2.0,
            virtual_max_candles=24,
            paper_variant_id="PAPER_TRAILING_SL_V1",
        )
        market = context["market_context"]
        self.assertEqual(market["schema_version"], 2)
        self.assertEqual(market["market_regime"], "BEARISH")
        self.assertEqual(market["btc_regime"], "STRONG_BEARISH")
        self.assertEqual(market["volatility_regime"], "HIGH")
        self.assertEqual(market["symbol_market_regime"], "RANGE_BREAKOUT")
        self.assertEqual(market["symbol_trend_regime"], "UP")
        self.assertEqual(market["liquidity"]["spread_pct"], 0.04)
        self.assertEqual(
            market["liquidity"]["quote_volume_usd"],
            250_000_000,
        )
        self.assertEqual(market["completeness"], "COMPLETE_PHASE7_1")

    def test_missing_candidate_liquidity_is_explicitly_partial(self):
        observed = {
            "completeness": "COMPLETE_PHASE7_1",
            "source": "BINANCE_BULK_24H_AND_BOOK_TICKER",
            "observed_at_ms": 123456789,
            "coverage": 1.0,
            "market_regime": "SIDEWAYS",
            "trend_regime": "SIDEWAYS",
            "volatility_regime": "LOW",
            "btc_regime": "SIDEWAYS",
            "market_breadth": {"coverage": 1.0},
            "liquidity_by_symbol": {},
        }
        context = build_experiment_context(
            decision_batch_id="batch-1",
            market_event_id="event-1",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=123,
            structure_fingerprint={"trend": "UP"},
            candidate_symbol="SOLUSDT",
            observed_market_context=observed,
            paper_taker_fee_rate=0.0005,
            paper_entry_slippage_pct=0.02,
            paper_exit_slippage_pct=0.02,
            virtual_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            virtual_target_r=2.0,
            virtual_max_candles=24,
            paper_variant_id="PAPER_TRAILING_SL_V1",
        )
        self.assertEqual(
            context["market_context"]["completeness"],
            "PARTIAL_PHASE7_1",
        )


if __name__ == "__main__":
    unittest.main()
