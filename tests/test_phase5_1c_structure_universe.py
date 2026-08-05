import unittest

from strategy.universe_structure import UniverseStructureAnalyzer
import universe_selector


def candle(index, *, slope=0.2, width=1.0):
    close = 100.0 + index * slope
    return [
        index * 300000,
        close - 0.2,
        close + width / 2,
        close - width / 2,
        close,
        1000,
    ]


class Phase51CStructureAnalyzerTests(unittest.TestCase):
    def test_trending_candles_are_classified(self):
        candles = [
            candle(index, slope=0.15, width=1.0)
            for index in range(80)
        ]
        result = UniverseStructureAnalyzer().analyze(candles)
        self.assertIn("TRENDING_UP", result.regime)
        self.assertGreater(result.structure_score, 0)
        self.assertIn(result.category, {
            "TREND",
            "BREAKOUT",
            "REVERSION",
        })
        self.assertEqual(len(result.setup_readiness), 10)

    def test_compression_is_detected(self):
        candles = []
        for index in range(80):
            width = 2.0 if index < 65 else 0.35
            candles.append(
                candle(index, slope=0.01, width=width)
            )
        result = UniverseStructureAnalyzer().analyze(candles)
        self.assertIn("COMPRESSING", result.regime)
        self.assertGreater(
            result.features["compression_score"],
            0.5,
        )

    def test_insufficient_history_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "STRUCTURE_HISTORY_INSUFFICIENT",
        ):
            UniverseStructureAnalyzer().analyze(
                [candle(index) for index in range(20)]
            )


class Phase51CUniverseSelectionTests(unittest.TestCase):
    def test_diversification_caps_then_backfills(self):
        original_size = universe_selector.EXPECTED_SIZE
        original_limits = (
            universe_selector.STRUCTURE_UNIVERSE_MAX_TREND,
            universe_selector.STRUCTURE_UNIVERSE_MAX_BREAKOUT,
            universe_selector.STRUCTURE_UNIVERSE_MAX_REVERSION,
        )
        try:
            universe_selector.EXPECTED_SIZE = 6
            universe_selector.STRUCTURE_UNIVERSE_MAX_TREND = 2
            universe_selector.STRUCTURE_UNIVERSE_MAX_BREAKOUT = 2
            universe_selector.STRUCTURE_UNIVERSE_MAX_REVERSION = 2
            ranked = []
            categories = [
                "TREND", "TREND", "TREND",
                "BREAKOUT", "BREAKOUT",
                "REVERSION",
            ]
            for index, category in enumerate(categories):
                ranked.append({
                    "symbol": f"S{index}USDT",
                    "category": category,
                    "universe_score": 1.0 - index * 0.01,
                    "retained": False,
                })
            selected = universe_selector._select_diversified(
                ranked
            )
            self.assertEqual(len(selected), 6)
            self.assertEqual(
                sum(
                    row["category"] == "TREND"
                    and row["selection_reason"]
                    != "DIVERSITY_BACKFILL"
                    for row in selected
                ),
                2,
            )
        finally:
            universe_selector.EXPECTED_SIZE = original_size
            (
                universe_selector.STRUCTURE_UNIVERSE_MAX_TREND,
                universe_selector.STRUCTURE_UNIVERSE_MAX_BREAKOUT,
                universe_selector.STRUCTURE_UNIVERSE_MAX_REVERSION,
            ) = original_limits

    def test_symbol_sanitization(self):
        self.assertTrue(
            universe_selector._valid_symbol("BTCUSDT")
        )
        self.assertFalse(
            universe_selector._valid_symbol("../BTCUSDT")
        )
        self.assertFalse(
            universe_selector._valid_symbol("BTC USDT")
        )


if __name__ == "__main__":
    unittest.main()
