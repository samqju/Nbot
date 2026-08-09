import json
import os
import tempfile
import unittest
from pathlib import Path

from learning.model_registry import ModelRegistry, ModelRegistryError
from learning.training_orchestrator import (
    AutoTrainingAlreadyRunning,
    AutoTrainingProcessLock,
    AutomaticTrainingOrchestrator,
    TrainingInventory,
)
from strategy.experiment_contract import (
    build_experiment_context,
    experiment_projection,
)
from strategy.features import CANDIDATE_FEATURE_NAMES


class Phase58AutomaticTrainingTests(unittest.TestCase):
    @staticmethod
    def _features(label, index):
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

    def _write_source(self, root, count=80):
        root = Path(root)
        observations_path = root / "observations.jsonl"
        outcomes_path = root / "outcomes.jsonl"
        observations = []
        outcomes = []
        base = 1_700_000_000_000
        for index in range(count):
            label = bool(index % 2)
            observed_at_ms = base + index * 600_000
            context = build_experiment_context(
                decision_batch_id=f"batch-{index}",
                market_event_id=f"event-{index}",
                strategy_version="STRUCTURE_RULES_V1",
                strategy_variant_id=(
                    "STRUCTURE_CANDIDATE_GENERATOR_V1"
                ),
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
            observations.append(
                {
                    "schema_version": 3,
                    **projection,
                    "observation_type": "STRATEGY_CANDIDATE",
                    "observed_at_ms": observed_at_ms,
                    "environment": "LIVE",
                    "execution_mode": "SHADOW",
                    "candidate_observation_id": candidate_id,
                    "symbol": "BTCUSDT",
                    "direction": "LONG" if label else "SHORT",
                    "pattern": "RANGE_BREAKOUT",
                    "bucket": index,
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
                    "features": self._features(label, index),
                    "structure_fingerprint": {
                        "structure": "RANGE_BREAKOUT"
                    },
                    "market_context": context["market_context"],
                    "cost_model": context["cost_model"],
                    "virtual_policy": context["virtual_policy"],
                    "paper_policy": context["paper_policy"],
                    "experiment_context": context,
                }
            )
            outcomes.append(
                {
                    "schema_version": 2,
                    **projection,
                    "observation_type": "CANDIDATE_OUTCOME",
                    "recorded_at_ms": observed_at_ms + 300_000,
                    "environment": "LIVE",
                    "execution_mode": "SHADOW",
                    "candidate_observation_id": candidate_id,
                    "outcome_type": "VIRTUAL_TRADE",
                    "symbol": "BTCUSDT",
                    "direction": "LONG" if label else "SHORT",
                    "outcome_variant_id": "VIRTUAL_FIXED_2R_24C_V1",
                    "experiment_context": context,
                    "payload": {
                        "exit_r": 2.0 if label else -1.0,
                        "profitable": label,
                    },
                }
            )
        observations_path.write_text(
            "".join(json.dumps(row) + "\n" for row in observations)
        )
        outcomes_path.write_text(
            "".join(json.dumps(row) + "\n" for row in outcomes)
        )
        return observations_path, outcomes_path

    def _orchestrator(self, root, *, count=80, **overrides):
        root = Path(root)
        observations, outcomes = self._write_source(root, count=count)
        arguments = {
            "enabled": True,
            "environment": "LIVE",
            "observations_path": str(observations),
            "outcomes_path": str(outcomes),
            "snapshot_root": str(root / "snapshots"),
            "model_root": str(root / "models"),
            "registry_path": str(root / "registry.json"),
            "status_path": str(root / "status.json"),
            "lock_path": str(root / "training.lock"),
            "outcome_type": "VIRTUAL_TRADE",
            "default_parent_model_id": "RULE_SYSTEM_V1",
            "min_new_outcomes": 40,
            "min_new_market_events": 40,
            "train_ratio": 0.60,
            "validation_ratio": 0.20,
            "test_ratio": 0.20,
            "embargo_seconds": 0,
            "baseline_min_train_rows": 20,
            "baseline_min_eval_rows": 5,
            "ensemble_min_train_rows": 20,
            "ensemble_min_eval_rows": 5,
            "random_state": 42,
            "calibration_bins": 5,
            "drift_bins": 5,
            "min_roc_auc": 0.0,
            "max_brier_score": 1.0,
            "max_calibration_gap": 1.0,
            "max_feature_psi": 10.0,
        }
        arguments.update(overrides)
        return AutomaticTrainingOrchestrator(**arguments)

    @staticmethod
    def _make_writable(root):
        root = Path(root)
        for path in root.rglob("*"):
            try:
                path.chmod(0o755 if path.is_dir() else 0o644)
            except FileNotFoundError:
                pass

    def test_inventory_counts_only_rows_after_cutoff(self):
        with tempfile.TemporaryDirectory() as root:
            observations, outcomes = self._write_source(root, count=10)
            inventory = TrainingInventory(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
                outcome_type="VIRTUAL_TRADE",
            )
            all_rows = inventory.scan(after_ms=0)
            cutoff = 1_700_000_000_000 + 4 * 600_000 + 300_000
            later = inventory.scan(after_ms=cutoff)
            self.assertEqual(all_rows["new_completed_outcomes"], 10)
            self.assertEqual(all_rows["new_independent_market_events"], 10)
            self.assertEqual(later["new_completed_outcomes"], 5)
            self.assertEqual(later["new_independent_market_events"], 5)

    def test_registry_preserves_rule_champion(self):
        with tempfile.TemporaryDirectory() as root:
            registry = ModelRegistry(
                path=str(Path(root) / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            registry.initialize()
            registry.register_training(
                {
                    "model_id": "MODEL_A",
                    "parent_model_id": "RULE_SYSTEM_V1",
                    "data_cutoff_ms": 123,
                }
            )
            registry.update_model(
                "MODEL_A",
                status="OFFLINE_VALIDATED",
                updates={"artifact_path": "model.pkl"},
            )
            self.assertEqual(
                registry.current_champion_model_id(), "RULE_SYSTEM_V1"
            )
            self.assertEqual(registry.latest_completed_cutoff_ms(), 123)

    def test_registry_rejects_illegal_direct_paper_transition(self):
        with tempfile.TemporaryDirectory() as root:
            registry = ModelRegistry(
                path=str(Path(root) / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            registry.register_training({"model_id": "MODEL_A"})
            with self.assertRaises(ModelRegistryError):
                registry.update_model("MODEL_A", status="PAPER_CHAMPION")

    def test_separate_training_lock_blocks_second_owner(self):
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / "training.lock")
            first = AutoTrainingProcessLock(path)
            second = AutoTrainingProcessLock(path)
            first.acquire()
            try:
                with self.assertRaises(AutoTrainingAlreadyRunning):
                    second.acquire()
            finally:
                first.release()

    def test_waiting_for_data_creates_no_model(self):
        with tempfile.TemporaryDirectory() as root:
            orchestrator = self._orchestrator(
                root,
                count=10,
                min_new_outcomes=40,
                min_new_market_events=40,
            )
            result = orchestrator.run_once()
            self.assertEqual(result["status"], "WAITING_FOR_DATA")
            self.assertFalse((Path(root) / "models").exists())

    def test_successful_pipeline_registers_provenance_without_promotion(self):
        with tempfile.TemporaryDirectory() as root:
            try:
                orchestrator = self._orchestrator(root, count=80)
                result = orchestrator.run_once()
                self.assertEqual(result["status"], "TRAINING_COMPLETE")
                self.assertEqual(result["model_status"], "OFFLINE_VALIDATED")
                self.assertFalse(result["champion_changed"])
                registry = json.loads((Path(root) / "registry.json").read_text())
                model = registry["models"][result["model_id"]]
                self.assertEqual(
                    registry["current_champion_model_id"],
                    "RULE_SYSTEM_V1",
                )
                self.assertEqual(model["parent_model_id"], "RULE_SYSTEM_V1")
                self.assertEqual(len(model["dataset_fingerprint"]), 64)
                self.assertEqual(len(model["artifact_checksum_sha256"]), 64)
                self.assertGreater(model["training_rows"], 0)
                self.assertEqual(model["feature_schema_version"], 3)
                self.assertIn("strategy_versions", model["strategy_schema"])
                self.assertEqual(model["runtime_activation"], "DISABLED")
                self.assertEqual(model["paper_authority"], "UNCHANGED")
                self.assertTrue(Path(model["artifact_path"]).exists())
            finally:
                self._make_writable(root)

    def test_failed_training_marks_invalid_and_keeps_champion(self):
        with tempfile.TemporaryDirectory() as root:
            try:
                orchestrator = self._orchestrator(
                    root,
                    count=80,
                    baseline_min_train_rows=10_000,
                    ensemble_min_train_rows=10_000,
                )
                with self.assertRaises(Exception):
                    orchestrator.run_once()
                registry = json.loads((Path(root) / "registry.json").read_text())
                model = registry["models"][registry["latest_model_id"]]
                self.assertEqual(model["status"], "INVALID")
                self.assertEqual(
                    registry["current_champion_model_id"],
                    "RULE_SYSTEM_V1",
                )
            finally:
                self._make_writable(root)

    def test_snapshot_fingerprint_is_reproducible(self):
        with tempfile.TemporaryDirectory() as root:
            try:
                orchestrator = self._orchestrator(root, count=40)
                first = orchestrator._create_snapshot()
                second = orchestrator._create_snapshot()
                self.assertEqual(
                    first["dataset_fingerprint"],
                    second["dataset_fingerprint"],
                )
                manifest = Path(first["snapshot_path"]) / "snapshot_manifest.json"
                self.assertEqual(manifest.stat().st_mode & 0o222, 0)
            finally:
                self._make_writable(root)

    def test_model_selection_uses_validation_not_test(self):
        baseline = {
            "name": "BASELINE",
            "evaluation": {
                "metrics": {
                    "validation": {
                        "log_loss": 0.20,
                        "brier_score": 0.10,
                        "roc_auc": 0.70,
                    },
                    "test": {"log_loss": 9.0},
                }
            },
        }
        ensemble = {
            "name": "ENSEMBLE",
            "evaluation": {
                "metrics": {
                    "validation": {
                        "log_loss": 0.30,
                        "brier_score": 0.05,
                        "roc_auc": 0.99,
                    },
                    "test": {"log_loss": 0.01},
                }
            },
        }
        winner = min(
            [baseline, ensemble],
            key=AutomaticTrainingOrchestrator._candidate_selection_key,
        )
        self.assertEqual(winner["name"], "BASELINE")

    def test_systemd_template_runs_separate_supervisor(self):
        service = Path(
            "deploy/observation/nbot-auto-training.service.in"
        ).read_text()
        self.assertIn("scripts.learning.auto_train --watch", service)
        self.assertIn("Nice=10", service)
        self.assertNotIn("run.py", service)


if __name__ == "__main__":
    unittest.main()
