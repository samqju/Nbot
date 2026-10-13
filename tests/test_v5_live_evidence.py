"""Prospective quotes, recovery, crash consistency and settlement evidence."""
import asyncio
import gc
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from nbot.observation.v5_live_evidence import (
    LiveEvidenceBridge, JointExitLab, FUNDING_GRACE_MS, submit_order,
)
from nbot.observation.v5_live_transport import PublicRest, stream_urls, run_research_capture, run_session
from nbot.observation.v5_paired_exits import PairedEntry, HORIZON_MS
from nbot.observation.v5_foundation import V5EvidenceStore

T = 100_000
END = T + HORIZON_MS


def trade(a=10, t=T-100, price="100"):
    return {"e": "aggTrade", "s": "BTCUSDT", "E": t, "T": t,
            "a": a, "f": a*2, "l": a*2+1, "p": price, "q": "1", "m": False}


def depth(u=100, pu=99, t=T-100, bid="99.9", ask="100", U=None):
    return {"e": "depthUpdate", "s": "BTCUSDT", "E": t, "T": t,
            "U": u if U is None else U, "u": u, "pu": pu,
            "b": [[bid, "2"]], "a": [[ask, "2"]]}


def quote(u=101, t=T+100, bid="98.5", ask="98.6"):
    return {"e": "bookTicker", "s": "BTCUSDT", "E": t, "T": t,
            "u": u, "b": bid, "a": ask, "B": "2", "A": "2"}


def entry(side="LONG", decision="d1"):
    return PairedEntry(decision, "BTCUSDT", side, T, 99.9, 100., T-100,
                       2., 99. if side == "LONG" else 100.9, 10, T-100)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        # Preexisting mechanical exit/funding fixtures are sparse synthetic
        # four-hour paths: isolate their logic from the production watchdog.
        # The independent-audit tests below explicitly restore the strict
        # 30-second coverage rule and exercise source silence fail-closed.
        self._synthetic_silence = patch(
            "nbot.observation.v5_live_evidence.MAX_BOOKTICKER_SILENCE_MS",
            HORIZON_MS + 100_000)
        self._synthetic_silence.start()
        self.addCleanup(self._synthetic_silence.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/"v5"/"live.db"
        self.b = LiveEvidenceBridge(self.path, symbols=["BTCUSDT"], clock=lambda: 0)
        self.b.initialize()
        self.b.connected("BTCUSDT")
        self.b.ingest(trade(), T-80)
        self.b.ingest(depth(), T-80)
        self.b.snapshot("BTCUSDT", {"lastUpdateId": 100, "T": T-100,
                                   "bids": [["99.9", "2"]],
                                   "asks": [["100", "2"]]}, T-70)
        # Entry must have a real bookTicker anchor, not a depth-only quote.
        self.b.ingest(quote(u=100,t=T-100,bid="99.9",ask="100"),T-60)
        self.b.add(entry())

    def tearDown(self):
        self.temp.cleanup()

    def finish(self, events=()):
        self.b.ingest(quote(u=200, t=END, bid="100.5", ask="100.6"), END+10)
        self.closing_depth()
        self.b.ingest(trade(a=11, t=END), END+20)
        def rest(path, params):
            self.assertEqual(path, "/fapi/v1/fundingRate")
            return list(events)
        key = self.b.reconcile_funding("BTCUSDT", T, END, rest,
                                      now_ms=END+FUNDING_GRACE_MS)
        return self.b.finalize("d1", now_ms=END+FUNDING_GRACE_MS, funding_key=key)

    def closing_depth(self,bid="100.5",ask="100.6"):
        d=depth(u=200,U=101,pu=100,t=END,bid=bid,ask=ask)
        d["b"].append(["99.9","0"])
        d["a"].append(["100","0"])
        self.b.ingest(d,END+15)

    def test_quote_only_stop_crossing_and_shared_path(self):
        self.b.ingest({"stream": "btcusdt@bookTicker", "data": quote()}, T+120)
        rows = self.finish()
        self.assertTrue(all(r.status == "OBSERVED_STREAM" and r.exit_time_ms == T+100 for r in rows))
        self.assertTrue(all(r.observed_accounting["exit_fill_price"] == 98.5 for r in rows))
        self.assertTrue(all(r.observed_accounting["gross_r"] < -1 for r in rows))
        self.assertEqual(len({r.evidence_digest for r in rows}), 1)
        self.assertEqual(self.b.feeds["BTCUSDT"]["agg"], 11)

    def test_auditor_p1_late_depth_cannot_overwrite_newer_entry_anchor(self):
        # Reproduction: bookTicker 102 at T+100, then older depth 101 at
        # T+50 arrives at T+120. Never admit a new SHORT at old depth 99.9.
        self.b.ingest(quote(u=102,t=T+100,bid="98.5",ask="98.6"),T+110)
        old = depth(u=101,pu=100,t=T+50,bid="99.9",ask="100")
        with self.assertRaisesRegex(ValueError,"V5_DEPTH_BEHIND_TICKER"):
            self.b.ingest(old,T+120)
        self.assertFalse(self.b.feeds["BTCUSDT"]["connected"])
        self.assertIsNone(self.b.feeds["BTCUSDT"]["quote"])
        candidate=replace(entry("SHORT","stale-short"),entry_time_ms=T+130,
                          entry_quote_time_ms=T+50,
                          entry_bid=99.9,entry_ask=100.,anchor_agg_id=10)
        with self.assertRaisesRegex(ValueError,"ANCHOR_UNPROVEN"):
            self.b.add(candidate)
        rows=self.b.finalize("d1",now_ms=T+130)
        self.assertTrue(all(r.status=="UNSCORABLE" for r in rows))

    def test_auditor_p1_no_bookticker_never_admits_or_scores(self):
        path=Path(self.temp.name)/"v5"/"no-ticker.db"
        bridge=LiveEvidenceBridge(path,symbols=["BTCUSDT"], clock=lambda: 0)
        bridge.initialize()
        bridge.connected("BTCUSDT")
        bridge.ingest(trade(),T-80)
        bridge.ingest(depth(),T-80)
        bridge.snapshot("BTCUSDT",{"lastUpdateId":100,"T":T-100,
                                   "bids":[["99.9","2"]],
                                   "asks":[["100","2"]]},T-70)
        self.assertIsNone(bridge.feeds["BTCUSDT"]["ticker"])
        with self.assertRaisesRegex(ValueError,"ANCHOR_UNPROVEN"):
            bridge.add(entry())
        # Even a legacy/directly restored path cannot silently bypass
        # the quote-source coverage gate at finalization.
        bridge.lab.add(entry())
        closing=depth(u=200,U=101,pu=100,t=END,bid="100.5",ask="100.6")
        closing["b"].append(["99.9","0"])
        closing["a"].append(["100","0"])
        bridge.ingest(closing,END+15)
        bridge.ingest(trade(11,END),END+20)
        proof=bridge.reconcile_funding("BTCUSDT",T,END,lambda *a:[],
                                      now_ms=END+FUNDING_GRACE_MS)
        rows=bridge.finalize("d1",now_ms=END+FUNDING_GRACE_MS,
                             funding_key=proof)
        self.assertTrue(all(r.status=="UNSCORABLE" and r.accounting is None
                            for r in rows))

    def test_auditor_p1_per_symbol_bookticker_silence_not_masked_by_other_traffic(self):
        self.b.ingest(trade(a=11,t=T+1000),T+1010)
        self.b.ingest(depth(u=101,pu=100,t=T+1100,bid="99.9",ask="100"),
                      T+1110)
        feed=self.b.feeds["BTCUSDT"]
        self.assertGreater(feed["source_receipts"]["aggTrade"],
                           feed["source_receipts"]["bookTicker"])
        self.assertGreater(feed["source_receipts"]["depthUpdate"],
                           feed["source_receipts"]["bookTicker"])
        with self.assertRaisesRegex(RuntimeError,"BOOKTICKER_SOURCE_SILENT"):
            self.b.check_source_coverage(T+31_000)
        self.assertFalse(feed["connected"])
        self.assertTrue(all(r.status=="UNSCORABLE"
                            for r in self.b.finalize("d1",now_ms=T+31_000)))

    def test_auditor_p1_unobserved_crossing_then_recovery_stays_unscorable(self):
        # Hypothetical missing stop crossing/reversal is NOT present in the
        # captured ticker stream. The intervening 31s of missing coverage
        # invalidates the path even after quotes apparently recover.
        with patch("nbot.observation.v5_live_evidence.MAX_BOOKTICKER_SILENCE_MS",30_000):
            self.b.ingest(trade(a=11,t=T+31_000),T+31_010)
            self.assertEqual(self.b.lab._paths["d1"].gap_reason,
                             "BOOKTICKER_COVERAGE_GAP")
            self.b.ingest(quote(u=101,t=T+31_100,bid="99.9",ask="100"),
                          T+31_110)
            self.b.ingest(depth(u=101,pu=100,t=T+31_100,bid="99.9",
                                ask="100"),T+31_120)
        rows=self.b.finalize("d1",now_ms=T+31_200)
        self.assertEqual({r.status for r in rows},{"UNSCORABLE"})
        self.assertEqual({r.reason for r in rows},{"BOOKTICKER_COVERAGE_GAP"})

    def test_auditor_p1_strict_tick_coverage_gap_invalidates_even_if_trades_continue(self):
        with patch("nbot.observation.v5_live_evidence.MAX_BOOKTICKER_SILENCE_MS",30_000):
            self.b.ingest(trade(a=11,t=T+31_000),T+31_010)
        self.assertEqual(self.b.lab._paths["d1"].gap_reason,
                         "BOOKTICKER_COVERAGE_GAP")
        rows=self.b.finalize("d1",now_ms=T+31_010)
        self.assertTrue(all(r.status=="UNSCORABLE" for r in rows))

    def test_entry_anchor_cannot_predate_quote_capture_receipt(self):
        with self.assertRaisesRegex(ValueError,"LIVE_ANCHOR_UNPROVEN"):
            self.b.add(replace(entry("SHORT","late-capture"),entry_time_ms=T-90))

    def test_quote_only_short_stop_uses_ask(self):
        self.b.add(entry("SHORT", "short"))
        self.b.ingest(quote(bid="101.1", ask="101.2"), T+110)
        self.finish()
        key = next(iter(self.b.funding))
        rows = self.b.finalize("short", now_ms=END+FUNDING_GRACE_MS, funding_key=key)
        self.assertTrue(all(r.observed_accounting["exit_fill_price"] == 101.2 for r in rows))

    def test_bookticker_ids_can_jump_and_exact_duplicate_is_idempotent(self):
        q = quote(u=999, bid="100.2", ask="100.3")
        self.b.ingest(q, T+110)
        count = self.b.lab._paths["d1"].events_seen
        self.b.ingest(q, T+110)
        self.assertEqual(self.b.lab._paths["d1"].events_seen, count)
        self.assertIsNone(self.b.lab._paths["d1"].gap_reason)

    def test_funding_sign_actual_settlement_mark_and_per_arm_exits(self):
        self.b.ingest(quote(bid="102.2", ask="102.3"), T+110)
        f = [{"symbol": "BTCUSDT", "fundingTime": T+5000,
              "fundingRate": ".001", "markPrice": "105"}]
        rows = self.finish(f)
        by = {r.policy_id: r for r in rows}
        self.assertEqual(by["FIXED_2R_V1"].observed_accounting["observed_funding_quote"], 0)
        self.assertAlmostEqual(by["TIME_EXIT_V1"].observed_accounting["observed_funding_quote"], -.21)
        self.assertEqual(by["TIME_EXIT_V1"].observed_accounting["observed_settlements"][0]["mark_price"], 105)

    def test_funding_boundary_and_missing_proof_fail_closed(self):
        f = [{"symbol": "BTCUSDT", "fundingTime": END,
              "fundingRate": ".001", "markPrice": "105"}]
        rows = self.finish(f)
        self.assertTrue(all(r.status == "UNSCORABLE" for r in rows))

    def test_funding_disagreement_future_and_bad_marks_never_prove_zero(self):
        args = ("BTCUSDT", T, END)
        with self.assertRaisesRegex(ValueError, "UNSETTLED"):
            self.b.reconcile_funding(*args, lambda *a: [], now_ms=END)
        one = {"symbol": "BTCUSDT", "fundingTime": T+1000,
               "fundingRate": ".001", "markPrice": "100"}
        with self.assertRaisesRegex(ValueError, "MISMATCH"):
            self.b.reconcile_funding(*args, unittest.mock.Mock(side_effect=[[one], []]),
                                     now_ms=END+FUNDING_GRACE_MS)
        for invalid in ({**one, "symbol": "ETHUSDT"}, {**one, "markPrice": "0"},
                        {**one, "fundingRate": "NaN"}, {**one, "rateType": "Special"}):
            with self.assertRaises(ValueError):
                self.b.reconcile_funding(*args, lambda *a: [invalid],
                                         now_ms=END+FUNDING_GRACE_MS)
        self.assertFalse(self.b.funding)

    def test_funding_overlap_conflict_is_preserved(self):
        self.b.reconcile_funding("BTCUSDT", T, END, lambda *a: [],
                                 now_ms=END+FUNDING_GRACE_MS)
        row = {"symbol": "BTCUSDT", "fundingTime": T+1000,
               "fundingRate": ".001", "markPrice": "100"}
        with self.assertRaisesRegex(ValueError, "CONFLICT"):
            self.b.reconcile_funding("BTCUSDT", T, END, lambda *a: [row],
                                     now_ms=END+FUNDING_GRACE_MS)

    def test_funding_pagination_must_exhaust_and_stay_strictly_ordered(self):
        rows = [{"symbol": "BTCUSDT", "fundingTime": T+i,
                 "fundingRate": "0", "markPrice": "100"} for i in range(1000)]
        with self.assertRaisesRegex(ValueError, "PAGINATION"):
            self.b.reconcile_funding("BTCUSDT", T, END, lambda *a: rows,
                                     now_ms=END+FUNDING_GRACE_MS, max_pages=1)
        calls = []
        def rest(path, params):
            calls.append(params["startTime"])
            return rows if params["startTime"] == T else []
        self.b.reconcile_funding("BTCUSDT", T, END, rest, now_ms=END+FUNDING_GRACE_MS)
        self.assertEqual(calls, [T, T+1000, T, T+1000])

    def test_gap_recovery_does_not_restore_missing_quotes(self):
        self.b.disconnect("BTCUSDT")
        recovered = self.b.recover_trades("BTCUSDT", 12, lambda *a: [trade(11,T+10),trade(12,T+20)])
        self.assertTrue(recovered)
        self.assertEqual(self.b.feeds["BTCUSDT"]["agg"], 12)
        rows = self.b.finalize("d1", now_ms=T+30)
        self.assertTrue(all(r.status == "UNSCORABLE" for r in rows))
        self.assertIsNone(self.b.feeds["BTCUSDT"]["quote"])

    def test_rest_recovery_partial_page_survives_restart(self):
        self.b.disconnect("BTCUSDT")
        self.assertFalse(self.b.recover_trades("BTCUSDT", 12,
                                              lambda *a: [trade(11,T+10)], max_pages=1))
        b = LiveEvidenceBridge(self.path, symbols=["BTCUSDT"], clock=lambda: 0)
        b.initialize()
        self.assertEqual(b.feeds["BTCUSDT"]["agg"], 11)
        self.assertFalse(b.recover_trades("BTCUSDT",12,lambda *a: []))
        with self.assertRaisesRegex(ValueError,"NOT_CONTIGUOUS"):
            b.recover_trades("BTCUSDT",13,lambda *a: [trade(13,T+20)])
        self.assertEqual(b.feeds["BTCUSDT"]["agg"],11)

    def test_restart_preserves_arm_and_digest_but_invalidates_quote_path(self):
        self.b.ingest(quote(), T+110)
        before = self.b.lab._paths["d1"].digest.hexdigest()
        b = LiveEvidenceBridge(self.path, symbols=["BTCUSDT"], clock=lambda: 0)
        b.initialize()
        p = b.lab._paths["d1"]
        self.assertEqual(p.digest.hexdigest(), before)
        self.assertEqual(p.arms["TIME_EXIT_V1"].exit_price,98.5)
        self.assertEqual(p.gap_reason,"PROCESS_RESTART")
        self.assertFalse(b.feeds["BTCUSDT"]["synced"])

    def test_pending_scored_results_survive_restart_and_ledger_retry(self):
        rows = self.finish()
        b = LiveEvidenceBridge(self.path, symbols=["BTCUSDT"], clock=lambda: 0)
        b.initialize()
        restored = b.finalize("d1",now_ms=END)
        self.assertTrue(all(r.status == 'REVOKED' for r in restored))
        self.assertEqual([r.observed_accounting for r in restored],
                         [r.observed_accounting for r in rows])
        store = V5EvidenceStore(Path(self.temp.name)/"v5"/"ledger.db")
        store.initialize()
        store.record_decision(decision_id="d1", event_open_ms=300_000, symbol="BTCUSDT",
                              side="LONG",setup_id="TEST",qualified=True,reason="TEST",
                              feature_digest="test",selection_policy_id="TEST")
        original=store.record_observed_pair
        count=0
        with patch.object(store,"_connect",side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                b.persist_results(store,"d1")
        self.assertEqual(store.observed_pairs(authority=b), [])
        self.assertEqual(b.lab.pending_persistence,1)
        b.persist_results(store,"d1")
        self.assertEqual(store.status()["scored"],0)
        self.assertEqual(len(store.observed_pairs(authority=b)),1)
        self.assertEqual(b.lab.pending_persistence,0)

    def test_depth_pu_gap_invalidates_all_arms_and_clears_book(self):
        with self.assertRaisesRegex(ValueError,"PU_GAP"):
            self.b.ingest(depth(u=102,pu=98,t=T+100),T+110)
        self.assertFalse(self.b.feeds["BTCUSDT"]["synced"])
        self.assertTrue(all(r.status=="UNSCORABLE" for r in self.b.finalize("d1",now_ms=T+200)))

    def test_absolute_depth_zero_removal_and_duplicate_conflict(self):
        d=depth(u=101,pu=100,t=T+100,bid="99.8")
        d["b"].append(["99.9","0"])
        self.b.ingest(d,T+110)
        self.assertEqual(self.b.feeds["BTCUSDT"]["depth_quote"]["b"],"99.8")
        self.b.ingest(d,T+110)
        with self.assertRaisesRegex(ValueError,"DUPLICATE_CONFLICT"):
            self.b.ingest({**d,"b":[["99.7","1"]]},T+110)

    def test_decimal_price_identity_and_future_exchange_time(self):
        d=depth(u=101,pu=100,t=T+100,bid="99.8")
        d["b"].append(["99.9000","0"])
        self.b.ingest(d,T+110)
        self.assertNotIn("99.9",self.b.feeds["BTCUSDT"]["bids"])
        with self.assertRaisesRegex(ValueError,"STALE"):
            self.b.ingest({**quote(t=T+200),"E":T+5000},T+210)

    def test_unbridgeable_snapshot_and_depth_buffer_budget(self):
        self.b.disconnect("BTCUSDT")
        self.b.connected("BTCUSDT")
        self.b.ingest(depth(u=200,U=200,t=T+100),T+110)
        with self.assertRaisesRegex(ValueError,"BRIDGE_MISSING"):
            self.b.snapshot("BTCUSDT",{"lastUpdateId":150,"T":T+100,
                                       "bids":[["99.9","2"]],"asks":[["100","2"]]},T+120)
        self.b.connected("BTCUSDT")
        with patch("nbot.observation.v5_live_evidence.MAX_BUFFER",0):
            with self.assertRaisesRegex(ValueError,"BUFFER_OVERFLOW"):
                self.b.ingest(depth(u=300,t=T+200),T+210)
        self.assertFalse(self.b.feeds["BTCUSDT"]["synced"])

    def test_rest_failure_and_duplicate_settlement_do_not_create_proof(self):
        def unavailable(*a): raise OSError("HTTP 429")
        with self.assertRaises(OSError):
            self.b.reconcile_funding("BTCUSDT",T,END,unavailable,
                                     now_ms=END+FUNDING_GRACE_MS)
        row={"symbol":"BTCUSDT","fundingTime":T+5000,"fundingRate":"0","markPrice":"100"}
        with self.assertRaisesRegex(ValueError,"CHRONOLOGY"):
            self.b.reconcile_funding("BTCUSDT",T,END,lambda *a:[row,row],
                                     now_ms=END+FUNDING_GRACE_MS)
        self.assertFalse(self.b.funding)

    def test_horizon_complete_checkpoint_can_finish_funding_after_restart(self):
        self.b.ingest(quote(t=END,bid="100.1",ask="100.2"),END+10)
        self.closing_depth("100.1","100.2")
        self.b.ingest(trade(11,END),END+20)
        b=LiveEvidenceBridge(self.path,symbols=["BTCUSDT"], clock=lambda: 0)
        b.initialize()
        self.assertEqual(b.lab._paths["d1"].gap_reason,"PROCESS_RESTART")
        key=b.reconcile_funding("BTCUSDT",T,END,lambda *a:[],now_ms=END+FUNDING_GRACE_MS)
        self.assertTrue(all(r.status=="UNSCORABLE" for r in b.finalize("d1",now_ms=END+FUNDING_GRACE_MS,funding_key=key)))

    def test_acknowledged_decision_identity_cannot_be_reused(self):
        self.finish()
        # Simulate an already persisted result acknowledgment; ID registry
        # survives independently of bounded in-memory pending results.
        self.b._change({"kind":"LEDGER_ACK","decision":"d1"},
                       lambda:self.b.lab.acknowledge_persisted("d1"))
        q=self.b.feeds["BTCUSDT"]["quote"]
        e=replace(entry(),entry_time_ms=END+100,entry_quote_time_ms=END,
                  entry_bid=float(q["b"]),entry_ask=float(q["a"]),
                  anchor_agg_id=11,anchor_trade_time_ms=END)
        with self.assertRaisesRegex(ValueError,"DECISION_REUSED"):
            self.b.add(e)
        self.assertEqual(self.b.lab.active_count,0)

    def test_snapshot_does_not_provide_historical_quote_recovery(self):
        self.b.disconnect("BTCUSDT")
        self.b.connected("BTCUSDT")
        self.b.ingest(depth(u=200,U=199,pu=198,t=T+100),T+110)
        self.b.snapshot("BTCUSDT",{"lastUpdateId":199,"T":T+100,
                                   "bids":[["99.9","2"]],"asks":[["100","2"]]},T+120)
        self.assertTrue(self.b.feeds["BTCUSDT"]["synced"])
        self.assertEqual(self.b.lab._paths["d1"].gap_reason,"WSS_DISCONNECTED")

    def test_reversed_joint_quote_time_and_same_time_conflict_fail_closed(self):
        self.b.ingest(quote(bid="100.1",ask="100.2"),T+110)
        self.b.ingest(trade(11,T+50),T+120)
        self.assertEqual(self.b.lab._paths["d1"].gap_reason,"JOINT_EVENT_LATE_OR_REVERSED")

    def test_horizon_quote_requires_trade_watermark_and_funding_proof(self):
        self.b.ingest(quote(t=END,bid="100.1",ask="100.2"),END+10)
        self.assertIsNone(self.b.finalize("d1",now_ms=END))
        self.b.ingest(trade(11,END),END+20)
        self.assertIsNone(self.b.finalize("d1",now_ms=END))
        d=depth(u=200,U=101,pu=100,t=END,bid="100.1",ask="100.2")
        d["b"].append(["99.9","0"]); d["a"].append(["100","0"])
        self.b.ingest(d,END+25)
        rows=self.b.finalize("d1",now_ms=END)
        self.assertEqual({r.status for r in rows},{"OBSERVED_STREAM"})
        self.assertTrue(all(r.accounting is None and r.observed_accounting["net_r"] is None for r in rows))

    def test_failed_commit_rolls_back_state_and_concurrent_writer_rejected(self):
        before=self.b.lab.dump()
        with patch.object(self.b,"_connect",side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.b.ingest(quote(),T+110)
        self.assertEqual(self.b.lab.dump(),before)
        self.assertIsNotNone(self.b.integrity_fault)
        self.b.recover_integrity()
        before=self.b.lab.dump()
        second=LiveEvidenceBridge(self.path,symbols=["BTCUSDT"], clock=lambda: 0)
        second.initialize()
        with self.assertRaisesRegex(RuntimeError,"CONCURRENT_WRITER"):
            self.b.ingest(quote(),T+110)
        self.assertEqual(self.b.lab.dump(),before)

    def test_corrupt_checkpoint_is_not_reinitialized(self):
        with sqlite3.connect(self.path) as c:
            c.execute("UPDATE checkpoint SET state='{}'")
        c.close()
        with self.assertRaisesRegex(ValueError,"CORRUPT"):
            LiveEvidenceBridge(self.path,symbols=["BTCUSDT"], clock=lambda: 0).initialize()

    def test_limits_no_orders_no_import_or_constructor_writes(self):
        path=Path(self.temp.name)/"v5"/"unused.db"
        LiveEvidenceBridge(path,symbols=["BTCUSDT"], clock=lambda: 0)
        self.assertFalse(path.exists())
        with self.assertRaisesRegex(ValueError,"PATH"):
            LiveEvidenceBridge(Path(self.temp.name)/"v4"/"raw.db",symbols=["BTCUSDT"], clock=lambda: 0)
        with self.assertRaisesRegex(RuntimeError,"NO_ORDER"):
            submit_order()
        with patch("nbot.observation.v5_live_evidence.MAX_DB_BYTES",1):
            with self.assertRaisesRegex(RuntimeError,"BACKPRESSURE"):
                self.b.ingest(quote(),T+110)


class TransportTests(unittest.TestCase):
    def test_routed_transport_buffers_snapshot_and_recovers_trade_range(self):
        class Socket:
            def __init__(self,url): self.market="/market/" in url
            async def __aenter__(self): return self
            async def __aexit__(self,*a): pass
            def __aiter__(self): return self.messages()
            async def messages(self):
                if self.market:
                    yield json.dumps({"data":trade()})
                    await asyncio.sleep(.1)
                    yield json.dumps({"data":trade(12,T+100)})
                    await asyncio.sleep(.1)
                else:
                    yield json.dumps({"data":depth()})
                    await asyncio.sleep(.05)
                    yield json.dumps({"data":depth(u=101,pu=100,t=T+50)})
                    await asyncio.Event().wait()
        def rest(path,params):
            if path=="/fapi/v1/depth":
                return {"lastUpdateId":100,"T":T-100,
                        "bids":[["99.9","2"]],"asks":[["100","2"]]}
            self.assertEqual(params["fromId"],11)
            return [trade(11,T+80)]
        with tempfile.TemporaryDirectory() as td:
            b=LiveEvidenceBridge(Path(td)/"v5"/"feed.db",symbols=["BTCUSDT"], clock=lambda: 0)
            b.initialize()
            with self.assertRaisesRegex(RuntimeError,"WSS_CLOSED"):
                asyncio.run(run_session(b,rest=rest,connect=lambda url,**k:Socket(url),
                                        clock=lambda:T+150))
            self.assertEqual(b.feeds["BTCUSDT"]["agg"],12)
            with b._connect() as c:
                kinds=[json.loads(r[0])["kind"] for r in c.execute("SELECT event FROM journal")]
            self.assertIn("DEPTH_SNAPSHOT",kinds)
            self.assertIn("REST_AGG_RECOVERY",kinds)
            self.assertFalse(b.feeds["BTCUSDT"]["synced"])

    def test_routed_streams_and_public_endpoint_allowlist(self):
        market,public=stream_urls(["BTCUSDT"])
        self.assertIn("/market/stream?streams=btcusdt@aggTrade",market)
        self.assertIn("/public/stream?streams=btcusdt@bookTicker/btcusdt@depth@100ms",public)
        with self.assertRaisesRegex(ValueError,"FORBIDDEN"):
            PublicRest()("/fapi/v1/order",{"symbol":"BTCUSDT"})
        with self.assertRaisesRegex(ValueError,"FORBIDDEN"):
            PublicRest()("/fapi/v1/depth",{"symbol":"BTCUSDT","signature":"secret"})
        with self.assertRaisesRegex(RuntimeError,"OPT_IN"):
            asyncio.run(run_research_capture(None))

    def test_wss_disconnect_is_not_swallowed(self):
        class Socket:
            async def __aenter__(self): return self
            async def __aexit__(self,*a): pass
            def __aiter__(self): return self
            async def __anext__(self): raise StopAsyncIteration
        with tempfile.TemporaryDirectory() as td:
            b=LiveEvidenceBridge(Path(td)/"v5"/"feed.db",symbols=["BTCUSDT"], clock=lambda: 0)
            b.initialize()
            with self.assertRaisesRegex(RuntimeError,"WSS_CLOSED"):
                asyncio.run(run_session(b,connect=lambda *a,**k: Socket()))
            self.assertFalse(b.feeds["BTCUSDT"]["connected"])


if __name__ == "__main__":
    unittest.main()
