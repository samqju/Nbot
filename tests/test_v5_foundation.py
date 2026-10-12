"""V5 clean-slate contract tests: no collector/execution involvement."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.observation.v5_accounting import (
    VERSION, ORDER_AUTHORITY, CostPolicy, FundingSettlement,
    score_trade, submit_order,
)
from nbot.observation.v5_foundation import V5EvidenceStore


def score(**overrides):
    args = dict(
        symbol="BTCUSDT", side="LONG", quantity=10, entry_fill_price=100,
        exit_fill_price=100, initial_stop_price=99,
        entry_time_ms=1000, exit_time_ms=3000,
        funding_events=(), funding_coverage_confirmed=True,
    )
    args.update(overrides)
    return score_trade(**args)


class V5AccountingTests(unittest.TestCase):
    def test_fee_slippage_and_r_are_different_units(self):
        x = score()
        self.assertEqual(ORDER_AUTHORITY,"NONE")
        self.assertEqual(x.policy_version, VERSION)
        self.assertAlmostEqual(x.one_r_quote, 10.0)
        self.assertAlmostEqual(x.fees_quote, 1.0)  # 0.05% on each $1,000 notional
        self.assertAlmostEqual(x.slippage_quote, .2)  # 1 bp each side
        self.assertAlmostEqual(x.net_r, -.12)
        y = score(initial_stop_price=99.9)
        self.assertAlmostEqual(y.fees_quote, 1.0)
        self.assertAlmostEqual(y.net_r, -1.2)

    def test_directional_gross_and_realized_exit_fee(self):
        x = score(side="SHORT", initial_stop_price=101, exit_fill_price=98)
        self.assertAlmostEqual(x.gross_quote,20.0)
        self.assertAlmostEqual(x.fees_quote,.99)
        self.assertAlmostEqual(x.slippage_quote,.198)
        self.assertAlmostEqual(x.net_quote,18.812)

    def test_funding_is_signed_and_only_on_proven_settlements(self):
        settlements = (FundingSettlement(symbol="BTCUSDT",time_ms=2000, rate=.001, mark_price=100),)
        self.assertAlmostEqual(score(funding_events=settlements).funding_quote, -1)
        self.assertAlmostEqual(score(side="SHORT",initial_stop_price=101,
                                      funding_events=settlements).funding_quote, +1)
        self.assertAlmostEqual(score(funding_events=(FundingSettlement("BTCUSDT",2000,-.001,100),)).funding_quote, +1)
        self.assertEqual(score(funding_events=()).funding_events_used, 0)
        with self.assertRaisesRegex(ValueError,"SYMBOL_MISMATCH"):
            score(funding_events=(FundingSettlement("ETHUSDT",2000,.001,100),))

    def test_missing_funding_coverage_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"COVERAGE"):
            score(funding_coverage_confirmed=False)
        with self.assertRaisesRegex(ValueError,"BOUNDARY"):
            score(funding_events=(FundingSettlement("BTCUSDT",1000,.001,100),))
        with self.assertRaisesRegex(ValueError,"ORDERED"):
            score(funding_events=(FundingSettlement("BTCUSDT",2200,.001,100),
                                  FundingSettlement("BTCUSDT",2100,.001,100)))
        with self.assertRaisesRegex(ValueError,"NUMBER"):
            FundingSettlement("BTCUSDT",2000,float("nan"),100)

    def test_initial_stop_and_chronology_are_validated(self):
        with self.assertRaisesRegex(ValueError,"STOP"):
            score(initial_stop_price=100)
        with self.assertRaisesRegex(ValueError,"STOP"):
            score(side="SHORT",initial_stop_price=99)
        with self.assertRaisesRegex(ValueError,"CHRONOLOGY"):
            score(exit_time_ms=1000)
        with self.assertRaisesRegex(ValueError,"COST_RATE"):
            CostPolicy(entry_fee_rate=-.01)
        with self.assertRaisesRegex(RuntimeError,"NO_ORDER_AUTHORITY"):
            submit_order()


class V5FoundationTests(unittest.TestCase):
    @staticmethod
    def decision(store, **changes):
        args = dict(
            decision_id="first", event_open_ms=300_000, symbol="BTCUSDT",
            side="LONG", setup_id="BREAKOUT_V5", qualified=True,
            reason="CONFIRMED_BREAKOUT", feature_digest="feature-sha",
            selection_policy_id="SELECTOR_V5_V1",
        )
        args.update(changes)
        store.record_decision(**args)

    def test_fresh_v5_ledger_immutable_multiple_exit_outcomes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"v5"/"evidence.db"
            store = V5EvidenceStore(path)
            self.assertFalse(path.exists())  # no import/constructor writes
            self.assertEqual(store.status()["decisions"],0)
            store.initialize()
            self.decision(store)
            self.decision(store)  # exact retry is idempotent
            result = score()
            store.record_outcome(decision_id="first",exit_policy_id="FIXED_2R_V1",
                evidence_digest="ticks-1",result=result)
            store.record_outcome(decision_id="first",exit_policy_id="TRAILING_V1",
                evidence_digest="ticks-1",result=None,unscorable_reason="WSS_GAP")
            store.record_outcome(decision_id="first",exit_policy_id="FIXED_2R_V1",
                evidence_digest="ticks-1",result=result)
            self.assertEqual(store.status()["decisions"],1)
            self.assertEqual(store.status()["scored"],1)
            self.assertEqual(store.status()["unscorable"],1)
            with self.assertRaisesRegex(ValueError,"IMMUTABLE_ID_REUSED"):
                self.decision(store,reason="DIFFERENT")
            with self.assertRaisesRegex(ValueError,"IMMUTABLE_ID_REUSED"):
                store.record_outcome(decision_id="first",exit_policy_id="TRAILING_V1",
                    evidence_digest="different",result=None,unscorable_reason="WSS_GAP")
            with sqlite3.connect(path) as db:
                with self.assertRaisesRegex(sqlite3.DatabaseError,"IMMUTABLE_V5_DECISION"):
                    db.execute("DELETE FROM v5_decisions")
                with self.assertRaisesRegex(sqlite3.DatabaseError,"IMMUTABLE_V5_OUTCOME"):
                    db.execute("UPDATE v5_outcomes SET status='SCORED'")
            with self.assertRaisesRegex(RuntimeError,"NO_ORDER_AUTHORITY"):
                store.submit_order()

    def test_missing_decision_unscorable_requires_reason(self):
        with tempfile.TemporaryDirectory() as td:
            store = V5EvidenceStore(Path(td)/"v5"/"evidence.db")
            store.initialize()
            with self.assertRaisesRegex(ValueError,"UNSCORABLE_REASON"):
                store.record_outcome(decision_id="no",exit_policy_id="A",
                    evidence_digest="sha",result=None)
            with self.assertRaises(sqlite3.IntegrityError):
                store.record_outcome(decision_id="no",exit_policy_id="A",
                    evidence_digest="sha",result=score())

    def test_paths_outside_v5_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,"V5_DIRECTORY"):
                V5EvidenceStore(Path(td)/"v4"/"research_ledger.db")
            with self.assertRaisesRegex(ValueError,"V5_DIRECTORY"):
                V5EvidenceStore(Path(td)/"v5"/".."/"v4"/"research_ledger.db")


if __name__ == "__main__":
    unittest.main()
