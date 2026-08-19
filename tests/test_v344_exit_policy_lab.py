from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import unittest

from nbot.observation.models import Candle, FundingEvent
from nbot.observation.outcomes import FuturePathStore, OUTCOME_VERSION
from nbot.observation.policies import (
    CONTROL_POLICY_VERSION,
    LAB_VERSION,
    POLICIES,
    POLICY_BY_VERSION,
    ExitPolicyConfig,
    ExitPolicyLab,
    _result_digest,
    simulate_policy,
)
from tests.test_v343_future_paths import (
    FakePublicClient,
    INTERVAL,
    SYMBOL,
    TARGET_OPEN,
    isolated_live_db,
    seed_target_and_future,
)


def make_bar(index: int, *, open_price: float, high: float, low: float, close: float) -> Candle:
    open_ms = index * INTERVAL
    return Candle(
        symbol=SYMBOL,
        open_time_ms=open_ms,
        close_time_ms=open_ms + INTERVAL - 1,
        open_price=open_price,
        high_price=high,
        low_price=low,
        close_price=close,
        base_volume=1000.0,
        quote_volume=100000.0,
        trade_count=100,
        taker_buy_base_volume=500.0,
        taker_buy_quote_volume=50000.0,
    )


def simulate(policy_version: str, path: list[Candle], *, side: str = "LONG", funding=()):
    entry = 100.0
    risk = 0.01
    if side == "LONG":
        favorable = max(c.high_price for c in path) / entry - 1.0
        adverse = max(0.0, 1.0 - min(c.low_price for c in path) / entry)
    else:
        favorable = max(0.0, 1.0 - min(c.low_price for c in path) / entry)
        adverse = max(c.high_price for c in path) / entry - 1.0
    return simulate_policy(
        spec=POLICY_BY_VERSION[policy_version],
        side=side,
        entry_price=entry,
        risk_frac=risk,
        path=path,
        funding_events=list(funding),
        roundtrip_base_cost_frac=0.001,
        full_mfe_frac=max(0.0, favorable),
        full_mae_frac=max(0.0, adverse),
        time_to_mfe_min=5,
        interval_minutes=5,
    )


def future_layer_digest(db) -> str:
    digest = hashlib.sha256()
    with db.connection() as conn:
        for table, sql in (
            ("future_path_sets", "SELECT * FROM future_path_sets ORDER BY outcome_version"),
            ("future_candle_cache", "SELECT * FROM future_candle_cache ORDER BY symbol,event_open_ms"),
            ("future_paths", "SELECT * FROM future_paths ORDER BY event_open_ms,symbol,outcome_version"),
            ("future_path_builds", "SELECT * FROM future_path_builds ORDER BY event_open_ms,outcome_version"),
            ("future_path_attempts", "SELECT * FROM future_path_attempts ORDER BY id"),
        ):
            for row in conn.execute(sql):
                digest.update(json.dumps([table, list(row)], separators=(",", ":"), allow_nan=True).encode())
                digest.update(b"\n")
    return digest.hexdigest()


def seed_policy_lab(db, *, funding_events=()):
    seed_target_and_future(db, funding_events=tuple(funding_events))
    outcomes = FuturePathStore(db, FakePublicClient())
    built = outcomes.build(max_events=0)
    if built.built_events <= 0:
        raise AssertionError(built)
    return ExitPolicyLab(db)


class V344PolicySimulationTests(unittest.TestCase):
    def test_catalog_has_one_control_and_seven_challengers_and_frozen_config(self):
        self.assertEqual(len(POLICIES), 8)
        self.assertEqual([p.policy_version for p in POLICIES if p.is_control], [CONTROL_POLICY_VERSION])
        self.assertEqual(LAB_VERSION, "EXIT_POLICY_LAB_V1")
        with self.assertRaisesRegex(ValueError, "LAB_VERSION_IMMUTABLE"):
            replace(ExitPolicyConfig(), lab_version="CHANGED").validate()

    def test_all_policy_traces_start_at_minus_one_r_and_never_loosen(self):
        path = [
            make_bar(i, open_price=100+i*.2, high=101.2+i*.3, low=99.5+i*.2, close=100.5+i*.25)
            for i in range(1, 20)
        ]
        for policy in POLICIES:
            trace = json.loads(simulate(policy.policy_version, path)["stop_trace_json"])
            values = [float(item[1]) for item in trace]
            self.assertEqual(values[0], -1.0)
            self.assertTrue(all(v >= -1.0 for v in values))
            self.assertTrue(all(values[i] >= values[i-1] for i in range(1, len(values))))

    def test_completed_bar_rule_does_not_retroactively_stop_same_bar(self):
        path = [
            make_bar(1, open_price=100.0, high=102.2, low=99.5, close=101.5),
            make_bar(2, open_price=101.5, high=101.7, low=100.8, close=101.0),
        ]
        result = simulate("CONTINUOUS_R_GIVEBACK_V1", path)
        self.assertEqual(result["exit_bar"], 2)

    def test_gap_through_active_stop_uses_adverse_open_fill(self):
        result = simulate(CONTROL_POLICY_VERSION, [
            make_bar(1, open_price=98.0, high=99.0, low=97.0, close=98.5)
        ])
        self.assertEqual(result["exit_reason"], "STOP")
        self.assertEqual(result["exit_price"], 98.0)
        self.assertLess(result["gross_r"], -1.9)

    def test_stagnation_exits_at_60_minutes(self):
        path = [make_bar(i, open_price=100, high=100.3, low=99.7, close=100.05) for i in range(1, 20)]
        result = simulate("STAGNATION_TIME_EXIT_V1", path)
        self.assertEqual(result["exit_reason"], "STAGNATION_60M")
        self.assertEqual(result["exit_bar"], 12)
        self.assertEqual(result["holding_minutes"], 60)

    def test_funding_cost_is_directional(self):
        path = [make_bar(1, open_price=100, high=100.5, low=99.5, close=100.2)]
        funding = ({"funding_time_ms": INTERVAL, "funding_rate": 0.001, "mark_price": 100.0},)
        self.assertAlmostEqual(simulate("RUNNER_POLICY_V1", path, side="LONG", funding=funding)["funding_cost_frac"], 0.001)
        self.assertAlmostEqual(simulate("RUNNER_POLICY_V1", path, side="SHORT", funding=funding)["funding_cost_frac"], -0.001)

    def test_same_bar_stop_and_favorable_extension_is_marked_ambiguous(self):
        result = simulate(CONTROL_POLICY_VERSION, [
            make_bar(1, open_price=100, high=102.0, low=98.0, close=100.5)
        ])
        self.assertEqual(result["exit_reason"], "STOP")
        self.assertEqual(result["ambiguous_stop_bar"], 1)


class V344PolicyLabIntegrationTests(unittest.TestCase):
    def test_builds_every_policy_and_side_only_for_risk_eligible_paths_without_mutating_sources(self):
        with isolated_live_db() as db:
            lab = seed_policy_lab(db)
            raw_before = db.audit(now_ms=70*INTERVAL, record=False)["evidence_digest"]
            future_before = future_layer_digest(db)
            with db.connection() as conn:
                eligible = int(conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE outcome_version=? AND risk_unit_frac IS NOT NULL AND risk_unit_frac>0 AND funding_complete=1",
                    (OUTCOME_VERSION,),
                ).fetchone()[0])
                ineligible = int(conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE outcome_version=? AND (risk_unit_frac IS NULL OR risk_unit_frac<=0 OR funding_complete=0)",
                    (OUTCOME_VERSION,),
                ).fetchone()[0])
            self.assertGreater(eligible, 0)
            self.assertGreater(ineligible, 0)
            result = lab.build(max_events=0)
            self.assertEqual(result.risk_eligible_paths, eligible)
            self.assertEqual(result.risk_ineligible_paths, ineligible)
            self.assertEqual(result.result_rows, eligible * len(POLICIES) * 2)
            self.assertEqual(raw_before, db.audit(now_ms=70*INTERVAL, record=False)["evidence_digest"])
            self.assertEqual(future_before, future_layer_digest(db))
            audit = lab.audit()
            self.assertTrue(audit["healthy"], audit)
            report = lab.report()
            self.assertEqual(report["authority"], "RESEARCH_ONLY_NO_POLICY_PROMOTION_NO_EXECUTION")
            self.assertEqual(report["policies"][f"{CONTROL_POLICY_VERSION}:LONG"]["rows"], eligible)

    def test_rebuild_is_deterministic(self):
        with isolated_live_db() as db:
            lab = seed_policy_lab(db)
            first = lab.build(max_events=0)
            self.assertGreater(first.result_rows, 0)
            with db.connection() as conn:
                before = conn.execute(
                    "SELECT event_open_ms,source_digest,result_digest FROM exit_policy_builds ORDER BY event_open_ms"
                ).fetchall()
            second = lab.build(max_events=0, rebuild=True)
            self.assertGreater(second.result_rows, 0)
            with db.connection() as conn:
                after = conn.execute(
                    "SELECT event_open_ms,source_digest,result_digest FROM exit_policy_builds ORDER BY event_open_ms"
                ).fetchall()
            self.assertEqual(before, after)
            self.assertTrue(lab.audit()["healthy"])

    def test_source_path_mutation_is_detected(self):
        with isolated_live_db() as db:
            lab = seed_policy_lab(db)
            lab.build(max_events=0)
            with db.connection() as conn:
                conn.execute(
                    "UPDATE future_paths SET path_digest='tampered' WHERE event_open_ms=? AND symbol=?",
                    (TARGET_OPEN, SYMBOL),
                )
            audit = lab.audit()
            self.assertGreater(audit["source_path_mismatches"], 0)
            self.assertGreater(audit["build_source_digest_mismatches"], 0)
            self.assertFalse(audit["healthy"])

    def test_underlying_future_candle_mutation_is_detected(self):
        with isolated_live_db() as db:
            lab = seed_policy_lab(db)
            lab.build(max_events=0)
            with db.connection() as conn:
                conn.execute(
                    "UPDATE candles_5m SET high_price=high_price+0.25 WHERE symbol=? AND event_open_ms=?",
                    (SYMBOL, TARGET_OPEN + INTERVAL),
                )
            audit = lab.audit()
            self.assertGreater(audit["source_candle_digest_mismatches"], 0)
            self.assertFalse(audit["healthy"])

    def test_persisted_result_tamper_is_detected(self):
        with isolated_live_db() as db:
            lab = seed_policy_lab(db)
            lab.build(max_events=0)
            with db.connection() as conn:
                conn.execute(
                    "UPDATE exit_policy_results SET net_r=net_r+1 WHERE event_open_ms=? AND symbol=? AND side='LONG' AND policy_version=?",
                    (TARGET_OPEN, SYMBOL, CONTROL_POLICY_VERSION),
                )
            audit = lab.audit()
            self.assertGreater(audit["result_digest_mismatches"], 0)
            self.assertGreater(audit["build_result_digest_mismatches"], 0)
            self.assertFalse(audit["healthy"])

    def test_definition_tamper_is_detected_without_repair(self):
        with isolated_live_db() as db:
            lab = seed_policy_lab(db)
            lab.build(max_events=0)
            with db.connection() as conn:
                conn.execute(
                    "UPDATE exit_policy_sets SET definition_hash='tampered' WHERE policy_version=?",
                    (CONTROL_POLICY_VERSION,),
                )
            audit = lab.audit()
            self.assertGreater(audit["policy_definition_mismatches"], 0)
            self.assertFalse(audit["healthy"])
            with db.connection() as conn:
                stored = conn.execute(
                    "SELECT definition_hash FROM exit_policy_sets WHERE policy_version=?",
                    (CONTROL_POLICY_VERSION,),
                ).fetchone()[0]
            self.assertEqual(stored, "tampered")

    def test_result_digest_normalizes_signed_zero(self):
        row = {
            "event_open_ms": 0, "symbol": SYMBOL, "side": "SHORT",
            "feature_version": "CANONICAL_FEATURES_V3_V1",
            "outcome_version": OUTCOME_VERSION, "lab_version": LAB_VERSION,
            "policy_version": CONTROL_POLICY_VERSION, "built_at_ms": 1,
            "entry_price": 100.0, "initial_risk_frac": 0.01,
            "source_path_digest": "p", "source_candle_digest": "c",
            "exit_bar": 1, "exit_time_ms": INTERVAL, "exit_price": 100.0,
            "exit_reason": "HORIZON_4H", "gross_return_frac": -0.0, "gross_r": -0.0,
            "funding_cost_frac": -0.0, "roundtrip_base_cost_frac": 0.0,
            "net_return_frac": -0.0, "net_r": -0.0, "mfe_r": 0.0, "mae_r": 0.0,
            "capture_ratio": None, "peak_favorable_r": 0.0, "peak_giveback_r": 0.0,
            "time_to_mfe_min": 0, "holding_minutes": 5, "post_exit_mfe_r": 0.0,
            "missed_extension_r": 0.0, "stop_updates": 0,
            "stop_trace_json": '[[0,-1.0,"INITIAL_RISK"]]', "ambiguous_stop_bar": 0,
            "result_digest": "",
        }
        roundtrip = dict(row)
        for field in ("gross_return_frac", "gross_r", "funding_cost_frac", "net_return_frac", "net_r"):
            roundtrip[field] = 0.0
        self.assertEqual(_result_digest(row), _result_digest(roundtrip))


if __name__ == "__main__":
    unittest.main()
