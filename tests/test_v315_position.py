import math
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

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
from nbot.execution.position import (
    INTEGER_R_STEP_CONTROL,
    ExecutionHealthMonitor,
    PositionLifecycle,
    PositionManageResult,
    PositionReconciliationRequired,
    PositionSafetyError,
)
from nbot.execution.risk import RiskManager
from nbot.execution.state import ExecutionStateError, ExecutionStateStore


NOW = 1_800_000_000_000


class FakeEmergency:
    def __init__(self):
        self.calls = []
        self.fail = False

    def flatten_verified(self, symbol, side, *, reason):
        self.calls.append((symbol, side, reason))
        if self.fail:
            raise RuntimeError("cannot prove flat")


class FakeExchange:
    def __init__(self, *, side="LONG", stop_price=99.0):
        self.side = side
        self.position = ExchangePosition("BTCUSDT", side, 10.0, 100.0)
        self.stop = ProtectiveStopRef(
            "BTCUSDT", side, 10.0, stop_price, stop_id="STOP-1", client_stop_id="CID-1"
        )
        self.position_snapshot_calls = 0
        self.stop_snapshot_calls = 0
        self.replace_calls = 0
        self.position_error = False
        self.stop_snapshot_fail_on_call = None
        self.fail_replace = False
        self.replacement_applies = True
        self.clear_stop_on_replace = False
        self.returned_stop_override = None
        self.replace_error = RuntimeError("replace timeout")
        self.stop_seq = 1

    def connect(self):
        return None

    def is_healthy(self):
        return True

    def quote(self, symbol):
        return Quote(symbol, 99.99, 100.01, NOW)

    def account_snapshot(self):
        return AccountSnapshot(10_000.0)

    def position_snapshot(self):
        self.position_snapshot_calls += 1
        if self.position_error:
            raise RuntimeError("position unavailable")
        return self.position

    def protective_stop_snapshot(self, symbol):
        self.stop_snapshot_calls += 1
        if self.stop_snapshot_fail_on_call == self.stop_snapshot_calls:
            raise RuntimeError("stop unavailable")
        return self.stop

    def validate_protective_stop(self, symbol, side, stop_price):
        return True

    def set_leverage(self, symbol, leverage):
        return None

    def open_market(self, plan, *, client_order_id):
        raise AssertionError("not an entry test")

    def recover_inflight_entry(self, plan, *, client_order_id):
        raise AssertionError("not an entry test")

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        raise AssertionError("not an entry test")

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        self.replace_calls += 1
        self.stop_seq += 1
        actual_price = (
            float(self.returned_stop_override)
            if self.returned_stop_override is not None
            else float(stop_price)
        )
        returned = ProtectiveStopRef(
            symbol,
            side,
            quantity,
            actual_price,
            stop_id=f"STOP-{self.stop_seq}",
            client_stop_id=f"CID-{self.stop_seq}",
        )
        if self.clear_stop_on_replace:
            self.stop = None
        elif self.replacement_applies:
            self.stop = returned
        if self.fail_replace:
            raise self.replace_error
        return returned

    def close_position(self, symbol, side, *, reason):
        return CloseFill(100.0, NOW, reason, 0.0)

    def recover_closed_position(self, local_position):
        return CloseFill(100.0, NOW, "RECOVERED", 0.0)


class PositionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.risk = RiskManager()
        self.emergency = FakeEmergency()

    def _store(
        self,
        *,
        side="LONG",
        stop_price=None,
        initial_stop=None,
        policy=INTEGER_R_STEP_CONTROL,
        mfe_r=0.0,
        mae_r=0.0,
    ):
        if initial_stop is None:
            initial_stop = 99.0 if side == "LONG" else 101.0
        if stop_price is None:
            stop_price = initial_stop
        state = ExecutionStateStore(
            self.root / f"state-{side}-{abs(hash((stop_price, policy, mfe_r, mae_r))) % 1_000_000}.json",
            profile="live-paper",
            market_environment="LIVE",
        )
        proposal_id = f"P-{side}-{abs(hash((stop_price, policy, mfe_r, mae_r))) % 1_000_000}"
        plan = EntryPlan(
            "BTCUSDT",
            side,
            10.0,
            100.0,
            initial_stop,
            10.0,
            1000.0,
            5,
        )
        fill = Fill(100.0, 10.0, "ORDER-1", "CLIENT-1", NOW - 10_000)
        self.assertTrue(state.reserve_proposal(proposal_id))
        state.begin_entry(
            EntryInflight(
                proposal_id=proposal_id,
                entry_authority="TEST_AUTH",
                exit_policy_version=policy,
                plan=plan,
                client_order_id="CLIENT-1",
                started_at_ms=NOW - 20_000,
            )
        )
        state.record_inflight_fill(fill)
        stop = ProtectiveStopRef(
            "BTCUSDT", side, 10.0, stop_price, stop_id="STOP-1", client_stop_id="CID-1"
        )
        state.promote_inflight_position(
            OpenPosition(
                proposal_id=proposal_id,
                symbol="BTCUSDT",
                side=side,
                entry_fill=fill,
                initial_risk_usd=10.0,
                initial_stop_price=initial_stop,
                protective_stop=stop,
                entry_authority="TEST_AUTH",
                exit_policy_version=policy,
                mfe_r=mfe_r,
                mae_r=mae_r,
            )
        )
        return state

    def _lifecycle(self, state, exchange, *, clock=None):
        return PositionLifecycle(
            exchange=exchange,
            state=state,
            risk=self.risk,
            emergency=self.emergency,
            monotonic_ns=clock or (lambda: 1_000_000_000),
        )

    def test_flat_returns_without_exchange_call(self):
        state = ExecutionStateStore(
            self.root / "flat.json", profile="live-paper", market_environment="LIVE"
        )
        exchange = FakeExchange()
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.0, NOW)
        self.assertEqual(result, PositionManageResult(status="FLAT"))
        self.assertEqual(exchange.position_snapshot_calls, 0)

    def test_other_symbol_is_ignored_before_exchange_or_state_write(self):
        state = self._store()
        exchange = FakeExchange()
        before = state.path.read_bytes()
        result = self._lifecycle(state, exchange).manage_tick("ETHUSDT", 101.0, NOW)
        self.assertEqual(result.status, "IGNORED_OTHER_SYMBOL")
        self.assertEqual(exchange.position_snapshot_calls, 0)
        self.assertEqual(exchange.stop_snapshot_calls, 0)
        self.assertEqual(state.path.read_bytes(), before)

    def test_invalid_zero_price_fails_closed(self):
        state = self._store()
        with self.assertRaisesRegex(PositionSafetyError, "OPEN_POSITION_PRICE_INVALID"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 0.0, NOW)

    def test_invalid_nan_price_fails_closed(self):
        state = self._store()
        with self.assertRaisesRegex(PositionSafetyError, "OPEN_POSITION_PRICE_INVALID"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", math.nan, NOW)

    def test_invalid_timestamp_fails_closed(self):
        state = self._store()
        with self.assertRaisesRegex(PositionSafetyError, "OPEN_POSITION_TIMESTAMP_INVALID"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 100.5, 0)

    def test_long_unrealized_pnl_and_r(self):
        state = self._store()
        result = self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 100.5, NOW)
        self.assertAlmostEqual(result.unrealized_pnl_usd, 5.0)
        self.assertAlmostEqual(result.current_r, 0.5)
        self.assertAlmostEqual(result.mfe_r, 0.5)
        self.assertAlmostEqual(result.mae_r, 0.0)

    def test_short_unrealized_pnl_and_r(self):
        state = self._store(side="SHORT")
        result = self._lifecycle(state, FakeExchange(side="SHORT", stop_price=101.0)).manage_tick(
            "BTCUSDT", 99.5, NOW
        )
        self.assertAlmostEqual(result.unrealized_pnl_usd, 5.0)
        self.assertAlmostEqual(result.current_r, 0.5)

    def test_long_adverse_excursion_persists(self):
        state = self._store()
        self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 99.5, NOW)
        self.assertAlmostEqual(state.open_position.mae_r, -0.5)

    def test_short_adverse_excursion_persists(self):
        state = self._store(side="SHORT")
        self._lifecycle(state, FakeExchange(side="SHORT", stop_price=101.0)).manage_tick(
            "BTCUSDT", 100.5, NOW
        )
        self.assertAlmostEqual(state.open_position.mae_r, -0.5)

    def test_mfe_never_moves_backward(self):
        state = self._store(mfe_r=0.8)
        self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 100.4, NOW)
        self.assertAlmostEqual(state.open_position.mfe_r, 0.8)

    def test_mae_never_moves_backward(self):
        state = self._store(mae_r=-0.8)
        self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 99.6, NOW)
        self.assertAlmostEqual(state.open_position.mae_r, -0.8)

    def test_mfe_mae_survive_restart(self):
        state = self._store()
        self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 102.4, NOW)
        restarted = ExecutionStateStore(
            state.path, profile="live-paper", market_environment="LIVE"
        )
        self.assertAlmostEqual(restarted.open_position.mfe_r, 2.4)
        self.assertAlmostEqual(restarted.open_position.mae_r, 0.0)

    def test_daily_highest_unrealized_updates(self):
        state = self._store()
        self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 100.7, NOW)
        self.assertAlmostEqual(state.daily_risk.highest_unrealized_usd, 7.0)

    def test_daily_highest_unrealized_never_decreases(self):
        state = self._store()
        state.set_daily_risk(
            DailyRisk(utc_day=self.risk.utc_day(NOW), highest_unrealized_usd=7.0)
        )
        self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 99.5, NOW)
        self.assertAlmostEqual(state.daily_risk.highest_unrealized_usd, 7.0)

    def test_daily_rollover_occurs_while_position_open(self):
        state = self._store()
        state.set_daily_risk(
            DailyRisk(
                utc_day="2025-01-01",
                realized_pnl_usd=5.0,
                peak_realized_pnl_usd=5.0,
                highest_unrealized_usd=3.0,
                trades_closed=1,
            )
        )
        self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 100.5, NOW)
        self.assertEqual(state.daily_risk.utc_day, self.risk.utc_day(NOW))
        self.assertEqual(state.daily_risk.realized_pnl_usd, 0.0)
        self.assertEqual(state.daily_risk.trades_closed, 0)

    def test_exchange_flat_requires_reconciliation_and_preserves_local_open(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.position = None
        proposal_id = state.open_position.proposal_id
        with self.assertRaisesRegex(PositionReconciliationRequired, "EXCHANGE_POSITION_CLOSED"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)
        self.assertEqual(state.open_position.proposal_id, proposal_id)

    def test_position_snapshot_failure_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.position_error = True
        with self.assertRaisesRegex(PositionReconciliationRequired, "POSITION_SNAPSHOT_FAILED"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_exchange_symbol_mismatch_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.position = ExchangePosition("ETHUSDT", "LONG", 10.0, 100.0)
        with self.assertRaisesRegex(PositionReconciliationRequired, "POSITION_SYMBOL_MISMATCH"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_exchange_side_mismatch_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.position = ExchangePosition("BTCUSDT", "SHORT", 10.0, 100.0)
        with self.assertRaisesRegex(PositionReconciliationRequired, "POSITION_SIDE_MISMATCH"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_exchange_quantity_mismatch_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.position = ExchangePosition("BTCUSDT", "LONG", 9.0, 100.0)
        with self.assertRaisesRegex(PositionReconciliationRequired, "POSITION_QUANTITY_MISMATCH"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_exchange_entry_price_mismatch_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.1)
        with self.assertRaisesRegex(PositionReconciliationRequired, "POSITION_ENTRY_PRICE_MISMATCH"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_missing_stop_requires_reconciliation_and_preserves_position(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.stop = None
        with self.assertRaisesRegex(PositionReconciliationRequired, "PROTECTIVE_STOP_MISSING"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)
        self.assertIsNotNone(state.open_position)
        self.assertEqual(state.health.stop_missing_events, 1)

    def test_stop_snapshot_failure_invokes_verified_emergency(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.stop_snapshot_fail_on_call = 1
        with self.assertRaisesRegex(PositionSafetyError, "PROTECTION_TRUTH_UNAVAILABLE_EMERGENCY_FLAT"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)
        self.assertEqual(self.emergency.calls[-1][2], "PROTECTION_TRUTH_UNAVAILABLE")
        self.assertIsNotNone(state.open_position)

    def test_stop_symbol_mismatch_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.stop = ProtectiveStopRef("ETHUSDT", "LONG", 10.0, 99.0, stop_id="S", client_stop_id="C")
        with self.assertRaisesRegex(PositionReconciliationRequired, "PROTECTIVE_STOP_SYMBOL_MISMATCH"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_stop_side_mismatch_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.stop = ProtectiveStopRef("BTCUSDT", "SHORT", 10.0, 99.0, stop_id="S", client_stop_id="C")
        with self.assertRaisesRegex(PositionReconciliationRequired, "PROTECTIVE_STOP_SIDE_MISMATCH"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_stop_quantity_mismatch_requires_reconciliation(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.stop = ProtectiveStopRef("BTCUSDT", "LONG", 9.0, 99.0, stop_id="S", client_stop_id="C")
        with self.assertRaisesRegex(PositionReconciliationRequired, "PROTECTIVE_STOP_QUANTITY_MISMATCH"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)

    def test_exchange_stop_looser_than_known_long_protection_emergency_flattens(self):
        state = self._store(stop_price=99.5, initial_stop=99.0)
        exchange = FakeExchange(stop_price=99.4)
        with self.assertRaisesRegex(PositionSafetyError, "PROTECTIVE_STOP_LOOSENED_EMERGENCY_FLAT"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.2, NOW)
        self.assertEqual(self.emergency.calls[-1][2], "PROTECTIVE_STOP_LOOSENED")

    def test_exchange_stop_looser_than_known_short_protection_emergency_flattens(self):
        state = self._store(side="SHORT", stop_price=100.5, initial_stop=101.0)
        exchange = FakeExchange(side="SHORT", stop_price=100.6)
        with self.assertRaisesRegex(PositionSafetyError, "PROTECTIVE_STOP_LOOSENED_EMERGENCY_FLAT"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 99.8, NOW)

    def test_long_risk_contract_breach_emergency_flattens_and_preserves_local_open(self):
        state = self._store()
        with self.assertRaisesRegex(PositionSafetyError, "RISK_CONTRACT_BREACH_EMERGENCY_FLAT"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 98.89, NOW)
        self.assertIsNotNone(state.open_position)
        self.assertEqual(self.emergency.calls[-1][2], "RISK_CONTRACT_BREACH")

    def test_short_risk_contract_breach_emergency_flattens(self):
        state = self._store(side="SHORT")
        exchange = FakeExchange(side="SHORT", stop_price=101.0)
        with self.assertRaisesRegex(PositionSafetyError, "RISK_CONTRACT_BREACH_EMERGENCY_FLAT"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.11, NOW)

    def test_risk_contract_boundary_uses_stop_settlement_not_emergency(self):
        state = self._store()
        with self.assertRaisesRegex(PositionReconciliationRequired, "STOP_BREACH_SETTLEMENT_REQUIRED"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 98.90, NOW)
        self.assertEqual(self.emergency.calls, [])

    def test_emergency_failure_is_fail_closed(self):
        state = self._store()
        self.emergency.fail = True
        with self.assertRaisesRegex(PositionSafetyError, "RISK_CONTRACT_BREACH_EMERGENCY_FAILED"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 98.0, NOW)
        self.assertIsNotNone(state.open_position)

    def test_long_stop_breach_requests_settlement(self):
        state = self._store()
        with self.assertRaisesRegex(PositionReconciliationRequired, "STOP_BREACH_SETTLEMENT_REQUIRED"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 99.0, NOW)
        self.assertEqual(state.health.stop_settlement_waits, 1)

    def test_short_stop_breach_requests_settlement(self):
        state = self._store(side="SHORT")
        exchange = FakeExchange(side="SHORT", stop_price=101.0)
        with self.assertRaisesRegex(PositionReconciliationRequired, "STOP_BREACH_SETTLEMENT_REQUIRED"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)

    def test_below_one_r_does_not_trail(self):
        state = self._store()
        exchange = FakeExchange()
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.99, NOW)
        self.assertFalse(result.stop_updated)
        self.assertEqual(exchange.replace_calls, 0)
        self.assertAlmostEqual(state.open_position.stop_price, 99.0)

    def test_long_one_r_moves_stop_to_breakeven(self):
        state = self._store()
        exchange = FakeExchange()
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertTrue(result.stop_updated)
        self.assertAlmostEqual(state.open_position.stop_price, 100.0)

    def test_long_two_r_locks_one_r(self):
        state = self._store()
        exchange = FakeExchange()
        self._lifecycle(state, exchange).manage_tick("BTCUSDT", 102.0, NOW)
        self.assertAlmostEqual(state.open_position.stop_price, 101.0)

    def test_long_three_point_eight_r_locks_two_r(self):
        state = self._store()
        exchange = FakeExchange()
        self._lifecycle(state, exchange).manage_tick("BTCUSDT", 103.8, NOW)
        self.assertAlmostEqual(state.open_position.stop_price, 102.0)

    def test_short_one_r_moves_stop_to_breakeven(self):
        state = self._store(side="SHORT")
        exchange = FakeExchange(side="SHORT", stop_price=101.0)
        self._lifecycle(state, exchange).manage_tick("BTCUSDT", 99.0, NOW)
        self.assertAlmostEqual(state.open_position.stop_price, 100.0)

    def test_short_two_r_locks_one_r(self):
        state = self._store(side="SHORT")
        exchange = FakeExchange(side="SHORT", stop_price=101.0)
        self._lifecycle(state, exchange).manage_tick("BTCUSDT", 98.0, NOW)
        self.assertAlmostEqual(state.open_position.stop_price, 99.0)

    def test_existing_tighter_stop_is_never_loosened(self):
        state = self._store(stop_price=101.5, initial_stop=99.0, mfe_r=2.0)
        exchange = FakeExchange(stop_price=101.5)
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 102.0, NOW)
        self.assertFalse(result.stop_updated)
        self.assertEqual(exchange.replace_calls, 0)
        self.assertAlmostEqual(state.open_position.stop_price, 101.5)

    def test_verified_stop_replacement_persists_new_identity(self):
        state = self._store()
        exchange = FakeExchange()
        self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertEqual(state.open_position.protective_stop.stop_id, "STOP-2")
        self.assertEqual(state.open_position.protective_stop.client_stop_id, "CID-2")

    def test_replacement_return_without_exchange_visibility_keeps_old_protection(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.replacement_applies = False
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertFalse(result.stop_updated)
        self.assertEqual(state.open_position.protective_stop.stop_id, "STOP-1")
        self.assertEqual(self.emergency.calls, [])

    def test_ambiguous_replace_with_old_stop_still_visible_stays_protected(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.fail_replace = True
        exchange.replacement_applies = False
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertFalse(result.stop_updated)
        self.assertAlmostEqual(state.open_position.stop_price, 99.0)
        self.assertEqual(self.emergency.calls, [])

    def test_ambiguous_replace_with_new_stop_visible_recovers_same_update(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.fail_replace = True
        exchange.replacement_applies = True
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertTrue(result.stop_updated)
        self.assertAlmostEqual(state.open_position.stop_price, 100.0)

    def test_ambiguous_replace_with_no_protection_emergency_flattens(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.fail_replace = True
        exchange.clear_stop_on_replace = True
        with self.assertRaisesRegex(PositionSafetyError, "STOP_REPLACEMENT_UNPROTECTED_EMERGENCY_FLAT"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)

    def test_replacement_verification_query_failure_emergency_flattens(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.stop_snapshot_fail_on_call = 2
        with self.assertRaisesRegex(PositionSafetyError, "STOP_REPLACEMENT_VERIFICATION_FAILED_EMERGENCY_FLAT"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)

    def test_replacement_that_loosens_known_protection_emergency_flattens(self):
        state = self._store(stop_price=99.5, initial_stop=99.0, mfe_r=1.0)
        exchange = FakeExchange(stop_price=99.5)
        exchange.returned_stop_override = 99.4
        with self.assertRaisesRegex(PositionSafetyError, "STOP_REPLACEMENT_LOOSENED_EMERGENCY_FLAT"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)

    def test_exchange_may_return_tighter_than_requested_stop(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.returned_stop_override = 100.2
        result = self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertTrue(result.stop_updated)
        self.assertAlmostEqual(state.open_position.stop_price, 100.2)

    def test_replacement_already_breached_by_current_mark_requires_settlement(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.returned_stop_override = 101.1
        with self.assertRaisesRegex(PositionReconciliationRequired, "STOP_BREACH_SETTLEMENT_REQUIRED"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertAlmostEqual(state.open_position.stop_price, 101.1)
        self.assertEqual(state.health.stop_settlement_waits, 1)

    def test_retraced_price_below_prior_mfe_trailing_target_requires_settlement(self):
        state = self._store(mfe_r=3.0)
        exchange = FakeExchange()
        with self.assertRaisesRegex(PositionReconciliationRequired, "STOP_BREACH_SETTLEMENT_REQUIRED"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 100.5, NOW)
        self.assertAlmostEqual(state.open_position.stop_price, 102.0)

    def test_position_persist_failure_after_stop_update_fails_closed(self):
        state = self._store()
        exchange = FakeExchange()
        original = state.open_position
        state.update_open_position = lambda _position: (_ for _ in ()).throw(
            ExecutionStateError("disk fail")
        )
        with self.assertRaisesRegex(PositionSafetyError, "OPEN_POSITION_PERSIST_FAILED"):
            self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertEqual(state.open_position, original)
        self.assertAlmostEqual(exchange.stop.trigger_price, 100.0)

    def test_unsupported_exit_policy_fails_closed(self):
        state = self._store(policy="OTHER_POLICY")
        with self.assertRaisesRegex(PositionSafetyError, "UNSUPPORTED_EXIT_POLICY"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 100.2, NOW)

    def test_health_counts_relevant_open_ticks(self):
        state = self._store()
        lifecycle = self._lifecycle(state, FakeExchange())
        lifecycle.manage_tick("BTCUSDT", 100.2, NOW)
        lifecycle.manage_tick("BTCUSDT", 100.3, NOW + 1_000)
        self.assertEqual(state.health.open_position_ticks, 2)

    def test_health_counts_verified_stop_updates_only(self):
        state = self._store()
        exchange = FakeExchange()
        self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertEqual(state.health.stop_updates, 1)

    def test_health_does_not_count_unapplied_stop_update(self):
        state = self._store()
        exchange = FakeExchange()
        exchange.replacement_applies = False
        self._lifecycle(state, exchange).manage_tick("BTCUSDT", 101.0, NOW)
        self.assertEqual(state.health.stop_updates, 0)

    def test_health_latency_is_measured_and_persisted(self):
        state = self._store()
        ticks = iter([1_000_000_000, 1_003_500_000])
        self._lifecycle(state, FakeExchange(), clock=lambda: next(ticks)).manage_tick(
            "BTCUSDT", 100.2, NOW
        )
        self.assertAlmostEqual(state.health.last_position_manage_ms, 3.5)
        self.assertAlmostEqual(state.health.max_position_manage_ms, 3.5)

    def test_health_max_latency_survives_restart(self):
        state = self._store()
        ticks = iter([0, 2_000_000])
        self._lifecycle(state, FakeExchange(), clock=lambda: next(ticks)).manage_tick(
            "BTCUSDT", 100.2, NOW
        )
        restarted = ExecutionStateStore(
            state.path, profile="live-paper", market_environment="LIVE"
        )
        self.assertAlmostEqual(restarted.health.max_position_manage_ms, 2.0)
        self.assertEqual(restarted.health.last_event, "POSITION_MANAGED")

    def test_health_persist_failure_after_success_fails_closed(self):
        state = self._store()
        state.set_health = lambda _health: (_ for _ in ()).throw(ExecutionStateError("disk fail"))
        with self.assertRaisesRegex(PositionSafetyError, "EXECUTION_HEALTH_PERSIST_FAILED"):
            self._lifecycle(state, FakeExchange()).manage_tick("BTCUSDT", 100.2, NOW)

    def test_health_monitor_rejects_unknown_counter(self):
        monitor = ExecutionHealthMonitor()
        with self.assertRaisesRegex(ValueError, "EXECUTION_HEALTH_COUNTER_UNKNOWN"):
            monitor.increment("unknown")

    def test_health_monitor_rejects_negative_latency(self):
        monitor = ExecutionHealthMonitor()
        with self.assertRaisesRegex(ValueError, "EXECUTION_HEALTH_LATENCY_INVALID"):
            monitor.observe_manage_ms(-1.0)

    def test_position_module_has_no_observation_research_learning_strategy_import(self):
        source = (Path(__file__).resolve().parents[1] / "nbot" / "execution" / "position.py").read_text()
        for forbidden in (
            "nbot.observation",
            "nbot.research",
            "nbot.learning",
            "nbot.strategy",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
