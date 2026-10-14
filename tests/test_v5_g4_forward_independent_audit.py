"""Synthetic-only separate G4 SHA+original frame source read audit tests."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.v5.g4_forward_independent_audit import audit_forward_source_copy
from nbot.v5.g4_forward_vault import ForwardSourceVault

SYMS=["BTCUSDT","QNTUSDT"]
NOW=1800000000000


def msg(agg=100,at=NOW):
    return json.dumps({"stream":"qntusdt@aggTrade",
         "data":{"e":"aggTrade","E":at-100,"s":"QNTUSDT",
                 "a":agg,"f":500+3*(agg-100),"l":502+3*(agg-100),
                 "T":at-150,"p":"200","q":"2.5","m":False,"st":1}},
                 separators=(",",":")).encode()


class G4IndependentAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"g4_raw_source.sqlite"
        with sqlite3.connect(self.path) as db:
            v=ForwardSourceVault(db,symbols=SYMS)
            v.connect(route="market_aggtrade",at_ms=NOW-1000)
            v.ingest(route="market_aggtrade",at_ms=NOW,raw=msg())
            v.ingest(route="market_aggtrade",at_ms=NOW+1000,raw=msg(agg=101,at=NOW+1000))
            v.disconnect(route="market_aggtrade",at_ms=NOW+1500)

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return audit_forward_source_copy(db_path=self.path)

    def test_independent_reader_verifies_chain_and_no_financial_authority(self):
        r=self.check()
        self.assertEqual(r["integrity_audit"],"PASS")
        self.assertEqual(r["source_recorded_frames"],2)
        self.assertEqual(r["records_verified"],4)
        self.assertEqual(r["socket_closed_events"],1)
        self.assertFalse(r["g4_scientific_accepted"])
        self.assertEqual(r["qualified_economic_outcomes"],0)
        self.assertFalse(r["continuous_quote_trade_funding_coverage_proven"])

    def test_integrity_reader_does_not_change_original_file(self):
        before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.check()
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),before)

    def test_tampered_frame_rejected_even_with_original_sha(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER g4_forward_receipts_no_update")
            db.execute("UPDATE g4_forward_receipts SET raw_frame=? "
                       "WHERE kind='FRAME' AND seq=2",(b"corrupt",))
        with self.assertRaisesRegex(ValueError,"G4_AUDIT_RAW_OR_SEQUENCE_TAMPERED"):
            self.check()

    def test_tampered_stored_state_rejected(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER g4_forward_receipts_no_update")
            db.execute("UPDATE g4_forward_receipts SET evidence_state=? "
                       "WHERE kind='FRAME' AND seq=2",("HOLD",))
        with self.assertRaisesRegex(ValueError,"G4_AUDIT_CHAIN_TAMPERED"):
            self.check()

    def test_missing_route_frame_is_distinct_source_coverage_gap(self):
        r=self.check()
        self.assertEqual(r["distinct_recorded_symbols_per_route"]["public_bookticker"],0)
        self.assertEqual(r["distinct_recorded_symbols_per_route"]["market_markprice"],0)
        self.assertFalse(r["g4_scientific_accepted"])

    def test_corrupt_cohort_holds(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DROP TRIGGER g4_forward_cohort_no_update")
            db.execute("UPDATE g4_forward_cohort SET cohort_sha=?",("1"*64,))
        with self.assertRaisesRegex(ValueError,"G4_AUDIT_COHORT_CHANGED"):
            self.check()

    def test_unclean_epoch_is_counted_not_discarded(self):
        with sqlite3.connect(self.path) as db:
            v=ForwardSourceVault(db,symbols=SYMS)
            v.connect(route="market_aggtrade",at_ms=NOW+2000)
            v.ingest(route="market_aggtrade",at_ms=NOW+2200,
                     raw=msg(agg=500,at=NOW+2200))
            # No disconnect. Restart must explicitly HOLD prior open source.
            v.connect(route="market_aggtrade",at_ms=NOW+3000)
        r=self.check()
        self.assertEqual(r["unclean_restart_events"],1)
        self.assertGreaterEqual(r["held_frames"],0)
        self.assertFalse(r["g4_scientific_accepted"])

    def test_invalid_input_path(self):
        with self.assertRaisesRegex(ValueError,"G4_AUDIT_SOURCE_MISSING_OR_SYMLINK"):
            audit_forward_source_copy(db_path=self.path.with_name("missing.sqlite"))


if __name__=="__main__":
    unittest.main()
