"""CS-00 true owner backup root G2/G3 checkpoint+concurrent writer acceptance.

No live Binance data, credentials or NBOT start. Verifies a boundary is a
cross-file committed receipt and owner backup refuses torn/altered writes.
"""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from nbot_v5_1.cs00_state_writer import SourceOnlyStateWriter,StateCheckpointHold,state_gate
from nbot_v5_1.cs00_source_pipeline import SourceOnlyPipeline
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.core import FiveMinuteEvent
from scripts.nbot_v5_1_owner_backup import create_backup,BackupHold,_verify_archive
from test_v5_1_g2 import manifest,history,END_OPEN,END_DECISION
from test_v5_1_g4_source import frame,NOW

class CS00StateAndBackup(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="cs00-recoverable-state-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.state=self.root/"nbot-v5.1-state"
        self.out=self.root/"NBOT_Backups"
        self.state.mkdir(mode=0o700);self.out.mkdir(mode=0o700)
        for part in ("observations","exploration","journals","evidence",
                     "research","learning","models"):
            (self.state/part).mkdir(mode=0o700)
        self.book=ObservationBook(manifest())
        self.pipeline=SourceOnlyPipeline(self.book,
                       state_root=self.state,recorder_root=self.state/"evidence")
        for sym in self.book.manifest.symbols:
            self.assertTrue(self.book.bootstrap(sym,history(sym),as_of_ms=END_DECISION))

    def commit(self):
        return self.pipeline.on_boundary(FiveMinuteEvent(END_OPEN,END_DECISION))

    def test_CSSTATE01_real_G2_G3_receipts_and_owner_backup_are_integral(self):
        self.commit()
        check=SourceOnlyStateWriter(self.state).verify()
        self.assertEqual((check["g2"],check["g3"],check["checkpoints"]),(1,1,1))
        result=create_backup(state=self.state,destination=self.out)
        self.assertEqual(result["status"],"BACKUP_CREATED_AND_LOCALLY_VERIFIED")
        man=_verify_archive(Path(result["backup"]))
        self.assertEqual(len(man["files"]),4)
        self.assertFalse(result["offhost_saved"])
        self.assertEqual(man["trading_authority"],"NONE")

    def test_CSSTATE02_G3_missing_file_refuses_owner_backup(self):
        self.commit()
        victim=next((self.state/"exploration").iterdir())
        victim.unlink()
        with self.assertRaises(BackupHold):
            create_backup(state=self.state,destination=self.out)
        self.assertFalse(list(self.out.glob("*.tar.gz")))

    def test_CSSTATE03_journal_checkpoint_missing_refuses_owner_backup(self):
        self.commit()
        next((self.state/"journals").iterdir()).unlink()
        with self.assertRaisesRegex(BackupHold,"CHECKPOINT"):
            create_backup(state=self.state,destination=self.out)

    def test_CSSTATE04_tampered_G2_observation_refuses_backup(self):
        self.commit()
        p=next((self.state/"observations").glob("event_*.json"))
        p.write_bytes(p.read_bytes()+b"x")
        with self.assertRaises(BackupHold):
            create_backup(state=self.state,destination=self.out)

    def test_CSSTATE05_raw_source_seal_in_owner_backup_root(self):
        self.commit()
        for kind in ("TRADE","QUOTE","MARK"):
            self.pipeline.ingest_offline_frame(kind=kind,raw=frame(kind),
                           received_ms=NOW,epoch=1)
        self.pipeline.seal()
        r=create_backup(state=self.state,destination=self.out)
        man=_verify_archive(Path(r["backup"]))
        files=[x["path"] for x in man["files"]]
        self.assertEqual(sum(x.startswith("evidence/segment-") for x in files),2)
        self.assertEqual(sum(x.startswith("observations/") for x in files),2)
        self.assertEqual(sum(x.startswith("exploration/") for x in files),1)

    def test_CSSTATE06_frozen_cohort_no_second_event(self):
        self.commit()
        with self.assertRaises(Exception):
            self.pipeline.on_boundary(FiveMinuteEvent(END_OPEN,END_DECISION))
        self.assertEqual(SourceOnlyStateWriter(self.state).verify()["checkpoints"],1)

if __name__=="__main__":unittest.main()
