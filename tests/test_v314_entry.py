from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nbot.exchange.contracts import (
    AccountSnapshot,
    CloseFill,
    ExchangePosition,
    Fill,
    ProtectiveStopRef,
    Quote,
)
from nbot.execution.entry import (
    EntryLifecycle,
    EntryLifecycleConfig,
    EntryProposal,
    EntryRejected,
    EntrySafetyError,
)
from nbot.execution.models import EntryInflight
from nbot.execution.risk import RiskManager
from nbot.execution.state import ExecutionStateStore

NOW = 1_776_510_000_000
AUTHORITY = "TESTNET_MECHANICAL_ONLY"
POLICY = "INTEGER_R_STEP_CONTROL"


def proposal(**overrides):
    data = dict(
        proposal_id="PROP-V314-001",
        generated_at_ms=NOW - 1_000,
        expires_at_ms=NOW + 20_000,
        profile="live-paper",
        market_environment="LIVE",
        symbol="BTCUSDT",
        side="LONG",
        reference_price=100.0,
        entry_authority=AUTHORITY,
        exit_policy_version=POLICY,
    )
    data.update(overrides)
    return EntryProposal(**data)


class FakeExchange:
    def __init__(self):
        self.healthy = True
        self.quote_value = Quote("BTCUSDT", 99.9, 100.1, NOW - 100)
        self.balance = 10_000.0
        self.position = None
        self.stop_ref = None
        self.validate_results = [True, True]
        self.validate_calls = []
        self.leverage_calls = []
        self.open_calls = []
        self.recover_calls = []
        self.ensure_calls = []
        self.close_calls = []
        self.open_error = None
        self.open_error_after_fill = False
        self.recovery_error = None
        self.recovered_fill = None
        self.fill_price = None
        self.fill_quantity_multiplier = 1.0
        self.fill_client_id_override = None
        self.stop_error = None
        self.stop_trigger_override = None
        self.state = None
        self.journal_seen_before_order = False
        self.fill_seen_before_stop = False

    def connect(self):
        return None

    def is_healthy(self):
        return self.healthy

    def quote(self, symbol):
        return self.quote_value

    def account_snapshot(self):
        return AccountSnapshot(self.balance)

    def position_snapshot(self):
        return self.position

    def protective_stop_snapshot(self, symbol):
        return self.stop_ref

    def validate_protective_stop(self, symbol, side, stop_price):
        self.validate_calls.append((symbol, side, stop_price))
        if self.validate_results:
            return self.validate_results.pop(0)
        return True

    def set_leverage(self, symbol, leverage):
        self.leverage_calls.append((symbol, leverage))

    def _fill(self, plan, client_order_id):
        price = plan.expected_entry_price if self.fill_price is None else self.fill_price
        quantity = plan.quantity * self.fill_quantity_multiplier
        cid = client_order_id if self.fill_client_id_override is None else self.fill_client_id_override
        return Fill(price, quantity, "ENTRY-1", cid, NOW + 10)

    def open_market(self, plan, *, client_order_id):
        self.open_calls.append((plan, client_order_id))
        if self.state is not None:
            inflight = self.state.entry_inflight
            self.journal_seen_before_order = (
                inflight is not None
                and inflight.client_order_id == client_order_id
                and inflight.proposal_id in self.state.snapshot.processed_proposal_ids
            )
        if self.open_error is not None and not self.open_error_after_fill:
            raise self.open_error
        fill = self._fill(plan, client_order_id)
        self.position = ExchangePosition(plan.symbol, plan.side, fill.quantity, fill.price)
        if self.open_error is not None:
            raise self.open_error
        return fill

    def recover_inflight_entry(self, plan, *, client_order_id):
        self.recover_calls.append((plan, client_order_id))
        if self.recovery_error is not None:
            raise self.recovery_error
        if self.recovered_fill is not None:
            self.position = ExchangePosition(
                plan.symbol, plan.side, self.recovered_fill.quantity, self.recovered_fill.price
            )
        return self.recovered_fill

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        self.ensure_calls.append((symbol, side, quantity, stop_price))
        if self.state is not None:
            self.fill_seen_before_stop = (
                self.state.entry_inflight is not None
                and self.state.entry_inflight.fill is not None
            )
        if self.stop_error is not None:
            raise self.stop_error
        trigger = stop_price if self.stop_trigger_override is None else self.stop_trigger_override
        self.stop_ref = ProtectiveStopRef(
            symbol, side, quantity, trigger, stop_id="STOP-1", client_stop_id="NBV3S-1"
        )
        return self.stop_ref

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        return self.ensure_protective_stop(symbol, side, quantity, stop_price)

    def close_position(self, symbol, side, *, reason):
        self.close_calls.append((symbol, side, reason))
        self.position = None
        return CloseFill(100.0, NOW + 100, reason, realized_pnl_usd=0.0, order_ids=("C-1",))

    def recover_closed_position(self, local_position):
        return CloseFill(100.0, NOW + 100, "RECOVERED", realized_pnl_usd=0.0, order_ids=("C-1",))


class FakeEmergency:
    def __init__(self, exchange):
        self.exchange = exchange
        self.calls = []
        self.error = None

    def flatten_verified(self, symbol, side, *, reason):
        self.calls.append((symbol, side, reason))
        if self.error is not None:
            raise self.error
        self.exchange.position = None


class EntryLifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "data" / "execution" / "paper" / "execution_state.json"
        self.state = ExecutionStateStore(path, profile="live-paper", market_environment="LIVE")
        self.state.set_entries_enabled(True)
        self.exchange = FakeExchange()
        self.exchange.state = self.state
        self.emergency = FakeEmergency(self.exchange)
        self.risk = RiskManager()
        self.config = EntryLifecycleConfig(
            profile="live-paper",
            market_environment="LIVE",
            allowed_entry_authorities=frozenset({AUTHORITY}),
            allowed_exit_policies=frozenset({POLICY}),
        )
        self.lifecycle = EntryLifecycle(
            exchange=self.exchange,
            state=self.state,
            risk=self.risk,
            emergency=self.emergency,
            config=self.config,
        )

    def execute(self, value=None):
        return self.lifecycle.execute(proposal() if value is None else value, now_ms=NOW)


class ProposalContractTests(unittest.TestCase):
    def test_proposal_rejects_bad_expiry(self):
        with self.assertRaisesRegex(ValueError, "ENTRY_PROPOSAL_EXPIRY_INVALID"):
            proposal(expires_at_ms=NOW - 1_000)

    def test_proposal_rejects_bad_symbol(self):
        with self.assertRaisesRegex(ValueError, "ENTRY_PROPOSAL_SYMBOL_INVALID"):
            proposal(symbol="btc/usdt")

    def test_proposal_rejects_bad_side(self):
        with self.assertRaisesRegex(ValueError, "ENTRY_PROPOSAL_SIDE_INVALID"):
            proposal(side="BUY")

    def test_config_rejects_profile_environment_mismatch(self):
        with self.assertRaisesRegex(ValueError, "ENTRY_CONFIG_ENVIRONMENT_MISMATCH"):
            EntryLifecycleConfig(
                profile="testnet-trade",
                market_environment="LIVE",
                allowed_entry_authorities=frozenset({AUTHORITY}),
                allowed_exit_policies=frozenset({POLICY}),
            )

    def test_client_order_id_is_deterministic_and_compact(self):
        a = EntryLifecycle.client_order_id(
            profile="live-paper", market_environment="LIVE", proposal_id="PROP-1"
        )
        b = EntryLifecycle.client_order_id(
            profile="live-paper", market_environment="LIVE", proposal_id="PROP-1"
        )
        c = EntryLifecycle.client_order_id(
            profile="testnet-trade", market_environment="TESTNET", proposal_id="PROP-1"
        )
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertLessEqual(len(a), 36)
        self.assertTrue(a.startswith("NBV3E-"))


class PreEntryGateTests(EntryLifecycleTestCase):
    def test_wrong_profile_rejected_before_exchange(self):
        with self.assertRaisesRegex(EntryRejected, "PROFILE_MISMATCH"):
            self.execute(proposal(profile="testnet-trade", market_environment="TESTNET"))
        self.assertEqual(self.exchange.open_calls, [])

    def test_wrong_environment_rejected_before_exchange(self):
        with self.assertRaisesRegex(EntryRejected, "ENVIRONMENT_MISMATCH"):
            self.execute(proposal(market_environment="TESTNET"))

    def test_future_proposal_rejected(self):
        with self.assertRaisesRegex(EntryRejected, "FUTURE_TIMESTAMP"):
            self.execute(proposal(generated_at_ms=NOW + 5_001, expires_at_ms=NOW + 20_000))

    def test_expired_proposal_rejected_at_boundary(self):
        with self.assertRaisesRegex(EntryRejected, "EXPIRED"):
            self.execute(proposal(generated_at_ms=NOW - 20_000, expires_at_ms=NOW))

    def test_unapproved_authority_rejected(self):
        with self.assertRaisesRegex(EntryRejected, "ENTRY_AUTHORITY_NOT_APPROVED"):
            self.execute(proposal(entry_authority="UNAPPROVED"))

    def test_unapproved_exit_policy_rejected(self):
        with self.assertRaisesRegex(EntryRejected, "EXIT_POLICY_NOT_APPROVED"):
            self.execute(proposal(exit_policy_version="UNKNOWN_POLICY"))

    def test_entries_disabled_rejected(self):
        self.state.set_entries_enabled(False)
        with self.assertRaisesRegex(EntryRejected, "ENTRY_DISABLED"):
            self.execute()

    def test_daily_halt_rejected(self):
        daily = self.risk.roll_daily(self.state.daily_risk, timestamp_ms=NOW)
        daily = self.risk.after_close(daily, realized_pnl_usd=-1000.0, closed_timestamp_ms=NOW)
        self.state.set_daily_risk(daily)
        with self.assertRaisesRegex(EntryRejected, "DAILY_LOSS_FLOOR_BREACH"):
            self.execute()

    def test_daily_roll_is_persisted_before_entry(self):
        self.execute()
        self.assertEqual(self.state.daily_risk.utc_day, self.risk.utc_day(NOW))

    def test_existing_local_position_rejected(self):
        opened = self.execute()
        with self.assertRaisesRegex(EntryRejected, "POSITION_ALREADY_OPEN"):
            self.lifecycle.execute(
                proposal(proposal_id="PROP-V314-002"), now_ms=NOW + 1
            )
        self.assertEqual(self.state.open_position, opened)

    def test_existing_inflight_rejected(self):
        plan = self.risk.build_entry_plan(symbol="BTCUSDT", side="LONG", entry_price=100.0)
        self.state.reserve_proposal("OTHER")
        self.state.begin_entry(EntryInflight("OTHER", AUTHORITY, POLICY, plan, "CID", NOW))
        with self.assertRaisesRegex(EntryRejected, "ENTRY_ALREADY_IN_PROGRESS"):
            self.execute()

    def test_duplicate_proposal_rejected_before_exchange(self):
        self.state.reserve_proposal("PROP-V314-001")
        with self.assertRaisesRegex(EntryRejected, "DUPLICATE_PROPOSAL"):
            self.execute()
        self.assertEqual(self.exchange.open_calls, [])

    def test_exchange_unhealthy_rejected(self):
        self.exchange.healthy = False
        with self.assertRaisesRegex(EntryRejected, "EXCHANGE_UNHEALTHY"):
            self.execute()

    def test_exchange_position_rejected(self):
        self.exchange.position = ExchangePosition("BTCUSDT", "LONG", 1.0, 100.0)
        with self.assertRaisesRegex(EntryRejected, "POSITION_ALREADY_OPEN"):
            self.execute()

    def test_quote_symbol_mismatch_rejected(self):
        self.exchange.quote_value = Quote("ETHUSDT", 99.9, 100.1, NOW)
        with self.assertRaisesRegex(EntryRejected, "QUOTE_SYMBOL_MISMATCH"):
            self.execute()

    def test_stale_quote_rejected(self):
        self.exchange.quote_value = Quote("BTCUSDT", 99.9, 100.1, NOW - 5_001)
        with self.assertRaisesRegex(EntryRejected, "QUOTE_STALE"):
            self.execute()

    def test_wide_spread_rejected(self):
        self.exchange.quote_value = Quote("BTCUSDT", 99.0, 101.0, NOW)
        with self.assertRaisesRegex(EntryRejected, "SPREAD_TOO_WIDE"):
            self.execute()

    def test_reference_drift_rejected(self):
        with self.assertRaisesRegex(EntryRejected, "REFERENCE_PRICE_DRIFT"):
            self.execute(proposal(reference_price=90.0))

    def test_insufficient_margin_rejected(self):
        self.exchange.balance = 199.99
        with self.assertRaisesRegex(EntryRejected, "INSUFFICIENT_MARGIN"):
            self.execute()

    def test_stop_infeasible_rejected_before_reservation(self):
        self.exchange.validate_results = [False]
        with self.assertRaisesRegex(EntryRejected, "PROTECTIVE_STOP_INFEASIBLE"):
            self.execute()
        self.assertFalse(self.state.has_processed_proposal("PROP-V314-001"))

    def test_leverage_failure_rejected_before_reservation(self):
        def broken(*args, **kwargs):
            raise RuntimeError("leverage")
        self.exchange.set_leverage = broken
        with self.assertRaisesRegex(EntryRejected, "LEVERAGE_SET_FAILED"):
            self.execute()
        self.assertFalse(self.state.has_processed_proposal("PROP-V314-001"))


class DurableEntryOrderingTests(EntryLifecycleTestCase):
    def test_proposal_and_journal_exist_before_market_order(self):
        self.execute()
        self.assertTrue(self.exchange.journal_seen_before_order)

    def test_market_order_is_called_exactly_once(self):
        self.execute()
        self.assertEqual(len(self.exchange.open_calls), 1)

    def test_fill_is_durable_before_stop_call(self):
        self.execute()
        self.assertTrue(self.exchange.fill_seen_before_stop)

    def test_success_promotes_only_after_verified_stop(self):
        position = self.execute()
        self.assertIsNone(self.state.entry_inflight)
        self.assertEqual(self.state.open_position, position)
        self.assertEqual(len(self.exchange.validate_calls), 2)
        self.assertIsNotNone(position.protective_stop.stop_id)

    def test_success_long_preserves_initial_dollar_risk_at_actual_fill(self):
        self.exchange.fill_price = 100.2
        position = self.execute()
        actual = abs(position.entry_price - position.initial_stop_price) * position.quantity
        self.assertAlmostEqual(actual, 10.0, places=9)

    def test_success_short_preserves_initial_dollar_risk(self):
        self.exchange.quote_value = Quote("BTCUSDT", 99.9, 100.1, NOW)
        position = self.execute(proposal(side="SHORT"))
        self.assertEqual(position.side, "SHORT")
        self.assertGreater(position.initial_stop_price, position.entry_price)
        actual = abs(position.entry_price - position.initial_stop_price) * position.quantity
        self.assertAlmostEqual(actual, 10.0, places=9)


class AmbiguousEntryTests(EntryLifecycleTestCase):
    def test_ambiguous_order_recovers_same_identity_without_second_market_order(self):
        self.exchange.open_error = TimeoutError("timeout")
        self.exchange.open_error_after_fill = True
        cid = EntryLifecycle.client_order_id(
            profile="live-paper", market_environment="LIVE", proposal_id="PROP-V314-001"
        )
        self.exchange.recovered_fill = Fill(100.1, 1000.0 / 100.1, "ENTRY-1", cid, NOW + 10)
        position = self.execute()
        self.assertEqual(len(self.exchange.open_calls), 1)
        self.assertEqual(len(self.exchange.recover_calls), 1)
        self.assertEqual(self.exchange.recover_calls[0][1], cid)
        self.assertEqual(position.entry_client_order_id, cid)

    def test_unresolved_ambiguous_order_keeps_inflight_and_never_resubmits(self):
        self.exchange.open_error = TimeoutError("timeout")
        with self.assertRaisesRegex(EntrySafetyError, "ENTRY_OUTCOME_UNRESOLVED"):
            self.execute()
        self.assertEqual(len(self.exchange.open_calls), 1)
        self.assertEqual(len(self.exchange.recover_calls), 1)
        self.assertIsNotNone(self.state.entry_inflight)
        self.assertIsNone(self.state.entry_inflight.fill)

    def test_recovery_error_keeps_inflight(self):
        self.exchange.open_error = TimeoutError("timeout")
        self.exchange.recovery_error = RuntimeError("query failed")
        with self.assertRaisesRegex(EntrySafetyError, "ENTRY_AMBIGUOUS_RECOVERY_FAILED"):
            self.execute()
        self.assertIsNotNone(self.state.entry_inflight)
        self.assertEqual(len(self.exchange.open_calls), 1)


class PostFillEmergencyTests(EntryLifecycleTestCase):
    def assert_emergency(self, expected_reason):
        self.assertEqual(len(self.emergency.calls), 1)
        self.assertEqual(self.emergency.calls[0][2], expected_reason)
        self.assertIsNotNone(self.state.entry_inflight)
        self.assertIsNotNone(self.state.entry_inflight.fill)
        self.assertIsNone(self.state.open_position)

    def test_fill_identity_mismatch_emergency_flatten(self):
        self.exchange.fill_client_id_override = "WRONG-CID"
        with self.assertRaisesRegex(EntrySafetyError, "ENTRY_FILL_IDENTITY_MISMATCH_EMERGENCY_FLAT"):
            self.execute()
        # The mismatching fill cannot be written into EntryInflight, so the
        # original recoverable journal remains without a stored fill.
        self.assertEqual(self.emergency.calls[0][2], "ENTRY_FILL_IDENTITY_MISMATCH")
        self.assertIsNotNone(self.state.entry_inflight)
        self.assertIsNone(self.state.entry_inflight.fill)

    def test_stop_placement_failure_emergency_flatten_and_preserves_fill_journal(self):
        self.exchange.stop_error = RuntimeError("stop failed")
        with self.assertRaisesRegex(EntrySafetyError, "PROTECTION_FAILED_EMERGENCY_FLAT"):
            self.execute()
        self.assert_emergency("PROTECTION_FAILED")

    def test_stop_verification_failure_emergency_flatten(self):
        self.exchange.validate_results = [True, False]
        with self.assertRaisesRegex(EntrySafetyError, "PROTECTION_NOT_VERIFIED_EMERGENCY_FLAT"):
            self.execute()
        self.assert_emergency("PROTECTION_NOT_VERIFIED")

    def test_post_fill_notional_breach_is_protected_then_emergency_flattened(self):
        self.exchange.fill_quantity_multiplier = 1.02
        with self.assertRaisesRegex(EntrySafetyError, "POST_FILL_NOTIONAL_BREACH_EMERGENCY_FLAT"):
            self.execute()
        self.assertIsNotNone(self.exchange.stop_ref)
        self.assert_emergency("POST_FILL_NOTIONAL_BREACH")

    def test_post_fill_slippage_breach_is_protected_then_emergency_flattened(self):
        self.exchange.fill_price = 102.0
        self.exchange.fill_quantity_multiplier = 100.1 / 102.0
        with self.assertRaisesRegex(EntrySafetyError, "POST_FILL_SLIPPAGE_BREACH_EMERGENCY_FLAT"):
            self.execute()
        self.assertIsNotNone(self.exchange.stop_ref)
        self.assert_emergency("POST_FILL_SLIPPAGE_BREACH")

    def test_post_fill_risk_breach_is_protected_then_emergency_flattened(self):
        # Actual stop is around 99.099; move it slightly farther so risk > 11.
        self.exchange.stop_trigger_override = 98.8
        with self.assertRaisesRegex(EntrySafetyError, "POST_FILL_RISK_BREACH_EMERGENCY_FLAT"):
            self.execute()
        self.assert_emergency("POST_FILL_RISK_BREACH")

    def test_stop_identity_mismatch_emergency_flatten(self):
        original = self.exchange.ensure_protective_stop
        def wrong_quantity(symbol, side, quantity, stop_price):
            ref = original(symbol, side, quantity, stop_price)
            return ProtectiveStopRef(symbol, side, quantity * 0.9, ref.trigger_price, stop_id="BAD")
        self.exchange.ensure_protective_stop = wrong_quantity
        with self.assertRaisesRegex(EntrySafetyError, "POST_FILL_STOP_IDENTITY_MISMATCH_EMERGENCY_FLAT"):
            self.execute()
        self.assert_emergency("POST_FILL_STOP_IDENTITY_MISMATCH")

    def test_emergency_failure_preserves_inflight_and_fails_closed(self):
        self.exchange.stop_error = RuntimeError("stop failed")
        self.emergency.error = RuntimeError("cannot prove flat")
        with self.assertRaisesRegex(EntrySafetyError, "PROTECTION_FAILED_EMERGENCY_FAILED"):
            self.execute()
        self.assertIsNotNone(self.state.entry_inflight)
        self.assertIsNotNone(self.state.entry_inflight.fill)
        self.assertIsNone(self.state.open_position)


if __name__ == "__main__":
    unittest.main()
