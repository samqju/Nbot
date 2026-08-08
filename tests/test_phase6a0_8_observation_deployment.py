import json
import tempfile
import time
import unittest
from pathlib import Path

from communication.execution_outcome import ExecutionOutcome
from deploy.observation.install_services import render_units
from execution.outcome_builder import build_execution_outcome
from learning.automatic_rollback import RuntimeRollbackEvidenceEvaluator
from learning.paper_canary import AutomaticPaperCanaryController, PaperCanaryRouter
from learning.paper_execution_evidence import iter_paper_execution_evidence
from observation.execution_outcome_receiver import LocalExecutionOutcomeReceiver


class Phase6A08ObservationDeploymentTests(unittest.TestCase):
    def _candidate_outcome_row(self, *, model_id="MODEL_A", net_r=0.25):
        now = int(time.time() * 1000)
        return {
            "schema_version": 2,
            "observation_type": "CANDIDATE_OUTCOME",
            "outcome_type": "EXECUTED_TRADE",
            "recorded_at_ms": now,
            "decision_batch_id": "batch-a",
            "market_event_id": "event-a",
            "candidate_observation_id": "candidate-a",
            "payload": {
                "closed_at_ms": now,
                "net_r": net_r,
                "selection_authority": "PAPER_CANARY",
                "paper_canary_model_id": model_id,
                "execution_outcome_id": "OUT-A",
            },
        }

    def test_evidence_adapter_accepts_candidate_outcome(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "outcomes.jsonl"
            path.write_text(json.dumps(self._candidate_outcome_row()) + "\n")
            rows = list(iter_paper_execution_evidence(path))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["net_r"], 0.25)
            self.assertEqual(rows[0]["paper_canary_model_id"], "MODEL_A")
            self.assertEqual(rows[0]["market_event_id"], "event-a")

    def test_evidence_adapter_keeps_legacy_paper_trade_compatibility(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "trades.jsonl"
            path.write_text(json.dumps({
                "trade_id": "T1",
                "closed_at_ms": 123,
                "net_r": -0.5,
                "selection_authority": "PAPER_CANARY",
                "paper_canary_model_id": "MODEL_A",
                "market_event_id": "event-legacy",
            }) + "\n")
            rows = list(iter_paper_execution_evidence(path))
            self.assertEqual(rows[0]["trade_id"], "T1")
            self.assertEqual(rows[0]["net_r"], -0.5)

    def test_receiver_preserves_canary_governance_fields(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "outcomes.jsonl"
            receiver = LocalExecutionOutcomeReceiver(
                candidate_outcomes_path=str(path),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            outcome = ExecutionOutcome.create(
                outcome_id="OUT-CANARY", proposal_id="PROP-CANARY",
                environment="LIVE", execution_mode="SHADOW",
                symbol="BTCUSDT", side="LONG", entry_price=100.0,
                exit_price=101.0, quantity=1.0, realized_pnl_usd=1.0,
                initial_risk_usd=2.0, r_multiple=0.5, mae_usd=-0.5,
                mfe_usd=1.5, mae_r=-0.25, mfe_r=0.75,
                entry_timestamp=1000, closed_timestamp=2000, holding_seconds=1,
                candidate_observation_id="candidate-canary",
                decision_batch_id="batch-canary", market_event_id="event-canary",
                model_version="MODEL_A", selection_authority="PAPER_CANARY",
                paper_canary_model_id="MODEL_A", paper_risk_multiplier=1.0,
                paper_allocation_id="CANARY-A",
            )
            receiver.receive(outcome)
            row = json.loads(path.read_text())
            payload = row["payload"]
            self.assertEqual(payload["closed_at_ms"], 2000)
            self.assertEqual(payload["net_r"], 0.5)
            self.assertEqual(payload["selection_authority"], "PAPER_CANARY")
            self.assertEqual(payload["paper_canary_model_id"], "MODEL_A")
            self.assertEqual(payload["paper_allocation_id"], "CANARY-A")


    def test_canary_router_daily_count_uses_candidate_outcomes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outcomes = root / "outcomes.jsonl"
            outcomes.write_text(json.dumps(self._candidate_outcome_row()) + "\n")
            router = PaperCanaryRouter(
                enabled=True, execution_mode="SHADOW", environment="LIVE",
                registry_path=str(root / "registry.json"),
                default_champion_model_id="RULE_SYSTEM_V1",
                decisions_path=str(root / "decisions.jsonl"),
                trades_path=str(outcomes), allocation_fraction=0.10,
                risk_multiplier=1.0, max_trades_per_utc_day=5,
                minimum_model_probability=0.50,
            )
            self.assertEqual(router._completed_today("MODEL_A"), 1)

    def test_canary_controller_metrics_use_candidate_outcomes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outcomes = root / "outcomes.jsonl"
            outcomes.write_text(json.dumps(self._candidate_outcome_row(net_r=0.4)) + "\n")
            controller = AutomaticPaperCanaryController(
                enabled=True, execution_mode="SHADOW", environment="LIVE",
                registry_path=str(root / "registry.json"), trades_path=str(outcomes),
                status_path=str(root / "status.json"), lock_path=str(root / "lock"),
                default_champion_model_id="RULE_SYSTEM_V1", min_completed_trades=1,
                max_drawdown_r=5.0, max_losing_streak=5, min_average_net_r=-0.1,
                recent_trade_window=10, min_recent_average_net_r=-0.1,
            )
            metrics = controller._metrics("MODEL_A")
            self.assertEqual(metrics["completed_trades"], 1)
            self.assertEqual(metrics["independent_market_events"], 1)
            self.assertAlmostEqual(metrics["average_net_r"], 0.4)

    def test_rollback_evaluator_uses_candidate_outcomes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outcomes = root / "outcomes.jsonl"
            outcomes.write_text(json.dumps(self._candidate_outcome_row(net_r=-0.2)) + "\n")
            evaluator = RuntimeRollbackEvidenceEvaluator(
                trades_path=str(outcomes), decisions_path=str(root / "decisions.jsonl"),
                outcomes_path=str(root / "virtual.jsonl"),
                observations_path=str(root / "observations.jsonl"),
                recent_trade_window=10, max_drawdown_r=5.0, max_losing_streak=5,
                min_completed_trades=1, min_average_net_r=-1.0,
                min_recent_average_net_r=-1.0, min_paired_events=1,
                min_average_r_lift=-1.0, min_runtime_decisions=1,
                max_prediction_failures=3, max_prediction_failure_rate=1.0,
                min_calibration_outcomes=1, max_brier_score=1.0,
                max_calibration_gap=1.0, min_drift_observations=1,
                max_feature_psi=10.0,
            )
            metrics = evaluator._paper_metrics("MODEL_A", "PAPER_CANARY", 1)
            self.assertEqual(metrics["completed_trades"], 1)
            self.assertAlmostEqual(metrics["average_net_r"], -0.2)

    def test_outcome_builder_preserves_paper_governance_identity(self):
        outcome = build_execution_outcome(
            open_position={
                "symbol": "BTCUSDT", "side": "LONG", "entry_price": 100.0,
                "qty": 1.0, "entry_timestamp": 1000, "initial_risk_usd": 2.0,
                "candidate_observation_id": "candidate-build",
                "model_version": "MODEL_A", "selection_authority": "PAPER_CANARY",
                "paper_canary_model_id": "MODEL_A", "paper_risk_multiplier": 1.0,
                "paper_allocation_id": "CANARY-BUILD",
            },
            environment="LIVE", execution_mode="SHADOW", exit_price=101.0,
            realized_pnl_usd=1.0, exit_reason="TEST", closed_timestamp=2000,
        )
        self.assertEqual(outcome.paper_canary_model_id, "MODEL_A")
        self.assertEqual(outcome.paper_risk_multiplier, 1.0)
        self.assertEqual(outcome.paper_allocation_id, "CANARY-BUILD")

    def test_observation_side_no_longer_imports_paper_trades_path(self):
        strategy = Path("strategy/strategy.py").read_text()
        controller = Path("scripts/learning/paper_canary_controller.py").read_text()
        self.assertNotIn("PAPER_TRADES_PATH", strategy)
        self.assertNotIn("PAPER_TRADES_PATH", controller)
        self.assertIn("trades_path=CANDIDATE_OUTCOMES_PATH", strategy)
        self.assertIn("trades_path=CANDIDATE_OUTCOMES_PATH", controller)

    def test_portable_templates_have_no_provider_specific_paths(self):
        for path in Path("deploy/observation").glob("*.service.in"):
            text = path.read_text()
            self.assertNotIn("/home/ubuntu", text)
            self.assertNotIn("/root/Nbot", text)
            self.assertNotIn("%h/nbot", text)
            self.assertIn("@NBOT_REPO@", text)
            self.assertIn("@NBOT_PYTHON@", text)
            self.assertIn("@NBOT_USER@", text)

    def test_service_renderer_uses_explicit_machine_parameters(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            repo = root / "repo"
            bin_dir = root / "venv" / "bin"
            repo.mkdir()
            bin_dir.mkdir(parents=True)
            python = bin_dir / "python"
            python.write_text("#!/bin/sh\n")
            dest = root / "units"
            written = render_units(
                repo=repo, python=python, user="nbot-user", destination=dest
            )
            self.assertEqual(len(written), 4)
            observation = (dest / "nbot-observation.service").read_text()
            self.assertIn(f"WorkingDirectory={repo.resolve()}", observation)
            self.assertIn(f"ExecStart={python} run_observation.py", observation)
            self.assertIn("User=nbot-user", observation)

    def test_service_renderer_preserves_virtualenv_launcher_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            repo = root / "repo"
            bin_dir = root / "venv" / "bin"
            repo.mkdir()
            bin_dir.mkdir(parents=True)
            real_python = bin_dir / "python3.12"
            real_python.write_text("#!/bin/sh\n")
            python = bin_dir / "python"
            python.symlink_to(real_python.name)
            dest = root / "units"
            render_units(
                repo=repo, python=python, user="nbot-user", destination=dest
            )
            observation = (dest / "nbot-observation.service").read_text()
            self.assertIn(f"ExecStart={python} run_observation.py", observation)
            self.assertNotIn(
                f"ExecStart={real_python} run_observation.py", observation
            )


if __name__ == "__main__":
    unittest.main()
