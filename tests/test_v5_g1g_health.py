"""G1g public/isolated read-only health check: fail on boot conflicts."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest

from nbot.v5.g1g_health import observe, HealthHold, LEGACY_UNITS, OLD_ENABLED_UNITS
from nbot.v5.observation_contract import INTERVAL_MS


class G1gHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"g1f.sqlite"
        self.event=INTERVAL_MS*1_000_000
        self.clock=self.event+INTERVAL_MS+5000
        self.legacy={s:"inactive" for s in LEGACY_UNITS}
        self.boot={s:"disabled" for s in OLD_ENABLED_UNITS}
        self.service_active="active"
        self.service_enabled="enabled"
        self.mem=45*1024*1024
        self.mem_max=200*1024*1024
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE g1f_event_manifest(event_open_ms INTEGER,state TEXT);
                CREATE TABLE g1f_candidate_events(status TEXT);
                CREATE TABLE g1f_universe_snapshots(symbols_json TEXT);
            """)
            db.execute("INSERT INTO g1f_universe_snapshots VALUES (?)",
                       (json.dumps(["BTCUSDT","ETHUSDT"]),))
            db.execute("INSERT INTO g1f_event_manifest VALUES (?,'OBSERVE_ONLY')",
                       (self.event,))
            db.executemany("INSERT INTO g1f_candidate_events VALUES (?)",
                           [("OBSERVED",)]*4)
            db.commit()

    def runner(self,args,**kw):
        self.assertEqual(args[0],"systemctl")
        if args[1]=="is-active":
            return SimpleNamespace(returncode=3,stdout=self.legacy[args[-1]]+"\n")
        if args[1]=="is-enabled":
            return SimpleNamespace(returncode=1,stdout=self.boot[args[-1]]+"\n")
        self.assertEqual(args[1],"show")
        key=args[3]
        mapping={
            "ActiveState":self.service_active,
            "UnitFileState":self.service_enabled,
            "MemoryMax":str(self.mem_max),
            "MemoryCurrent":str(self.mem),
        }
        return SimpleNamespace(returncode=0,stdout=mapping[key]+"\n")

    def snapshot(self):
        return observe(path=str(self.path),now_ms=self.clock,runner=self.runner)

    def test_healthy_boot_database_and_count_pass_without_authority(self):
        out=self.snapshot()
        self.assertEqual(out["status"],"PASS")
        self.assertEqual(out["event_count"],1)
        self.assertEqual(out["observed_directional_records"],4)
        self.assertEqual(out["unscorable_directional_records"],0)
        self.assertEqual(out["database_integrity"],"ok")
        self.assertEqual(out["order_authority"],"NONE")
        self.assertFalse(out["research_ready"])
        self.assertEqual(out["training_labels_created"],0)

    def test_any_legacy_running_or_enabled_holds(self):
        for unit in LEGACY_UNITS:
            with self.subTest(unit=unit):
                self.legacy[unit]="active"
                self.assertIn("LEGACY_NOT_INACTIVE_"+unit,self.snapshot()["reasons"])
                self.legacy[unit]="inactive"
        for unit in OLD_ENABLED_UNITS:
            with self.subTest(unit=unit):
                self.boot[unit]="enabled"
                self.assertIn("LEGACY_BOOT_ENABLED_"+unit,self.snapshot()["reasons"])
                self.boot[unit]="disabled"

    def test_stale_event_and_missing_observations_hold(self):
        self.clock+=21*60000
        self.assertIn("V5_LAST_EVENT_STALE",self.snapshot()["reasons"])
        self.clock=self.event+INTERVAL_MS+5000
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM g1f_candidate_events")
            db.commit()
        self.assertIn("V5_EVENT_DENOMINATOR_MISMATCH",self.snapshot()["reasons"])

    def test_v5_disabled_or_overmemory_hold(self):
        self.service_enabled="disabled"
        self.assertIn("V5_BOOT_NOT_ENABLED",self.snapshot()["reasons"])
        self.service_enabled="enabled"
        self.service_active="inactive"
        self.assertIn("V5_NOT_ACTIVE",self.snapshot()["reasons"])
        self.service_active="active"
        self.mem=220*1024*1024
        self.assertIn("V5_MEMORY_LIMIT_UNSAFE",self.snapshot()["reasons"])

    def test_missing_db_and_symlink_refused_without_touching_source(self):
        link=Path(self.tmp.name)/"shortcut.sqlite"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(HealthHold,"SYMLINK"):
            observe(path=str(link),now_ms=self.clock,runner=self.runner)
        with self.assertRaisesRegex(HealthHold,"MISSING"):
            observe(path=str(link)+".missing",now_ms=self.clock,
                    runner=self.runner)


if __name__=="__main__":
    unittest.main()
