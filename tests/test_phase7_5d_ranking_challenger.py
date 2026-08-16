import json
import pickle
import tempfile
import unittest
from pathlib import Path

from learning.ensemble_experiment import FEATURE_NAMES
from learning.ranking_challenger import (
    OfflineRankingChallengerExperiment,
    RANKING_CHAMPION_BASELINE,
    RANKING_MODEL_FAMILY,
    RANKING_POPULATION,
    RANKING_TARGET,
)


class Phase75DRankingChallengerTests(unittest.TestCase):
    @staticmethod
    def _context(*, bullish=True):
        return {
            "completeness": "COMPLETE_PHASE7_1",
            "market_regime": "BULLISH" if bullish else "BEARISH",
            "volatility_regime": "NORMAL",
            "btc_regime": "SIDEWAYS",
            "btc_change_pct_24h": 1.0 if bullish else -1.0,
            "context_coverage": 1.0,
            "market_breadth": {
                "advancing_fraction": 0.65 if bullish else 0.35,
                "declining_fraction": 0.35 if bullish else 0.65,
                "unchanged_fraction": 0.0,
                "median_change_pct_24h": 1.0 if bullish else -1.0,
                "median_abs_change_pct_24h": 2.0,
                "coverage": 1.0,
            },
            "liquidity": {
                "spread_pct": 0.02,
                "quote_volume_usd": 100_000_000.0,
            },
        }

    @classmethod
    def _row(
        cls,
        event,
        choice,
        *,
        target_r,
        signal,
        final_score,
        eligible=True,
        direction="LONG",
    ):
        features = {
            name: 0.1 + index * 0.01
            for index, name in enumerate(FEATURE_NAMES)
        }
        features["dist_low"] = float(signal)
        return {
            "candidate_observation_id": f"candidate-{event}-{choice}",
            "market_event_id": f"event-{event}",
            "observed_at_ms": 1_700_000_000_000 + event * 300_000,
            "recorded_at_ms": 1_700_000_100_000 + event * 300_000,
            "outcome_type": "VIRTUAL_TRADE",
            "execution_eligible": eligible,
            "symbol": f"SYM{choice}USDT",
            "direction": direction,
            "pattern": "MEAN_REVERSION" if choice else "RANGE_BREAKOUT",
            "rule_score": float(final_score),
            "final_score": float(final_score),
            "features": features,
            "market_context": cls._context(bullish=(event % 2 == 0)),
            "label_profitable": target_r > 0,
            "target_r": float(target_r),
        }

    @classmethod
    def _events(cls, start, count, *, include_ineligible=False):
        rows = []
        for event in range(start, start + count):
            # Candidate 1 is consistently better in R but RULE_SYSTEM_V1's
            # final_score deliberately prefers candidate 0.
            rows.append(
                cls._row(
                    event,
                    0,
                    target_r=-1.0,
                    signal=-1.0,
                    final_score=0.9,
                    direction="SHORT",
                )
            )
            rows.append(
                cls._row(
                    event,
                    1,
                    target_r=1.5,
                    signal=1.0,
                    final_score=0.4,
                    direction="LONG",
                )
            )
            if include_ineligible:
                rows.append(
                    cls._row(
                        event,
                        2,
                        target_r=9.0,
                        signal=9.0,
                        final_score=1.0,
                        eligible=False,
                    )
                )
        return rows

    @staticmethod
    def _write(path, rows):
        Path(path).write_text("".join(json.dumps(row) + "\n" for row in rows))

    def _run(self, root, *, include_ineligible=False):
        root = Path(root)
        self._write(root / "train.jsonl", self._events(0, 30, include_ineligible=include_ineligible))
        self._write(root / "validation.jsonl", self._events(100, 12, include_ineligible=include_ineligible))
        self._write(root / "test.jsonl", self._events(200, 12, include_ineligible=include_ineligible))
        return OfflineRankingChallengerExperiment(
            train_path=root / "train.jsonl",
            validation_path=root / "validation.jsonl",
            test_path=root / "test.jsonl",
            artifact_path=root / "ranking.pkl",
            report_path=root / "ranking.json",
            min_train_rows=20,
            min_eval_rows=10,
            min_train_events=10,
            min_eval_events=5,
            ridge_alpha=10.0,
            context_aware=True,
            evaluate_test=True,
        ).run()

    def test_ranking_challenger_learns_relative_r_and_beats_rule_baseline(self):
        with tempfile.TemporaryDirectory() as root:
            report = self._run(root)
            self.assertEqual(report["status"], "EXPERIMENT_COMPLETE")
            self.assertEqual(report["model_family"], RANKING_MODEL_FAMILY)
            self.assertEqual(report["target_definition"], RANKING_TARGET)
            self.assertEqual(report["training_population"], RANKING_POPULATION)
            self.assertEqual(report["champion_baseline"], RANKING_CHAMPION_BASELINE)
            for split in ("validation", "test"):
                metrics = report["evaluation"][split]
                self.assertEqual(metrics["events"], 12)
                self.assertGreater(metrics["paired_average_r_lift"], 2.0)
                self.assertGreater(metrics["ranking_average_r"], 1.0)
                self.assertLess(metrics["rule_average_r"], 0.0)

    def test_execution_ineligible_rows_are_excluded_from_training_and_evaluation(self):
        with tempfile.TemporaryDirectory() as root:
            report = self._run(root, include_ineligible=True)
            self.assertEqual(report["rows"]["train"], 60)
            self.assertEqual(report["rows"]["validation"], 24)
            self.assertEqual(report["rows"]["test"], 24)
            self.assertEqual(report["issues"]["train_execution_ineligible_excluded"], 30)
            self.assertEqual(report["issues"]["validation_execution_ineligible_excluded"], 12)
            self.assertEqual(report["issues"]["test_execution_ineligible_excluded"], 12)

    def test_artifact_is_research_only_and_has_zero_authority(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            report = self._run(root)
            artifact = pickle.loads((root / "ranking.pkl").read_bytes())
            self.assertTrue(report["research_only"])
            self.assertTrue(artifact["research_only"])
            self.assertEqual(artifact["runtime_activation"], "DISABLED")
            self.assertEqual(artifact["paper_authority"], "UNCHANGED")
            self.assertFalse(artifact["paper_promotion_allowed"])
            self.assertEqual(artifact["real_order_authority"], "NONE")
            self.assertFalse(artifact["selected_using_test_data"])
            self.assertTrue(artifact["direction_interactions"])

    def test_insufficient_independent_events_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            self._write(root / "train.jsonl", self._events(0, 3))
            self._write(root / "validation.jsonl", self._events(100, 2))
            self._write(root / "test.jsonl", self._events(200, 2))
            report = OfflineRankingChallengerExperiment(
                train_path=root / "train.jsonl",
                validation_path=root / "validation.jsonl",
                test_path=root / "test.jsonl",
                artifact_path=root / "ranking.pkl",
                report_path=root / "ranking.json",
                min_train_rows=1,
                min_eval_rows=1,
                min_train_events=10,
                min_eval_events=5,
            ).run()
            self.assertEqual(report["status"], "INSUFFICIENT_DATA")
            self.assertFalse((root / "ranking.pkl").exists())


if __name__ == "__main__":
    unittest.main()
