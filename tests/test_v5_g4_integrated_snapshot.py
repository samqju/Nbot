"""No-write original integrated WAL snapshot in an isolated research-only temp dir."""
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.v5.g4_integrated_snapshot import snapshot_integrated_source
from tests.test_v5_g4_source_binding import db_fixture


class G4IntegratedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.work=Path(self.tmp.name)
        self.source=self.work/"g1g2g3.sqlite"
        db_fixture(self.source)
        self.root=self.work/"g4-forward-source-review"
        self.root.mkdir(mode=0o700)
        self.copy=self.root/"g4_g1g2g3_review_copy.sqlite"

    def tearDown(self):
        self.tmp.cleanup()

    def test_online_consistent_copy_without_mutating_original(self):
        original=hashlib.sha256(self.source.read_bytes()).hexdigest()
        audit=snapshot_integrated_source(source_db=self.source,
                                         output_db=self.copy)
        self.assertEqual(audit["events"],1)
        self.assertEqual(audit["directional_candidates"],100)
        self.assertEqual(audit["g2_witnesses"],50)
        self.assertEqual(audit["g3_contexts"],1)
        self.assertEqual(audit["source_db_access"],"READ_ONLY")
        self.assertEqual(audit["source_mutations"],0)
        self.assertEqual(audit["order_authority"],"NONE")
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(),original)
        self.assertEqual(audit["file_sha256"],hashlib.sha256(self.copy.read_bytes()).hexdigest())
        self.assertEqual(os.stat(self.copy).st_mode & 0o077,0)

    def test_second_request_refuses_overwrite(self):
        snapshot_integrated_source(source_db=self.source,output_db=self.copy)
        with self.assertRaisesRegex(ValueError,"G4_G1_SNAPSHOT_UNSAFE_SOURCE_OR_DESTINATION"):
            snapshot_integrated_source(source_db=self.source,output_db=self.copy)

    def test_live_source_name_cannot_be_foreign(self):
        foreign=self.work/"other.sqlite"
        foreign.write_bytes(self.source.read_bytes())
        with self.assertRaisesRegex(ValueError,"G4_G1_SNAPSHOT_UNSAFE_SOURCE_OR_DESTINATION"):
            snapshot_integrated_source(source_db=foreign,output_db=self.copy)

    def test_refuses_missing_provenance_schema(self):
        with sqlite3.connect(self.source) as db:
            db.execute("DROP TABLE g2_quote_witness")
        with self.assertRaisesRegex(ValueError,"G4_G1_ORIGINAL_SCHEMA_INCOMPLETE"):
            snapshot_integrated_source(source_db=self.source,output_db=self.copy)
        self.assertFalse(self.copy.exists())

    def test_rejects_world_readable_destination(self):
        self.root.chmod(0o755)
        with self.assertRaisesRegex(ValueError,"G4_G1_SNAPSHOT_UNSAFE_SOURCE_OR_DESTINATION"):
            snapshot_integrated_source(source_db=self.source,output_db=self.copy)

if __name__=="__main__":
    unittest.main()
