import hashlib
import json
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np

from learning.model_artifact_scorer import (
    RegisteredModelArtifactScorer,
    RegisteredModelScoringError,
)
from learning.model_registry import ModelRegistry
from learning.shadow_decision_testing import (
    ChampionChallengerShadowTester,
    ShadowDecisionEvaluator,
)
from strategy.candidate import StrategyCandidate
from strategy.decision_cycle import FiveMinuteDecisionCycleCoordinator
from strategy.experiment_contract import build_experiment_context
from strategy.features import CandidateFeatures


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


class Phase59ContinuousShadowTestingTests(unittest.TestCase):
    def _context(self, batch, event, bucket, trend="UP"):
        return build_experiment_context(
            decision_batch_id=batch,
            market_event_id=event,
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=bucket,
            structure_fingerprint={
                "structure": "RANGE_BREAKOUT",
                "trend": trend,
                "volatility": "HIGH" if trend == "UP" else "LOW",
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

    def _candidate(
        self,
        symbol,
        rule_score,
        feature_score,
        observation_id,
        batch="batch-1",
        event="event-1",
        bucket=1,
        direction="LONG",
        pattern="RANGE_BREAKOUT",
        trend="UP",
    ):
        features = CandidateFeatures(
            short_range=feature_score,
            long_range=0.02,
            trend_score=5.0,
            wick_ratio_recent=0.2,
            body_ratio_recent=0.8,
            range_acceleration=1.1,
            dist_high=0.01,
            dist_low=0.02,
            directional_consistency=0.7,
        )
        return StrategyCandidate(
            symbol=symbol,
            direction=direction,
            score=rule_score,
            pattern=pattern,
            bucket=bucket,
            features=features,
            score_breakdown=Breakdown(rule_score),
            reference_price=100.0,
            observation_id=observation_id,
            decision_batch_id=batch,
            market_event_id=event,
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            model_version="RULE_SYSTEM_V1",
            experiment_context=self._context(
                batch, event, bucket, trend=trend
            ),
        )

    @staticmethod
    def _artifact(path, model_id):
        artifact = {
            "artifact_schema_version": 1,
            "model_kind": "LOGISTIC_REGRESSION_BASELINE",
            "model_id": model_id,
            "base_feature_names": FEATURE_NAMES,
            "pattern_categories": ("RANGE_BREAKOUT",),
            "vector_columns": tuple(range(13)),
            "scaler": IdentityScaler(),
            "model": FirstFeatureProbabilityModel(),
            "runtime_activation": "DISABLED",
        }
        data = pickle.dumps(artifact)
        Path(path).write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def _registry_with_challenger(self, root, model_id="MODEL_A"):
        root = Path(root)
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
            }
        )
        registry.update_model(model_id, status="OFFLINE_VALIDATED")
        return registry, artifact_path

    def test_cycle_waits_for_coverage_and_settle(self):
        coordinator = FiveMinuteDecisionCycleCoordinator(
            minimum_coverage=0.75,
            settle_seconds=1.0,
        )
        coordinator.set_symbols(["A", "B", "C", "D"])
        for symbol in ("A", "B", "C"):
            coordinator.mark_rollover(
                symbol=symbol, new_bucket=10, now_monotonic=0.0
            )
        self.assertEqual(
            coordinator.ready_buckets(now_monotonic=0.5), []
        )
        ready = coordinator.ready_buckets(now_monotonic=1.0)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0]["coverage"], 0.75)

    def test_cycle_releases_immediately_at_complete_coverage(self):
        coordinator = FiveMinuteDecisionCycleCoordinator(
            minimum_coverage=0.90,
            settle_seconds=10.0,
        )
        coordinator.set_symbols(["A", "B"])
        coordinator.mark_rollover(
            symbol="A", new_bucket=5, now_monotonic=0.0
        )
        coordinator.mark_rollover(
            symbol="B", new_bucket=5, now_monotonic=0.0
        )
        self.assertEqual(
            coordinator.ready_buckets(now_monotonic=0.0)[0][
                "symbols_completed"
            ],
            2,
        )
        coordinator.mark_processed(5)
        self.assertEqual(coordinator.ready_buckets(now_monotonic=20), [])

    def test_registry_activates_shadow_without_changing_champion(self):
        with tempfile.TemporaryDirectory() as root:
            registry, _ = self._registry_with_challenger(root)
            selected = registry.activate_next_shadow_challenger()
            self.assertEqual(selected["status"], "SHADOW")
            self.assertEqual(
                registry.current_shadow_model_id(), "MODEL_A"
            )
            self.assertEqual(
                registry.current_champion_model_id(), "RULE_SYSTEM_V1"
            )
            self.assertEqual(
                selected["paper_authority"], "UNCHANGED"
            )

    def test_registered_baseline_artifact_scores_candidates(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "model.pkl"
            checksum = self._artifact(path, "MODEL_A")
            scorer = RegisteredModelArtifactScorer(
                model_id="MODEL_A",
                artifact_path=str(path),
                expected_checksum_sha256=checksum,
            )
            low = self._candidate(
                "BTCUSDT", 0.9, 0.1, "low"
            )
            high = self._candidate(
                "ETHUSDT", 0.8, 0.9, "high"
            )
            scores = scorer.score_candidates([low, high])
            self.assertGreater(scores["high"], scores["low"])

    def test_registered_artifact_checksum_is_enforced(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "model.pkl"
            self._artifact(path, "MODEL_A")
            with self.assertRaises(RegisteredModelScoringError):
                RegisteredModelArtifactScorer(
                    model_id="MODEL_A",
                    artifact_path=str(path),
                    expected_checksum_sha256="0" * 64,
                )

    def test_snapshot_records_rules_champion_and_challenger_top_k(self):
        with tempfile.TemporaryDirectory() as root:
            registry, _ = self._registry_with_challenger(root)
            path = Path(root) / "decisions.jsonl"
            tester = ChampionChallengerShadowTester(
                enabled=True,
                environment="LIVE",
                registry_path=str(registry.path),
                default_champion_model_id="RULE_SYSTEM_V1",
                decisions_path=str(path),
                top_k=3,
            )
            candidates = [
                self._candidate("BTCUSDT", 0.9, 0.1, "a"),
                self._candidate("ETHUSDT", 0.8, 0.9, "b"),
                self._candidate("SOLUSDT", 0.7, 0.7, "c"),
            ]
            result = tester.record_cycle(
                candidates=candidates,
                decision_batch_id="batch-1",
                market_event_id="event-1",
                candle_bucket=1,
                cycle_coverage={"coverage": 1.0},
            )
            self.assertEqual(
                result["systems"]["RULES"]["top_one"][0][
                    "candidate_observation_id"
                ],
                "a",
            )
            self.assertEqual(
                result["systems"]["CHAMPION"]["kind"], "RULES"
            )
            self.assertEqual(
                result["systems"]["CHALLENGER"]["top_one"][0][
                    "candidate_observation_id"
                ],
                "b",
            )
            self.assertEqual(
                len(result["systems"]["CHALLENGER"]["top_k"]), 3
            )
            self.assertEqual(result["runtime_effect"], "NONE")
            self.assertEqual(result["paper_authority"], "UNCHANGED")
            self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_snapshot_without_challenger_still_records_rule_cycle(self):
        with tempfile.TemporaryDirectory() as root:
            registry = ModelRegistry(
                path=str(Path(root) / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            tester = ChampionChallengerShadowTester(
                enabled=True,
                environment="LIVE",
                registry_path=str(registry.path),
                default_champion_model_id="RULE_SYSTEM_V1",
                decisions_path=str(Path(root) / "decisions.jsonl"),
            )
            result = tester.record_cycle(
                candidates=[
                    self._candidate("BTCUSDT", 0.9, 0.1, "a")
                ],
                decision_batch_id="batch-1",
                market_event_id="event-1",
                candle_bucket=1,
            )
            self.assertEqual(
                result["systems"]["CHALLENGER"]["status"],
                "UNAVAILABLE",
            )
            self.assertEqual(
                result["systems"]["RULES"]["status"], "AVAILABLE"
            )

    @staticmethod
    def _decision(
        batch,
        event,
        rules,
        champion,
        challenger,
        timestamp,
    ):
        def system(model_id, ids, kind="MODEL"):
            return {
                "model_id": model_id,
                "kind": kind,
                "status": "AVAILABLE",
                "top_one": ids[:1],
                "top_k": ids,
                "runtime_effect": "NONE",
            }

        return {
            "schema_version": 1,
            "observation_type": "CHAMPION_CHALLENGER_DECISION",
            "observed_at_ms": timestamp,
            "decision_batch_id": batch,
            "market_event_id": event,
            "runtime_effect": "NONE",
            "systems": {
                "RULES": system("RULE_SYSTEM_V1", rules, "RULES"),
                "CHAMPION": system("RULE_SYSTEM_V1", champion, "RULES"),
                "CHALLENGER": system("MODEL_A", challenger),
            },
        }

    @staticmethod
    def _selection(candidate_id, direction="LONG", pattern="RANGE_BREAKOUT"):
        return {
            "candidate_observation_id": candidate_id,
            "symbol": candidate_id.upper() + "USDT",
            "direction": direction,
            "pattern": pattern,
            "market_context": {
                "market_regime": "BULLISH",
                "trend_regime": "UP",
                "volatility_regime": "HIGH",
            },
        }

    @staticmethod
    def _outcome_row(candidate_id, net_r, gross_r=None, cost_r=0.1):
        gross = net_r + cost_r if gross_r is None else gross_r
        return {
            "observation_type": "CANDIDATE_OUTCOME",
            "recorded_at_ms": 1000,
            "candidate_observation_id": candidate_id,
            "outcome_type": "VIRTUAL_TRADE",
            "payload": {
                "net_exit_r": net_r,
                "gross_exit_r": gross,
                "estimated_cost_r": cost_r,
                "profitable": net_r > 0,
            },
        }

    def test_evaluator_uses_net_r_and_independent_market_events(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            a = self._selection("a")
            b = self._selection("b")
            c = self._selection("c")
            decisions = [
                self._decision(
                    "batch-1", "event-shared", [a, b], [a, b], [b, c], 1
                ),
                self._decision(
                    "batch-2", "event-shared", [a, c], [a, c], [b, c], 2
                ),
            ]
            outcomes = [
                self._outcome_row("a", -1.1),
                self._outcome_row("b", 1.9),
                self._outcome_row("c", 0.9),
            ]
            (root / "decisions.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in decisions)
            )
            (root / "outcomes.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in outcomes)
            )
            report = ShadowDecisionEvaluator(
                decisions_path=str(root / "decisions.jsonl"),
                outcomes_path=str(root / "outcomes.jsonl"),
                report_path=str(root / "report.json"),
            ).evaluate()
            top_one = report["policies"]["CHALLENGER"]["TOP_ONE"][
                "summary"
            ]
            self.assertEqual(top_one["completed_raw_batches"], 2)
            self.assertEqual(top_one["independent_market_events"], 1)
            self.assertAlmostEqual(top_one["average_net_r"], 1.9)
            top_k = report["policies"]["CHALLENGER"]["TOP_K"][
                "summary"
            ]
            self.assertAlmostEqual(top_k["average_net_r"], 1.4)
            self.assertAlmostEqual(
                top_k["average_estimated_cost_r"], 0.1
            )

    def test_evaluator_reports_disagreement_lift_drawdown_and_regimes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            a = self._selection("a", direction="LONG")
            b = self._selection("b", direction="SHORT")
            decisions = [
                self._decision("batch-1", "event-1", [a], [a], [b], 1),
                self._decision("batch-2", "event-2", [a], [a], [b], 2),
            ]
            outcomes = [
                self._outcome_row("a", -1.1),
                self._outcome_row("b", 1.9),
            ]
            (root / "decisions.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in decisions)
            )
            (root / "outcomes.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in outcomes)
            )
            report = ShadowDecisionEvaluator(
                decisions_path=str(root / "decisions.jsonl"),
                outcomes_path=str(root / "outcomes.jsonl"),
                report_path=str(root / "report.json"),
            ).evaluate()
            comparison = report["pairwise"][
                "CHALLENGER_VS_CHAMPION"
            ]["TOP_ONE"]
            self.assertEqual(comparison["disagreement_events"], 2)
            self.assertAlmostEqual(
                comparison["left_minus_right_average_net_r"], 3.0
            )
            challenger = report["policies"]["CHALLENGER"][
                "TOP_ONE"
            ]
            self.assertIn("direction", challenger["regimes"])
            self.assertIn("SHORT", challenger["regimes"]["direction"])
            self.assertEqual(
                challenger["summary"]["maximum_losing_streak"], 0
            )
            self.assertEqual(report["promotion_authority"], "NONE")

    def test_engine_processes_shadow_cycle_before_open_position_fast_path(self):
        source = Path("engine/core.py").read_text()
        cycle_position = source.index("process_ready_decision_cycles")
        open_mode_position = source.index("MODE A — POSITION OPEN")
        self.assertLess(cycle_position, open_mode_position)
        self.assertIn("runtime_effect=NONE", source)


if __name__ == "__main__":
    unittest.main()
