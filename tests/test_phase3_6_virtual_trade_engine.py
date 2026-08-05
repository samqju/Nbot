import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from strategy.candidate import StrategyCandidate
from strategy.candidate_risk import CandidateRiskPlan
from strategy.features import CandidateFeatures
from strategy.virtual_trade_engine import VirtualTradeEngine


class Phase36VirtualTradeTests(unittest.TestCase):
    def _candidate(self, root, direction="LONG"):
        features = CandidateFeatures(
            0.01, 0.02, 7, 0.4, 0.6, 0.5, -0.01, 0.03, 4
        )
        risk = CandidateRiskPlan(
            risk_budget_usd=10,
            reference_price=100,
            stop_distance_pct=1,
            stop_distance_price=1,
            suggested_stop_price=99 if direction == "LONG" else 101,
            suggested_quantity=10,
            suggested_notional_usd=1000,
            required_margin_usd=200,
            risk_efficiency=1,
            capped_by="NOTIONAL",
        )
        return StrategyCandidate(
            "BTCUSDT",
            direction,
            0.8,
            "RANGE_BREAKOUT",
            1,
            features,
            reference_price=100,
            risk_plan=risk,
        )

    def test_all_candidates_can_be_enrolled_in_parallel(self):
        with tempfile.TemporaryDirectory() as root:
            env = {
                "VIRTUAL_TRADES_PATH": str(Path(root) / "virtual.jsonl"),
                "VIRTUAL_TRADE_MAX_ACTIVE": "500",
                "VIRTUAL_TRADE_MAX_CANDLES": "24",
                "VIRTUAL_TRADE_TARGET_R": "2",
            }
            with patch.dict("os.environ", env):
                engine = VirtualTradeEngine()
            first = self._candidate(root, "LONG")
            second = self._candidate(root, "SHORT")
            self.assertEqual(engine.enroll_all([first, second]), 2)
            self.assertEqual(engine.active_count(), 2)

    def test_long_target_closes_at_positive_r(self):
        with tempfile.TemporaryDirectory() as root:
            import strategy.virtual_trade_engine as module
            old_path = module.VIRTUAL_TRADES_PATH
            module.VIRTUAL_TRADES_PATH = str(Path(root) / "virtual.jsonl")
            try:
                engine = VirtualTradeEngine()
                candidate = self._candidate(root, "LONG")
                engine.enroll(candidate)
                results = engine.on_candle(
                    "BTCUSDT",
                    (100, 102.1, 99.5, 101.5),
                )
                self.assertEqual(len(results), 1)
                self.assertEqual(results[0]["exit_reason"], "TARGET")
                self.assertEqual(results[0]["exit_r"], 2.0)
            finally:
                module.VIRTUAL_TRADES_PATH = old_path


if __name__ == "__main__":
    unittest.main()
