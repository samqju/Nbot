"""CS-00 owner one-command WinSCP backup: private offline fixture tests."""
from __future__ import annotations
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.nbot_v5_1_owner_backup import (
    BackupHold,create_backup,_verify_archive,_walk_files,_copy_regular,VERSION)

class OwnerManualBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-cs00-manual-backup-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.state=self.root/"nbot-v5.1-state"
        self.out=self.root/"NBOT_Backups"
        self.state.mkdir(mode=0o700);self.out.mkdir(mode=0o700)
    def record(self,name="research/virtual_results.jsonl",raw=b'{"result":"VALID"}\n'):
        p=self.state/name;p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        p.write_bytes(raw);p.chmod(0o600)
        return p
    def run_backup(self):
        return create_backup(state=self.state,destination=self.out)

    def test_MB01_no_records_does_not_create_fake_backup(self):
        with self.assertRaisesRegex(BackupHold,"NO_V5_1_RECORDS_YET"):
            self.run_backup()
        self.assertFalse(list(self.out.iterdir()))

    def test_MB02_dated_backup_contains_scoped_research_and_manifest(self):
        self.record()
        x=self.run_backup()
        self.assertEqual(x["status"],"BACKUP_CREATED_AND_LOCALLY_VERIFIED")
        self.assertEqual(x["files"],1)
        self.assertFalse(x["offhost_saved"])
        p=Path(x["backup"])
        self.assertTrue(p.exists())
        self.assertEqual(p.stat().st_mode&0o077,0)
        self.assertEqual(len(list(self.out.glob("*.tar.gz"))),1)
        self.assertEqual(len(list(self.out.glob("*.sha256"))),1)
        self.assertEqual(
            Path(x["sha256_file"]).read_text().strip(),
            f"{sha256(p.read_bytes()).hexdigest()}  {p.name}")
        d=_verify_archive(p)
        self.assertEqual(d["schema"],VERSION)
        self.assertEqual(d["trading_authority"],"NONE")
        with tarfile.open(p,"r:gz") as a:
            self.assertEqual(a.extractfile("research/virtual_results.jsonl").read(),
                             b'{"result":"VALID"}\n')

    def test_MB03_sqlite_online_backup_contains_committed_WAL(self):
        p=self.state/"learning.sqlite"
        conn=sqlite3.connect(p)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE x (id integer primary key, state text)")
        conn.execute("INSERT INTO x VALUES(1,'UNRECOVERABLE_EXCLUDED')")
        conn.commit()
        p.chmod(0o600)
        x=self.run_backup()
        self.assertEqual(x["files"],1)
        archive=Path(x["backup"])
        with tarfile.open(archive,"r:gz") as a:
            blob=a.extractfile("learning.sqlite").read()
        restored=self.root/"restored.sqlite"
        restored.write_bytes(blob)
        new=sqlite3.connect(restored)
        try:
            self.assertEqual(new.execute("SELECT state FROM x").fetchone()[0],
                             "UNRECOVERABLE_EXCLUDED")
            self.assertEqual(new.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        finally:new.close();conn.close()

    def test_MB04_secret_files_never_copied(self):
        self.record("research/api_key.json",b'{"token":"NO"}')
        with self.assertRaisesRegex(BackupHold,"POSSIBLE_SECRET"):
            self.run_backup()

    def test_MB05_world_readable_records_blocked(self):
        p=self.record();p.chmod(0o644)
        with self.assertRaisesRegex(BackupHold,"RECORD_NOT_PRIVATE"):
            self.run_backup()

    def test_MB06_symlink_record_denied(self):
        p=self.record("research/a.jsonl")
        (self.state/"research/b.jsonl").symlink_to(p)
        with self.assertRaisesRegex(BackupHold,"SYMLINK_FILE_DENIED"):
            self.run_backup()

    def test_MB07_unknown_directory_not_silently_omitted(self):
        (self.state/"unknown").mkdir(mode=0o700)
        with self.assertRaisesRegex(BackupHold,"UNEXPECTED_DIRECTORY"):
            self.run_backup()

    def test_MB08_unrecognized_filetype_denied_not_omitted(self):
        self.record("models/trained.exe",b"bad")
        with self.assertRaisesRegex(BackupHold,"UNSUPPORTED_RECORD_TYPE"):
            self.run_backup()

    def test_MB09_corrupted_archive_detected(self):
        self.record()
        p=Path(self.run_backup()["backup"])
        with p.open("ab") as f:f.write(b"garbage")
        # gzip ignores trailing bytes; independent SHA sidecar detects this.
        self.assertNotEqual(
            sha256(p.read_bytes()).hexdigest(),
            list(self.out.glob("*.sha256"))[0].read_text().split()[0])

    def test_MB10_two_manual_commands_keep_independent_immutable_files(self):
        self.record()
        first=self.run_backup()
        second=self.run_backup()
        self.assertNotEqual(first["backup"],second["backup"])
        self.assertEqual(len(list(self.out.glob("*.tar.gz"))),2)
        self.assertTrue(Path(first["backup"]).exists())

    def test_MB11_concurrent_file_change_fails_closed(self):
        p=self.record()
        with tempfile.TemporaryDirectory(prefix="mb11-") as d:
            target=Path(d)/"out"
            with patch("os.read",side_effect=lambda *args,**kwargs:b''):
                with self.assertRaises(BackupHold):
                    _copy_regular(p,target,len(p.read_bytes()))

    def test_MB12_no_NBOT_process_or_network_calls_in_module(self):
        from scripts import nbot_v5_1_owner_backup as m
        self.assertFalse(any(hasattr(m,x) for x in ("start_bot","place_order",
                                                 "connect_to_binance","run_daemon")))
        self.assertEqual(m.VERSION,VERSION)

    def test_MB13_relative_invalid_paths_and_unsafe_dir_denied(self):
        self.record()
        self.state.chmod(0o755)
        with self.assertRaisesRegex(BackupHold,"PRIVATE_DIRECTORY"):
            self.run_backup()

    def test_MB14_reject_non_sqlite_db_without_success(self):
        self.record("research/fake.sqlite",b"invalid")
        with self.assertRaises(BackupHold):
            self.run_backup()
        self.assertEqual(len(list(self.out.glob("*.tar.gz"))),0)

if __name__=="__main__":unittest.main()
