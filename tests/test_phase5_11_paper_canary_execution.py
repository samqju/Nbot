import hashlib
import json
import pickle
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from execution.paper_account import PaperAccount
from learning.model_registry import ModelRegistry
from learning.paper_canary import (
    AutomaticPaperCanaryController,
    PaperCanaryRouter,
)
from risk.risk import RiskManager
from strategy.candidate import StrategyCandidate
from strategy.features import CandidateFeatures
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


class Phase511PaperCanaryExecutionTests(unittest.TestCase):
    def _artifact(self, path: Path, model_id: str) -> str:
        artifact = {
            "artifact_schema_version": 1,
            "model_kind": "LOGISTIC_REGRESSION_BASELINE",
            "model_id": model_id,
            "base_feature_names": FEATURE_NAMES,
            "pattern_categories": ("RANGE_BREAKOUT",),
            "scaler": IdentityScaler(),
            "model": FirstFeatureProbabilityModel(),
            "runtime_activation": "DISABLED",
        }
        data = pickle.dumps(artifact)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def _registry_with_canary(self, root: Path, model_id="MODEL_A"):
        artifact = root / f"{model_id}.pkl"
        checksum = self._artifact(artifact, model_id)
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
                "artifact_path": str(artifact),
                "artifact_checksum_sha256": checksum,
            }
        )
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
            direction="LONG",
            score=rule_score,
            pattern="RANGE_BREAKOUT",
            bucket=1,
            features=features,
            score_breakdown=Breakdown(rule_score),
            reference_price=100.0,
            observation_id=observation_id,
            decision_batch_id="batch-1",
            market_event_id="event-1",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            model_version="RULE_SYSTEM_V1",
        )

    def _router(self, root: Path, **overrides):
        args = {
            "enabled": True,
            "execution_mode": "SHADOW",
            "environment": "LIVE",
            "registry_path": str(root / "registry.json"),
            "default_champion_model_id": "RULE_SYSTEM_V1",
            "decisions_path": str(root / "canary_decisions.jsonl"),
            "trades_path": str(root / "paper_trades.jsonl"),
            "allocation_fraction": 0.10,
            "risk_multiplier": 1.0,
            "max_trades_per_utc_day": 5,
            "minimum_model_probability": 0.50,
        }
        args.update(overrides)
        return PaperCanaryRouter(**args)

    def _controller(self, root: Path, **overrides):
        args = {
            "enabled": True,
            "execution_mode": "SHADOW",
            "environment": "LIVE",
            "registry_path": str(root / "registry.json"),
            "trades_path": str(root / "paper_trades.jsonl"),
            "status_path": str(root / "canary_status.json"),
            "lock_path": str(root / "canary.lock"),
            "default_champion_model_id": "RULE_SYSTEM_V1",
            "min_completed_trades": 3,
            "max_drawdown_r": 3.0,
            "max_losing_streak": 3,
            "min_average_net_r": -0.10,
            "recent_trade_window": 2,
            "min_recent_average_net_r": -0.25,
        }
        args.update(overrides)
        return AutomaticPaperCanaryController(**args)

    @staticmethod
    def _write_trades(path: Path, model_id: str, values):
        now = int(time.time() * 1000)
        rows = [
            {
                "trade_id": f"trade-{index}",
                "closed_at_ms": now + index,
                "net_r": value,
                "selection_authority": "PAPER_CANARY",
                "paper_canary_model_id": model_id,
            }
            for index, value in enumerate(values)
        ]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_router_selects_model_candidate_at_unchanged_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registry_with_canary(root)
            low = self._candidate("BTCUSDT", 0.9, 0.1, "low")
            high = self._candidate("ETHUSDT", 0.8, 0.9, "high")
            router = self._router(root)
            batch_id = next(
                f"batch-{index}"
                for index in range(1000)
                if router._allocation(
                    model_id="MODEL_A",
                    decision_batch_id=f"batch-{index}",
                )[1] < 0.10
            )
            route = router.route(
                candidates=[low, high],
                rule_candidate=low,
                decision_batch_id=batch_id,
                market_event_id="event-1",
                candle_bucket=1,
            )
            self.assertTrue(route.is_canary)
            self.assertEqual(route.candidate.observation_id, "high")
            self.assertEqual(route.model_id, "MODEL_A")
            self.assertEqual(route.risk_multiplier, 1.0)
            record = registry.get_model("MODEL_A")
            self.assertEqual(
                record["runtime_activation"],
                "PAPER_CANARY_ACTIVE_SHADOW_ONLY",
            )
            self.assertEqual(registry.current_champion_model_id(), "RULE_SYSTEM_V1")

    def test_router_blocks_canary_outside_shadow_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry_with_canary(root)
            rule = self._candidate("BTCUSDT", 0.9, 0.1, "rule")
            route = self._router(root, execution_mode="TRADE").route(
                candidates=[rule],
                rule_candidate=rule,
                decision_batch_id="batch-1",
                market_event_id="event-1",
                candle_bucket=1,
            )
            self.assertFalse(route.is_canary)
            self.assertEqual(route.candidate.observation_id, "rule")
            self.assertIn("NON_SHADOW", route.reason)

    def test_artifact_checksum_failure_falls_back_to_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, artifact = self._registry_with_canary(root)
            artifact.write_bytes(artifact.read_bytes() + b"corrupt")
            rule = self._candidate("BTCUSDT", 0.9, 0.1, "rule")
            route = self._router(root).route(
                candidates=[rule],
                rule_candidate=rule,
                decision_batch_id="batch-1",
                market_event_id="event-1",
                candle_bucket=1,
            )
            self.assertFalse(route.is_canary)
            self.assertIn("FAILURE_FALLBACK", route.reason)
            self.assertEqual(registry.get_model("MODEL_A")["status"], "PAPER_CANARY")

    def test_daily_canary_limit_falls_back_to_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry_with_canary(root)
            self._write_trades(root / "paper_trades.jsonl", "MODEL_A", [0.1])
            rule = self._candidate("BTCUSDT", 0.9, 0.1, "rule")
            route = self._router(root, max_trades_per_utc_day=1).route(
                candidates=[rule],
                rule_candidate=rule,
                decision_batch_id="batch-1",
                market_event_id="event-1",
                candle_bucket=1,
            )
            self.assertEqual(route.reason, "PAPER_CANARY_DAILY_TRADE_LIMIT")
            self.assertFalse(route.is_canary)

    def test_trade_intent_requires_canary_identity(self):
        with self.assertRaises(ValueError):
            TradeIntent(
                symbol="BTCUSDT",
                direction="LONG",
                pattern="RANGE_BREAKOUT",
                entry_price=None,
                generated_at=datetime.now(timezone.utc),
                selection_authority="PAPER_CANARY",
                paper_risk_multiplier=1.0,
            )

    def test_canary_uses_normal_risk_plan(self):
        risk = RiskManager(
            NOTIONAL_TARGET=1000.0,
            NOTIONAL_TOLERANCE_PCT=1.0,
            RISK_PER_TRADE_USD=10.0,
            RISK_TOLERANCE_PCT=10.0,
        )
        plan = risk.build_entry_plan(
            direction="LONG",
            entry_price=100.0,
            notional_target=1000.0,
            risk_usd=10.0,
        )
        self.assertAlmostEqual(plan.quantity, 10.0)
        self.assertAlmostEqual(plan.initial_sl, 99.0)

    def test_paper_trade_persists_canary_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account = PaperAccount(
                starting_balance_usd=10000.0,
                state_path=str(root / "state.json"),
                trades_path=str(root / "trades.jsonl"),
                source="PAPER_LIVE",
            )
            account.load_or_create()
            account.open_position(
                symbol="BTCUSDT",
                side="LONG",
                qty=1.0,
                entry_price=100.0,
                stop_loss=99.0,
                opened_at_ms=1,
                initial_risk_usd=1.0,
                entry_fee_usd=0.0,
                selection_authority="PAPER_CANARY",
                paper_canary_model_id="MODEL_A",
                paper_risk_multiplier=1.0,
                paper_allocation_id="CANARY_X",
            )
            trade = account.close_position(
                exit_price=101.0,
                closed_at_ms=2,
                exit_fee_usd=0.0,
                exit_reason="TEST",
            )
            self.assertEqual(trade.selection_authority, "PAPER_CANARY")
            self.assertEqual(trade.paper_canary_model_id, "MODEL_A")
            self.assertEqual(trade.paper_risk_multiplier, 1.0)

    def test_controller_waits_without_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ModelRegistry(
                path=str(root / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            ).initialize()
            result = self._controller(root).run_once()
            self.assertEqual(result["status"], "WAITING_FOR_PAPER_CANARY")
            self.assertFalse(result["champion_changed"])

    def test_controller_records_healthy_canary_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registry_with_canary(root)
            self._write_trades(root / "paper_trades.jsonl", "MODEL_A", [0.3, -0.1, 0.2])
            result = self._controller(root).run_once()
            self.assertEqual(result["status"], "PAPER_CANARY_ACTIVE")
            self.assertEqual(registry.get_model("MODEL_A")["status"], "PAPER_CANARY")
            self.assertEqual(result["metrics"]["completed_trades"], 3)

    def test_controller_rolls_back_losing_streak_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry, _ = self._registry_with_canary(root)
            self._write_trades(root / "paper_trades.jsonl", "MODEL_A", [-1.0, -1.0, -1.0])
            result = self._controller(root).run_once()
            self.assertEqual(result["status"], "ROLLED_BACK")
            self.assertEqual(registry.get_model("MODEL_A")["status"], "ROLLED_BACK")
            self.assertIsNone(registry.current_paper_canary_model_id())
            self.assertEqual(registry.current_champion_model_id(), "RULE_SYSTEM_V1")

    def test_systemd_controller_is_separate_from_trading_engine(self):
        service = Path(
            "deploy/observation/nbot-paper-canary-controller.service.in"
        ).read_text()
        self.assertIn(
            "scripts.learning.paper_canary_controller --watch",
            service,
        )
        self.assertIn("Nice=10", service)
        self.assertNotIn("run.py", service)

    def test_failed_atomic_rollback_keeps_canary_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._registry_with_canary(root)
            self._write_trades(root / "paper_trades.jsonl", "MODEL_A", [-1.0, -1.0, -1.0])
            with patch(
                "learning.model_registry.os.replace",
                side_effect=OSError("forced replace failure"),
            ):
                with self.assertRaises(OSError):
                    self._controller(root).run_once()
            reloaded = ModelRegistry(
                path=str(root / "registry.json"),
                environment="LIVE",
                default_champion_model_id="RULE_SYSTEM_V1",
            )
            self.assertEqual(reloaded.get_model("MODEL_A")["status"], "PAPER_CANARY")
            self.assertEqual(reloaded.current_paper_canary_model_id(), "MODEL_A")
