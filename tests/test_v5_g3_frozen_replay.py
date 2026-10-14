"""G3 replay: frozen G2 witness clocks, full breadth and tampering fail closed."""
import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.observation_contract import INTERVAL_MS, PATTERN_IDS, SCHEMA_VERSION, SIDES
from nbot.v5.g1f_journal import CandidateJournal, canonical, digest
from nbot.v5.g2_source_witness import SourceWitness
from nbot.v5.g3_frozen_replay import audit_g3, G3Hold


class G3FrozenSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"g3_original_proof.sqlite"
        self.db=sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.first=INTERVAL_MS*1234
        self.next=self.first+INTERVAL_MS
        self.symbols=tuple(sorted(("BTCUSDT",)+tuple(f"COIN{i:02d}USDT" for i in range(11))))
        self.journal=CandidateJournal(self.db)
        self.cohort=self.journal.begin_cohort(
            self.symbols,selected_ms=self.first+INTERVAL_MS+900,
            event_open_ms=self.first
        )
        self.witness=SourceWitness(self.db)
        exchange={"symbols":[
            {"symbol":s,"contractType":"PERPETUAL","status":"TRADING",
             "quoteAsset":"USDT","marginAsset":"USDT"}
            for s in self.symbols
        ]}
        ticker=[{"symbol":s,"quoteVolume":str(10000000-i*1000)}
                for i,s in enumerate(self.symbols)]
        self.assertEqual(self.witness.witness_cohort(
            exchange=exchange,ticker=ticker,selected=self.symbols,
            received_ms=self.first+INTERVAL_MS+1000,
            exchange_server_ms=self.first+INTERVAL_MS+900,
            first_event_open_ms=self.first),self.cohort)
        self.db.execute("""
        CREATE TABLE candle_rows(
          symbol TEXT NOT NULL,open_ms INTEGER NOT NULL,
          candle_json TEXT NOT NULL,candle_sha TEXT NOT NULL,
          first_seen_ms INTEGER NOT NULL,
          PRIMARY KEY(symbol,open_ms))
        """)
        for symbol in self.symbols:
            for i in range(97):
                bar_ms=self.first-(95-i)*INTERVAL_MS
                base=100+i*.07
                bar=(bar_ms,float(base),float(base+.25),float(base-.25),
                     float(base+.04),float(100+i))
                payload=canonical(bar)
                received=(self.first+INTERVAL_MS+100
                          if i<96 else self.next+INTERVAL_MS+100)
                self.db.execute(
                    "INSERT INTO candle_rows VALUES (?,?,?,?,?)",
                    (symbol,bar_ms,payload,
                     hashlib.sha256(payload.encode()).hexdigest(),received)
                )
        for event in (self.first,self.next):
            self.write_event(event)
        self.db.commit()

    def write_event(self,event):
        committed=event+INTERVAL_MS+1000
        total=2*len(self.symbols)
        summary={"cohort_digest":self.cohort,"event_open_ms":event,
                 "status":"OBSERVE_ONLY","observed":total,"unscorable":0,
                 "btc_valid":True,"coverage_valid":True,"gap":False,
                 "research_ready":False,"training_labels_created":0,
                 "order_authority":"NONE"}
        self.db.execute(
            "INSERT INTO g1f_event_manifest VALUES (?,?,?,?,?,?)",
            (event,self.cohort,committed,
             "OBSERVE_ONLY",canonical(summary),digest(summary)))
        for symbol in self.symbols:
            for side in SIDES:
                identity=digest({"schema":SCHEMA_VERSION,"event_open_ms":event,
                                 "symbol":symbol,"side":side})
                record={
                    "schema_version":SCHEMA_VERSION,"decision_id":identity,
                    "event_open_ms":event,"decision_at_ms":committed,
                    "symbol":symbol,"side":side,"status":"OBSERVED",
                    "reason_codes":[],"action":"OBSERVE_ONLY",
                    "order_authority":"NONE",
                    "patterns":{p:"NO_MATCH" for p in PATTERN_IDS}
                }
                raw=canonical(record)
                self.db.execute(
                    "INSERT INTO g1f_candidate_events VALUES (?,?,?,?,?,?,?)",
                    (identity,event,symbol,side,"OBSERVED",
                     hashlib.sha256(raw.encode()).hexdigest(),raw))
        sources={
            s:{"bid":100.,"ask":100.08,
               "quote_received_ms":committed-100,
               "trade_received_ms":committed-200,
               "market_connected":True,"public_connected":True,
               "market_epoch":1,"public_epoch":1}
            for s in self.symbols
        }
        result=self.witness.witness_event_quotes(
            cohort_digest=self.cohort,event_open_ms=event,
            asof_ms=committed,sources=sources)
        self.assertEqual(result["recorded"],len(self.symbols))

    def report(self):
        return audit_g3(self.path,max_events=2,
                        now_ms=self.first+5*INTERVAL_MS)

    def test_two_original_source_events_pass_and_are_deterministic(self):
        a,b=self.report(),self.report()
        self.assertEqual(a,b)
        self.assertEqual(a["audit"],"PASS")
        self.assertEqual(a["events_replayed"],2)
        self.assertEqual(a["frozen_cohort_size"],len(self.symbols))
        self.assertEqual(a["unknown_coin_events"],0)
        self.assertEqual(a["order_authority"],"NONE")
        self.assertNotEqual(a["event_evidence"][0]["feature_sha256"],
                            a["event_evidence"][1]["feature_sha256"])

    def test_missing_original_witness_holds_all_replay(self):
        self.db.execute("DROP TRIGGER g2_quote_immutable_d")
        self.db.execute("DELETE FROM g2_quote_witness WHERE event_open_ms=?",
                        (self.next,))
        self.db.commit()
        with self.assertRaisesRegex(G3Hold,"G2_SOURCE_UNQUALIFIED"):
            self.report()

    def test_forged_candle_sha_rejected(self):
        self.db.execute("UPDATE candle_rows SET candle_sha='FAKE' WHERE symbol='BTCUSDT'")
        self.db.commit()
        with self.assertRaisesRegex(G3Hold,"ASOF_BAR_EVIDENCE_INVALID"):
            self.report()

    def test_candle_receipt_after_original_commit_is_future_data(self):
        self.db.execute(
            "UPDATE candle_rows SET first_seen_ms=? "
            "WHERE symbol='BTCUSDT' AND open_ms=?",
            (self.first+3*INTERVAL_MS,self.first))
        self.db.commit()
        with self.assertRaisesRegex(G3Hold,"ASOF_BAR_EVIDENCE_INVALID"):
            self.report()

    def test_missing_third_complete_event_is_hold(self):
        with self.assertRaisesRegex(G3Hold,"G2_SOURCE_UNQUALIFIED"):
            audit_g3(self.path,max_events=3,
                     now_ms=self.first+5*INTERVAL_MS)

    def test_symlink_and_missing_database_refused(self):
        linked=Path(self.temp.name)/"linked.sqlite"
        linked.symlink_to(self.path)
        with self.assertRaisesRegex(G3Hold,"MISSING_OR_LINK"):
            audit_g3(linked)
        with self.assertRaisesRegex(G3Hold,"MISSING_OR_LINK"):
            audit_g3(Path(self.temp.name)/"missing.sqlite")


if __name__=="__main__":
    unittest.main()
