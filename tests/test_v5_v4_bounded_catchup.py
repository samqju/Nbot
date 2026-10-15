"""V4-derived bounded catch-up adapted to V5 immutable G1 event source.

Synthetic sqlite fixtures only; never start G1/G4 collectors or trading.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from nbot.v5.continuous_research import bounded_original_event_batch
from nbot.v5.research_store import ResearchStore


class BoundedOriginalCatchupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.source=self.base/"g1source.sqlite"
        with sqlite3.connect(self.source) as db:
            db.execute("CREATE TABLE g1f_event_manifest (event_open_ms INTEGER PRIMARY KEY)")
            db.executemany("INSERT INTO g1f_event_manifest VALUES (?)",
                           [(300000*(i+1),) for i in range(25000)])
        self.store=ResearchStore(self.base/"continuous_research.sqlite")
        self.addCleanup(self.store.close)

    def due(self,n=3):
        return bounded_original_event_batch(
            self.source,self.store,start_event_ms=300000,max_events=n)

    def done(self,at):
        self.store.append("event:"+str(at),"EVENT_COMPLETE",at,
                          {"event_ms":at,"candidate_population":100})

    def test_25000_market_events_use_fixed_three_event_batch(self):
        self.assertEqual(self.due(),(300000,600000,900000))
        for x in (300000,600000,900000):
            self.done(x)
        self.assertEqual(self.due(),(1200000,1500000,1800000))
        self.assertEqual(self.due(1),(1200000,))
        self.assertEqual(self.store.audit()["integrity"],"PASS")

    def test_restart_cursor_does_not_repeat_completed_event(self):
        self.done(300000)
        self.store.close()
        self.store=ResearchStore(self.base/"continuous_research.sqlite")
        self.assertEqual(self.due(),(600000,900000,1200000))

    def test_incomplete_event_restarts_at_same_original_event(self):
        self.done(300000)
        self.store.append("candidate:synthetic","CANDIDATE",600000,
                          {"side":"LONG","order_authority":"NONE"})
        self.assertEqual(self.due(),(600000,900000,1200000))

    def test_missing_backfilled_event_above_completed_cursor_held(self):
        self.done(300000)
        self.done(600000)
        with sqlite3.connect(self.source) as db:
            db.execute("DELETE FROM g1f_event_manifest WHERE event_open_ms=300000")
        with self.assertRaisesRegex(ValueError,"HISTORICAL_EVENT_GAP_HOLD"):
            self.due()

    def test_extra_older_immutable_event_requires_independent_review(self):
        self.done(300000)
        with sqlite3.connect(self.source) as db:
            db.execute("INSERT INTO g1f_event_manifest VALUES (?)",(0,))
        # Event is before declared start boundary; it must not change cursor.
        self.assertEqual(self.due(),(600000,900000,1200000))

    def test_corrupt_cursor_clock_and_batch_size_hold(self):
        self.store.append("event:bad","EVENT_COMPLETE",300000,
                          {"event_ms":123,"candidate_population":100})
        with self.assertRaisesRegex(ValueError,"CURSOR_TAMPERED"):
            self.due()
        with self.assertRaisesRegex(ValueError,"CURSOR_INPUT_INVALID"):
            self.due(100000)

    def test_full_source_exhaustion_has_no_restart_replay(self):
        with sqlite3.connect(self.source) as db:
            db.execute("DELETE FROM g1f_event_manifest WHERE event_open_ms>600000")
        self.done(300000)
        self.done(600000)
        self.assertEqual(self.due(),())


if __name__=="__main__":
    unittest.main()
