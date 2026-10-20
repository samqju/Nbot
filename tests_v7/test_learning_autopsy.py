"""Fail-closed reproducibility and economic-score helpers for LEARN-3C."""
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from scripts.v7_three_coin_learning_audit import events, prediction_bins, asof_bucket, file_sha


class LearningAutopsyTests(unittest.TestCase):
    def test_hash_chain_catches_modified_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"events.jsonl"
            previous="0"*64
            records=[]
            for i in range(3):
                body={"sequence":i,"previous_sha256":previous,
                      "time_ms":i*300000,"event":"decision","reason":"BRAIN_ABSTAIN"}
                digest=sha256(json.dumps(body,sort_keys=True,separators=(",",":"),
                                         allow_nan=False).encode()).hexdigest()
                records.append({**body,"sha256":digest})
                previous=digest
            p.write_text("".join(json.dumps(x)+"\n" for x in records))
            self.assertEqual(len(list(events(p))),3)
            records[1]["reason"]="SELECTED"
            p.write_text("".join(json.dumps(x)+"\n" for x in records))
            with self.assertRaisesRegex(AssertionError,"BROKEN_EVENT_CHAIN_HASH"):
                list(events(p))

    def test_prediction_bands_do_not_count_negative_as_positive(self):
        records=[
            {"predicted_net":.00005,"actual_net":-.001,"net_usdt":-1},
            {"predicted_net":.0003,"actual_net":.002,"net_usdt":2},
            {"predicted_net":.0012,"actual_net":-.004,"net_usdt":-4},
        ]
        rows=prediction_bins(records)
        self.assertEqual(sum(r["trades"] for r in rows),3)
        self.assertEqual(round(sum(r["net_usdt"] for r in rows),2),-3)
        self.assertTrue(any(r["realized_positive_rate"]==0 for r in rows))

    def test_btc_entry_status_is_asof_binned(self):
        self.assertEqual(asof_bucket({"btc_r12":.006}),"BTC_UP_1H")
        self.assertEqual(asof_bucket({"btc_r12":-.006}),"BTC_DOWN_1H")
        self.assertEqual(asof_bucket({"btc_r12":.002}),"BTC_FLAT_1H")
        self.assertEqual(asof_bucket({}),"UNKNOWN")


if __name__=="__main__":
    unittest.main()
