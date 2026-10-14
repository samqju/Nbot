"""G3 replay tests: source-verified event clocks and original SHA only."""
import hashlib
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.observation_contract import INTERVAL_MS
from nbot.v5.g3_frozen_replay import audit_g3, G3Hold
from tests.test_v5_g2_source_acceptance import G2AcceptanceFixture
from tests.test_v5_g3_market_context import candles
from nbot.v5.g1f_journal import canonical


class G3FrozenSourceTests(unittest.TestCase):
    add_event = G2AcceptanceFixture.add_event
    write_source = G2AcceptanceFixture.write_source

    def setUp(self):
        G2AcceptanceFixture.setUp(self)
        # Immutable two-event source, 97 progressively closed candles per
        # symbol. Receipt time is always after that candle closes, but never
        # after the ORIGINAL event's committed feature-valid-from clock.
        self.db.execute("""
          CREATE TABLE candle_rows (
            symbol TEXT NOT NULL,open_ms INTEGER NOT NULL,
            candle_json TEXT NOT NULL,candle_sha TEXT NOT NULL,
            first_seen_ms INTEGER NOT NULL,
            PRIMARY KEY(symbol,open_ms))
        """)
        for symbol in self.symbols:
            for i in range(97):
                bar_ms=self.first-(95-i)*INTERVAL_MS
                base=100+i*.07
                bar=(bar_ms,float(base),float(base+.25),
                     float(base-.25),float(base+.04),float(100+i))
                payload=canonical(bar)
                at=(self.first+INTERVAL_MS+100
                    if i<96 else self.next+INTERVAL_MS+100)
                self.db.execute(
                    "INSERT INTO candle_rows VALUES (?,?,?,?,?)",
                    (symbol,bar_ms,payload,
                     hashlib.sha256(payload.encode()).hexdigest(),at),
                )
        self.db.commit()

    def report(self):
        return audit_g3(self.path,max_events=2,
                        now_ms=self.first+5*INTERVAL_MS)

    def test_frozen_original_source_two_events_exact_and_repeatable(self):
        a,b=self.report(),self.report()
        self.assertEqual(a,b)
        self.assertEqual(a["audit"],"PASS")
        self.assertEqual(a["events_replayed"],2)
        self.assertEqual(a["frozen_cohort_size"],2)
        self.assertEqual(a["unknown_coin_events"],0)
        self.assertEqual(a["order_authority"],"NONE")
        self.assertNotEqual(a["event_evidence"][0]["feature_sha256"],
                            a["event_evidence"][1]["feature_sha256"])

    def test_unwitnessed_quote_rows_are_not_economically_accepted(self):
        self.db.execute("DROP TRIGGER g2_quote_immutable_d")
        self.db.execute(
            "DELETE FROM g2_quote_witness WHERE event_open_ms=?",
            (self.next,))
        self.db.commit()
        with self.assertRaisesRegex(G3Hold,"G2_SOURCE_UNQUALIFIED"):
            self.report()

    def test_mutated_candle_digest_cannot_pass_feature_replay(self):
        self.db.execute("UPDATE candle_rows SET candle_sha='FAKE' WHERE symbol='BTCUSDT'")
        self.db.commit()
        with self.assertRaisesRegex(G3Hold,"ASOF_BAR_EVIDENCE"):
            self.report()

    def test_future_received_candle_forbidden(self):
        self.db.execute(
            "UPDATE candle_rows SET first_seen_ms=? "
            "WHERE symbol='BTCUSDT' AND open_ms=?",
            (self.first+3*INTERVAL_MS,self.first))
        self.db.commit()
        with self.assertRaisesRegex(G3Hold,"ASOF_BAR_EVIDENCE"):
            self.report()

    def test_insufficient_event_window_not_pass(self):
        with self.assertRaisesRegex(G3Hold,"SOURCE_UNQUALIFIED"):
            audit_g3(self.path,max_events=3,
                     now_ms=self.first+5*INTERVAL_MS)

    def test_symlink_and_absent_evidence_refused(self):
        linked=Path(self.tmp.name)/"linked.sqlite"
        linked.symlink_to(self.path)
        with self.assertRaisesRegex(G3Hold,"MISSING_OR_LINK"):
            audit_g3(linked)
        with self.assertRaisesRegex(G3Hold,"MISSING_OR_LINK"):
            audit_g3(Path(self.tmp.name)/"absent.sqlite")


if __name__=="__main__":
    unittest.main()
