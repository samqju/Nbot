"""Offline closed-candle tests; no network, VPS, Binance or paper execution."""
from copy import deepcopy
import sqlite3
import unittest

from nbot.observation import candidate_setups as old_rules
from nbot.v5.observation_contract import (
    INTERVAL_MS, PATTERN_IDS, append_candidate_records,
    initialize_candidate_ledger,
)
from nbot.v5.pattern_adapter import (
    DETECTOR_VERSION, build_observations_from_closed_candles,
)

EVENT = INTERVAL_MS * 1_000_000
DECISION = EVENT + INTERVAL_MS + 5_000
SYMBOLS = tuple(f"COIN{i:02d}USDT" for i in range(12))


def bars(*, trend=0., jump=0., last_volume=10.):
    closes = [100. + i * trend for i in range(60)]
    closes[-1] += jump
    return [
        (EVENT - (59 - i) * INTERVAL_MS, x, x + .5, x - .5, x,
         last_volume if i == 59 else 10.)
        for i, x in enumerate(closes)
    ]


def sources(symbols=SYMBOLS):
    return {"BTCUSDT": bars(), **{s: bars() for s in symbols}}


def evaluate(*, symbols=SYMBOLS, candles=None, observed=DECISION):
    return build_observations_from_closed_candles(
        event_open_ms=EVENT,
        decision_at_ms=DECISION,
        observed_at_ms=observed,
        eligible_symbols=symbols,
        candles_by_symbol=sources(symbols) if candles is None else candles,
    )


def row(rows, symbol=SYMBOLS[0], side="LONG"):
    return next(r for r in rows if r["symbol"] == symbol and r["side"] == side)


class V5PatternAdapterTests(unittest.TestCase):
    def test_exact_24_original_rules_are_present(self):
        self.assertEqual(len(PATTERN_IDS), 24)
        self.assertEqual(PATTERN_IDS, tuple(x.id for x in old_rules.REGISTRY))
        result = row(evaluate())
        self.assertEqual(set(result["patterns"]), set(PATTERN_IDS))
        self.assertTrue(all(s == "NO_MATCH" for s in result["patterns"].values()))
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["detector_version"], DETECTOR_VERSION)
        self.assertEqual(len(result["source_digest"]), 64)
        self.assertEqual(len(result["btc_source_digest"]), 64)

    def test_50_symbols_have_100_closed_candle_observations(self):
        symbols = tuple(f"COIN{i:02d}USDT" for i in range(50))
        result = evaluate(symbols=symbols)
        self.assertEqual(len(result), 100)
        self.assertTrue(all(r["status"] == "OBSERVED" for r in result))
        self.assertEqual(len({r["decision_id"] for r in result}), 100)

    def test_real_rule_outputs_include_overlapping_breakout_and_volume(self):
        data = sources()
        data[SYMBOLS[0]] = bars(jump=5., last_volume=30.)
        result = row(evaluate(candles=data))
        self.assertEqual(result["patterns"]["DONCHIAN_BREAKOUT_V1"], "MATCH")
        self.assertEqual(result["patterns"]["VOLUME_BREAKOUT_V1"], "MATCH")
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(result["order_authority"], "NONE")
        self.assertEqual(result["action"], "OBSERVE_ONLY")

    def test_legacy_trend_proxy_is_derived_from_candles_not_faked(self):
        data = sources()
        data[SYMBOLS[0]] = bars(trend=.2)
        result = row(evaluate(candles=data))
        self.assertEqual(result["patterns"]["TREND_CONTINUATION_V1"], "MATCH")
        self.assertEqual(result["status"], "OBSERVED")

    def test_btc_relative_momentum_uses_actual_btc_candle_returns(self):
        data = sources()
        data[SYMBOLS[0]] = bars(jump=5.)
        strong = row(evaluate(candles=data))
        self.assertEqual(strong["patterns"]["BTC_RELATIVE_MOMENTUM_V1"], "MATCH")
        data["BTCUSDT"] = bars(jump=8.)
        weakened = row(evaluate(candles=data))
        self.assertEqual(weakened["patterns"]["BTC_RELATIVE_MOMENTUM_V1"], "NO_MATCH")

    def test_btc_can_be_context_only_outside_eligible_universe(self):
        result = evaluate()
        self.assertNotIn("BTCUSDT", {r["symbol"] for r in result})
        self.assertTrue(all(r["btc_context_valid"] for r in result))

    def test_missing_or_stale_btc_is_unknown_not_zero(self):
        missing = sources()
        del missing["BTCUSDT"]
        stale = sources()
        stale["BTCUSDT"] = stale["BTCUSDT"][:-1]
        for data in (missing, stale):
            result = evaluate(candles=data)
            self.assertTrue(all(r["status"] == "UNSCORABLE" for r in result))
            self.assertTrue(all(not r["btc_context_valid"] for r in result))
            self.assertEqual(row(result)["patterns"]["BTC_RELATIVE_MOMENTUM_V1"],
                             "UNAVAILABLE")

    def test_missing_symbol_does_not_disappear_from_universe(self):
        data = sources()
        del data[SYMBOLS[0]]
        result = evaluate(candles=data)
        self.assertEqual(len(result), 24)
        self.assertEqual(row(result)["status"], "UNSCORABLE")
        self.assertIn("SYMBOL_MISSING", row(result)["reason_codes"])
        self.assertEqual(row(result, SYMBOLS[1])["status"], "OBSERVED")

    def test_gapped_future_or_malformed_candle_is_unscorable(self):
        original = sources()
        invalid_cases = [
            original[SYMBOLS[0]][:20] + original[SYMBOLS[0]][21:],
            original[SYMBOLS[0]][:48],
            original[SYMBOLS[0]] + [
                (EVENT + INTERVAL_MS, 100., 101., 99., 100., 10.)
            ],
            original[SYMBOLS[0]][:-1] + [
                (EVENT, 100., 99., 101., 100., 10.)
            ],
        ]
        for invalid in invalid_cases:
            data = sources()
            data[SYMBOLS[0]] = invalid
            with self.subTest(issue=str(invalid[-1][0])):
                result = row(evaluate(candles=data))
                self.assertEqual(result["status"], "UNSCORABLE")
                self.assertTrue(any("SYMBOL_" in reason
                                    for reason in result["reason_codes"]))
                self.assertEqual(result["patterns"]["EMA_CROSS_V1"], "UNAVAILABLE")

    def test_future_observation_timestamp_abstains(self):
        data = sources()
        data[SYMBOLS[0]] = bars(jump=5., last_volume=30.)
        result = evaluate(candles=data, observed=DECISION + 1)
        self.assertTrue(all(r["status"] == "UNSCORABLE" for r in result))
        self.assertTrue(all(not r["btc_context_valid"] for r in result))
        self.assertEqual(row(result)["patterns"]["DONCHIAN_BREAKOUT_V1"], "UNAVAILABLE")

    def test_malformed_candle_row_fails_closed_without_crashing(self):
        data = sources()
        data[SYMBOLS[0]][-1] = "BROKEN_ROW"
        observed = row(evaluate(candles=data))
        self.assertEqual(observed["status"], "UNSCORABLE")
        self.assertIn("SYMBOL_CANDLE_SHAPE_INVALID", observed["reason_codes"])

    def test_too_few_simultaneous_markets_abstains(self):
        short_universe = SYM = tuple(f"COIN{i:02d}USDT" for i in range(9))
        result = evaluate(symbols=short_universe)
        self.assertEqual(len(result), 18)
        self.assertTrue(all(r["status"] == "UNSCORABLE" for r in result))
        self.assertIn("SYMBOL_CROSS_SECTION_INCOMPLETE",
                      result[0]["reason_codes"])

    def test_replay_is_deterministic_and_source_changes_are_rejected(self):
        data = sources()
        first = evaluate(candles=data)
        reordered = evaluate(
            symbols=tuple(reversed(SYMBOLS)),
            candles={k: data[k] for k in reversed(tuple(data))}
        )
        self.assertEqual(first, reordered)
        with sqlite3.connect(":memory:") as con:
            initialize_candidate_ledger(con)
            self.assertEqual(append_candidate_records(con, first), 24)
            self.assertEqual(append_candidate_records(con, reordered), 0)
            changed = deepcopy(data)
            changed[SYMBOLS[0]][0] = (
                changed[SYMBOLS[0]][0][0], 100., 101., 99., 100., 11.
            )
            new_records = evaluate(candles=changed)
            self.assertEqual(row(first)["decision_id"], row(new_records)["decision_id"])
            self.assertNotEqual(row(first)["source_digest"], row(new_records)["source_digest"])
            with self.assertRaisesRegex(ValueError, "V5_CHANGED_DECISION_REJECTED"):
                append_candidate_records(con, new_records)
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM v5_candidate_observations")
                .fetchone()[0], 24
            )

    def test_extraneous_candle_inputs_are_rejected(self):
        data = sources()
        data["SECRETCOIN"] = bars()
        with self.assertRaisesRegex(ValueError, "V5_UNEXPECTED_CANDLE_SOURCE"):
            evaluate(candles=data)


if __name__ == "__main__":
    unittest.main()
