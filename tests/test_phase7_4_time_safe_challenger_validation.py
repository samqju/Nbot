import json
import pickle
import tempfile
import unittest
from pathlib import Path

from learning.baseline_trainer import BaselineModelTrainer
from learning.ensemble_experiment import OfflineEnsembleExperiment
from learning.time_split import TimeAwareDatasetSplitter
from learning.training_orchestrator import AutomaticTrainingOrchestrator
from strategy.experiment_contract import build_experiment_context, experiment_projection
from strategy.features import CANDIDATE_FEATURE_NAMES


class Phase74TimeSafeChallengerValidationTests(unittest.TestCase):

    @staticmethod
    def _features(label):
        values = {
            "short_range": 0.01 if label else 0.02,
            "long_range": 0.02 if label else 0.03,
            "trend_score": 10.0 if label else -10.0,
            "wick_ratio_recent": 0.1 if label else 0.9,
            "body_ratio_recent": 0.9 if label else 0.1,
            "range_acceleration": 1.2 if label else 0.8,
            "dist_high": -0.01 if label else 0.03,
            "dist_low": 0.03 if label else -0.01,
            "directional_consistency": 8.0 if label else -8.0,
        }
        return {name: values[name] for name in CANDIDATE_FEATURE_NAMES}

    def _orchestrator(self, root, *, count=80, **overrides):
        root = Path(root)
        observations_path = root / "observations.jsonl"
        outcomes_path = root / "outcomes.jsonl"
        observations, outcomes = [], []
        base = 1_700_000_000_000
        for index in range(count):
            label = bool(index % 2)
            observed_at_ms = base + index * 600_000
            context = build_experiment_context(
                decision_batch_id=f"batch-{index}",
                market_event_id=f"event-{index}",
                strategy_version="STRUCTURE_RULES_V1",
                strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
                selection_model_version="RULE_SYSTEM_V1",
                environment="LIVE",
                execution_mode="SHADOW",
                candle_bucket=index,
                structure_fingerprint={
                    "structure": "RANGE_BREAKOUT",
                    "trend": "UP" if label else "DOWN",
                    "volatility": "NORMAL",
                    "compression": False,
                },
                candidate_symbol="BTCUSDT",
                observed_market_context={
                    "schema_version": 1,
                    "source": "TEST",
                    "observed_at_ms": observed_at_ms,
                    "candle_bucket": index,
                    "coverage": 1.0,
                    "market_regime": "BULLISH" if label else "BEARISH",
                    "trend_regime": "BULLISH" if label else "BEARISH",
                    "volatility_regime": "NORMAL",
                    "btc_regime": "BULLISH" if label else "BEARISH",
                    "btc_change_pct_24h": 2.0 if label else -2.0,
                    "market_breadth": {
                        "symbols_expected": 200,
                        "symbols_observed": 200,
                        "coverage": 1.0,
                        "advancing_fraction": 0.7 if label else 0.3,
                        "declining_fraction": 0.3 if label else 0.7,
                        "unchanged_fraction": 0.0,
                        "median_change_pct_24h": 2.0 if label else -2.0,
                        "median_abs_change_pct_24h": 3.0,
                    },
                    "liquidity_by_symbol": {
                        "BTCUSDT": {
                            "spread_pct": 0.01,
                            "quote_volume_usd": 1_000_000_000.0,
                        }
                    },
                    "completeness": "COMPLETE_PHASE7_1",
                },
                paper_taker_fee_rate=0.0005,
                paper_entry_slippage_pct=0.02,
                paper_exit_slippage_pct=0.02,
                virtual_variant_id="VIRTUAL_FIXED_2R_24C_V1",
                virtual_target_r=2.0,
                virtual_max_candles=24,
                paper_variant_id="PAPER_TRAILING_SL_V1",
            )
            projection = experiment_projection(context)
            candidate_id = f"candidate-{index}"
            observations.append({
                "schema_version": 3, **projection,
                "observation_type": "STRATEGY_CANDIDATE",
                "observed_at_ms": observed_at_ms,
                "environment": "LIVE", "execution_mode": "SHADOW",
                "candidate_observation_id": candidate_id,
                "symbol": "BTCUSDT",
                "direction": "LONG" if label else "SHORT",
                "pattern": "RANGE_BREAKOUT", "bucket": index,
                "rule_score": 0.8 if label else 0.2,
                "final_score": 0.8 if label else 0.2,
                "score_breakdown": None,
                "reference_price": 100.0,
                "risk_plan": None,
                "rank": 1,
                "selected": True,
                "execution_eligible": True,
                "selection_status": "SELECTED_FOR_EXECUTION",
                "rejection_reason": None,
                "eligible_for_training": True,
                "features": self._features(label),
                "structure_fingerprint": {"structure": "RANGE_BREAKOUT"},
                "market_context": context["market_context"],
                "cost_model": context["cost_model"],
                "virtual_policy": context["virtual_policy"],
                "paper_policy": context["paper_policy"],
                "experiment_context": context,
            })
            outcomes.append({
                "schema_version": 2, **projection,
                "observation_type": "CANDIDATE_OUTCOME",
                "recorded_at_ms": observed_at_ms + 300_000,
                "environment": "LIVE", "execution_mode": "SHADOW",
                "candidate_observation_id": candidate_id,
                "outcome_type": "VIRTUAL_TRADE",
                "symbol": "BTCUSDT",
                "direction": "LONG" if label else "SHORT",
                "outcome_variant_id": "VIRTUAL_FIXED_2R_24C_V1",
                "experiment_context": context,
                "payload": {
                    "exit_r": 2.0 if label else -1.0,
                    "net_exit_r": 2.0 if label else -1.0,
                    "profitable": label,
                    "cost_breakdown": {
                        "spread_r": 0.01, "funding_r": 0.0,
                        "total_cost_r": 0.05,
                        "cost_completeness": "FEES_SLIPPAGE_SPREAD_FUNDING_COMPLETE_PHASE7_3",
                    },
                },
            })
        observations_path.write_text("".join(json.dumps(r)+"\n" for r in observations))
        outcomes_path.write_text("".join(json.dumps(r)+"\n" for r in outcomes))
        args = {
            "enabled": True, "environment": "LIVE",
            "observations_path": str(observations_path),
            "outcomes_path": str(outcomes_path),
            "snapshot_root": str(root / "snapshots"),
            "model_root": str(root / "models"),
            "registry_path": str(root / "registry.json"),
            "status_path": str(root / "status.json"),
            "lock_path": str(root / "training.lock"),
            "outcome_type": "VIRTUAL_TRADE",
            "default_parent_model_id": "RULE_SYSTEM_V1",
            "min_new_outcomes": 40, "min_new_market_events": 40,
            "train_ratio": 0.60, "validation_ratio": 0.20, "test_ratio": 0.20,
            "embargo_seconds": 0,
            "baseline_min_train_rows": 20, "baseline_min_eval_rows": 5,
            "ensemble_min_train_rows": 20, "ensemble_min_eval_rows": 5,
            "random_state": 42, "calibration_bins": 5, "drift_bins": 5,
            "min_roc_auc": 0.0, "max_brier_score": 1.0,
            "max_calibration_gap": 1.0, "max_feature_psi": 10.0,
        }
        args.update(overrides)
        return AutomaticTrainingOrchestrator(**args)
    @staticmethod
    def _row(candidate_id, event_id, observed_at_ms, label):
        return {
            "candidate_observation_id": candidate_id,
            "market_event_id": event_id,
            "observed_at_ms": observed_at_ms,
            "recorded_at_ms": observed_at_ms + 1000,
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "pattern": "RANGE_BREAKOUT",
            "outcome_type": "VIRTUAL_TRADE",
            "features": {
                "short_range": 0.01,
                "long_range": 0.02,
                "trend_score": 1.0 if label else -1.0,
                "wick_ratio_recent": 0.2,
                "body_ratio_recent": 0.8,
                "range_acceleration": 1.1,
                "dist_high": -0.01,
                "dist_low": 0.03,
                "directional_consistency": 4.0,
            },
            "rule_score": 0.7 if label else 0.3,
            "final_score": 0.75 if label else 0.25,
            "label_profitable": bool(label),
        }

    @staticmethod
    def _write_jsonl(path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_market_event_grouping_never_splits_correlated_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            rows = []
            for event in range(12):
                observed = 1_700_000_000_000 + event * 3_600_000
                for candidate in range(2):
                    rows.append(
                        self._row(
                            f"candidate-{event}-{candidate}",
                            f"event-{event}",
                            observed,
                            (event + candidate) % 2 == 0,
                        )
                    )
            dataset = root / "dataset.jsonl"
            self._write_jsonl(dataset, rows)
            paths = {name: root / f"{name}.jsonl" for name in ("train", "validation", "test")}
            report = TimeAwareDatasetSplitter(
                dataset_path=str(dataset),
                train_path=str(paths["train"]),
                validation_path=str(paths["validation"]),
                test_path=str(paths["test"]),
                report_path=str(root / "report.json"),
                train_ratio=0.5,
                validation_ratio=0.25,
                test_ratio=0.25,
                embargo_seconds=0,
                group_by_market_event=True,
            ).split()
            self.assertEqual(report["status"], "READY")
            self.assertEqual(report["configuration"]["grouping_policy"], "MARKET_EVENT")
            split_events = {}
            for name, path in paths.items():
                split_events[name] = {
                    json.loads(line)["market_event_id"]
                    for line in path.read_text().splitlines()
                    if line.strip()
                }
            self.assertFalse(split_events["train"] & split_events["validation"])
            self.assertFalse(split_events["train"] & split_events["test"])
            self.assertFalse(split_events["validation"] & split_events["test"])
            self.assertEqual(sum(len(v) for v in split_events.values()), 12)
            self.assertFalse(report["leakage_checks"]["market_event_overlap"])

    def test_market_event_mode_fails_closed_without_event_identity(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            rows = [
                self._row(f"candidate-{i}", f"event-{i}", 1000 + i * 1000, i % 2 == 0)
                for i in range(4)
            ]
            for row in rows:
                row.pop("market_event_id")
            dataset = root / "dataset.jsonl"
            self._write_jsonl(dataset, rows)
            report = TimeAwareDatasetSplitter(
                dataset_path=str(dataset),
                train_path=str(root / "train.jsonl"),
                validation_path=str(root / "validation.jsonl"),
                test_path=str(root / "test.jsonl"),
                report_path=str(root / "report.json"),
                train_ratio=0.5,
                validation_ratio=0.25,
                test_ratio=0.25,
                embargo_seconds=0,
                group_by_market_event=True,
            ).split()
            self.assertEqual(report["status"], "INSUFFICIENT_DATA")
            self.assertEqual(report["issues"]["candidate_market_event_invalid"], 4)

    def test_candidate_training_does_not_need_or_read_test_before_selection(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            train = root / "train.jsonl"
            validation = root / "validation.jsonl"
            train_rows = [
                self._row(f"train-{i}", f"train-event-{i}", 1000 + i * 1000, i % 2 == 0)
                for i in range(20)
            ]
            validation_rows = [
                self._row(f"validation-{i}", f"validation-event-{i}", 100_000 + i * 1000, i % 2 == 0)
                for i in range(10)
            ]
            self._write_jsonl(train, train_rows)
            self._write_jsonl(validation, validation_rows)
            baseline_report = BaselineModelTrainer(
                train_path=str(train),
                validation_path=str(validation),
                test_path=None,
                artifact_path=str(root / "baseline.pkl"),
                report_path=str(root / "baseline.json"),
                min_train_rows=10,
                min_eval_rows=4,
                evaluate_test=False,
            ).train()
            ensemble_report = OfflineEnsembleExperiment(
                train_path=str(train),
                validation_path=str(validation),
                test_path=None,
                artifact_path=str(root / "ensemble.pkl"),
                report_path=str(root / "ensemble.json"),
                min_train_rows=10,
                min_eval_rows=4,
                evaluate_test=False,
            ).run()
            self.assertEqual(baseline_report["status"], "TRAINED")
            self.assertNotIn("test", baseline_report["metrics"])
            self.assertFalse(baseline_report["test_evaluated_during_training"])
            baseline_artifact = pickle.loads((root / "baseline.pkl").read_bytes())
            self.assertFalse(baseline_artifact["test_evaluated_during_training"])
            self.assertEqual(ensemble_report["status"], "EXPERIMENT_COMPLETE")
            self.assertIsNone(ensemble_report["winner"]["test_metrics"])
            self.assertFalse(ensemble_report["winner"]["test_evaluated_during_training"])

    def test_cohort_readiness_waits_without_registering_model(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            orchestrator = self._orchestrator(
                root,
                count=50,
                min_new_outcomes=40,
                min_new_market_events=40,
                min_train_market_events=100,
                min_validation_market_events=5,
                min_test_market_events=5,
            )
            result = orchestrator.run_once()
            self.assertEqual(result["status"], "WAITING_FOR_COHORT")
            self.assertFalse(result["cohort_readiness"]["ready"])
            registry = json.loads((root / "registry.json").read_text())
            self.assertEqual(registry["models"], {})

    def test_final_test_is_opened_only_after_validation_winner_is_frozen(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            orchestrator = self._orchestrator(
                root,
                count=80,
                min_new_outcomes=40,
                min_new_market_events=40,
                min_train_market_events=10,
                min_validation_market_events=5,
                min_test_market_events=5,
            )
            result = orchestrator.run_once()
            self.assertEqual(result["status"], "TRAINING_COMPLETE")
            model_dir = Path(result["model_path"]).parent
            pretest = json.loads((model_dir / "pretest_selection_report.json").read_text())
            final = json.loads((model_dir / "challenger_selection_report.json").read_text())
            self.assertFalse(pretest["selected_using_test_data"])
            self.assertEqual(pretest["test_set_policy"], "SEALED_UNTIL_FINAL_CANDIDATE_SELECTED")
            self.assertTrue(all(v["test_metrics"] is None for v in pretest["candidates"].values()))
            self.assertTrue(final["test_unchanged"])
            self.assertFalse(final["selected_using_test_data"])
            evaluated = [name for name, row in final["candidates"].items() if row["test_evaluated"]]
            self.assertEqual(evaluated, [final["selected_candidate"]])


if __name__ == "__main__":
    unittest.main()
