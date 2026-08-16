import json
import tempfile
import unittest
from pathlib import Path

from learning.ensemble_experiment import FEATURE_NAMES
from learning.ranking_walk_forward import (
    OfflineWalkForwardRankingValidator,
    WALK_FORWARD_PHASE,
    WALK_FORWARD_POLICY,
)


class Phase75D2WalkForwardRankingTests(unittest.TestCase):
    @staticmethod
    def _context():
        return {
            "completeness": "COMPLETE_PHASE7_1",
            "market_regime": "SIDEWAYS",
            "volatility_regime": "NORMAL",
            "btc_regime": "SIDEWAYS",
            "btc_change_pct_24h": 0.0,
            "context_coverage": 1.0,
            "market_breadth": {
                "advancing_fraction": 0.5,
                "declining_fraction": 0.5,
                "unchanged_fraction": 0.0,
                "median_change_pct_24h": 0.0,
                "median_abs_change_pct_24h": 2.0,
                "coverage": 1.0,
            },
            "liquidity": {
                "spread_pct": 0.02,
                "quote_volume_usd": 100_000_000.0,
            },
        }

    @classmethod
    def _row(cls, event, choice, *, target_r, signal, final_score, eligible=True):
        features = {
            name: 0.1 + index * 0.01
            for index, name in enumerate(FEATURE_NAMES)
        }
        features["dist_low"] = float(signal)
        return {
            "candidate_observation_id": f"candidate-{event}-{choice}",
            "market_event_id": f"event-{event:04d}",
            "observed_at_ms": 1_700_000_000_000 + event * 300_000,
            "recorded_at_ms": 1_700_000_100_000 + event * 300_000,
            "outcome_type": "VIRTUAL_TRADE",
            "execution_eligible": eligible,
            "symbol": f"SYM{choice}USDT",
            "direction": "LONG",
            "pattern": "MEAN_REVERSION" if choice else "RANGE_BREAKOUT",
            "rule_score": float(final_score),
            "final_score": float(final_score),
            "features": features,
            "market_context": cls._context(),
            "label_profitable": target_r > 0,
            "target_r": float(target_r),
        }

    @classmethod
    def _dataset(cls, path, *, late_reversal=False):
        rows = []
        for event in range(100):
            reversal = late_reversal and event >= 90
            if reversal:
                candidate0_r, candidate1_r = +1.5, -1.0
                candidate0_signal, candidate1_signal = 1.0, 0.0
            else:
                candidate0_r, candidate1_r = -1.0, +1.5
                candidate0_signal, candidate1_signal = 0.0, 1.0
            rows.extend([
                cls._row(
                    event,
                    0,
                    target_r=candidate0_r,
                    signal=candidate0_signal,
                    final_score=0.90,
                ),
                cls._row(
                    event,
                    1,
                    target_r=candidate1_r,
                    signal=candidate1_signal,
                    final_score=0.40,
                ),
                cls._row(
                    event,
                    2,
                    target_r=+1.0,
                    signal=0.5,
                    final_score=0.10,
                    eligible=False,
                ),
            ])
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def _run(self, root, *, late_reversal=False):
        dataset = root / "dataset.jsonl"
        report_path = root / "report.json"
        self._dataset(dataset, late_reversal=late_reversal)
        report = OfflineWalkForwardRankingValidator(
            dataset_path=dataset,
            report_path=report_path,
            fold_count=5,
            initial_train_fraction=0.50,
            min_positive_folds=5,
            min_train_rows=20,
            min_eval_rows=10,
            min_train_events=10,
            min_eval_events=5,
            ridge_alpha=10.0,
            context_aware=True,
            embargo_seconds=0,
        ).run()
        return report, json.loads(report_path.read_text())

    def test_stable_future_lift_passes_all_walk_forward_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, persisted = self._run(Path(tmp), late_reversal=False)
        self.assertEqual(report["phase"], WALK_FORWARD_PHASE)
        self.assertEqual(report["validation_policy"], WALK_FORWARD_POLICY)
        self.assertEqual(report["status"], "VALIDATION_COMPLETE")
        self.assertEqual(len(report["folds"]), 5)
        self.assertEqual(report["aggregate"]["positive_champion_lift_folds"], 5)
        self.assertGreater(report["aggregate"]["weighted_paired_average_r_lift"], 0.0)
        self.assertTrue(report["walk_forward_passed"])
        self.assertEqual(report["research_readiness"], "READY_FOR_FRESH_VALIDATION_DESIGN")
        self.assertEqual(persisted["research_readiness"], report["research_readiness"])

    def test_late_reversal_fails_repeated_champion_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, _persisted = self._run(Path(tmp), late_reversal=True)
        self.assertEqual(report["status"], "VALIDATION_COMPLETE")
        self.assertLess(report["aggregate"]["positive_champion_lift_folds"], 5)
        self.assertFalse(report["checks"]["positive_champion_lift_folds"]["passed"])
        self.assertFalse(report["walk_forward_passed"])
        self.assertEqual(report["research_readiness"], "NOT_READY")

    def test_future_only_pattern_does_not_enter_earlier_fold_vocabulary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            self._dataset(dataset, late_reversal=False)
            rows = [json.loads(line) for line in dataset.read_text().splitlines()]
            for row in rows:
                if row["observed_at_ms"] >= 1_700_000_000_000 + 90 * 300_000:
                    row["pattern"] = "FUTURE_ONLY_PATTERN"
            dataset.write_text("".join(json.dumps(row) + "\n" for row in rows))
            report = OfflineWalkForwardRankingValidator(
                dataset_path=dataset,
                report_path=root / "report.json",
                fold_count=5,
                initial_train_fraction=0.50,
                min_positive_folds=5,
                min_train_rows=20,
                min_eval_rows=10,
                min_train_events=10,
                min_eval_events=5,
                embargo_seconds=0,
            ).run()
        self.assertNotIn("FUTURE_ONLY_PATTERN", report["folds"][0]["pattern_categories"])
        self.assertNotIn("FUTURE_ONLY_PATTERN", report["folds"][1]["pattern_categories"])
        self.assertNotIn("FUTURE_ONLY_PATTERN", report["folds"][2]["pattern_categories"])
        self.assertNotIn("FUTURE_ONLY_PATTERN", report["folds"][3]["pattern_categories"])
        self.assertNotIn("FUTURE_ONLY_PATTERN", report["folds"][4]["pattern_categories"])

    def test_validator_never_grants_runtime_or_capital_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, _persisted = self._run(Path(tmp), late_reversal=False)
        self.assertTrue(report["research_only"])
        self.assertEqual(report["runtime_activation"], "DISABLED")
        self.assertEqual(report["paper_authority"], "UNCHANGED")
        self.assertFalse(report["paper_promotion_allowed"])
        self.assertFalse(report["promotion_eligible"])
        self.assertEqual(report["real_order_authority"], "NONE")
        self.assertFalse(report["selected_using_future_fold_data"])

    def test_embargo_purges_training_events_near_future_fold(self):
        validator = OfflineWalkForwardRankingValidator(
            dataset_path="unused.jsonl",
            report_path="unused-report.json",
            embargo_seconds=6,
        )
        train_events = [
            (1_000, "event-old", []),
            (5_000, "event-near", []),
        ]
        eval_events = [(10_000, "event-future", [])]
        kept, purged = validator._apply_embargo(train_events, eval_events)
        self.assertEqual([event[1] for event in kept], ["event-old"])
        self.assertEqual(purged, 1)

    def test_invalid_walk_forward_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            self._dataset(dataset)
            with self.assertRaisesRegex(ValueError, "FOLD_COUNT"):
                OfflineWalkForwardRankingValidator(
                    dataset_path=dataset,
                    report_path=root / "report.json",
                    fold_count=1,
                )


if __name__ == "__main__":
    unittest.main()
