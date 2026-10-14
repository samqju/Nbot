"""Source-preserving deterministic G2 candidate replay tests, no real data."""
import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g1f_journal import CandidateJournal, canonical, digest
from nbot.v5.g2_population_replay import ReplayHold, audit_replay
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.pattern_adapter import build_observations_from_closed_candles


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"g2_replay.sqlite"
        self.db=sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.event=INTERVAL_MS*1000
        self.commit=self.event+INTERVAL_MS+1000
        self.symbols=tuple(sorted(["BTCUSDT"]+[f"COIN{i:02d}USDT" for i in range(9)]))
        CandidateJournal(self.db)
        self.digest=CandidateJournal(self.db).begin_cohort(
            self.symbols,selected_ms=self.event-300_000,
            event_open_ms=self.event,
        )
        self.db.execute("""
          CREATE TABLE candle_rows (
            symbol TEXT,open_ms INTEGER,candle_json TEXT,
            candle_sha TEXT,first_seen_ms INTEGER,
            PRIMARY KEY(symbol,open_ms))
        """)
        sources={}
        for idx,symbol in enumerate(self.symbols):
            bars=[]
            for k in range(96):
                ms=self.event-INTERVAL_MS*(95-k)
                p=100+idx*2+k*0.05+k*k*0.0002
                bar=(ms,float(p),float(p+0.7),float(p-0.5),
                     float(p+0.1),float(100+k+idx))
                bars.append(bar)
                packed=canonical(bar)
                self.db.execute("INSERT INTO candle_rows VALUES (?,?,?,?,?)",
                    (symbol,ms,packed,hashlib.sha256(packed.encode()).hexdigest(),
                     self.commit-1))
            sources[symbol]=bars
        records=build_observations_from_closed_candles(
            event_open_ms=self.event,decision_at_ms=self.commit,
            observed_at_ms=self.commit,eligible_symbols=self.symbols,
            candles_by_symbol=sources,
        )
        self.assertTrue(all(r["status"]=="OBSERVED" for r in records))
        self.assertEqual(len(records),20)
        summary={"cohort_digest":self.digest,"event_open_ms":self.event,
                 "status":"OBSERVE_ONLY","observed":20,"unscorable":0,
                 "btc_valid":True,"coverage_valid":True,"gap":False,
                 "research_ready":False,"training_labels_created":0,
                 "order_authority":"NONE"}
        self.db.execute("INSERT INTO g1f_event_manifest VALUES (?,?,?,?,?,?)",
                        (self.event,self.digest,self.commit,
                         summary["status"],canonical(summary),digest(summary)))
        for record in records:
            raw=canonical(record)
            self.db.execute("INSERT INTO g1f_candidate_events VALUES (?,?,?,?,?,?,?)",
                (record["decision_id"],self.event,record["symbol"],record["side"],
                 record["status"],hashlib.sha256(raw.encode()).hexdigest(),raw))
        self.db.commit()

    def report(self):
        return audit_replay(self.path,now_ms=self.commit+100_000)

    def test_verified_source_replays_all_twenty_both_directions(self):
        r=self.report()
        self.assertEqual(r["audit"],"PASS")
        self.assertEqual(r["exact_replay_matches"],20)
        self.assertEqual(r["replayed_candidate_records"],20)
        self.assertFalse(r["quote_snapshots_archived"])
        self.assertEqual(r["matured_outcomes"],0)

    def test_quote_witness_completeness_is_reported_truthfully(self):
        self.assertFalse(self.report()["quote_snapshots_archived"])
        self.db.execute("CREATE TABLE g2_quote_witness (event_open_ms INTEGER,symbol TEXT)")
        self.db.executemany(
            "INSERT INTO g2_quote_witness VALUES (?,?)",
            ((self.event,s) for s in self.symbols)
        )
        self.db.commit()
        self.assertTrue(self.report()["quote_snapshots_archived"])
        self.db.execute("DELETE FROM g2_quote_witness WHERE symbol='BTCUSDT'")
        self.db.commit()
        self.assertFalse(self.report()["quote_snapshots_archived"])

    def test_changed_candle_sha_is_not_trusted(self):
        self.db.execute("UPDATE candle_rows SET candle_sha='bad' WHERE symbol='BTCUSDT'")
        self.db.commit()
        r=self.report()
        self.assertEqual(r["audit"],"HOLD")
        self.assertIn("ARCHIVE_CANDLE_CLOCK_MISMATCH",r["violations"])

    def test_missing_96_history_is_hold(self):
        self.db.execute("DELETE FROM candle_rows WHERE symbol='BTCUSDT' LIMIT 1")
        self.db.commit()
        r=self.report()
        self.assertEqual(r["audit"],"HOLD")
        self.assertIn("ARCHIVE_HISTORY_INCOMPLETE",r["violations"])

    def test_bar_not_known_until_after_decision_is_hold(self):
        self.db.execute(
            "UPDATE candle_rows SET first_seen_ms=? "
            "WHERE symbol='BTCUSDT' AND open_ms=?",
            (self.commit+1,self.event))
        self.db.commit()
        r=self.report()
        self.assertEqual(r["audit"],"HOLD")
        self.assertIn("ARCHIVE_HISTORY_NOT_CAUSAL",r["violations"])

    def test_missing_db_or_symlink_forbidden(self):
        link=Path(self.tmp.name)/"linked.sqlite"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(ReplayHold,"SYMLINK"):
            audit_replay(link)
        with self.assertRaisesRegex(ReplayHold,"MISSING"):
            audit_replay(Path(self.tmp.name)/"absent.sqlite")

    def test_sample_limit_enforced(self):
        with self.assertRaisesRegex(ReplayHold,"BOUNDED"):
            audit_replay(self.path,max_events=500)

    def test_corrupted_candidate_detector_output_is_hold(self):
        self.db.execute("DROP TRIGGER g1f_candidate_no_update")
        row=self.db.execute(
            "SELECT decision_id,record_json FROM g1f_candidate_events LIMIT 1"
        ).fetchone()
        rec=json.loads(row[1])
        rec["patterns"]["PIN_BAR_REJECTION_V1"]="MATCH" if rec["patterns"]["PIN_BAR_REJECTION_V1"]!="MATCH" else "NO_MATCH"
        changed=canonical(rec)
        self.db.execute(
            "UPDATE g1f_candidate_events SET record_json=?,record_sha=? WHERE decision_id=?",
            (changed,hashlib.sha256(changed.encode()).hexdigest(),row[0]))
        self.db.commit()
        self.assertIn("REPLAY_FEATURE_MISMATCH",self.report()["violations"])


if __name__=="__main__":
    unittest.main()
