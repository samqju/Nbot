"""Exact trailing threshold math; no Freqtrade model, orders or data."""
import ast
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]/"user_data/strategies/NbotV6ExactOneTrailResearch.py"
tree=ast.parse(P.read_text())
m=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="exact_trailing_stop_price")
fn=ast.Module(body=[m],type_ignores=[])
ns={}
exec(compile(fn,str(P),"exec"),ns)
stop=ns["exact_trailing_stop_price"]
class ExactOneStopTests(unittest.TestCase):
    def test_long_exact_percentage_points(self):
        for high,wanted in [(100,None),(100.5,None),(101,100),(101.5,100.5),
                            (102,101),(103,102),(104,103),(105,104)]:
            got=stop(100,high,False)
            if wanted is None:self.assertIsNone(got)
            else:self.assertAlmostEqual(got,wanted,places=9)
    def test_short_exact_percentage_points(self):
        for low,wanted in [(100,None),(99.5,None),(99,100),(98.5,99.5),
                           (98,99),(97,98),(96,97),(95,96)]:
            got=stop(100,low,True)
            if wanted is None:self.assertIsNone(got)
            else:self.assertAlmostEqual(got,wanted,places=9)
    def test_invalid_prices_not_activated(self):
        self.assertIsNone(stop(0,102,False))
        self.assertIsNone(stop(100,0,False))
    def test_only_original_entries_no_time_exit_and_native_roi(self):
        classes={x.name:x for x in tree.body if isinstance(x,ast.ClassDef)}
        self.assertEqual(len([k for k in classes if k.endswith("ExactOneTrailResearch")]),8)
        root=classes["_NbotV6Exact1PctActivation"]
        fields={target.id:ast.literal_eval(stmt.value)
            for stmt in root.body if isinstance(stmt,ast.Assign)
            for target in stmt.targets if isinstance(target,ast.Name)
            and target.id in {"stoploss","minimal_roi","trailing_stop","use_custom_stoploss"}}
        self.assertEqual(fields,{"stoploss":-.02,"minimal_roi":{"0":.05},
                                  "trailing_stop":False,"use_custom_stoploss":True})
        body=P.read_text()
        self.assertIn("from NbotV6NoTimeLimitResearch import _NoSixtyMinuteFixed",body)
        self.assertNotIn("def custom_exit",body)
    def test_callback_calls_absolute_stop_helper_and_preserves_none_until_arm(self):
        c=next(x for x in tree.body if isinstance(x,ast.ClassDef)
               and x.name=="_NbotV6Exact1PctActivation")
        method=next(x for x in c.body if isinstance(x,ast.FunctionDef)
                    and x.name=="custom_stoploss")
        calls=[x.func.id for x in ast.walk(method)
               if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)]
        self.assertIn("exact_trailing_stop_price",calls)
        self.assertIn("stoploss_from_absolute",calls)
if __name__=="__main__":unittest.main()
