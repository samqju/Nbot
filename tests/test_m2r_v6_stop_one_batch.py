"""Offline stop -1% controlled challenger: static safety/parameter proof."""
import ast
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import m2r_v6_stop_one_batch as batch

class OnePercentStopTests(unittest.TestCase):
    def test_exact_sixteen_native_jobs_unchanged_entries_and_continuous_dates(self):
        self.assertEqual(len(batch.TASKS),16)
        self.assertEqual(len(set(batch.TASKS)),16)
        self.assertEqual(set(p for fam,p in batch.TASKS),{"fixed","trailing"})
        self.assertEqual(len(set(f for f,p in batch.TASKS)),8)
        source=(ROOT/"scripts/m2r_v6_stop_one_batch.py").read_text()
        self.assertIn("20260701-20261001",source)
        self.assertIn("REFUSE_OVERWRITE_PREVIOUS_ATTEMPT",source)
        self.assertIn("FROZEN_ORIGINAL_ENTRIES_CHANGED",source)
        self.assertIn("EXPLICIT_OFFLINE_RESEARCH_AUTHORIZATION_REQUIRED",source)
        self.assertIn("--enable-protections",source)
        self.assertIn("no_live_paper_or_automatic_promotion",source)
    def test_only_change_is_tight_stop_and_inherit_original_no_time_exit(self):
        path=ROOT/"user_data/strategies/NbotV6StopOneResearch.py"
        tree=ast.parse(path.read_text())
        cls={x.name:x for x in tree.body if isinstance(x,ast.ClassDef)}
        self.assertEqual(len([x for x in cls if x.startswith("NbotV6")]),16)
        for name in ("_StopOneFixed","_StopOneTrailing"):
            c=cls[name]
            stop=[x.value for x in c.body if isinstance(x,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=="stoploss" for t in x.targets)]
            self.assertEqual(len(stop),1)
            self.assertEqual(ast.literal_eval(stop[0]),-.01)
        self.assertNotIn("custom_exit",path.read_text())
        self.assertNotIn("trailing_stop_positive",path.read_text())
        self.assertNotIn("minimal_roi",path.read_text())
    def test_fail_closed_without_owner_optin_on_nonroot_ci(self):
        with patch.object(batch.os,"geteuid",return_value=0), patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"EXPLICIT_OFFLINE_RESEARCH_AUTHORIZATION_REQUIRED"):
                batch.preflight()
        self.assertNotEqual(batch.OUTPUT,batch.BASE)
        self.assertEqual(batch.IMAGE,"freqtradeorg/freqtrade:stable_freqai")

if __name__=="__main__":unittest.main()
