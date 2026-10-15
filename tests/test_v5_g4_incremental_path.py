"""V4-style streaming G4 prices against independently SHA-chained originals.

Synthetic public WSS only. Never creates exchange orders or economic labels.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.g4_segmented_source import SegmentedForwardSource
from nbot.v5.g4_incremental_path import original_segment_price_path

T=1800000000000
SYMS=tuple(sorted(("BTCUSDT",)+tuple(f"C{i:02d}USDT" for i in range(49))))


def tick(sym, agg, time, price, first=None):
    first=500+3*(agg-100) if first is None else first
    return json.dumps({
        "stream":sym.lower()+"@aggTrade",
        "data":{"e":"aggTrade","E":time-30,"s":sym,"a":agg,
                "f":first,"l":first+2,"T":time-30,
                "p":str(price),"q":"1.0","m":False,"st":1}},
        separators=(",",":")).encode()


def policy(side="LONG"):
    return ({"decision_id":"a"*64,"status":"OBSERVED","symbol":"BTCUSDT",
             "side":side,"decision_at_ms":T+1000},
            {"policy_sha256":"b"*64,"horizon_ms":300000,
             "declared_at_ms":T-300000,
             "entry_reference_price":"100",
             "stop_price":"95" if side=="LONG" else "115",
             "target_price":"110" if side=="LONG" else "95"})


class IncrementalG4PathTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        os.chmod(self.root,0o700)
        self.vault=SegmentedForwardSource(
            self.root,symbols=SYMS,max_pending_frames=32,
            max_pending_bytes=65536,max_disk_bytes=10*1024*1024)
        self.vault.connect(route="market_aggtrade",at_ms=T+800)
        self.vault.ingest(route="market_aggtrade",at_ms=T+900,
                          raw=tick("BTCUSDT",100,T+900,100))

    def ingest(self,agg,time,price,first=None):
        self.vault.ingest(
            route="market_aggtrade",at_ms=time,
            raw=tick("BTCUSDT",agg,time,price,first=first))

    def replay(self,at,side="LONG"):
        self.vault.flush()
        cand,pol=policy(side)
        return original_segment_price_path(
            segment_dir=self.root,candidate=cand,policy=pol,audit_at_ms=at)

    def test_early_target_first_with_complete_original_agg_continuity(self):
        self.ingest(101,T+1200,100)
        self.ingest(102,T+1400,110)
        result=self.replay(T+1600)
        self.assertEqual(result.state,"PATH_REPLAYED")
        self.assertEqual(result.exit_reason,"TARGET_PRICE_CROSSED")
        self.assertEqual(result.gross_path_r,"2")
        self.assertIsNone(result.net_r)
        self.assertEqual(result.scored_outcomes,0)
        self.assertEqual(result.financial_authority,"NONE")
        self.assertEqual(result.path_trade_count,3)

    def test_stop_precedes_later_target(self):
        self.ingest(101,T+1200,95)
        self.ingest(102,T+1400,110)
        r=self.replay(T+2000)
        self.assertEqual(r.state,"PATH_REPLAYED")
        self.assertEqual(r.exit_reason,"STOP_PRICE_CROSSED")
        self.assertEqual(r.gross_path_r,"-1")

    def test_market_id_gap_never_scores(self):
        self.ingest(103,T+1200,110)
        result=self.replay(T+1500)
        self.assertEqual(result.state,"HOLD")
        self.assertTrue(result.reasons)

    def test_restart_before_target_cannot_promote_path(self):
        self.ingest(101,T+1200,105)
        self.vault.disconnect(route="market_aggtrade",at_ms=T+1300)
        self.vault.connect(route="market_aggtrade",at_ms=T+1400)
        self.ingest(102,T+1500,110)
        r=self.replay(T+1700)
        self.assertEqual(r.state,"HOLD")
        self.assertTrue(any("INTERRUPTED" in reason or "RESTART" in reason
                            for reason in r.reasons))

    def test_future_market_frame_not_visible_at_earlier_audit(self):
        self.ingest(101,T+1200,110)
        r=self.replay(T+1100)
        self.assertNotEqual(r.state,"PATH_REPLAYED")

    def test_horizon_requires_last_original_frame_after_horizon(self):
        self.ingest(101,T+1200,102)
        r=self.replay(T+301000)
        self.assertEqual(r.state,"HOLD")
        self.assertIn("G4_INCREMENTAL_FULL_HORIZON_NOT_PROVEN",r.reasons)
        self.ingest(102,T+301100,103)
        r=self.replay(T+301200)
        self.assertEqual(r.state,"PATH_REPLAYED")
        self.assertEqual(r.exit_reason,"HORIZON_LAST_TRADE")
        self.assertEqual(r.exit_trade_price,"102")

    def test_large_cross_coin_stream_keeps_no_trade_row_list(self):
        # 50-coin high-rate other-market traffic; BTC proof remains exact.
        others=tuple(s for s in SYMS if s!="BTCUSDT")
        for i in range(1750):
            sym=others[i%len(others)]
            agg=100+i//len(others)
            self.vault.ingest(route="market_aggtrade",
                              at_ms=T+1400+i,
                              raw=tick(sym,agg,T+1400+i,100))
        self.ingest(101,T+4000,110)
        r=self.replay(T+4200)
        self.assertEqual(r.state,"PATH_REPLAYED")
        self.assertEqual(r.path_trade_count,2)  # one BTC pre-decision + target
        self.assertFalse(list(self.root.glob("*.sqlite*")))

    def test_tampered_compressed_segment_refuses_wins(self):
        self.ingest(101,T+1200,110)
        self.vault.flush()
        item=next(self.root.glob("segment-*.gz"))
        item.write_bytes(item.read_bytes()+b"tamper")
        with self.assertRaisesRegex(ValueError,"G4_SEGMENT_"):
            self.replay(T+1600)

    def test_100_overlapping_paths_use_one_source_scan_and_match_individual(self):
        from dataclasses import asdict
        from unittest.mock import patch
        from nbot.v5 import g4_incremental_path as module
        self.ingest(101,T+1200,110)
        self.vault.flush()
        requests=[]
        for i in range(100):
            c,p=policy("LONG" if i%2 else "SHORT")
            c["decision_id"]=format(i,"064x")
            requests.append((c,p))
        reader=module.read_segments
        with patch.object(module,"read_segments",wraps=reader) as reads:
            results=module.original_segment_price_paths(
                segment_dir=self.root,requests=requests,audit_at_ms=T+1600)
        self.assertEqual(reads.call_count,1)
        self.assertEqual(len(results),100)
        for c,p in requests[:2]:
            single=module.original_segment_price_path(
                segment_dir=self.root,candidate=c,policy=p,audit_at_ms=T+1600)
            self.assertEqual(asdict(single),asdict(results[c["decision_id"]]))


if __name__=="__main__":
    unittest.main()
