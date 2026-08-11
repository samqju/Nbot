import tempfile
import unittest
from pathlib import Path
from strategy.candidate import StrategyCandidate
from strategy.candidate_risk import CandidateRiskPlan
from strategy.experiment_contract import build_experiment_context
from strategy.features import CandidateFeatures
from strategy.strategy_lab import build_approved_variant_catalog
from strategy.virtual_trade_engine import VirtualTradeEngine


class RuntimeStore:
    def __init__(self):
        self.sections = {
            "active_virtual_trades": [],
        }

    def get_section(self, section):
        return list(self.sections.get(section, []))

    def replace_section(self, section, rows):
        self.sections[section] = list(rows)


class LogProbe:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warning(self, message):
        self.warnings.append(message)

    def info(self, message):
        self.infos.append(message)


def catalog():
    return build_approved_variant_catalog(
        baseline_variant_id="VIRTUAL_FIXED_2R_24C_V1",
        baseline_target_r=2.0,
        baseline_max_candles=24,
    )


def candidate(index=1, pattern="RANGE_BREAKOUT"):
    context = build_experiment_context(
        decision_batch_id="batch-1",
        market_event_id="event-1",
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
    row = StrategyCandidate(
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
        observation_id=f"candidate-{index}",
        decision_batch_id="batch-1",
        market_event_id="event-1",
        strategy_version="STRUCTURE_RULES_V1",
        strategy_variant_id="STRUCTURE_CANDIDATE_GENERATOR_V1",
        model_version="RULE_SYSTEM_V1",
        experiment_context=context,
    )
    return row



class Phase6B4VirtualExperimentCapacityTests(unittest.TestCase):
    def make_engine(self, *, max_active):
        engine = VirtualTradeEngine(
            system_log=LogProbe(),
            runtime_store=RuntimeStore(),
            lab_enabled=True,
            variant_catalog=catalog(),
            max_active=max_active,
            environment="LIVE",
            execution_mode="SHADOW",
        )
        engine.path = Path(tempfile.mkdtemp()) / "virtual.jsonl"
        return engine

    def test_capacity_rejection_is_counted_and_summarized(self):
        engine = self.make_engine(max_active=2)

        created = engine.enroll_all([candidate()])
        metrics = engine.metrics_snapshot()

        self.assertEqual(created, 2)
        self.assertEqual(metrics["runtime_enrollment_attempts"], 3)
        self.assertEqual(metrics["runtime_enrollments"], 2)
        self.assertEqual(metrics["runtime_capacity_rejections"], 1)
        self.assertEqual(metrics["active_experiments"], 2)
        self.assertEqual(metrics["capacity_remaining"], 0)
        self.assertEqual(metrics["capacity_utilization"], 1.0)
        self.assertEqual(metrics["peak_active_experiments"], 2)
        self.assertEqual(len(engine.system_log.warnings), 1)
        self.assertIn("rejected=1", engine.system_log.warnings[0])

    def test_capacity_telemetry_has_headroom_when_not_saturated(self):
        engine = self.make_engine(max_active=10)

        created = engine.enroll_all([candidate()])
        metrics = engine.metrics_snapshot()

        self.assertEqual(created, 3)
        self.assertEqual(metrics["runtime_capacity_rejections"], 0)
        self.assertEqual(metrics["active_experiments"], 3)
        self.assertEqual(metrics["max_active_experiments"], 10)
        self.assertEqual(metrics["capacity_remaining"], 7)
        self.assertAlmostEqual(metrics["capacity_utilization"], 0.3)
        self.assertEqual(metrics["peak_active_experiments"], 3)
        self.assertEqual(engine.system_log.warnings, [])

    def test_recovered_active_rows_seed_peak_capacity_metric(self):
        store = RuntimeStore()
        base = self.make_engine(max_active=10)
        base.enroll_all([candidate()])
        store.sections["active_virtual_trades"] = (
            base.runtime_state_snapshot()
        )

        engine = VirtualTradeEngine(
            runtime_store=store,
            lab_enabled=True,
            variant_catalog=catalog(),
            max_active=10,
            environment="LIVE",
            execution_mode="SHADOW",
        )
        metrics = engine.metrics_snapshot()

        self.assertEqual(metrics["active_experiments"], 3)
        self.assertEqual(metrics["peak_active_experiments"], 3)
        self.assertEqual(metrics["runtime_capacity_rejections"], 0)


    def test_enroll_all_supports_phase6b1_lightweight_probe(self):
        engine = VirtualTradeEngine.__new__(VirtualTradeEngine)
        engine.lab_enabled = False
        engine._baseline_variant = object()
        engine.system_log = None
        engine.catalog_version = "TEST"
        engine._active_state_dirty = False

        persist_flags = []
        flushes = []

        def fake_enroll(_candidate, _variant, *, persist=True):
            persist_flags.append(persist)
            engine._active_state_dirty = True
            return True

        def fake_flush():
            flushes.append(True)
            engine._active_state_dirty = False
            return True

        engine._enroll_variant = fake_enroll
        engine.flush_active_state = fake_flush

        created = VirtualTradeEngine.enroll_all(
            engine,
            [object() for _ in range(25)],
        )

        self.assertEqual(created, 25)
        self.assertEqual(persist_flags, [False] * 25)
        self.assertEqual(len(flushes), 1)


if __name__ == "__main__":
    unittest.main()
