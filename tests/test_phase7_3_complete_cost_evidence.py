import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from execution.binance_market_client import BinanceMarketClient
from learning.cost_evidence import (
    PHASE7_COMPLETE_COST_BASIS,
    has_complete_cost_evidence,
)
from learning.training_orchestrator import TrainingInventory
from observation.virtual_cost_evidence import (
    ObservationVirtualCostEvidenceProvider,
)
from workers.observation_worker import ObservationWorker
from strategy.candidate import StrategyCandidate
from strategy.candidate_outcome import CandidateOutcomeWriter
from strategy.candidate_risk import CandidateRiskPlan
from strategy.experiment_contract import (
    build_experiment_context,
    experiment_projection,
)
from strategy.features import CandidateFeatures
from strategy.strategy import Strategy
from strategy.strategy_lab import estimate_round_trip_cost_r
from strategy.virtual_trade_engine import VirtualTradeEngine


class SilentLog:
    def debug(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class Phase73CompleteCostEvidenceTests(unittest.TestCase):
    @staticmethod
    def _observed_context(spread_pct=0.04):
        return {
            "schema_version": 1,
            "source": "TEST",
            "observed_at_ms": 1_700_000_000_000,
            "candle_bucket": 123,
            "coverage": 1.0,
            "market_regime": "BULLISH",
            "trend_regime": "BULLISH",
            "volatility_regime": "NORMAL",
            "btc_regime": "BULLISH",
            "btc_change_pct_24h": 2.0,
            "market_breadth": {
                "symbols_expected": 200,
                "symbols_observed": 200,
                "coverage": 1.0,
                "advancing_fraction": 0.7,
                "declining_fraction": 0.3,
                "unchanged_fraction": 0.0,
                "median_change_pct_24h": 2.0,
                "median_abs_change_pct_24h": 3.0,
            },
            "liquidity_by_symbol": {
                "BTCUSDT": {
                    "spread_pct": spread_pct,
                    "quote_volume_usd": 1_000_000_000.0,
                }
            },
            "completeness": "COMPLETE_PHASE7_1",
        }

    def _context(self, *, event="event-73", spread_pct=0.04):
        return build_experiment_context(
            decision_batch_id="batch-73",
            market_event_id=event,
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            selection_model_version="RULE_SYSTEM_V1",
            environment="LIVE",
            execution_mode="SHADOW",
            candle_bucket=123,
            structure_fingerprint={
                "structure": "RANGE_BREAKOUT",
                "trend": "UP",
                "volatility": "NORMAL",
                "compression": False,
            },
            candidate_symbol="BTCUSDT",
            observed_market_context=self._observed_context(spread_pct),
            paper_taker_fee_rate=0.0005,
            paper_entry_slippage_pct=0.02,
            paper_exit_slippage_pct=0.02,
            virtual_variant_id="VIRTUAL_FIXED_2R_24C_V1",
            virtual_target_r=2.0,
            virtual_max_candles=24,
            paper_variant_id="PAPER_TRAILING_SL_V1",
        )

    def _candidate(self):
        context = self._context()
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
        return StrategyCandidate(
            symbol="BTCUSDT",
            direction="LONG",
            score=0.8,
            pattern="RANGE_BREAKOUT",
            bucket=123,
            features=CandidateFeatures(
                0.01, 0.02, 5, 0.2, 0.8, 1.1, -0.01, 0.03, 4
            ),
            reference_price=100,
            risk_plan=risk,
            decision_batch_id="batch-73",
            market_event_id="event-73",
            strategy_version="STRUCTURE_RULES_V1",
            strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
            model_version="RULE_SYSTEM_V1",
            experiment_context=context,
        )

    def test_market_client_reads_bulk_book_and_funding_history(self):
        client = object.__new__(BinanceMarketClient)
        calls = []

        def public_get(path, params=None):
            calls.append((path, params))
            if path.endswith("bookTicker"):
                return [
                    {
                        "symbol": "BTCUSDT",
                        "bidPrice": "99.99",
                        "askPrice": "100.01",
                    },
                    {
                        "symbol": "ETHUSDT",
                        "bidPrice": "49.99",
                        "askPrice": "50.01",
                    },
                ]
            return [
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.0001",
                    "fundingTime": 1_700_000_100_000,
                    "markPrice": "101.0",
                    "rateType": "Regular",
                }
            ]

        client._public_get = public_get
        result = client.get_virtual_cost_evidence_rows(
            symbols=["BTCUSDT", "ETHUSDT"],
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_300_000,
        )
        self.assertEqual(
            [path for path, _ in calls],
            ["/fapi/v1/ticker/bookTicker", "/fapi/v1/fundingRate"],
        )
        self.assertAlmostEqual(result["spread_by_symbol"]["BTCUSDT"], 0.02)
        self.assertEqual(
            result["funding_events_by_symbol"]["BTCUSDT"][0]["funding_rate"],
            0.0001,
        )
        self.assertTrue(result["funding_history_complete"])

    def test_market_client_paginates_funding_history_without_skipping_boundary(self):
        client = object.__new__(BinanceMarketClient)
        funding_calls = []
        first_page = [
            {
                "symbol": "BTCUSDT",
                "fundingRate": "0.0001",
                "fundingTime": 1_700_000_000_001 + index,
                "markPrice": "100.0",
                "rateType": "Regular",
            }
            for index in range(1000)
        ]
        last = first_page[-1]

        def public_get(path, params=None):
            if path.endswith("bookTicker"):
                return [{
                    "symbol": "BTCUSDT",
                    "bidPrice": "99.99",
                    "askPrice": "100.01",
                }]
            funding_calls.append(dict(params or {}))
            if len(funding_calls) == 1:
                return first_page
            return [dict(last)]

        client._public_get = public_get
        result = client.get_virtual_cost_evidence_rows(
            symbols=["BTCUSDT"],
            start_ms=1_700_000_000_000,
            end_ms=1_700_001_000_000,
        )
        self.assertEqual(len(funding_calls), 2)
        self.assertEqual(
            funding_calls[1]["startTime"],
            last["fundingTime"],
        )
        self.assertEqual(result["funding_rows_returned"], 1000)
        self.assertEqual(result["funding_pages"], 2)
        self.assertTrue(result["funding_history_complete"])

    def test_malformed_unrequested_funding_row_does_not_poison_history(self):
        client = object.__new__(BinanceMarketClient)

        def public_get(path, params=None):
            if path.endswith("bookTicker"):
                return [{
                    "symbol": "BTCUSDT",
                    "bidPrice": "99.99",
                    "askPrice": "100.01",
                }]
            return [
                {
                    "symbol": "UNRELATEDUSDT",
                    "fundingRate": "not-a-number",
                    "fundingTime": 1_700_000_050_000,
                    "markPrice": "bad",
                },
                {
                    "symbol": "BTCUSDT",
                    "fundingRate": "0.0001",
                    "fundingTime": 1_700_000_100_000,
                    "markPrice": "101.0",
                },
            ]

        client._public_get = public_get
        result = client.get_virtual_cost_evidence_rows(
            symbols=["BTCUSDT"],
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_300_000,
        )
        self.assertTrue(result["funding_history_complete"])
        self.assertEqual(result["funding_parse_errors"], 0)
        self.assertEqual(
            result["funding_events_by_symbol"]["BTCUSDT"][0]["funding_rate"],
            0.0001,
        )

    def test_malformed_target_funding_event_fails_history_closed(self):
        client = object.__new__(BinanceMarketClient)

        def public_get(path, params=None):
            if path.endswith("bookTicker"):
                return [{
                    "symbol": "BTCUSDT",
                    "bidPrice": "99.99",
                    "askPrice": "100.01",
                }]
            return [{
                "symbol": "BTCUSDT",
                "fundingRate": "not-a-number",
                "fundingTime": 1_700_000_100_000,
                "markPrice": "101.0",
            }]

        client._public_get = public_get
        result = client.get_virtual_cost_evidence_rows(
            symbols=["BTCUSDT"],
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_300_000,
        )
        self.assertFalse(result["funding_history_complete"])
        self.assertEqual(result["funding_parse_errors"], 1)

    def test_provider_marks_complete_window_and_preserves_actual_funding(self):
        class Client:
            def get_virtual_cost_evidence_rows(self, **_kwargs):
                return {
                    "spread_by_symbol": {"BTCUSDT": 0.04, "ETHUSDT": 0.05},
                    "funding_events_by_symbol": {
                        "BTCUSDT": [{
                            "funding_time": 1_700_000_100_000,
                            "funding_rate": 0.0001,
                            "mark_price": 101.0,
                            "rate_type": "Regular",
                        }]
                    },
                    "funding_coverage_start_ms": 1_700_000_000_000,
                    "funding_coverage_end_ms": 1_700_000_300_000,
                    "funding_history_complete": True,
                    "funding_rows_returned": 1,
                }

        snapshot = ObservationVirtualCostEvidenceProvider(
            market_client=Client(), system_log=SilentLog()
        ).snapshot(
            symbols=["BTCUSDT", "ETHUSDT"],
            candle_bucket=123,
            start_ms=1_700_000_000_000,
            end_ms=1_700_000_300_000,
        )
        self.assertEqual(snapshot["completeness"], "COMPLETE_PHASE7_3")
        self.assertEqual(snapshot["spread_coverage"], 1.0)
        self.assertEqual(
            snapshot["funding_events_by_symbol"]["BTCUSDT"][0]["funding_rate"],
            0.0001,
        )

    def test_cost_estimator_uses_half_spread_each_side_and_actual_funding(self):
        result = estimate_round_trip_cost_r(
            entry_price=100,
            exit_price=102,
            risk_distance=1,
            taker_fee_rate=0.0005,
            entry_slippage_pct=0.02,
            exit_slippage_pct=0.02,
            entry_spread_pct=0.04,
            exit_spread_pct=0.06,
            direction="LONG",
            funding_events=[{
                "funding_time": 1_700_000_100_000,
                "funding_rate": 0.0001,
                "mark_price": 101.0,
                "rate_type": "Regular",
            }],
            funding_history_complete=True,
        )
        self.assertAlmostEqual(result["spread_r"], 0.0506)
        self.assertAlmostEqual(result["funding_r"], 0.0101)
        self.assertEqual(result["funding_event_count"], 1)
        self.assertEqual(result["cost_completeness"], PHASE7_COMPLETE_COST_BASIS)

        short = estimate_round_trip_cost_r(
            entry_price=100,
            exit_price=99,
            risk_distance=1,
            taker_fee_rate=0.0005,
            entry_slippage_pct=0.02,
            exit_slippage_pct=0.02,
            entry_spread_pct=0.04,
            exit_spread_pct=0.04,
            direction="SHORT",
            funding_events=[{
                "funding_time": 1_700_000_100_000,
                "funding_rate": 0.0001,
                "mark_price": 100.0,
            }],
            funding_history_complete=True,
        )
        self.assertAlmostEqual(short["funding_r"], -0.01)

        no_event = estimate_round_trip_cost_r(
            entry_price=100,
            exit_price=101,
            risk_distance=1,
            taker_fee_rate=0.0005,
            entry_slippage_pct=0.02,
            exit_slippage_pct=0.02,
            entry_spread_pct=0.04,
            exit_spread_pct=0.04,
            direction="LONG",
            funding_events=[],
            funding_history_complete=True,
        )
        self.assertEqual(no_event["funding_r"], 0.0)
        self.assertEqual(
            no_event["cost_completeness"], PHASE7_COMPLETE_COST_BASIS
        )

    def test_virtual_outcome_records_complete_cost_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            outcomes_path = root / "outcomes.jsonl"
            virtual_path = root / "virtual.jsonl"
            writer = CandidateOutcomeWriter(
                str(outcomes_path), environment="LIVE", execution_mode="SHADOW"
            )
            import strategy.virtual_trade_engine as module
            with patch.object(module, "VIRTUAL_TRADES_PATH", str(virtual_path)):
                engine = VirtualTradeEngine(
                    outcome_writer=writer,
                    lab_enabled=False,
                    max_active=20,
                )
            candidate = self._candidate()
            self.assertTrue(engine.enroll(candidate))
            opened = engine.oldest_active_opened_at_ms()
            self.assertIsNotNone(opened)
            closed = opened + 120_000
            engine.set_cost_evidence_snapshot({
                "spread_by_symbol": {"BTCUSDT": 0.06},
                "funding_events_by_symbol": {
                    "BTCUSDT": [{
                        "funding_time": opened + 60_000,
                        "funding_rate": 0.0001,
                        "mark_price": 101.0,
                        "rate_type": "Regular",
                    }]
                },
                "funding_coverage_start_ms": opened - 1,
                "funding_coverage_end_ms": closed,
                "funding_history_complete": True,
            })
            results = engine.on_candle(
                "BTCUSDT",
                (100.0, 102.5, 99.8, 102.0),
                closed_at_ms=closed,
            )
            self.assertEqual(len(results), 1)
            breakdown = results[0]["cost_breakdown"]
            self.assertEqual(
                breakdown["cost_completeness"], PHASE7_COMPLETE_COST_BASIS
            )
            self.assertGreater(breakdown["spread_r"], 0)
            self.assertGreater(breakdown["funding_r"], 0)
            self.assertLess(results[0]["net_exit_r"], results[0]["gross_exit_r"])

            row = json.loads(outcomes_path.read_text().splitlines()[0])
            self.assertTrue(has_complete_cost_evidence(row))

    def test_strategy_cost_window_starts_at_exact_oldest_active_trade(self):
        strategy = object.__new__(Strategy)
        strategy._virtual_trade_engine = SimpleNamespace(
            oldest_active_opened_at_ms=lambda: 1_700_000_250_000
        )
        self.assertEqual(
            strategy.get_virtual_cost_evidence_start_ms(
                default_start_ms=1_700_000_000_000
            ),
            1_700_000_250_000,
        )

    def test_observation_worker_retries_partial_cost_snapshot_before_rollover(self):
        class StrategyDouble:
            def __init__(self):
                self.snapshots = []

            def set_virtual_cost_evidence(self, snapshot):
                self.snapshots.append(snapshot)

            def get_virtual_cost_evidence_start_ms(self, *, default_start_ms):
                return default_start_ms + 3_300_000

        class Provider:
            def __init__(self):
                self.calls = []

            def snapshot(self, **kwargs):
                self.calls.append(kwargs)
                if len(self.calls) == 1:
                    return {
                        "completeness": "PARTIAL_PHASE7_3",
                        "funding_history_complete": False,
                        "funding_rows_returned": 1000,
                        "funding_pages": 1,
                        "funding_parse_errors": 0,
                    }
                return {
                    "completeness": "COMPLETE_PHASE7_3",
                    "funding_history_complete": True,
                    "funding_rows_returned": 12,
                    "funding_pages": 1,
                    "funding_parse_errors": 0,
                }

        worker = object.__new__(ObservationWorker)
        worker.strategy = StrategyDouble()
        worker.universe = SimpleNamespace(observation_symbols={"BTCUSDT"})
        worker.virtual_cost_evidence_provider = Provider()
        worker.system_log = SilentLog()
        worker._last_virtual_cost_bucket = None
        tick = SimpleNamespace(timestamp=1_700_000_400_000)

        worker._maybe_refresh_virtual_cost_evidence(tick)
        worker._maybe_refresh_virtual_cost_evidence(tick)

        self.assertEqual(len(worker.virtual_cost_evidence_provider.calls), 2)
        self.assertEqual(len(worker.strategy.snapshots), 1)
        self.assertEqual(
            worker.strategy.snapshots[0]["completeness"],
            "COMPLETE_PHASE7_3",
        )

    def test_observation_worker_collects_cost_evidence_once_per_bucket(self):
        class Strategy:
            def __init__(self):
                self.snapshots = []

            def set_virtual_cost_evidence(self, snapshot):
                self.snapshots.append(snapshot)

            def get_virtual_cost_evidence_start_ms(self, *, default_start_ms):
                return default_start_ms - 300_000

        class Provider:
            def __init__(self):
                self.calls = []

            def snapshot(self, **kwargs):
                self.calls.append(kwargs)
                return {"completeness": "COMPLETE_PHASE7_3"}

        worker = object.__new__(ObservationWorker)
        worker.strategy = Strategy()
        worker.universe = SimpleNamespace(
            observation_symbols={"BTCUSDT", "ETHUSDT"}
        )
        worker.virtual_cost_evidence_provider = Provider()
        worker.system_log = SilentLog()
        worker._last_virtual_cost_bucket = None
        tick = SimpleNamespace(timestamp=1_700_000_400_000)

        worker._maybe_refresh_virtual_cost_evidence(tick)
        worker._maybe_refresh_virtual_cost_evidence(tick)

        self.assertEqual(len(worker.virtual_cost_evidence_provider.calls), 1)
        call = worker.virtual_cost_evidence_provider.calls[0]
        self.assertEqual(set(call["symbols"]), {"BTCUSDT", "ETHUSDT"})
        self.assertEqual(
            call["start_ms"],
            tick.timestamp - (4 * 60 * 60 * 1000) - 300_000,
        )
        self.assertEqual(len(worker.strategy.snapshots), 1)

    def test_observation_worker_cost_failure_degrades_learning_only(self):
        warnings = []

        class Log(SilentLog):
            def warning(self, message):
                warnings.append(message)

        class Strategy:
            def set_virtual_cost_evidence(self, _snapshot):
                raise AssertionError("setter must not run on provider failure")

        class Provider:
            def __init__(self):
                self.calls = 0

            def snapshot(self, **_kwargs):
                self.calls += 1
                raise RuntimeError("simulated funding outage")

        worker = object.__new__(ObservationWorker)
        worker.strategy = Strategy()
        worker.universe = SimpleNamespace(observation_symbols={"BTCUSDT"})
        worker.virtual_cost_evidence_provider = Provider()
        worker.system_log = Log()
        worker._last_virtual_cost_bucket = None
        tick = SimpleNamespace(timestamp=1_700_000_400_000)

        worker._maybe_refresh_virtual_cost_evidence(tick)
        worker._maybe_refresh_virtual_cost_evidence(tick)

        self.assertEqual(worker.virtual_cost_evidence_provider.calls, 2)
        self.assertTrue(
            any("learning_cost_completeness=PARTIAL" in row for row in warnings)
        )

    def test_training_inventory_excludes_partial_cost_labels(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            observations = []
            outcomes = []
            for index, complete in ((1, True), (2, False)):
                context = self._context(event=f"event-{index}")
                projection = experiment_projection(context)
                candidate_id = f"candidate-{index}"
                observations.append({
                    "candidate_observation_id": candidate_id,
                    **projection,
                    "experiment_contract_version": 1,
                    "market_context": context["market_context"],
                    "experiment_context": context,
                })
                breakdown = {
                    "spread_r": 0.01 if complete else None,
                    "funding_r": 0.0 if complete else None,
                    "total_cost_r": 0.05,
                    "cost_completeness": (
                        PHASE7_COMPLETE_COST_BASIS
                        if complete
                        else "FEES_AND_CONFIGURED_SLIPPAGE_ONLY"
                    ),
                }
                outcomes.append({
                    "candidate_observation_id": candidate_id,
                    "outcome_type": "VIRTUAL_TRADE",
                    "outcome_variant_id": "VIRTUAL_FIXED_2R_24C_V1",
                    "recorded_at_ms": 1_700_000_000_000 + index * 300_000,
                    "payload": {"cost_breakdown": breakdown},
                })

            obs_path = root / "observations.jsonl"
            out_path = root / "outcomes.jsonl"
            obs_path.write_text("".join(json.dumps(x) + "\n" for x in observations))
            out_path.write_text("".join(json.dumps(x) + "\n" for x in outcomes))
            report = TrainingInventory(
                observations_path=str(obs_path),
                outcomes_path=str(out_path),
                outcome_type="VIRTUAL_TRADE",
                require_complete_market_context=True,
                require_complete_cost_evidence=True,
            ).scan(after_ms=0)
            self.assertEqual(report["new_completed_outcomes"], 1)
            self.assertEqual(report["new_independent_market_events"], 1)
            self.assertEqual(
                report["issues"]["cost_evidence_incomplete_excluded"], 1
            )


if __name__ == "__main__":
    unittest.main()
