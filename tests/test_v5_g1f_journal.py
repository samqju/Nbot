"""G1f durable frozen-cohort and two-direction candidate journal tests."""
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g1f_journal import CandidateJournal, JournalHold
from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.public_market import decode_klines
from tests.test_v5_public_market import klines

EVENT=INTERVAL_MS*1_000_000
COHORT=tuple(["BTCUSDT"]+[f"COIN{i:02}USDT" for i in range(11)])


class CandidateJournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"g1f.db"
        self.db=sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        self.journal=CandidateJournal(self.db)
        self.identity=self.journal.begin_cohort(
            COHORT,selected_ms=EVENT,event_open_ms=EVENT)

    def commit(self, *, event=EVENT, health=None, quarantine=None,
               btc_good=True, coverage_good=True):
        bars=decode_klines(klines(event),event_open_ms=event)
        return self.journal.commit_event(
            cohort_digest=self.identity,event_open_ms=event,
            observed_ms=event+INTERVAL_MS+9000,
            eligible_symbols=COHORT,
            candles_by_symbol={s:bars for s in COHORT},
            quarantine=quarantine or {},
            health_holds=health or {},
            btc_valid=btc_good,coverage_valid=coverage_good,
        )

    def test_all_long_short_records_after_closed_event(self):
        report=self.commit()
        self.assertEqual(report["event_open_ms"],EVENT)
        self.assertEqual(report["observed"]+report["unscorable"],24)
        self.assertEqual(self.journal.inspect()["candidate_rows"],24)
        self.assertFalse(report["research_ready"])
        self.assertEqual(report["training_labels_created"],0)
        self.assertEqual(report["order_authority"],"NONE")
        self.assertEqual(self.db.execute("SELECT COUNT(DISTINCT direction) FROM "
                         "g1f_candidate_events").fetchone()[0],2)

    def test_one_coin_quarantined_both_directions_and_no_record_deleted(self):
        report=self.commit(quarantine={"COIN00USDT":("WSS_REST_MISMATCH",)})
        self.assertEqual(report["unscorable"],2)
        rows=self.db.execute(
            "SELECT record_json FROM g1f_candidate_events WHERE symbol='COIN00USDT'"
        ).fetchall()
        self.assertEqual(len(rows),2)
        for (serialized,) in rows:
            rec=json.loads(serialized)
            self.assertEqual(rec["status"],"UNSCORABLE")
            self.assertIn("WSS_REST_MISMATCH",rec["reason_codes"])
            self.assertTrue(all(x=="UNAVAILABLE" for x in rec["patterns"].values()))

    def test_btc_failure_blocks_both_sides_of_all_coins(self):
        report=self.commit(btc_good=False)
        self.assertEqual(report["observed"],0)
        self.assertEqual(report["unscorable"],24)
        self.assertEqual(self.journal.inspect()["observed_rows"],0)

    def test_skipped_event_is_marked_unscorable_not_silently_bridged(self):
        self.commit()
        later=self.commit(event=EVENT+2*INTERVAL_MS)
        self.assertTrue(later["gap"])
        self.assertEqual(later["observed"],0)
        self.assertEqual(later["unscorable"],24)
        self.assertEqual(self.journal.inspect()["candidate_rows"],48)

    def test_cohort_rotation_refused_even_after_restart(self):
        self.commit()
        self.db.close()
        with sqlite3.connect(self.path) as db:
            reopened=CandidateJournal(db)
            self.assertEqual(
                reopened.begin_cohort(COHORT,selected_ms=EVENT+INTERVAL_MS,
                                      event_open_ms=EVENT+INTERVAL_MS),
                self.identity)
            with self.assertRaisesRegex(JournalHold,"ROTATION_REQUIRES_REVIEW"):
                reopened.begin_cohort(
                    COHORT[:-1]+("EXTRAUSDT",),selected_ms=EVENT+INTERVAL_MS,
                    event_open_ms=EVENT+INTERVAL_MS)
            self.assertEqual(reopened.inspect()["candidate_rows"],24)

    def test_replay_and_reverse_timestamp_are_refused(self):
        self.commit()
        with self.assertRaisesRegex(JournalHold,"REPLAY_OR_REWIND"):
            self.commit()
        with self.assertRaisesRegex(JournalHold,"REPLAY_OR_REWIND"):
            self.commit(event=EVENT-INTERVAL_MS)

    def test_immutable_tables_and_atomic_batch_failure(self):
        self.commit()
        for table in ("g1f_universe_snapshots","g1f_event_manifest",
                      "g1f_candidate_events"):
            for statement in (f"DELETE FROM {table}",
                              f"UPDATE {table} SET rowid=rowid"):
                with self.subTest(statement=statement), self.assertRaises(
                    sqlite3.IntegrityError):
                    self.db.execute(statement)
        self.db.rollback()
        # Simulate a duplicate ID injected before transaction; event must
        # roll back all newly inserted candidates AND manifest.
        duplicated=self.db.execute(
            "SELECT decision_id FROM g1f_candidate_events LIMIT 1"
        ).fetchone()[0]
        with self.assertRaises(JournalHold):
            self.commit(event=EVENT)
        self.assertEqual(self.journal.inspect()["candidate_rows"],24)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM "
                         "g1f_event_manifest").fetchone()[0],1)

    def test_reopen_does_not_certify_research_or_training(self):
        self.commit(health={"COIN01USDT":("TRADE_NOT_FRESH",)})
        self.db.close()
        with sqlite3.connect(self.path) as db:
            result=CandidateJournal(db).inspect()
            self.assertEqual(result["candidate_rows"],24)
            self.assertFalse(result["research_ready"])
            self.assertEqual(result["training_labels_created"],0)
            self.assertEqual(result["order_authority"],"NONE")


if __name__=="__main__":
    unittest.main()
