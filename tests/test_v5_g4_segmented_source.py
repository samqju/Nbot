"""G4 raw evidence RAM/checkpoint regression: no tick SQLite, no invented continuity.

Synthetic public-frame fixtures only. NEVER starts a trading or market service.
"""
import asyncio
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g4_segmented_source import SegmentedForwardSource, read_segments
from nbot.v5.g4_forward_capture_runner import run_bounded, main
from nbot.v5.g4_forward_stream_contract import forward_stream_endpoints
from tests.test_v5_g4_forward_vault import quote, trade, NOW
from tests.test_v5_g4_forward_capture_runner import MockConnector, cohort


SYMS=tuple(sorted(("BTCUSDT",)+tuple("COIN%02dUSDT"%i for i in range(49))))


class SegmentedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix="g4-forward-offline-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        os.chmod(self.root,0o700)
        self.archive=self.root/"segments"
        self.archive.mkdir(mode=0o700)

    def storage(self, **extra):
        kw={"symbols":SYMS,"max_pending_bytes":65536,
            "max_pending_frames":64,"max_disk_bytes":262144}
        kw.update(extra)
        return SegmentedForwardSource(self.archive,**kw)

    def test_lossless_fifty_coin_ram_1000_quotes_and_zero_tick_sql(self):
        v=self.storage(max_disk_bytes=1048576)
        v.connect(route="public_bookticker",at_ms=NOW-1000)
        originals=[]
        for i in range(1000):
            original=quote(symbol=SYMS[i%50],at=NOW+i)
            originals.append(original)
            v.ingest(route="public_bookticker",at_ms=NOW+i,raw=original)
            self.assertLessEqual(v.pending_bytes,65536)
            self.assertLessEqual(len(v.pending),64)
        v.flush()
        self.assertEqual(v.audit()["audit"],"PASS")
        persisted=[raw for r,raw in read_segments(self.archive,SYMS)
                   if r["kind"]=="FRAME"]
        self.assertEqual(originals,persisted)
        self.assertEqual(len(persisted),1000)
        self.assertGreater(v.segment_count,1)
        self.assertFalse(list(self.root.rglob("*.sqlite*")))
        self.assertEqual(v.audit()["economic_outcomes"],0)

    def test_abrupt_restart_admits_only_committed_prefix_and_marks_gap(self):
        v=self.storage()
        v.connect(route="market_aggtrade",at_ms=NOW-1000)
        committed=trade(symbol="BTCUSDT",at=NOW)
        v.ingest(route="market_aggtrade",at_ms=NOW,raw=committed)
        v.flush()
        dropped=trade(symbol="BTCUSDT",agg=101,first=503,last=504,at=NOW+1)
        v.ingest(route="market_aggtrade",at_ms=NOW+1,raw=dropped)
        self.assertEqual(len(v.pending),1)
        # Simulate hard crash: RAM never reaches stable storage.
        del v
        after=self.storage()
        self.assertEqual(after.audit()["counts"]["FRAME"],1)
        after.connect(route="market_aggtrade",at_ms=NOW+10000)
        after.flush()
        self.assertEqual(after.audit()["counts"]["ABRUPT_RESTART_HOLD"],1)
        rows=list(read_segments(self.archive,SYMS))
        self.assertNotIn(dropped,[raw for rec,raw in rows])
        self.assertTrue(any(rec["kind"]=="ABRUPT_RESTART_HOLD"
                            for rec,_ in rows))

    def test_tampered_compressed_segment_is_rejected(self):
        v=self.storage()
        v.connect(route="public_bookticker",at_ms=NOW-100)
        v.ingest(route="public_bookticker",at_ms=NOW,raw=quote(at=NOW))
        v.flush()
        p=next(self.archive.glob("segment-*.gz"))
        p.write_bytes(p.read_bytes()+b"x")
        with self.assertRaises(ValueError):
            list(read_segments(self.archive,SYMS))

    def test_orphan_unpaired_segment_stops_recovery(self):
        v=self.storage()
        v.connect(route="public_bookticker",at_ms=NOW-100)
        orphan=self.archive/"segment-00000002.gz"
        orphan.write_bytes(b"orphan")
        with self.assertRaisesRegex(ValueError,"G4_SEGMENT_ORPHAN"):
            self.storage()

    def test_private_root_and_cohort_mismatch_fail_closed(self):
        self.storage()
        with self.assertRaisesRegex(ValueError,"G4_SEGMENT_COHORT_CONFLICT"):
            SegmentedForwardSource(self.archive,symbols=("BTCUSDT","QNTUSDT"))
        os.chmod(self.archive,0o755)
        with self.assertRaisesRegex(ValueError,"G4_SEGMENT_ROOT_UNSAFE"):
            self.storage()

    def test_public_mock_runner_uses_compressed_only_and_never_fills(self):
        v=self.storage()
        conn=MockConnector()
        r=asyncio.run(run_bounded(
            vault=v,endpoints=forward_stream_endpoints(SYMS),
            connector=conn,duration_s=10,max_frames=3,
            max_db_mib=1,clock_ms=lambda:NOW))
        self.assertEqual(r["frames_seen"],3)
        self.assertEqual(r["stop_reason"],"MAX_FRAMES")
        self.assertEqual(r["counts"]["FRAME"],3)
        self.assertFalse(r["g4_scientific_accepted"])
        self.assertEqual(r["order_authority"],"NONE")
        self.assertEqual(r["audit"],"PASS")
        self.assertFalse(list(self.root.rglob("*.sqlite*")))

    def test_legacy_raw_sqlite_dry_run_is_not_activated(self):
        import json
        manifest=self.root/"g1_cohort.json"
        manifest.write_text(json.dumps(cohort()))
        from contextlib import redirect_stdout
        from io import StringIO
        output=StringIO()
        with redirect_stdout(output):
            rc=main(["--cohort-manifest",str(manifest),
                     "--source-root",str(self.root)])
        self.assertEqual(rc,0)
        data=json.loads(output.getvalue())
        self.assertEqual(data["storage_mode"],"segments")
        self.assertFalse(list(self.root.rglob("*.sqlite*")))


if __name__=="__main__":
    unittest.main()
