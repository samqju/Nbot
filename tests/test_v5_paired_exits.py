"""V5 three-armed 4h paired-exit comparison; no network or orders."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from nbot.observation.v5_paired_exits import (
    HORIZON_MS, EXIT_POLICIES, MAX_CONCURRENT, PairedEntry,
    PairedTick, PairedExitLab, persist_to_v5_ledger, submit_order,
)
from nbot.observation.v5_accounting import FundingSettlement
from nbot.observation.v5_foundation import V5EvidenceStore

ENTRY_TIME = 100_000
DEADLINE = ENTRY_TIME + HORIZON_MS


def entry(*, decision_id="d1", side="LONG", symbol="BTCUSDT"):
    return PairedEntry(
        decision_id, symbol, side, ENTRY_TIME, 99.9, 100.0, ENTRY_TIME - 100,
        2.0, 99.0 if side == "LONG" else 100.9,
        999, ENTRY_TIME - 200,
    )


def tick(agg_id, time_ms, *, bid, ask=None, symbol="BTCUSDT",
         quote_time_ms=None):
    if ask is None:
        ask = bid + 0.1
    if quote_time_ms is None:
        quote_time_ms = time_ms
    return PairedTick(symbol, agg_id, time_ms, time_ms + 20,
                      (bid + ask) / 2, quote_time_ms, agg_id * 2,
                      bid, ask)


def complete(lab, *, final_bid=101.4, final_ask=None, extra=(), proof=True):
    for t in extra:
        lab.ingest(t)
    lab.ingest(tick(1000 + len(extra), DEADLINE, bid=final_bid, ask=final_ask))
    return lab.finalize("d1", now_ms=DEADLINE, funding_coverage_confirmed=proof)


class PairedPolicyTests(unittest.TestCase):
    def test_same_full_path_three_different_exits(self):
        lab=PairedExitLab()
        lab.add(entry())
        self.assertIsNone(lab.finalize("d1",now_ms=ENTRY_TIME+5))
        # +2R target, then retreat to +0.5R: the trailing rule locks +1R
        # after the +2.1R peak. At the final tick, time-only exits at +1.4R.
        lab.ingest(tick(1000, ENTRY_TIME+1000, bid=102.1))
        self.assertEqual(lab.active_count,1)
        lab.ingest(tick(1001, ENTRY_TIME+2000, bid=101.4))
        lab.ingest(tick(1002, ENTRY_TIME+3000, bid=100.8))
        lab.ingest(tick(1003, DEADLINE, bid=101.4))
        results=lab.finalize("d1",now_ms=DEADLINE,
                             funding_coverage_confirmed=True)
        by={x.policy_id:x for x in results}
        self.assertEqual(set(by),set(EXIT_POLICIES))
        self.assertEqual(by["FIXED_2R_V1"].exit_reason,"TARGET")
        self.assertEqual(by["TIME_EXIT_V1"].exit_reason,"HORIZON")
        self.assertEqual(by["INTEGER_TRAIL_V1"].exit_reason,"STOP")
        self.assertEqual([by[x].accounting.net_r > 0 for x in EXIT_POLICIES],
                         [True,True,True])
        self.assertEqual(len({r.evidence_digest for r in results}),1)
        self.assertTrue(all(r.events_seen==4 for r in results))
        self.assertIs(results,lab.finalize("d1",now_ms=DEADLINE))
        self.assertEqual(lab.active_count,0)
        self.assertEqual(lab.pending_persistence,1)
        lab.acknowledge_persisted("d1")
        self.assertEqual(lab.pending_persistence,0)

    def test_initial_minus_one_r_for_every_arm_and_short_executable_ask(self):
        lab=PairedExitLab()
        lab.add(entry(side="SHORT"))
        # SHORT entry bid 99.9; stop 100.9 (1R), exit uses ask 101.3.
        lab.ingest(tick(1000,ENTRY_TIME+1000,bid=101.2,ask=101.3))
        lab.ingest(tick(1001,DEADLINE,bid=99.4,ask=99.5))
        rows=lab.finalize("d1",now_ms=DEADLINE,funding_coverage_confirmed=True)
        self.assertTrue(all(r.accounting.gross_r < -1.39 for r in rows))
        self.assertTrue(all(r.exit_reason=="STOP" for r in rows))
        self.assertTrue(all(r.accounting.net_r < r.accounting.gross_r for r in rows))

    def test_no_fictitious_horizon_exit_if_last_tick_is_before_deadline(self):
        lab=PairedExitLab()
        lab.add(entry())
        lab.ingest(tick(1000,ENTRY_TIME+1000,bid=100.5))
        self.assertIsNone(lab.finalize("d1",now_ms=DEADLINE))
        rows=lab.finalize("d1",now_ms=DEADLINE+5001)
        self.assertTrue(all(r.status=="UNSCORABLE" and
                            r.reason=="HORIZON_CLOSE_WITNESS_MISSING" for r in rows))

    def test_one_gap_invalidates_all_arms_even_if_one_earlier_exited(self):
        lab=PairedExitLab()
        lab.add(entry())
        lab.ingest(tick(1000,ENTRY_TIME+1000,bid=102.2))
        lab.ingest(tick(1002,ENTRY_TIME+2000,bid=102.4))
        rows=lab.finalize("d1",now_ms=ENTRY_TIME+2000)
        self.assertTrue(all(r.status=="UNSCORABLE" for r in rows))
        self.assertTrue(all(r.accounting is None for r in rows))
        self.assertEqual({r.reason for r in rows},{"TICK_GAP_OR_STALE_QUOTE"})

    def test_disconnect_invalidates_all_policy_arms(self):
        lab=PairedExitLab()
        lab.add(entry())
        lab.invalidate_symbol("BTCUSDT",reason="WSS_DISCONNECTED")
        results=lab.finalize("d1",now_ms=ENTRY_TIME+100)
        self.assertEqual({r.reason for r in results},{"WSS_DISCONNECTED"})

    def test_missing_funding_never_assumed_zero(self):
        lab=PairedExitLab()
        lab.add(entry())
        lab.ingest(tick(1000,DEADLINE,bid=100.3))
        rows=lab.finalize("d1",now_ms=DEADLINE)
        self.assertEqual({r.reason for r in rows},{"FUNDING_COVERAGE_UNPROVEN"})
        self.assertTrue(all(r.accounting is None for r in rows))

    def test_signed_funding_applies_per_exit_not_only_full_horizon(self):
        lab=PairedExitLab()
        lab.add(entry())
        lab.ingest(tick(1000,ENTRY_TIME+1000,bid=102.2))
        lab.ingest(tick(1001,DEADLINE,bid=101.2))
        f=(FundingSettlement("BTCUSDT",ENTRY_TIME+5000,.001,100.0),)
        rows=lab.finalize("d1",now_ms=DEADLINE,
                          funding_events=f,funding_coverage_confirmed=True)
        by={r.policy_id:r for r in rows}
        self.assertEqual(by["FIXED_2R_V1"].accounting.funding_events_used,0)
        self.assertEqual(by["TIME_EXIT_V1"].accounting.funding_events_used,1)
        self.assertEqual(by["INTEGER_TRAIL_V1"].accounting.funding_events_used,1)

    def test_boundary_funding_uncertainty_rejects_entire_paired_sample(self):
        lab=PairedExitLab()
        lab.add(entry())
        lab.ingest(tick(1000,ENTRY_TIME+1000,bid=102.2))
        lab.ingest(tick(1001,DEADLINE,bid=101.2))
        # The fixed-target arm closes exactly on a funding settlement.
        # Its timing is ambiguous; no selective retention of other arms.
        f=(FundingSettlement("BTCUSDT",ENTRY_TIME+1000,.001,100.0),)
        rows=lab.finalize("d1",now_ms=DEADLINE,
                          funding_events=f,funding_coverage_confirmed=True)
        self.assertEqual({r.reason for r in rows},
                         {"ACCOUNTING_OR_FUNDING_UNSCORABLE"})
        self.assertTrue(all(r.accounting is None for r in rows))

    def test_late_receipt_cannot_be_relabelled_as_live_evidence(self):
        lab=PairedExitLab()
        lab.add(entry())
        future_receipt=replace(
            tick(1000,ENTRY_TIME+1000,bid=100.4),
            receipt_time_ms=ENTRY_TIME+1000+5000,
        )
        lab.ingest(future_receipt)
        rows=lab.finalize("d1",now_ms=ENTRY_TIME+6000)
        self.assertEqual({r.reason for r in rows},
                         {"TICK_GAP_OR_STALE_QUOTE"})

    def test_corrupt_or_stale_quote_rejected_and_retransmission_safe(self):
        lab=PairedExitLab()
        lab.add(entry())
        x=tick(1000,ENTRY_TIME+1000,bid=100.5)
        lab.ingest(x)
        lab.ingest(x)
        bad=replace(tick(1001,ENTRY_TIME+2000,bid=100.6),
                    quote_time_ms=ENTRY_TIME-8000)
        lab.ingest(bad)
        rows=lab.finalize("d1",now_ms=ENTRY_TIME+2000)
        self.assertEqual({r.reason for r in rows},{"TICK_GAP_OR_STALE_QUOTE"})
        self.assertTrue(all(r.events_seen==1 for r in rows))

    def test_horizon_late_tick_is_not_accepted_as_price(self):
        lab=PairedExitLab()
        lab.add(entry())
        lab.ingest(tick(1000,DEADLINE+6000,bid=100.5))
        rows=lab.finalize("d1",now_ms=DEADLINE+6000)
        self.assertEqual({r.reason for r in rows},{"HORIZON_CLOSE_WITNESS_MISSING"})

    def test_entry_validation_capacity_and_two_directions(self):
        with self.assertRaisesRegex(ValueError,"INITIAL_STOP"):
            replace(entry(),initial_stop_price=100.0)
        lab=PairedExitLab()
        lab.add(entry())
        with self.assertRaisesRegex(ValueError,"DECISION_REUSED"):
            lab.add(entry())
        with self.assertRaisesRegex(ValueError,"SYMBOL_SIDE_ACTIVE"):
            lab.add(entry(decision_id="d2"))
        # Opposite directions are separate hypotheses.
        lab.add(entry(decision_id="d3",side="SHORT"))
        for i in range(98):
            lab.add(entry(decision_id=f"sym{i}",symbol=f"ASSET{i}USDT"))
        self.assertEqual(lab.active_count,MAX_CONCURRENT)
        with self.assertRaisesRegex(ValueError,"CAPACITY"):
            lab.add(entry(decision_id="extra",symbol="NEWUSDT"))
        with self.assertRaisesRegex(RuntimeError,"NO_ORDER_AUTHORITY"):
            submit_order()

    def test_append_only_three_policy_outcomes_and_retry(self):
        with tempfile.TemporaryDirectory() as td:
            store=V5EvidenceStore(Path(td)/"v5"/"evidence.db")
            store.initialize()
            store.record_decision(
                decision_id="d1",event_open_ms=300_000,symbol="BTCUSDT",
                side="LONG",setup_id="LEVEL_BREAKOUT_V1",
                qualified=True,reason="SETUP_CONFIRMED",
                feature_digest="test-feature",selection_policy_id="V5_SELECTION_TEST")
            lab=PairedExitLab()
            lab.add(entry())
            lab.ingest(tick(1000,DEADLINE,bid=100.4))
            rows=lab.finalize("d1",now_ms=DEADLINE,funding_coverage_confirmed=True)
            persist_to_v5_ledger(store,rows)
            persist_to_v5_ledger(store,rows)
            self.assertEqual(store.status()["scored"],3)
            with sqlite3.connect(store.path) as c:
                self.assertEqual(c.execute(
                    "SELECT COUNT(DISTINCT digest) FROM v5_outcomes").fetchone()[0],3)
            lab.acknowledge_persisted("d1")

    def test_streaming_cost_does_not_retain_history(self):
        lab=PairedExitLab()
        lab.add(entry())
        for i in range(5000):
            lab.ingest(tick(1000+i,ENTRY_TIME+1+i,bid=100.4))
        self.assertEqual(lab.active_count,1)
        path=lab._paths["d1"]
        self.assertFalse(hasattr(path,"events"))
        self.assertEqual(path.events_seen,5000)
        lab.ingest(tick(6000,DEADLINE,bid=100.2))
        rows=lab.finalize("d1",now_ms=DEADLINE,funding_coverage_confirmed=True)
        self.assertTrue(all(r.status=="SCORED" for r in rows))


if __name__ == "__main__":
    unittest.main()
