import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.dataset_builder import TrainingDatasetBuilder
from learning.operator_status import AutoLearningStatusPublisher
from learning.training_orchestrator import (
    AutomaticTrainingOrchestrator,
    TrainingInventory,
)
from tests import test_phase4_1_dataset_builder as phase41
from tests import test_phase5_8_automatic_training_orchestrator as phase58


class Phase75BMemorySafeTrainingPipelineTests(unittest.TestCase):
    def test_dataset_builder_uses_disk_backed_streaming_contract(self):
        helper = phase41.Phase41DatasetBuilderTests()
        with tempfile.TemporaryDirectory() as root:
            report, dataset_path, _ = helper._build(
                root,
                [
                    helper._observation("candidate-2"),
                    helper._observation("candidate-1"),
                ],
                [
                    helper._make_outcome(
                        "candidate-2", recorded_at_ms=4000
                    ),
                    helper._make_outcome(
                        "candidate-1", recorded_at_ms=3000
                    ),
                ],
            )
            self.assertEqual(
                report["output"]["build_mode"],
                "DISK_BACKED_STREAMING_SQLITE",
            )
            rows = [
                json.loads(line)
                for line in dataset_path.read_text().splitlines()
            ]
            self.assertEqual(
                [row["candidate_observation_id"] for row in rows],
                ["candidate-1", "candidate-2"],
            )
            leftovers = list(Path(root).glob(".dataset-build.*"))
            self.assertEqual(leftovers, [])

    def test_inventory_streaming_preserves_qualified_counts(self):
        helper = phase58.Phase58AutomaticTrainingTests()
        with tempfile.TemporaryDirectory() as root:
            observations, outcomes = helper._write_source(root, count=24)
            inventory = TrainingInventory(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
                outcome_type="VIRTUAL_TRADE",
                require_complete_market_context=True,
                require_complete_cost_evidence=True,
            ).scan(after_ms=0)
            self.assertEqual(inventory["new_completed_outcomes"], 24)
            self.assertEqual(inventory["new_independent_market_events"], 24)
            self.assertEqual(
                inventory["scan_mode"],
                "DISK_BACKED_STREAMING_SQLITE",
            )
            self.assertEqual(
                list(Path(root).glob(".training-inventory.*")), []
            )

    def test_snapshot_does_not_bulk_read_dataset_into_python_memory(self):
        helper = phase58.Phase58AutomaticTrainingTests()
        with tempfile.TemporaryDirectory() as root:
            orchestrator = helper._orchestrator(root, count=40)
            try:
                with patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("bulk read_bytes forbidden"),
                ), patch.object(
                    Path,
                    "read_text",
                    side_effect=AssertionError("bulk read_text forbidden"),
                ):
                    snapshot = orchestrator._create_snapshot()
                self.assertEqual(
                    snapshot["build_mode"],
                    "STREAMING_BOUNDED_MEMORY",
                )
                manifest_path = (
                    Path(snapshot["snapshot_path"])
                    / "snapshot_manifest.json"
                )
                with manifest_path.open("r") as handle:
                    manifest = json.load(handle)
                self.assertEqual(
                    manifest["snapshot_build_mode"],
                    "STREAMING_BOUNDED_MEMORY",
                )
            finally:
                helper._make_writable(root)

    def test_streaming_fingerprint_matches_legacy_byte_fingerprint(self):
        with tempfile.TemporaryDirectory() as root:
            dataset_path = Path(root) / "dataset.jsonl"
            dataset_path.write_bytes(b'{"a":1}\n{"b":2}\n')
            metadata = {"rows": 2, "phase": "7.5B"}
            legacy = AutomaticTrainingOrchestrator._fingerprint(
                dataset_path.read_bytes(), metadata
            )
            streaming = AutomaticTrainingOrchestrator._fingerprint_file(
                dataset_path, metadata
            )
            self.assertEqual(streaming, legacy)
            self.assertEqual(len(streaming), hashlib.sha256().digest_size * 2)

    def test_learning_status_exposes_cohort_purge_and_embargo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = 1_786_510_000_000
            (root / "training.json").write_text(json.dumps({
                "generated_at_ms": now,
                "phase": "7.4",
                "status": "WAITING_FOR_COHORT",
                "inventory": {
                    "new_completed_outcomes": 12982,
                    "new_independent_market_events": 226,
                    "issue_count": 0,
                },
                "thresholds": {
                    "min_new_outcomes": 1000,
                    "min_new_market_events": 200,
                    "min_train_market_events": 50,
                    "min_validation_market_events": 20,
                    "min_test_market_events": 20,
                },
                "cohort_readiness": {
                    "ready": False,
                    "split_status": "INSUFFICIENT_AFTER_EMBARGO",
                    "snapshot_build_mode": "STREAMING_BOUNDED_MEMORY",
                    "split_market_events": {
                        "train": 137,
                        "validation": 0,
                        "test": 23,
                    },
                    "checks": {
                        "train_market_events": {"required_min": 50},
                        "validation_market_events": {"required_min": 20},
                        "test_market_events": {"required_min": 20},
                    },
                    "purging": {"candidate_groups_excluded": 31},
                    "embargo": {"candidate_groups_excluded": 35},
                },
            }))
            publisher = AutoLearningStatusPublisher(
                environment="LIVE",
                execution_mode="SHADOW",
                default_champion_model_id="RULE_SYSTEM_V1",
                status_path=str(root / "status.json"),
                registry_path=str(root / "registry.json"),
                observations_path=str(root / "missing-observations.jsonl"),
                outcomes_path=str(root / "missing-outcomes.jsonl"),
                training_outcome_type="VIRTUAL_TRADE",
                auto_training_status_path=str(root / "training.json"),
                promotion_status_path=str(root / "promotion.json"),
                promotion_evidence_path=str(root / "promotion-evidence.json"),
                paper_canary_status_path=str(root / "canary.json"),
                strategy_policy_path=str(root / "strategy.json"),
                source_stale_seconds=10**9,
            )
            document = publisher.refresh()
            cohort = document["training_data"]["cohort_readiness"]
            self.assertEqual(cohort["split_market_events"]["train"], 137)
            rendered = publisher.render_console(document)
            self.assertIn("STREAMING_BOUNDED_MEMORY", rendered)
            self.assertIn("137 / 50 [PASS]", rendered)
            self.assertIn("0 / 20 [WAIT]", rendered)
            self.assertIn("23 / 20 [PASS]", rendered)
            self.assertIn("Purged event groups    : 31", rendered)
            self.assertIn("Embargoed event groups : 35", rendered)


if __name__ == "__main__":
    unittest.main()
