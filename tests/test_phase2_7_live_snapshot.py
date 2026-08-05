import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from execution.live_snapshot import LiveSnapshotStore


class Phase27LiveSnapshotTests(unittest.TestCase):
    def _payload(self, *, balance=100.0, positions=None, orders=None, stops=None):
        return {
            "available_balance_usdt": balance,
            "positions": positions or [],
            "open_orders": orders or [],
            "protective_stops": stops or [],
            "user_stream_healthy": True,
            "reconciliation": {"status": "SAFE", "issues": []},
            "capabilities": {
                "adapter": "LiveExchange",
                "read_only": True,
                "supports_real_orders": False,
                "write_operations": "BLOCKED",
            },
        }

    def test_first_snapshot_creates_baseline(self):
        with tempfile.TemporaryDirectory() as root:
            store = LiveSnapshotStore(str(Path(root) / "snapshot.json"))
            current = self._payload()
            drift = store.compare(None, current)
            self.assertEqual(drift.status, "BASELINE_CREATED")
            self.assertTrue(drift.clean)

    def test_atomic_write_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "snapshot.json"
            store = LiveSnapshotStore(str(path))
            written = store.write(self._payload())
            loaded = store.load()
            self.assertEqual(loaded, written)
            self.assertEqual(loaded["version"], 1)
            self.assertTrue(path.exists())
            self.assertFalse(list(path.parent.glob("*.tmp")))

    def test_structural_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as root:
            store = LiveSnapshotStore(str(Path(root) / "snapshot.json"))
            previous = self._payload()
            current = self._payload(
                positions=[{"symbol": "BTCUSDT"}],
                orders=[{"symbol": "ETHUSDT"}],
                stops=[{"symbol": "SOLUSDT"}],
            )
            drift = store.compare(previous, current)
            self.assertEqual(drift.status, "DRIFT_DETECTED")
            self.assertIn("POSITION_SET_CHANGED", drift.issues)
            self.assertIn("OPEN_ORDER_SET_CHANGED", drift.issues)
            self.assertIn("PROTECTIVE_STOP_SET_CHANGED", drift.issues)

    def test_balance_change_is_reported_but_not_structural_issue(self):
        with tempfile.TemporaryDirectory() as root:
            store = LiveSnapshotStore(str(Path(root) / "snapshot.json"))
            drift = store.compare(
                self._payload(balance=100.0),
                self._payload(balance=95.5),
            )
            self.assertEqual(drift.status, "NO_STRUCTURAL_DRIFT")
            self.assertAlmostEqual(drift.balance_delta_usdt, -4.5)
            self.assertTrue(drift.clean)

    def test_invalid_snapshot_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "snapshot.json"
            path.write_text(json.dumps({"version": 999}))
            store = LiveSnapshotStore(str(path))
            with self.assertRaisesRegex(
                RuntimeError,
                "LIVE_SNAPSHOT_SCHEMA_INVALID",
            ):
                store.load()


if __name__ == "__main__":
    unittest.main()
