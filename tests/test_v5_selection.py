"""V5 directional qualification and read-only market adapter fixtures."""
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from nbot.observation.v5_selection import (
    Bar, DepthSnapshot, Instrument, Observation, SelectionPolicy, evaluate, plan_event,
    CAPACITY, VERSION, submit_order,
)
from nbot.observation.v5_market_reader import read_completed_event

EVENT = 18_000_000
NOW = EVENT + 300_000 + 10_000


def observations(kind="breakout", *, symbol="BTCUSDT", meta=True, cost_ok=True):
    # 49 contiguous completed 5-minute candles. Last candle has deliberate
    # directional information; no candle beyond EVENT is available.
    bars = []
    for i in range(49):
        level = 90.0 + 0.08 * i
        if kind == "range":
            level = 100 + (0.15 if i % 2 else -0.15)
        if kind == "flat":
            level = 100
        high, low, close, op = level + .8, level - .8, level + .2, level
        volume = 1_000_000.0
        if i == 48:
            if kind == "breakout":
                op,close,high,low,volume = 94,98.5,99,93.5,2_000_000
            elif kind == "downbreak":
                op,close,high,low,volume = 89,84.0,89.5,83.5,2_000_000
            elif kind == "range":
                op,close,high,low,volume = 99.8,100.5,100.7,99.0,2_000_000
            elif kind == "flat":
                op,close,high,low,volume = 100,100,100.05,99.95,1_000_000
        bars.append(Bar(EVENT-(48-i)*300_000,op,high,low,close,volume))
    price = 98.5 if kind == "breakout" else 84.0 if kind == "downbreak" else 100.5 if kind == "range" else 100
    bid=price - (.015 if cost_ok else .4)
    inst = Instrument(symbol,0.01,0.001,5.0,True, NOW-1_000,
                      0.001,100.0,"a"*64) if meta else None
    depth = DepthSnapshot(symbol,NOW-2_500,NOW-1_500,1234,
                          ((bid,10.0),),((price,10.0),),"b"*64) if meta else None
    return Observation(symbol,EVENT,EVENT+300_000-1,NOW-3_000,
                       bid,price,12_000_000,0.0001,1,tuple(bars),True,inst,depth)


class V5DirectionalSelectionTests(unittest.TestCase):
    def test_breakout_long_selected_not_automatic_short(self):
        market=observations()
        long=evaluate(market,"LONG",now_ms=NOW)
        short=evaluate(market,"SHORT",now_ms=NOW)
        self.assertTrue(long.qualified, long.reason)
        self.assertEqual(long.setup,"LEVEL_BREAKOUT_V1")
        self.assertFalse(short.qualified)
        self.assertIn("NO_CONFIRMED_DIRECTIONAL_SETUP",short.reason)
        plan=plan_event((market,),event_open_ms=EVENT,now_ms=NOW)
        self.assertEqual(plan.policy,VERSION)
        self.assertEqual([x.side for x in plan.selected],["LONG"])
        self.assertEqual(len(plan.exploratory),0)
        self.assertEqual(plan.order_authority,"NONE")
        self.assertFalse(plan.abstained)

    def test_no_setups_causes_abstention_without_filling_hundred(self):
        market=observations(kind="flat")
        result=plan_event((market,),event_open_ms=EVENT,now_ms=NOW)
        self.assertTrue(result.abstained)
        self.assertEqual(result.selected,())
        self.assertEqual(result.exploratory,())
        self.assertEqual(len(result.records),2)
        self.assertTrue(all(not row.qualified for row in result.records))
        self.assertEqual(CAPACITY,100)

    def test_side_specific_down_breakout(self):
        market=observations("downbreak")
        result=plan_event((market,),event_open_ms=EVENT,now_ms=NOW)
        self.assertEqual([x.side for x in result.selected],["SHORT"])

    def test_missing_metadata_stale_snapshot_or_future_candle_fails_closed(self):
        market=observations(meta=False)
        res=evaluate(market,"LONG",now_ms=NOW)
        self.assertIn("INSTRUMENT_RULES_MISSING",res.reason)
        self.assertFalse(res.exploration_eligible)
        from dataclasses import replace
        missing_depth=replace(observations(),depth=None)
        self.assertIn("DEPTH_MISSING",evaluate(missing_depth,"LONG",now_ms=NOW).reason)
        from dataclasses import replace
        old=replace(observations(),captured_at_ms=NOW+1)
        self.assertIn("SNAPSHOT_STALE",evaluate(old,"LONG",now_ms=NOW).reason)
        b=list(observations().bars)
        b[-1]=replace(b[-1],open_ms=EVENT+300_000)
        bad=replace(observations(),bars=tuple(b))
        self.assertIn("INVALID_4H_HISTORY",evaluate(bad,"LONG",now_ms=NOW).reason)
        self.assertEqual(evaluate(bad,"LONG",now_ms=NOW).sampling_probability,0)
        malformed=replace(observations(),bid=None)
        self.assertIn("INVALID_BID_ASK",evaluate(malformed,"LONG",now_ms=NOW).reason)
        self.assertFalse(evaluate(bad,"LONG",now_ms=NOW).qualified)

    def test_economics_and_future_metadata_rejected(self):
        from dataclasses import replace
        m=observations(cost_ok=False)
        self.assertIn("SPREAD_TOO_WIDE",evaluate(m,"LONG",now_ms=NOW).reason)
        # The wider spread is independently rejected by the depth-quote gate
        # before setup evaluation, rather than allowed to qualify.
        m=observations()
        stale=replace(m,instrument=replace(m.instrument,captured_at_ms=NOW+1))
        self.assertIn("INSTRUMENT_RULES_STALE",evaluate(stale,"LONG",now_ms=NOW).reason)
        zero_funding=replace(m,funding_rate=None)
        self.assertIn("FUNDING_SNAPSHOT",evaluate(zero_funding,"LONG",now_ms=NOW).reason)

    def test_depth_validation_rejects_stale_mismatched_and_thin_books(self):
        from dataclasses import replace
        m=observations()
        for replacement,expected in (
            (replace(m.depth,captured_at_ms=NOW+1),"DEPTH_STALE"),
            (replace(m.depth,bids=((m.bid-.1,10.0),)),"QUOTE_MISMATCH"),
            (replace(m.depth,asks=((m.ask,0.0001),)),"NOTIONAL_INSUFFICIENT"),
            (replace(m.depth,bids=((m.ask+.1,10.0),)),"DEPTH_CROSSED"),
            (replace(m.depth,update_id=0),"DEPTH_STALE"),
        ):
            bad=replace(m,depth=replacement)
            result=evaluate(bad,"LONG",now_ms=NOW)
            self.assertIn(expected,result.reason)
            self.assertFalse(result.qualified)
            self.assertFalse(result.exploration_eligible)

    def test_duplicate_active_and_capacity_are_not_refilled(self):
        m=observations()
        self.assertFalse(plan_event((m,),event_open_ms=EVENT,now_ms=NOW,
                                    active_pairs={("BTCUSDT","LONG")},active_count=1).selected)
        self.assertFalse(plan_event((m,),event_open_ms=EVENT,now_ms=NOW,
                                    active_count=100).selected)
        with self.assertRaisesRegex(ValueError,"ACTIVE_CAPACITY"):
            plan_event((m,),event_open_ms=EVENT,now_ms=NOW,active_count=101)
        with self.assertRaisesRegex(ValueError,"UNIVERSE_DUPLICATE"):
            plan_event((m,m),event_open_ms=EVENT,now_ms=NOW)

    def test_deterministic_exploration_never_invents_qualified_entry(self):
        from dataclasses import replace
        obs=[]
        for k in range(15):
            m=observations(kind="breakout",symbol=f"X{k}USDT")
            # Marginal directional candle: one of our recorded near misses.
            b=list(m.bars)
            b[-1]=replace(b[-1],open=95,close=96.4,high=96.5,low=94.8,
                          quote_volume=1_000_000)
            obs.append(replace(m,bars=tuple(b),ask=96.4,bid=96.38,
                               depth=replace(m.depth,bids=((96.38,10.0),),
                                             asks=((96.4,10.0),)),
                               selection_rank=k))
        a=plan_event(obs,event_open_ms=EVENT,now_ms=NOW)
        b=plan_event(list(reversed(obs)),event_open_ms=EVENT,now_ms=NOW)
        self.assertEqual(a,b)
        self.assertLessEqual(len(a.exploratory),4)
        self.assertEqual(len(a.selected),0)
        self.assertTrue(all(e.status=="EXPLORATORY" and e.sampling_probability>0
                            and not e.qualified for e in a.exploratory))
        eligible_by_side={side:sum(r.exploration_eligible for r in a.records if r.side==side)
                          for side in ("LONG","SHORT")}
        selected_by_side={side:sum(r.side==side for r in a.exploratory)
                          for side in ("LONG","SHORT")}
        for item in a.exploratory:
            self.assertAlmostEqual(item.sampling_probability,
                                   selected_by_side[item.side]/eligible_by_side[item.side])
        with self.assertRaisesRegex(RuntimeError,"NO_ORDER_AUTHORITY"):
            submit_order()


class V5ReadOnlyEvidenceTests(unittest.TestCase):
    def test_reader_only_complete_provenance_and_untouched_database(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"observer.db"
            m=observations()
            with closing(sqlite3.connect(p)) as db, db:
                db.executescript("""
                    CREATE TABLE market_events(event_open_ms INTEGER,event_close_ms INTEGER,
                      captured_at_ms INTEGER,status TEXT);
                    CREATE TABLE event_provenance(event_open_ms INTEGER,evidence_mode TEXT,
                      context_complete INTEGER,membership_quality TEXT);
                    CREATE TABLE market_snapshots(event_open_ms INTEGER,symbol TEXT,
                      bid_price REAL,ask_price REAL,quote_volume_24h_usd REAL,
                      funding_rate REAL,universe_rank INTEGER,captured_at_ms INTEGER);
                    CREATE TABLE universe_membership(event_open_ms INTEGER,symbol TEXT,
                      membership_quality TEXT);
                    CREATE TABLE candles_5m(event_open_ms INTEGER,symbol TEXT,open_price REAL,
                      high_price REAL,low_price REAL,close_price REAL,quote_volume REAL);
                """)
                db.execute("INSERT INTO market_events VALUES (?,?,?,?)",
                           (EVENT,EVENT+299999,NOW-3000,"COMPLETE"))
                db.execute("INSERT INTO event_provenance VALUES (?,?,?,?)",
                           (EVENT,"LIVE_POINT_IN_TIME",1,"POINT_IN_TIME"))
                db.execute("INSERT INTO market_snapshots VALUES (?,?,?,?,?,?,?,?)",
                           (EVENT,m.symbol,m.bid,m.ask,m.quote_volume_24h_usd,
                            m.funding_rate,m.selection_rank,m.captured_at_ms))
                db.execute("INSERT INTO universe_membership VALUES (?,?,?)",
                           (EVENT,m.symbol,"POINT_IN_TIME"))
                db.executemany("INSERT INTO candles_5m VALUES (?,?,?,?,?,?,?)",
                               [(b.open_ms,m.symbol,b.open,b.high,b.low,b.close,b.quote_volume)
                                for b in m.bars])
            before=p.read_bytes()
            result=read_completed_event(p,event_open_ms=EVENT,now_ms=NOW,
                                        instruments={m.symbol:m.instrument},
                                        depths={m.symbol:m.depth})
            self.assertEqual(result,(m,))
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual([r.side for r in plan_event(result,event_open_ms=EVENT,
                                                          now_ms=NOW).selected],["LONG"])
            with closing(sqlite3.connect(p)) as db, db:
                db.execute("UPDATE event_provenance SET context_complete=0")
            with self.assertRaisesRegex(ValueError,"PROVENANCE"):
                read_completed_event(p,event_open_ms=EVENT,now_ms=NOW)
            with closing(sqlite3.connect(p)) as db, db:
                db.execute("UPDATE event_provenance SET context_complete=1")
                db.execute("DELETE FROM universe_membership WHERE symbol=?", (m.symbol,))
            with self.assertRaisesRegex(ValueError,"UNIVERSE_INVALID"):
                read_completed_event(p,event_open_ms=EVENT,now_ms=NOW)


if __name__=="__main__":
    unittest.main()
