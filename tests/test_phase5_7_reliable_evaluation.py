import json
import tempfile
import unittest
from pathlib import Path

from learning.reliable_evaluation import ReliableEvaluationEngine
from learning.time_split import TimeAwareDatasetSplitter


class Phase57ReliableEvaluationTests(unittest.TestCase):
    @staticmethod
    def _dataset_row(
        index,
        *,
        net_r=0.2,
        event_id=None,
        variant_id="VARIANT_A",
        direction="LONG",
        pattern="RANGE_BREAKOUT",
        trend="UP",
        volatility="HIGH",
        recorded_offset=100,
        btc_regime=None,
        spread=None,
        quote_volume=None,
    ):
        observed = index * 1000
        return {
            "dataset_schema_version": 3,
            "experiment_contract_version": 1,
            "candidate_observation_id": f"candidate-{index}",
            "decision_batch_id": f"batch-{index}",
            "market_event_id": event_id or f"event-{index}",
            "strategy_version": "STRUCTURE_RULES_V1",
            "strategy_variant_id": "STRUCTURE_CANDIDATE_GENERATOR_V1",
            "model_version": "RULE_SYSTEM_V1",
            "outcome_variant_id": variant_id,
            "observed_at_ms": observed,
            "recorded_at_ms": observed + recorded_offset,
            "symbol": "BTCUSDT",
            "direction": direction,
            "pattern": pattern,
            "outcome_type": "VIRTUAL_STRATEGY_VARIANT",
            "target_r": net_r,
            "label_profitable": net_r > 0,
            "strategy_lab_catalog_version": "PHASE5_6_APPROVED_V1",
            "strategy_lab": {
                "variant": {"family": "BREAKOUT"},
            },
            "market_context": {
                "market_regime": "BREAKOUT",
                "trend_regime": trend,
                "volatility_regime": volatility,
                "btc_regime": btc_regime,
                "liquidity": {
                    "spread_pct": spread,
                    "quote_volume_usd": quote_volume,
                },
            },
        }

    @staticmethod
    def _write(path, rows):
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )

    def _evaluate(self, root, rows, **overrides):
        root = Path(root)
        dataset = root / "dataset.jsonl"
        report = root / "reliable.json"
        self._write(dataset, rows)
        arguments = {
            "dataset_path": str(dataset),
            "report_path": str(report),
            "catalog_version": "PHASE5_6_APPROVED_V1",
            "train_ratio": 0.50,
            "validation_ratio": 0.25,
            "test_ratio": 0.25,
            "embargo_seconds": 0,
            "walk_forward_folds": 2,
            "min_outcomes": 8,
            "min_market_events": 8,
            "min_holdout_events": 2,
            "min_regime_events": 2,
            "min_avg_net_r": 0.02,
            "min_positive_fold_ratio": 0.50,
            "max_drawdown_r": 30,
            "liquid_max_spread_pct": 0.15,
            "liquid_min_quote_volume_usd": 15_000_000,
        }
        arguments.update(overrides)
        return ReliableEvaluationEngine(**arguments).evaluate()

    def test_time_split_purges_label_window_crossing_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            rows = []
            for index in range(10):
                recorded_offset = 100
                if index == 5:
                    # Candidate 5 belongs to raw train, but its label uses
                    # data after candidate 6 starts validation.
                    recorded_offset = 2_000
                rows.append({
                    "candidate_observation_id": f"candidate-{index}",
                    "observed_at_ms": index * 1000,
                    "recorded_at_ms": index * 1000 + recorded_offset,
                    "symbol": "BTCUSDT",
                    "direction": "LONG",
                    "pattern": "RANGE_BREAKOUT",
                    "outcome_type": "VIRTUAL_TRADE",
                    "features": {},
                    "label_profitable": True,
                })
            dataset = root / "dataset.jsonl"
            self._write(dataset, rows)
            report = TimeAwareDatasetSplitter(
                dataset_path=str(dataset),
                train_path=str(root / "train.jsonl"),
                validation_path=str(root / "validation.jsonl"),
                test_path=str(root / "test.jsonl"),
                report_path=str(root / "report.json"),
                train_ratio=0.60,
                validation_ratio=0.20,
                test_ratio=0.20,
                embargo_seconds=0,
            ).split()
            self.assertEqual(
                report["purging"]["candidate_groups_excluded"],
                1,
            )
            self.assertFalse(
                report["leakage_checks"]["label_window_overlap"]
            )

    def test_market_event_grouping_counts_one_correlated_event(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [
                self._dataset_row(0, event_id="event-a", net_r=1.0),
                self._dataset_row(1, event_id="event-a", net_r=-0.5),
                self._dataset_row(2, event_id="event-b", net_r=0.5),
                self._dataset_row(3, event_id="event-b", net_r=0.5),
            ]
            report = self._evaluate(
                root,
                rows,
                min_outcomes=4,
                min_market_events=2,
                min_holdout_events=1,
                min_regime_events=1,
                walk_forward_folds=1,
            )
            variant = report["variants"]["VARIANT_A"]
            self.assertEqual(variant["raw"]["count"], 4)
            self.assertEqual(
                variant["market_event_grouped"]["count"],
                2,
            )

    def test_fixed_split_purges_overlapping_event_window(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [self._dataset_row(i) for i in range(12)]
            # Raw train ends at index 5; validation begins at index 6.
            rows[5]["recorded_at_ms"] = rows[6]["observed_at_ms"] + 1
            report = self._evaluate(root, rows)
            split = report["variants"]["VARIANT_A"][
                "fixed_chronological_split"
            ]
            self.assertEqual(split["purging"]["events_excluded"], 1)
            self.assertLess(
                split["train"]["last_recorded_at_ms"],
                split["boundaries"]["validation_start_ms"],
            )

    def test_walk_forward_uses_expanding_chronological_windows(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [self._dataset_row(i, net_r=0.2) for i in range(20)]
            report = self._evaluate(root, rows)
            walk = report["variants"]["VARIANT_A"]["walk_forward"]
            self.assertEqual(walk["completed_folds"], 2)
            first, second = walk["folds"]
            self.assertLess(first["train"]["count"], second["train"]["count"])
            self.assertTrue(first["chronological"])
            self.assertTrue(second["chronological"])

    def test_regime_report_marks_missing_btc_and_liquidity_as_unavailable(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [
                self._dataset_row(
                    i,
                    direction="LONG" if i % 2 == 0 else "SHORT",
                    trend="UP" if i < 10 else "DOWN",
                    volatility="HIGH" if i % 3 else "LOW",
                )
                for i in range(20)
            ]
            report = self._evaluate(root, rows)
            regimes = report["variants"]["VARIANT_A"]["regimes"]
            self.assertEqual(regimes["btc_regime"]["status"], "NOT_AVAILABLE")
            self.assertEqual(regimes["liquidity"]["status"], "NOT_AVAILABLE")
            self.assertIn("LONG", regimes["trade_direction"]["groups"])
            self.assertIn("SHORT", regimes["trade_direction"]["groups"])
            self.assertIn("BULLISH", regimes["market_direction"]["groups"])
            self.assertIn("BEARISH", regimes["market_direction"]["groups"])

    def test_positive_stable_variant_becomes_shadow_eligible_only(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [self._dataset_row(i, net_r=0.2) for i in range(20)]
            report = self._evaluate(root, rows)
            variant = report["variants"]["VARIANT_A"]
            self.assertEqual(variant["verdict"], "SHADOW_ELIGIBLE")
            self.assertTrue(variant["authority"]["paper_verdicts_blocked"])
            self.assertEqual(
                report["maximum_automatic_verdict"],
                "SHADOW_ELIGIBLE",
            )
            self.assertEqual(
                report["recommended_variant"],
                "VARIANT_A",
            )

    def test_negative_untouched_test_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [
                self._dataset_row(i, net_r=(0.3 if i < 15 else -0.5))
                for i in range(20)
            ]
            report = self._evaluate(root, rows)
            variant = report["variants"]["VARIANT_A"]
            self.assertEqual(variant["verdict"], "REJECT")
            self.assertIn(
                "UNTOUCHED_TEST_EXPECTANCY_NON_POSITIVE",
                variant["reason_codes"],
            )
            self.assertTrue(variant["plain_english"])

    def test_positive_but_weak_variant_is_offline_validated(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [self._dataset_row(i, net_r=0.05) for i in range(20)]
            report = self._evaluate(
                root,
                rows,
                min_avg_net_r=0.10,
            )
            variant = report["variants"]["VARIANT_A"]
            self.assertEqual(variant["verdict"], "OFFLINE_VALIDATED")
            self.assertIn(
                "UNTOUCHED_TEST_EXPECTANCY_BELOW_SHADOW_GATE",
                variant["reason_codes"],
            )

    def test_insufficient_sample_requests_more_data_and_lists_all_verdicts(self):
        with tempfile.TemporaryDirectory() as root:
            rows = [self._dataset_row(i) for i in range(4)]
            report = self._evaluate(root, rows)
            variant = report["variants"]["VARIANT_A"]
            self.assertEqual(variant["verdict"], "COLLECT_MORE_DATA")
            supported = report["verdict_definitions"]["supported"]
            self.assertIn("PAPER_CANARY_ELIGIBLE", supported)
            self.assertIn("PAPER_CHAMPION_ELIGIBLE", supported)
            self.assertIn(
                "PAPER_CANARY_ELIGIBLE",
                report["verdict_definitions"]["reserved_for_later_phases"],
            )


if __name__ == "__main__":
    unittest.main()
