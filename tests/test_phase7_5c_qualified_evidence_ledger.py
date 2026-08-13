import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.evidence_ledger import (
    LEDGER_SOURCE_MODE,
    Phase7EvidenceLedger,
)
from learning.model_registry import ModelRegistry
from learning.training_orchestrator import AutomaticTrainingOrchestrator
from tests import test_phase5_8_automatic_training_orchestrator as phase58
from utils.jsonl_history import (
    append_jsonl_line_bounded,
    history_directory,
)


class Phase75CQualifiedEvidenceLedgerTests(unittest.TestCase):
    def _source_rows(self, root, count=4):
        helper = phase58.Phase58AutomaticTrainingTests()
        observations, outcomes = helper._write_source(root, count=count)
        obs_rows = [json.loads(x) for x in observations.read_text().splitlines()]
        out_rows = [json.loads(x) for x in outcomes.read_text().splitlines()]
        return observations, outcomes, obs_rows, out_rows

    def _ledger(self, root):
        return Phase7EvidenceLedger(
            path=str(Path(root) / "phase7.sqlite3"),
            generation="PHASE7_LEDGER_V1",
            training_outcome_type="VIRTUAL_TRADE",
            environment="LIVE",
            pending_retention_hours=100000.0,
        )

    def test_candidate_is_qualified_once_and_exported_directly(self):
        with tempfile.TemporaryDirectory() as root:
            _, _, observations, outcomes = self._source_rows(root, count=2)
            ledger = self._ledger(root)
            self.assertEqual(
                ledger.register_candidate(observations[0])["decision"],
                "PENDING",
            )
            result = ledger.qualify_outcome(outcomes[0])
            self.assertEqual(result["decision"], "QUALIFIED")
            duplicate = ledger.qualify_outcome(outcomes[0])
            self.assertEqual(duplicate["decision"], "REJECTED")
            self.assertEqual(duplicate["reason"], "DUPLICATE")

            inventory = ledger.inventory(after_ms=0)
            self.assertEqual(inventory["new_completed_outcomes"], 1)
            self.assertEqual(inventory["pending_candidate_facts"], 0)
            self.assertEqual(inventory["new_independent_market_events"], 1)
            self.assertEqual(inventory["scan_mode"], LEDGER_SOURCE_MODE)
            self.assertEqual(inventory["ledger_generation"], "PHASE7_LEDGER_V1")

            destination = Path(root) / "training.jsonl"
            exported = ledger.export_dataset(destination)
            self.assertEqual(exported["rows"], 1)
            row = json.loads(destination.read_text().strip())
            self.assertEqual(row["candidate_observation_id"], "candidate-0")
            self.assertNotIn("score_breakdown", row)
            self.assertNotIn("risk_plan", row)
            self.assertNotIn("experiment_context", row)

    def test_incomplete_context_and_cost_are_rejected_before_training(self):
        with tempfile.TemporaryDirectory() as root:
            _, _, observations, outcomes = self._source_rows(root, count=2)
            ledger = self._ledger(root)

            observations[0]["market_context"]["completeness"] = "PARTIAL"
            observations[0]["experiment_context"]["market_context"]["completeness"] = "PARTIAL"
            result = ledger.register_candidate(observations[0])
            self.assertEqual(result["decision"], "PENDING")
            result = ledger.qualify_outcome(outcomes[0])
            self.assertEqual(result["decision"], "REJECTED")
            self.assertEqual(result["reason"], "INCOMPLETE_CONTEXT")

            self.assertEqual(
                ledger.register_candidate(observations[1])["decision"],
                "PENDING",
            )
            outcomes[1]["payload"]["cost_breakdown"]["cost_completeness"] = (
                "FEES_AND_CONFIGURED_SLIPPAGE_ONLY"
            )
            result = ledger.qualify_outcome(outcomes[1])
            self.assertEqual(result["decision"], "REJECTED")
            self.assertEqual(result["reason"], "INCOMPLETE_COST")
            inventory = ledger.inventory(after_ms=0)
            self.assertEqual(inventory["new_completed_outcomes"], 0)
            self.assertEqual(inventory["pending_candidate_facts"], 0)

    def test_auto_training_uses_ledger_when_raw_history_is_gone(self):
        helper = phase58.Phase58AutomaticTrainingTests()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations_path, outcomes_path, observations, outcomes = self._source_rows(
                root, count=80
            )
            ledger = self._ledger(root)
            for observation, outcome in zip(observations, outcomes):
                self.assertEqual(
                    ledger.register_candidate(observation)["decision"],
                    "PENDING",
                )
                self.assertEqual(
                    ledger.qualify_outcome(outcome)["decision"],
                    "QUALIFIED",
                )

            observations_path.unlink()
            outcomes_path.unlink()
            orchestrator = AutomaticTrainingOrchestrator(
                enabled=True,
                environment="LIVE",
                observations_path=str(observations_path),
                outcomes_path=str(outcomes_path),
                snapshot_root=str(root / "snapshots"),
                model_root=str(root / "models"),
                registry_path=str(root / "registry.json"),
                status_path=str(root / "status.json"),
                lock_path=str(root / "training.lock"),
                outcome_type="VIRTUAL_TRADE",
                default_parent_model_id="RULE_SYSTEM_V1",
                min_new_outcomes=40,
                min_new_market_events=40,
                train_ratio=0.60,
                validation_ratio=0.20,
                test_ratio=0.20,
                embargo_seconds=0,
                baseline_min_train_rows=20,
                baseline_min_eval_rows=5,
                ensemble_min_train_rows=20,
                ensemble_min_eval_rows=5,
                random_state=42,
                calibration_bins=5,
                drift_bins=5,
                min_roc_auc=0.0,
                max_brier_score=1.0,
                max_calibration_gap=1.0,
                max_feature_psi=10.0,
                evidence_ledger_path=str(root / "phase7.sqlite3"),
                evidence_generation="PHASE7_LEDGER_V1",
            )
            with patch(
                "learning.training_orchestrator.TrainingDatasetBuilder.build",
                side_effect=AssertionError("RAW_HISTORY_MUST_NOT_BE_SCANNED"),
            ):
                result = orchestrator.run_once()
            self.assertEqual(result["status"], "TRAINING_COMPLETE")
            record = orchestrator.registry.get_model(result["model_id"])
            self.assertEqual(record["evidence_generation"], "PHASE7_LEDGER_V1")
            self.assertEqual(record["training_source"], LEDGER_SOURCE_MODE)
            helper._make_writable(root)

    def test_model_cutoff_is_isolated_by_evidence_generation(self):
        with tempfile.TemporaryDirectory() as root:
            registry = ModelRegistry(
                path=str(Path(root) / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            registry.initialize()
            registry.register_training({
                "model_id": "OLD_MODEL",
                "data_cutoff_ms": 999999,
            })
            registry.update_model("OLD_MODEL", status="REJECTED")
            registry.register_training({
                "model_id": "LEDGER_MODEL",
                "data_cutoff_ms": 123,
                "evidence_generation": "PHASE7_LEDGER_V1",
            })
            registry.update_model("LEDGER_MODEL", status="REJECTED")
            self.assertEqual(registry.latest_completed_cutoff_ms(), 999999)
            self.assertEqual(
                registry.latest_completed_cutoff_ms(
                    evidence_generation="PHASE7_LEDGER_V1"
                ),
                123,
            )

    def test_raw_spool_rotates_small_segments_and_prunes_oldest(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "candidate_observations_live.jsonl"
            for index in range(20):
                append_jsonl_line_bounded(
                    path,
                    json.dumps({"index": index, "payload": "x" * 120}),
                    max_bytes=400,
                    retain_segments=2,
                    segment_tag="test",
                )
            segments = list(history_directory(path).glob("*.jsonl"))
            self.assertLessEqual(len(segments), 2)
            self.assertLess(path.stat().st_size, 500)


if __name__ == "__main__":
    unittest.main()
