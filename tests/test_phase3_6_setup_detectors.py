import unittest

from strategy.setup_detectors import SetupDetectorRegistry


class Phase36SetupDetectorTests(unittest.TestCase):
    def test_registry_declares_all_requested_detectors(self):
        self.assertEqual(
            set(SetupDetectorRegistry.DETECTOR_NAMES),
            {
                "PULLBACK_CONTINUATION",
                "MEAN_REVERSION",
                "FAKE_BREAKOUT",
                "LIQUIDITY_SWEEP",
                "SUPPORT_BOUNCE",
                "RESISTANCE_REJECTION",
                "MOMENTUM_EXHAUSTION",
                "TRIANGLE_BREAKOUT",
                "RANGE_BREAKOUT",
                "TREND_REVERSAL",
            },
        )

    def test_range_breakout_long_is_detected(self):
        candles = []
        for idx in range(30):
            base = 100.0 + (idx % 3) * 0.1
            candles.append((base, 101.0, 99.0, 100.0))
        candles[-1] = (100.0, 103.0, 99.8, 102.5)
        signals = SetupDetectorRegistry().detect_all(candles)
        self.assertTrue(
            any(
                s.pattern == "RANGE_BREAKOUT"
                and s.direction == "LONG"
                for s in signals
            )
        )

    def test_fake_breakout_short_is_detected(self):
        candles = [(100.0, 101.0, 99.0, 100.0) for _ in range(30)]
        candles[-1] = (100.5, 102.0, 99.8, 100.2)
        signals = SetupDetectorRegistry().detect_all(candles)
        self.assertTrue(
            any(
                s.pattern == "FAKE_BREAKOUT"
                and s.direction == "SHORT"
                for s in signals
            )
        )


if __name__ == "__main__":
    unittest.main()
