"""Synthetic-only G4 WAL backup/restore and safety tests, never live DB."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.v5.g4_forward_backup import backup_and_verify
from nbot.v5.g4_forward_vault import ForwardSourceVault

CLOCK=1800000000000


class G4RawBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/"g4-forward-backup-test"
        self.root.mkdir(mode=0o700)
        self.src=self.root/"g4_raw_source.sqlite"
        self.dst=self.root/"g4_source_restored.sqlite"
        with sqlite3.connect(self.src) as db:
            db.execute("PRAGMA journal_mode=WAL")
            vault=ForwardSourceVault(db,symbols=["BTCUSDT","QNTUSDT"])
            vault.connect(route="market_aggtrade",at_ms=CLOCK)
            vault.ingest(route="market_aggtrade",at_ms=CLOCK+10,raw=b"synthetic-bad-raw")
            vault.disconnect(route="market_aggtrade",at_ms=CLOCK+20)

    def tearDown(self):
        self.tmp.cleanup()

    def test_isolated_backup_verified_and_not_a_model_label(self):
        before=hashlib.sha256(self.src.read_bytes()).hexdigest()
        r=backup_and_verify(source_db=self.src,restore_copy=self.dst)
        self.assertEqual(r["status"],"G4_ISOLATED_SOURCE_SQLITE_BACKUP_RESTORED_AND_VERIFIED")
        self.assertEqual(r["restored_records"],3)
        self.assertEqual(r["source_head_sha256"],r["restored_head_sha256"])
        self.assertFalse(r["source_scientific_accepted"])
        self.assertEqual(r["training_labels_created"],0)
        self.assertEqual(self.src.read_bytes() and
                         hashlib.sha256(self.src.read_bytes()).hexdigest(),before)

    def test_refuses_to_overwrite_existing_evidence(self):
        backup_and_verify(source_db=self.src,restore_copy=self.dst)
        with self.assertRaisesRegex(ValueError,"G4_SNAPSHOT_DESTINATION_NOT_ISOLATED_OR_FRESH"):
            backup_and_verify(source_db=self.src,restore_copy=self.dst)

    def test_refuses_any_original_observation_db_name(self):
        with self.assertRaisesRegex(ValueError,"G4_SNAPSHOT_DESTINATION_NOT_ISOLATED_OR_FRESH"):
            backup_and_verify(source_db=self.root/"g1g2g3.sqlite",restore_copy=self.dst)

    def test_refuses_outside_root_restore(self):
        external=Path(self.tmp.name)/"g4_source_restored.sqlite"
        with self.assertRaisesRegex(ValueError,"G4_SNAPSHOT_DESTINATION_NOT_ISOLATED_OR_FRESH"):
            backup_and_verify(source_db=self.src,restore_copy=external)

    def test_corrupt_ledger_fails_before_creating_backup(self):
        with sqlite3.connect(self.src) as db:
            db.execute("DROP TRIGGER g4_forward_receipts_no_update")
            db.execute("UPDATE g4_forward_receipts SET raw_frame=? "
                       "WHERE kind='FRAME'",(b"changed",))
        with self.assertRaisesRegex(ValueError,"G4_AUDIT_RAW_OR_SEQUENCE_TAMPERED"):
            backup_and_verify(source_db=self.src,restore_copy=self.dst)
        self.assertFalse(self.dst.exists())

if __name__=="__main__":
    unittest.main()
