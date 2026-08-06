import hashlib
import json
import pickle
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from learning.automatic_rollback import RuntimeRollbackEvidenceEvaluator
from learning.model_registry import ModelRegistry
from learning.paper_canary import (
    AutomaticPaperCanaryController,
    PaperCanaryRouter,
)
from strategy.candidate import StrategyCandidate
from strategy.features import (
    CANDIDATE_FEATURE_SCHEMA_VERSION,
    CandidateFeatures,
)


FEATURES = (
    "short_range", "long_range", "trend_score", "wick_ratio_recent",
    "body_ratio_recent", "range_acceleration", "dist_high", "dist_low",
    "directional_consistency",
)


class IdentityScaler:
    def transform(self, values):
        return np.asarray(values, dtype=float)


class ConstantModel:
    def predict_proba(self, values):
        rows = len(values)
        return np.asarray([[0.2, 0.8]] * rows, dtype=float)


class Breakdown:
    def __init__(self, score):
        self.rule_score = score


class Phase512AutomaticRollbackTests(unittest.TestCase):
    def _artifact(self, path: Path, model_id: str, *, schema=None):
        artifact = {
            "artifact_schema_version": 1,
            "model_kind": "LOGISTIC_REGRESSION_BASELINE",
            "model_id": model_id,
            "feature_schema_version": (
                CANDIDATE_FEATURE_SCHEMA_VERSION if schema is None else schema
            ),
            "base_feature_names": FEATURES,
            "pattern_categories": ("RANGE_BREAKOUT",),
            "scaler": IdentityScaler(),
            "model": ConstantModel(),
            "runtime_activation": "DISABLED",
        }
        data = pickle.dumps(artifact)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def _register(self, root: Path, model_id: str, parent="RULE_SYSTEM_V1"):
        artifact = root / f"{model_id}.pkl"
        checksum = self._artifact(artifact, model_id)
        registry = ModelRegistry(
            path=str(root / "registry.json"), environment="LIVE",
            default_champion_model_id="RULE_SYSTEM_V1",
        )
        registry.initialize()
        registry.register_training({
            "model_id": model_id,
            "parent_model_id": parent,
            "artifact_path": str(artifact),
            "artifact_checksum_sha256": checksum,
            "feature_schema_version": CANDIDATE_FEATURE_SCHEMA_VERSION,
            "dataset_snapshot_path": str(root / f"snapshot-{model_id}"),
            "training_completed_at_ms": int(time.time() * 1000),
        })
        registry.update_model(model_id, status="OFFLINE_VALIDATED")
        return registry, artifact

    def _to_canary(self, registry, model_id):
        registry.activate_next_shadow_challenger()
        registry.apply_promotion_decision(
            model_id, decision="PROMOTE_TO_PAPER_CANARY",
            evidence={}, gate_report={}, reason_codes=["TEST"],
        )

    def _to_champion(self, registry, model_id):
        self._to_canary(registry, model_id)
        registry.advance_paper_canary_stage(
            model_id, target_stage="PAPER_CANARY_25_PERCENT",
            evidence={}, reason_codes=["TEST"],
        )
        registry.advance_paper_canary_stage(
            model_id, target_stage="PAPER_CANARY_50_PERCENT",
            evidence={}, reason_codes=["TEST"],
        )
        registry.promote_paper_canary_to_champion(
            model_id, evidence={}, reason_codes=["TEST"],
        )

    @staticmethod
    def _candidate(observation_id="candidate-1"):
        return StrategyCandidate(
            symbol="BTCUSDT", direction="LONG", score=0.8,
            pattern="RANGE_BREAKOUT", bucket=1,
            features=CandidateFeatures(
                short_range=0.8, long_range=0.02, trend_score=5.0,
                wick_ratio_recent=0.2, body_ratio_recent=0.8,
                range_acceleration=1.1, dist_high=0.01, dist_low=0.02,
                directional_consistency=0.7,
            ),
            score_breakdown=Breakdown(0.8), reference_price=100.0,
            observation_id=observation_id, decision_batch_id="batch",
            market_event_id="event", strategy_version="RULES_V1",
            strategy_variant_id="BASELINE", model_version="RULE_SYSTEM_V1",
        )

    def _evaluator(self, root: Path, **overrides):
        args = dict(
            trades_path=str(root / "trades.jsonl"),
            decisions_path=str(root / "decisions.jsonl"),
            outcomes_path=str(root / "outcomes.jsonl"),
            observations_path=str(root / "observations.jsonl"),
            recent_trade_window=5, max_drawdown_r=5.0,
            max_losing_streak=5, min_completed_trades=3,
            min_average_net_r=-0.10, min_recent_average_net_r=-0.25,
            min_paired_events=2, min_average_r_lift=-0.15,
            min_runtime_decisions=3, max_prediction_failures=2,
            max_prediction_failure_rate=0.50,
            min_calibration_outcomes=2, max_brier_score=0.25,
            max_calibration_gap=0.25, min_drift_observations=2,
            max_feature_psi=0.25,
        )
        args.update(overrides)
        return RuntimeRollbackEvidenceEvaluator(**args)

    @staticmethod
    def _write_jsonl(path: Path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def _record(self, registry, model_id):
        return registry.get_model(model_id)

    def test_artifact_failure_requires_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._register(root, "MODEL_A")
            artifact.unlink()
            report = self._evaluator(root).evaluate(
                model_id="MODEL_A", role="PAPER_CANARY",
                record=self._record(registry, "MODEL_A"),
                started_at_ms=0, benchmark_model_id="RULE_SYSTEM_V1",
            )
            self.assertTrue(report["rollback_required"])
            self.assertIn("MODEL_ARTIFACT_UNAVAILABLE", report["reason_codes"])

    def test_prediction_failure_threshold_requires_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._register(root, "MODEL_A")
            self._write_jsonl(root / "decisions.jsonl", [
                {"observed_at_ms": i + 1, "evaluated_model_id": "MODEL_A",
                 "health_failure_code": "PREDICTION_FAILURE"}
                for i in range(3)
            ])
            report = self._evaluator(root).evaluate(
                model_id="MODEL_A", role="PAPER_CANARY",
                record=self._record(registry, "MODEL_A"),
                started_at_ms=0, benchmark_model_id="RULE_SYSTEM_V1",
            )
            self.assertIn("PREDICTION_FAILURE_THRESHOLD_BREACH", report["reason_codes"])

    def test_required_feature_and_schema_fail_closed_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._register(root, "MODEL_A")
            self._write_jsonl(root / "decisions.jsonl", [
                {"observed_at_ms": 1, "evaluated_model_id": "MODEL_A",
                 "health_failure_code": "REQUIRED_FEATURE_MISSING"},
                {"observed_at_ms": 2, "evaluated_model_id": "MODEL_A",
                 "health_failure_code": "FEATURE_SCHEMA_MISMATCH"},
            ])
            report = self._evaluator(root).evaluate(
                model_id="MODEL_A", role="PAPER_CANARY",
                record=self._record(registry, "MODEL_A"),
                started_at_ms=0, benchmark_model_id="RULE_SYSTEM_V1",
            )
            self.assertIn("REQUIRED_FEATURE_MISSING", report["reason_codes"])
            self.assertIn("FEATURE_SCHEMA_MISMATCH", report["reason_codes"])

    def test_material_independent_underperformance_requires_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._register(root, "MODEL_A")
            decisions, outcomes = [], []
            for i in range(2):
                decisions.append({
                    "observed_at_ms": i + 1, "evaluated_model_id": "MODEL_A",
                    "evaluated_model_candidate_observation_id": f"m{i}",
                    "benchmark_candidate_observation_id": f"b{i}",
                    "evaluated_model_probability": 0.8,
                    "market_event_id": f"event-{i}",
                })
                for cid, value in ((f"m{i}", -0.4), (f"b{i}", 0.0)):
                    outcomes.append({"candidate_observation_id": cid,
                        "outcome_type": "VIRTUAL_TRADE",
                        "payload": {"net_exit_r": value}})
            self._write_jsonl(root / "decisions.jsonl", decisions)
            self._write_jsonl(root / "outcomes.jsonl", outcomes)
            report = self._evaluator(root).evaluate(
                model_id="MODEL_A", role="PAPER_CANARY",
                record=self._record(registry, "MODEL_A"), started_at_ms=0,
                benchmark_model_id="RULE_SYSTEM_V1",
            )
            self.assertIn("MATERIAL_CHAMPION_UNDERPERFORMANCE", report["reason_codes"])

    def test_calibration_deterioration_requires_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._register(root, "MODEL_A")
            self._write_jsonl(root / "decisions.jsonl", [
                {"observed_at_ms": i + 1, "evaluated_model_id": "MODEL_A",
                 "evaluated_model_candidate_observation_id": f"m{i}",
                 "evaluated_model_probability": 0.99,
                 "market_event_id": f"event-{i}"}
                for i in range(2)
            ])
            self._write_jsonl(root / "outcomes.jsonl", [
                {"candidate_observation_id": f"m{i}",
                 "outcome_type": "VIRTUAL_TRADE", "payload": {"net_exit_r": -1.0}}
                for i in range(2)
            ])
            report = self._evaluator(root, max_calibration_gap=0.10).evaluate(
                model_id="MODEL_A", role="PAPER_CANARY",
                record=self._record(registry, "MODEL_A"), started_at_ms=0,
                benchmark_model_id="RULE_SYSTEM_V1",
            )
            self.assertIn("BRIER_SCORE_DETERIORATION", report["reason_codes"])
            self.assertIn("CALIBRATION_GAP_DETERIORATION", report["reason_codes"])

    def test_feature_drift_uses_immutable_training_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._register(root, "MODEL_A")
            snapshot = root / "snapshot-MODEL_A"
            train = []
            live = []
            decisions = []
            for i in range(20):
                base = {name: 0.01 + i * 0.0001 for name in FEATURES}
                train.append({"features": base, "rule_score": 0.5, "final_score": 0.5})
            for i in range(20):
                cid = f"live-{i}"
                base = {name: 10.0 + i for name in FEATURES}
                live.append({"candidate_observation_id": cid, "features": base,
                             "rule_score": 10.0, "final_score": 10.0})
                decisions.append({"observed_at_ms": i + 1,
                    "evaluated_model_id": "MODEL_A",
                    "evaluated_model_candidate_observation_id": cid})
            self._write_jsonl(snapshot / "training_dataset.jsonl", train)
            self._write_jsonl(root / "observations.jsonl", live)
            self._write_jsonl(root / "decisions.jsonl", decisions)
            report = self._evaluator(root, min_drift_observations=10).evaluate(
                model_id="MODEL_A", role="PAPER_CANARY",
                record=self._record(registry, "MODEL_A"), started_at_ms=0,
                benchmark_model_id="RULE_SYSTEM_V1",
            )
            self.assertIn("FEATURE_DRIFT_PSI_BREACH", report["reason_codes"])

    def _controller(self, root: Path):
        return AutomaticPaperCanaryController(
            enabled=True, execution_mode="SHADOW", environment="LIVE",
            registry_path=str(root / "registry.json"),
            trades_path=str(root / "trades.jsonl"),
            status_path=str(root / "status.json"), lock_path=str(root / "lock"),
            default_champion_model_id="RULE_SYSTEM_V1",
            min_completed_trades=3, max_drawdown_r=5.0,
            max_losing_streak=5, min_average_net_r=-0.10,
            recent_trade_window=5, min_recent_average_net_r=-0.25,
            decisions_path=str(root / "decisions.jsonl"),
            outcomes_path=str(root / "outcomes.jsonl"),
            observations_path=str(root / "observations.jsonl"),
            rollback_min_runtime_decisions=1,
            rollback_max_prediction_failures=1,
        )

    def test_canary_rollback_keeps_model_champion_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._register(root, "MODEL_A")
            self._to_champion(registry, "MODEL_A")
            _, artifact_b = self._register(root, "MODEL_B", parent="MODEL_A")
            self._to_canary(registry, "MODEL_B")
            artifact_b.unlink()
            result = self._controller(root).run_once()
            self.assertEqual(result["status"], "ROLLED_BACK")
            self.assertEqual(registry.current_champion_model_id(), "MODEL_A")
            self.assertIsNone(registry.current_paper_canary_model_id())

    def test_model_champion_rollback_restores_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._register(root, "MODEL_A")
            self._to_champion(registry, "MODEL_A")
            artifact.unlink()
            result = self._controller(root).run_once()
            self.assertEqual(result["status"], "PAPER_CHAMPION_ROLLED_BACK")
            self.assertEqual(registry.current_champion_model_id(), "RULE_SYSTEM_V1")
            self.assertEqual(registry.get_model("MODEL_A")["status"], "ROLLED_BACK")

    def test_model_champion_rollback_restores_previous_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._register(root, "MODEL_A")
            self._to_champion(registry, "MODEL_A")
            _, artifact_b = self._register(root, "MODEL_B", parent="MODEL_A")
            self._to_champion(registry, "MODEL_B")
            artifact_b.unlink()
            result = self._controller(root).run_once()
            self.assertEqual(result["restored_champion_model_id"], "MODEL_A")
            self.assertEqual(registry.current_champion_model_id(), "MODEL_A")

    def test_failed_atomic_champion_rollback_preserves_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._register(root, "MODEL_A")
            self._to_champion(registry, "MODEL_A")
            artifact.unlink()
            controller = self._controller(root)
            with patch.object(controller.registry, "_write", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    controller.run_once()
            self.assertEqual(registry.current_champion_model_id(), "MODEL_A")
            self.assertEqual(registry.get_model("MODEL_A")["status"], "PAPER_CHAMPION")

    def test_router_records_model_health_failure_for_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._register(root, "MODEL_A")
            self._to_canary(registry, "MODEL_A")
            artifact.write_bytes(artifact.read_bytes() + b"corrupt")
            router = PaperCanaryRouter(
                enabled=True, execution_mode="SHADOW", environment="LIVE",
                registry_path=str(root / "registry.json"),
                default_champion_model_id="RULE_SYSTEM_V1",
                decisions_path=str(root / "decisions.jsonl"),
                trades_path=str(root / "trades.jsonl"),
                allocation_fraction=0.10, risk_multiplier=1.0,
                max_trades_per_utc_day=5, minimum_model_probability=0.50,
            )
            batch = next(
                f"batch-{i}" for i in range(1000)
                if router._allocation(
                    model_id="MODEL_A", decision_batch_id=f"batch-{i}"
                )[1] < 0.10
            )
            candidate = self._candidate()
            route = router.route(
                candidates=[candidate], rule_candidate=candidate,
                decision_batch_id=batch, market_event_id="event",
                candle_bucket=1,
            )
            self.assertEqual(route.selection_authority, "RULES")
            row = json.loads((root / "decisions.jsonl").read_text().splitlines()[-1])
            self.assertEqual(row["evaluated_model_id"], "MODEL_A")
            self.assertEqual(row["health_failure_code"], "ARTIFACT_FAILURE")
            self.assertEqual(row["real_order_authority"], "NONE")

    def test_phase512_service_remains_outside_trading_engine(self):
        service = Path(
            "deploy/systemd/nbot-paper-canary-controller.service"
        ).read_text()
        self.assertIn("scripts.learning.paper_canary_controller --watch", service)
        self.assertNotIn("run.py", service)
        self.assertIn("IOSchedulingClass=idle", service)

    def test_rollback_history_has_no_real_order_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._register(root, "MODEL_A")
            self._to_champion(registry, "MODEL_A")
            artifact.unlink()
            self._controller(root).run_once()
            document = registry.load()
            self.assertEqual(document["rollback_history"][-1]["real_order_authority"], "NONE")
            self.assertEqual(document["authority"]["real_order_authority"], "NONE")


if __name__ == "__main__":
    unittest.main()
