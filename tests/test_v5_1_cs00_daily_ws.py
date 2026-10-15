"""CS-00 verified historical daily archive fallback and public WSS codec tests."""
from hashlib import sha256
import io
from pathlib import Path
import tempfile
import unittest
import zipfile

from nbot_v5_1.cs00_daily_archive import (
    archive_paths,replay_official_daily_zip,DailyArchiveHold)
from nbot_v5_1.cs00_history_recovery import HistoricalAggTradeRecovery
from nbot_v5_1.cs00_public_ws import PublicTlsSocket,PublicSocketHold
from nbot_v5_1.cs00_source_runtime import public_routes
from test_v5_1_cs00_history_recovery import T,SHA
from test_v5_1_cs00_runtime_work import SYMBOLS

DAY="2026-10-14"
SYMBOL="BTCUSDT"
HEADER="agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"

class DailyArchiveTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix="cs00-daily-archive-")
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        self.name=f"{SYMBOL}-aggTrades-{DAY}.zip"
        self.path=self.root/self.name
        self.now=T+50*3600*1000
        self.recovery=lambda:HistoricalAggTradeRecovery(
            experiment_id=SHA,symbol=SYMBOL,first_agg_id=10,last_agg_id=12,
            gap_start_ms=T,gap_end_ms=T+10000,now_ms=self.now,
            side="LONG",stop="99",target="102")

    def archive(self,*,invalid=False,extra=False):
        data=(HEADER+"10,100,1,10,10,%d,true\n"
             "11,98,1,11,11,%d,false\n"
             "12,103,1,12,12,%d,false\n")%(T+1000,T+2000,T+3000)
        if invalid:data=data.replace("11,98","13,98")
        with zipfile.ZipFile(self.path,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(self.name[:-4]+".csv",data)
            if extra:z.writestr("unsafe.txt","none")
        return (sha256(self.path.read_bytes()).hexdigest()+"  "+self.name+"\n").encode()

    def test_CSAR01_official_daily_path_correct_and_no_network(self):
        u,ck=archive_paths(SYMBOL,DAY)
        self.assertIn("/data/futures/um/daily/aggTrades/BTCUSDT/",u)
        self.assertTrue(ck.endswith(".zip.CHECKSUM"))
        with self.assertRaises(DailyArchiveHold):
            archive_paths("BTCUSDT/evil",DAY)

    def test_CSAR02_checksum_verifies_replays_trade_path_only(self):
        ck=self.archive()
        r=self.recovery()
        m=replay_official_daily_zip(zip_path=self.path,checksum_bytes=ck,
                 symbol=SYMBOL,day=DAY,recovery=r,received_at_ms=self.now)
        self.assertEqual(m["source_state"],"TRADE_PATH_RECOVERED_ONLY")
        self.assertFalse(m["qualified_quote_cost_or_paper"])
        self.assertEqual(r.proof().trade_count,3)
        self.assertEqual(r.traded_price_first_touch(
            side="LONG",stop="99",target="102").barrier,"STOP")

    def test_CSAR03_zip_checksum_mismatch_denied(self):
        ck=self.archive()
        with self.assertRaisesRegex(DailyArchiveHold,"CHECKSUM_MISMATCH"):
            replay_official_daily_zip(zip_path=self.path,
                checksum_bytes=b"0"*64+b"  "+self.name.encode(),
                symbol=SYMBOL,day=DAY,recovery=self.recovery(),
                received_at_ms=self.now)

    def test_CSAR04_invalid_aggregate_order_denied(self):
        ck=self.archive(invalid=True)
        with self.assertRaises(DailyArchiveHold):
            replay_official_daily_zip(zip_path=self.path,checksum_bytes=ck,
                symbol=SYMBOL,day=DAY,recovery=self.recovery(),received_at_ms=self.now)

    def test_CSAR05_extra_zip_members_denied(self):
        ck=self.archive(extra=True)
        with self.assertRaisesRegex(DailyArchiveHold,"UNSAFE_ZIP_LAYOUT"):
            replay_official_daily_zip(zip_path=self.path,checksum_bytes=ck,
                symbol=SYMBOL,day=DAY,recovery=self.recovery(),received_at_ms=self.now)

    def test_CSAR06_missing_data_cannot_be_marked_recovered(self):
        ck=self.archive()
        r=HistoricalAggTradeRecovery(experiment_id=SHA,symbol=SYMBOL,
               first_agg_id=10,last_agg_id=13,gap_start_ms=T,
               gap_end_ms=T+10000,now_ms=self.now,
               side="LONG",stop="99",target="102")
        with self.assertRaisesRegex(DailyArchiveHold,"NOT_FULLY_RECOVERED"):
            replay_official_daily_zip(zip_path=self.path,checksum_bytes=ck,
                symbol=SYMBOL,day=DAY,recovery=r,received_at_ms=self.now)


class _SocketFake:
    def __init__(self,payload):self.buffer=bytearray(payload);self.sent=[]
    def recv(self,n):
        b=self.buffer[:n];del self.buffer[:n];return bytes(b)
    def sendall(self,b):self.sent.append(b)
    def close(self):pass

def server_frame(opcode,payload=b"",fin=True):
    return bytes(((0x80 if fin else 0)|opcode,len(payload)))+payload

class PublicTransportCodec(unittest.TestCase):
    def sock(self,raw):
        x=PublicTlsSocket(public_routes(SYMBOLS)[0].uri)
        x.sock=_SocketFake(raw);x.closed=False
        return x
    def test_CSWS01_inbound_public_text(self):
        p=self.sock(server_frame(1,b'{"stream":"btcusdt@aggTrade"}'))
        self.assertIn(b"BTC",p.read_message().replace(b"btc",b"BTC"))
    def test_CSWS02_ping_pong_remains_masked(self):
        p=self.sock(server_frame(9,b"xy")+server_frame(1,b"ok"))
        self.assertEqual(p.read_message(),b"ok")
        self.assertEqual(p.sock.sent[0][0]&15,10)
        self.assertTrue(p.sock.sent[0][1]&0x80)
    def test_CSWS03_fragments_reassemble_bounded(self):
        p=self.sock(server_frame(1,b"hello",False)+server_frame(0,b"world"))
        self.assertEqual(p.read_message(),b"helloworld")
    def test_CSWS04_masked_server_or_close_requires_hold(self):
        for raw in (b"\x81\x81",server_frame(8,b"")):
            with self.subTest(raw=raw),self.assertRaises(PublicSocketHold):
                self.sock(raw).read_message()
    def test_CSWS05_unexpected_server_binaries_rejected(self):
        with self.assertRaises(PublicSocketHold):
            self.sock(server_frame(2,b"evil")).read_message()
    def test_CSWS06_truncated_payload_holds(self):
        with self.assertRaises(PublicSocketHold):
            self.sock(bytes((0x81,0x05))+b"hi").read_message()

if __name__=="__main__":unittest.main()
