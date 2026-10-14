import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from nbot.v5.g4_forward_vault import ForwardSourceVault
from nbot.v5.g4_forward_independent_audit import audit_forward_source_copy
from tests.test_v5_g4_forward_vault import SYMS,NOW,trade


class BatchedVaultTests(unittest.TestCase):
    def test_metadata_durable_frames_bounded_and_crash_explicit(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"source.sqlite"
            db=sqlite3.connect(p);db.execute("PRAGMA journal_mode=WAL")
            v=ForwardSourceVault(db,symbols=SYMS,batch_frames=64)
            v.connect(route="market_aggtrade",at_ms=NOW)
            v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
            with sqlite3.connect(p) as independent:
                self.assertEqual(independent.execute("SELECT count(*) FROM g4_forward_receipts").fetchone()[0],1)
            independent.close()
            db.rollback();db.close()
            db=sqlite3.connect(p);v=ForwardSourceVault(db,symbols=SYMS,batch_frames=64)
            v.connect(route="market_aggtrade",at_ms=NOW+1)
            self.assertEqual(v.audit()["counts"]["ABRUPT_RESTART_HOLD"],1)
            db.close()

    def test_flush_and_independent_replay_keep_all_original_bytes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"source.sqlite"
            db=sqlite3.connect(p);v=ForwardSourceVault(db,symbols=SYMS,batch_frames=64)
            v.connect(route="market_aggtrade",at_ms=NOW)
            v.ingest(route="market_aggtrade",at_ms=NOW,raw=trade())
            v.flush();db.close()
            report=audit_forward_source_copy(db_path=p)
            self.assertEqual(report["records_verified"],2)
            self.assertEqual(report["source_recorded_frames"],1)

    def test_batch_cannot_be_unbounded(self):
        db=sqlite3.connect(":memory:")
        with self.assertRaisesRegex(ValueError,"BATCH_BOUNDS"):
            ForwardSourceVault(db,symbols=SYMS,batch_frames=257)
        db.close()
