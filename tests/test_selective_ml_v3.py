import json
import unittest

from nbot.observation.selective_ml_v3 import _groups
from nbot.observation.selective_ml import SelectiveMLConfig


class _Memory:
    def iter_training_rows(self):
        rows = [
            (100, {"symbol":"AAAUSDT","side":"LONG","feature_vector_json":json.dumps({"x":1}),"target_net_r":99}),
            (100, {"symbol":"BBBUSDT","side":"SHORT","feature_vector_json":json.dumps({"x":2}),"target_net_r":99}),
            (200, {"symbol":"AAAUSDT","side":"LONG","feature_vector_json":json.dumps({"x":3}),"target_net_r":99}),
        ]
        yield from rows


class _Ledger:
    def training_targets(self):
        return {
            (100,"AAAUSDT","LONG"):{"feature_vector":{"x":1},"target_net_r":0.5},
            (200,"AAAUSDT","LONG"):{"feature_vector":{"x":3},"target_net_r":-0.25},
        }


class SelectiveMLV3TargetTests(unittest.TestCase):
    def test_groups_use_only_resolved_high_resolution_targets(self):
        cfg = SelectiveMLConfig(max_events=600,max_rows=60000)
        groups = _groups(_Memory(), _Ledger(), cfg)
        self.assertEqual([g[0] for g in groups],[100,200])
        self.assertEqual(groups[0][1][0]["target_net_r"],.5)
        self.assertEqual(groups[1][1][0]["target_net_r"],-.25)
        self.assertEqual(sum(len(r) for _,r in groups),2)

    def test_feature_mismatch_is_excluded_not_silently_relabelled(self):
        class BadLedger:
            def training_targets(self):
                return {(100,"AAAUSDT","LONG"):{"feature_vector":{"x":9},"target_net_r":1.0}}
        groups = _groups(_Memory(), BadLedger(), SelectiveMLConfig())
        self.assertEqual(groups,[])


if __name__ == "__main__":
    unittest.main()
