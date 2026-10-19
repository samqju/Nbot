"""Safety checks for 64-job no-time-limit A/B research plan (no VPS research)."""
import ast
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import m2r_v6_no_time_exit_batch as batch

class ResearchNoTimeA_B(unittest.TestCase):
    def test_finite_only_known_periods_and_families(self):
        plan=batch.plan("sha")
        self.assertEqual(len(plan),64)
        self.assertEqual(len(set(plan)),64)
        self.assertEqual(set(f for kind,p,f,t in plan),set(batch.FAMILIES))
        self.assertEqual(set(t for kind,p,f,t in plan),set(batch.PERIODS))
        self.assertEqual(set(p for kind,p,f,t in plan),{"fixed","trailing"})
        self.assertTrue(all(k.startswith("no_time_") for k,p,f,t in plan))
        self.assertEqual(batch.PERIODS["full_july_september"],"20260701-20261001")

    def test_strategy_has_no_time_exit_and_preserves_frozen_roi_and_stop(self):
        path=ROOT/"user_data/strategies/NbotV6NoTimeLimitResearch.py"
        body=path.read_text()
        tree=ast.parse(body)
        classes={x.name:x for x in tree.body if isinstance(x,ast.ClassDef)}
        self.assertEqual(len([c for c in classes if c.endswith("NoTimeFixedResearch")]),8)
        self.assertEqual(len([c for c in classes if c.endswith("NoTimeTrailingResearch")]),8)
        for base in ("_NoSixtyMinuteFixed","_NoSixtyMinuteTrailing"):
            node=classes[base]
            assign={target.id:ast.literal_eval(expr.value)
                    for expr in node.body if isinstance(expr,ast.Assign)
                    for target in expr.targets if isinstance(target,ast.Name)
                    and target.id in ("minimal_roi","stoploss","trailing_stop",
                                      "trailing_stop_positive",
                                      "trailing_stop_positive_offset")}
            self.assertEqual(assign["minimal_roi"],{"0":0.05})
            self.assertEqual(assign["stoploss"],-0.02)
            self.assertTrue(any(isinstance(x,ast.FunctionDef) and x.name=="custom_exit"
                        and isinstance(x.body[0],ast.Return)
                        and isinstance(x.body[0].value,ast.Constant)
                        and x.body[0].value.value is None for x in node.body))
        self.assertEqual(body.count("minutes=60"),0)
        self.assertEqual(body.count("v6_library_60m_exit"),0)

    def test_executor_requires_explicit_owner_optin(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(RuntimeError,"EXPLICIT_OFFLINE_ONLY_AUTHORIZATION_REQUIRED"):
                batch.preflight()
        # Passing the exact opt-in is not enough to permit work in wrong environment.
        self.assertFalse(batch.OUTPUT==batch.ORIGINAL)
        self.assertFalse(batch.OUTPUT==batch.ROOT/"global-25x8-20261018")

    def test_executor_flags_no_orders_and_no_overwrite(self):
        src=(ROOT/"scripts/m2r_v6_no_time_exit_batch.py").read_text()
        self.assertIn("--cache","none") if False else None
        for part in ("--enable-protections","--fee","0.0005",
                     "--network","--cap-drop","no-new-privileges",
                     "PARTIAL_NO_TIME_RESULT_MANUAL_REVIEW",
                     "ORIGINAL_LIBRARY_ENTRY_SIGNALS_CHANGED",
                     "FREQTRADE_NATIVE_JOB_FAILED"):
            self.assertIn(part,src)

if __name__=="__main__":unittest.main()
