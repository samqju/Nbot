"""Unit-only tests for one-time no-write original cohort export."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.v5.g1f_journal import canonical,digest
from nbot.v5.g4_cohort_export import export_frozen_cohort
from nbot.v5.g4_forward_capture_runner import source_cohort_file


def fixture(work: Path):
    original=work/"original.sqlite"
    with sqlite3.connect(original) as db:
        db.execute("CREATE TABLE g1f_universe_snapshots(cohort_digest TEXT,"
                   "symbols_json TEXT,selection_version TEXT)")
        db.execute("CREATE TABLE g2_cohort_witness(cohort_digest TEXT,"
                   "payload_json TEXT,payload_sha TEXT)")
        syms=sorted(["BTCUSDT"]+[f"COIN{i:02d}USDT" for i in range(49)])
        version="USDM_PERPETUAL_24H_QUOTE_VOLUME_V1"
        sha=digest({"selection_version":version,"symbols":tuple(syms)})
        db.execute("INSERT INTO g1f_universe_snapshots VALUES (?,?,?)",
                   (sha,canonical(syms),version))
        evidence={"cohort_digest":sha,"ranked_selected":syms}
        raw=canonical(evidence)
        db.execute("INSERT INTO g2_cohort_witness VALUES (?,?,?)",
                   (sha,raw,hashlib.sha256(raw.encode()).hexdigest()))
    target=work/"g4-forward-test"
    target.mkdir(mode=0o700)
    return original,target/"frozen_cohort.json"


class G4CohortExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.work=Path(self.tmp.name)
        self.original,self.out=fixture(self.work)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verified_original_populates_strict_readonly_frozen_manifest(self):
        before=hashlib.sha256(self.original.read_bytes()).hexdigest()
        result=export_frozen_cohort(db_path=self.original,output=self.out)
        self.assertEqual(result["symbols"],50)
        self.assertEqual(result["source_db_mutations"],0)
        self.assertEqual(len(source_cohort_file(self.out.read_bytes())),50)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(),before)
        self.assertEqual(self.out.stat().st_mode & 0o077,0)

    def test_second_export_refuses_rewrite(self):
        export_frozen_cohort(db_path=self.original,output=self.out)
        with self.assertRaisesRegex(ValueError,"G4_COHORT_OUTPUT_NAME_OR_EXISTENCE_INVALID"):
            export_frozen_cohort(db_path=self.original,output=self.out)

    def test_outside_a_private_g4_source_root_is_refused(self):
        target=self.work/"wrong"/"frozen_cohort.json"
        target.parent.mkdir()
        with self.assertRaisesRegex(ValueError,"G4_COHORT_ISOLATED_OUTPUT_DIR_INVALID"):
            export_frozen_cohort(db_path=self.original,output=target)

    def test_bad_original_cohort_sha_holds(self):
        with sqlite3.connect(self.original) as db:
            db.execute("UPDATE g1f_universe_snapshots SET cohort_digest=?",("0"*64,))
        with self.assertRaisesRegex(ValueError,"G4_COHORT_FROZEN_G1_SOURCE_INVALID"):
            export_frozen_cohort(db_path=self.original,output=self.out)

    def test_missing_original_g2_provenance_holds(self):
        with sqlite3.connect(self.original) as db:
            db.execute("DELETE FROM g2_cohort_witness")
        with self.assertRaisesRegex(ValueError,"G4_COHORT_G2_WITNESS_NOT_VERIFIED"):
            export_frozen_cohort(db_path=self.original,output=self.out)

    def test_symlink_source_refused(self):
        symlink=self.work/"link.sqlite"
        symlink.symlink_to(self.original)
        with self.assertRaisesRegex(ValueError,"G4_COHORT_INPUT_NOT_REGULAR_DB"):
            export_frozen_cohort(db_path=symlink,output=self.out)

if __name__=="__main__":
    unittest.main()
