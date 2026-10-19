"""Fail-closed offline native +1 pp trailing A/B batch contracts."""
import pathlib,sys,unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import m2r_v6_exact_one_trail_batch as b

class ExactOneNativeBatchTests(unittest.TestCase):
    def test_exactly_original_eight_family_backtests(self):
        self.assertEqual(len(b.FAMILIES),8)
        self.assertEqual(len(set(b.FAMILIES)),8)
        self.assertEqual(b.BRANCH,"prototype/v6-freqtrade-freqai-20261016")
    def test_only_offline_and_no_time_exit(self):
        src=(ROOT/"scripts/m2r_v6_exact_one_trail_batch.py").read_text()
        for text in ("OWNER","OFFLINE_OWNER_OPTIN_REQUIRED","--enable-protections",
                     "not cmd(\"docker\",\"ps\",\"-q\")",
                     "--fee\",\"0.0005","--timerange\",\"20260701-20261001",
                     "REFUSE_RETRY_OR_OVERWRITE_PARTIAL",
                     "FROZEN_ENTRY_LIBRARY_CHANGED",
                     "OLD_TRAILING_NATIVE_ZIP_CHANGED"):
            self.assertIn(text,src)
        self.assertNotIn("v6_library_60m_exit\"\n",src)
    def test_fail_before_any_run_without_owner_flag(self):
        with patch.object(b.os,"geteuid",return_value=0),patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"OFFLINE_OWNER_OPTIN_REQUIRED"):
                b.preflight()
    def test_distinct_isolated_output(self):
        self.assertNotEqual(b.OUTPUT,b.OLD)
        self.assertTrue(str(b.OUTPUT).endswith("exact-one-trailing-20261019"))
if __name__=="__main__":unittest.main()
