"""G4 authentic *public WSS local-source* validation and bounded custody.

These are synthetic raw combined frames; do not certify Binance origin,
independent exchange signature, settled funding, 20-stream endurance or
scientific after-cost labels.
"""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from nbot_v5_1.deep_source import stream_urls,verify_frame,DeepSourceHold
from nbot_v5_1.deep_segments import DeepSegmentRecorder,DeepSegmentHold

NOW=1792048000500
SYMBOLS=("BTCUSDT","ETHUSDT")

def frame(kind="TRADE",symbol="BTCUSDT",id=5,received=NOW):
    event=received-300
    rows={
      "TRADE":{"e":"aggTrade","E":event,"s":symbol,"a":id,"f":id*2,
               "l":id*2+1,"T":event,"p":"100.23","q":"0.25","m":False},
      "QUOTE":{"e":"bookTicker","E":event,"s":symbol,
               "b":"100.2","B":"2","a":"100.4","A":"3"},
      "MARK":{"e":"markPriceUpdate","E":event,"s":symbol,
              "p":"100.35","i":"100.20","r":"0.0001","T":received+20000},
    }
    return json.dumps({"stream":symbol.lower()+"@"+{
        "TRADE":"aggTrade","QUOTE":"bookTicker","MARK":"markPrice@1s"}[kind],
        "data":rows[kind]},separators=(",",":")).encode()


class DeepSourceTests(unittest.TestCase):
    def test_F01_routes_are_whitelisted_public_and_market_only(self):
        names=("BTCUSDT",)+tuple(f"COIN{x:02d}USDT" for x in range(19))
        r=stream_urls(names)
        self.assertEqual(len(r),3)
        self.assertIn("/public/stream?streams=",r["QUOTE"])
        self.assertIn("/market/stream?streams=",r["TRADE"])
        self.assertIn("/market/stream?streams=",r["MARK"])
        self.assertFalse(any("/private/" in v or "apiKey" in v for v in r.values()))
        with self.assertRaises(DeepSourceHold):
            stream_urls(("ETHUSDT",))

    def test_F02_book_trade_mark_original_raw_identification(self):
        for kind in ("QUOTE","TRADE","MARK"):
            raw=frame(kind)
            e=verify_frame(kind=kind,raw=raw,received_at_ms=NOW,
                 source_epoch=1,selected_symbols=SYMBOLS)
            self.assertEqual(e.state,"RECEIVED_UNQUALIFIED_LOCAL_WSS")
            self.assertEqual(e.sha256,hashlib.sha256(raw).hexdigest())
            self.assertEqual(e.source_grade,"PUBLIC_TLS_WSS_LOCAL_RAW_NOT_EXCHANGE_SIGNED")
            self.assertEqual(e.order_authority,"NONE")
            self.assertEqual(e.qualified_outcomes,0)

    def test_F03_wrong_symbol_route_future_and_stale_fail_closed(self):
        self.assertEqual(verify_frame(kind="TRADE",raw=frame(symbol="XRPUSDT"),
            received_at_ms=NOW,source_epoch=1,selected_symbols=SYMBOLS).state,"HOLD")
        self.assertEqual(verify_frame(kind="QUOTE",raw=frame("TRADE"),
            received_at_ms=NOW,source_epoch=1,selected_symbols=SYMBOLS).state,"HOLD")
        self.assertEqual(verify_frame(kind="TRADE",raw=frame(received=NOW-8000),
            received_at_ms=NOW,source_epoch=1,selected_symbols=SYMBOLS).state,"HOLD")

    def test_F04_id_gaps_and_repeats_are_hold_not_hidden(self):
        a=verify_frame(kind="TRADE",raw=frame(id=6),received_at_ms=NOW,
                source_epoch=1,selected_symbols=SYMBOLS,
                prior_agg_id=5,prior_last_trade_id=11)
        self.assertEqual(a.state,"RECEIVED_UNQUALIFIED_LOCAL_WSS")
        for a_id in (5,7):
            e=verify_frame(kind="TRADE",raw=frame(id=a_id),
                 received_at_ms=NOW,source_epoch=1,selected_symbols=SYMBOLS,
                 prior_agg_id=5,prior_last_trade_id=11)
            self.assertEqual(e.state,"HOLD")
            self.assertIn("ID_",e.reason)

    def test_F05_invalid_private_route_and_malformed_byte_holds(self):
        with self.assertRaises(DeepSourceHold):verify_frame(
            kind="PRIVATE",raw=frame(),received_at_ms=NOW,
            source_epoch=1,selected_symbols=SYMBOLS)
        with self.assertRaises(DeepSourceHold):verify_frame(
            kind="TRADE",raw=b"not json",received_at_ms=NOW,
            source_epoch=1,selected_symbols=SYMBOLS)
        with self.assertRaises(DeepSourceHold):verify_frame(
            kind="TRADE",raw=frame(),received_at_ms=NOW,
            source_epoch=0,selected_symbols=SYMBOLS)


class DeepSegmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-g4-source-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rec=DeepSegmentRecorder(self.root,symbols=SYMBOLS)

    def test_A01_append_flush_verify_exact_public_frame_bytes(self):
        raw=frame()
        self.rec.append(kind="TRADE",raw=raw,received_at_ms=NOW,epoch=1)
        self.rec.append(kind="QUOTE",raw=frame("QUOTE"),received_at_ms=NOW,epoch=1)
        self.rec.append(kind="MARK",raw=frame("MARK"),received_at_ms=NOW,epoch=1)
        self.assertEqual(self.rec.flush(),"segment-00000001")
        replay,last,num=self.rec.replay()
        self.assertEqual(len(replay),3)
        self.assertEqual(num,1)
        self.assertEqual(replay[0][1],raw)
        self.assertEqual(last,self.rec.last_receipt)
        self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in self.root.iterdir()))

    def test_A02_two_segments_linked_and_recovered_new_epoch(self):
        self.rec.append(kind="TRADE",raw=frame(id=5),received_at_ms=NOW,epoch=1)
        self.rec.flush()
        self.rec.append(kind="TRADE",raw=frame(id=6),received_at_ms=NOW,epoch=1)
        self.rec.flush()
        rest=DeepSegmentRecorder(self.root,symbols=SYMBOLS)
        self.assertEqual(rest.attach(),2)
        self.assertEqual(rest.next_id,3)
        self.assertEqual(rest.epoch_holds,set(SYMBOLS))

    def test_A03_tampered_gzip_blocks_replay(self):
        self.rec.append(kind="TRADE",raw=frame(),received_at_ms=NOW,epoch=1)
        name=self.rec.flush()
        (self.root/(name+".gz")).write_bytes(b"\x1f\x8binvalid")
        with self.assertRaises(DeepSegmentHold):self.rec.replay()

    def test_A04_tampered_meta_blocks_replay(self):
        self.rec.append(kind="TRADE",raw=frame(),received_at_ms=NOW,epoch=1)
        name=self.rec.flush()
        path=self.root/(name+".json")
        meta=json.loads(path.read_bytes())
        meta["body_sha256"]="0"*64
        path.write_text(json.dumps(meta))
        with self.assertRaises(DeepSegmentHold):self.rec.replay()

    def test_A05_partial_file_restart_does_not_autorepair(self):
        (self.root/"segment-00000001.gz").write_bytes(b"partial")
        with self.assertRaises(DeepSegmentHold):self.rec.attach()
        self.assertTrue((self.root/"segment-00000001.gz").exists())

    def test_A06_no_writer_when_disk_full(self):
        self.rec.quota_bytes=1024*1024
        # Large legitimate declared fixture payload occupies the finite
        # allocation without spoofing a WSS trade.
        name="segment-00000001.gz"
        (self.root/name).write_bytes(b"a"*1024*1024)
        (self.root/name).chmod(0o600)
        self.rec.queue=[{"kind":"TRADE","raw_b64":"","raw_sha256":"0"*64,
                         "received_at_ms":NOW,"epoch":1}]
        self.rec.queued_bytes=1
        with self.assertRaises(DeepSegmentHold):self.rec.flush()

    def test_A07_owner_private_and_unknown_filename_fails(self):
        self.root.chmod(0o777)
        try:
            with self.assertRaises(DeepSegmentHold):self.rec.replay()
        finally:self.root.chmod(0o700)
        (self.root/"orphan.part").write_text("nothing")
        with self.assertRaises(DeepSegmentHold):self.rec.replay()

    def test_A08_no_silent_trade_gap(self):
        self.rec.append(kind="TRADE",raw=frame(id=5),received_at_ms=NOW,epoch=1)
        with self.assertRaises(DeepSegmentHold):
            self.rec.append(kind="TRADE",raw=frame(id=7),received_at_ms=NOW,epoch=1)
        self.assertIn("BTCUSDT",self.rec.epoch_holds)
        self.assertEqual(len(self.rec.queue),1)

    def test_A10_interleaved_two_coins_independent_trade_cursors(self):
        for id,sym in ((5,"BTCUSDT"),(50,"ETHUSDT"),
                       (6,"BTCUSDT"),(51,"ETHUSDT")):
            r=frame(symbol=sym,id=id)
            self.assertEqual(self.rec.append(kind="TRADE",raw=r,
                      received_at_ms=NOW,epoch=1).state,
                      "RECEIVED_UNQUALIFIED_LOCAL_WSS")
        self.rec.flush()
        messages,_,_=self.rec.replay()
        self.assertEqual(len(messages),4)
        self.assertEqual({x.symbol for x,_ in messages},set(SYMBOLS))

    def test_A11_interleaved_one_coin_sequence_gap_holds(self):
        self.rec.append(kind="TRADE",raw=frame(symbol="BTCUSDT",id=5),
                        received_at_ms=NOW,epoch=1)
        self.rec.append(kind="TRADE",raw=frame(symbol="ETHUSDT",id=50),
                        received_at_ms=NOW,epoch=1)
        with self.assertRaises(DeepSegmentHold):
            self.rec.append(kind="TRADE",raw=frame(symbol="BTCUSDT",id=7),
                            received_at_ms=NOW,epoch=1)
        self.assertIn("BTCUSDT",self.rec.epoch_holds)
        self.assertNotIn("ETHUSDT",self.rec.epoch_holds)

    def test_A12_underlying_id_gap_needs_review_not_false_ws_loss(self):
        first=frame(id=5)
        second=json.loads(frame(id=6))
        # AggTrade IDs 5->6 are complete; Binance may omit transaction
        # types from underlying trade IDs 12 and 13.
        second["data"]["f"]=14
        second["data"]["l"]=15
        second=json.dumps(second,separators=(",",":")).encode()
        self.rec.append(kind="TRADE",raw=first,received_at_ms=NOW,epoch=1)
        result=self.rec.append(kind="TRADE",raw=second,received_at_ms=NOW,epoch=1)
        self.assertEqual(result.agg_id,6)
        self.assertEqual(self.rec.underlying_id_gap_reviews,1)
        self.assertFalse(self.rec.epoch_holds)
        self.rec.flush()
        rows,old,num=self.rec.replay()
        self.assertEqual(len(rows),2)
        self.assertEqual(self.rec.last_replay_underlying_id_gap_reviews,1)

    def test_A13_underlying_trade_overlap_still_hard_hold(self):
        first=frame(id=5)
        second=json.loads(frame(id=6))
        second["data"]["f"]=11
        second["data"]["l"]=12
        second=json.dumps(second,separators=(",",":")).encode()
        self.rec.append(kind="TRADE",raw=first,received_at_ms=NOW,epoch=1)
        with self.assertRaisesRegex(DeepSegmentHold,"UNDERLYING_REORDER"):
            self.rec.append(kind="TRADE",raw=second,received_at_ms=NOW,epoch=1)

    def test_A09_constructor_no_file_side_effect(self):
        child=self.root/"missing"
        new=DeepSegmentRecorder(child,symbols=SYMBOLS)
        self.assertFalse(child.exists())
        with self.assertRaises(DeepSegmentHold):new.replay()
        self.assertFalse(child.exists())

if __name__=="__main__":unittest.main()
