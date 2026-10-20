from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone

from nbot.exchange.contracts import AccountSnapshot, Fill, ProtectiveStopRef, Quote
from nbot.execution.models import DailyRisk
from nbot.execution.risk import RiskConfig, RiskConfigError, RiskManager, RiskRejected


def ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp() * 1000)


def quote(*, bid=99.9, ask=100.1, timestamp_ms=1_700_000_000_000):
    return Quote(symbol="BTCUSDT", bid=bid, ask=ask, timestamp_ms=timestamp_ms)


def fill(*, price=100.0, quantity=10.0):
    return Fill(
        price=price,
        quantity=quantity,
        order_id="ORDER-1",
        client_order_id="CLIENT-1",
        timestamp_ms=1_700_000_000_100,
    )


def stop(*, trigger=99.0, quantity=10.0, symbol="BTCUSDT", side="LONG"):
    return ProtectiveStopRef(
        symbol=symbol,
        side=side,
        quantity=quantity,
        trigger_price=trigger,
        stop_id="STOP-1",
    )


class RiskConfigTests(unittest.TestCase):
    def test_frozen_parity_defaults(self):
        cfg = RiskConfig()
        self.assertEqual(cfg.risk_per_trade_usd, 10.0)
        self.assertEqual(cfg.max_notional_usd, 1000.0)
        self.assertEqual(cfg.leverage, 5)
        self.assertEqual(cfg.max_spread_pct, 0.25)
        self.assertEqual(cfg.max_quote_age_ms, 5000)
        self.assertEqual(cfg.max_reference_price_drift_pct, 0.25)
        self.assertEqual(cfg.post_fill_notional_tolerance_pct, 1.0)
        self.assertEqual(cfg.post_fill_risk_tolerance_pct, 10.0)
        self.assertEqual(cfg.max_entry_slippage_pct, 1.0)
        self.assertEqual(cfg.daily_profit_lock_trigger_r, 100.0)
        self.assertEqual(cfg.daily_normal_giveback_r, 95.0)
        self.assertEqual(cfg.daily_profit_giveback_r, 3.0)
        self.assertEqual(cfg.max_capital_positions, 1)

    def test_invalid_primary_limits_fail_closed(self):
        bad = (
            {"risk_per_trade_usd": 0},
            {"max_notional_usd": 0},
            {"leverage": 0},
            {"max_spread_pct": 0},
            {"max_spread_pct": 5.1},
            {"max_quote_age_ms": 0},
            {"max_reference_price_drift_pct": -0.1},
            {"max_reference_price_drift_pct": 10.1},
        )
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(RiskConfigError):
                RiskConfig(**kwargs)

    def test_invalid_post_fill_limits_fail_closed(self):
        bad = (
            {"post_fill_notional_tolerance_pct": -0.1},
            {"post_fill_notional_tolerance_pct": 5.1},
            {"post_fill_risk_tolerance_pct": -0.1},
            {"post_fill_risk_tolerance_pct": 20.1},
            {"max_entry_slippage_pct": -0.1},
            {"max_entry_slippage_pct": 10.1},
        )
        for kwargs in bad:
            with self.subTest(kwargs=kwargs), self.assertRaises(RiskConfigError):
                RiskConfig(**kwargs)

    def test_invalid_daily_limits_fail_closed(self):
        for kwargs in (
            {"daily_profit_lock_trigger_r": 0},
            {"daily_normal_giveback_r": 0},
            {"daily_profit_giveback_r": 0},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(RiskConfigError):
                RiskConfig(**kwargs)

    def test_exactly_one_capital_position_is_not_configurable_upward(self):
        for value in (0, 2, 10):
            with self.subTest(value=value), self.assertRaisesRegex(
                RiskConfigError, "MAX_CAPITAL_POSITIONS_MUST_BE_ONE"
            ):
                RiskConfig(max_capital_positions=value)

    def test_risk_must_fit_inside_notional(self):
        with self.assertRaisesRegex(RiskConfigError, "RISK_MUST_BE_BELOW_MAX_NOTIONAL"):
            RiskConfig(risk_per_trade_usd=1000.0, max_notional_usd=1000.0)


class EntryRiskTests(unittest.TestCase):
    def setUp(self):
        self.risk = RiskManager()

    def test_flat_capacity_passes(self):
        self.risk.check_entry_capacity(open_position=None, entry_inflight=None)

    def test_existing_position_blocks_entry(self):
        with self.assertRaisesRegex(RiskRejected, "POSITION_ALREADY_OPEN"):
            self.risk.check_entry_capacity(open_position=object(), entry_inflight=None)  # type: ignore[arg-type]

    def test_inflight_entry_blocks_entry(self):
        with self.assertRaisesRegex(RiskRejected, "ENTRY_ALREADY_IN_PROGRESS"):
            self.risk.check_entry_capacity(open_position=None, entry_inflight=object())  # type: ignore[arg-type]

    def test_fresh_quote_at_spread_boundary_passes(self):
        q = Quote(symbol="BTCUSDT", bid=99.875, ask=100.125, timestamp_ms=10_000)
        self.assertAlmostEqual(q.spread_pct, 0.25)
        self.risk.check_quote(q, now_ms=15_000)

    def test_stale_quote_rejected(self):
        with self.assertRaisesRegex(RiskRejected, "QUOTE_STALE"):
            self.risk.check_quote(quote(timestamp_ms=10_000), now_ms=15_001)

    def test_small_future_quote_skew_within_freshness_window_passes(self):
        self.risk.check_quote(quote(timestamp_ms=15_000), now_ms=10_000)

    def test_future_quote_beyond_skew_window_rejected(self):
        with self.assertRaisesRegex(RiskRejected, "QUOTE_FUTURE"):
            self.risk.check_quote(quote(timestamp_ms=15_001), now_ms=10_000)

    def test_wide_spread_rejected(self):
        with self.assertRaisesRegex(RiskRejected, "SPREAD_TOO_WIDE"):
            self.risk.check_quote(Quote("BTCUSDT", 99.0, 101.0, 10_000), now_ms=10_001)

    def test_entry_price_uses_executable_side(self):
        q = quote(bid=99.0, ask=101.0)
        self.assertEqual(self.risk.entry_price(q, "LONG"), 101.0)
        self.assertEqual(self.risk.entry_price(q, "SHORT"), 99.0)

    def test_invalid_side_rejected(self):
        with self.assertRaisesRegex(RiskRejected, "SIDE_INVALID"):
            self.risk.entry_price(quote(), "BUY")  # type: ignore[arg-type]

    def test_reference_drift_boundary_passes(self):
        drift = self.risk.check_reference_drift(entry_price=100.25, reference_price=100.0)
        self.assertAlmostEqual(drift, 0.25)

    def test_reference_drift_over_limit_rejected(self):
        with self.assertRaisesRegex(RiskRejected, "REFERENCE_PRICE_DRIFT"):
            self.risk.check_reference_drift(entry_price=100.251, reference_price=100.0)

    def test_invalid_reference_price_rejected(self):
        with self.assertRaisesRegex(RiskRejected, "REFERENCE_PRICE_INVALID"):
            self.risk.check_reference_drift(entry_price=100.0, reference_price=0.0)

    def test_long_plan_matches_frozen_risk_contract(self):
        plan = self.risk.build_entry_plan(symbol="BTCUSDT", side="LONG", entry_price=100.0)
        self.assertAlmostEqual(plan.quantity, 10.0)
        self.assertAlmostEqual(plan.notional_usd, 1000.0)
        self.assertAlmostEqual(plan.initial_risk_usd, 10.0)
        self.assertAlmostEqual(plan.initial_stop_price, 99.0)
        self.assertEqual(plan.leverage, 5)

    def test_short_plan_matches_frozen_risk_contract(self):
        plan = self.risk.build_entry_plan(symbol="BTCUSDT", side="SHORT", entry_price=100.0)
        self.assertAlmostEqual(plan.quantity, 10.0)
        self.assertAlmostEqual(plan.initial_stop_price, 101.0)

    def test_margin_exact_boundary_passes(self):
        plan = self.risk.build_entry_plan(symbol="BTCUSDT", side="LONG", entry_price=100.0)
        required = self.risk.check_account_margin(AccountSnapshot(200.0), plan)
        self.assertAlmostEqual(required, 200.0)

    def test_insufficient_margin_rejected(self):
        plan = self.risk.build_entry_plan(symbol="BTCUSDT", side="LONG", entry_price=100.0)
        with self.assertRaisesRegex(RiskRejected, "INSUFFICIENT_MARGIN"):
            self.risk.check_account_margin(AccountSnapshot(199.99), plan)


class PostFillRiskTests(unittest.TestCase):
    def setUp(self):
        self.risk = RiskManager()
        self.plan = self.risk.build_entry_plan(symbol="BTCUSDT", side="LONG", entry_price=100.0)

    def test_safe_fill_passes(self):
        self.assertIsNone(
            self.risk.post_fill_violation(plan=self.plan, fill=fill(), stop_ref=stop())
        )
        self.risk.require_post_fill_safe(plan=self.plan, fill=fill(), stop_ref=stop())

    def test_notional_tolerance_boundary_passes(self):
        self.assertIsNone(
            self.risk.post_fill_violation(
                plan=self.plan,
                fill=fill(price=101.0, quantity=10.0),
                stop_ref=stop(trigger=100.0, quantity=10.0),
            )
        )

    def test_notional_breach_detected_before_other_post_fill_checks(self):
        result = self.risk.post_fill_violation(
            plan=self.plan,
            fill=fill(price=102.0, quantity=10.0),
            stop_ref=stop(trigger=101.0, quantity=10.0),
        )
        self.assertEqual(result, "POST_FILL_NOTIONAL_BREACH")

    def test_slippage_breach_detected(self):
        result = self.risk.post_fill_violation(
            plan=self.plan,
            fill=fill(price=101.001, quantity=1000.0 / 101.001),
            stop_ref=stop(trigger=100.0, quantity=1000.0 / 101.001),
        )
        self.assertEqual(result, "POST_FILL_SLIPPAGE_BREACH")

    def test_stop_identity_symbol_mismatch_detected(self):
        result = self.risk.post_fill_violation(
            plan=self.plan,
            fill=fill(),
            stop_ref=stop(symbol="ETHUSDT"),
        )
        self.assertEqual(result, "POST_FILL_STOP_IDENTITY_MISMATCH")

    def test_stop_identity_side_mismatch_detected(self):
        result = self.risk.post_fill_violation(
            plan=self.plan,
            fill=fill(),
            stop_ref=stop(side="SHORT", trigger=101.0),
        )
        self.assertEqual(result, "POST_FILL_STOP_IDENTITY_MISMATCH")

    def test_stop_identity_quantity_mismatch_detected(self):
        result = self.risk.post_fill_violation(
            plan=self.plan,
            fill=fill(),
            stop_ref=stop(quantity=9.99),
        )
        self.assertEqual(result, "POST_FILL_STOP_IDENTITY_MISMATCH")

    def test_risk_tolerance_boundary_passes(self):
        self.assertIsNone(
            self.risk.post_fill_violation(
                plan=self.plan,
                fill=fill(),
                stop_ref=stop(trigger=98.9),
            )
        )

    def test_risk_breach_detected(self):
        result = self.risk.post_fill_violation(
            plan=self.plan,
            fill=fill(),
            stop_ref=stop(trigger=98.89),
        )
        self.assertEqual(result, "POST_FILL_RISK_BREACH")

    def test_require_post_fill_safe_raises_stable_reason(self):
        with self.assertRaisesRegex(RiskRejected, "POST_FILL_RISK_BREACH"):
            self.risk.require_post_fill_safe(
                plan=self.plan,
                fill=fill(),
                stop_ref=stop(trigger=98.89),
            )


class DailyRiskTests(unittest.TestCase):
    def setUp(self):
        self.risk = RiskManager()
        self.day1 = ms("2026-08-18T12:00:00")
        self.day2 = ms("2026-08-19T00:00:01")

    def test_normal_daily_floor_uses_95r_giveback(self):
        self.assertAlmostEqual(self.risk.daily_floor_usd(0.0), -950.0)
        self.assertAlmostEqual(self.risk.daily_floor_usd(500.0), -450.0)

    def test_profit_lock_switches_to_3r_giveback_at_100r(self):
        self.assertAlmostEqual(self.risk.daily_floor_usd(999.99), 49.99)
        self.assertAlmostEqual(self.risk.daily_floor_usd(1000.0), 970.0)

    def test_new_day_initializes_deterministically(self):
        rolled = self.risk.roll_daily(DailyRisk(), timestamp_ms=self.day1)
        self.assertEqual(rolled.utc_day, "2026-08-18")
        self.assertEqual(rolled.realized_pnl_usd, 0.0)
        self.assertEqual(rolled.loss_floor_usd, -950.0)
        self.assertFalse(rolled.halted)

    def test_same_day_preserves_accounting(self):
        daily = DailyRisk(
            utc_day="2026-08-18",
            realized_pnl_usd=25.0,
            peak_realized_pnl_usd=25.0,
            trades_closed=2,
        )
        rolled = self.risk.roll_daily(daily, timestamp_ms=self.day1)
        self.assertEqual(rolled.realized_pnl_usd, 25.0)
        self.assertEqual(rolled.trades_closed, 2)

    def test_rollover_resets_sticky_halt(self):
        halted = DailyRisk(
            utc_day="2026-08-18",
            realized_pnl_usd=-1000.0,
            peak_realized_pnl_usd=0.0,
            loss_floor_usd=-950.0,
            halted=True,
            halt_reason="DAILY_LOSS_FLOOR_BREACH",
            trades_closed=3,
        )
        rolled = self.risk.roll_daily(halted, timestamp_ms=self.day2)
        self.assertEqual(rolled.utc_day, "2026-08-19")
        self.assertFalse(rolled.halted)
        self.assertEqual(rolled.realized_pnl_usd, 0.0)
        self.assertEqual(rolled.trades_closed, 0)

    def test_breach_sets_daily_halt(self):
        daily = DailyRisk(
            utc_day="2026-08-18",
            realized_pnl_usd=-951.0,
            peak_realized_pnl_usd=0.0,
        )
        result = self.risk.evaluate_daily(daily)
        self.assertTrue(result.halted)
        self.assertEqual(result.halt_reason, "DAILY_LOSS_FLOOR_BREACH")
        self.assertEqual(result.loss_floor_usd, -950.0)

    def test_persisted_halt_is_sticky_until_rollover(self):
        daily = DailyRisk(
            utc_day="2026-08-18",
            realized_pnl_usd=0.0,
            peak_realized_pnl_usd=0.0,
            halted=True,
            halt_reason="OPERATOR_DAILY_HALT",
        )
        result = self.risk.evaluate_daily(daily)
        self.assertTrue(result.halted)
        self.assertEqual(result.halt_reason, "OPERATOR_DAILY_HALT")

    def test_check_daily_entry_rejects_sticky_halt(self):
        daily = DailyRisk(
            utc_day="2026-08-18",
            halted=True,
            halt_reason="DAILY_LOSS_FLOOR_BREACH",
        )
        with self.assertRaisesRegex(RiskRejected, "DAILY_LOSS_FLOOR_BREACH"):
            self.risk.check_daily_entry(daily, now_ms=self.day1)

    def test_after_close_updates_realized_peak_and_count(self):
        daily = DailyRisk(utc_day="2026-08-18")
        result = self.risk.after_close(
            daily,
            realized_pnl_usd=25.0,
            closed_timestamp_ms=self.day1,
            highest_unrealized_usd=30.0,
        )
        self.assertEqual(result.realized_pnl_usd, 25.0)
        self.assertEqual(result.peak_realized_pnl_usd, 25.0)
        self.assertEqual(result.highest_unrealized_usd, 30.0)
        self.assertEqual(result.trades_closed, 1)

    def test_after_loss_does_not_reduce_peak(self):
        daily = DailyRisk(
            utc_day="2026-08-18",
            realized_pnl_usd=100.0,
            peak_realized_pnl_usd=100.0,
            trades_closed=1,
        )
        result = self.risk.after_close(
            daily,
            realized_pnl_usd=-25.0,
            closed_timestamp_ms=self.day1,
        )
        self.assertEqual(result.realized_pnl_usd, 75.0)
        self.assertEqual(result.peak_realized_pnl_usd, 100.0)
        self.assertEqual(result.trades_closed, 2)

    def test_after_close_on_new_utc_day_resets_before_accounting(self):
        daily = DailyRisk(
            utc_day="2026-08-18",
            realized_pnl_usd=100.0,
            peak_realized_pnl_usd=100.0,
            trades_closed=2,
        )
        result = self.risk.after_close(
            daily,
            realized_pnl_usd=-10.0,
            closed_timestamp_ms=self.day2,
        )
        self.assertEqual(result.utc_day, "2026-08-19")
        self.assertEqual(result.realized_pnl_usd, -10.0)
        self.assertEqual(result.peak_realized_pnl_usd, 0.0)
        self.assertEqual(result.trades_closed, 1)

    def test_invalid_close_accounting_is_rejected(self):
        daily = DailyRisk(utc_day="2026-08-18")
        with self.assertRaisesRegex(RiskRejected, "REALIZED_PNL_USD_INVALID"):
            self.risk.after_close(
                daily,
                realized_pnl_usd=float("nan"),
                closed_timestamp_ms=self.day1,
            )


if __name__ == "__main__":
    unittest.main()
