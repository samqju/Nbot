import tempfile
from pathlib import Path
import unittest

from nbot.observation.v4_generation import _qualification_status
from nbot.observation.v4_paper_contest import (
    AUTHORITY,
    CHECKPOINT_TRADES,
    ORDER_AUTHORITY,
    V4PaperContestStore,
)


class _Model:
    qualification = "BASELINE_READY"
    model_digest = "abc"


class V4GenerationQueueTests(unittest.TestCase):
    def test_only_first_generation_is_baseline(self):
        self.assertEqual(
            _qualification_status(
                0, {"mean_net_r": -10.0, "positive_rate": 0.0}
            ),
            "BASELINE_READY",
        )
        self.assertEqual(
            _qualification_status(
                1, {"mean_net_r": -0.1, "positive_rate": 0.9}
            ),
            "RESEARCH_REJECTED",
        )
        self.assertEqual(
            _qualification_status(
                1, {"mean_net_r": 0.1, "positive_rate": 0.5}
            ),
            "CHALLENGER_READY",
        )


class V4PaperContestStoreTests(unittest.TestCase):
    def _contest(self, store):
        return store.ensure_contest(
            champion_generation=None,
            challenger_generation=1,
            models={1: _Model()},
            now_ms=1,
        )

    def test_no_order_authority_contract(self):
        self.assertEqual(ORDER_AUTHORITY, "NONE")
        self.assertIn("NO_ORDER_AUTHORITY", AUTHORITY)
        self.assertEqual(CHECKPOINT_TRADES, 100)

    def test_one_hundred_scored_trades_requires_review_not_auto_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            store = V4PaperContestStore(Path(td) / "paper.db")
            contest_id = self._contest(store)
            for i in range(CHECKPOINT_TRADES):
                decision_id = f"d{i}"
                store.open_trade(
                    decision_id=decision_id,
                    contest_id=contest_id,
                    generation=1,
                    event_open_ms=i * 300_000,
                    symbol="BTCUSDT",
                    side="LONG",
                    entry_time_ms=i * 300_000 + 1,
                    entry_price=100.0,
                    one_r_price=1.0,
                )
                store.close_trade(
                    decision_id,
                    net_r=1.0 if i % 2 == 0 else -0.5,
                    mfe_r=1.0,
                    mae_r=-0.5,
                    exit_time_ms=i * 300_000 + 2,
                    exit_reason="STOP",
                    source_digest=f"s{i}",
                )
            contest = store.active_contest()
            self.assertEqual(contest["status"], "REVIEW_REQUIRED")
            status = store.contest_model_status(contest_id, 1)
            self.assertEqual(status["completed_trades"], CHECKPOINT_TRADES)
            self.assertEqual(status["status"], "REVIEW_REQUIRED")
            self.assertAlmostEqual(status["realized_r"], 25.0)
            self.assertEqual(store.status()["automatic_promotion"], False)

    def test_unscorable_trade_does_not_count_toward_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            store = V4PaperContestStore(Path(td) / "paper.db")
            contest_id = self._contest(store)
            store.open_trade(
                decision_id="gap",
                contest_id=contest_id,
                generation=1,
                event_open_ms=0,
                symbol="ETHUSDT",
                side="SHORT",
                entry_time_ms=1,
                entry_price=100.0,
                one_r_price=1.0,
            )
            store.mark_unscorable("gap", reason="GAP_UNRESOLVED")
            status = store.status()
            self.assertEqual(status["models"][0]["completed_trades"], 0)
            self.assertEqual(status["models"][0]["unscorable_trades"], 1)

    def test_new_head_to_head_contest_starts_fresh_model_counts(self):
        with tempfile.TemporaryDirectory() as td:
            store = V4PaperContestStore(Path(td) / "paper.db")
            first = self._contest(store)
            with store.path.open("rb"):
                pass
            # Close the baseline review after reaching its checkpoint via direct
            # fixture state: the review API itself requires REVIEW_REQUIRED.
            with __import__("sqlite3").connect(store.path) as conn:
                conn.execute(
                    "UPDATE contests SET status='CLOSED',review_decision='PROMOTE' WHERE contest_id=?",
                    (first,),
                )
            champion = _Model()
            challenger = _Model()
            second = store.ensure_contest(
                champion_generation=1,
                challenger_generation=2,
                models={1: champion, 2: challenger},
                now_ms=2,
            )
            self.assertNotEqual(first, second)
            self.assertEqual(
                store.contest_model_status(second, 1)["completed_trades"], 0
            )
            self.assertEqual(
                store.contest_model_status(second, 2)["completed_trades"], 0
            )


if __name__ == "__main__":
    unittest.main()
