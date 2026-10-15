"""CS-00 frozen 100/200/20 source-only source pipeline rehearsal."""
import tempfile
from pathlib import Path
import unittest
from nbot_v5_1.cs00_source_pipeline import SourceOnlyPipeline
from nbot_v5_1.cs00_commissioning import CommissioningHold
from nbot_v5_1.core import FiveMinuteEvent
from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.deep_segments import DeepSegmentRecorder
from test_v5_1_g2 import manifest,history,END_OPEN,END_DECISION
from test_v5_1_g4_source import frame,NOW

class SourcePipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="cs00-source-pipeline-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"raw"
        self.root.mkdir(mode=0o700)
        self.book=ObservationBook(manifest())
        self.pipeline=SourceOnlyPipeline(self.book,recorder_root=self.root)

    def boot(self):
        for s in self.book.manifest.symbols:
            self.assertTrue(self.book.bootstrap(s,history(s),as_of_ms=END_DECISION))
        return self.pipeline.on_boundary(FiveMinuteEvent(END_OPEN,END_DECISION))

    def test_CSP01_100_200_20_freeze_and_no_order(self):
        x=self.boot()
        self.assertEqual((x.broad,x.directions,x.deep),(100,200,20))
        self.assertEqual(x.action,"NO_TRADE")
        self.assertEqual(x.financial_authority,"NONE")
        self.assertIn("BTCUSDT",self.pipeline.deep.symbols)
        self.assertEqual(self.pipeline.status()["original_virtual_allowed"],False)
        self.assertEqual(self.pipeline.status()["source_frames"],0)

    def test_CSP02_live_frame_without_cohort_is_blocked(self):
        with self.assertRaises(CommissioningHold):
            self.pipeline.ingest_offline_frame(kind="TRADE",raw=frame(),
                                              received_ms=NOW,epoch=1)

    def test_CSP03_20x3_original_shaped_bytes_seal_replay(self):
        self.boot()
        for s in self.pipeline.deep.symbols:
            for k in ("TRADE","QUOTE","MARK"):
                r=self.pipeline.ingest_offline_frame(
                    kind=k,raw=frame(k,symbol=s,id=8),
                    received_ms=NOW,epoch=1)
                self.assertFalse(r.source_qualified)
        self.assertEqual(self.pipeline.status()["source_frames"],60)
        self.pipeline.seal()
        reread=DeepSegmentRecorder(self.root,symbols=tuple(self.pipeline.deep.symbols))
        proof=reread.replay()
        self.assertIsNotNone(proof)
        self.assertEqual(self.pipeline.status()["source_grade"],
                         "LOCAL_UNQUALIFIED_NO_ORIGINAL_RELEASE")

    def test_CSP04_trade_gap_holds_and_cannot_grade_score(self):
        self.boot()
        self.pipeline.ingest_offline_frame(
            kind="TRADE",raw=frame(id=8),received_ms=NOW,epoch=1)
        status=self.pipeline.ingest_offline_frame(
            kind="TRADE",raw=frame(id=10,received=NOW+1000),
            received_ms=NOW+1000,epoch=1)
        self.assertEqual(status.state,"SOURCE_HOLD")
        self.assertEqual(self.pipeline.status()["source_gap_count"],1)
        self.assertEqual(self.pipeline.status()["financial_authority"],"NONE")

    def test_CSP05_boundary_replay_never_double_counts(self):
        self.boot()
        with self.assertRaises(CommissioningHold):
            self.pipeline.on_boundary(FiveMinuteEvent(END_OPEN,END_DECISION))
        self.assertEqual(self.pipeline.status()["boundaries"],1)

    def test_CSP06_emergency_stop_locks_every_source_kind(self):
        self.boot()
        z=self.pipeline.emergency_hold(at_ms=NOW,reason="OFFLINE_FORCED_FAIL")
        self.assertTrue(z["must_stop_source_only_intake"])
        self.assertFalse(z["restart_without_epoch_audit"])
        self.assertEqual(len(self.pipeline.intake.quarantine),60)

    def test_CSP07_resource_alarm_is_HOLD_without_start(self):
        self.boot()
        x=self.pipeline.heartbeat(
            at_ms=NOW,rss_kib=300000,
            free_disk_bytes=1,queue_depth=5000,boundary_lag_ms=2000)
        self.assertEqual(x["state"],"EMERGENCY_SOURCE_HOLD")
        self.assertFalse(self.pipeline.status()["active"])

if __name__=="__main__":unittest.main()
