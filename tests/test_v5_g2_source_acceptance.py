"""G2 provenance: actual as-of integration, immutable verification and safety."""
import asyncio
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g2_source_witness import SourceWitness
from nbot.v5.g2_source_acceptance import source_acceptance, AcceptanceHold
from nbot.v5.g1f_engine import audit_event
from nbot.v5.observation_contract import INTERVAL_MS
from tests.test_v5_g2_population_audit import G2PopulationAuditTests
from tests.test_v5_g1f_engine import G1fEngineTests, NOW, FINAL, SYMBOLS, latest_rest


class G2AcceptanceFixture(unittest.TestCase):
    """Reuse source-journal setup, without inheriting unrelated tests."""
    add_event = G2PopulationAuditTests.add_event
    def setUp(self):
        G2PopulationAuditTests.setUp(self)
        self.next=self.first+INTERVAL_MS
        self.add_event(self.next)
        self.witness=SourceWitness(self.db)
        self.exchange={"symbols":[
            {"symbol":s,"contractType":"PERPETUAL","status":"TRADING",
             "quoteAsset":"USDT","marginAsset":"USDT"}
            for s in self.symbols
        ]}
        self.ticker=[{"symbol":"BTCUSDT","quoteVolume":"10000000"},
                     {"symbol":"ETHUSDT","quoteVolume":"5000000"}]
        self.sha=self.witness.witness_cohort(
            exchange=self.exchange,ticker=self.ticker,selected=self.symbols,
            first_event_open_ms=self.first,
            received_ms=self.first+INTERVAL_MS+1000,
            exchange_server_ms=self.first+INTERVAL_MS+900)
        for event in (self.first,self.next):
            self.write_source(event)

    def write_source(self,event):
        asof=event+INTERVAL_MS+1000
        source={
            s:{"bid":100.0,"ask":100.08,
               "quote_received_ms":asof-100,"trade_received_ms":asof-200,
               "market_connected":True,"public_connected":True,
               "market_epoch":1,"public_epoch":1}
            for s in self.symbols
        }
        self.witness.witness_event_quotes(
            cohort_digest=self.sha,event_open_ms=event,
            asof_ms=asof,sources=source)

    def acceptance(self):
        return source_acceptance(
            self.path,min_complete_events=2,
            now_ms=self.first+5*INTERVAL_MS)

    def test_two_consecutive_complete_source_events_pass(self):
        out=self.acceptance()
        self.assertEqual(out["audit"],"PASS")
        self.assertEqual(out["complete_source_witness_rows"],4)
        self.assertEqual(out["fully_source_verified_observation_events"],2)
        self.assertEqual(out["universe_selection_audit"]["rankable_not_in_frozen_top50"],0)
        self.assertEqual(out["symbol_event_source_recorded"],4)
        self.assertFalse(out["research_ready"])

    def test_missing_witness_event_row_never_passes(self):
        self.db.execute("DROP TRIGGER g2_quote_immutable_d")
        self.db.execute("DELETE FROM g2_quote_witness WHERE symbol='ETHUSDT' AND event_open_ms=?",
                        (self.next,))
        self.db.commit()
        self.assertIn("WITNESS_EVENT_DENOMINATOR_MISSING",self.acceptance()["violations"])

    def test_source_payload_corruption_detected(self):
        self.db.execute("DROP TRIGGER g2_quote_immutable_u")
        self.db.execute("UPDATE g2_quote_witness SET payload_sha='bad' WHERE symbol='BTCUSDT'")
        self.db.commit()
        self.assertIn("WITNESS_EVIDENCE_SHA_OR_CLOCK_INVALID",self.acceptance()["violations"])

    def test_older_unwitnessed_data_cannot_claim_pass(self):
        self.db.execute("DROP TRIGGER g2_cohort_immutable_d")
        self.db.execute("DELETE FROM g2_cohort_witness")
        self.db.commit()
        with self.assertRaisesRegex(AcceptanceHold,"WITNESSED_COHORT"):
            self.acceptance()

    def test_insufficient_real_event_windows_is_hold(self):
        r=source_acceptance(self.path,min_complete_events=3,
                            now_ms=self.first+5*INTERVAL_MS)
        self.assertEqual(r["audit"],"HOLD")
        self.assertEqual(r["event_manifests"],2)

    def test_held_quote_must_not_be_accepted_as_observed(self):
        self.db.execute("DROP TRIGGER g2_quote_immutable_u")
        row=self.db.execute(
            "SELECT payload_json FROM g2_quote_witness "
            "WHERE symbol='ETHUSDT' AND event_open_ms=?",
            (self.next,)
        ).fetchone()[0]
        import hashlib
        from nbot.v5.g1f_journal import canonical
        payload=json.loads(row)
        payload["source"]["quote_received_ms"]=payload["asof_ms"]-25000
        payload["status"]="HOLD"
        payload["hold_reasons"]=["QUOTE_STALE_OR_MISSING"]
        new=canonical(payload)
        self.db.execute("UPDATE g2_quote_witness SET payload_json=?,payload_sha=? "
                        "WHERE symbol='ETHUSDT' AND event_open_ms=?",
                        (new,hashlib.sha256(new.encode()).hexdigest(),self.next))
        self.db.commit()
        self.assertIn("HELD_SOURCE_WAS_ACCEPTED",self.acceptance()["violations"])


class G2LiveHookTests(unittest.TestCase):
    setUp = G1fEngineTests.setUp
    create = G1fEngineTests.create
    def test_original_g1f_engine_records_exact_source_clock_when_opted_in(self):
        s,j,ident,finality=self.create()
        try:
            # Existing G1F unit tests run without this optional hook.
            witness=SourceWitness(s.ledger.db)
            exchange={"symbols":[
                {"symbol":symbol,"contractType":"PERPETUAL","status":"TRADING",
                 "quoteAsset":"USDT","marginAsset":"USDT"}
                for symbol in SYMBOLS
            ]}
            ticker=[{"symbol":sym,"quoteVolume":str(1000000-i*10000)}
                    for i,sym in enumerate(SYMBOLS)]
            cid=witness.witness_cohort(
                exchange=exchange,ticker=ticker,selected=SYMBOLS,
                received_ms=FINAL+1000,exchange_server_ms=FINAL+950,
                first_event_open_ms=FINAL-INTERVAL_MS)
            self.assertEqual(cid,ident)
            cursor=[NOW+100]
            def clock():
                cursor[0]+=1000
                return cursor[0]
            async def skip(_):return None
            r=asyncio.run(audit_event(
                s,j,finality,symbols=SYMBOLS,cohort_digest=ident,
                event_open_ms=FINAL,getter=latest_rest,
                sleep=skip,clock=clock,source_witness=witness))
            self.assertEqual(r["unscorable"],4)
            rows=s.ledger.db.execute(
                "SELECT COUNT(*),MIN(asof_ms),MAX(asof_ms) FROM g2_quote_witness"
            ).fetchone()
            self.assertEqual(rows[0],2)
            self.assertEqual(rows[1],NOW+2100)
            self.assertEqual(rows[1],rows[2])
        finally:
            s.close()


if __name__=="__main__":
    unittest.main()
