"""G1f data freshness and staged as-of REST audit: no outside network."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nbot.v5.observation_continuity import ObservationContinuity
from nbot.v5.finality_quarantine import FinalityQuarantine
from nbot.v5.g1f_engine import audit_event, feed_holds
from nbot.v5.g1f_journal import CandidateJournal
from nbot.v5.observation_contract import INTERVAL_MS
from tests.test_v5_public_market import klines

EVENT=INTERVAL_MS*1_000_000
FINAL=EVENT+INTERVAL_MS
NOW=FINAL+INTERVAL_MS+1000
SYMBOLS=("BTCUSDT","ETHUSDT")


def depth(symbol):
    return json.dumps({
        "stream":symbol.lower()+"@depth5@500ms",
        "data":{"e":"depthUpdate","E":NOW-9,"s":symbol,
                "U":1,"u":2,"b":[["99.9","2"]],"a":[["100.1","3"]]},
    })


def trade(symbol):
    return json.dumps({
        "stream":symbol.lower()+"@aggTrade",
        "data":{"e":"aggTrade","E":NOW-9,"T":NOW-10,
                "s":symbol,"a":1,"p":"100","q":"1"},
    })


def final(symbol):
    return json.dumps({
        "stream":symbol.lower()+"@kline_5m",
        "data":{"e":"kline","E":NOW-100,"s":symbol,
                "k":{"t":FINAL,"T":FINAL+INTERVAL_MS-1,
                     "s":symbol,"i":"5m","x":True,"o":"100",
                     "h":"101","l":"99","c":"100","v":"10"}},
    })


def latest_rest(path,params=None):
    if path!="/fapi/v1/klines" or params["interval"]!="5m":
        raise AssertionError("Unexpected REST method/params")
    assert params["startTime"]==str(FINAL)
    assert params["endTime"]==str(FINAL+INTERVAL_MS-1)
    return [[FINAL,"100","101","99","100","10",FINAL+INTERVAL_MS-1]]


class G1fEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"test.sqlite"

    def create(self):
        session=ObservationContinuity(SYMBOLS,self.path)
        for sym in SYMBOLS:
            session.restore_rest(
                sym,klines(EVENT),event_open_ms=EVENT,
                observed_ms=EVENT+INTERVAL_MS+1000,
            )
        session.connect("market")
        session.connect("public")
        for sym in SYMBOLS:
            session.consume("market",final(sym),received_ms=NOW)
            session.consume("market",trade(sym),received_ms=NOW)
            session.consume("public",depth(sym),received_ms=NOW)
        journal=CandidateJournal(session.ledger.db)
        ident=journal.begin_cohort(SYMBOLS,selected_ms=EVENT,
                                  event_open_ms=EVENT)
        q=FinalityQuarantine(session.ledger.db)
        return session,journal,ident,q

    def audit(self,session,journal,ident,q, *, getter=latest_rest,
              interrupted=False):
        cursor=[NOW+100]
        def clock():
            cursor[0]+=1000
            return cursor[0]
        async def skip_sleep(_):
            return None
        return asyncio.run(audit_event(
            session,journal,q,symbols=SYMBOLS,
            cohort_digest=ident,event_open_ms=FINAL,
            getter=getter,sleep=skip_sleep,clock=clock,
            interrupted=interrupted,rest_delay_seconds=8,
        ))

    def test_closed_final_verified_but_small_cross_section_is_unscorable(self):
        s,j,ident,q=self.create()
        try:
            summary=self.audit(s,j,ident,q)
            self.assertEqual(summary["source_verified"],2)
            self.assertEqual(summary["health_held"],0)
            self.assertEqual(summary["observed"],0)
            self.assertEqual(summary["unscorable"],4)
            self.assertEqual(j.inspect()["candidate_rows"],4)
            self.assertFalse(summary["research_ready"])
            self.assertEqual(summary["order_authority"],"NONE")
        finally:
            s.close()

    def test_stale_btc_quote_blocks_every_coin(self):
        s,j,ident,q=self.create()
        try:
            stale=s.store.coins["BTCUSDT"].last_quote
            stale["received_ms"]=NOW-25000
            flags=feed_holds(s,SYMBOLS,event_open_ms=FINAL,measured_ms=NOW)
            self.assertIn("QUOTE_NOT_FRESH",flags["BTCUSDT"])
            summary=self.audit(s,j,ident,q)
            self.assertEqual(summary["observed"],0)
            self.assertEqual(summary["health_held"],1)
        finally:
            s.close()

    def test_missing_or_crossed_quotes_hold_source(self):
        s,j,ident,q=self.create()
        try:
            s.store.coins["ETHUSDT"].last_quote=None
            flags=feed_holds(s,SYMBOLS,event_open_ms=FINAL,measured_ms=NOW)
            self.assertIn("QUOTE_NOT_FRESH",flags["ETHUSDT"])
            s.store.coins["ETHUSDT"].last_quote={
                **s.store.coins["BTCUSDT"].last_quote,
                "bid":100.0,"ask":99.0,
            }
            flags=feed_holds(s,SYMBOLS,event_open_ms=FINAL,measured_ms=NOW)
            self.assertIn("QUOTE_SPREAD_UNSAFE",flags["ETHUSDT"])
        finally:
            s.close()

    def test_one_rest_mismatch_stays_quarantined_after_later_match(self):
        s,j,ident,q=self.create()
        calls={}
        def getter(path,params=None):
            sym=params["symbol"]
            calls[sym]=calls.get(sym,0)+1
            if sym=="ETHUSDT" and calls[sym]==1:
                return [[FINAL,"100","101","99","100.6","10.3",
                         FINAL+INTERVAL_MS-1]]
            return latest_rest(path,params)
        try:
            summary=self.audit(s,j,ident,q,getter=getter)
            self.assertEqual(summary["quarantined"],1)
            self.assertIn("WSS_REST_MISMATCH",q.reasons("ETHUSDT",FINAL))
            self.assertFalse(summary["research_ready"])
            self.assertEqual(summary["unscorable"],4)
        finally:
            s.close()

    def test_disconnect_cannot_become_healthy_from_rest_proof(self):
        s,j,ident,q=self.create()
        try:
            summary=self.audit(s,j,ident,q,interrupted=True)
            self.assertEqual(summary["health_held"],2)
            self.assertEqual(summary["observed"],0)
        finally:
            s.close()


if __name__=="__main__":
    unittest.main()
