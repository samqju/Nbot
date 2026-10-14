"""Offline-only source witness: frozen universe ranking, quote as-of, fail closed."""
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g2_source_witness import SourceWitness, WitnessHold
from nbot.v5.observation_contract import INTERVAL_MS


class G2SourceWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=sqlite3.connect(Path(self.temp.name)/"source.sqlite")
        self.addCleanup(self.db.close)
        self.w=SourceWitness(self.db)
        self.event=INTERVAL_MS*1000
        self.now=self.event+INTERVAL_MS+1000
        self.exchange={"symbols":[
            {"symbol":"BTCUSDT","contractType":"PERPETUAL","status":"TRADING",
             "quoteAsset":"USDT","marginAsset":"USDT"},
            {"symbol":"ETHUSDT","contractType":"PERPETUAL","status":"TRADING",
             "quoteAsset":"USDT","marginAsset":"USDT"},
            {"symbol":"OLDUSDT","contractType":"PERPETUAL","status":"BREAK",
             "quoteAsset":"USDT","marginAsset":"USDT"},
        ]}
        self.ticker=[
            {"symbol":"BTCUSDT","quoteVolume":"100000000"},
            {"symbol":"ETHUSDT","quoteVolume":"50000000"},
            {"symbol":"OLDUSDT","quoteVolume":"200000000"},
        ]
        self.selected=("BTCUSDT","ETHUSDT")

    def cohort(self, **kw):
        opts=dict(exchange=self.exchange,ticker=self.ticker,
                  selected=self.selected,received_ms=self.event+1000,
                  first_event_open_ms=self.event,
                  exchange_server_ms=self.event+950)
        opts.update(kw)
        return self.w.witness_cohort(**opts)

    def quotes(self):
        return {
            s:dict(bid=100.0,ask=100.05,
                   quote_received_ms=self.now-100,
                   trade_received_ms=self.now-200,
                   market_connected=True,public_connected=True,
                   market_epoch=1,public_epoch=1)
            for s in self.selected
        }

    def test_frozen_snapshot_reproducible_and_repeated_idempotent(self):
        cohort=self.cohort()
        self.assertEqual(self.cohort(),cohort)
        row=self.db.execute("SELECT payload_json FROM g2_cohort_witness").fetchone()
        data=json.loads(row[0])
        self.assertIn("OLDUSDT",[x["symbol"] for x in data["exchange"]["symbols"]])
        self.assertEqual(data["ranked_selected"],["BTCUSDT","ETHUSDT"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM g2_cohort_witness").fetchone()[0],1)

    def test_ranking_swap_rejected(self):
        with self.assertRaisesRegex(WitnessHold,"NOT_REPRODUCIBLE"):
            self.cohort(selected=("ETHUSDT","BTCUSDT"))

    def test_future_source_clock_refused(self):
        with self.assertRaisesRegex(WitnessHold,"CLOCK"):
            self.cohort(received_ms=self.event-100,
                        exchange_server_ms=self.event+1000)

    def test_cohort_changed_source_proof_rejected(self):
        self.cohort()
        changed=list(self.ticker)
        changed[-1]={"symbol":"OLDUSDT","quoteVolume":"7000"}
        with self.assertRaisesRegex(WitnessHold,"REPLAY_CONFLICT"):
            self.cohort(ticker=changed)

    def test_complete_two_coin_source_witness_and_idempotence(self):
        cohort=self.cohort()
        source=self.quotes()
        report=self.w.witness_event_quotes(
            cohort_digest=cohort,event_open_ms=self.event,
            asof_ms=self.now,sources=source)
        self.assertEqual(report["recorded"],2)
        self.assertEqual(report["qualified_local_sources"],2)
        self.assertFalse(report["research_ready"])
        self.assertEqual(report["order_authority"],"NONE")
        self.w.witness_event_quotes(
            cohort_digest=cohort,event_open_ms=self.event,
            asof_ms=self.now,sources=source)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM g2_quote_witness").fetchone()[0],2)

    def test_missing_symbol_quote_denominator_forbidden(self):
        cohort=self.cohort()
        sources=self.quotes()
        sources.pop("ETHUSDT")
        with self.assertRaisesRegex(WitnessHold,"DENOMINATOR"):
            self.w.witness_event_quotes(
                cohort_digest=cohort,event_open_ms=self.event,
                asof_ms=self.now,sources=sources)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM g2_quote_witness").fetchone()[0],0)

    def test_stale_quote_is_persisted_as_held_not_verified(self):
        cohort=self.cohort()
        src=self.quotes()
        src["ETHUSDT"]["trade_received_ms"]=self.now-20_000
        report=self.w.witness_event_quotes(
            cohort_digest=cohort,event_open_ms=self.event,asof_ms=self.now,sources=src)
        self.assertEqual(report["source_held"],1)
        held=self.db.execute("SELECT payload_json FROM g2_quote_witness WHERE symbol='ETHUSDT'").fetchone()[0]
        self.assertIn("TRADE_STALE_OR_MISSING",held)
        self.assertIn("UNVERIFIED",held)

    def test_future_quote_time_never_qualifies(self):
        cohort=self.cohort()
        src=self.quotes()
        src["ETHUSDT"]["quote_received_ms"]=self.now+1
        report=self.w.witness_event_quotes(
            cohort_digest=cohort,event_open_ms=self.event,asof_ms=self.now,sources=src)
        self.assertEqual(report["qualified_local_sources"],1)

    def test_mutated_payload_replay_fails_without_partial_writes(self):
        cohort=self.cohort()
        src=self.quotes()
        self.w.witness_event_quotes(
            cohort_digest=cohort,event_open_ms=self.event,asof_ms=self.now,sources=src)
        src["ETHUSDT"]["bid"]=99.0
        with self.assertRaisesRegex(WitnessHold,"REPLAY_CONFLICT"):
            self.w.witness_event_quotes(
                cohort_digest=cohort,event_open_ms=self.event,asof_ms=self.now,sources=src)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM g2_quote_witness").fetchone()[0],2)

    def test_sqlite_immutable_triggers(self):
        cohort=self.cohort()
        with self.assertRaisesRegex(sqlite3.DatabaseError,"IMMUTABLE"):
            self.db.execute("UPDATE g2_cohort_witness SET payload_sha='fake'")
        self.db.rollback()
        self.w.witness_event_quotes(
            cohort_digest=cohort,event_open_ms=self.event,
            asof_ms=self.now,sources=self.quotes())
        with self.assertRaisesRegex(sqlite3.DatabaseError,"IMMUTABLE"):
            self.db.execute("DELETE FROM g2_quote_witness")
        self.db.rollback()


if __name__=="__main__":
    unittest.main()
