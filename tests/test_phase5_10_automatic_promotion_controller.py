import hashlib
import json
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.model_registry import ModelRegistry
from learning.promotion_controller import AutomaticPromotionController
from learning.shadow_decision_testing import ShadowDecisionEvaluator


class DummyScaler:
    def transform(self, values):
        return values


class DummyModel:
    def predict_proba(self, values):
        return [[0.5, 0.5] for _ in values]


class Phase510AutomaticPromotionControllerTests(unittest.TestCase):
    def _artifact(self, path: Path, model_id: str) -> str:
        artifact = {
            "artifact_schema_version": 1,
            "model_kind": "LOGISTIC_REGRESSION_BASELINE",
            "model_id": model_id,
            "base_feature_names": ("short_range",),
            "pattern_categories": ("RANGE_BREAKOUT",),
            "scaler": DummyScaler(),
            "model": DummyModel(),
            "runtime_activation": "DISABLED",
        }
        data = pickle.dumps(artifact)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def _registry(self, root: Path, model_id="MODEL_A"):
        artifact_path = root / f"{model_id}.pkl"
        checksum = self._artifact(artifact_path, model_id)
        registry = ModelRegistry(
            path=str(root / "registry.json"),
            environment="LIVE",
            default_champion_model_id="RULE_SYSTEM_V1",
        )
        registry.register_training(
            {
                "model_id": model_id,
                "parent_model_id": "RULE_SYSTEM_V1",
                "training_completed_at_ms": 10,
                "artifact_path": str(artifact_path),
                "artifact_checksum_sha256": checksum,
                "dataset_fingerprint": "a" * 64,
                "test_metrics": {"brier_score": 0.20},
                "calibration_metrics": {"test_max_abs_gap": 0.05},
                "drift_metrics": {"max_feature_psi": 0.10},
            }
        )
        registry.update_model(model_id, status="OFFLINE_VALIDATED")
        registry.activate_next_shadow_challenger()
        return registry, artifact_path

    @staticmethod
    def _selection(candidate_id):
        return {
            "candidate_observation_id": candidate_id,
            "symbol": candidate_id.upper() + "USDT",
            "direction": "LONG",
            "pattern": "RANGE_BREAKOUT",
            "market_context": {
                "market_regime": "BULLISH",
                "trend_regime": "UP",
                "volatility_regime": "NORMAL",
            },
        }

    def _write_evidence(
        self,
        root: Path,
        *,
        model_id="MODEL_A",
        events=4,
        challenger_r=0.30,
        champion_r=0.05,
        event_prefix="event",
    ):
        decisions = []
        outcomes = []
        for index in range(events):
            champion_id = f"champ-{event_prefix}-{index}"
            challenger_id = f"chall-{event_prefix}-{index}"
            champion = self._selection(champion_id)
            challenger = self._selection(challenger_id)
            decisions.append(
                {
                    "schema_version": 1,
                    "observation_type": "CHAMPION_CHALLENGER_DECISION",
                    "observed_at_ms": index + 1,
                    "decision_batch_id": f"batch-{event_prefix}-{index}",
                    "market_event_id": f"{event_prefix}-{index}",
                    "current_champion_model_id": "RULE_SYSTEM_V1",
                    "current_challenger_model_id": model_id,
                    "runtime_effect": "NONE",
                    "systems": {
                        "RULES": {
                            "model_id": "RULE_SYSTEM_V1",
                            "status": "AVAILABLE",
                            "top_one": [champion],
                            "top_k": [champion],
                        },
                        "CHAMPION": {
                            "model_id": "RULE_SYSTEM_V1",
                            "status": "AVAILABLE",
                            "top_one": [champion],
                            "top_k": [champion],
                        },
                        "CHALLENGER": {
                            "model_id": model_id,
                            "status": "AVAILABLE",
                            "top_one": [challenger],
                            "top_k": [challenger],
                        },
                    },
                }
            )
            for candidate_id, net_r in (
                (champion_id, champion_r),
                (challenger_id, challenger_r),
            ):
                outcomes.append(
                    {
                        "observation_type": "CANDIDATE_OUTCOME",
                        "recorded_at_ms": 1000 + index,
                        "candidate_observation_id": candidate_id,
                        "outcome_type": "VIRTUAL_TRADE",
                        "payload": {
                            "net_exit_r": net_r,
                            "gross_exit_r": net_r + 0.1,
                            "estimated_cost_r": 0.1,
                        },
                    }
                )
        (root / "decisions.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in decisions)
        )
        (root / "outcomes.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in outcomes)
        )

    def _controller(
        self,
        root: Path,
        *,
        matched=4,
        independent=4,
        disagreements=2,
        lift=0.10,
    ):
        return AutomaticPromotionController(
            enabled=True,
            environment="LIVE",
            decisions_path=str(root / "decisions.jsonl"),
            outcomes_path=str(root / "outcomes.jsonl"),
            evidence_report_path=str(root / "promotion_evidence.json"),
            registry_path=str(root / "registry.json"),
            status_path=str(root / "promotion_status.json"),
            lock_path=str(root / "promotion.lock"),
            default_champion_model_id="RULE_SYSTEM_V1",
            outcome_type="VIRTUAL_TRADE",
            min_matched_outcomes=matched,
            min_independent_events=independent,
            min_disagreement_events=disagreements,
            min_average_r_lift=lift,
            min_after_cost_expectancy=0.0,
            max_win_rate_deterioration=0.02,
            max_brier_score=0.25,
            max_calibration_gap=0.10,
            max_feature_psi=0.25,
            min_recent_expectancy=0.0,
            recent_event_window=2,
            extend_evidence_ratio=0.50,
        )

    def test_registry_promotes_canary_atomically_without_champion_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registry(root)
            record = registry.apply_promotion_decision(
                "MODEL_A",
                decision="PROMOTE_TO_PAPER_CANARY",
                evidence={"matched_candidate_outcomes": 1000},
                gate_report={"all_gates_passed": True},
                reason_codes=["ALL_GATES_PASSED"],
            )
            self.assertEqual(record["status"], "PAPER_CANARY")
            self.assertIsNone(registry.current_shadow_model_id())
            self.assertEqual(
                registry.current_paper_canary_model_id(), "MODEL_A"
            )
            self.assertEqual(
                registry.current_champion_model_id(), "RULE_SYSTEM_V1"
            )
            self.assertEqual(
                record["paper_authority"],
                "CANARY_SLOT_RESERVED_NO_ORDER_ROUTING",
            )

    def test_registry_reject_and_hold_transitions_are_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registry(root)
            held = registry.apply_promotion_decision(
                "MODEL_A",
                decision="HOLD",
                evidence={"matched_candidate_outcomes": 10},
                gate_report={"all_gates_passed": False},
                reason_codes=["INSUFFICIENT"],
            )
            self.assertEqual(held["status"], "SHADOW")
            rejected = registry.apply_promotion_decision(
                "MODEL_A",
                decision="REJECT",
                evidence={"matched_candidate_outcomes": 1000},
                gate_report={"all_gates_passed": False},
                reason_codes=["NEGATIVE_R_LIFT"],
            )
            self.assertEqual(rejected["status"], "REJECTED")
            self.assertIsNone(registry.current_shadow_model_id())
            self.assertIsNone(registry.current_paper_canary_model_id())

    def test_registry_failed_atomic_replace_never_activates_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registry(root)
            with patch(
                "learning.model_registry.os.replace",
                side_effect=OSError("forced replace failure"),
            ):
                with self.assertRaises(OSError):
                    registry.apply_promotion_decision(
                        "MODEL_A",
                        decision="PROMOTE_TO_PAPER_CANARY",
                        evidence={"matched_candidate_outcomes": 1000},
                        gate_report={"all_gates_passed": True},
                        reason_codes=["ALL_GATES_PASSED"],
                    )
            reloaded = ModelRegistry(
                path=str(root / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            self.assertEqual(reloaded.current_shadow_model_id(), "MODEL_A")
            self.assertIsNone(reloaded.current_paper_canary_model_id())
            self.assertEqual(reloaded.get_model("MODEL_A")["status"], "SHADOW")

    def test_evaluator_filters_model_and_reports_recent_paired_win_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(root, events=3, challenger_r=0.3)
            original = (root / "decisions.jsonl").read_text()
            original_outcomes = (root / "outcomes.jsonl").read_text()
            self._write_evidence(
                root,
                model_id="MODEL_B",
                events=1,
                challenger_r=-1.0,
                event_prefix="other",
            )
            (root / "decisions.jsonl").write_text(
                original + (root / "decisions.jsonl").read_text()
            )
            (root / "outcomes.jsonl").write_text(
                original_outcomes + (root / "outcomes.jsonl").read_text()
            )
            report = ShadowDecisionEvaluator(
                decisions_path=str(root / "decisions.jsonl"),
                outcomes_path=str(root / "outcomes.jsonl"),
                report_path=str(root / "report.json"),
                challenger_model_id="MODEL_A",
                champion_model_id="RULE_SYSTEM_V1",
                recent_event_window=2,
            ).evaluate()
            summary = report["policies"]["CHALLENGER"]["TOP_ONE"]["summary"]
            comparison = report["pairwise"]["CHALLENGER_VS_CHAMPION"]["TOP_ONE"]
            self.assertEqual(summary["independent_market_events"], 3)
            self.assertEqual(summary["recent_event_count"], 2)
            self.assertAlmostEqual(summary["recent_average_net_r"], 0.3)
            self.assertEqual(comparison["left_win_rate"], 1.0)
            self.assertEqual(comparison["right_win_rate"], 1.0)
            self.assertEqual(
                report["filters"]["challenger_model_id"], "MODEL_A"
            )

    def test_controller_holds_when_evidence_is_small(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry(root)
            self._write_evidence(root, events=1)
            result = self._controller(root).run_once()
            self.assertEqual(result["promotion_outcome"], "HOLD")
            self.assertEqual(
                ModelRegistry(
                    path=str(root / "registry.json"),
                    environment="LIVE",
                    default_champion_model_id="RULE_SYSTEM_V1",
                ).get_model("MODEL_A")["status"],
                "SHADOW",
            )

    def test_controller_extends_promising_partial_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry(root)
            self._write_evidence(root, events=2)
            result = self._controller(root).run_once()
            self.assertEqual(result["promotion_outcome"], "EXTEND_SHADOW")
            self.assertIn(
                "PROMISING_EARLY_FORWARD_EVIDENCE",
                result["reason_codes"],
            )

    def test_controller_promotes_only_after_all_gates_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry(root)
            self._write_evidence(root, events=4)
            result = self._controller(root).run_once()
            self.assertEqual(
                result["promotion_outcome"], "PROMOTE_TO_PAPER_CANARY"
            )
            registry = ModelRegistry(
                path=str(root / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            self.assertEqual(registry.get_model("MODEL_A")["status"], "PAPER_CANARY")
            self.assertEqual(registry.current_paper_canary_model_id(), "MODEL_A")
            self.assertEqual(registry.current_champion_model_id(), "RULE_SYSTEM_V1")
            self.assertFalse(result["paper_order_routing_changed"])

    def test_controller_rejects_sufficient_negative_forward_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry(root)
            self._write_evidence(
                root,
                events=4,
                challenger_r=-0.3,
                champion_r=0.2,
            )
            result = self._controller(root).run_once()
            self.assertEqual(result["promotion_outcome"], "REJECT")
            self.assertIn("NEGATIVE_R_LIFT", result["reason_codes"])

    def test_controller_rejects_tampered_artifact_before_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._registry(root)
            self._write_evidence(root, events=4)
            artifact.write_bytes(b"tampered")
            result = self._controller(root).run_once()
            self.assertEqual(result["promotion_outcome"], "REJECT")
            self.assertTrue(
                any(
                    "artifact_integrity" in code
                    for code in result["reason_codes"]
                )
            )
            self.assertIsNone(registry.current_paper_canary_model_id())

    def test_controller_skips_rewriting_without_new_completed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry(root)
            self._write_evidence(root, events=1)
            controller = self._controller(root)
            first = controller.run_once()
            second = controller.run_once()
            self.assertEqual(first["promotion_outcome"], "HOLD")
            self.assertEqual(second["status"], "NO_NEW_COMPLETED_EVIDENCE")
            self.assertFalse(second["registry_changed"])


if __name__ == "__main__":
    unittest.main()
