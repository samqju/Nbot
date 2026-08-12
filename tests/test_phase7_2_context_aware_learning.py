import json
import pickle
import tempfile
import unittest
from pathlib import Path

from learning.baseline_trainer import BaselineModelTrainer, FEATURE_NAMES
from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    CONTEXT_FEATURE_SCHEMA_VERSION,
    context_feature_mapping,
    context_feature_vector,
    is_complete_market_context,
)
from learning.ensemble_experiment import OfflineEnsembleExperiment
from learning.model_registry import ModelRegistry, ModelRegistryError
from learning.model_artifact_scorer import (
    RegisteredModelArtifactScorer,
    RegisteredModelScoringError,
)
from learning.shadow_scorer import ShadowModelScorer
from learning.training_orchestrator import TrainingInventory
from strategy.candidate import StrategyCandidate
from strategy.experiment_contract import (
    build_experiment_context,
    experiment_projection,
)
from strategy.features import CandidateFeatures


class Phase72ContextAwareLearningTests(unittest.TestCase):
    @staticmethod
    def _observed_context(*, label=True, bucket=1, symbol="ADAUSDT"):
        bullish = bool(label)
        return {
            "schema_version": 1,
            "source": "TEST_BINANCE_BULK",
            "observed_at_ms": 1_700_000_000_000 + bucket * 300_000,
            "candle_bucket": bucket,
            "coverage": 1.0,
            "market_regime": "BULLISH" if bullish else "BEARISH",
            "trend_regime": "BULLISH" if bullish else "BEARISH",
            "volatility_regime": "NORMAL" if bullish else "HIGH",
            "btc_regime": "BULLISH" if bullish else "BEARISH",
            "btc_change_pct_24h": 2.5 if bullish else -3.5,
            "market_breadth": {
                "symbols_expected": 200,
                "symbols_observed": 200,
                "coverage": 1.0,
                "advancing_fraction": 0.72 if bullish else 0.24,
                "declining_fraction": 0.28 if bullish else 0.76,
                "unchanged_fraction": 0.0,
                "median_change_pct_24h": 2.1 if bullish else -2.7,
                "median_abs_change_pct_24h": 3.2 if bullish else 4.4,
            },
            "liquidity_by_symbol": {
                symbol: {
                    "spread_pct": 0.04 if bullish else 0.07,
                    "quote_volume_usd": 125_000_000.0,
                }
            },
            "completeness": "COMPLETE_PHASE7_1",
        }

    @classmethod
    def _experiment_context(cls, *, label=True, bucket=1, symbol="ADAUSDT"):
        return build_experiment_context(
            decision_batch_id=f"batch-{bucket}",
            market_event_id=f"event-{bucket}",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=bucket,
            structure_fingerprint={
                "structure": "RANGE_BREAKOUT",
                "trend": "UP" if label else "DOWN",
                "volatility": "NORMAL",
                "compression": False,
            },
            candidate_symbol=symbol,
            observed_market_context=cls._observed_context(
                label=label, bucket=bucket, symbol=symbol
            ),
            paper_taker_fee_rate=0.0005,
            paper_entry_slippage_pct=0.02,
            paper_exit_slippage_pct=0.02,
            virtual_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            virtual_target_r=2.0,
            virtual_max_candles=24,
            paper_variant_id="PAPER_TRAILING_SL_V1",
        )

    @classmethod
    def _row(cls, index, *, complete=True):
        label = bool(index % 2)
        context = cls._experiment_context(label=label, bucket=index)
        market_context = context["market_context"]
        if not complete:
            market_context = dict(market_context)
            market_context["btc_regime"] = None
            market_context["completeness"] = "PARTIAL_PHASE7_1"
        features = {
            name: (index + offset + 1) / 100.0
            for offset, name in enumerate(FEATURE_NAMES)
        }
        return {
            "candidate_observation_id": f"candidate-{index}",
            "outcome_type": "VIRTUAL_TRADE",
            "label_profitable": label,
            "direction": "LONG" if label else "SHORT",
            "pattern": "RANGE_BREAKOUT",
            "rule_score": 0.8 if label else 0.2,
            "final_score": 0.8 if label else 0.2,
            "features": features,
            "market_context": market_context,
            "experiment_context": context,
        }

    @staticmethod
    def _write(path, rows):
        Path(path).write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_context_feature_contract_is_fixed_and_finite(self):
        context = self._experiment_context(label=True, bucket=1)["market_context"]
        vector = context_feature_vector(context)
        mapping = context_feature_mapping(context)
        self.assertEqual(len(vector), len(CONTEXT_FEATURE_NAMES))
        self.assertEqual(tuple(mapping), CONTEXT_FEATURE_NAMES)
        self.assertEqual(CONTEXT_FEATURE_SCHEMA_VERSION, 1)
        self.assertTrue(is_complete_market_context(context))
        self.assertEqual(mapping["ctx_market_regime::BULLISH"], 1.0)
        self.assertEqual(mapping["ctx_market_regime::BEARISH"], 0.0)
        self.assertGreater(mapping["ctx_log10_quote_volume_usd"], 8.0)

    def test_context_aware_baseline_excludes_partial_rows(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            train = [self._row(i) for i in range(40)] + [self._row(100, complete=False)]
            validation = [self._row(200 + i) for i in range(12)]
            test = [self._row(400 + i) for i in range(12)]
            for name, rows in (("train", train), ("validation", validation), ("test", test)):
                self._write(root / f"{name}.jsonl", rows)

            artifact_path = root / "model.pkl"
            report = BaselineModelTrainer(
                train_path=root / "train.jsonl",
                validation_path=root / "validation.jsonl",
                test_path=root / "test.jsonl",
                artifact_path=artifact_path,
                report_path=root / "report.json",
                min_train_rows=20,
                min_eval_rows=5,
                context_aware=True,
            ).train()

            self.assertEqual(report["status"], "TRAINED")
            self.assertEqual(report["rows"]["train"], 40)
            self.assertEqual(report["issues"]["train_market_context_incomplete"], 1)
            artifact = pickle.loads(artifact_path.read_bytes())
            self.assertTrue(artifact["requires_complete_market_context"])
            self.assertEqual(
                artifact["context_feature_schema_version"],
                CONTEXT_FEATURE_SCHEMA_VERSION,
            )
            self.assertEqual(
                tuple(artifact["context_feature_names"]),
                CONTEXT_FEATURE_NAMES,
            )
            self.assertTrue(
                all(name in artifact["vector_columns"] for name in CONTEXT_FEATURE_NAMES)
            )

    def test_registered_context_model_scores_complete_candidate_and_rejects_partial(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for split, start, count in (
                ("train", 0, 40),
                ("validation", 100, 12),
                ("test", 200, 12),
            ):
                self._write(
                    root / f"{split}.jsonl",
                    [self._row(start + i) for i in range(count)],
                )
            artifact_path = root / "model.pkl"
            BaselineModelTrainer(
                train_path=root / "train.jsonl",
                validation_path=root / "validation.jsonl",
                test_path=root / "test.jsonl",
                artifact_path=artifact_path,
                report_path=root / "report.json",
                min_train_rows=20,
                min_eval_rows=5,
                context_aware=True,
            ).train()

            scorer = RegisteredModelArtifactScorer(
                model_id="PHASE72_TEST",
                artifact_path=str(artifact_path),
                expected_feature_schema_version=3,
            )
            candidate = StrategyCandidate(
                symbol="ADAUSDT",
                direction="LONG",
                score=0.8,
                pattern="RANGE_BREAKOUT",
                bucket=500,
                features=CandidateFeatures(
                    short_range=0.01,
                    long_range=0.02,
                    trend_score=1.0,
                    wick_ratio_recent=0.2,
                    body_ratio_recent=0.8,
                    range_acceleration=1.1,
                    dist_high=-0.01,
                    dist_low=0.03,
                    directional_consistency=4.0,
                ),
                experiment_context=self._experiment_context(
                    label=True, bucket=500
                ),
            )
            probability = scorer.score_candidates([candidate])[candidate.observation_id]
            self.assertGreaterEqual(probability, 0.0)
            self.assertLessEqual(probability, 1.0)

            partial = StrategyCandidate(
                symbol="ADAUSDT",
                direction="LONG",
                score=0.8,
                pattern="RANGE_BREAKOUT",
                bucket=501,
                features=candidate.features,
                experiment_context=None,
            )
            with self.assertRaises(RegisteredModelScoringError):
                scorer.score_candidates([partial])

    def test_training_inventory_ignores_historical_partial_context(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations = []
            outcomes = []
            for index, complete in ((1, True), (2, False)):
                context = self._experiment_context(
                    label=bool(index % 2), bucket=index
                )
                if not complete:
                    context = dict(context)
                    context["market_context"] = dict(
                        context["market_context"]
                    )
                    context["market_context"]["btc_regime"] = None
                    context["market_context"]["completeness"] = (
                        "PARTIAL_PHASE7_1"
                    )
                projection = experiment_projection(context)
                candidate_id = f"inventory-{index}"
                observations.append({
                    "candidate_observation_id": candidate_id,
                    "experiment_contract_version": 1,
                    **projection,
                    "market_context": context["market_context"],
                    "experiment_context": context,
                })
                outcomes.append({
                    "candidate_observation_id": candidate_id,
                    "outcome_type": "VIRTUAL_TRADE",
                    "outcome_variant_id": "VIRTUAL_FIXED_2R_24C_V1",
                    "recorded_at_ms": 1_700_000_000_000 + index * 300_000,
                })
            obs_path = root / "observations.jsonl"
            out_path = root / "outcomes.jsonl"
            self._write(obs_path, observations)
            self._write(out_path, outcomes)

            report = TrainingInventory(
                observations_path=str(obs_path),
                outcomes_path=str(out_path),
                outcome_type="VIRTUAL_TRADE",
                require_complete_market_context=True,
            ).scan(after_ms=0)
            self.assertEqual(report["new_completed_outcomes"], 1)
            self.assertEqual(report["new_independent_market_events"], 1)
            self.assertEqual(
                report["issues"]["market_context_incomplete_excluded"],
                1,
            )


    def test_phase72_model_cannot_enter_paper_canary(self):
        with tempfile.TemporaryDirectory() as root:
            registry = ModelRegistry(
                path=str(Path(root) / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            registry.initialize()
            registry.register_training({
                "model_id": "PHASE72_LOCKED",
                "parent_model_id": "RULE_SYSTEM_V1",
                "artifact_path": "challenger.pkl",
                "paper_promotion_allowed": False,
                "training_completed_at_ms": 1,
            })
            registry.update_model(
                "PHASE72_LOCKED",
                status="OFFLINE_VALIDATED",
                updates={"artifact_path": "challenger.pkl"},
            )
            shadow = registry.activate_next_shadow_challenger()
            self.assertEqual(shadow["status"], "SHADOW")
            self.assertEqual(
                registry.current_champion_model_id(), "RULE_SYSTEM_V1"
            )
            with self.assertRaises(ModelRegistryError):
                registry.apply_promotion_decision(
                    "PHASE72_LOCKED",
                    decision="PROMOTE_TO_PAPER_CANARY",
                    evidence={},
                    gate_report={},
                    reason_codes=[],
                )
            self.assertEqual(
                registry.current_shadow_model_id(), "PHASE72_LOCKED"
            )
            self.assertEqual(
                registry.current_champion_model_id(), "RULE_SYSTEM_V1"
            )


    def test_context_aware_ensemble_shadow_scores_without_runtime_authority(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for split, start, count in (
                ("train", 0, 60),
                ("validation", 100, 20),
                ("test", 200, 20),
            ):
                self._write(
                    root / f"{split}.jsonl",
                    [self._row(start + i) for i in range(count)],
                )
            artifact_path = root / "ensemble.pkl"
            report = OfflineEnsembleExperiment(
                train_path=root / "train.jsonl",
                validation_path=root / "validation.jsonl",
                test_path=root / "test.jsonl",
                artifact_path=artifact_path,
                report_path=root / "ensemble_report.json",
                min_train_rows=20,
                min_eval_rows=5,
                context_aware=True,
            ).run()
            self.assertEqual(report["status"], "EXPERIMENT_COMPLETE")

            candidate = StrategyCandidate(
                symbol="ADAUSDT",
                direction="LONG",
                score=0.8,
                pattern="RANGE_BREAKOUT",
                bucket=700,
                features=CandidateFeatures(
                    short_range=0.01,
                    long_range=0.02,
                    trend_score=1.0,
                    wick_ratio_recent=0.2,
                    body_ratio_recent=0.8,
                    range_acceleration=1.1,
                    dist_high=-0.01,
                    dist_low=0.03,
                    directional_consistency=4.0,
                ),
                experiment_context=self._experiment_context(
                    label=True, bucket=700
                ),
            )
            scorer = ShadowModelScorer(
                enabled=True,
                artifact_path=str(artifact_path),
                predictions_path=str(root / "shadow.jsonl"),
                refresh_seconds=1,
            )
            predictions = scorer.score_candidates(
                [candidate], rule_selected_candidate=candidate
            )
            self.assertEqual(len(predictions), 1)
            self.assertEqual(predictions[0]["runtime_effect"], "NONE")
            self.assertTrue(predictions[0]["rule_selected"])
            artifact = pickle.loads(artifact_path.read_bytes())
            self.assertEqual(artifact["runtime_activation"], "DISABLED")
            self.assertTrue(artifact["requires_complete_market_context"])



if __name__ == "__main__":
    unittest.main()
