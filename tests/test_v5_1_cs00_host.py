"""CS-00 non-invasive host monitor: no HTTP, service commands or writes."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot_v5_1.cs00_commissioning import CommissioningHold
from nbot_v5_1.cs00_host_monitor import (
    _available_memory_bytes, inspect_offline_host)


class CS00HostMonitorTests(unittest.TestCase):
    def test_HOST01_real_host_snapshot_never_authorizes_start(self):
        value=inspect_offline_host()
        self.assertGreater(value["cpu_logical"],0)
        self.assertGreater(value["mem_available_kib"],0)
        self.assertGreater(value["disk_available_mib"],0)
        self.assertFalse(value["nbot_services_modified_by_probe"])
        self.assertFalse(value["source_collector_started_by_probe"])
        self.assertFalse(value["actual_archive_provider_contacted"])
        self.assertEqual(value["trading_authority"],"NONE")
        self.assertTrue(value["commissioning_go"].startswith("HOLD"))

    def test_HOST02_missing_mem_available_fails_closed(self):
        with tempfile.TemporaryDirectory() as s:
            p=Path(s)/"bad"
            p.write_text("MemFree: 100 kB\n")
            with self.assertRaisesRegex(CommissioningHold,"MEM_AVAILABLE"):
                _available_memory_bytes(p)

    def test_HOST03_bad_resource_paths_refused(self):
        with tempfile.TemporaryDirectory() as s:
            path=Path(s)
            link=path/"ln"
            link.symlink_to("/tmp")
            with self.assertRaises(CommissioningHold):
                inspect_offline_host(disk_mount=link)
            with self.assertRaises(CommissioningHold):
                inspect_offline_host(disk_mount=Path("relative"))

    def test_HOST04_low_disk_or_mem_generates_hold(self):
        class FakeDisk:
            f_bavail=1
            f_frsize=4096
        with patch("nbot_v5_1.cs00_host_monitor.os.statvfs",return_value=FakeDisk()),\
             patch("nbot_v5_1.cs00_host_monitor._available_memory_bytes",return_value=4*1024*1024):
            a=inspect_offline_host()
        self.assertIn("FREE_DISK_RESERVE_HOLD",a["alerts"])
        self.assertIn("AVAILABLE_RAM_LOW_HOLD",a["alerts"])
        self.assertTrue(a["commissioning_go"].startswith("HOLD"))


if __name__=="__main__":
    unittest.main()
