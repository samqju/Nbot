"""CS-00 command is NOT a market service. A startup flag is an error."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ENTRY=Path(__file__).resolve().parents[1]/"scripts"/"cs00_observation_entry.py"


class CS00CommandLockTests(unittest.TestCase):
    def run_cmd(self,*opts):
        return subprocess.run([sys.executable,"-B",str(ENTRY),*opts],
                  capture_output=True,text=True,timeout=20)

    def test_CMD01_default_exits_without_running_service(self):
        r=self.run_cmd()
        self.assertEqual(r.returncode,0,r.stderr)
        a=json.loads(r.stdout)
        self.assertEqual(a["state"],"STOPPED_OFFLINE_ONLY")
        self.assertFalse(a["production_start_authorized"])
        self.assertFalse(a["public_network_allowed"])
        self.assertEqual(a["order_authority"],"NONE")
        self.assertFalse(a["archive"]["actual_offhost_archival_verified"])

    def test_CMD02_no_public_market_enable_switch(self):
        r=self.run_cmd("--public-network")
        self.assertNotEqual(r.returncode,0)
        self.assertNotIn("passed",r.stdout)

    def test_CMD03_no_start_service_switch(self):
        self.assertNotEqual(self.run_cmd("--start").returncode,0)

    def test_CMD04_no_order_switch(self):
        self.assertNotEqual(self.run_cmd("--real").returncode,0)

    def test_CMD05_no_paper_or_testnet_switch(self):
        self.assertNotEqual(self.run_cmd("--paper").returncode,0)
        self.assertNotEqual(self.run_cmd("--testnet").returncode,0)

    def test_CMD06_no_unknown_flag_abbreviation(self):
        self.assertNotEqual(self.run_cmd("--off").returncode,0)

if __name__=="__main__":
    unittest.main()
