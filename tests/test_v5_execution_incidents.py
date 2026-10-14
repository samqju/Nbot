"""Offline E5 incident and synthetic outage acceptance."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.test_v5_execution_engine import NOW, MODELS, KEYS
from tests.test_v5_execution_replay import frame, proposal, RECEIPT_KEY, RULES
from nbot.v5.execution_engine import OfflineExecutionEngine
from nbot.v5.execution_replay import SyntheticReplay
from nbot.v5.execution_incidents import SyntheticIncidentGuard, MAX_DISTINCT_INCIDENTS


class IncidentGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "incidents.sqlite"
        self.engine = OfflineExecutionEngine(self.path, MODELS, KEYS)
        self.replay = SyntheticReplay(self.engine, RULES, RECEIPT_KEY)
        self.guard = SyntheticIncidentGuard(self.replay)

    def tearDown(self):
        self.engine.close_database()
        self.tmp.cleanup()

    def test_successful_synthetic_frame_not_logged_as_incident(self):
        ok = self.guard.observe(frame(), [proposal()])
        self.assertTrue(self.replay.verify_receipt(ok))
        self.assertEqual(self.guard.operator_snapshot()["journaled_unique_incidents"], 0)

    def test_stale_quote_is_holding_incident_without_orders(self):
        bad = frame(observed_at_ms=NOW-10000)
        result = self.guard.observe(bad, [proposal()])
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(result["reason"], "QUOTE_STALE_OR_FUTURE")
        self.assertEqual(result["orders_created"], 0)
        self.assertEqual(self.guard.operator_snapshot()["journaled_unique_incidents"], 1)
        self.assertEqual(self.engine.db.execute("SELECT count(*) FROM fills").fetchone()[0], 0)

    def test_duplicate_bad_event_not_unbounded(self):
        bad = frame(btc_healthy=False)
        first = self.guard.observe(bad, [])
        again = self.guard.observe(bad, [])
        self.assertEqual(first["incident_id"], again["incident_id"])
        self.assertEqual(self.guard.operator_snapshot()["journaled_unique_incidents"], 1)

    def test_journal_survives_restart_without_any_live_activation(self):
        self.guard.observe(frame(1, NOW, btc_healthy=False), [])
        self.engine.close_database()
        self.engine = OfflineExecutionEngine(self.path, MODELS, KEYS)
        self.replay = SyntheticReplay(self.engine, RULES, RECEIPT_KEY)
        self.guard = SyntheticIncidentGuard(self.replay)
        self.assertEqual(self.guard.operator_snapshot()["recent"][0]["reason"], "MARKET_DATA_UNVERIFIED")
        self.assertEqual(self.engine.integrity(), "ok")

    def test_no_source_yet_holds_without_fabricated_trades(self):
        result = self.guard.check_source_timeout(NOW)
        self.assertEqual(result["reason"], "NO_REPLAY_EVIDENCE")
        self.assertFalse(self.engine.report("CHAMPION_PAPER")["killed"])
        self.assertEqual(self.engine.db.execute("SELECT count(*) FROM orders").fetchone()[0], 0)

    def test_source_timeout_quarantines_new_entries_and_preserves_open_positions(self):
        self.guard.observe(frame(), [proposal()])
        self.assertEqual(self.guard.check_source_timeout(NOW+1000)["status"],
                         "QUALIFIED_SYNTHETIC_RECENT_FRAME")
        result = self.guard.check_source_timeout(NOW+RULES.max_evidence_gap_ms+1)
        self.assertEqual(result["reason"], "SOURCE_TIMEOUT")
        self.assertTrue(result["new_entries_blocked"])
        self.assertEqual(result["open_positions_unresolved"]["CHAMPION_PAPER"], 1)
        self.assertTrue(self.engine.report("CHAMPION_PAPER")["killed"])
        self.assertTrue(self.engine.report("CHALLENGER_PAPER")["killed"])
        self.assertEqual(self.engine.report("CHAMPION_PAPER")["settled_count"], 0)
        self.assertEqual(self.guard.operator_snapshot()["recent"][0]["reason"], "SOURCE_TIMEOUT")

    def test_immutable_incident_rows(self):
        self.guard.observe(frame(btc_healthy=False), [])
        with self.assertRaises(sqlite3.DatabaseError):
            self.engine.db.execute("DELETE FROM execution_incidents")
        with self.assertRaises(sqlite3.DatabaseError):
            self.engine.db.execute("UPDATE execution_incidents SET reason='PASS'")

    def test_incident_capacity_bounded_and_overflow_visible(self):
        for i in range(MAX_DISTINCT_INCIDENTS+2):
            self.guard.observe(frame(i+1, NOW, btc_healthy=False), [])
        state = self.guard.operator_snapshot()
        self.assertEqual(state["journaled_unique_incidents"], MAX_DISTINCT_INCIDENTS)
        self.assertEqual(state["dropped_distinct_at_capacity"], 2)
        self.assertLessEqual(len(state["recent"]), 20)

    def test_malformed_input_logs_no_raw_signed_secrets(self):
        request = {"invalid": ["secret-string-that-must-not-be-stored"]}
        result = self.guard.observe(request, [])
        self.assertEqual(result["status"], "HOLD")
        db_rows = self.engine.db.execute(
            "SELECT reason,event_id,event_digest FROM execution_incidents").fetchall()
        self.assertEqual(len(db_rows), 1)
        self.assertNotIn("secret-string", str([tuple(r) for r in db_rows]))

    def test_incident_outcomes_cannot_be_treated_as_paper_fills(self):
        self.guard.observe(frame(1, NOW, bid="101", ask="100"), [proposal()])
        self.assertEqual(self.engine.db.execute("SELECT count(*) FROM settled").fetchone()[0], 0)
        self.assertEqual(self.engine.db.execute("SELECT count(*) FROM replay_frames").fetchone()[0], 0)
        self.assertEqual(self.guard.operator_snapshot()["books"]["CHAMPION_PAPER"]["open_position_count"], 0)


if __name__ == "__main__":
    unittest.main()
