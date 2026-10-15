"""Rollover and interrupted copy recovery using disposable synthetic bytes."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nbot.v5.g4_archive_rollover import archive_committed_segments
from nbot.v5.g4_segmented_source import SegmentedForwardSource, read_segments
from tests.test_v5_g4_forward_vault import quote, NOW
from tests.test_v5_g4_segmented_source import SYMS


class ArchiveRolloverTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"hot"
        self.cold=Path(self.temp.name)/"mounted-archive"
        self.root.mkdir(mode=0o700); self.cold.mkdir(mode=0o700)
        self.source=SegmentedForwardSource(self.root,symbols=SYMS,max_pending_frames=16,
                                           max_pending_bytes=65536,max_disk_bytes=1048576)
        self.source.connect(route="public_bookticker",at_ms=NOW-1000)
        for i in range(200):
            self.source.ingest(route="public_bookticker",at_ms=NOW+i,
                               raw=quote(symbol=SYMS[i%50],at=NOW+i))
        self.source.flush()

    def test_lossless_rollover_preserves_receipt_and_segment_chain_after_restart(self):
        before=list(read_segments(self.root,SYMS))
        result=archive_committed_segments(self.root,self.cold)
        self.assertGreater(result["segments_relocated"],0)
        self.assertGreater(result["hot_bytes_released"],0)
        self.assertEqual(list(read_segments(self.root,SYMS)),before)
        restarted=SegmentedForwardSource(self.root,symbols=SYMS)
        restarted.connect(route="public_bookticker",at_ms=NOW+1000)
        self.assertEqual(restarted.audit()["counts"]["ABRUPT_RESTART_HOLD"],1)

    def test_termination_after_locator_before_unlink_is_recoverable(self):
        before=list(read_segments(self.root,SYMS))
        with patch.object(Path,"unlink",side_effect=OSError("SYNTHETIC_TERMINATION")):
            with self.assertRaisesRegex(OSError,"TERMINATION"):
                archive_committed_segments(self.root,self.cold)
        self.assertEqual(list(read_segments(self.root,SYMS)),before)
        archive_committed_segments(self.root,self.cold)
        self.assertEqual(list(read_segments(self.root,SYMS)),before)

    def test_missing_or_tampered_archived_bytes_fail_closed(self):
        archive_committed_segments(self.root,self.cold)
        target=next(self.cold.glob("*.gz"))
        raw=target.read_bytes()
        target.write_bytes(raw+b"corrupt")
        with self.assertRaises(ValueError):
            list(read_segments(self.root,SYMS))
        target.write_bytes(raw)
        target.unlink()
        with self.assertRaises(ValueError):
            list(read_segments(self.root,SYMS))

    def test_failed_write_preserves_hot_originals(self):
        before=list(read_segments(self.root,SYMS))
        with patch("nbot.v5.g4_archive_rollover._durable_publish",side_effect=OSError("SIMULATED_ENOSPC")):
            with self.assertRaisesRegex(OSError,"ENOSPC"):
                archive_committed_segments(self.root,self.cold)
        self.assertEqual(list(read_segments(self.root,SYMS)),before)

    def test_quota_rollover_continues_without_fixed_time_stop(self):
        source=SegmentedForwardSource(self.root,symbols=SYMS,max_pending_frames=32,
                                      max_pending_bytes=65536,max_disk_bytes=131072,
                                      rollover_destination=self.cold)
        for i in range(200,2000):
            source.ingest(route="public_bookticker",at_ms=NOW+i,
                          raw=quote(symbol=SYMS[i%50],at=NOW+i))
        source.flush()
        self.assertTrue(list(self.cold.glob("*.gz")))
        self.assertEqual(source.audit()["counts"]["FRAME"],2000)
