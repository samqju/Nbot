from __future__ import annotations

import dataclasses
import json
import math
import unittest

from nbot.exchange.contracts import (
    AccountSnapshot,
    CloseFill,
    EntryPlan,
    ExchangePosition,
    Fill,
    ProtectiveStopRef,
    Quote,
)
from nbot.execution.models import DailyRisk, EntryInflight, ExecutionHealth, OpenPosition


class ExchangeFactModelTests(unittest.TestCase):
    def test_quote_exposes_mid_and_spread(self):
        quote = Quote("BTCUSDT", bid=100.0, ask=101.0, timestamp_ms=1_700_000_000_000)
        self.assertEqual(quote.mid, 100.5)
        self.assertAlmostEqual(quote.spread_pct, 1.0 / 100.5 * 100.0)

    def test_quote_rejects_crossed_book(self):
        with self.assertRaisesRegex(ValueError, "QUOTE_CROSSED_BOOK"):
            Quote("BTCUSDT", bid=101.0, ask=100.0, timestamp_ms=1)

    def test_quote_rejects_nonfinite_or_nonpositive_prices(self):
        for bid, ask in ((0.0, 1.0), (1.0, 0.0), (math.nan, 1.0), (1.0, math.inf)):
            with self.subTest(bid=bid, ask=ask):
                with self.assertRaises(ValueError):
                    Quote("BTCUSDT", bid=bid, ask=ask, timestamp_ms=1)

    def test_quote_rejects_invalid_symbol_and_timestamp(self):
        for symbol in ("btcusdt", "BTC-USDT", " BTCUSDT", ""):
            with self.subTest(symbol=symbol):
                with self.assertRaises(ValueError):
                    Quote(symbol, bid=1.0, ask=1.0, timestamp_ms=1)
        with self.assertRaises(ValueError):
            Quote("BTCUSDT", bid=1.0, ask=1.0, timestamp_ms=0)

    def test_account_snapshot_accepts_zero_but_rejects_negative_or_nonfinite(self):
        self.assertEqual(AccountSnapshot(0.0).available_balance_usd, 0.0)
        for value in (-0.01, math.nan, math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AccountSnapshot(value)

    def test_exchange_position_is_one_way_and_positive(self):
        position = ExchangePosition("ETHUSDT", "SHORT", 2.0, 3000.0)
        self.assertEqual(position.side, "SHORT")
        for kwargs in (
            {"side": "BUY"},
            {"quantity": 0.0},
            {"entry_price": -1.0},
        ):
            base = dict(symbol="ETHUSDT", side="LONG", quantity=1.0, entry_price=10.0)
            base.update(kwargs)
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    ExchangePosition(**base)

    def test_fill_requires_durable_order_identities(self):
        fill = Fill(100.0, 2.0, "12345", "NBOT-ENTRY-1", 1000)
        self.assertEqual(fill.client_order_id, "NBOT-ENTRY-1")
        for kwargs in (
            {"price": 0.0},
            {"quantity": 0.0},
            {"order_id": ""},
            {"client_order_id": ""},
            {"timestamp_ms": 0},
        ):
            base = dict(price=100.0, quantity=2.0, order_id="1", client_order_id="CID", timestamp_ms=1)
            base.update(kwargs)
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    Fill(**base)

    def test_close_fill_keeps_authoritative_and_theoretical_accounting_separate(self):
        close = CloseFill(
            price=105.0,
            timestamp_ms=2000,
            reason="STOP_FILLED",
            realized_pnl_usd=9.5,
            order_ids=("9", "10"),
            source="EXCHANGE_TRADES_AND_INCOME",
            theoretical_pnl_usd=10.0,
            pnl_variance_usd=-0.5,
        )
        self.assertEqual(close.realized_pnl_usd, 9.5)
        self.assertEqual(close.theoretical_pnl_usd, 10.0)

    def test_close_fill_allows_unresolved_realized_pnl_but_not_fake_zero_price(self):
        close = CloseFill(price=100.0, timestamp_ms=1, reason="RECOVERY", realized_pnl_usd=None)
        self.assertIsNone(close.realized_pnl_usd)
        with self.assertRaises(ValueError):
            CloseFill(price=0.0, timestamp_ms=1, reason="RECOVERY")

    def test_close_fill_rejects_nonfinite_accounting_and_mutable_order_ids(self):
        with self.assertRaises(ValueError):
            CloseFill(price=1.0, timestamp_ms=1, reason="X", realized_pnl_usd=math.nan)
        with self.assertRaises(ValueError):
            CloseFill(price=1.0, timestamp_ms=1, reason="X", order_ids=["1"])  # type: ignore[arg-type]

    def test_protective_stop_requires_identity(self):
        with self.assertRaisesRegex(ValueError, "STOP_IDENTITY_MISSING"):
            ProtectiveStopRef("BTCUSDT", "LONG", 1.0, 99.0)
        ref = ProtectiveStopRef("BTCUSDT", "LONG", 1.0, 99.0, client_stop_id="NBOT-STOP-1")
        self.assertEqual(ref.client_stop_id, "NBOT-STOP-1")

    def test_protective_stop_rejects_invalid_shape(self):
        for kwargs in (
            {"side": "SELL"},
            {"quantity": 0.0},
            {"trigger_price": 0.0},
            {"stop_id": ""},
        ):
            base = dict(
                symbol="BTCUSDT",
                side="LONG",
                quantity=1.0,
                trigger_price=99.0,
                stop_id="STOP-1",
            )
            base.update(kwargs)
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    ProtectiveStopRef(**base)

    def test_entry_plan_accepts_long_and_short_directional_stops(self):
        long_plan = EntryPlan("BTCUSDT", "LONG", 1.0, 100.0, 99.0, 1.0, 100.0, 2)
        short_plan = EntryPlan("BTCUSDT", "SHORT", 1.0, 100.0, 101.0, 1.0, 100.0, 2)
        self.assertEqual(long_plan.side, "LONG")
        self.assertEqual(short_plan.side, "SHORT")

    def test_entry_plan_rejects_stop_on_wrong_side(self):
        with self.assertRaisesRegex(ValueError, "LONG_STOP_NOT_BELOW_ENTRY"):
            EntryPlan("BTCUSDT", "LONG", 1.0, 100.0, 100.0, 1.0, 100.0, 2)
        with self.assertRaisesRegex(ValueError, "SHORT_STOP_NOT_ABOVE_ENTRY"):
            EntryPlan("BTCUSDT", "SHORT", 1.0, 100.0, 100.0, 1.0, 100.0, 2)

    def test_entry_plan_rejects_invalid_capital_fields(self):
        for kwargs in (
            {"quantity": 0.0},
            {"expected_entry_price": 0.0},
            {"initial_risk_usd": 0.0},
            {"notional_usd": 0.0},
            {"leverage": 0},
        ):
            base = dict(
                symbol="BTCUSDT",
                side="LONG",
                quantity=1.0,
                expected_entry_price=100.0,
                initial_stop_price=99.0,
                initial_risk_usd=1.0,
                notional_usd=100.0,
                leverage=2,
            )
            base.update(kwargs)
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    EntryPlan(**base)


class ExecutionStateModelTests(unittest.TestCase):
    def setUp(self):
        self.fill = Fill(100.0, 2.0, "ENTRY-1", "NBOT-E-1", 1000)
        self.long_stop = ProtectiveStopRef(
            "BTCUSDT", "LONG", 2.0, 99.0, stop_id="STOP-1", client_stop_id="NBOT-S-1"
        )
        self.long_plan = EntryPlan("BTCUSDT", "LONG", 2.0, 100.0, 99.0, 2.0, 200.0, 2)

    def _open_long(self, **changes):
        data = dict(
            proposal_id="PROP-1",
            symbol="BTCUSDT",
            side="LONG",
            entry_fill=self.fill,
            initial_risk_usd=2.0,
            initial_stop_price=99.0,
            protective_stop=self.long_stop,
            entry_authority="TESTNET_MECHANICAL_ONLY",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
        )
        data.update(changes)
        return OpenPosition(**data)

    def test_open_position_exposes_fill_and_stop_facts_without_duplication(self):
        position = self._open_long()
        self.assertEqual(position.entry_price, 100.0)
        self.assertEqual(position.quantity, 2.0)
        self.assertEqual(position.entry_order_id, "ENTRY-1")
        self.assertEqual(position.entry_client_order_id, "NBOT-E-1")
        self.assertEqual(position.stop_price, 99.0)

    def test_open_position_requires_canonical_matching_stop(self):
        wrong_symbol = ProtectiveStopRef("ETHUSDT", "LONG", 2.0, 99.0, stop_id="S")
        with self.assertRaisesRegex(ValueError, "STOP_SYMBOL_MISMATCH"):
            self._open_long(protective_stop=wrong_symbol)
        wrong_side = ProtectiveStopRef("BTCUSDT", "SHORT", 2.0, 101.0, stop_id="S")
        with self.assertRaisesRegex(ValueError, "STOP_SIDE_MISMATCH"):
            self._open_long(protective_stop=wrong_side)
        wrong_qty = ProtectiveStopRef("BTCUSDT", "LONG", 1.0, 99.0, stop_id="S")
        with self.assertRaisesRegex(ValueError, "STOP_QUANTITY_MISMATCH"):
            self._open_long(protective_stop=wrong_qty)

    def test_open_position_rejects_weaker_than_initial_long_protection(self):
        weaker = ProtectiveStopRef("BTCUSDT", "LONG", 2.0, 98.5, stop_id="S")
        with self.assertRaisesRegex(ValueError, "PROTECTION_LOOSENED"):
            self._open_long(protective_stop=weaker)

    def test_open_position_allows_tighter_long_protection_above_entry(self):
        tighter = ProtectiveStopRef("BTCUSDT", "LONG", 2.0, 101.0, stop_id="S")
        position = self._open_long(protective_stop=tighter, mfe_r=2.2, mae_r=-0.4)
        self.assertEqual(position.stop_price, 101.0)

    def test_open_position_rejects_weaker_than_initial_short_protection(self):
        short_fill = Fill(100.0, 2.0, "E", "CID", 1)
        weaker = ProtectiveStopRef("BTCUSDT", "SHORT", 2.0, 101.5, stop_id="S")
        with self.assertRaisesRegex(ValueError, "PROTECTION_LOOSENED"):
            OpenPosition(
                proposal_id="P",
                symbol="BTCUSDT",
                side="SHORT",
                entry_fill=short_fill,
                initial_risk_usd=2.0,
                initial_stop_price=101.0,
                protective_stop=weaker,
                entry_authority="A",
                exit_policy_version="INTEGER_R_STEP_CONTROL",
            )

    def test_open_position_enforces_mfe_mae_sign_contract(self):
        with self.assertRaises(ValueError):
            self._open_long(mfe_r=-0.01)
        with self.assertRaises(ValueError):
            self._open_long(mae_r=0.01)

    def test_entry_inflight_carries_exact_plan_and_client_identity(self):
        inflight = EntryInflight(
            proposal_id="PROP-1",
            entry_authority="TESTNET_MECHANICAL_ONLY",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
            plan=self.long_plan,
            client_order_id="NBOT-E-1",
            started_at_ms=900,
        )
        self.assertIsNone(inflight.fill)
        self.assertEqual(inflight.plan, self.long_plan)

    def test_entry_inflight_accepts_only_fill_for_same_client_identity(self):
        good = EntryInflight(
            "PROP-1", "AUTH", "POLICY", self.long_plan, "NBOT-E-1", 900, self.fill
        )
        self.assertEqual(good.fill, self.fill)
        wrong_fill = Fill(100.0, 2.0, "ENTRY-1", "OTHER", 1000)
        with self.assertRaisesRegex(ValueError, "FILL_CLIENT_ORDER_ID_MISMATCH"):
            EntryInflight("PROP-1", "AUTH", "POLICY", self.long_plan, "NBOT-E-1", 900, wrong_fill)

    def test_entry_inflight_rejects_missing_identity_or_bad_timestamp(self):
        with self.assertRaises(ValueError):
            EntryInflight("PROP-1", "AUTH", "POLICY", self.long_plan, "", 900)
        with self.assertRaises(ValueError):
            EntryInflight("PROP-1", "AUTH", "POLICY", self.long_plan, "CID", 0)

    def test_daily_risk_default_is_flat_unhalted_state(self):
        daily = DailyRisk()
        self.assertEqual(daily.realized_pnl_usd, 0.0)
        self.assertEqual(daily.peak_realized_pnl_usd, 0.0)
        self.assertFalse(daily.halted)
        self.assertEqual(daily.trades_closed, 0)

    def test_daily_risk_validates_utc_day_and_peak(self):
        valid = DailyRisk(
            utc_day="2026-08-18",
            realized_pnl_usd=5.0,
            peak_realized_pnl_usd=7.0,
            loss_floor_usd=-3.0,
            trades_closed=2,
        )
        self.assertEqual(valid.utc_day, "2026-08-18")
        with self.assertRaisesRegex(ValueError, "UTC_DAY_INVALID"):
            DailyRisk(utc_day="18-08-2026")
        with self.assertRaisesRegex(ValueError, "PEAK_BELOW_REALIZED"):
            DailyRisk(realized_pnl_usd=5.0, peak_realized_pnl_usd=4.0)

    def test_daily_risk_halt_reason_is_consistent(self):
        halted = DailyRisk(halted=True, halt_reason="DAILY_LOSS_FLOOR_BREACH")
        self.assertTrue(halted.halted)
        with self.assertRaisesRegex(ValueError, "HALT_REASON_REQUIRED"):
            DailyRisk(halted=True)
        with self.assertRaisesRegex(ValueError, "HALT_REASON_WITHOUT_HALT"):
            DailyRisk(halted=False, halt_reason="X")

    def test_daily_risk_rejects_negative_counts_and_highest_unrealized(self):
        with self.assertRaises(ValueError):
            DailyRisk(trades_closed=-1)
        with self.assertRaises(ValueError):
            DailyRisk(highest_unrealized_usd=-0.01)

    def test_execution_health_defaults_to_zero(self):
        health = ExecutionHealth()
        self.assertEqual(health.open_position_ticks, 0)
        self.assertEqual(health.max_position_manage_ms, 0.0)

    def test_execution_health_accepts_valid_snapshot(self):
        health = ExecutionHealth(
            prepare_calls=1,
            open_position_ticks=10,
            stop_updates=2,
            reconciliations=3,
            last_position_manage_ms=4.5,
            max_position_manage_ms=9.2,
            last_event="POSITION_MANAGED",
        )
        self.assertEqual(health.reconciliations, 3)

    def test_execution_health_rejects_negative_counter_or_timing(self):
        with self.assertRaises(ValueError):
            ExecutionHealth(reconciliations=-1)
        with self.assertRaises(ValueError):
            ExecutionHealth(last_position_manage_ms=-1.0)

    def test_execution_health_max_must_cover_last_sample(self):
        with self.assertRaisesRegex(ValueError, "MAX_BELOW_LAST"):
            ExecutionHealth(last_position_manage_ms=10.0, max_position_manage_ms=9.0)

    def test_state_models_are_frozen(self):
        position = self._open_long()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            position.mfe_r = 1.0  # type: ignore[misc]

    def test_models_are_json_serializable_via_dataclasses_asdict(self):
        inflight = EntryInflight(
            "PROP-1", "AUTH", "POLICY", self.long_plan, "NBOT-E-1", 900, self.fill
        )
        position = self._open_long()
        payload = {
            "entry_inflight": dataclasses.asdict(inflight),
            "open_position": dataclasses.asdict(position),
            "daily_risk": dataclasses.asdict(DailyRisk()),
            "health": dataclasses.asdict(ExecutionHealth()),
        }
        encoded = json.dumps(payload, sort_keys=True)
        self.assertIn('"proposal_id": "PROP-1"', encoded)


if __name__ == "__main__":
    unittest.main()
