"""Offline-only G4 source staged bootstrap and disabled systemd template."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from nbot.v5.g4_source_preflight import audit_g4_capture_preflight
from nbot.v5.g4_segmented_source import SegmentedForwardSource
from tests.test_v5_g4_source_binding import db_fixture


class G4ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.source=self.base/"g1g2g3.sqlite"
        db_fixture(self.source)
        self.root=self.base/"g4-forward-research"
        self.root.mkdir(mode=0o700)
        with sqlite3.connect(self.source) as db:
            symbols,digest=db.execute(
                "SELECT symbols_json,cohort_digest "
                "FROM g1f_universe_snapshots").fetchone()
        self.symbols=json.loads(symbols)
        self.original_digest=digest
        self.manifest=self.root/"cohort.json"
        self.manifest.write_text(json.dumps(
            {"symbols":self.symbols,"cohort_digest":digest}))

    def audit(self):
        return audit_g4_capture_preflight(
            g1_db=self.source,cohort_manifest=self.manifest,
            source_root=self.root)

    def test_private_original_fifty_cohort_passes_read_only(self):
        before=self.source.read_bytes()
        result=self.audit()
        self.assertEqual(result["audit"],"PASS")
        self.assertEqual(result["symbols"],50)
        self.assertEqual(result["g1_db_access"],"READ_ONLY")
        self.assertEqual(result["order_authority"],"NONE")
        self.assertEqual(self.source.read_bytes(),before)

    def test_tampered_manifest_rejected_before_any_network(self):
        manifest=json.loads(self.manifest.read_text())
        manifest["cohort_digest"]="0"*64
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.audit()

    def test_g1_original_cohort_digest_conflict_rejected(self):
        manifest=json.loads(self.manifest.read_text())
        manifest["symbols"][1]="ALTEREDUSDT"
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            self.audit()

    def test_archive_source_stays_independently_audited(self):
        archive=self.root/"segments"
        archive.mkdir(mode=0o700)
        source=SegmentedForwardSource(archive,symbols=self.symbols)
        source.connect(route="market_aggtrade",at_ms=1800000000000)
        self.assertEqual(self.audit()["g4_segment_archive"],
                         "EXISTING_AUDITED")
        p=next(archive.glob("segment-*.gz"))
        p.write_bytes(p.read_bytes()+b"corrupt")
        with self.assertRaises(ValueError):
            self.audit()

    def test_unsafe_source_root_or_symlink_manifest_forbidden(self):
        os.chmod(self.root,0o755)
        with self.assertRaisesRegex(ValueError,"G4_BOOTSTRAP_SOURCE_ROOT"):
            self.audit()
        os.chmod(self.root,0o700)
        self.manifest.unlink()
        self.manifest.symlink_to(self.source)
        with self.assertRaisesRegex(ValueError,"G4_BOOTSTRAP_SOURCE_ROOT"):
            self.audit()

    def test_source_unit_is_manual_observation_requisite_no_execution(self):
        unit=(Path(__file__).resolve().parents[1]/
              "deploy/v5/nbot-v5-g4-source-capture.service").read_text()
        self.assertIn("Requisite=nbot-v5-g1g2g3-observation.service",unit)
        self.assertIn("WorkingDirectory=/home/ubuntu/Nbot",unit)
        self.assertIn("Restart=no",unit)
        self.assertNotIn("\n[Install]",unit)
        self.assertIn("ConditionPathExists=/home/ubuntu/Nbot/runtime/source/OWNER_APPROVED_G4_CAPTURE_RELEASE",unit)
        self.assertIn("nbot.v5.g4_source_preflight",unit)
        self.assertIn("--storage-mode segments",unit)
        self.assertIn("--enable-network",unit)
        self.assertNotIn("--legacy-per-frame-sqlite-opt-in",unit)
        self.assertNotIn("api_key",unit.lower())
        self.assertNotIn("api_secret",unit.lower())


if __name__=="__main__":
    unittest.main()
