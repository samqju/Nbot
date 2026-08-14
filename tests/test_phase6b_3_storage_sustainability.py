import json
import tempfile
import unittest
from pathlib import Path

from learning.model_registry import ModelRegistry
from learning.training_orchestrator import (
    AutomaticTrainingOrchestrator,
    TrainingInventory,
)
from tests import test_phase5_8_automatic_training_orchestrator as phase58
from utils.jsonl_history import (
    append_jsonl_line,
    history_directory,
    iter_jsonl_lines,
    rotate_jsonl_to_history,
)


class Phase6B3StorageSustainabilityTests(unittest.TestCase):
    def test_rotation_preserves_logical_rows_and_compresses_history(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_outcomes_live.jsonl"
            append_jsonl_line(path, json.dumps({"row": 1}))
            append_jsonl_line(path, json.dumps({"row": 2}))

            result = rotate_jsonl_to_history(
                path,
                segment_tag="cutoff-123",
                min_bytes=1,
            )
            self.assertTrue(result["rotated"])
            self.assertEqual(path.read_text(), "")
            self.assertTrue(result["archive_path"].endswith(".jsonl.gz"))
            self.assertTrue(Path(result["archive_path"]).exists())

            append_jsonl_line(path, json.dumps({"row": 3}))
            rows = [json.loads(line) for line in iter_jsonl_lines(path)]
            self.assertEqual(rows, [{"row": 1}, {"row": 2}, {"row": 3}])

    def test_snapshot_keeps_training_dataset_but_not_duplicate_raw_sources(self):
        helper = phase58.Phase58AutomaticTrainingTests()
        with tempfile.TemporaryDirectory() as root:
            orchestrator = helper._orchestrator(root, count=40)
            snapshot = orchestrator._create_snapshot()
            snapshot_path = Path(snapshot["snapshot_path"])
            try:
                self.assertTrue((snapshot_path / "training_dataset.jsonl").exists())
                self.assertTrue((snapshot_path / "snapshot_manifest.json").exists())
                self.assertTrue(
                    (snapshot_path / "dataset_integrity_report.json").exists()
                )
                self.assertFalse((snapshot_path / "source").exists())
                self.assertFalse(
                    (snapshot_path / "training_dataset_all.jsonl").exists()
                )
                report = json.loads(
                    (snapshot_path / "dataset_integrity_report.json").read_text()
                )
                self.assertFalse(report["output"]["full_dataset_persisted"])
            finally:
                helper._make_writable(root)

    def test_existing_rejected_storage_is_pruned_but_cutoff_is_preserved(self):
        helper = phase58.Phase58AutomaticTrainingTests()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            orchestrator = helper._orchestrator(
                root,
                count=10,
                min_new_outcomes=100,
                min_new_market_events=100,
                history_rotate_min_bytes=10**9,
            )
            registry = ModelRegistry(
                path=str(root / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            registry.initialize()

            snapshot = root / "snapshots" / "old-rejected"
            model_dir = root / "models" / "MODEL_REJECTED"
            snapshot.mkdir(parents=True)
            model_dir.mkdir(parents=True)
            (snapshot / "training_dataset.jsonl").write_text("x" * 1024)
            (model_dir / "challenger.pkl").write_text("y" * 2048)

            registry.register_training(
                {
                    "model_id": "MODEL_REJECTED",
                    "parent_model_id": "RULE_SYSTEM_V1",
                    "data_cutoff_ms": 123456,
                    "dataset_snapshot_path": str(snapshot),
                    "model_directory": str(model_dir),
                    "artifact_path": str(model_dir / "challenger.pkl"),
                }
            )
            registry.update_model("MODEL_REJECTED", status="REJECTED")

            result = orchestrator.run_once()
            self.assertEqual(result["status"], "WAITING_FOR_DATA")
            self.assertFalse(snapshot.exists())
            self.assertFalse(model_dir.exists())
            record = registry.get_model("MODEL_REJECTED")
            self.assertEqual(record["status"], "REJECTED")
            self.assertEqual(record["data_cutoff_ms"], 123456)
            self.assertIsNone(record["artifact_path"])
            self.assertIsNone(record["dataset_snapshot_path"])
            self.assertGreaterEqual(record["storage_reclaimed_bytes"], 3072)
            self.assertTrue(record["storage_pruned_at_ms"])
            self.assertEqual(registry.latest_completed_cutoff_ms(), 123456)

    def test_training_inventory_reads_archived_and_live_rows(self):
        helper = phase58.Phase58AutomaticTrainingTests()
        with tempfile.TemporaryDirectory() as root:
            observations, outcomes = helper._write_source(root, count=10)
            rotate_jsonl_to_history(
                observations,
                segment_tag="cutoff-1",
                min_bytes=1,
            )
            rotate_jsonl_to_history(
                outcomes,
                segment_tag="cutoff-1",
                min_bytes=1,
            )
            inventory = TrainingInventory(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
                outcome_type="VIRTUAL_TRADE",
            ).scan(after_ms=0)
            self.assertEqual(inventory["new_completed_outcomes"], 10)
            self.assertEqual(inventory["new_independent_market_events"], 10)
            self.assertTrue(history_directory(observations).exists())
            self.assertTrue(history_directory(outcomes).exists())

    def test_rejected_new_challenger_prunes_snapshot_and_model_directory(self):
        helper = phase58.Phase58AutomaticTrainingTests()
        with tempfile.TemporaryDirectory() as root:
            orchestrator = helper._orchestrator(
                root,
                count=80,
                max_feature_psi=-1.0,
                history_rotate_min_bytes=1,
            )
            result = orchestrator.run_once()
            self.assertEqual(result["status"], "TRAINING_COMPLETE")
            self.assertEqual(result["model_status"], "REJECTED")
            self.assertIsNone(result["model_path"])
            self.assertIsNone(result["snapshot_path"])

            registry = orchestrator.registry
            record = registry.get_model(result["model_id"])
            self.assertEqual(record["status"], "REJECTED")
            self.assertIsNone(record["artifact_path"])
            self.assertIsNone(record["dataset_snapshot_path"])
            self.assertTrue(record["storage_pruned_at_ms"])
            self.assertTrue(record["evaluation_diagnostics_retained"])
            diagnostics = record["evaluation_diagnostics"]
            self.assertIn("validation", diagnostics["calibration"])
            self.assertIn("test", diagnostics["calibration"])
            self.assertIn("features", diagnostics["drift"])
            self.assertIn(
                "max_stability_feature_psi", diagnostics["drift"]
            )
            self.assertIn(
                "max_regime_context_psi", diagnostics["drift"]
            )

            # Even after hot files rotate away, all evidence remains readable.
            inventory = TrainingInventory(
                observations_path=str(orchestrator.observations_path),
                outcomes_path=str(orchestrator.outcomes_path),
                outcome_type="VIRTUAL_TRADE",
            ).scan(after_ms=0)
            self.assertEqual(inventory["new_completed_outcomes"], 80)


if __name__ == "__main__":
    unittest.main()
