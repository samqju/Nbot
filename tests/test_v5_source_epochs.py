"""Persistent V5 public WSS generations must survive crashes and refuse tampering."""
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nbot.v5.source_epochs import SourceEpochAudit, SourceEpochHold
from nbot.v5.observation_continuity import ObservationContinuity


class SourceEpochAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/"epoch_test.db"

    def test_generation_monotonicity_and_append_only_sql(self):
        with sqlite3.connect(self.path) as db:
            audit = SourceEpochAudit(db)
            self.assertIsNone(audit.latest("market"))
            audit.append("market", 1, "CONNECTED", at_ms=123)
            with self.assertRaises(SourceEpochHold):
                audit.append("market", 2, "CONNECTED", at_ms=124)
            with self.assertRaises(SourceEpochHold):
                audit.append("market", 1, "DISCONNECTED", at_ms=-1)
            audit.append("market", 1, "DISCONNECTED", at_ms=125)
            audit.append("market", 2, "CONNECTED", at_ms=126)
            self.assertEqual(audit.latest("market"), (2, "CONNECTED"))
            for stmt in (
                "DELETE FROM v5_source_epochs",
                "UPDATE v5_source_epochs SET serial=serial",
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(stmt)
            db.rollback()
            self.assertFalse(audit.overview()["research_ready"])

    def test_real_observation_context_records_crash_and_recovery_generation(self):
        with ObservationContinuity(("BTCUSDT",), self.path) as first:
            first.connect("market")
            first.connect("public")
            self.assertEqual(first.generations["market"], 1)
            # Unclean close simulates a process crash without socket callbacks.
        with ObservationContinuity(("BTCUSDT",), self.path) as restarted:
            self.assertEqual(restarted.sources.latest("market"),
                             (1, "UNCLEAN_RESTART"))
            self.assertEqual(restarted.sources.latest("public"),
                             (1, "UNCLEAN_RESTART"))
            self.assertFalse(restarted.store.health.market_connected)
            restarted.connect("market")
            self.assertEqual(restarted.generations["market"], 2)
            restarted.disconnect("market")
            self.assertEqual(restarted.sources.latest("market"),
                             (2, "DISCONNECTED"))
            self.assertFalse(restarted.sources.overview()["research_ready"])
        with ObservationContinuity(("BTCUSDT",), self.path) as third:
            self.assertEqual(third.generations["market"], 2)
            self.assertEqual(third.sources.latest("market"),
                             (2, "DISCONNECTED"))

    def test_unknown_route_and_invalid_transitions_rejected(self):
        with sqlite3.connect(self.path) as db:
            audit = SourceEpochAudit(db)
            with self.assertRaises(SourceEpochHold):
                audit.latest("private")
            with self.assertRaises(SourceEpochHold):
                audit.append("market", 1, "DISCONNECTED", at_ms=100)
            with self.assertRaises(SourceEpochHold):
                audit.append("market", 0, "CONNECTED", at_ms=100)
            self.assertEqual(audit.recover_unclosed(at_ms=100), {})
            self.assertFalse(audit.overview()["research_ready"])

    def test_restart_event_deduplicates_after_the_first_restart(self):
        with sqlite3.connect(self.path) as db:
            audit = SourceEpochAudit(db)
            audit.append("public", 1, "CONNECTED", at_ms=100)
            self.assertEqual(audit.recover_unclosed(at_ms=200), {"public": 1})
            self.assertEqual(audit.recover_unclosed(at_ms=201), {})
            self.assertEqual(audit.latest("public"), (1, "UNCLEAN_RESTART"))
            audit.append("public", 2, "CONNECTED", at_ms=202)
            audit.append("public", 2, "DISCONNECTED", at_ms=203)
            self.assertEqual(audit.latest("public"), (2, "DISCONNECTED"))


if __name__ == "__main__":
    unittest.main()
