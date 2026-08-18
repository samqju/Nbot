from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from nbot.exchange.contracts import (
    AccountSnapshot,
    CloseFill,
    EntryPlan,
    ExchangePosition,
    Fill,
    ProtectiveStopRef,
    Quote,
)
from nbot.execution.models import DailyRisk, EntryInflight, OpenPosition
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.reconciliation import (
    ReconciliationConfig,
    ReconciliationCritical,
    ReconciliationExchangePort,
    ReconciliationLifecycle,
    ReconciliationResult,
)
from nbot.execution.risk import RiskConfig, RiskManager
from nbot.execution.state import ExecutionStateError, RecoveryMetadata


NOW = 1_800_100_000_000
POLICY = "INTEGER_R_STEP_CONTROL"
AUTHORITY = "TESTNET_MECHANICAL_ONLY"


class FakeClock:
    def __init__(self):
        self.value = 100.0
        self.sleep_calls = []
        self.on_sleep = None

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.sleep_calls.append(seconds)
        self.value += seconds
        if self.on_sleep is not None:
            self.on_sleep(len(self.sleep_calls))


class FakeReconciliationExchange:
    def __init__(self):
        self.connected = 0
        self.healthy = True
        self.position = None
        self.stop = None
        self.quote_value = Quote("BTCUSDT", 99.9, 100.1, NOW)
        self.balance = 10_000.0
        self.position_error = None
        self.stop_error = None
        self.quote_error = None
        self.cleanup_error = None
        self.ensure_error = None
        self.recover_entry_error = None
        self.recover_close_error = None
        self.recover_inflight_close_error = None
        self.validate_result = True
        self.recovered_fill = None
        self.recovered_close = CloseFill(
            99.0,
            NOW + 1_000,
            "EXCHANGE_FLAT_RECOVERED_AFTER_RESTART",
            realized_pnl_usd=-10.0,
            order_ids=("CLOSE-1",),
            source="USER_TRADES",
            theoretical_pnl_usd=-10.0,
            pnl_variance_usd=0.0,
        )
        self.recovered_inflight_close = self.recovered_close
        self.orphans = 0
        self.cleanup_calls = 0
        self.position_calls = 0
        self.stop_calls = 0
        self.quote_calls = 0
        self.recover_entry_calls = []
        self.ensure_calls = []
        self.validate_calls = []
        self.open_calls = 0
        self.recover_close_calls = 0
        self.recover_inflight_close_calls = 0
        self.stop_seq = 1

    def connect(self):
        self.connected += 1

    def is_healthy(self):
        return self.healthy

    def quote(self, symbol):
        self.quote_calls += 1
        if self.quote_error is not None:
            raise self.quote_error
        return self.quote_value

    def account_snapshot(self):
        return AccountSnapshot(self.balance)

    def position_snapshot(self):
        self.position_calls += 1
        if self.position_error is not None:
            raise self.position_error
        return self.position

    def protective_stop_snapshot(self, symbol):
        self.stop_calls += 1
        if self.stop_error is not None:
            raise self.stop_error
        return self.stop

    def validate_protective_stop(self, symbol, side, stop_price):
        self.validate_calls.append((symbol, side, stop_price))
        return self.validate_result

    def set_leverage(self, symbol, leverage):
        return None

    def open_market(self, plan, *, client_order_id):
        self.open_calls += 1
        raise AssertionError("reconciliation must never submit a new market entry")

    def recover_inflight_entry(self, plan, *, client_order_id):
        self.recover_entry_calls.append((plan, client_order_id))
        if self.recover_entry_error is not None:
            raise self.recover_entry_error
        return self.recovered_fill

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        self.ensure_calls.append((symbol, side, quantity, stop_price))
        if self.ensure_error is not None:
            raise self.ensure_error
        self.stop_seq += 1
        self.stop = ProtectiveStopRef(
            symbol,
            side,
            quantity,
            stop_price,
            stop_id=f"STOP-{self.stop_seq}",
            client_stop_id=f"CID-{self.stop_seq}",
        )
        return self.stop

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        return self.ensure_protective_stop(symbol, side, quantity, stop_price)

    def close_position(self, symbol, side, *, reason):
        self.position = None
        return CloseFill(99.0, NOW + 2_000, reason, realized_pnl_usd=-10.0)

    def recover_closed_position(self, local_position):
        self.recover_close_calls += 1
        if self.recover_close_error is not None:
            raise self.recover_close_error
        return self.recovered_close

    def cleanup_orphan_protective_stops(self):
        self.cleanup_calls += 1
        if self.cleanup_error is not None:
            raise self.cleanup_error
        removed = self.orphans
        self.orphans = 0
        self.stop = None if self.position is None else self.stop
        return removed

    def recover_closed_inflight_entry(self, inflight):
        self.recover_inflight_close_calls += 1
        if self.recover_inflight_close_error is not None:
            raise self.recover_inflight_close_error
        return self.recovered_inflight_close


class FakeEmergency:
    def __init__(self, exchange):
        self.exchange = exchange
        self.calls = []
        self.error = None
        self.leave_open = False

    def flatten_verified(self, symbol, side, *, reason):
        self.calls.append((symbol, side, reason))
        if self.error is not None:
            raise self.error
        if not self.leave_open:
            self.exchange.position = None


class IncompleteExchange:
    pass


class ReconciliationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.durable = ExecutionDurableStore(self.root, profile="live-paper")
        self.state = self.durable.state
        self.risk = RiskManager()
        self.exchange = FakeReconciliationExchange()
        self.emergency = FakeEmergency(self.exchange)
        self.clock = FakeClock()

    def lifecycle(self, *, config=None, now_ms=lambda: NOW):
        return ReconciliationLifecycle(
            exchange=self.exchange,
            durable=self.durable,
            risk=self.risk,
            emergency=self.emergency,
            config=config or ReconciliationConfig(stop_trigger_grace_seconds=0.0),
            now_ms=now_ms,
            monotonic=self.clock.monotonic,
            sleep=self.clock.sleep,
        )

    def make_inflight(self, *, side="LONG", with_fill=False, proposal_id="PROP-1"):
        stop = 99.0 if side == "LONG" else 101.0
        plan = EntryPlan("BTCUSDT", side, 10.0, 100.0, stop, 10.0, 1000.0, 5)
        fill = Fill(100.0, 10.0, "ENTRY-1", "CLIENT-1", NOW - 20_000)
        self.assertTrue(self.state.reserve_proposal(proposal_id))
        self.state.begin_entry(
            EntryInflight(
                proposal_id=proposal_id,
                entry_authority=AUTHORITY,
                exit_policy_version=POLICY,
                plan=plan,
                client_order_id="CLIENT-1",
                started_at_ms=NOW - 30_000,
            )
        )
        if with_fill:
            self.state.record_inflight_fill(fill)
        return plan, fill

    def make_open(
        self,
        *,
        side="LONG",
        stop_price=None,
        initial_stop=None,
        proposal_id="PROP-OPEN",
        mfe_r=0.0,
        mae_r=0.0,
    ):
        if initial_stop is None:
            initial_stop = 99.0 if side == "LONG" else 101.0
        if stop_price is None:
            stop_price = initial_stop
        plan, fill = self.make_inflight(side=side, with_fill=True, proposal_id=proposal_id)
        stop = ProtectiveStopRef(
            "BTCUSDT",
            side,
            10.0,
            stop_price,
            stop_id="STOP-1",
            client_stop_id="CID-1",
        )
        position = OpenPosition(
            proposal_id=proposal_id,
            symbol="BTCUSDT",
            side=side,
            entry_fill=fill,
            initial_risk_usd=10.0,
            initial_stop_price=initial_stop,
            protective_stop=stop,
            entry_authority=AUTHORITY,
            exit_policy_version=POLICY,
            mfe_r=mfe_r,
            mae_r=mae_r,
        )
        self.state.promote_inflight_position(position)
        self.exchange.position = ExchangePosition("BTCUSDT", side, 10.0, 100.0)
        self.exchange.stop = stop
        return position


class ConfigAndBoundaryTests(ReconciliationTestCase):
    def test_default_parity_settlement_config(self):
        cfg = ReconciliationConfig()
        self.assertEqual(cfg.stop_trigger_grace_seconds, 8.0)
        self.assertEqual(cfg.stop_trigger_poll_interval_seconds, 0.5)

    def test_negative_grace_rejected(self):
        with self.assertRaisesRegex(ValueError, "STOP_TRIGGER_GRACE_SECONDS_INVALID"):
            ReconciliationConfig(stop_trigger_grace_seconds=-1)

    def test_grace_above_sixty_rejected(self):
        with self.assertRaisesRegex(ValueError, "STOP_TRIGGER_GRACE_SECONDS_INVALID"):
            ReconciliationConfig(stop_trigger_grace_seconds=61)

    def test_nonpositive_poll_interval_rejected(self):
        with self.assertRaisesRegex(ValueError, "STOP_TRIGGER_POLL_INTERVAL_SECONDS_INVALID"):
            ReconciliationConfig(stop_trigger_poll_interval_seconds=0)

    def test_bool_config_rejected(self):
        with self.assertRaises(ValueError):
            ReconciliationConfig(stop_trigger_grace_seconds=True)

    def test_extended_exchange_port_runtime_contract(self):
        self.assertIsInstance(self.exchange, ReconciliationExchangePort)

    def test_incomplete_exchange_rejected_at_construction(self):
        with self.assertRaisesRegex(TypeError, "RECONCILIATION_EXCHANGE_PORT_INCOMPLETE"):
            ReconciliationLifecycle(
                exchange=IncompleteExchange(),
                durable=self.durable,
                risk=self.risk,
                emergency=self.emergency,
            )


class FlatTruthTests(ReconciliationTestCase):
    def test_flat_flat_is_clean_and_connects(self):
        result = self.lifecycle().reconcile()
        self.assertEqual(result, ReconciliationResult(status="FLAT"))
        self.assertEqual(self.exchange.connected, 1)
        self.assertEqual(self.state.recovery.last_reconciliation_ms, NOW)
        self.assertFalse(self.state.recovery.critical)

    def test_flat_orphans_are_removed_before_clean_result(self):
        self.exchange.orphans = 3
        result = self.lifecycle().reconcile()
        self.assertEqual(result.orphans_removed, 3)
        self.assertEqual(self.exchange.orphans, 0)

    def test_orphan_cleanup_failure_blocks_entries(self):
        self.state.set_entries_enabled(True)
        self.exchange.cleanup_error = RuntimeError("cancel failed")
        with self.assertRaisesRegex(ReconciliationCritical, "ORPHAN_STOP_CLEANUP_FAILED"):
            self.lifecycle().reconcile()
        self.assertFalse(self.state.snapshot.entries_enabled)
        self.assertTrue(self.state.recovery.critical)

    def test_unmanaged_exchange_position_fails_closed(self):
        self.state.set_entries_enabled(True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 1.0, 100.0)
        with self.assertRaisesRegex(ReconciliationCritical, "UNMANAGED_EXCHANGE_POSITION"):
            self.lifecycle().reconcile()
        self.assertFalse(self.state.snapshot.entries_enabled)

    def test_unhealthy_exchange_fails_closed_before_position_truth(self):
        self.exchange.healthy = False
        with self.assertRaisesRegex(ReconciliationCritical, "EXCHANGE_UNHEALTHY"):
            self.lifecycle().reconcile()
        self.assertEqual(self.exchange.position_calls, 0)

    def test_position_snapshot_error_fails_closed(self):
        self.exchange.position_error = RuntimeError("api down")
        with self.assertRaisesRegex(ReconciliationCritical, "EXCHANGE_POSITION_SNAPSHOT_FAILED"):
            self.lifecycle().reconcile()

    def test_invalid_reconciliation_clock_fails_closed(self):
        with self.assertRaisesRegex(ReconciliationCritical, "RECONCILIATION_TIME_INVALID"):
            self.lifecycle(now_ms=lambda: 0).reconcile()

    def test_success_clears_previous_recovery_critical(self):
        self.state.set_recovery(
            RecoveryMetadata(
                last_reconciliation_ms=NOW - 1,
                critical=True,
                critical_reason="OLD_FAILURE",
                last_event="OLD_FAILURE",
            )
        )
        self.lifecycle().reconcile()
        self.assertFalse(self.state.recovery.critical)
        self.assertEqual(self.state.recovery.last_event, "FLAT")

    def test_reconciliation_health_counter_increments(self):
        self.lifecycle().reconcile()
        self.assertEqual(self.state.health.reconciliations, 1)
        self.assertEqual(self.state.health.last_event, "FLAT")


class OpenPositionIdentityTests(ReconciliationTestCase):
    def test_matching_open_position_and_stop_reconcile(self):
        self.make_open()
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_RECONCILED")
        self.assertIsNotNone(self.state.open_position)

    def test_tighter_stop_is_adopted_without_loosening(self):
        self.make_open(stop_price=99.0)
        tighter = ProtectiveStopRef("BTCUSDT", "LONG", 10.0, 99.5, stop_id="S2")
        self.exchange.stop = tighter
        self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position.stop_price, 99.5)
        self.assertEqual(self.state.open_position.protective_stop.stop_id, "S2")

    def test_symbol_mismatch_fails_closed(self):
        self.make_open()
        self.exchange.position = ExchangePosition("ETHUSDT", "LONG", 10.0, 100.0)
        with self.assertRaisesRegex(ReconciliationCritical, "POSITION_SYMBOL_MISMATCH"):
            self.lifecycle().reconcile()

    def test_side_mismatch_fails_closed(self):
        self.make_open()
        self.exchange.position = ExchangePosition("BTCUSDT", "SHORT", 10.0, 100.0)
        with self.assertRaisesRegex(ReconciliationCritical, "POSITION_SIDE_MISMATCH"):
            self.lifecycle().reconcile()

    def test_quantity_mismatch_fails_closed(self):
        self.make_open()
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 9.0, 100.0)
        with self.assertRaisesRegex(ReconciliationCritical, "POSITION_QUANTITY_MISMATCH"):
            self.lifecycle().reconcile()

    def test_entry_price_mismatch_fails_closed(self):
        self.make_open()
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 101.0)
        with self.assertRaisesRegex(ReconciliationCritical, "POSITION_ENTRY_PRICE_MISMATCH"):
            self.lifecycle().reconcile()

    def test_stop_snapshot_error_preserves_open_state(self):
        local = self.make_open()
        self.exchange.stop_error = RuntimeError("stop endpoint down")
        with self.assertRaisesRegex(ReconciliationCritical, "PROTECTIVE_STOP_SNAPSHOT_FAILED"):
            self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position, local)

    def test_wrong_stop_identity_is_repaired(self):
        self.make_open()
        self.exchange.stop = ProtectiveStopRef("BTCUSDT", "LONG", 9.0, 99.0, stop_id="BAD")
        result = self.lifecycle().reconcile()
        self.assertTrue(result.recovered_stop)
        self.assertEqual(self.state.open_position.protective_stop.quantity, 10.0)
        self.assertTrue(self.exchange.ensure_calls)

    def test_looser_stop_is_repaired_to_last_known_protection(self):
        self.make_open(stop_price=99.5, initial_stop=99.0)
        self.exchange.stop = ProtectiveStopRef("BTCUSDT", "LONG", 10.0, 99.0, stop_id="LOOSE")
        result = self.lifecycle().reconcile()
        self.assertTrue(result.recovered_stop)
        self.assertGreaterEqual(self.state.open_position.stop_price, 99.5)


class StopRecoveryTests(ReconciliationTestCase):
    def test_missing_stop_safe_price_is_restored(self):
        self.make_open()
        self.exchange.stop = None
        result = self.lifecycle().reconcile()
        self.assertTrue(result.recovered_stop)
        self.assertEqual(self.state.health.stop_missing_events, 1)
        self.assertEqual(self.state.health.stop_recoveries, 1)
        self.assertIsNotNone(self.exchange.stop)

    def test_missing_stop_reappears_during_grace_without_replacement(self):
        self.make_open()
        self.exchange.stop = None
        self.clock.on_sleep = lambda n: setattr(
            self.exchange,
            "stop",
            ProtectiveStopRef("BTCUSDT", "LONG", 10.0, 99.0, stop_id="REAPPEARED"),
        ) if n == 1 else None
        cfg = ReconciliationConfig(stop_trigger_grace_seconds=1.0, stop_trigger_poll_interval_seconds=0.1)
        result = self.lifecycle(config=cfg).reconcile()
        self.assertEqual(result.status, "POSITION_RECONCILED")
        self.assertFalse(self.exchange.ensure_calls)

    def test_missing_stop_position_closes_during_grace(self):
        self.make_open()
        self.exchange.stop = None
        self.clock.on_sleep = lambda n: setattr(self.exchange, "position", None) if n == 1 else None
        cfg = ReconciliationConfig(stop_trigger_grace_seconds=1.0, stop_trigger_poll_interval_seconds=0.1)
        result = self.lifecycle(config=cfg).reconcile()
        self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
        self.assertIsNone(self.state.open_position)
        self.assertEqual(self.durable.outbox.pending_count(), 1)

    def test_missing_stop_already_breached_emergency_closes_after_grace(self):
        self.make_open()
        self.exchange.stop = None
        self.exchange.quote_value = Quote("BTCUSDT", 98.9, 99.0, NOW)
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_EMERGENCY_CLOSED")
        self.assertEqual(self.emergency.calls[-1][2], "RECOVERY_BREACHED_STOP")
        self.assertIsNone(self.state.open_position)

    def test_active_breached_stop_settles_during_grace(self):
        self.make_open()
        self.exchange.quote_value = Quote("BTCUSDT", 98.9, 99.0, NOW)
        self.clock.on_sleep = lambda n: setattr(self.exchange, "position", None) if n == 1 else None
        cfg = ReconciliationConfig(stop_trigger_grace_seconds=1.0, stop_trigger_poll_interval_seconds=0.1)
        result = self.lifecycle(config=cfg).reconcile()
        self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
        self.assertFalse(self.emergency.calls)

    def test_active_breached_stop_unsettled_uses_emergency(self):
        self.make_open()
        self.exchange.quote_value = Quote("BTCUSDT", 98.9, 99.0, NOW)
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_EMERGENCY_CLOSED")
        self.assertEqual(self.emergency.calls[-1][2], "LOCAL_STOP_BREACH_UNSETTLED")

    def test_stop_validation_false_uses_emergency(self):
        self.make_open()
        self.exchange.stop = None
        self.exchange.validate_result = False
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_EMERGENCY_CLOSED")
        self.assertIn("UNRESTORABLE", self.emergency.calls[-1][2])

    def test_stop_ensure_failure_uses_emergency(self):
        self.make_open()
        self.exchange.stop = None
        self.exchange.ensure_error = RuntimeError("stop post failed")
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_EMERGENCY_CLOSED")
        self.assertIn("RECOVERY_FAILED", self.emergency.calls[-1][2])

    def test_emergency_failure_preserves_open_position(self):
        local = self.make_open()
        self.exchange.stop = None
        self.exchange.validate_result = False
        self.emergency.error = RuntimeError("cannot prove flat")
        with self.assertRaisesRegex(ReconciliationCritical, "EMERGENCY_FAILED"):
            self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position, local)

    def test_emergency_claim_without_flatness_is_rejected(self):
        local = self.make_open()
        self.exchange.stop = None
        self.exchange.validate_result = False
        self.emergency.leave_open = True
        with self.assertRaisesRegex(ReconciliationCritical, "EMERGENCY_NOT_FLAT"):
            self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position, local)

    def test_quote_failure_during_missing_stop_recovery_fails_closed(self):
        self.make_open()
        self.exchange.stop = None
        self.exchange.quote_error = RuntimeError("quote down")
        with self.assertRaisesRegex(ReconciliationCritical, "EXECUTION_QUOTE_FAILED"):
            self.lifecycle().reconcile()


class CloseRecoveryTests(ReconciliationTestCase):
    def test_exchange_flat_recovers_authoritative_close_and_daily_risk(self):
        self.make_open(mfe_r=2.0, mae_r=-0.5)
        self.exchange.position = None
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
        self.assertIsNone(self.state.open_position)
        self.assertEqual(self.state.daily_risk.realized_pnl_usd, -10.0)
        self.assertEqual(self.state.daily_risk.trades_closed, 1)
        self.assertEqual(self.durable.outbox.pending_count(), 1)
        rows = self.durable.history.records()
        self.assertEqual(len(rows), 1)
        payload = rows[0]["payload"]
        self.assertEqual(payload["realized_pnl_usd"], -10.0)
        self.assertEqual(payload["mfe_r"], 2.0)
        self.assertEqual(payload["mae_r"], -0.5)

    def test_zero_realized_close_is_valid_accounting(self):
        self.make_open()
        self.exchange.position = None
        self.exchange.recovered_close = replace(self.exchange.recovered_close, realized_pnl_usd=0.0)
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
        self.assertEqual(self.state.daily_risk.realized_pnl_usd, 0.0)

    def test_missing_realized_pnl_never_finalizes(self):
        local = self.make_open()
        self.exchange.position = None
        self.exchange.recovered_close = replace(self.exchange.recovered_close, realized_pnl_usd=None)
        with self.assertRaisesRegex(ReconciliationCritical, "CLOSE_ACCOUNTING_UNRESOLVED"):
            self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position, local)
        self.assertEqual(self.durable.outbox.pending_count(), 0)

    def test_close_timestamp_before_entry_never_finalizes(self):
        local = self.make_open()
        self.exchange.position = None
        self.exchange.recovered_close = replace(self.exchange.recovered_close, timestamp_ms=NOW - 30_000)
        with self.assertRaisesRegex(ReconciliationCritical, "CLOSE_TIMESTAMP_PRECEDES_ENTRY"):
            self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position, local)

    def test_close_recovery_error_preserves_open(self):
        local = self.make_open()
        self.exchange.position = None
        self.exchange.recover_close_error = RuntimeError("history incomplete")
        with self.assertRaisesRegex(ReconciliationCritical, "EXTERNAL_CLOSE_RECOVERY_FAILED"):
            self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position, local)

    def test_orphan_cleanup_failure_after_close_evidence_preserves_open_and_no_outcome(self):
        local = self.make_open()
        self.exchange.position = None
        self.exchange.cleanup_error = RuntimeError("orphan remains")
        with self.assertRaisesRegex(ReconciliationCritical, "ORPHAN_STOP_CLEANUP_FAILED"):
            self.lifecycle().reconcile()
        self.assertEqual(self.state.open_position, local)
        self.assertEqual(self.durable.outbox.pending_count(), 0)
        self.assertEqual(self.durable.history.records(), [])

    def test_outcome_id_is_deterministic_for_same_entry_identity(self):
        local = self.make_open()
        lifecycle = self.lifecycle()
        first = lifecycle._deterministic_outcome_id(proposal_id=local.proposal_id, entry_fill=local.entry_fill)
        second = lifecycle._deterministic_outcome_id(proposal_id=local.proposal_id, entry_fill=local.entry_fill)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("OUT-"))

    def test_close_payload_keeps_exchange_accounting_audit(self):
        self.make_open()
        self.exchange.position = None
        self.lifecycle().reconcile()
        payload = self.durable.history.records()[0]["payload"]
        self.assertEqual(payload["close_source"], "USER_TRADES")
        self.assertEqual(payload["close_order_ids"], ["CLOSE-1"])
        self.assertEqual(payload["theoretical_pnl_usd"], -10.0)
        self.assertEqual(payload["pnl_variance_usd"], 0.0)

    def test_atomic_state_clear_and_daily_update_retry_does_not_double_apply(self):
        self.make_open()
        self.exchange.position = None
        original = self.state._clear_open_after_durable_close
        calls = {"n": 0}

        def fail_once(*, daily_risk=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ExecutionStateError("simulated crash before final state commit")
            return original(daily_risk=daily_risk)

        with mock.patch.object(self.state, "_clear_open_after_durable_close", side_effect=fail_once):
            with self.assertRaisesRegex(ReconciliationCritical, "CLOSE_DURABILITY_FAILED"):
                self.lifecycle().reconcile()
        self.assertIsNotNone(self.state.open_position)
        self.assertEqual(self.state.daily_risk.realized_pnl_usd, 0.0)
        self.assertEqual(self.durable.outbox.pending_count(), 1)
        self.assertEqual(len(self.durable.history.records()), 1)

        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "POSITION_CLOSE_RECOVERED")
        self.assertEqual(self.state.daily_risk.realized_pnl_usd, -10.0)
        self.assertEqual(self.state.daily_risk.trades_closed, 1)
        self.assertEqual(len(self.durable.history.records()), 1)
        self.assertEqual(self.durable.outbox.pending_count(), 1)


class InflightRecoveryTests(ReconciliationTestCase):
    def test_known_unfilled_inflight_exchange_flat_is_cleared_without_new_order(self):
        self.make_inflight(with_fill=False)
        self.exchange.recovered_fill = None
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "ENTRY_INFLIGHT_PROVEN_UNFILLED")
        self.assertIsNone(self.state.entry_inflight)
        self.assertEqual(self.exchange.open_calls, 0)
        self.assertEqual(len(self.exchange.recover_entry_calls), 1)

    def test_unfilled_inflight_with_exchange_position_fails_closed(self):
        self.make_inflight(with_fill=False)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.exchange.recovered_fill = None
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_NOT_FILLED_BUT_POSITION_EXISTS"):
            self.lifecycle().reconcile()
        self.assertIsNotNone(self.state.entry_inflight)

    def test_inflight_recovery_error_preserves_journal(self):
        self.make_inflight(with_fill=False)
        self.exchange.recover_entry_error = RuntimeError("ambiguous")
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_RECOVERY_FAILED"):
            self.lifecycle().reconcile()
        self.assertIsNotNone(self.state.entry_inflight)

    def test_recovered_fill_open_position_promotes_after_protection(self):
        plan, fill = self.make_inflight(with_fill=False)
        self.exchange.recovered_fill = fill
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.exchange.stop = ProtectiveStopRef("BTCUSDT", "LONG", 10.0, 99.0, stop_id="S1")
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "ENTRY_INFLIGHT_RECOVERED_OPEN")
        self.assertIsNone(self.state.entry_inflight)
        self.assertIsNotNone(self.state.open_position)
        self.assertEqual(self.exchange.open_calls, 0)
        self.assertEqual(self.state.open_position.entry_fill, fill)

    def test_persisted_inflight_fill_does_not_query_entry_order_again(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.exchange.stop = ProtectiveStopRef("BTCUSDT", "LONG", 10.0, 99.0, stop_id="S1")
        self.lifecycle().reconcile()
        self.assertEqual(self.exchange.recover_entry_calls, [])

    def test_recovered_fill_wrong_client_identity_fails_closed(self):
        self.make_inflight(with_fill=False)
        self.exchange.recovered_fill = Fill(100.0, 10.0, "ENTRY-1", "OTHER", NOW - 20_000)
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_CLIENT_ORDER_ID_MISMATCH"):
            self.lifecycle().reconcile()

    def test_inflight_open_symbol_mismatch_fails_closed(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("ETHUSDT", "LONG", 10.0, 100.0)
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_POSITION_SYMBOL_MISMATCH"):
            self.lifecycle().reconcile()

    def test_inflight_open_side_mismatch_fails_closed(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "SHORT", 10.0, 100.0)
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_POSITION_SIDE_MISMATCH"):
            self.lifecycle().reconcile()

    def test_inflight_open_quantity_mismatch_fails_closed(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 9.0, 100.0)
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_POSITION_QUANTITY_MISMATCH"):
            self.lifecycle().reconcile()

    def test_inflight_open_entry_price_mismatch_fails_closed(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 101.0)
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_POSITION_ENTRY_PRICE_MISMATCH"):
            self.lifecycle().reconcile()

    def test_inflight_missing_stop_is_restored_then_promoted(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.exchange.stop = None
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "ENTRY_INFLIGHT_RECOVERED_OPEN")
        self.assertTrue(self.exchange.ensure_calls)
        self.assertEqual(self.state.health.stop_recoveries, 1)

    def test_inflight_exchange_flat_recovers_close_and_clears_journal(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = None
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "ENTRY_INFLIGHT_CLOSE_RECOVERED")
        self.assertIsNone(self.state.entry_inflight)
        self.assertEqual(self.durable.outbox.pending_count(), 1)
        self.assertEqual(self.state.daily_risk.trades_closed, 1)

    def test_inflight_close_without_realized_accounting_stays_fail_closed(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = None
        self.exchange.recovered_inflight_close = replace(
            self.exchange.recovered_inflight_close,
            realized_pnl_usd=None,
        )
        with self.assertRaisesRegex(ReconciliationCritical, "CLOSE_ACCOUNTING_UNRESOLVED"):
            self.lifecycle().reconcile()
        self.assertIsNotNone(self.state.entry_inflight)
        self.assertEqual(self.durable.outbox.pending_count(), 0)

    def test_inflight_close_cleanup_failure_preserves_journal_and_no_outcome(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = None
        self.exchange.cleanup_error = RuntimeError("orphan remains")
        with self.assertRaisesRegex(ReconciliationCritical, "ORPHAN_STOP_CLEANUP_FAILED"):
            self.lifecycle().reconcile()
        self.assertIsNotNone(self.state.entry_inflight)
        self.assertEqual(self.durable.outbox.pending_count(), 0)

    def test_inflight_post_fill_notional_violation_emergency_closes(self):
        plan, fill = self.make_inflight(with_fill=False)
        bad_fill = Fill(100.0, 8.0, "ENTRY-1", "CLIENT-1", NOW - 20_000)
        self.exchange.recovered_fill = bad_fill
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 8.0, 100.0)
        self.exchange.stop = ProtectiveStopRef("BTCUSDT", "LONG", 8.0, 98.75, stop_id="S1")
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "ENTRY_INFLIGHT_EMERGENCY_CLOSED")
        self.assertEqual(self.emergency.calls[-1][2], "POST_FILL_NOTIONAL_BREACH")
        self.assertIsNone(self.state.entry_inflight)

    def test_inflight_stop_infeasible_emergency_closes_and_settles(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.exchange.stop = None
        self.exchange.validate_result = False
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "ENTRY_INFLIGHT_EMERGENCY_CLOSED")
        self.assertEqual(self.emergency.calls[-1][2], "ENTRY_INFLIGHT_STOP_UNRESTORABLE")
        self.assertIsNone(self.state.entry_inflight)

    def test_inflight_stop_ensure_failure_emergency_closes_and_settles(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.exchange.stop = None
        self.exchange.ensure_error = RuntimeError("stop write failed")
        result = self.lifecycle().reconcile()
        self.assertEqual(result.status, "ENTRY_INFLIGHT_EMERGENCY_CLOSED")
        self.assertEqual(self.emergency.calls[-1][2], "ENTRY_INFLIGHT_PROTECTION_RECOVERY_FAILED")

    def test_inflight_emergency_close_recovery_failure_preserves_journal(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.exchange.stop = None
        self.exchange.validate_result = False
        self.exchange.recover_inflight_close_error = RuntimeError("accounting unavailable")
        with self.assertRaisesRegex(ReconciliationCritical, "ENTRY_INFLIGHT_CLOSE_RECOVERY_FAILED"):
            self.lifecycle().reconcile()
        self.assertIsNotNone(self.state.entry_inflight)

    def test_inflight_outcome_marks_recovered_crash_window(self):
        plan, fill = self.make_inflight(with_fill=True)
        self.exchange.position = None
        self.lifecycle().reconcile()
        payload = self.durable.history.records()[0]["payload"]
        self.assertTrue(payload["recovered_from_entry_inflight"])
        self.assertEqual(payload["entry_client_order_id"], "CLIENT-1")


class DailyAndDurabilityExtensionTests(ReconciliationTestCase):
    def test_state_open_clear_can_atomically_apply_daily_risk(self):
        self.make_open()
        daily = DailyRisk(
            utc_day="2027-01-15",
            realized_pnl_usd=5.0,
            peak_realized_pnl_usd=5.0,
            trades_closed=1,
        )
        self.state._clear_open_after_durable_close(daily_risk=daily)
        self.assertIsNone(self.state.open_position)
        self.assertEqual(self.state.daily_risk, daily)

    def test_state_inflight_clear_can_atomically_apply_daily_risk(self):
        self.make_inflight(with_fill=True)
        daily = DailyRisk(
            utc_day="2027-01-15",
            realized_pnl_usd=-5.0,
            peak_realized_pnl_usd=0.0,
            trades_closed=1,
        )
        self.state._clear_inflight_after_durable_close(daily_risk=daily)
        self.assertIsNone(self.state.entry_inflight)
        self.assertEqual(self.state.daily_risk, daily)

    def test_durable_inflight_finalizer_rejects_identity_mismatch(self):
        self.make_inflight(with_fill=True)
        payload = {
            "outcome_id": "OUT-X",
            "proposal_id": "WRONG",
            "symbol": "BTCUSDT",
            "side": "LONG",
        }
        with self.assertRaisesRegex(ExecutionStateError, "EXECUTION_OUTCOME_PROPOSAL_MISMATCH"):
            self.durable.finalize_closed_inflight("OUT-X", payload)
        self.assertIsNotNone(self.state.entry_inflight)

    def test_daily_rollover_happens_during_reconciliation(self):
        self.state.set_daily_risk(
            DailyRisk(
                utc_day="2026-01-01",
                realized_pnl_usd=50.0,
                peak_realized_pnl_usd=50.0,
                halted=True,
                halt_reason="DAILY_RISK_FLOOR",
                trades_closed=3,
            )
        )
        self.lifecycle().reconcile()
        self.assertNotEqual(self.state.daily_risk.utc_day, "2026-01-01")
        self.assertEqual(self.state.daily_risk.realized_pnl_usd, 0.0)
        self.assertFalse(self.state.daily_risk.halted)


if __name__ == "__main__":
    unittest.main()
