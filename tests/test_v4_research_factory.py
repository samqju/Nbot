import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace

from nbot.observation.v4_research import (
    AUTHORITY, BATCH_SIZE, CAPACITY, ORDER_AUTHORITY,
    V4ResearchStore,
)
from nbot.observation.v4_generation import V4GenerationStore
from nbot.observation.live_two_tier import ResearchWssFeed
from nbot.observation.wss_market import WssMarketState
from nbot.observation.wss_transport import CombinedStreamRunner


class V4ResearchContractTests(unittest.TestCase):
    def test_fixed_capacity_and_batch_contract(self):
        self.assertEqual(CAPACITY,100)
        self.assertEqual(BATCH_SIZE,1000)
        self.assertEqual(ORDER_AUTHORITY,"NONE")
        self.assertIn("NO_EXECUTION",AUTHORITY)

    def test_batches_close_only_at_each_1000_resolved(self):
        with tempfile.TemporaryDirectory() as td:
            store=V4ResearchStore(Path(td)/"meta.db")
            self.assertEqual(store.close_ready_batches(999,now_ms=1),[])
            self.assertEqual(store.close_ready_batches(1000,now_ms=2),[1])
            self.assertEqual(store.close_ready_batches(1999,now_ms=3),[])
            self.assertEqual(store.close_ready_batches(2000,now_ms=4),[2])
            self.assertEqual(store.close_ready_batches(2500,now_ms=5),[])
            status=store.status()
            self.assertEqual([b["batch_no"] for b in status["batches"]],[1,2])

    def test_generation_state_starts_without_champion(self):
        with tempfile.TemporaryDirectory() as td:
            store=V4GenerationStore(Path(td)/"generations.db")
            self.assertEqual(store.state(),{
                "champion_generation":None,
                "challenger_generation":None,
            })
            store.set_state("challenger_generation",1)
            self.assertEqual(store.state()["challenger_generation"],1)

    def test_generation_artifact_digest_is_checked(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"generations.db"
            store=V4GenerationStore(path)
            generation=store.save_generation(
                batch_no=1,artifact={"x":1},training_rows=100,
                training_events=40,validation_events=10,
                validation_mean=.1,validation_positive=.6,
                qualification="BASELINE_READY",now_ms=1,
            )
            self.assertEqual(generation,1)
            self.assertEqual(store.generation(1)["artifact"],{"x":1})
            with sqlite3.connect(path) as conn:
                conn.execute("UPDATE generations SET artifact_json=? WHERE generation=1",
                             (json.dumps({"x":2}),))
            with self.assertRaisesRegex(ValueError,"ARTIFACT_CORRUPT"):
                store.generation(1)


class _ReplayRecorder:
    def __init__(self):
        self.invalidated = []

    def invalidate_paths(self, symbols):
        self.invalidated.append(tuple(symbols))


class _RuntimeRecorder:
    def __init__(self):
        self.replays = _ReplayRecorder()


class V4WssIsolationTests(unittest.TestCase):
    def test_book_ticker_disconnect_does_not_invalidate_research_paths(self):
        runtime = _RuntimeRecorder()
        feed = ResearchWssFeed(runtime)
        shard = SimpleNamespace(streams=("btcusdt@bookTicker",))
        feed._shard_event_sink(shard)("disconnected", ("BTCUSDT",))
        self.assertEqual(runtime.replays.invalidated, [])

    def test_agg_trade_disconnect_invalidates_only_that_shard(self):
        runtime = _RuntimeRecorder()
        feed = ResearchWssFeed(runtime)
        shard = SimpleNamespace(streams=("btcusdt@aggTrade", "ethusdt@aggTrade"))
        feed._shard_event_sink(shard)("disconnected", ("BTCUSDT", "ETHUSDT"))
        self.assertEqual(runtime.replays.invalidated, [("BTCUSDT", "ETHUSDT")])

    def test_reconnect_runner_labels_stream_type(self):
        state = WssMarketState(("BTCUSDT",))
        book = CombinedStreamRunner(
            url="wss://example/public?streams=btcusdt@bookTicker",
            state=state,
            symbols=("BTCUSDT",),
        )
        trades = CombinedStreamRunner(
            url="wss://example/market?streams=btcusdt@aggTrade",
            state=state,
            symbols=("BTCUSDT",),
        )
        self.assertEqual(book.stream_kind, "bookTicker")
        self.assertEqual(trades.stream_kind, "aggTrade")

    def test_symbol_local_market_gap_invalidates_only_symbol(self):
        runtime = _RuntimeRecorder()
        feed = ResearchWssFeed(runtime)
        feed._on_market_event(
            "market_data_gap",
            {"symbol": "ETHUSDT", "reason": "WSS_AGG_TRADE_OUT_OF_ORDER"},
        )
        self.assertEqual(runtime.replays.invalidated, [("ETHUSDT",)])
        self.assertEqual(feed.last_error, "WSS_AGG_TRADE_OUT_OF_ORDER:ETHUSDT")


if __name__=="__main__":
    unittest.main()
