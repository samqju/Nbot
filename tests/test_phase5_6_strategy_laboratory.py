import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.dataset_builder import TrainingDatasetBuilder
from learning.strategy_lab import StrategyLabEvaluator
from strategy.candidate import StrategyCandidate
from strategy.candidate_observer import CandidateObservationWriter
from strategy.candidate_outcome import CandidateOutcomeWriter
from strategy.candidate_risk import CandidateRiskPlan
from strategy.experiment_contract import build_experiment_context
from strategy.features import CandidateFeatures
from strategy.learning_runtime_state import LearningRuntimeStateStore
from strategy.strategy_lab import (
    build_approved_variant_catalog,
    variants_for_pattern,
)
from strategy.virtual_trade_engine import VirtualTradeEngine


class Phase56StrategyLaboratoryTests(unittest.TestCase):
    def _context(self):
        return build_experiment_context(
            decision_batch_id="batch-56",
            market_event_id="event-56",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=123,
            structure_fingerprint={
                "structure": "BREAKOUT",
                "trend": "UP",
                "volatility": "NORMAL",
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

    def _candidate(self, *, pattern="RANGE_BREAKOUT"):
        risk = CandidateRiskPlan(
            risk_budget_usd=10,
            reference_price=100,
            stop_distance_pct=1,
            stop_distance_price=1,
            suggested_stop_price=99,
            suggested_quantity=10,
            suggested_notional_usd=1000,
            required_margin_usd=200,
            risk_efficiency=1,
            capped_by="NOTIONAL",
        )
        context = self._context()
        return StrategyCandidate(
            symbol="BTCUSDT",
            direction="LONG",
            score=0.8,
            pattern=pattern,
            bucket=123,
            features=CandidateFeatures(
                0.01, 0.02, 5, 0.2, 0.8, 1.1, -0.01, 0.03, 4
            ),
            reference_price=100,
            risk_plan=risk,
            decision_batch_id="batch-56",
            market_event_id="event-56",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            model_version="RULE_SYSTEM_V1",
            experiment_context=context,
        )

    def _catalog(self):
        return build_approved_variant_catalog(
            baseline_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            baseline_target_r=2.0,
            baseline_max_candles=24,
        )

    def test_catalog_applies_only_approved_family_variants(self):
        catalog = self._catalog()
        breakout = variants_for_pattern(catalog, "RANGE_BREAKOUT")
        reversion = variants_for_pattern(catalog, "MEAN_REVERSION")
        self.assertEqual(len(breakout), 3)
        self.assertEqual(len(reversion), 3)
        self.assertIn(
            "VIRTUAL_BREAKOUT_WIDE_2_5R_36C_V1",
            {row.variant_id for row in breakout},
        )
        self.assertNotIn(
            "VIRTUAL_REVERSION_FAST_1_25R_8C_V1",
            {row.variant_id for row in breakout},
        )

    def test_lab_enrolls_multiple_variants_without_changing_candidate(self):
        candidate = self._candidate()
        engine = VirtualTradeEngine(
            lab_enabled=True,
            variant_catalog=self._catalog(),
            catalog_version="PHASE5_6_APPROVED_V1",
            max_active=20,
        )
        created = engine.enroll_all([candidate])
        self.assertEqual(created, 3)
        self.assertEqual(engine.active_count(), 3)
        self.assertEqual(engine.active_candidate_count(), 1)
        self.assertEqual(candidate.risk_plan.stop_distance_price, 1.0)

    def test_outcomes_are_cost_aware_and_baseline_remains_identifiable(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outcomes = root / "outcomes.jsonl"
            virtual = root / "virtual.jsonl"
            writer = CandidateOutcomeWriter(
                str(outcomes),
                environment="LIVE",
                execution_mode="SHADOW",
            )
            import strategy.virtual_trade_engine as module
            with patch.object(module, "VIRTUAL_TRADES_PATH", str(virtual)):
                engine = VirtualTradeEngine(
                    outcome_writer=writer,
                    lab_enabled=True,
                    variant_catalog=self._catalog(),
                    catalog_version="PHASE5_6_APPROVED_V1",
                    max_active=20,
                )
            engine.enroll_all([self._candidate()])
            results = engine.on_candle(
                "BTCUSDT",
                (100.0, 103.2, 99.5, 103.0),
            )
            self.assertEqual(len(results), 3)
            self.assertTrue(all(row["net_exit_r"] < row["gross_exit_r"] for row in results))
            rows = [json.loads(line) for line in outcomes.read_text().splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertEqual(
                sum(row["outcome_type"] == "VIRTUAL_TRADE" for row in rows),
                1,
            )
            self.assertEqual(
                sum(row["outcome_type"] == "VIRTUAL_STRATEGY_VARIANT" for row in rows),
                2,
            )
            for row in rows:
                payload = row["payload"]
                self.assertEqual(
                    payload["label_basis"],
                    "NET_AFTER_ESTIMATED_COSTS",
                )
                self.assertEqual(payload["exit_r"], payload["net_exit_r"])
                self.assertGreater(payload["estimated_cost_r"], 0)

    def test_recovery_supports_same_candidate_with_multiple_variants(self):
        with tempfile.TemporaryDirectory() as root:
            store = LearningRuntimeStateStore(
                str(Path(root) / "runtime.json")
            )
            engine = VirtualTradeEngine(
                runtime_store=store,
                lab_enabled=True,
                variant_catalog=self._catalog(),
                catalog_version="PHASE5_6_APPROVED_V1",
                max_active=20,
            )
            engine.enroll_all([self._candidate()])
            restored = VirtualTradeEngine(
                runtime_store=store,
                lab_enabled=True,
                variant_catalog=self._catalog(),
                catalog_version="PHASE5_6_APPROVED_V1",
                max_active=20,
            )
            self.assertEqual(restored.active_count(), 3)
            self.assertEqual(restored.active_candidate_count(), 1)

    def test_evaluator_groups_correlated_candidates_by_market_event(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outcomes = root / "outcomes.jsonl"
            report_path = root / "report.json"
            rows = []
            for index, (event_id, net_r) in enumerate((
                ("event-a", 1.0),
                ("event-a", -0.5),
                ("event-b", 1.0),
                ("event-b", 0.5),
            )):
                rows.append({
                    "recorded_at_ms": index + 1,
                    "candidate_observation_id": f"candidate-{index}",
                    "market_event_id": event_id,
                    "outcome_type": "VIRTUAL_STRATEGY_VARIANT",
                    "outcome_variant_id": "VARIANT_A",
                    "payload": {
                        "pattern": "RANGE_BREAKOUT",
                        "gross_exit_r": net_r + 0.1,
                        "net_exit_r": net_r,
                        "estimated_cost_r": 0.1,
                        "profitable": net_r > 0,
                        "exit_reason": "TARGET",
                        "strategy_lab_catalog_version": (
                            "PHASE5_6_APPROVED_V1"
                        ),
                        "strategy_lab_family": "TEST",
                    },
                })
            outcomes.write_text(
                "".join(json.dumps(row) + "\n" for row in rows)
            )
            report = StrategyLabEvaluator(
                outcomes_path=str(outcomes),
                report_path=str(report_path),
                catalog_version="PHASE5_6_APPROVED_V1",
                min_outcomes=4,
                min_market_events=2,
                min_avg_net_r=0.01,
                max_drawdown_r=10,
            ).evaluate()
            variant = report["variants"]["VARIANT_A"]
            self.assertEqual(variant["raw"]["count"], 4)
            self.assertEqual(variant["event_grouped"]["count"], 2)
            self.assertEqual(variant["unique_market_events"], 2)
            self.assertEqual(variant["verdict"], "SHADOW_ELIGIBLE")
            self.assertEqual(report["runtime_activation"], "DISABLED")

    def test_dataset_prefers_net_r_and_variant_context(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations = root / "observations.jsonl"
            outcomes = root / "outcomes.jsonl"
            dataset = root / "dataset.jsonl"
            report = root / "report.json"
            candidate = self._candidate()
            CandidateObservationWriter(str(observations)).append(
                candidate,
                rank=1,
                selected=True,
            )
            context = dict(candidate.experiment_context)
            context["virtual_policy"] = {
                "schema_version": 2,
                "variant_id": "VARIANT_NET",
                "family": "TEST",
                "base_stop_multiplier": 1.0,
                "stop_r": 1.0,
                "target_r": 2.0,
                "max_candles": 24,
                "ambiguous_touch_policy": "STOP_FIRST",
                "label_basis": "NET_AFTER_ESTIMATED_COSTS",
            }
            context["strategy_lab"] = {
                "schema_version": 1,
                "catalog_version": "PHASE5_6_APPROVED_V1",
                "research_only": True,
                "paper_authority": "UNCHANGED",
                "variant": {},
            }
            CandidateOutcomeWriter(str(outcomes)).append(
                observation_id=candidate.observation_id,
                outcome_type="VIRTUAL_STRATEGY_VARIANT",
                symbol="BTCUSDT",
                direction="LONG",
                payload={
                    "exit_r": -0.1,
                    "gross_exit_r": 0.1,
                    "net_exit_r": -0.1,
                    "profitable": False,
                    "strategy_lab_catalog_version": (
                        "PHASE5_6_APPROVED_V1"
                    ),
                },
                experiment_context=context,
                outcome_variant_id="VARIANT_NET",
            )
            TrainingDatasetBuilder(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
                dataset_path=str(dataset),
                report_path=str(report),
            ).build()
            row = json.loads(dataset.read_text())
            self.assertEqual(row["target_r"], -0.1)
            self.assertFalse(row["label_profitable"])
            self.assertEqual(
                row["strategy_lab_catalog_version"],
                "PHASE5_6_APPROVED_V1",
            )
            self.assertEqual(
                row["virtual_policy"]["variant_id"],
                "VARIANT_NET",
            )


if __name__ == "__main__":
    unittest.main()
