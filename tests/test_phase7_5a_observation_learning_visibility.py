import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from communication.observation_client import (
    ObservationClient,
    ObservationClientError,
)
from communication.observation_server import ObservationHTTPServer
from learning.operator_status import AutoLearningStatusPublisher
from workers.execution_worker import ExecutionWorker


class Phase75AObservationLearningVisibilityTests(unittest.TestCase):
    def test_authenticated_learning_status_round_trip(self):
        target = SimpleNamespace(
            learning_operator_status=lambda: {
                "status": "OK",
                "order_authority": "NONE",
                "document": {"current_paper_champion": "RULE_SYSTEM_V1"},
                "telegram_body": "<pre>NBOT LEARNING STATUS</pre>",
            }
        )
        server = ObservationHTTPServer(
            target=target,
            host="127.0.0.1",
            port=0,
            auth_token="secret",
        )
        _, port = server.start()
        try:
            client = ObservationClient(
                host="127.0.0.1",
                port=port,
                auth_token="secret",
            )
            result = client.request_learning_status()
            self.assertEqual(result["status"], "OK")
            self.assertEqual(result["order_authority"], "NONE")
            self.assertEqual(
                result["document"]["current_paper_champion"],
                "RULE_SYSTEM_V1",
            )
        finally:
            server.stop()

    def test_learning_status_requires_existing_control_authentication(self):
        target = SimpleNamespace(
            learning_operator_status=lambda: {
                "status": "OK",
                "order_authority": "NONE",
                "document": {},
                "telegram_body": "<pre>OK</pre>",
            }
        )
        server = ObservationHTTPServer(
            target=target,
            host="127.0.0.1",
            port=0,
            auth_token="secret",
        )
        _, port = server.start()
        try:
            client = ObservationClient(
                host="127.0.0.1",
                port=port,
                auth_token="wrong",
            )
            with self.assertRaises(ObservationClientError):
                client.request_learning_status()
        finally:
            server.stop()

    def test_execution_learning_command_is_thin_remote_proxy(self):
        worker = object.__new__(ExecutionWorker)
        worker.system_log = Mock()
        worker.observation_client = Mock()
        worker.observation_client.request_learning_status.return_value = {
            "status": "OK",
            "order_authority": "NONE",
            "document": {},
            "telegram_body": "<pre>REMOTE LEARNING</pre>",
        }

        with patch("workers.execution_worker.send_info") as send_info:
            worker._handle_operator_command("/learning")

        worker.observation_client.request_learning_status.assert_called_once_with()
        send_info.assert_called_once_with(
            "LEARNING STATUS",
            "<pre>REMOTE LEARNING</pre>",
        )

    def test_learning_unavailable_does_not_change_execution_state(self):
        worker = object.__new__(ExecutionWorker)
        worker.system_log = Mock()
        worker.observation_client = Mock()
        worker.observation_client.request_learning_status.side_effect = (
            ObservationClientError("down")
        )

        with patch("workers.execution_worker.send_warning") as warning:
            worker._handle_operator_command("/learning")

        warning.assert_called_once()
        title, body = warning.call_args.args
        self.assertEqual(title, "LEARNING STATUS UNAVAILABLE")
        self.assertIn("unchanged", body.lower())

    def test_phase7_status_uses_trainer_qualified_cohort_and_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = 1_786_510_000_000
            (root / "training.json").write_text(json.dumps({
                "generated_at_ms": now,
                "phase": "7.4",
                "status": "WAITING_FOR_DATA",
                "inventory": {
                    "new_completed_outcomes": 1807,
                    "new_independent_market_events": 54,
                    "issue_count": 10,
                },
                "thresholds": {
                    "min_new_outcomes": 1000,
                    "min_new_market_events": 200,
                },
            }))
            (root / "promotion.json").write_text(json.dumps({
                "generated_at_ms": now,
                "phase": "7.5",
                "status": "WAITING_FOR_SHADOW_CHALLENGER",
                "promotion_outcome": "HOLD",
                "reason_codes": ["NO_CURRENT_SHADOW_MODEL"],
                "thresholds": {
                    "min_matched_outcomes": 1000,
                    "min_independent_events": 150,
                    "min_disagreement_events": 75,
                    "min_regime_events": 20,
                    "min_distinct_market_regimes": 2,
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
            training = document["training_data"]
            forward = document["forward_comparison"]
            self.assertEqual(training["completed_outcomes"], 1807)
            self.assertEqual(training["required_outcomes"], 1000)
            self.assertEqual(training["independent_market_events"], 54)
            self.assertEqual(
                training["required_independent_market_events"], 200
            )
            self.assertEqual(
                training["count_basis"],
                "AUTO_TRAINING_QUALIFIED_COHORT",
            )
            self.assertEqual(forward["matched_required"], 1000)
            self.assertEqual(forward["independent_required"], 150)
            self.assertEqual(forward["disagreement_required"], 75)
            self.assertEqual(forward["market_regimes_required"], 2)

            rendered = publisher.render_console(document)
            self.assertIn("1,807 / 1,000 [PASS]", rendered)
            self.assertIn("54 / 200 [WAIT]", rendered)
            self.assertIn("0 / 1,000 [WAIT]", rendered)
            self.assertIn("0 / 150 [WAIT]", rendered)
            self.assertIn("0 / 75 [WAIT]", rendered)
            self.assertIn("0 / 2 [WAIT]", rendered)

    def test_phase7_promotion_lock_is_plain_english_success_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "registry.json").write_text(json.dumps({
                "current_champion_model_id": "RULE_SYSTEM_V1",
                "current_shadow_model_id": "MODEL_A",
                "latest_model_id": "MODEL_A",
                "models": {"MODEL_A": {
                    "status": "SHADOW",
                    "training_rows": 1500,
                    "independent_event_count": 250,
                }},
            }))
            (root / "promotion.json").write_text(json.dumps({
                "status": "EVALUATED",
                "model_id": "MODEL_A",
                "promotion_outcome": "EXTEND_SHADOW",
                "reason_codes": ["PHASE7_PAPER_PROMOTION_LOCKED"],
                "gates": {"all_gates_passed": True, "checks": {}},
            }))
            publisher = AutoLearningStatusPublisher(
                environment="LIVE",
                execution_mode="SHADOW",
                default_champion_model_id="RULE_SYSTEM_V1",
                status_path=str(root / "status.json"),
                registry_path=str(root / "registry.json"),
                observations_path=str(root / "observations.jsonl"),
                outcomes_path=str(root / "outcomes.jsonl"),
                training_outcome_type="VIRTUAL_TRADE",
                auto_training_status_path=str(root / "training.json"),
                promotion_status_path=str(root / "promotion.json"),
                promotion_evidence_path=str(root / "promotion-evidence.json"),
                paper_canary_status_path=str(root / "canary.json"),
                strategy_policy_path=str(root / "strategy.json"),
                source_stale_seconds=1800,
            )
            document = publisher.refresh()
            self.assertEqual(
                document["governance"]["current_verdict"],
                "EXTEND_SHADOW",
            )
            self.assertIn(
                "passed the Phase-7 forward gates",
                document["governance"]["plain_english_reason"],
            )
            self.assertTrue(
                document["forward_comparison"]["all_gates_passed"]
            )


if __name__ == "__main__":
    unittest.main()
