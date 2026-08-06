import hashlib
import json
import pickle
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from learning.model_registry import ModelRegistry, ModelRegistryError
from learning.paper_canary import AutomaticPaperCanaryController, PaperCanaryRouter
from learning.strategy_policy import StrategyPolicyRecommender
from strategy.candidate import StrategyCandidate
from strategy.features import CandidateFeatures
from strategy.strategy_lab import build_approved_variant_catalog
from strategy.trade_intent import TradeIntent
from datetime import datetime, timezone


FEATURE_NAMES = (
    "short_range",
    "long_range",
    "trend_score",
    "wick_ratio_recent",
    "body_ratio_recent",
    "range_acceleration",
    "dist_high",
    "dist_low",
    "directional_consistency",
)
BASELINE_VARIANT = "VIRTUAL_FIXED_2R_24C_V1"
CATALOG_VERSION = "PHASE5_6_APPROVED_V1"


class IdentityScaler:
    def transform(self, values):
        return np.asarray(values, dtype=float)


class FirstFeatureProbabilityModel:
    def predict_proba(self, values):
        matrix = np.asarray(values, dtype=float)
        probability = np.clip(matrix[:, 0], 0.001, 0.999)
        return np.column_stack([1.0 - probability, probability])


class Breakdown:
    def __init__(self, score):
        self.rule_score = score


class MissionAlignmentCorrectionTests(unittest.TestCase):
    def _artifact(self, path: Path, model_id: str) -> str:
        payload = pickle.dumps({
            "artifact_schema_version": 1,
            "model_kind": "LOGISTIC_REGRESSION_BASELINE",
            "model_id": model_id,
            "base_feature_names": FEATURE_NAMES,
            "pattern_categories": ("RANGE_BREAKOUT",),
            "scaler": IdentityScaler(),
            "model": FirstFeatureProbabilityModel(),
            "runtime_activation": "DISABLED",
        })
        path.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest()

    def _registered_canary(self, root: Path, model_id="MODEL_A"):
        artifact = root / f"{model_id}.pkl"
        checksum = self._artifact(artifact, model_id)
        registry = ModelRegistry(
            path=str(root / "registry.json"),
            environment="LIVE",
            default_champion_model_id="RULE_SYSTEM_V1",
        )
        registry.register_training({
            "model_id": model_id,
            "parent_model_id": registry.current_champion_model_id(),
            "training_completed_at_ms": 10,
            "artifact_path": str(artifact),
            "artifact_checksum_sha256": checksum,
        })
        registry.update_model(model_id, status="OFFLINE_VALIDATED")
        registry.activate_next_shadow_challenger()
        registry.apply_promotion_decision(
            model_id,
            decision="PROMOTE_TO_PAPER_CANARY",
            evidence={"matched_candidate_outcomes": 1000},
            gate_report={"all_gates_passed": True},
            reason_codes=["ALL_GATES_PASSED"],
        )
        return registry, artifact

    def _candidate(self, symbol, rule_score, feature_score, observation_id):
        return StrategyCandidate(
            symbol=symbol,
            direction="LONG",
            score=rule_score,
            pattern="RANGE_BREAKOUT",
            bucket=1,
            features=CandidateFeatures(
                short_range=feature_score,
                long_range=0.02,
                trend_score=5.0,
                wick_ratio_recent=0.2,
                body_ratio_recent=0.8,
                range_acceleration=1.1,
                dist_high=0.01,
                dist_low=0.02,
                directional_consistency=0.7,
            ),
            score_breakdown=Breakdown(rule_score),
            reference_price=100.0,
            observation_id=observation_id,
            decision_batch_id="batch",
            market_event_id="event",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            model_version="RULE_SYSTEM_V1",
        )

    def _router(self, root: Path):
        return PaperCanaryRouter(
            enabled=True,
            execution_mode="SHADOW",
            environment="LIVE",
            registry_path=str(root / "registry.json"),
            default_champion_model_id="RULE_SYSTEM_V1",
            decisions_path=str(root / "routing.jsonl"),
            trades_path=str(root / "trades.jsonl"),
            allocation_fraction=0.10,
            risk_multiplier=1.0,
            max_trades_per_utc_day=100,
            minimum_model_probability=0.0,
        )

    def test_initial_canary_stage_is_explicit_ten_percent(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry, _ = self._registered_canary(Path(tmp))
            record = registry.get_model("MODEL_A")
            self.assertEqual(record["paper_canary_stage"], "PAPER_CANARY_10_PERCENT")
            self.assertEqual(record["paper_canary_allocation_fraction"], 0.10)
            self.assertEqual(record["paper_canary_risk_multiplier"], 1.0)

    def test_registry_only_allows_sequential_canary_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry, _ = self._registered_canary(Path(tmp))
            with self.assertRaises(ModelRegistryError):
                registry.advance_paper_canary_stage(
                    "MODEL_A",
                    target_stage="PAPER_CANARY_50_PERCENT",
                    evidence={},
                    reason_codes=[],
                )
            record = registry.advance_paper_canary_stage(
                "MODEL_A",
                target_stage="PAPER_CANARY_25_PERCENT",
                evidence={"independent_market_events": 20},
                reason_codes=["GATES_PASSED"],
            )
            self.assertEqual(record["paper_canary_allocation_fraction"], 0.25)

    def test_champion_promotion_retains_previous_champion_and_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._registered_canary(root)
            registry.advance_paper_canary_stage(
                "MODEL_A", target_stage="PAPER_CANARY_25_PERCENT",
                evidence={}, reason_codes=["PASS"],
            )
            registry.advance_paper_canary_stage(
                "MODEL_A", target_stage="PAPER_CANARY_50_PERCENT",
                evidence={}, reason_codes=["PASS"],
            )
            record = registry.promote_paper_canary_to_champion(
                "MODEL_A", evidence={}, reason_codes=["PASS"],
            )
            self.assertEqual(record["status"], "PAPER_CHAMPION")
            self.assertEqual(registry.current_champion_model_id(), "MODEL_A")
            self.assertEqual(registry.previous_champion_model_id(), "RULE_SYSTEM_V1")
            self.assertTrue(artifact.exists())
            self.assertEqual(record["real_order_authority"], "NONE")

    def test_second_champion_keeps_first_model_as_previous_standby(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, first_artifact = self._registered_canary(root, "MODEL_A")
            for stage in ("PAPER_CANARY_25_PERCENT", "PAPER_CANARY_50_PERCENT"):
                registry.advance_paper_canary_stage(
                    "MODEL_A", target_stage=stage, evidence={}, reason_codes=["PASS"]
                )
            registry.promote_paper_canary_to_champion(
                "MODEL_A", evidence={}, reason_codes=["PASS"]
            )
            registry, second_artifact = self._registered_canary(root, "MODEL_B")
            for stage in ("PAPER_CANARY_25_PERCENT", "PAPER_CANARY_50_PERCENT"):
                registry.advance_paper_canary_stage(
                    "MODEL_B", target_stage=stage, evidence={}, reason_codes=["PASS"]
                )
            registry.promote_paper_canary_to_champion(
                "MODEL_B", evidence={}, reason_codes=["PASS"]
            )
            self.assertEqual(registry.current_champion_model_id(), "MODEL_B")
            self.assertEqual(registry.previous_champion_model_id(), "MODEL_A")
            self.assertTrue(first_artifact.exists())
            self.assertTrue(second_artifact.exists())
            self.assertEqual(registry.get_model("MODEL_A")["status"], "PAPER_CHAMPION")

    def test_router_uses_model_champion_when_no_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registered_canary(root)
            registry.advance_paper_canary_stage(
                "MODEL_A", target_stage="PAPER_CANARY_25_PERCENT",
                evidence={}, reason_codes=["PASS"],
            )
            registry.advance_paper_canary_stage(
                "MODEL_A", target_stage="PAPER_CANARY_50_PERCENT",
                evidence={}, reason_codes=["PASS"],
            )
            registry.promote_paper_canary_to_champion(
                "MODEL_A", evidence={}, reason_codes=["PASS"],
            )
            rule = self._candidate("BTCUSDT", 0.9, 0.1, "rule")
            model = self._candidate("ETHUSDT", 0.8, 0.9, "model")
            route = self._router(root).route(
                candidates=[rule, model], rule_candidate=rule,
                decision_batch_id="batch-1", market_event_id="event-1",
                candle_bucket=1,
            )
            self.assertEqual(route.selection_authority, "PAPER_CHAMPION")
            self.assertEqual(route.candidate.observation_id, "model")
            self.assertEqual(route.risk_multiplier, 1.0)

    def test_stage_fraction_changes_deterministic_batch_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registered_canary(root)
            router = self._router(root)
            batch = next(
                f"batch-{index}" for index in range(10000)
                if 0.10 <= router._allocation(
                    model_id="MODEL_A", decision_batch_id=f"batch-{index}"
                )[1] < 0.25
            )
            rule = self._candidate("BTCUSDT", 0.9, 0.1, "rule")
            model = self._candidate("ETHUSDT", 0.8, 0.9, "model")
            ten = router.route(
                candidates=[rule, model], rule_candidate=rule,
                decision_batch_id=batch, market_event_id="event-1", candle_bucket=1,
            )
            self.assertEqual(ten.selection_authority, "RULES")
            registry.advance_paper_canary_stage(
                "MODEL_A", target_stage="PAPER_CANARY_25_PERCENT",
                evidence={}, reason_codes=["PASS"],
            )
            twenty_five = router.route(
                candidates=[rule, model], rule_candidate=rule,
                decision_batch_id=batch, market_event_id="event-2", candle_bucket=2,
            )
            self.assertEqual(twenty_five.selection_authority, "PAPER_CANARY")
            self.assertEqual(twenty_five.canary_stage, "PAPER_CANARY_25_PERCENT")

    def test_model_selected_trade_intent_cannot_reduce_risk(self):
        with self.assertRaises(ValueError):
            TradeIntent(
                symbol="BTCUSDT", direction="LONG", pattern="RANGE_BREAKOUT",
                entry_price=None, generated_at=datetime.now(timezone.utc),
                selection_authority="PAPER_CHAMPION",
                paper_canary_model_id="MODEL_A",
                paper_risk_multiplier=0.5,
            )

    def test_controller_advances_using_independent_event_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registered_canary(root)
            now = int(time.time() * 1000)
            (root / "trades.jsonl").write_text(json.dumps({
                "trade_id": "t1", "closed_at_ms": now, "net_r": 0.2,
                "selection_authority": "PAPER_CANARY",
                "paper_canary_model_id": "MODEL_A",
                "market_event_id": "event-1",
            }) + "\n")
            controller = AutomaticPaperCanaryController(
                enabled=True, execution_mode="SHADOW", environment="LIVE",
                registry_path=str(root / "registry.json"),
                trades_path=str(root / "trades.jsonl"),
                status_path=str(root / "status.json"), lock_path=str(root / "lock"),
                default_champion_model_id="RULE_SYSTEM_V1",
                min_completed_trades=1, max_drawdown_r=5.0,
                max_losing_streak=5, min_average_net_r=-0.1,
                recent_trade_window=1, min_recent_average_net_r=-0.1,
                stage_10_min_completed_trades=1,
                stage_10_min_independent_events=1,
                stage_25_min_completed_trades=100,
                stage_25_min_independent_events=100,
                stage_50_min_completed_trades=200,
                stage_50_min_independent_events=200,
            )
            result = controller.run_once()
            self.assertEqual(result["status"], "PAPER_CANARY_STAGE_ADVANCED")
            self.assertEqual(
                registry.get_model("MODEL_A")["paper_canary_stage"],
                "PAPER_CANARY_25_PERCENT",
            )

    def test_controller_promotes_fifty_percent_canary_to_champion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registered_canary(root)
            registry.advance_paper_canary_stage(
                "MODEL_A", target_stage="PAPER_CANARY_25_PERCENT",
                evidence={}, reason_codes=["PASS"],
            )
            registry.advance_paper_canary_stage(
                "MODEL_A", target_stage="PAPER_CANARY_50_PERCENT",
                evidence={}, reason_codes=["PASS"],
            )
            now = int(time.time() * 1000)
            (root / "trades.jsonl").write_text(json.dumps({
                "trade_id": "t1", "closed_at_ms": now, "net_r": 0.2,
                "selection_authority": "PAPER_CANARY",
                "paper_canary_model_id": "MODEL_A",
                "market_event_id": "event-1",
            }) + "\n")
            controller = AutomaticPaperCanaryController(
                enabled=True, execution_mode="SHADOW", environment="LIVE",
                registry_path=str(root / "registry.json"),
                trades_path=str(root / "trades.jsonl"),
                status_path=str(root / "status.json"), lock_path=str(root / "lock"),
                default_champion_model_id="RULE_SYSTEM_V1",
                min_completed_trades=1, max_drawdown_r=5.0,
                max_losing_streak=5, min_average_net_r=-0.1,
                recent_trade_window=1, min_recent_average_net_r=-0.1,
                stage_50_min_completed_trades=1,
                stage_50_min_independent_events=1,
            )
            result = controller.run_once()
            self.assertEqual(result["status"], "PAPER_CHAMPION_PROMOTED")
            self.assertEqual(registry.current_champion_model_id(), "MODEL_A")
            self.assertEqual(result["real_order_authority"], "NONE")

    def test_strategy_policy_ignores_unapproved_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outcomes = root / "outcomes.jsonl"
            rows = []
            for event_index in range(2):
                for variant_id, value in (
                    (BASELINE_VARIANT, 0.03),
                    ("VIRTUAL_BREAKOUT_WIDE_2_5R_36C_V1", 0.20),
                    ("ROGUE_RANDOM_99R", 99.0),
                ):
                    rows.append({
                        "outcome_type": "VIRTUAL_STRATEGY_VARIANT",
                        "outcome_variant_id": variant_id,
                        "candidate_observation_id": f"c-{event_index}-{variant_id}",
                        "market_event_id": f"event-{event_index}",
                        "recorded_at_ms": event_index,
                        "payload": {
                            "pattern": "RANGE_BREAKOUT",
                            "strategy_lab_catalog_version": CATALOG_VERSION,
                            "net_exit_r": value,
                        },
                    })
            outcomes.write_text("".join(json.dumps(row) + "\n" for row in rows))
            report = StrategyPolicyRecommender(
                outcomes_path=str(outcomes),
                recommendation_path=str(root / "recommendation.json"),
                catalog_version=CATALOG_VERSION,
                approved_catalog=build_approved_variant_catalog(
                    baseline_variant_id=BASELINE_VARIANT,
                    baseline_target_r=2.0,
                    baseline_max_candles=24,
                ),
                min_independent_events=2,
                min_average_net_r=0.02,
            ).refresh()
            recommendation = report["recommendations"]["RANGE_BREAKOUT"]
            self.assertEqual(
                recommendation["selected_variant_id"],
                "VIRTUAL_BREAKOUT_WIDE_2_5R_36C_V1",
            )
            self.assertNotIn("ROGUE_RANDOM_99R", report["approved_variant_ids"])
            self.assertEqual(report["issues"]["unapproved_variant_ignored"], 2)
            self.assertEqual(report["real_order_authority"], "NONE")

    def test_strategy_policy_retains_approved_baseline_without_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outcomes = root / "outcomes.jsonl"
            outcomes.write_text(json.dumps({
                "outcome_type": "VIRTUAL_TRADE",
                "outcome_variant_id": BASELINE_VARIANT,
                "candidate_observation_id": "c1",
                "market_event_id": "e1",
                "recorded_at_ms": 1,
                "payload": {
                    "pattern": "MEAN_REVERSION",
                    "strategy_lab_catalog_version": CATALOG_VERSION,
                    "net_exit_r": 0.01,
                },
            }) + "\n")
            report = StrategyPolicyRecommender(
                outcomes_path=str(outcomes),
                recommendation_path=str(root / "recommendation.json"),
                catalog_version=CATALOG_VERSION,
                approved_catalog=build_approved_variant_catalog(
                    baseline_variant_id=BASELINE_VARIANT,
                    baseline_target_r=2.0,
                    baseline_max_candles=24,
                ),
                min_independent_events=10,
                min_average_net_r=0.02,
            ).refresh()
            recommendation = report["recommendations"]["MEAN_REVERSION"]
            self.assertEqual(recommendation["selected_variant_id"], BASELINE_VARIANT)
            self.assertEqual(recommendation["status"], "COLLECT_MORE_DATA")
            self.assertEqual(recommendation["paper_authority"], "UNCHANGED")


if __name__ == "__main__":
    unittest.main()
