import hashlib
import json
import pickle
import tempfile
import unittest
from pathlib import Path

from learning.context_features import (
    CONTEXT_FEATURE_NAMES,
    CONTEXT_FEATURE_SCHEMA_VERSION,
)
from learning.cost_evidence import PHASE7_COMPLETE_COST_BASIS
from learning.model_registry import ModelRegistry
from learning.promotion_controller import AutomaticPromotionController
from learning.shadow_decision_testing import ShadowDecisionEvaluator


class DummyScaler:
    def transform(self, values):
        return values


class DummyModel:
    def predict_proba(self, values):
        return [[0.4, 0.6] for _ in values]


class Phase75ChampionChallengerValidationTests(unittest.TestCase):
    @staticmethod
    def _context(regime="BULLISH", *, btc_regime=None):
        regime = regime.upper()
        bullish = regime == "BULLISH"
        btc = btc_regime or ("BULLISH" if bullish else "BEARISH")
        return {
            "schema_version": 2,
            "source": "TEST_PHASE7_5",
            "completeness": "COMPLETE_PHASE7_1",
            "context_coverage": 1.0,
            "market_regime": regime,
            "volatility_regime": "NORMAL" if bullish else "HIGH",
            "btc_regime": btc,
            "btc_change_pct_24h": 2.0 if bullish else -2.0,
            "market_breadth": {
                "symbols_expected": 200,
                "symbols_observed": 200,
                "coverage": 1.0,
                "advancing_fraction": 0.70 if bullish else 0.25,
                "declining_fraction": 0.30 if bullish else 0.75,
                "unchanged_fraction": 0.0,
                "median_change_pct_24h": 1.5 if bullish else -1.5,
                "median_abs_change_pct_24h": 2.5,
            },
            "liquidity": {
                "spread_pct": 0.04,
                "quote_volume_usd": 100_000_000.0,
            },
        }

    @classmethod
    def _selection(cls, candidate_id, regime="BULLISH"):
        return {
            "candidate_observation_id": candidate_id,
            "symbol": candidate_id.upper() + "USDT",
            "direction": "LONG",
            "pattern": "RANGE_BREAKOUT",
            "market_context": cls._context(regime),
        }

    @classmethod
    def _decision(cls, index, regime="BULLISH", model_id="MODEL_A"):
        champion = cls._selection(f"champ-{index}", regime)
        challenger = cls._selection(f"chall-{index}", regime)
        return {
            "schema_version": 1,
            "observation_type": "CHAMPION_CHALLENGER_DECISION",
            "observed_at_ms": 1_700_000_000_000 + index * 300_000,
            "decision_batch_id": f"batch-{index}",
            "market_event_id": f"event-{index}",
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

    @staticmethod
    def _outcome(candidate_id, net_r, *, complete=True):
        cost = 0.20
        breakdown = {
            "cost_completeness": (
                PHASE7_COMPLETE_COST_BASIS
                if complete
                else "FEES_SLIPPAGE_SPREAD_ONLY"
            ),
            "spread_r": 0.05,
            "funding_r": 0.0 if complete else None,
            "total_cost_r": cost if complete else None,
        }
        return {
            "observation_type": "CANDIDATE_OUTCOME",
            "candidate_observation_id": candidate_id,
            "outcome_type": "VIRTUAL_TRADE",
            "payload": {
                "net_exit_r": net_r,
                "gross_exit_r": net_r + cost,
                "estimated_cost_r": cost,
                "cost_breakdown": breakdown,
            },
        }

    @classmethod
    def _write_evidence(cls, root, specs, *, incomplete_event=None):
        decisions = []
        outcomes = []
        for index, (regime, challenger_r, champion_r) in enumerate(specs):
            decisions.append(cls._decision(index, regime))
            complete = index != incomplete_event
            outcomes.extend([
                cls._outcome(f"champ-{index}", champion_r, complete=complete),
                cls._outcome(f"chall-{index}", challenger_r, complete=complete),
            ])
        (root / "decisions.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in decisions)
        )
        (root / "outcomes.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in outcomes)
        )

    @staticmethod
    def _artifact(path, model_id="MODEL_A"):
        artifact = {
            "artifact_schema_version": 1,
            "model_kind": "LOGISTIC_REGRESSION_BASELINE",
            "model_id": model_id,
            "feature_schema_version": 3,
            "base_feature_names": ("short_range",),
            "pattern_categories": ("RANGE_BREAKOUT",),
            "scaler": DummyScaler(),
            "model": DummyModel(),
            "runtime_activation": "DISABLED",
            "requires_complete_market_context": True,
            "context_feature_schema_version": CONTEXT_FEATURE_SCHEMA_VERSION,
            "context_feature_names": CONTEXT_FEATURE_NAMES,
        }
        data = pickle.dumps(artifact)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    @classmethod
    def _phase7_registry(cls, root, model_id="MODEL_A"):
        artifact_path = root / f"{model_id}.pkl"
        checksum = cls._artifact(artifact_path, model_id)
        registry = ModelRegistry(
            path=str(root / "registry.json"),
            environment="LIVE",
            default_champion_model_id="RULE_SYSTEM_V1",
        )
        registry.register_training({
            "model_id": model_id,
            "parent_model_id": "RULE_SYSTEM_V1",
            "training_completed_at_ms": 10,
            "artifact_path": str(artifact_path),
            "artifact_checksum_sha256": checksum,
            "dataset_fingerprint": "a" * 64,
            "test_metrics": {"brier_score": 0.20},
            "calibration_metrics": {"test_max_abs_gap": 0.05},
            "drift_metrics": {"max_feature_psi": 0.10},
            "phase": "7.4",
            "requires_complete_market_context": True,
            "requires_complete_cost_evidence": True,
            "test_set_policy": "SEALED_UNTIL_FINAL_CANDIDATE_SELECTED",
            "selected_using_test_data": False,
            "paper_promotion_allowed": False,
        })
        registry.update_model(model_id, status="OFFLINE_VALIDATED")
        registry.activate_next_shadow_challenger(
            require_phase7_validation=True
        )
        return registry

    @classmethod
    def _controller(cls, root, **overrides):
        params = dict(
            enabled=True,
            environment="LIVE",
            decisions_path=str(root / "decisions.jsonl"),
            outcomes_path=str(root / "outcomes.jsonl"),
            evidence_report_path=str(root / "evidence.json"),
            registry_path=str(root / "registry.json"),
            status_path=str(root / "status.json"),
            lock_path=str(root / "promotion.lock"),
            default_champion_model_id="RULE_SYSTEM_V1",
            outcome_type="VIRTUAL_TRADE",
            min_matched_outcomes=4,
            min_independent_events=4,
            min_disagreement_events=2,
            min_average_r_lift=0.0,
            min_after_cost_expectancy=0.0,
            max_win_rate_deterioration=1.0,
            max_brier_score=0.25,
            max_calibration_gap=0.10,
            max_feature_psi=0.25,
            min_recent_expectancy=-1.0,
            recent_event_window=4,
            extend_evidence_ratio=0.50,
            phase7_strict_evidence=True,
            min_regime_events=2,
            min_distinct_market_regimes=2,
            min_regime_average_r_lift=0.0,
            min_regime_after_cost_expectancy=0.0,
        )
        params.update(overrides)
        return AutomaticPromotionController(**params)

    def test_strict_evaluator_excludes_incomplete_cost_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(
                root,
                [
                    ("BULLISH", 0.4, 0.1),
                    ("BEARISH", 0.3, 0.1),
                ],
                incomplete_event=1,
            )
            report = ShadowDecisionEvaluator(
                decisions_path=str(root / "decisions.jsonl"),
                outcomes_path=str(root / "outcomes.jsonl"),
                report_path=str(root / "report.json"),
                require_complete_market_context=True,
                require_complete_cost_evidence=True,
            ).evaluate()
            self.assertEqual(report["phase"], "7.5")
            comparison = report["pairwise"]["CHALLENGER_VS_CHAMPION"]["TOP_ONE"]
            self.assertEqual(comparison["independent_market_event_pairs"], 1)
            self.assertGreaterEqual(
                report["issues"].get("cost_evidence_incomplete_excluded", 0),
                2,
            )
            self.assertEqual(
                report["evidence_policy"]["return_basis"],
                "NET_AFTER_COMPLETE_PHASE7_3_COSTS",
            )

    def test_pairwise_report_measures_market_btc_and_volatility_regimes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_evidence(
                root,
                [
                    ("BULLISH", 0.4, 0.1),
                    ("BULLISH", 0.3, 0.1),
                    ("BEARISH", 0.2, 0.05),
                    ("BEARISH", 0.25, 0.05),
                ],
            )
            report = ShadowDecisionEvaluator(
                decisions_path=str(root / "decisions.jsonl"),
                outcomes_path=str(root / "outcomes.jsonl"),
                report_path=str(root / "report.json"),
                require_complete_market_context=True,
                require_complete_cost_evidence=True,
            ).evaluate()
            comparison = report["pairwise"]["CHALLENGER_VS_CHAMPION"]["TOP_ONE"]
            self.assertEqual(
                comparison["regimes"]["market_regime"]["BULLISH"][
                    "independent_market_event_pairs"
                ],
                2,
            )
            self.assertEqual(
                comparison["regimes"]["market_regime"]["BEARISH"][
                    "independent_market_event_pairs"
                ],
                2,
            )
            self.assertIn("btc_regime", comparison["regimes"])
            self.assertIn("volatility_regime", comparison["regimes"])

    def test_controller_extends_shadow_when_regime_diversity_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._phase7_registry(root)
            self._write_evidence(
                root,
                [("BULLISH", 0.3, 0.1)] * 4,
            )
            result = self._controller(root).run_once()
            self.assertEqual(result["phase"], "7.5")
            self.assertEqual(result["promotion_outcome"], "EXTEND_SHADOW")
            self.assertFalse(
                result["gates"]["checks"]["market_regime_coverage"]["passed"]
            )
            self.assertEqual(
                result["evidence"]["regime_robustness"]["market_regime"][
                    "eligible_group_count"
                ],
                1,
            )

    def test_controller_rejects_challenger_with_negative_supported_regime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._phase7_registry(root)
            self._write_evidence(
                root,
                [
                    ("BULLISH", 0.6, 0.1),
                    ("BULLISH", 0.6, 0.1),
                    ("BEARISH", -0.05, -0.10),
                    ("BEARISH", -0.05, -0.10),
                ],
            )
            result = self._controller(root).run_once()
            self.assertEqual(result["promotion_outcome"], "REJECT")
            self.assertIn(
                "SUPPORTED_REGIME_EXPECTANCY_NOT_POSITIVE",
                result["reason_codes"],
            )

    def test_all_phase75_gates_pass_but_paper_authority_stays_locked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = self._phase7_registry(root)
            self._write_evidence(
                root,
                [
                    ("BULLISH", 0.4, 0.1),
                    ("BULLISH", 0.3, 0.1),
                    ("BEARISH", 0.35, 0.1),
                    ("BEARISH", 0.30, 0.1),
                ],
            )
            result = self._controller(root).run_once()
            self.assertTrue(result["gates"]["all_gates_passed"])
            self.assertEqual(result["promotion_outcome"], "EXTEND_SHADOW")
            self.assertEqual(result["reason_codes"], ["PHASE7_PAPER_PROMOTION_LOCKED"])
            self.assertEqual(registry.current_champion_model_id(), "RULE_SYSTEM_V1")
            self.assertIsNone(registry.current_paper_canary_model_id())
            self.assertEqual(registry.current_shadow_model_id(), "MODEL_A")

    def test_strict_shadow_activation_archives_legacy_slot_and_uses_phase7_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = ModelRegistry(
                path=str(root / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            registry.initialize()
            legacy_path = root / "legacy.pkl"
            legacy_path.write_bytes(b"legacy")
            registry.register_training({
                "model_id": "LEGACY",
                "training_completed_at_ms": 1,
                "artifact_path": str(legacy_path),
            })
            registry.update_model("LEGACY", status="OFFLINE_VALIDATED")
            registry.activate_next_shadow_challenger()
            self.assertEqual(registry.current_shadow_model_id(), "LEGACY")

            phase7_path = root / "phase7.pkl"
            phase7_path.write_bytes(b"phase7")
            registry.register_training({
                "model_id": "PHASE7",
                "training_completed_at_ms": 2,
                "artifact_path": str(phase7_path),
                "phase": "7.4",
                "requires_complete_market_context": True,
                "requires_complete_cost_evidence": True,
                "test_set_policy": "SEALED_UNTIL_FINAL_CANDIDATE_SELECTED",
                "selected_using_test_data": False,
                "paper_promotion_allowed": False,
            })
            registry.update_model("PHASE7", status="OFFLINE_VALIDATED")

            selected = registry.activate_next_shadow_challenger(
                require_phase7_validation=True
            )
            self.assertEqual(selected["model_id"], "PHASE7")
            self.assertEqual(registry.get_model("LEGACY")["status"], "ARCHIVED")
            self.assertEqual(registry.current_shadow_model_id(), "PHASE7")


if __name__ == "__main__":
    unittest.main()
