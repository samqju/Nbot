import json
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from execution.paper_account import PaperAccount
from execution.paper_exchange import PaperExchange
from learning.dataset_builder import TrainingDatasetBuilder
from learning.shadow_scorer import ShadowModelScorer
from strategy.candidate import StrategyCandidate
from strategy.candidate_observer import CandidateObservationWriter
from strategy.candidate_outcome import CandidateOutcomeWriter
from strategy.experiment_contract import (
    EXPERIMENT_CONTRACT_VERSION,
    build_experiment_context,
    build_market_event_id,
    validate_experiment_context,
)
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


class SilentLog:
    def info(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


class MarketClient:
    def quantize_price(self, symbol, price):
        return float(price)

    def get_last_price(self, symbol):
        return 100.0


class Breakdown:
    def __init__(self, rule_score):
        self.rule_score = rule_score

    def as_dict(self):
        return {
            "rule_score": self.rule_score,
            "final_score": self.rule_score,
        }


class Phase55ExperimentDataContractTests(unittest.TestCase):
    def _context(self, *, batch="batch-1", event="event-1"):
        return build_experiment_context(
            decision_batch_id=batch,
            market_event_id=event,
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=123,
            structure_fingerprint={
                "structure": "TREND_CONTINUATION",
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

    def _candidate(self, context=None):
        context = context or self._context()
        return StrategyCandidate(
            symbol="BTCUSDT",
            direction="LONG",
            score=0.8,
            pattern="RANGE_BREAKOUT",
            bucket=123,
            features=CandidateFeatures(
                0.01, 0.02, 5, 0.2, 0.8, 1.1, -0.01, 0.03, 4
            ),
            structure_fingerprint={"trend": "UP"},
            score_breakdown=Breakdown(0.7),
            reference_price=100.0,
            decision_batch_id=context["decision_batch_id"],
            market_event_id=context["market_event_id"],
            strategy_version=context["strategy_version"],
            strategy_variant_id=context["strategy_variant_id"],
            model_version=context["selection_model_version"],
            execution_eligible=True,
            experiment_context=context,
        )

    def test_contract_explicitly_versions_context_and_missing_inputs(self):
        context = self._context()
        validate_experiment_context(context)
        self.assertEqual(
            context["contract_version"],
            EXPERIMENT_CONTRACT_VERSION,
        )
        self.assertEqual(
            context["market_context"]["market_regime"],
            "TREND_CONTINUATION",
        )
        self.assertIsNone(context["market_context"]["btc_regime"])
        self.assertEqual(
            context["market_context"]["completeness"],
            "PARTIAL_PHASE5_5",
        )

    def test_market_event_id_is_stable_for_same_candle(self):
        first = build_market_event_id(
            environment="LIVE",
            candle_bucket=123,
        )
        second = build_market_event_id(
            environment="LIVE",
            candle_bucket=123,
        )
        different = build_market_event_id(
            environment="LIVE",
            candle_bucket=124,
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)

    def test_observation_outcome_and_dataset_share_contract(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations = root / "observations.jsonl"
            outcomes = root / "outcomes.jsonl"
            dataset = root / "dataset.jsonl"
            report = root / "report.json"
            context = self._context()
            candidate = self._candidate(context)

            CandidateObservationWriter(str(observations)).append(
                candidate,
                rank=1,
                selected=True,
            )
            CandidateOutcomeWriter(str(outcomes)).append(
                observation_id=candidate.observation_id,
                outcome_type="VIRTUAL_TRADE",
                symbol=candidate.symbol,
                direction=candidate.direction,
                payload={
                    "exit_r": 2.0,
                    "profitable": True,
                },
                experiment_context=context,
                outcome_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            )

            built = TrainingDatasetBuilder(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
                dataset_path=str(dataset),
                report_path=str(report),
            ).build()
            row = json.loads(dataset.read_text())
            self.assertEqual(built["status"], "READY")
            self.assertEqual(row["experiment_contract_version"], 1)
            self.assertEqual(row["decision_batch_id"], "batch-1")
            self.assertEqual(row["market_event_id"], "event-1")
            self.assertEqual(
                row["outcome_variant_id"],
                "VIRTUAL_FIXED_2R_24C_V1",
            )
            self.assertFalse(row["legacy_record"])

    def test_contract_mismatch_is_excluded_from_dataset(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations = root / "observations.jsonl"
            outcomes = root / "outcomes.jsonl"
            dataset = root / "dataset.jsonl"
            report = root / "report.json"
            candidate = self._candidate(self._context(batch="batch-a"))
            CandidateObservationWriter(str(observations)).append(
                candidate,
                rank=1,
                selected=True,
            )
            CandidateOutcomeWriter(str(outcomes)).append(
                observation_id=candidate.observation_id,
                outcome_type="VIRTUAL_TRADE",
                symbol=candidate.symbol,
                direction=candidate.direction,
                payload={"exit_r": -1.0, "profitable": False},
                experiment_context=self._context(batch="batch-b"),
                outcome_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            )
            built = TrainingDatasetBuilder(
                observations_path=str(observations),
                outcomes_path=str(outcomes),
                dataset_path=str(dataset),
                report_path=str(report),
            ).build()
            self.assertEqual(built["output"]["rows_written"], 0)
            self.assertEqual(
                built["issues"][
                    "experiment_context_decision_batch_id_mismatch"
                ],
                1,
            )

    def test_paper_trade_preserves_experiment_identity(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            account = PaperAccount(
                starting_balance_usd=10000,
                state_path=str(root / "state.json"),
                trades_path=str(root / "trades.jsonl"),
                source="PAPER_LIVE",
            )
            account.load_or_create()
            exchange = PaperExchange(
                market_client=MarketClient(),
                account=account,
                system_log=SilentLog(),
            )
            ack = exchange.place_entry(
                symbol="BTCUSDT",
                side="LONG",
                quantity=1.0,
                price=100.0,
                client_order_id="phase55",
            )
            context = self._context()
            exchange.set_pending_entry_metadata(
                symbol="BTCUSDT",
                client_order_id="phase55",
                metadata={
                    "candidate_observation_id": "candidate-55",
                    "decision_batch_id": "batch-1",
                    "market_event_id": "event-1",
                    "strategy_version": "STRUCTURE_RULES_V1",
                    "strategy_variant_id": (
                        "STRUCTURE_CANDIDATE_GENERATOR_V1"
                    ),
                    "model_version": "RULE_SYSTEM_V1",
                    "pattern": "RANGE_BREAKOUT",
                    "structure_fingerprint": {"trend": "UP"},
                    "experiment_context": context,
                },
            )
            exchange.place_initial_sl(
                symbol="BTCUSDT",
                side="LONG",
                qty=ack.filled_qty,
                stop_price=95.0,
            )
            position = account.get_open_position()
            self.assertEqual(
                position.candidate_observation_id,
                "candidate-55",
            )
            self.assertEqual(position.decision_batch_id, "batch-1")
            self.assertEqual(position.pattern, "RANGE_BREAKOUT")
            trade = exchange.emergency_exit()
            self.assertEqual(trade.market_event_id, "event-1")
            self.assertEqual(
                trade.experiment_context["contract_version"],
                1,
            )

    def test_shadow_prediction_records_batch_and_artifact_version(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            candidate = self._candidate()
            vector = (
                [float(candidate.features.as_dict()[name]) for name in FEATURE_NAMES]
                + [0.7, 0.8, 1.0, 1.0]
            )
            X = np.asarray([
                [value + (index * 0.001 if col == 0 else 0.0)
                 for col, value in enumerate(vector)]
                for index in range(20)
            ])
            y = np.asarray([index % 2 for index in range(20)])
            scaler = StandardScaler().fit(X)
            model = LogisticRegression(max_iter=1000).fit(
                scaler.transform(X),
                y,
            )
            artifact = {
                "artifact_schema_version": 1,
                "artifact_kind": "OFFLINE_ENSEMBLE_EXPERIMENT",
                "base_feature_names": FEATURE_NAMES,
                "pattern_categories": ("RANGE_BREAKOUT",),
                "vector_columns": tuple(range(X.shape[1])),
                "scaler": scaler,
                "models": {"LOGISTIC_REGRESSION": model},
                "winner": {
                    "kind": "MODEL",
                    "name": "LOGISTIC_REGRESSION",
                },
                "runtime_activation": "DISABLED",
            }
            artifact_path = root / "artifact.pkl"
            artifact_path.write_bytes(pickle.dumps(artifact))
            predictions_path = root / "predictions.jsonl"
            ShadowModelScorer(
                enabled=True,
                artifact_path=artifact_path,
                predictions_path=predictions_path,
            ).score_candidates(
                [candidate],
                rule_selected_candidate=candidate,
            )
            row = json.loads(predictions_path.read_text())
            self.assertEqual(row["decision_batch_id"], "batch-1")
            self.assertEqual(row["market_event_id"], "event-1")
            self.assertTrue(
                row["shadow_model_version"].startswith("sha256:")
            )
            self.assertEqual(row["schema_version"], 2)


if __name__ == "__main__":
    unittest.main()
