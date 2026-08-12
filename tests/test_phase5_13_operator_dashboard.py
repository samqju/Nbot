import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.operator_status import AutoLearningStatusPublisher
from strategy.experiment_contract import EXPERIMENT_CONTRACT_VERSION


class Phase513OperatorDashboardTests(unittest.TestCase):
    def _publisher(self, root: Path, **overrides):
        args = dict(
            environment="LIVE",
            execution_mode="SHADOW",
            default_champion_model_id="RULE_SYSTEM_V1",
            status_path=str(root / "auto_learning_status_live.json"),
            registry_path=str(root / "registry.json"),
            observations_path=str(root / "observations.jsonl"),
            outcomes_path=str(root / "outcomes.jsonl"),
            training_outcome_type="VIRTUAL_TRADE",
            auto_training_status_path=str(root / "training.json"),
            promotion_status_path=str(root / "promotion.json"),
            promotion_evidence_path=str(root / "promotion_evidence.json"),
            paper_canary_status_path=str(root / "canary.json"),
            strategy_policy_path=str(root / "strategy_policy.json"),
            source_stale_seconds=1800,
        )
        args.update(overrides)
        return AutoLearningStatusPublisher(**args)

    @staticmethod
    def _write(path: Path, document):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document))

    @staticmethod
    def _write_jsonl(path: Path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_missing_sources_produce_safe_rule_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            document = self._publisher(root).refresh()
            self.assertEqual(document["current_paper_champion"], "RULE_SYSTEM_V1")
            self.assertIsNone(document["current_challenger"])
            self.assertEqual(document["challenger_stage"], "NONE")
            self.assertEqual(document["safety"]["real_order_execution"], "IMPOSSIBLE")
            self.assertEqual(document["safety"]["real_order_authority"], "NONE")

    def test_atomic_status_file_is_valid_complete_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            publisher = self._publisher(root)
            document = publisher.refresh()
            stored = json.loads((root / "auto_learning_status_live.json").read_text())
            self.assertEqual(stored, document)
            self.assertFalse(list(root.glob(".auto_learning_status_live.json.*.tmp")))

    def test_training_inventory_counts_current_contract_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            observations = []
            outcomes = []
            for index, event in enumerate(("event-a", "event-a", "event-b")):
                candidate = f"candidate-{index}"
                observations.append({
                    "candidate_observation_id": candidate,
                    "experiment_contract_version": EXPERIMENT_CONTRACT_VERSION,
                    "market_event_id": event,
                })
                outcomes.append({
                    "candidate_observation_id": candidate,
                    "outcome_type": "VIRTUAL_TRADE",
                    "outcome_variant_id": "BASELINE",
                    "recorded_at_ms": index + 1,
                })
            self._write_jsonl(root / "observations.jsonl", observations)
            self._write_jsonl(root / "outcomes.jsonl", outcomes)
            document = self._publisher(root).refresh()
            self.assertEqual(document["training_data"]["completed_outcomes"], 3)
            self.assertEqual(document["training_data"]["independent_market_events"], 2)

    def test_shadow_evidence_populates_required_comparison_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "registry.json", {
                "current_champion_model_id": "RULE_SYSTEM_V1",
                "current_shadow_model_id": "MODEL_A",
                "current_paper_canary_model_id": None,
                "latest_model_id": "MODEL_A",
                "models": {"MODEL_A": {"model_id": "MODEL_A", "status": "SHADOW"}},
                "authority": {"paper_activation": "RULE_CHAMPION_ONLY"},
            })
            self._write(root / "promotion.json", {
                "model_id": "MODEL_A",
                "promotion_outcome": "EXTEND_SHADOW",
                "reason_codes": ["AVERAGE_R_LIFT_GATE_PENDING"],
                "evidence": {
                    "matched_candidate_outcomes": 311,
                    "independent_decision_events": 174,
                    "paired_disagreement_events": 96,
                    "average_r_lift_over_champion": 0.091,
                    "after_cost_expectancy": 0.073,
                    "champion_average_net_r": -0.018,
                },
            })
            document = self._publisher(root).refresh()
            forward = document["forward_comparison"]
            self.assertEqual(document["challenger_stage"], "SHADOW")
            self.assertEqual(forward["matched_candidate_outcomes"], 311)
            self.assertEqual(forward["independent_decision_events"], 174)
            self.assertEqual(forward["paired_disagreement_events"], 96)
            self.assertAlmostEqual(forward["average_r_lift_over_champion"], 0.091)
            self.assertEqual(document["governance"]["current_verdict"], "EXTEND_SHADOW")

    def test_canary_stage_and_paper_metrics_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "registry.json", {
                "current_champion_model_id": "RULE_SYSTEM_V1",
                "current_shadow_model_id": None,
                "current_paper_canary_model_id": "MODEL_A",
                "models": {"MODEL_A": {
                    "model_id": "MODEL_A", "status": "PAPER_CANARY",
                    "paper_canary_stage": "PAPER_CANARY_25_PERCENT",
                }},
                "authority": {"paper_activation": "PAPER_CANARY_25_PERCENT"},
            })
            self._write(root / "canary.json", {
                "status": "PAPER_CANARY_ACTIVE",
                "model_id": "MODEL_A",
                "paper_canary_stage": "PAPER_CANARY_25_PERCENT",
                "reason_codes": ["COLLECTING_INDEPENDENT_STAGE_EVIDENCE"],
                "next_stage": "PAPER_CANARY_50_PERCENT",
                "next_stage_gates": {"min_completed_trades": 150, "min_independent_events": 100},
                "metrics": {
                    "completed_trades": 90,
                    "independent_market_events": 65,
                    "average_net_r": 0.04,
                    "recent_average_net_r": 0.03,
                },
            })
            document = self._publisher(root).refresh()
            self.assertEqual(document["challenger_stage"], "PAPER_CANARY_25_PERCENT")
            self.assertEqual(document["governance"]["current_verdict"], "EXTEND_PAPER_CANARY")
            self.assertIn("35 new independent events", document["governance"]["next_automatic_action"])
            self.assertAlmostEqual(document["forward_comparison"]["challenger_average_net_r"], 0.04)

    def test_waiting_training_status_explains_next_automatic_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "training.json", {
                "status": "WAITING_FOR_DATA",
                "inventory": {"new_completed_outcomes": 800, "new_independent_market_events": 160},
                "thresholds": {"min_new_outcomes": 1000, "min_new_market_events": 200},
            })
            document = self._publisher(root).refresh()
            self.assertEqual(document["governance"]["current_verdict"], "COLLECT_MORE_DATA")
            self.assertIn("200 new completed outcomes", document["governance"]["next_automatic_action"])
            self.assertIn("40 new independent events", document["governance"]["next_automatic_action"])

    def test_plain_english_rollback_reason_is_operator_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "canary.json", {
                "status": "ROLLED_BACK",
                "model_id": "MODEL_A",
                "reason_codes": ["FEATURE_DRIFT_PSI_BREACH"],
            })
            self._write(root / "registry.json", {
                "current_champion_model_id": "RULE_SYSTEM_V1",
                "latest_model_id": "MODEL_A",
                "models": {"MODEL_A": {"status": "ROLLED_BACK"}},
                "authority": {"paper_activation": "RULE_CHAMPION_ONLY"},
            })
            document = self._publisher(root).refresh()
            self.assertIn("feature drift", document["governance"]["plain_english_reason"].lower())

    def test_console_contains_all_required_operator_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = self._publisher(Path(tmp)).refresh()
            text = AutoLearningStatusPublisher.render_console(document)
            for label in (
                "Current champion", "Current challenger", "Challenger stage",
                "Training status", "Qualified outcomes", "Independent events",
                "Comparison status", "Matched outcomes", "Disagreement events",
                "Market regimes", "Champion average R", "Challenger average R",
                "Lift", "Current verdict", "Reason", "Paper activation",
                "Real-order execution", "Next automatic action",
            ):
                self.assertIn(label, text)

    def test_telegram_body_escapes_dynamic_html(self):
        document = {
            "environment": "LIVE", "execution_mode": "SHADOW",
            "current_paper_champion": "RULE<ONE>", "current_challenger": None,
            "challenger_stage": "NONE", "training_data": {},
            "forward_comparison": {}, "governance": {}, "safety": {},
            "source_health": {},
        }
        body = AutoLearningStatusPublisher.render_telegram_body(document)
        self.assertIn("RULE&lt;ONE&gt;", body)
        self.assertNotIn("RULE<ONE>", body)
        self.assertTrue(body.startswith("<pre>"))

    def test_non_shadow_configuration_is_explicitly_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            document = self._publisher(
                Path(tmp), execution_mode="TRADE"
            ).refresh()
            self.assertEqual(document["safety"]["real_order_execution"], "NOT_SAFELY_BLOCKED")
            self.assertEqual(document["safety"]["phase6_startup_gate"], "BLOCKED_UNLESS_LIVE_SHADOW")

    def test_strategy_policy_summary_is_research_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "strategy_policy.json", {
                "status": "READY", "catalog_version": "CATALOG_V1",
                "recommendations": {"BREAKOUT": {"variant_id": "FAST"}},
                "activation": "RESEARCH_RECOMMENDATION_ONLY",
            })
            document = self._publisher(root).refresh()
            policy = document["strategy_policy"]
            self.assertEqual(policy["recommended_pattern_count"], 1)
            self.assertEqual(policy["activation"], "RESEARCH_RECOMMENDATION_ONLY")
            self.assertEqual(policy["real_order_authority"], "NONE")

    def test_stale_source_is_visible_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "promotion.json", {
                "generated_at_ms": int(time.time() * 1000) - 100_000,
                "promotion_outcome": "HOLD",
            })
            document = self._publisher(root, source_stale_seconds=60).refresh()
            self.assertIn("promotion_controller", document["source_health"]["warnings"])
            self.assertEqual(
                document["source_health"]["sources"]["promotion_controller"]["status"],
                "STALE",
            )

    def test_registry_training_counts_are_not_lowered_by_empty_live_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "registry.json", {
                "current_champion_model_id": "RULE_SYSTEM_V1",
                "current_shadow_model_id": "MODEL_A",
                "latest_model_id": "MODEL_A",
                "models": {"MODEL_A": {
                    "status": "SHADOW", "training_rows": 8462,
                    "independent_event_count": 1174,
                }},
                "authority": {},
            })
            document = self._publisher(root).refresh()
            self.assertEqual(document["training_data"]["completed_outcomes"], 8462)
            self.assertEqual(document["training_data"]["independent_market_events"], 1174)

    def test_split_execution_worker_learning_command_is_remote_read_only(self):
        source = Path("workers/execution_worker.py").read_text(encoding="utf-8")
        self.assertIn('"/learning"', source)
        self.assertIn("request_learning_status", source)
        self.assertNotIn("AutoLearningStatusPublisher", source)
        self.assertNotIn("from learning", source)

    def test_real_order_authority_is_never_inferred_from_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write(root / "registry.json", {
                "current_champion_model_id": "MODEL_A",
                "models": {"MODEL_A": {"status": "PAPER_CHAMPION"}},
                "authority": {"paper_activation": "PAPER_CHAMPION_MODEL_SELECTION", "real_order_authority": "ENABLED"},
            })
            document = self._publisher(root).refresh()
            self.assertEqual(document["safety"]["real_order_authority"], "NONE")
            self.assertEqual(document["safety"]["real_order_execution"], "IMPOSSIBLE")


if __name__ == "__main__":
    unittest.main()
