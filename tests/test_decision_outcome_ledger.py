import tempfile
import unittest
from pathlib import Path

from nbot.exchange.binance_stream import AggTrade
from nbot.observation.decision_ledger import DecisionOutcomeLedger


def trade(symbol, price, t, aid):
    return AggTrade(symbol, price, 1.0, t, t, aid, aid, aid, False)


class DecisionOutcomeLedgerTests(unittest.TestCase):
    def make(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ledger = DecisionOutcomeLedger(Path(tmp.name) / "ledger.db")
        base = dict(
            release_sha="a"*40, profile="live-paper", event_ms=1_000_000, decision_ms=1_300_000,
            symbol="BTCUSDT", bid=99.99, ask=100.0,
            feature_vector={"x": 1.0}, candidate_ids=["MODEL_ONLY"],
            scores={"conservative_score_r": -0.1}, rank=1, model_digest=None,
        )
        return ledger, base

    def test_loss_first_then_rally_is_stopped_loss(self):
        ledger, base = self.make()
        ledger.record(side="LONG", selected=False, decision="REJECTED",
                      blocker="LOW_CONFIDENCE", **base)
        # Planned per-R distance is 1.0; initial stop is 99.0.
        ledger.on_agg_trade(trade("BTCUSDT", 98.9, 1_300_100, 1))
        # Later rally must not resurrect a stopped counterfactual.
        ledger.on_agg_trade(trade("BTCUSDT", 104.0, 1_300_200, 2))
        ledger.finalize_funding([])
        row = next(iter(ledger.training_targets().values()))
        self.assertLess(row["target_net_r"], -1.0)
        self.assertEqual(row["assessment"], "AVOIDED_LOSS")

    def test_profit_first_moves_integer_stop_before_reversal(self):
        ledger, base = self.make()
        ledger.record(side="LONG", selected=False, decision="REJECTED",
                      blocker="LOW_CONFIDENCE", **base)
        # Simulated fill is 100.02. +3R is just above 103.02.
        ledger.on_agg_trade(trade("BTCUSDT", 103.2, 1_300_100, 1))
        # Stop is now +2R around the fill. Reversal crosses it.
        ledger.on_agg_trade(trade("BTCUSDT", 101.9, 1_300_200, 2))
        ledger.finalize_funding([])
        row = next(iter(ledger.training_targets().values()))
        self.assertGreater(row["target_net_r"], 1.0)
        self.assertEqual(row["assessment"], "MISSED_PROFITABLE_POLICY_OUTCOME")

    def test_unresolved_stream_gap_excluded_from_training(self):
        ledger, base = self.make()
        ledger.record(side="SHORT", selected=False, decision="REJECTED",
                      blocker="LOWER_RANKED", **base)
        ledger.on_agg_trade(trade("BTCUSDT", 100.0, 1_300_100, 1))
        ledger.mark_stream_gap(at_ms=1_300_150)
        ledger.on_agg_trade(trade("BTCUSDT", 101.5, 1_300_200, 2))
        ledger.finalize_funding([])
        self.assertEqual(ledger.training_targets(), {})

    def test_resolved_gap_can_be_used_after_backfill(self):
        ledger, base = self.make()
        ledger.record(side="SHORT", selected=False, decision="REJECTED",
                      blocker="LOWER_RANKED", **base)
        ledger.mark_stream_gap(at_ms=1_300_010)
        ledger.on_agg_trade(trade("BTCUSDT", 101.5, 1_300_100, 1), source="REST_BACKFILL")
        ledger.resolve_stream_gap("BTCUSDT")
        ledger.finalize_funding([])
        targets = ledger.training_targets()
        self.assertEqual(len(targets), 1)


    def test_batch_replay_preserves_profit_then_stop_chronology(self):
        ledger, base = self.make()
        ledger.record(side="LONG", selected=False, decision="REJECTED",
                      blocker="LOW_CONFIDENCE", **base)
        ledger.on_agg_trades((
            trade("BTCUSDT", 103.2, 1_300_100, 1),
            trade("BTCUSDT", 101.9, 1_300_200, 2),
        ))
        ledger.finalize_funding([])
        row = next(iter(ledger.training_targets().values()))
        self.assertGreater(row["target_net_r"], 1.0)
        self.assertEqual(row["assessment"], "MISSED_PROFITABLE_POLICY_OUTCOME")

    def test_funding_requires_full_proven_coverage_when_bounds_are_supplied(self):
        ledger, base = self.make()
        ledger.record(side="LONG", selected=False, decision="REJECTED",
                      blocker="LOW_CONFIDENCE", **base)
        ledger.on_agg_trade(trade("BTCUSDT", 98.9, 1_300_100, 1))
        self.assertEqual(ledger.funding_requirement_start_ms(), 1_300_000)
        # A query window beginning after the decision cannot prove that no
        # funding event occurred during the complete hypothetical holding time.
        ledger.finalize_funding(
            [], coverage_start_ms=1_300_050, coverage_end_ms=1_400_000
        )
        self.assertEqual(ledger.training_targets(), {})
        ledger.finalize_funding(
            [], coverage_start_ms=1_300_000, coverage_end_ms=1_400_000
        )
        self.assertEqual(len(ledger.training_targets()), 1)
        self.assertIsNone(ledger.funding_requirement_start_ms())

    def test_same_event_isolated_by_live_profile(self):
        ledger, base = self.make()
        first = ledger.record(
            side="LONG", selected=False, decision="REJECTED",
            blocker="LOW_CONFIDENCE", **base
        )
        other = dict(base)
        other["profile"] = "live-trade"
        second = ledger.record(
            side="LONG", selected=False, decision="REJECTED",
            blocker="LOW_CONFIDENCE", **other
        )
        self.assertNotEqual(first, second)

    def test_catchup_restarts_inclusive_of_last_trade_millisecond(self):
        ledger, base = self.make()
        ledger.record(
            side="LONG", selected=False, decision="REJECTED",
            blocker="LOW_CONFIDENCE", **base
        )
        ledger.on_agg_trade(trade("BTCUSDT", 100.1, 1_300_100, 10))
        self.assertEqual(ledger.catchup_start_ms("BTCUSDT"), 1_300_100)

    def test_horizon_waits_for_gap_repair_before_maturing(self):
        ledger, base = self.make()
        ledger.record(
            side="LONG", selected=False, decision="REJECTED",
            blocker="LOW_CONFIDENCE", **base
        )
        ledger.on_agg_trade(trade("BTCUSDT", 100.5, 1_300_100, 1))
        ledger.mark_stream_gap(at_ms=1_400_000, symbol="BTCUSDT")
        horizon = 1_300_000 + 4 * 60 * 60 * 1000
        self.assertEqual(ledger.expire(now_ms=horizon + 1), 0)
        self.assertIn("BTCUSDT", ledger.pending_symbols())
        ledger.resolve_stream_gap("BTCUSDT")
        self.assertEqual(ledger.expire(now_ms=horizon + 1), 1)

    def test_horizon_close_seals_open_path(self):
        ledger, base = self.make()
        ledger.record(side="LONG", selected=True, decision="APPROVED",
                      blocker=None, **base)
        ledger.on_agg_trade(trade("BTCUSDT", 100.5, 1_300_100, 1))
        ledger.expire(now_ms=1_300_000 + 4*60*60*1000 + 1)
        ledger.finalize_funding([])
        row = next(iter(ledger.training_targets().values()))
        self.assertEqual(row["assessment"], "APPROVED_COUNTERFACTUAL")


if __name__ == "__main__":
    unittest.main()
