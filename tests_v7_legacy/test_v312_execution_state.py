from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nbot.exchange.contracts import EntryPlan, Fill, ProtectiveStopRef
from nbot.execution.models import DailyRisk, EntryInflight, ExecutionHealth, OpenPosition
from nbot.execution.state import (
    EXECUTION_STATE_VERSION,
    ExecutionStateError,
    ExecutionStatePaths,
    ExecutionStateStore,
    RecoveryMetadata,
)


def plan(side="LONG"):
    return EntryPlan(
        symbol="BTCUSDT",
        side=side,
        quantity=0.01,
        expected_entry_price=100.0,
        initial_stop_price=95.0 if side == "LONG" else 105.0,
        initial_risk_usd=0.05,
        notional_usd=1.0,
        leverage=2,
    )


def fill(client_order_id="entry-1"):
    return Fill(
        price=100.0,
        quantity=0.01,
        order_id="123",
        client_order_id=client_order_id,
        timestamp_ms=1_700_000_000_000,
    )


def inflight(with_fill=False):
    f = fill() if with_fill else None
    return EntryInflight(
        proposal_id="PROP-1",
        entry_authority="TESTNET_MECHANICAL_ONLY",
        exit_policy_version="INTEGER_R_STEP_CONTROL",
        plan=plan(),
        client_order_id="entry-1",
        started_at_ms=1_700_000_000_000,
        fill=f,
    )


def position():
    return OpenPosition(
        proposal_id="PROP-1",
        symbol="BTCUSDT",
        side="LONG",
        entry_fill=fill(),
        initial_risk_usd=0.05,
        initial_stop_price=95.0,
        protective_stop=ProtectiveStopRef(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            trigger_price=96.0,
            stop_id="STOP-1",
        ),
        entry_authority="TESTNET_MECHANICAL_ONLY",
        exit_policy_version="INTEGER_R_STEP_CONTROL",
    )


class ExecutionStatePathTests(unittest.TestCase):
    def test_profile_paths_are_strictly_separated(self):
        root = Path("/repo")
        t = ExecutionStatePaths.for_profile(root, "testnet-trade")
        p = ExecutionStatePaths.for_profile(root, "live-paper")
        r = ExecutionStatePaths.for_profile(root, "live-trade")
        self.assertEqual(t.base_dir, root / "data/execution/testnet")
        self.assertEqual(p.base_dir, root / "data/execution/paper")
        self.assertEqual(r.base_dir, root / "data/execution/real")
        self.assertEqual(t.market_environment, "TESTNET")
        self.assertEqual(p.market_environment, "LIVE")
        self.assertEqual(r.market_environment, "LIVE")
        self.assertEqual(len({t.base_dir, p.base_dir, r.base_dir}), 3)

    def test_unknown_profile_fails_closed(self):
        with self.assertRaisesRegex(ExecutionStateError, "EXECUTION_PROFILE_UNSUPPORTED"):
            ExecutionStatePaths.for_profile("/repo", "unsafe")


class ExecutionStateStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data/execution/paper/execution_state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def store(self):
        return ExecutionStateStore(self.path, profile="live-paper", market_environment="LIVE")

    def test_missing_state_is_created_fail_safe_and_atomic_shape_is_versioned(self):
        store = self.store()
        self.assertFalse(store.snapshot.entries_enabled)
        self.assertIsNone(store.open_position)
        self.assertIsNone(store.entry_inflight)
        raw = json.loads(self.path.read_text())
        self.assertEqual(raw["state_version"], EXECUTION_STATE_VERSION)
        self.assertEqual(raw["profile"], "live-paper")
        self.assertEqual(raw["market_environment"], "LIVE")
        self.assertEqual(oct(self.path.stat().st_mode & 0o777), "0o600")
        self.assertEqual(oct(self.path.parent.stat().st_mode & 0o777), "0o700")

    def test_restart_round_trip_preserves_instance_and_state(self):
        store = self.store()
        instance = store.snapshot.execution_instance_id
        store.set_entries_enabled(True)
        store.set_daily_risk(DailyRisk(utc_day="2026-08-18", realized_pnl_usd=2.0, peak_realized_pnl_usd=3.0, trades_closed=1))
        store.set_health(ExecutionHealth(prepare_calls=2, last_event="READY"))
        store.set_recovery(RecoveryMetadata(last_reconciliation_ms=123, last_event="FLAT_CONFIRMED"))
        reloaded = self.store()
        self.assertEqual(reloaded.snapshot.execution_instance_id, instance)
        self.assertTrue(reloaded.snapshot.entries_enabled)
        self.assertEqual(reloaded.daily_risk.realized_pnl_usd, 2.0)
        self.assertEqual(reloaded.health.prepare_calls, 2)
        self.assertEqual(reloaded.recovery.last_reconciliation_ms, 123)

    def test_corrupt_json_fails_closed(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{"state_version":')
        with self.assertRaisesRegex(ExecutionStateError, "EXECUTION_STATE_CORRUPT"):
            self.store()

    def test_wrong_schema_version_fails_closed(self):
        store = self.store()
        raw = store.export_dict()
        raw["state_version"] = "OLD"
        self.path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ExecutionStateError, "VERSION_MISMATCH"):
            self.store()

    def test_unknown_top_level_field_fails_closed(self):
        store = self.store()
        raw = store.export_dict()
        raw["invented"] = 1
        self.path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ExecutionStateError, "SCHEMA_INVALID"):
            self.store()

    def test_wrong_profile_fails_closed(self):
        store = self.store()
        raw = store.export_dict()
        raw["profile"] = "testnet-trade"
        raw["market_environment"] = "TESTNET"
        self.path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ExecutionStateError, "PROFILE_MISMATCH"):
            self.store()

    def test_constructor_rejects_profile_environment_mismatch(self):
        with self.assertRaisesRegex(ExecutionStateError, "PROFILE_ENVIRONMENT_MISMATCH"):
            ExecutionStateStore(self.path, profile="live-paper", market_environment="TESTNET")

    def test_open_and_inflight_together_is_rejected_on_load(self):
        store = self.store()
        raw = store.export_dict()
        raw["open_position"] = json.loads(json.dumps({
            "proposal_id": position().proposal_id,
            "symbol": position().symbol,
            "side": position().side,
            "entry_fill": {
                "price": 100.0, "quantity": 0.01, "order_id": "123",
                "client_order_id": "entry-1", "timestamp_ms": 1700000000000,
            },
            "initial_risk_usd": 0.05,
            "initial_stop_price": 95.0,
            "protective_stop": {
                "symbol": "BTCUSDT", "side": "LONG", "quantity": 0.01,
                "trigger_price": 96.0, "stop_id": "STOP-1", "client_stop_id": None,
            },
            "entry_authority": "TESTNET_MECHANICAL_ONLY",
            "exit_policy_version": "INTEGER_R_STEP_CONTROL",
            "mfe_r": 0.0,
            "mae_r": 0.0,
        }))
        raw["entry_inflight"] = {
            "proposal_id": "PROP-1", "entry_authority": "TESTNET_MECHANICAL_ONLY",
            "exit_policy_version": "INTEGER_R_STEP_CONTROL",
            "plan": {
                "symbol": "BTCUSDT", "side": "LONG", "quantity": 0.01,
                "expected_entry_price": 100.0, "initial_stop_price": 95.0,
                "initial_risk_usd": 0.05, "notional_usd": 1.0, "leverage": 2,
            },
            "client_order_id": "entry-1", "started_at_ms": 1700000000000, "fill": None,
        }
        self.path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ExecutionStateError, "OPEN_AND_INFLIGHT"):
            self.store()

    def test_proposal_reservation_persists_and_duplicate_returns_false(self):
        store = self.store()
        self.assertTrue(store.reserve_proposal("PROP-1"))
        self.assertFalse(store.reserve_proposal("PROP-1"))
        reloaded = self.store()
        self.assertTrue(reloaded.has_processed_proposal("PROP-1"))
        self.assertEqual(reloaded.snapshot.processed_proposal_ids, ("PROP-1",))

    def test_begin_entry_requires_durable_proposal_reservation(self):
        store = self.store()
        with self.assertRaisesRegex(ExecutionStateError, "PROPOSAL_NOT_RESERVED"):
            store.begin_entry(inflight())

    def test_entry_inflight_survives_restart_before_order_result(self):
        store = self.store()
        store.reserve_proposal("PROP-1")
        store.begin_entry(inflight())
        reloaded = self.store()
        self.assertEqual(reloaded.entry_inflight, inflight())
        self.assertTrue(reloaded.has_processed_proposal("PROP-1"))

    def test_inflight_fill_survives_restart(self):
        store = self.store()
        store.reserve_proposal("PROP-1")
        store.begin_entry(inflight())
        store.record_inflight_fill(fill())
        reloaded = self.store()
        self.assertEqual(reloaded.entry_inflight.fill, fill())

    def test_cannot_begin_second_entry(self):
        store = self.store()
        store.reserve_proposal("PROP-1")
        store.begin_entry(inflight())
        with self.assertRaisesRegex(ExecutionStateError, "ENTRY_ALREADY_INFLIGHT"):
            store.begin_entry(inflight())

    def test_promote_requires_fill(self):
        store = self.store()
        store.reserve_proposal("PROP-1")
        store.begin_entry(inflight())
        with self.assertRaisesRegex(ExecutionStateError, "ENTRY_FILL_MISSING"):
            store.promote_inflight_position(position())

    def test_protected_position_promotion_is_atomic_and_survives_restart(self):
        store = self.store()
        store.reserve_proposal("PROP-1")
        store.begin_entry(inflight())
        store.record_inflight_fill(fill())
        store.promote_inflight_position(position())
        self.assertIsNone(store.entry_inflight)
        self.assertEqual(store.open_position, position())
        reloaded = self.store()
        self.assertIsNone(reloaded.entry_inflight)
        self.assertEqual(reloaded.open_position, position())

    def test_open_position_identity_cannot_be_rewritten(self):
        store = self.store()
        store.reserve_proposal("PROP-1")
        store.begin_entry(inflight())
        store.record_inflight_fill(fill())
        store.promote_inflight_position(position())
        changed = OpenPosition(
            proposal_id="PROP-2",
            symbol=position().symbol,
            side=position().side,
            entry_fill=position().entry_fill,
            initial_risk_usd=position().initial_risk_usd,
            initial_stop_price=position().initial_stop_price,
            protective_stop=position().protective_stop,
            entry_authority=position().entry_authority,
            exit_policy_version=position().exit_policy_version,
        )
        with self.assertRaisesRegex(ExecutionStateError, "IDENTITY_CHANGED"):
            store.update_open_position(changed)

    def test_failed_atomic_replace_leaves_previous_state_intact(self):
        store = self.store()
        before = self.path.read_bytes()
        with mock.patch("nbot.execution.state.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                store.set_entries_enabled(True)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(store.snapshot.entries_enabled)
        self.assertFalse(self.store().snapshot.entries_enabled)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
