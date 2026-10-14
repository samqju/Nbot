"""Read-only original G1 hold investigation mocks; no production DB writes."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.v5.g4_original_hold_probe import find_explicit_g1_holds
from tests.test_v5_g4_source_binding import db_fixture,EVENT,canonical,digest


class OriginalHoldAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"original_simulated.sqlite"
        db_fixture(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_hold_returns_empty_no_trade_claim(self):
        r=find_explicit_g1_holds(self.path)
        self.assertEqual(r["explicit_hold_events"],0)
        self.assertEqual(r["original_source_mutations"],0)
        self.assertEqual(r["order_authority"],"NONE")

    def test_explicit_one_coin_both_sides_hold_is_not_deleted(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE g1f_event_manifest SET state='HOLD'")
            for direction in ("LONG","SHORT"):
                raw=db.execute("SELECT record_json FROM g1f_candidate_events "
                               "WHERE event_open_ms=? AND symbol='BTCUSDT' "
                               "AND direction=?",(EVENT,direction)).fetchone()[0]
                row=json.loads(raw)
                row["status"]="UNSCORABLE"
                row["reason_codes"]=["TRADE_NOT_FRESH"]
                db.execute("UPDATE g1f_candidate_events SET status=?,record_json=?,record_sha=? "
                           "WHERE event_open_ms=? AND symbol='BTCUSDT' AND direction=?",
                           ("UNSCORABLE",canonical(row),digest(row),EVENT,direction))
        r=find_explicit_g1_holds(self.path)
        self.assertEqual(r["total_event_manifests"],1)
        self.assertEqual(r["explicit_hold_events"],1)
        self.assertEqual(r["holds"][0]["held_symbols"],["BTCUSDT"])
        self.assertEqual(r["holds"][0]["candidate_reason_counts"]["TRADE_NOT_FRESH"],2)

    def test_refuses_missing_production_copy(self):
        with self.assertRaisesRegex(ValueError,"G1_HOLD_PROBE_SOURCE_INVALID"):
            find_explicit_g1_holds(Path(self.tmp.name)/"does-not-exist.sqlite")


if __name__=="__main__":
    unittest.main()
