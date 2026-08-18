from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nbot.exchange.contracts import EntryPlan, Fill, ProtectiveStopRef
from nbot.execution.models import EntryInflight, OpenPosition
from nbot.execution.outcomes import ExecutionDurableStore, ExecutionHistoryStore, PendingOutcomeOutbox
from nbot.execution.state import ExecutionStateError


def payload(outcome_id="OUT-1"):
    return {
        "outcome_id": outcome_id,
        "proposal_id": "PROP-1",
        "symbol": "BTCUSDT",
        "side": "LONG",
        "realized_pnl_usd": 1.25,
        "closed_timestamp_ms": 1_700_000_100_000,
    }


def prepare_open(store: ExecutionDurableStore):
    plan = EntryPlan(
        symbol="BTCUSDT", side="LONG", quantity=0.01,
        expected_entry_price=100.0, initial_stop_price=95.0,
        initial_risk_usd=0.05, notional_usd=1.0, leverage=2,
    )
    fill = Fill(
        price=100.0, quantity=0.01, order_id="123", client_order_id="entry-1",
        timestamp_ms=1_700_000_000_000,
    )
    inflight = EntryInflight(
        proposal_id="PROP-1", entry_authority="TESTNET_MECHANICAL_ONLY",
        exit_policy_version="INTEGER_R_STEP_CONTROL", plan=plan,
        client_order_id="entry-1", started_at_ms=1_700_000_000_000,
    )
    pos = OpenPosition(
        proposal_id="PROP-1", symbol="BTCUSDT", side="LONG", entry_fill=fill,
        initial_risk_usd=0.05, initial_stop_price=95.0,
        protective_stop=ProtectiveStopRef(
            symbol="BTCUSDT", side="LONG", quantity=0.01,
            trigger_price=96.0, stop_id="STOP-1",
        ),
        entry_authority="TESTNET_MECHANICAL_ONLY",
        exit_policy_version="INTEGER_R_STEP_CONTROL",
    )
    store.state.reserve_proposal("PROP-1")
    store.state.begin_entry(inflight)
    store.state.record_inflight_fill(fill)
    store.state.promote_inflight_position(pos)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "history.jsonl"
        self.history = ExecutionHistoryStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_is_idempotent(self):
        self.assertTrue(self.history.append("OUT-1", payload()))
        self.assertFalse(self.history.append("OUT-1", payload()))
        self.assertEqual(len(self.history.records()), 1)

    def test_same_id_different_payload_is_collision(self):
        self.history.append("OUT-1", payload())
        changed = payload()
        changed["realized_pnl_usd"] = 999
        with self.assertRaisesRegex(ExecutionStateError, "HISTORY_ID_COLLISION"):
            self.history.append("OUT-1", changed)

    def test_corrupt_history_fails_closed_on_open(self):
        self.path.write_text('{"bad":')
        with self.assertRaisesRegex(ExecutionStateError, "HISTORY_CORRUPT"):
            ExecutionHistoryStore(self.path)

    def test_history_file_is_0600(self):
        self.history.append("OUT-1", payload())
        self.assertEqual(oct(self.path.stat().st_mode & 0o777), "0o600")

    def test_atomic_rewrite_failure_preserves_old_history(self):
        self.history.append("OUT-1", payload())
        before = self.path.read_bytes()
        with mock.patch("nbot.execution.outcomes.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                self.history.append("OUT-2", payload("OUT-2"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(self.history.records()), 1)


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "pending"
        self.outbox = PendingOutcomeOutbox(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_enqueue_is_idempotent_and_file_is_0600(self):
        self.assertTrue(self.outbox.enqueue("OUT-1", payload()))
        self.assertFalse(self.outbox.enqueue("OUT-1", payload()))
        self.assertEqual(self.outbox.pending_count(), 1)
        file_path = next(self.path.glob("*.json"))
        self.assertEqual(oct(file_path.stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct(self.path.stat().st_mode & 0o777), "0o700")

    def test_same_id_different_payload_is_collision(self):
        self.outbox.enqueue("OUT-1", payload())
        changed = payload()
        changed["realized_pnl_usd"] = 999
        with self.assertRaisesRegex(ExecutionStateError, "OUTBOX_ID_COLLISION"):
            self.outbox.enqueue("OUT-1", changed)

    def test_payload_outcome_id_must_match_storage_identity(self):
        with self.assertRaisesRegex(ExecutionStateError, "OUTCOME_ID_MISMATCH"):
            self.outbox.enqueue("OUT-1", payload("OUT-2"))

    def test_corrupt_outbox_fails_closed_on_open(self):
        bad = self.path / ("a" * 64 + ".json")
        bad.write_text('{"bad":')
        with self.assertRaisesRegex(ExecutionStateError, "OUTBOX_CORRUPT"):
            PendingOutcomeOutbox(self.path)

    def test_filename_identity_mismatch_fails_closed(self):
        self.outbox.enqueue("OUT-1", payload())
        original = next(self.path.glob("*.json"))
        wrong = self.path / ("b" * 64 + ".json")
        original.rename(wrong)
        with self.assertRaisesRegex(ExecutionStateError, "FILENAME_ID_MISMATCH"):
            PendingOutcomeOutbox(self.path)

    def test_acknowledge_removes_only_valid_record(self):
        self.outbox.enqueue("OUT-1", payload())
        self.assertTrue(self.outbox.acknowledge("OUT-1"))
        self.assertFalse(self.outbox.acknowledge("OUT-1"))
        self.assertEqual(self.outbox.pending_count(), 0)

    def test_non_json_finite_number_is_rejected(self):
        bad = payload()
        bad["realized_pnl_usd"] = float("nan")
        with self.assertRaisesRegex(ExecutionStateError, "OUTCOME_JSON_INVALID"):
            self.outbox.enqueue("OUT-1", bad)


class DurableCloseOrderingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = ExecutionDurableStore(self.root, profile="live-paper")
        prepare_open(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_close_persists_outbox_and_history_before_clearing_open(self):
        self.store.finalize_closed_position("OUT-1", payload())
        self.assertIsNone(self.store.state.open_position)
        self.assertEqual(self.store.outbox.pending_count(), 1)
        self.assertEqual(len(self.store.history.records()), 1)

    def test_restart_after_completed_close_keeps_pending_outcome(self):
        self.store.finalize_closed_position("OUT-1", payload())
        restarted = ExecutionDurableStore(self.root, profile="live-paper")
        self.assertIsNone(restarted.state.open_position)
        self.assertEqual(restarted.outbox.pending_count(), 1)
        self.assertEqual(len(restarted.history.records()), 1)

    def test_failure_clearing_state_leaves_open_plus_both_durable_close_records(self):
        with mock.patch.object(
            self.store.state,
            "_clear_open_after_durable_close",
            side_effect=OSError("simulated crash boundary"),
        ):
            with self.assertRaises(OSError):
                self.store.finalize_closed_position("OUT-1", payload())
        self.assertIsNotNone(self.store.state.open_position)
        self.assertEqual(self.store.outbox.pending_count(), 1)
        self.assertEqual(len(self.store.history.records()), 1)
        # Retry the whole close transaction: outbox/history must not duplicate.
        self.store.finalize_closed_position("OUT-1", payload())
        self.assertIsNone(self.store.state.open_position)
        self.assertEqual(self.store.outbox.pending_count(), 1)
        self.assertEqual(len(self.store.history.records()), 1)

    def test_incomplete_outcome_identity_does_not_clear_open_position(self):
        incomplete = {"outcome_id": "OUT-1", "realized_pnl_usd": 1.25}
        with self.assertRaisesRegex(ExecutionStateError, "OUTCOME_IDENTITY_INCOMPLETE"):
            self.store.finalize_closed_position("OUT-1", incomplete)
        self.assertIsNotNone(self.store.state.open_position)
        self.assertEqual(self.store.outbox.pending_count(), 0)
        self.assertEqual(self.store.history.records(), [])

    def test_outcome_identity_mismatch_does_not_clear_open_position(self):
        wrong = payload()
        wrong["proposal_id"] = "PROP-WRONG"
        with self.assertRaisesRegex(ExecutionStateError, "OUTCOME_PROPOSAL_MISMATCH"):
            self.store.finalize_closed_position("OUT-1", wrong)
        self.assertIsNotNone(self.store.state.open_position)
        self.assertEqual(self.store.outbox.pending_count(), 0)
        self.assertEqual(self.store.history.records(), [])

    def test_finalize_without_open_position_fails_closed(self):
        self.store.finalize_closed_position("OUT-1", payload())
        with self.assertRaisesRegex(ExecutionStateError, "FINALIZE_WITHOUT_OPEN_POSITION"):
            self.store.finalize_closed_position("OUT-1", payload())


if __name__ == "__main__":
    unittest.main()
