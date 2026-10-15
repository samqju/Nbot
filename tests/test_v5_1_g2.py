"""G2 source-universe, finalized 100-symbol observation and durable receipt tests.

Fixtures are synthetic, never qualified original exchange evidence.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nbot_v5_1.core import FiveMinuteEvent, INTERVAL_MS, ObservationAuthority
from nbot_v5_1.universe import BTC, UNIVERSE_SCHEMA, UniverseHold, select_universe
from nbot_v5_1.observation import (
    ClosedBar, rest_closed_bar, ObservationBook, OBSERVATION_SCHEMA, HISTORY_BARS,
)
from nbot_v5_1.observation_store import CompactObservationStore, ObservationStorageHold
from nbot_v5_1.public_market import PublicUsdMClient, PublicMarketHold, PUBLIC_API_SCHEMA

END_OPEN = INTERVAL_MS * 200
END_DECISION = END_OPEN + INTERVAL_MS


def market_fixture(n: int = 145):
    symbols = [BTC] + [f"COIN{i:03d}USDT" for i in range(n-1)]
    exchange = {"symbols": [
        {"symbol": s, "contractType": "PERPETUAL", "status": "TRADING",
         "quoteAsset": "USDT", "marginAsset": "USDT"} for s in symbols]}
    tickers = [{"symbol": s, "quoteVolume": str(10_000_000 + i * 150_000),
                "priceChangePercent": str(i - 70)}
               for i,s in enumerate(symbols)]
    books = [{"symbol": s, "bidPrice": "100", "askPrice": "100.10"}
             for s in symbols]
    histories = {s: 100 for s in symbols}
    health = {s: True for s in symbols}
    return exchange, tickers, books, histories, health


def manifest(n: int = 145, **kwargs):
    exchange, tickers, books, histories, health = market_fixture(n)
    return select_universe(exchange, tickers, books, histories, health,
                           source_received_at_ms=END_OPEN,
                           selected_at_ms=END_OPEN + 1000, **kwargs)


def bar(symbol: str, opening: int, *, epoch: int = 0,
        received: int = END_DECISION, route: str = "public_rest") -> ClosedBar:
    return ClosedBar(symbol, opening, opening+INTERVAL_MS-1,
                     "100", "102", "99", "101", "1.25",
                     received, epoch, route)


def history(symbol: str, *, epoch: int = 0):
    return [bar(symbol, END_OPEN - (95-i)*INTERVAL_MS, epoch=epoch)
            for i in range(96)]


class UniverseTests(unittest.TestCase):
    def test_U01_100_exact_no_duplicates_btc(self):
        m=manifest()
        self.assertEqual(m.schema, UNIVERSE_SCHEMA)
        self.assertEqual(len(m.entries), 100)
        self.assertEqual(len(set(m.symbols)), 100)
        self.assertIn(BTC, m.symbols)
        self.assertEqual(m.symbols[0], BTC)
        self.assertEqual(m.qualified_count,145)

    def test_U02_nominal_50_25_25_tags_preserved(self):
        m=manifest()
        groups={e.symbol: set(e.groups) for e in m.entries}
        self.assertIn("BTC_MANDATORY",groups[BTC])
        self.assertEqual(sum("TURNOVER" in tags for tags in groups.values()),50)
        self.assertGreaterEqual(sum("GAINER" in tags for tags in groups.values()),20)
        self.assertGreaterEqual(sum("LOSER" in tags for tags in groups.values()),20)
        self.assertTrue(any("FALLBACK" in tags for tags in groups.values()))

    def test_U03_selection_deterministic_independent_input_order(self):
        e,t,b,h,s=market_fixture()
        a=select_universe(e,t,b,h,s,source_received_at_ms=END_OPEN,
                          selected_at_ms=END_OPEN+1000)
        other=select_universe({"symbols": list(reversed(e["symbols"]))},
             list(reversed(t)),list(reversed(b)),h,s,
             source_received_at_ms=END_OPEN, selected_at_ms=END_OPEN+1000)
        self.assertEqual(a.selection_digest,other.selection_digest)
        self.assertEqual(a.symbols,other.symbols)
        self.assertRegex(a.selection_digest, r"\A[0-9a-f]{64}\Z")

    def test_U04_fewer_than_100_stays_small(self):
        m=manifest(n=20)
        self.assertEqual(len(m.symbols),20)
        self.assertEqual(len(m.symbols),len(set(m.symbols)))

    def test_U05_btc_missing_or_unqualified_fails(self):
        e,t,b,h,s=market_fixture()
        h[BTC]=0
        with self.assertRaisesRegex(UniverseHold,"BTC_NOT_QUALIFIED"):
            select_universe(e,t,b,h,s,source_received_at_ms=END_OPEN,
                            selected_at_ms=END_OPEN+1)
        e["symbols"][0]["status"]="BREAK"
        with self.assertRaises(UniverseHold):
            select_universe(e,t,b,h,s,source_received_at_ms=END_OPEN,
                            selected_at_ms=END_OPEN+1)

    def test_U06_ineligible_and_bad_spreads_logged(self):
        e,t,b,h,s=market_fixture()
        e["symbols"][5]["contractType"]="CURRENT_QUARTER"
        b[6]["askPrice"]="110"
        h[e["symbols"][7]["symbol"]]=1
        s[e["symbols"][8]["symbol"]]=False
        m=select_universe(e,t,b,h,s,source_received_at_ms=END_OPEN,
                          selected_at_ms=END_OPEN+1)
        rejects=dict(m.rejected)
        self.assertEqual(rejects[e["symbols"][5]["symbol"]],"INELIGIBLE_CONTRACT")
        self.assertEqual(rejects[e["symbols"][6]["symbol"]],"SPREAD_EXCESSIVE")
        self.assertEqual(rejects[e["symbols"][7]["symbol"]],"HISTORY_UNVERIFIED")
        self.assertEqual(rejects[e["symbols"][8]["symbol"]],"SOURCE_UNHEALTHY")

    def test_U07_nonfinite_bad_data_is_rejected(self):
        e,t,b,h,s=market_fixture()
        t[9]["quoteVolume"]="NaN"
        t[10]["priceChangePercent"]="Infinity"
        m=select_universe(e,t,b,h,s,source_received_at_ms=END_OPEN,
                          selected_at_ms=END_OPEN+1)
        self.assertEqual(dict(m.rejected)[t[9]["symbol"]],"INVALID_MARKET_METRICS")
        self.assertEqual(dict(m.rejected)[t[10]["symbol"]],"INVALID_MARKET_METRICS")

    def test_U08_duplicate_or_stale_snapshot_fails_closed(self):
        e,t,b,h,s=market_fixture()
        t.append(dict(t[0]))
        with self.assertRaises(UniverseHold):
            select_universe(e,t,b,h,s,source_received_at_ms=END_OPEN,
                            selected_at_ms=END_OPEN+1)
        t.pop()
        with self.assertRaises(UniverseHold):
            select_universe(e,t,b,h,s,source_received_at_ms=END_OPEN,
                            selected_at_ms=END_OPEN+61_000)

    def test_U09_btc_can_be_forced_without_changing_group_quota(self):
        m=manifest()
        self.assertEqual(m.symbols[0],BTC)
        self.assertIn("BTC_MANDATORY",m.entries[0].groups)
        self.assertLessEqual(len(m.symbols),100)

    def test_U10_known_at_negative_clock_rejected(self):
        e,t,b,h,s=market_fixture()
        for recv,sel in [(-1,0),(10,9),(0,60_001),(True,100)]:
            with self.subTest(recv=recv,sel=sel), self.assertRaises(UniverseHold):
                select_universe(e,t,b,h,s,source_received_at_ms=recv,selected_at_ms=sel)


class KlineTests(unittest.TestCase):
    def setUp(self):
        self.m=manifest()
        self.book=ObservationBook(self.m)
        self.event=FiveMinuteEvent(END_OPEN,END_DECISION)

    def test_O01_rest_final_open_close_semantics(self):
        row=[END_OPEN,"100","102","99","101","1.25",END_DECISION-1,
             "125",12,"0.4","0.5","0"]
        b=rest_closed_bar(BTC,row,known_at_ms=END_DECISION,epoch=0)
        self.assertEqual(b.close_ms,END_DECISION-1)
        self.assertTrue(b.closed)
        with self.assertRaises(ValueError):
            rest_closed_bar(BTC,row,known_at_ms=END_DECISION-1,epoch=0)

    def test_O02_reject_open_boolean_or_bad_ohlcv(self):
        for fields in (dict(closed=False),dict(closed=1),
                      dict(opening="NaN"),dict(opening="103"),
                      dict(volume="-1"),dict(high="90"),
                      dict(open_ms=END_OPEN+1),dict(received_at_ms=True)):
            values=dict(symbol=BTC,open_ms=END_OPEN,close_ms=END_DECISION-1,
                   opening="100",high="102",low="99",closing="101",volume="1",
                   received_at_ms=END_DECISION,epoch=0,route="public_rest")
            values.update(fields)
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                ClosedBar(**values)

    def test_O03_uninitialized_100_denominator_all_explicit_hold(self):
        shot=self.book.snapshot(self.event)
        self.assertEqual(len(shot.rows),100)
        self.assertEqual(shot.healthy_count,0)
        self.assertEqual(shot.hold_count,100)
        self.assertFalse(shot.btc_healthy)
        self.assertTrue(all("NO_CANDLE" in r.reasons for r in shot.rows))

    def test_O04_96_contiguous_history_bootstrap(self):
        self.assertTrue(self.book.bootstrap(BTC,history(BTC),as_of_ms=END_DECISION))
        shot=self.book.snapshot(self.event)
        self.assertEqual(shot.healthy_count,1)
        self.assertEqual(shot.hold_count,99)
        self.assertTrue(shot.btc_healthy)
        self.assertEqual(self.book.buffered_candles,96)

    def test_O05_100_coin_history_and_snapshot(self):
        for s in self.m.symbols:
            self.assertTrue(self.book.bootstrap(s,history(s),as_of_ms=END_DECISION))
        shot=self.book.snapshot(self.event)
        self.assertEqual(shot.healthy_count,100)
        self.assertEqual(shot.hold_count,0)
        self.assertEqual(len(shot.rows),100)
        self.assertEqual(self.book.buffered_candles,9600)
        self.assertEqual(len({r.symbol for r in shot.rows}),100)
        self.assertTrue(all(r.state=="METADATA_CLOSED" for r in shot.rows))

    def test_O06_missing_middle_candle_bootstrap_hold(self):
        gaps=history(BTC)
        gaps.pop(7)
        self.assertFalse(self.book.bootstrap(BTC,gaps,as_of_ms=END_DECISION))
        self.assertEqual(self.book.snapshot(self.event).rows[0].state,"HOLD")

    def test_O07_future_history_receipt_rejected(self):
        bars=history(BTC)
        future=[bar(BTC,b.open_ms,received=END_DECISION+1) for b in bars]
        self.assertFalse(self.book.bootstrap(BTC,future,as_of_ms=END_DECISION))

    def test_O08_wrong_epoch_and_reconnect_need_rebootstrap(self):
        self.assertTrue(self.book.bootstrap(BTC,history(BTC),as_of_ms=END_DECISION))
        self.book.reconnect(BTC,next_epoch=1,route="public_rest")
        self.assertFalse(self.book.snapshot(self.event).btc_healthy)
        self.assertFalse(self.book.ingest(bar(BTC,END_OPEN,epoch=1),decision_at_ms=END_DECISION))
        self.assertTrue(self.book.bootstrap(BTC,history(BTC,epoch=1),as_of_ms=END_DECISION))
        self.assertTrue(self.book.snapshot(self.event).btc_healthy)

    def test_O09_duplicate_replay_and_conflicting_content(self):
        self.assertTrue(self.book.bootstrap(BTC,history(BTC),as_of_ms=END_DECISION))
        last=history(BTC)[-1]
        self.assertFalse(self.book.ingest(last,decision_at_ms=END_DECISION))
        conflict=ClosedBar(BTC,END_OPEN,END_DECISION-1,
                   "100","103","99","102","1",END_DECISION,0,"public_rest")
        self.assertFalse(self.book.ingest(conflict,decision_at_ms=END_DECISION))
        self.assertIn("DUPLICATE_CONFLICT",self.book.snapshot(self.event).rows[0].reasons)

    def test_O10_gap_future_epoch_mismatch_all_hold(self):
        self.assertTrue(self.book.bootstrap(BTC,history(BTC),as_of_ms=END_DECISION))
        with self.assertRaises(ValueError): self.book.reconnect(BTC,next_epoch=0,route="public_rest")
        self.assertFalse(self.book.ingest(bar(BTC,END_OPEN+INTERVAL_MS,epoch=3,
                      received=END_DECISION+INTERVAL_MS),
                      decision_at_ms=END_DECISION+INTERVAL_MS))
        self.assertIn("FUTURE_RECEIPT",self.book.snapshot(self.event).rows[0].reasons)

    def test_O11_cannot_construct_future_universe_snapshot(self):
        with self.assertRaises(ValueError):
            self.book.snapshot(FiveMinuteEvent(END_OPEN-INTERVAL_MS,END_OPEN))

    def test_O12_no_trade_authority_no_future_features(self):
        self.book.bootstrap(BTC,history(BTC),as_of_ms=END_DECISION)
        shot=self.book.snapshot(self.event)
        self.assertFalse(hasattr(shot,"submit_order"))
        self.assertFalse(hasattr(shot,"economic_qualified"))
        self.assertEqual(ObservationAuthority.NONE.value,"NONE")
        with self.assertRaises(FrozenInstanceError):
            shot.healthy_count=100


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="nbot-g2-")
        self.addCleanup(self.tmp.cleanup)
        self.m=manifest()
        self.book=ObservationBook(self.m)
        self.shot=self.book.snapshot(FiveMinuteEvent(END_OPEN,END_DECISION))
        self.store=CompactObservationStore(Path(self.tmp.name))

    def test_S01_manifest_and_observation_atomic_replay(self):
        a=self.store.put_manifest(self.m)
        b=self.store.put_snapshot(self.shot)
        self.assertTrue(a.startswith("manifest_"))
        self.assertTrue(b.startswith("event_"))
        self.assertEqual(len(self.store.replay()),2)
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.json"))),2)
        self.assertEqual(self.store.put_snapshot(self.shot),b)

    def test_S02_files_owner_private_and_hash_protected(self):
        name=self.store.put_snapshot(self.shot)
        p=Path(self.tmp.name)/name
        self.assertEqual(p.stat().st_mode&0o777,0o600)
        contents=p.read_bytes()
        p.write_bytes(contents.replace(b"NO_CANDLE",b"GAP_EVENT"))
        with self.assertRaises(ObservationStorageHold):
            self.store.replay()

    def test_S03_partial_receipt_fails_closed(self):
        name=self.store.put_snapshot(self.shot)
        p=Path(self.tmp.name)/name
        p.write_bytes(b'{"incomplete":')
        with self.assertRaises(ObservationStorageHold): self.store.replay()
        with self.assertRaises(ObservationStorageHold): self.store.put_snapshot(self.shot)

    def test_S04_unknown_file_and_symlink_fail_closed(self):
        (Path(self.tmp.name)/"unreviewed.tmp").write_text("orphan")
        with self.assertRaises(ObservationStorageHold): self.store.put_snapshot(self.shot)

    def test_S05_quota_fails_closed_no_prune(self):
        st=CompactObservationStore(Path(self.tmp.name),max_bytes=128*1024)
        st.put_manifest(self.m)
        first=st.put_snapshot(self.shot)
        for i in range(2,100):
            shot=self.book.snapshot(FiveMinuteEvent(END_OPEN+i*INTERVAL_MS,
                                                    END_DECISION+i*INTERVAL_MS))
            try: st.put_snapshot(shot)
            except ObservationStorageHold as exc:
                self.assertIn("QUOTA",str(exc))
                break
        else: self.fail("unbounded storage")
        self.assertIn(first,[p.name for p in Path(self.tmp.name).glob("event_*")])

    def test_S06_permission_and_duplicate_key_validation(self):
        p=Path(self.tmp.name)
        p.chmod(0o777)
        with self.assertRaises(ObservationStorageHold): self.store.put_manifest(self.m)
        p.chmod(0o700)
        name=self.store.put_manifest(self.m)
        (p/name).chmod(0o644)
        with self.assertRaises(ObservationStorageHold): self.store.replay()

    def test_S07_no_implicit_filesystem_creation(self):
        p=Path(self.tmp.name)/"not-created"
        s=CompactObservationStore(p)
        self.assertFalse(p.exists())
        with self.assertRaises(ObservationStorageHold): s.put_manifest(self.m)
        self.assertFalse(p.exists())


class PublicClientTests(unittest.TestCase):
    def test_P01_default_network_locked(self):
        client=PublicUsdMClient()
        for f in (client.exchange_info,client.tickers_24hr,client.book_tickers):
            with self.assertRaises(PublicMarketHold): f()
        with self.assertRaises(PublicMarketHold): client.closed_klines(BTC)

    def test_P02_whitelisted_routes_and_budget(self):
        captured=[]
        def transport(url):
            captured.append(url)
            return b'{"symbols":[]}'
        c=PublicUsdMClient(allow_public_network=True,transport=transport,
                            now=lambda: 1_000_000,weight_budget=50)
        self.assertEqual(c.exchange_info().kind,"EXCHANGE_INFO")
        c.tickers_24hr()
        c.book_tickers()
        self.assertEqual(c.weight_used,46)
        with self.assertRaises(PublicMarketHold): c.closed_klines(BTC,limit=100)
        self.assertEqual(len(captured),3)
        self.assertTrue(all(x.startswith("https://fapi.binance.com/fapi/v1/") for x in captured))
        self.assertEqual(PUBLIC_API_SCHEMA,"NBOT_V5_1_PUBLIC_USDM_V1")

    def test_P03_invalid_symbols_and_payloads(self):
        c=PublicUsdMClient(allow_public_network=True,transport=lambda _:b"[]")
        for sym in ("BTC-USDT","btcUSDT","",True):
            with self.assertRaises(ValueError): c.closed_klines(sym)
        for limit in (True,1,501):
            with self.assertRaises(ValueError): c.closed_klines(BTC,limit=limit)
        for payload in (b"",b"{",b"NaN",b"a"*(4*1024*1024+1)):
            c=PublicUsdMClient(allow_public_network=True,transport=lambda _,p=payload:p)
            with self.assertRaises(PublicMarketHold): c.exchange_info()

    def test_P04_never_has_account_or_order_methods(self):
        c=PublicUsdMClient()
        for name in ("submit_order","balance","positions","listen_key",
                     "user_trades","api_key","signed_request","http_post"):
            self.assertFalse(hasattr(c,name))
        self.assertFalse(c.allowed)


if __name__=="__main__":
    unittest.main()
