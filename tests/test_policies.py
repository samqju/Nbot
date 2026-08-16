import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from nbot.binance import Candle, SourceCapture, UniverseRow
from nbot.config import CONFIG, OUTCOME_CONFIG, POLICY_CONFIG, RESEARCH_CONFIG
from nbot.db import EvidenceDB
from nbot.outcomes import FuturePathEngine
from nbot.policies import POLICIES, POLICY_BY_VERSION, ExitPolicyLab, _result_digest, simulate_policy
from nbot.research import ResearchEngine


class FakeHistoricalClient:
    def __init__(self, cfg, price_fn, latest_closed_index=69):
        self.cfg = cfg
        self.price_fn = price_fn
        self.latest_closed_index = latest_closed_index

    def server_time_ms(self):
        return (self.latest_closed_index + 1) * self.cfg.candle_interval_ms + 1_000

    def historical_candles(self, symbol, start_open_ms, end_open_ms):
        rows = {}
        interval = self.cfg.candle_interval_ms
        for open_ms in range(start_open_ms, end_open_ms + 1, interval):
            index = open_ms // interval
            close = self.price_fn(symbol, index)
            rows[open_ms] = Candle(
                symbol,
                open_ms,
                open_ms + interval - 1,
                close * 0.999,
                close * 1.003,
                close * 0.997,
                close,
                1000.0,
                1_000_000.0,
                100,
                500.0,
                500_000.0,
            )
        return rows


def make_bar(index, *, open_price, high, low, close):
    interval = 300_000
    open_ms = index * interval
    return Candle(
        "AAAUSDT",
        open_ms,
        open_ms + interval - 1,
        open_price,
        high,
        low,
        close,
        1000.0,
        1_000_000.0,
        100,
        500.0,
        500_000.0,
    )


class PolicySimulationTests(unittest.TestCase):
    def _simulate(self, policy_version, path, *, side="LONG", funding_events=()):
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
            event_open_ms=0,
            entry_price=entry,
            risk_frac=risk,
            path=path,
            funding_events=list(funding_events),
            roundtrip_base_cost_frac=0.001,
            full_mfe_frac=max(0.0, favorable),
            full_mae_frac=max(0.0, adverse),
            time_to_mfe_min=5,
            interval_minutes=5,
        )

    def test_catalog_has_one_control_and_seven_challengers(self):
        self.assertEqual(len(POLICIES), 8)
        controls = [policy for policy in POLICIES if policy.is_control]
        self.assertEqual([policy.policy_version for policy in controls], ["INTEGER_R_STEP_CONTROL"])

    def test_all_policy_traces_start_at_minus_one_r_and_never_loosen(self):
        path = [
            make_bar(i, open_price=100 + i * 0.2, high=101.2 + i * 0.3, low=99.5 + i * 0.2, close=100.5 + i * 0.25)
            for i in range(1, 20)
        ]
        import json
        for policy in POLICIES:
            result = self._simulate(policy.policy_version, path)
            trace = json.loads(result["stop_trace_json"])
            self.assertEqual(trace[0][1], -1.0)
            self.assertTrue(all(float(item[1]) >= -1.0 for item in trace))
            self.assertTrue(all(float(trace[i][1]) >= float(trace[i - 1][1]) for i in range(1, len(trace))))

    def test_integer_control_uses_completed_bar_staircase(self):
        path = [
            make_bar(1, open_price=100.0, high=101.2, low=99.6, close=101.0),
            make_bar(2, open_price=101.0, high=101.8, low=100.4, close=101.6),
            make_bar(3, open_price=101.6, high=102.2, low=100.8, close=101.5),
            make_bar(4, open_price=101.5, high=101.7, low=100.8, close=101.0),
        ]
        result = self._simulate("INTEGER_R_STEP_CONTROL", path)
        self.assertEqual(result["exit_reason"], "STOP")
        self.assertAlmostEqual(result["exit_price"], 101.0)
        self.assertGreater(result["gross_r"], 0.9)

    def test_no_retroactive_trailing_inside_same_bar(self):
        # Bar 1 reaches +2R and falls back below what a freshly-computed trail
        # would be. The new stop only becomes valid for bar 2, so bar 1 must not
        # be exited retroactively.
        path = [
            make_bar(1, open_price=100.0, high=102.2, low=99.5, close=101.5),
            make_bar(2, open_price=101.5, high=101.7, low=100.8, close=101.0),
        ]
        result = self._simulate("CONTINUOUS_R_GIVEBACK_V1", path)
        self.assertEqual(result["exit_bar"], 2)

    def test_stagnation_policy_releases_slot_at_60_minutes(self):
        path = [
            make_bar(i, open_price=100.0, high=100.3, low=99.7, close=100.05)
            for i in range(1, 20)
        ]
        result = self._simulate("STAGNATION_TIME_EXIT_V1", path)
        self.assertEqual(result["exit_bar"], 12)
        self.assertEqual(result["exit_reason"], "STAGNATION_60M")
        self.assertEqual(result["holding_minutes"], 60)

    def test_stop_gap_uses_adverse_open_fill(self):
        path = [make_bar(1, open_price=98.0, high=99.0, low=97.0, close=98.5)]
        result = self._simulate("INTEGER_R_STEP_CONTROL", path)
        self.assertEqual(result["exit_reason"], "STOP")
        self.assertEqual(result["exit_price"], 98.0)
        self.assertLess(result["gross_r"], -1.9)

    def test_funding_cost_sign_is_directional(self):
        path = [make_bar(1, open_price=100.0, high=100.5, low=99.5, close=100.2)]
        funding = [{"funding_time_ms": 300_000, "funding_rate": 0.001, "mark_price": 100.0}]
        long_result = self._simulate("RUNNER_POLICY_V1", path, side="LONG", funding_events=funding)
        short_result = self._simulate("RUNNER_POLICY_V1", path, side="SHORT", funding_events=funding)
        self.assertAlmostEqual(long_result["funding_cost_frac"], 0.001)
        self.assertAlmostEqual(short_result["funding_cost_frac"], -0.001)

    def test_result_digest_normalizes_signed_zero_for_sqlite_roundtrip(self):
        row = {
            "event_open_ms": 0,
            "symbol": "AAAUSDT",
            "side": "SHORT",
            "feature_version": "CANONICAL_FEATURES_V1",
            "outcome_version": "FUTURE_PATH_4H_V1",
            "lab_version": "EXIT_POLICY_LAB_V1",
            "policy_version": "INTEGER_R_STEP_CONTROL",
            "built_at_ms": 1,
            "entry_price": 100.0,
            "initial_risk_frac": 0.01,
            "source_path_digest": "p",
            "source_candle_digest": "c",
            "exit_bar": 1,
            "exit_time_ms": 300000,
            "exit_price": 100.0,
            "exit_reason": "HORIZON_4H",
            "gross_return_frac": -0.0,
            "gross_r": -0.0,
            "funding_cost_frac": -0.0,
            "roundtrip_base_cost_frac": 0.0,
            "net_return_frac": -0.0,
            "net_r": -0.0,
            "mfe_r": 0.0,
            "mae_r": 0.0,
            "capture_ratio": None,
            "peak_favorable_r": 0.0,
            "peak_giveback_r": 0.0,
            "time_to_mfe_min": 0,
            "holding_minutes": 5,
            "post_exit_mfe_r": 0.0,
            "missed_extension_r": 0.0,
            "stop_updates": 0,
            "stop_trace_json": "[[0,-1.0,\"INITIAL_1R\"]]",
            "ambiguous_stop_bar": 0,
            "result_digest": "",
        }
        sqlite_roundtrip = dict(row)
        for field in (
            "gross_return_frac", "gross_r", "funding_cost_frac", "net_return_frac", "net_r"
        ):
            sqlite_roundtrip[field] = 0.0
        self.assertEqual(_result_digest(row), _result_digest(sqlite_roundtrip))


class PolicyLabIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = replace(CONFIG, database_path=Path(self.tmp.name) / "observer.db", observation_universe_size=3)
        self.db = EvidenceDB(self.cfg)
        self.db.initialize()
        self._seed(70)
        ResearchEngine(self.cfg, RESEARCH_CONFIG, self.db).build(max_events=0)
        self.db.store_funding_sync(
            start_ms=0,
            end_ms=100 * self.cfg.candle_interval_ms,
            events=[],
            captured_at_ms=100 * self.cfg.candle_interval_ms + 1,
        )
        FuturePathEngine(
            self.cfg,
            OUTCOME_CONFIG,
            self.db,
            FakeHistoricalClient(self.cfg, self._price, latest_closed_index=69),
        ).build(max_events=0)
        self.lab = ExitPolicyLab(self.cfg, POLICY_CONFIG, self.db)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def _price(symbol: str, index: int) -> float:
        if symbol == "BTCUSDT":
            return 100.0 + index * 0.20
        if symbol == "AAAUSDT":
            return 50.0 + index * 0.30
        return 80.0 - index * 0.08

    def _seed(self, count):
        interval = self.cfg.candle_interval_ms
        for index in range(count):
            open_ms = index * interval
            close_ms = open_ms + interval - 1
            symbols = ("BTCUSDT", "AAAUSDT", "BBBUSDT")
            rows = []
            candles = {}
            for rank, symbol in enumerate(symbols, 1):
                close = self._price(symbol, index)
                rows.append(UniverseRow(
                    symbol,
                    rank,
                    1_000_000_000.0 / rank,
                    close * 0.9999,
                    close * 1.0001,
                    0.02 * rank,
                    close,
                    close,
                    0.0001 * rank,
                    close_ms + 8 * 60 * 60 * 1000,
                ))
                candles[symbol] = Candle(
                    symbol,
                    open_ms,
                    close_ms,
                    close * 0.999,
                    close * 1.003,
                    close * 0.997,
                    close,
                    1000.0,
                    1_000_000.0,
                    100,
                    500.0,
                    500_000.0,
                )
            status = self.db.store_event(
                event_open_ms=open_ms,
                event_close_ms=close_ms,
                captured_at_ms=close_ms + 5_000,
                capture_started_at_ms=close_ms + 1_000,
                server_time_before_ms=close_ms + 1_000,
                server_time_after_ms=close_ms + 5_000,
                source_captures=(SourceCapture("point_in_time_context", close_ms + 1_000, close_ms + 2_000),),
                requested_symbols=3,
                universe_rows=rows,
                candles=candles,
                error_count=0,
                capture_duration_ms=4_000,
            )
            self.assertEqual(status, "COMPLETE")

    def test_builds_both_sides_for_every_policy_only_when_risk_unit_exists(self):
        with self.db.connection() as conn:
            eligible = conn.execute(
                "SELECT COUNT(*) FROM future_paths WHERE risk_unit_frac IS NOT NULL AND risk_unit_frac>0"
            ).fetchone()[0]
            ineligible = conn.execute(
                "SELECT COUNT(*) FROM future_paths WHERE risk_unit_frac IS NULL"
            ).fetchone()[0]
        self.assertGreater(eligible, 0)
        self.assertGreater(ineligible, 0)
        result = self.lab.build(max_events=0)
        self.assertEqual(result.risk_eligible_paths, eligible)
        self.assertEqual(result.risk_ineligible_paths, ineligible)
        self.assertEqual(result.result_rows, eligible * len(POLICIES) * 2)
        audit = self.lab.audit()
        self.assertTrue(all(value == 0 for key, value in audit.items() if key not in {"lab_version", "policy_count", "result_rows"}))

    def test_rebuild_is_deterministic_and_digests_stay_clean(self):
        first = self.lab.build(max_events=0)
        self.assertGreater(first.result_rows, 0)
        with self.db.connection() as conn:
            before = conn.execute(
                "SELECT event_open_ms, result_digest FROM exit_policy_builds ORDER BY event_open_ms"
            ).fetchall()
        second = self.lab.build(max_events=0, rebuild=True)
        self.assertGreater(second.result_rows, 0)
        with self.db.connection() as conn:
            after = conn.execute(
                "SELECT event_open_ms, result_digest FROM exit_policy_builds ORDER BY event_open_ms"
            ).fetchall()
        self.assertEqual(before, after)
        self.assertEqual(self.lab.audit()["result_digest_mismatches"], 0)

    def test_report_is_research_only_and_contains_control(self):
        self.lab.build(max_events=0)
        report = self.lab.report()
        self.assertEqual(report["authority"], "RESEARCH_ONLY_NO_POLICY_PROMOTION")
        self.assertIn("INTEGER_R_STEP_CONTROL:LONG", report["policies"])
        self.assertGreater(report["policies"]["INTEGER_R_STEP_CONTROL:LONG"]["rows"], 0)

    def test_source_path_mutation_is_detected(self):
        self.lab.build(max_events=1)
        with self.db.connection() as conn:
            target = conn.execute(
                "SELECT event_open_ms, symbol FROM exit_policy_results LIMIT 1"
            ).fetchone()
            conn.execute(
                "UPDATE future_paths SET path_digest='tampered' WHERE event_open_ms=? AND symbol=?",
                target,
            )
        audit = self.lab.audit()
        self.assertGreater(audit["source_path_mismatches"], 0)
        self.assertGreater(audit["build_source_digest_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
