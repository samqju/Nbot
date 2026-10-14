"""High-rate 50-market source invariants: no tick-to-SQL fanout.

All traffic is synthetic, public-format WSS. No live market requests or
services; never create persistent NBOT runtime files on either VPS.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from nbot.v5.candle_ledger import EvidenceHold
from nbot.v5.g1f_runner import MAX_DB_MIB, METRICS_EVERY_SECONDS, db_size_mib, resource_guard
from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.stream_buffer import BoundedObservationBuffer
from nbot.v5.ws_contract import UnsafeStream, decode_frame
from tests.test_v5_observation_continuity import quote, trade, RECEIVED


class FiftyCoinStorageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"bounded_g1.sqlite"
        self.symbols=("BTCUSDT",)+tuple(
            "M%02dUSDT" % i for i in range(49))

    def test_forty_thousand_ticks_make_zero_sqlite_writes(self):
        with ObservationContinuity(self.symbols,self.path) as session:
            session.connect("market")
            session.connect("public")
            before_changes=session.ledger.db.total_changes
            before_bytes=sum(
                f.stat().st_size for f in self.path.parent.glob("bounded_g1.sqlite*")
            )
            writes=[]
            session.ledger.db.set_trace_callback(
                lambda sql: writes.append(sql) if sql.lstrip().upper().startswith(
                    ("INSERT","REPLACE","UPDATE","DELETE","CREATE","DROP","ALTER")
                ) else None
            )
            for number in range(1,401):
                for symbol in self.symbols:
                    self.assertEqual(
                        session.consume("public",quote(symbol,update=number),
                                        received_ms=RECEIVED+number),
                        "QUOTE_LATEST_REPLACED")
                    self.assertEqual(
                        session.consume("market",trade(symbol,agg=number),
                                        received_ms=RECEIVED+number),
                        "TRADE_CURSOR_ADVANCED")
            session.ledger.db.set_trace_callback(None)
            after_bytes=sum(
                f.stat().st_size for f in self.path.parent.glob("bounded_g1.sqlite*")
            )
            self.assertEqual(writes,[])
            self.assertEqual(session.ledger.db.total_changes,before_changes)
            self.assertEqual(after_bytes,before_bytes)
            self.assertEqual(session.stats["trade_updates"],20000)
            self.assertEqual(session.stats["sampled_quote_updates"],20000)
            state=session.store.describe()
            self.assertEqual(state["symbol_count"],50)
            self.assertEqual(state["latest_quotes_retained"],50)
            self.assertEqual(state["latest_trades_retained"],50)
            self.assertEqual(state["total_candles_retained"],0)
            self.assertEqual(len(session.store.coins),50)

    def test_public_frames_are_decoded_once_not_twice(self):
        with ObservationContinuity(("BTCUSDT","ETHUSDT"),self.path) as session:
            session.connect("market")
            session.connect("public")
            with patch("nbot.v5.observation_continuity.decode_frame",
                       wraps=decode_frame) as original, patch(
                "nbot.v5.stream_buffer.decode_frame",
                side_effect=AssertionError("SECOND_JSON_PARSE_FORBIDDEN")
            ):
                session.consume("public",quote(),received_ms=RECEIVED)
                session.consume("market",trade(),received_ms=RECEIVED)
            self.assertEqual(original.call_count,2)

    def test_decoded_buffer_refuses_foreign_coin_route_and_type(self):
        store=BoundedObservationBuffer(("BTCUSDT","ETHUSDT"))
        store.connect("market")
        store.connect("public")
        for frame in (
            {"route":"market","kind":"aggTrade","symbol":"NOTSELECTEDUSDT"},
            {"route":"orders","kind":"aggTrade","symbol":"BTCUSDT"},
            {"route":"market","kind":"PRIVATE_ORDER","symbol":"BTCUSDT"},
        ):
            with self.subTest(frame=frame),self.assertRaises(UnsafeStream):
                store.consume_decoded(frame)

    def test_metric_journaling_is_at_most_one_heartbeat_per_minute(self):
        self.assertGreaterEqual(METRICS_EVERY_SECONDS,60)

    def test_sqlite_limit_counts_wal_and_shm_not_only_db(self):
        self.path.write_bytes(b"db")
        wal=Path(str(self.path)+"-wal")
        with wal.open("wb") as f:
            f.truncate((MAX_DB_MIB+1)*1024*1024)
        self.assertGreater(db_size_mib(self.path),MAX_DB_MIB)
        with self.assertRaisesRegex(EvidenceHold,"RESOURCE_LIMIT_EXCEEDED"):
            resource_guard(self.path)


if __name__=="__main__":
    unittest.main()
