"""Synthetic-only safety tests for the isolated V5 first checkpoint."""
import sqlite3
import unittest
from dataclasses import replace
from nbot.v5.observation_contract import (
    Evidence, INTERVAL_MS, PATTERN_IDS, append_candidate_records,
    build_candidate_records, initialize_candidate_ledger,
)

EVENT = INTERVAL_MS * 1_000_000
DECISION = EVENT + INTERVAL_MS + 2_000


def sample(patterns=None):
    default = {p: "NO_MATCH" for p in PATTERN_IDS}
    if patterns:
        default.update(patterns)
    return Evidence(
        last_closed_bar_open_ms=EVENT,
        source_max_bar_open_ms=EVENT,
        observed_at_ms=DECISION,
        patterns_by_side={"LONG": default, "SHORT": default},
    )


def records(symbols=("BTCUSDT", "ETHUSDT"), btc=None, observations=None):
    return build_candidate_records(
        event_open_ms=EVENT,
        decision_at_ms=DECISION,
        eligible_symbols=symbols,
        btc_context=sample() if btc is None else btc,
        observations={s: sample() for s in symbols} if observations is None else observations,
    )


class V5ObservationContractTests(unittest.TestCase):
    def test_50_coins_create_100_directional_observations(self):
        universe = tuple(f"COIN{i:02d}USDT" for i in range(50))
        rows = records(universe)
        self.assertEqual(len(rows), 100)
        self.assertEqual(len(set(r["decision_id"] for r in rows)), 100)
        self.assertEqual({r["side"] for r in rows}, {"LONG", "SHORT"})
        self.assertTrue(all(r["status"] == "OBSERVED" for r in rows))
        self.assertTrue(all(r["order_authority"] == "NONE" for r in rows))

    def test_missing_symbol_is_recorded_not_dropped(self):
        rows = records(observations={"BTCUSDT": sample()})
        missing = [r for r in rows if r["symbol"] == "ETHUSDT"]
        self.assertEqual(len(missing), 2)
        self.assertTrue(all(r["status"] == "UNSCORABLE" for r in missing))
        self.assertIn("SYMBOL_MISSING", missing[0]["reason_codes"])

    def test_stale_btc_blocks_both_sides_for_every_coin(self):
        rows = records(btc=replace(sample(), last_closed_bar_open_ms=EVENT - INTERVAL_MS))
        self.assertTrue(all(not r["btc_context_valid"] for r in rows))
        self.assertTrue(all(r["status"] == "UNSCORABLE" for r in rows))

    def test_missing_pattern_does_not_become_false_or_trade(self):
        rows = records(observations={"BTCUSDT": sample({"EMA_CROSS_V1": "MATCH"}),
                                     "ETHUSDT": replace(sample(), patterns_by_side={})})
        match = next(r for r in rows if r["symbol"] == "BTCUSDT" and r["side"] == "LONG")
        self.assertEqual(match["patterns"]["EMA_CROSS_V1"], "MATCH")
        self.assertEqual(len(match["patterns"]), 24)
        eth = next(r for r in rows if r["symbol"] == "ETHUSDT")
        self.assertEqual(eth["patterns"]["EMA_CROSS_V1"], "UNAVAILABLE")
        self.assertEqual(eth["action"], "OBSERVE_ONLY")
        self.assertEqual(eth["status"], "UNSCORABLE")

    def test_future_source_and_premature_observation_block(self):
        for bad in (
            replace(sample(), source_max_bar_open_ms=EVENT + INTERVAL_MS),
            replace(sample(), observed_at_ms=EVENT),
            replace(sample(), observed_at_ms=DECISION + 1),
        ):
            rows = records(observations={"BTCUSDT": bad, "ETHUSDT": sample()})
            self.assertEqual(rows[0]["status"], "UNSCORABLE")

    def test_invalid_or_duplicate_universe_rejected(self):
        for universe in (("BTCUSDT", "BTCUSDT"), ("bad-coin",), ()):
            with self.assertRaises(ValueError):
                records(universe)
        with self.assertRaises(ValueError):
            records(("BTCUSDT",), observations={"BTCUSDT": sample(), "XRPUSDT": sample()})

    def test_determinism_and_append_only_idempotency(self):
        first = records(("ETHUSDT", "BTCUSDT"))
        self.assertEqual(first, records(("BTCUSDT", "ETHUSDT")))
        with sqlite3.connect(":memory:") as con:
            initialize_candidate_ledger(con)
            self.assertEqual(append_candidate_records(con, first), 4)
            self.assertEqual(append_candidate_records(con, first), 0)
            modified = [dict(r) for r in first]
            modified[1]["status"] = "UNSCORABLE"
            with self.assertRaisesRegex(ValueError, "CHANGED_DECISION"):
                append_candidate_records(con, modified)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM v5_candidate_observations").fetchone()[0], 4)
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("DELETE FROM v5_candidate_observations")

    def test_failed_batch_is_atomic(self):
        original = records()
        altered = [dict(r) for r in original]
        altered[-1]["reason_codes"] = ["TAMPERED"]
        with sqlite3.connect(":memory:") as con:
            initialize_candidate_ledger(con)
            self.assertEqual(append_candidate_records(con, original[-1:]), 1)
            with self.assertRaises(ValueError):
                append_candidate_records(con, altered)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM v5_candidate_observations").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
