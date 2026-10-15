"""G3 200-direction evidence receipt integrity, recovery and no trade authority."""
from __future__ import annotations
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot_v5_1.observation import ObservationBook
from nbot_v5_1.core import FiveMinuteEvent
from nbot_v5_1.exploration import explore_event, PATTERN_IDS
from nbot_v5_1.exploration_store import ExplorationStore, ExplorationStoreHold
from test_v5_1_g2 import manifest, history, END_OPEN, END_DECISION


class G3StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-g3-store-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.store=ExplorationStore(self.root)
        self.book=ObservationBook(manifest(12))
        for s in self.book.manifest.symbols:
            self.assertTrue(self.book.bootstrap(s,history(s),as_of_ms=END_DECISION))
        self.event=FiveMinuteEvent(END_OPEN,END_DECISION)

    def batch(self, limit=24):
        return explore_event(self.book,self.event,capacity_slots=1,evaluation_limit=limit)

    def test_P01_full_24x2_batch_durable_and_replay(self):
        b=self.batch()
        filename=self.store.append(b)
        self.assertEqual(self.store.append(b),filename)
        (recovered,)=self.store.replay()
        self.assertEqual(recovered,b.as_record())
        self.assertEqual(len(recovered["rows"]),24)
        self.assertTrue(all(len(row["patterns"])==len(PATTERN_IDS)
                            for row in recovered["rows"]))
        self.assertEqual((self.root/filename).stat().st_mode&0o777,0o600)

    def test_P02_conflicting_same_event_capacity_is_forbidden(self):
        self.store.append(self.batch(limit=3))
        with self.assertRaisesRegex(ExplorationStoreHold,"CONFLICTING_EVENT"):
            self.store.append(self.batch(limit=4))
        self.assertEqual(len(self.store.replay()),1)

    def test_P03_broken_compressed_record_blocks_all_replay(self):
        name=self.store.append(self.batch())
        (self.root/name).write_bytes(b"\x1f\x8bbroken")
        with self.assertRaises(ExplorationStoreHold):self.store.replay()
        with self.assertRaises(ExplorationStoreHold):self.store.append(self.batch())

    def test_P04_unauthorized_changed_200_side_state_detected(self):
        name=self.store.append(self.batch())
        path=self.root/name
        original=json.loads(gzip.decompress(path.read_bytes()))
        original["batch"]["rows"][0]["patterns"][PATTERN_IDS[0]]="MATCH"
        path.write_bytes(gzip.compress(json.dumps(original,sort_keys=True,
                      separators=(",",":")).encode(),mtime=0))
        with self.assertRaisesRegex(ExplorationStoreHold,"HASH_MISMATCH"):
            self.store.replay()

    def test_P05_cannot_change_authority_to_trade_even_with_new_hash(self):
        name=self.store.append(self.batch())
        path=self.root/name
        raw=json.loads(gzip.decompress(path.read_bytes()))
        raw["batch"]["rows"][0]["authority"]="LIVE"
        import hashlib
        raw["sha256"]=hashlib.sha256(json.dumps(raw["batch"],sort_keys=True,
                   separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
        path.write_bytes(gzip.compress(json.dumps(raw,sort_keys=True,
                   separators=(",",":")).encode(),mtime=0))
        with self.assertRaisesRegex(ExplorationStoreHold,"ORDER_AUTHORITY"):
            self.store.replay()

    def test_P06_permissions_and_orphans_are_not_silently_repaired(self):
        name=self.store.append(self.batch())
        path=self.root/name
        path.chmod(0o644)
        with self.assertRaises(ExplorationStoreHold):self.store.replay()
        path.chmod(0o600)
        (self.root/"orphan.tmp").write_text("partial")
        with self.assertRaises(ExplorationStoreHold):self.store.replay()
        self.assertTrue((self.root/"orphan.tmp").exists())

    def test_P07_world_writable_directory_and_missing_folder(self):
        self.root.chmod(0o777)
        try:
            with self.assertRaises(ExplorationStoreHold):self.store.append(self.batch())
        finally: self.root.chmod(0o700)
        missing=self.root/"missing"
        s=ExplorationStore(missing)
        with self.assertRaises(ExplorationStoreHold):s.append(self.batch())
        self.assertFalse(missing.exists())

    def test_P08_disk_budget_full_refuses_new_evidence(self):
        bounded=ExplorationStore(self.root,budget_bytes=1024*1024)
        first=bounded.append(self.batch())
        filler=self.root/("g3_"+"9"*16+"_"+"b"*64+".json.gz")
        with filler.open("wb") as handle:
            handle.write(b"X"*(1024*1024))
        with self.assertRaisesRegex(ExplorationStoreHold,"QUOTA_FULL"):
            bounded.append(self.batch())
        self.assertTrue((self.root/first).exists())

    def test_P09_failed_directory_fsync_retry_preserves_identical_receipt(self):
        true_sync, observed=os.fsync, []
        def error_first_dir(fd):
            mode=os.fstat(fd).st_mode
            import stat
            if stat.S_ISDIR(mode) and not observed:
                observed.append(True)
                raise OSError("simulated first directory sync failure")
            return true_sync(fd)
        b=self.batch()
        with patch("nbot_v5_1.exploration_store.os.fsync",side_effect=error_first_dir):
            with self.assertRaises(OSError):
                self.store.append(b)
        name=self.store.append(b)
        self.assertEqual(self.store.replay()[0],b.as_record())
        self.assertEqual(len(list(self.root.iterdir())),1)
        self.assertTrue((self.root/name).exists())

    def test_P10_constructor_does_not_create_any_file(self):
        path=self.root/"empty"
        s=ExplorationStore(path)
        self.assertFalse(path.exists())
        with self.assertRaises(ExplorationStoreHold):s.replay()
        self.assertFalse(path.exists())


if __name__ == "__main__":unittest.main()
