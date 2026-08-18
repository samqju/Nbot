from __future__ import annotations

import json
import math
import os
from pathlib import Path
import stat
import tempfile
import unittest

from nbot.config.profiles import Profile, get_profile
from nbot.exchange.contracts import EntryPlan, ExchangePort, Quote
from nbot.exchange.paper import (
    PAPER_ACCOUNT_VERSION,
    PaperExchange,
    PaperExchangeConfig,
    PaperExchangeError,
)
from nbot.execution.entry import EntryLifecycle, EntryLifecycleConfig, EntryProposal
from nbot.execution.emergency import EmergencyFlattener
from nbot.execution.models import EntryInflight, OpenPosition
from nbot.execution.risk import RiskManager
from nbot.execution.state import ExecutionStateStore
from nbot.execution.reconciliation import ReconciliationExchangePort


class FakeMarket:
    def __init__(self, *, symbol="BTCUSDT", bid=99.0, ask=101.0, timestamp_ms=1_000):
        self.connected = False
        self.healthy = True
        self.quotes = {symbol: Quote(symbol=symbol, bid=bid, ask=ask, timestamp_ms=timestamp_ms)}
        self.connect_calls = 0
        self.quote_calls = []

    def connect(self):
        self.connected = True
        self.connect_calls += 1

    def is_healthy(self):
        return self.healthy

    def quote(self, symbol):
        self.quote_calls.append(symbol)
        return self.quotes[symbol]

    def set_quote(self, symbol, bid, ask, timestamp_ms):
        self.quotes[symbol] = Quote(symbol=symbol, bid=bid, ask=ask, timestamp_ms=timestamp_ms)


class PaperExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profile = get_profile("live-paper")
        self.market = FakeMarket()
        self.config = PaperExchangeConfig(
            starting_balance_usd=10_000.0,
            entry_slippage_pct=0.10,
            exit_slippage_pct=0.20,
            taker_fee_rate=0.001,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def exchange(self, *, connect=True, market=None, config=None, profile=None):
        ex = PaperExchange(
            repo_root=self.root,
            profile=profile or self.profile,
            market_data=market or self.market,
            config=config or self.config,
        )
        if connect:
            ex.connect()
        return ex

    def plan(self, *, side="LONG", quantity=2.0, expected=100.0, stop=None, leverage=5):
        if stop is None:
            stop = 95.0 if side == "LONG" else 105.0
        risk = abs(expected - stop) * quantity
        return EntryPlan(
            symbol="BTCUSDT",
            side=side,
            quantity=quantity,
            expected_entry_price=expected,
            initial_stop_price=stop,
            initial_risk_usd=risk,
            notional_usd=expected * quantity,
            leverage=leverage,
        )

    def open_and_protect(self, ex, *, side="LONG", client_id="NBV3E-paper-entry", quantity=2.0):
        plan = self.plan(side=side, quantity=quantity)
        ex.set_leverage(plan.symbol, plan.leverage)
        fill = ex.open_market(plan, client_order_id=client_id)
        stop_price = 95.0 if side == "LONG" else 105.0
        stop = ex.ensure_protective_stop(plan.symbol, plan.side, fill.quantity, stop_price)
        return plan, fill, stop

    def local_open(self, *, plan, fill, stop, proposal_id="proposal-paper"):
        return OpenPosition(
            proposal_id=proposal_id,
            symbol=plan.symbol,
            side=plan.side,
            entry_fill=fill,
            initial_risk_usd=plan.initial_risk_usd,
            initial_stop_price=plan.initial_stop_price,
            protective_stop=stop,
            entry_authority="TEST",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
        )

    # Config/profile/contract -------------------------------------------------

    def test_config_defaults_are_valid(self):
        PaperExchangeConfig()

    def test_config_rejects_zero_balance(self):
        with self.assertRaises(ValueError):
            PaperExchangeConfig(starting_balance_usd=0)

    def test_config_rejects_negative_slippage(self):
        with self.assertRaises(ValueError):
            PaperExchangeConfig(entry_slippage_pct=-0.1)

    def test_config_rejects_negative_exit_slippage(self):
        with self.assertRaises(ValueError):
            PaperExchangeConfig(exit_slippage_pct=-0.1)

    def test_config_rejects_fee_at_or_above_one(self):
        with self.assertRaises(ValueError):
            PaperExchangeConfig(taker_fee_rate=1.0)

    def test_rejects_non_live_paper_profile(self):
        with self.assertRaises(ValueError):
            self.exchange(connect=False, profile=get_profile("testnet-trade"))

    def test_rejects_profile_with_order_authority(self):
        bad = Profile(
            name="live-paper",
            market_environment="LIVE",
            execution_mode="PAPER",
            capital_kind="LOCAL_PAPER",
            execution_state_dir=Path("data/execution/paper"),
            observation_db=Path("data/observation/live/observer.db"),
            evidence_lineage="LIVE_PAPER_OPERATIONAL",
            binance_order_writes=True,
            real_capital=False,
            requires_arm_gate=False,
        )
        with self.assertRaises(ValueError):
            self.exchange(connect=False, profile=bad)

    def test_implements_exchange_port_runtime_protocol(self):
        ex = self.exchange(connect=False)
        self.assertIsInstance(ex, ExchangePort)

    def test_implements_reconciliation_exchange_port_runtime_protocol(self):
        ex = self.exchange(connect=False)
        self.assertIsInstance(ex, ReconciliationExchangePort)

    def test_module_has_no_binance_or_requests_import(self):
        text = (Path(__file__).resolve().parents[1] / "nbot/exchange/paper.py").read_text()
        import_lines = [
            line.strip().lower()
            for line in text.splitlines()
            if line.lstrip().startswith(("import ", "from "))
        ]
        self.assertFalse(any("requests" in line for line in import_lines))
        self.assertFalse(any("binance" in line for line in import_lines))

    # Connect/durability ------------------------------------------------------

    def test_connect_creates_account_and_connects_market(self):
        ex = self.exchange()
        self.assertTrue(ex.account_path.is_file())
        self.assertEqual(self.market.connect_calls, 1)

    def test_account_file_mode_is_0600(self):
        ex = self.exchange()
        mode = stat.S_IMODE(ex.account_path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_new_account_has_expected_version_and_profile(self):
        ex = self.exchange()
        raw = json.loads(ex.account_path.read_text())
        self.assertEqual(raw["version"], PAPER_ACCOUNT_VERSION)
        self.assertEqual(raw["profile"], "live-paper")
        self.assertEqual(raw["market_environment"], "LIVE")

    def test_is_healthy_false_before_connect(self):
        ex = self.exchange(connect=False)
        self.assertFalse(ex.is_healthy())

    def test_is_healthy_delegates_market_health(self):
        ex = self.exchange()
        self.assertTrue(ex.is_healthy())
        self.market.healthy = False
        self.assertFalse(ex.is_healthy())

    def test_reconnect_restores_existing_account(self):
        ex = self.exchange()
        ex.set_leverage("BTCUSDT", 7)
        ex2 = self.exchange()
        raw = json.loads(ex2.account_path.read_text())
        self.assertEqual(raw["leverage_by_symbol"]["BTCUSDT"], 7)

    def test_corrupt_json_fails_closed(self):
        ex = self.exchange()
        ex.account_path.write_text("{broken")
        with self.assertRaises(PaperExchangeError):
            self.exchange()

    def test_unsupported_version_fails_closed(self):
        ex = self.exchange()
        raw = json.loads(ex.account_path.read_text())
        raw["version"] = "OLD"
        ex.account_path.write_text(json.dumps(raw))
        with self.assertRaises(PaperExchangeError):
            self.exchange()

    def test_starting_balance_change_fails_closed(self):
        self.exchange()
        changed = PaperExchangeConfig(starting_balance_usd=9_000.0)
        with self.assertRaises(PaperExchangeError):
            self.exchange(config=changed)

    # Quote/account/leverage --------------------------------------------------

    def test_quote_delegates_market_truth(self):
        ex = self.exchange()
        q = ex.quote("BTCUSDT")
        self.assertEqual(q, self.market.quotes["BTCUSDT"])
        self.assertEqual(self.market.quote_calls[-1], "BTCUSDT")

    def test_quote_symbol_mismatch_fails_closed(self):
        class WrongMarket(FakeMarket):
            def quote(self, symbol):
                return Quote(symbol="ETHUSDT", bid=10, ask=11, timestamp_ms=1_000)

        ex = self.exchange(market=WrongMarket())
        with self.assertRaises(PaperExchangeError):
            ex.quote("BTCUSDT")

    def test_account_snapshot_starts_at_configured_balance(self):
        ex = self.exchange()
        self.assertEqual(ex.account_snapshot().available_balance_usd, 10_000.0)

    def test_set_leverage_persists(self):
        ex = self.exchange()
        ex.set_leverage("BTCUSDT", 8)
        raw = json.loads(ex.account_path.read_text())
        self.assertEqual(raw["leverage_by_symbol"]["BTCUSDT"], 8)

    def test_set_leverage_rejects_bad_value(self):
        ex = self.exchange()
        with self.assertRaises(ValueError):
            ex.set_leverage("BTCUSDT", 0)

    def test_open_position_reduces_available_balance_by_margin(self):
        ex = self.exchange()
        plan = self.plan(quantity=2.0, leverage=5)
        ex.set_leverage(plan.symbol, plan.leverage)
        fill = ex.open_market(plan, client_order_id="NBV3E-margin")
        expected = 10_000.0 - (fill.price * fill.quantity / 5)
        self.assertAlmostEqual(ex.account_snapshot().available_balance_usd, expected)

    # Entry identity ----------------------------------------------------------

    def test_open_requires_leverage_to_be_set(self):
        ex = self.exchange()
        with self.assertRaisesRegex(PaperExchangeError, "PAPER_LEVERAGE_NOT_SET"):
            ex.open_market(self.plan(), client_order_id="NBV3E-no-lev")

    def test_long_entry_fills_from_ask_with_adverse_slippage(self):
        ex = self.exchange()
        plan = self.plan(side="LONG")
        ex.set_leverage(plan.symbol, plan.leverage)
        fill = ex.open_market(plan, client_order_id="NBV3E-long")
        self.assertAlmostEqual(fill.price, 101.0 * 1.001)
        self.assertEqual(fill.quantity, 2.0)

    def test_short_entry_fills_from_bid_with_adverse_slippage(self):
        ex = self.exchange()
        plan = self.plan(side="SHORT")
        ex.set_leverage(plan.symbol, plan.leverage)
        fill = ex.open_market(plan, client_order_id="NBV3E-short")
        self.assertAlmostEqual(fill.price, 99.0 * 0.999)

    def test_entry_order_id_is_deterministic_for_client_identity(self):
        ex = self.exchange()
        plan = self.plan()
        ex.set_leverage(plan.symbol, plan.leverage)
        fill1 = ex.open_market(plan, client_order_id="NBV3E-deterministic")
        fill2 = ex.open_market(plan, client_order_id="NBV3E-deterministic")
        self.assertEqual(fill1, fill2)

    def test_duplicate_client_id_does_not_create_second_position(self):
        ex = self.exchange()
        plan = self.plan()
        ex.set_leverage(plan.symbol, plan.leverage)
        fill1 = ex.open_market(plan, client_order_id="NBV3E-dup")
        fill2 = ex.open_market(plan, client_order_id="NBV3E-dup")
        self.assertEqual(fill1, fill2)
        self.assertEqual(ex.position_snapshot().quantity, plan.quantity)

    def test_client_id_reuse_with_different_plan_fails_closed(self):
        ex = self.exchange()
        p1 = self.plan(quantity=2.0)
        ex.set_leverage(p1.symbol, p1.leverage)
        ex.open_market(p1, client_order_id="NBV3E-reuse")
        p2 = self.plan(quantity=3.0)
        with self.assertRaisesRegex(PaperExchangeError, "PLAN_MISMATCH"):
            ex.open_market(p2, client_order_id="NBV3E-reuse")

    def test_second_distinct_entry_is_rejected_while_open(self):
        ex = self.exchange()
        p = self.plan()
        ex.set_leverage(p.symbol, p.leverage)
        ex.open_market(p, client_order_id="NBV3E-first")
        with self.assertRaisesRegex(PaperExchangeError, "POSITION_ALREADY_OPEN"):
            ex.open_market(p, client_order_id="NBV3E-second")

    def test_recover_inflight_returns_none_when_unknown(self):
        ex = self.exchange()
        self.assertIsNone(ex.recover_inflight_entry(self.plan(), client_order_id="NBV3E-missing"))

    def test_recover_inflight_returns_exact_durable_fill_after_restart(self):
        ex = self.exchange()
        p = self.plan()
        ex.set_leverage(p.symbol, p.leverage)
        fill = ex.open_market(p, client_order_id="NBV3E-recover")
        ex2 = self.exchange()
        recovered = ex2.recover_inflight_entry(p, client_order_id="NBV3E-recover")
        self.assertEqual(recovered, fill)

    def test_position_snapshot_exists_before_stop_is_attached(self):
        ex = self.exchange()
        p = self.plan()
        ex.set_leverage(p.symbol, p.leverage)
        fill = ex.open_market(p, client_order_id="NBV3E-unprotected-window")
        pos = ex.position_snapshot()
        self.assertEqual(pos.quantity, fill.quantity)
        self.assertIsNone(ex.protective_stop_snapshot(p.symbol))

    def test_entry_lifecycle_integrates_with_real_paper_exchange_long(self):
        market = FakeMarket(bid=99.9, ask=100.1, timestamp_ms=1_000)
        ex = self.exchange(market=market)
        state = ExecutionStateStore(
            self.root / "data/execution/paper/execution_state.json",
            profile="live-paper",
            market_environment="LIVE",
        )
        state.set_entries_enabled(True)
        lifecycle = EntryLifecycle(
            exchange=ex,
            state=state,
            risk=RiskManager(),
            emergency=EmergencyFlattener(exchange=ex, sleep=lambda _: None),
            config=EntryLifecycleConfig(
                profile="live-paper",
                market_environment="LIVE",
                allowed_entry_authorities=frozenset({"TEST"}),
                allowed_exit_policies=frozenset({"INTEGER_R_STEP_CONTROL"}),
            ),
        )
        proposal = EntryProposal(
            proposal_id="proposal-paper-integration-long",
            generated_at_ms=900,
            expires_at_ms=2_000,
            profile="live-paper",
            market_environment="LIVE",
            symbol="BTCUSDT",
            side="LONG",
            reference_price=100.0,
            entry_authority="TEST",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
        )
        opened = lifecycle.execute(proposal, now_ms=1_000)
        self.assertEqual(state.open_position, opened)
        self.assertIsNone(state.entry_inflight)
        self.assertEqual(ex.position_snapshot().side, "LONG")
        self.assertIsNotNone(ex.protective_stop_snapshot("BTCUSDT"))

    def test_entry_lifecycle_integrates_with_real_paper_exchange_short(self):
        market = FakeMarket(bid=99.9, ask=100.1, timestamp_ms=1_000)
        ex = self.exchange(market=market)
        state = ExecutionStateStore(
            self.root / "data/execution/paper/execution_state.json",
            profile="live-paper",
            market_environment="LIVE",
        )
        state.set_entries_enabled(True)
        lifecycle = EntryLifecycle(
            exchange=ex,
            state=state,
            risk=RiskManager(),
            emergency=EmergencyFlattener(exchange=ex, sleep=lambda _: None),
            config=EntryLifecycleConfig(
                profile="live-paper",
                market_environment="LIVE",
                allowed_entry_authorities=frozenset({"TEST"}),
                allowed_exit_policies=frozenset({"INTEGER_R_STEP_CONTROL"}),
            ),
        )
        proposal = EntryProposal(
            proposal_id="proposal-paper-integration-short",
            generated_at_ms=900,
            expires_at_ms=2_000,
            profile="live-paper",
            market_environment="LIVE",
            symbol="BTCUSDT",
            side="SHORT",
            reference_price=100.0,
            entry_authority="TEST",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
        )
        opened = lifecycle.execute(proposal, now_ms=1_000)
        self.assertEqual(state.open_position, opened)
        self.assertEqual(ex.position_snapshot().side, "SHORT")
        self.assertIsNotNone(ex.protective_stop_snapshot("BTCUSDT"))

    # Protection --------------------------------------------------------------

    def test_ensure_initial_long_stop(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex, side="LONG")
        self.assertEqual(stop.trigger_price, 95.0)
        self.assertTrue(ex.validate_protective_stop(p.symbol, p.side, 95.0))

    def test_ensure_initial_short_stop(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex, side="SHORT")
        self.assertEqual(stop.trigger_price, 105.0)
        self.assertTrue(ex.validate_protective_stop(p.symbol, p.side, 105.0))

    def test_invalid_long_initial_stop_direction_rejected(self):
        ex = self.exchange()
        p = self.plan(side="LONG")
        ex.set_leverage(p.symbol, p.leverage)
        fill = ex.open_market(p, client_order_id="NBV3E-bad-stop-long")
        with self.assertRaisesRegex(PaperExchangeError, "LONG_STOP_INVALID"):
            ex.ensure_protective_stop(p.symbol, p.side, fill.quantity, fill.price + 1)

    def test_invalid_short_initial_stop_direction_rejected(self):
        ex = self.exchange()
        p = self.plan(side="SHORT")
        ex.set_leverage(p.symbol, p.leverage)
        fill = ex.open_market(p, client_order_id="NBV3E-bad-stop-short")
        with self.assertRaisesRegex(PaperExchangeError, "SHORT_STOP_INVALID"):
            ex.ensure_protective_stop(p.symbol, p.side, fill.quantity, fill.price - 1)

    def test_ensure_same_stop_is_idempotent(self):
        ex = self.exchange()
        p, fill, stop1 = self.open_and_protect(ex)
        stop2 = ex.ensure_protective_stop(p.symbol, p.side, fill.quantity, 95.0)
        self.assertEqual(stop1, stop2)

    def test_ensure_different_stop_does_not_silently_replace(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex)
        with self.assertRaisesRegex(PaperExchangeError, "DIFFERENT_PROTECTIVE_STOP"):
            ex.ensure_protective_stop(p.symbol, p.side, fill.quantity, 96.0)

    def test_stop_snapshot_wrong_symbol_returns_none(self):
        ex = self.exchange()
        self.open_and_protect(ex)
        self.assertIsNone(ex.protective_stop_snapshot("ETHUSDT"))

    def test_validate_stop_false_for_wrong_price(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex)
        self.assertFalse(ex.validate_protective_stop(p.symbol, p.side, 94.0))

    def test_replace_long_stop_tightens_and_changes_identity(self):
        ex = self.exchange()
        p, fill, old = self.open_and_protect(ex, side="LONG")
        new = ex.replace_protective_stop(p.symbol, p.side, fill.quantity, 97.0)
        self.assertGreater(new.trigger_price, old.trigger_price)
        self.assertNotEqual(new.stop_id, old.stop_id)
        self.assertEqual(ex.protective_stop_snapshot(p.symbol), new)

    def test_replace_short_stop_tightens_and_changes_identity(self):
        ex = self.exchange()
        p, fill, old = self.open_and_protect(ex, side="SHORT")
        new = ex.replace_protective_stop(p.symbol, p.side, fill.quantity, 103.0)
        self.assertLess(new.trigger_price, old.trigger_price)
        self.assertNotEqual(new.stop_id, old.stop_id)

    def test_replace_long_stop_cannot_loosen(self):
        ex = self.exchange()
        p, fill, old = self.open_and_protect(ex, side="LONG")
        with self.assertRaisesRegex(PaperExchangeError, "LOOSEN_FORBIDDEN"):
            ex.replace_protective_stop(p.symbol, p.side, fill.quantity, 94.0)

    def test_replace_short_stop_cannot_loosen(self):
        ex = self.exchange()
        p, fill, old = self.open_and_protect(ex, side="SHORT")
        with self.assertRaisesRegex(PaperExchangeError, "LOOSEN_FORBIDDEN"):
            ex.replace_protective_stop(p.symbol, p.side, fill.quantity, 106.0)

    def test_replace_requires_existing_stop(self):
        ex = self.exchange()
        p = self.plan()
        ex.set_leverage(p.symbol, p.leverage)
        fill = ex.open_market(p, client_order_id="NBV3E-no-stop")
        with self.assertRaisesRegex(PaperExchangeError, "PROTECTIVE_STOP_MISSING"):
            ex.replace_protective_stop(p.symbol, p.side, fill.quantity, 96.0)

    def test_stop_identity_survives_restart(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex)
        ex2 = self.exchange()
        self.assertEqual(ex2.protective_stop_snapshot(p.symbol), stop)

    def test_unprotected_position_survives_restart_as_unprotected(self):
        ex = self.exchange()
        p = self.plan()
        ex.set_leverage(p.symbol, p.leverage)
        ex.open_market(p, client_order_id="NBV3E-crash-before-stop")
        ex2 = self.exchange()
        self.assertIsNotNone(ex2.position_snapshot())
        self.assertIsNone(ex2.protective_stop_snapshot(p.symbol))

    # Stop settlement ---------------------------------------------------------

    def test_non_triggering_tick_keeps_long_open(self):
        ex = self.exchange()
        self.open_and_protect(ex, side="LONG")
        close = ex.on_market_tick(symbol="BTCUSDT", bid=96.0, ask=96.2, timestamp_ms=2_000)
        self.assertIsNone(close)
        self.assertIsNotNone(ex.position_snapshot())

    def test_long_stop_trigger_closes_at_observed_bid_with_exit_slippage(self):
        ex = self.exchange()
        self.open_and_protect(ex, side="LONG")
        close = ex.on_market_tick(symbol="BTCUSDT", bid=94.0, ask=94.2, timestamp_ms=2_000)
        self.assertAlmostEqual(close.price, 94.0 * 0.998)
        self.assertEqual(close.reason, "STOP_LOSS")
        self.assertIsNone(ex.position_snapshot())

    def test_short_stop_trigger_closes_at_observed_ask_with_exit_slippage(self):
        ex = self.exchange()
        self.open_and_protect(ex, side="SHORT")
        close = ex.on_market_tick(symbol="BTCUSDT", bid=106.0, ask=106.2, timestamp_ms=2_000)
        self.assertAlmostEqual(close.price, 106.2 * 1.002)
        self.assertEqual(close.reason, "STOP_LOSS")

    def test_gap_through_stop_uses_worse_observed_market_not_stop_price(self):
        ex = self.exchange()
        self.open_and_protect(ex, side="LONG")
        close = ex.on_market_tick(symbol="BTCUSDT", bid=90.0, ask=90.2, timestamp_ms=2_000)
        self.assertLess(close.price, 95.0)

    def test_other_symbol_tick_does_not_touch_position(self):
        ex = self.exchange()
        self.open_and_protect(ex)
        ex.on_market_tick(symbol="ETHUSDT", bid=1.0, ask=1.1, timestamp_ms=2_000)
        self.assertIsNotNone(ex.position_snapshot())

    # Close/accounting/recovery ----------------------------------------------

    def test_manual_long_close_uses_bid_and_after_fee_realized_pnl(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex, side="LONG")
        self.market.set_quote("BTCUSDT", 110.0, 110.2, 3_000)
        close = ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
        exit_price = 110.0 * 0.998
        gross = (exit_price - fill.price) * fill.quantity
        expected = gross - fill.price * fill.quantity * 0.001 - exit_price * fill.quantity * 0.001
        self.assertAlmostEqual(close.realized_pnl_usd, expected)
        self.assertAlmostEqual(close.theoretical_pnl_usd, gross)
        self.assertEqual(close.source, "PAPER_ACCOUNT")

    def test_manual_short_close_uses_ask(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex, side="SHORT")
        self.market.set_quote("BTCUSDT", 90.0, 90.2, 3_000)
        close = ex.close_position("BTCUSDT", "SHORT", reason="MANUAL")
        self.assertAlmostEqual(close.price, 90.2 * 1.002)
        self.assertGreater(close.realized_pnl_usd, 0)

    def test_close_reason_is_preserved(self):
        ex = self.exchange()
        self.open_and_protect(ex)
        self.market.set_quote("BTCUSDT", 102.0, 102.2, 3_000)
        close = ex.close_position("BTCUSDT", "LONG", reason="EMERGENCY_TEST")
        self.assertEqual(close.reason, "EMERGENCY_TEST")

    def test_close_clears_stop_and_position_atomically(self):
        ex = self.exchange()
        self.open_and_protect(ex)
        self.market.set_quote("BTCUSDT", 102.0, 102.2, 3_000)
        ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
        raw = json.loads(ex.account_path.read_text())
        self.assertIsNone(raw["position"])
        self.assertIsNone(raw["protective_stop"])

    def test_balance_updates_by_realized_pnl(self):
        ex = self.exchange()
        self.open_and_protect(ex)
        self.market.set_quote("BTCUSDT", 110.0, 110.2, 3_000)
        close = ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
        self.assertAlmostEqual(ex.account_snapshot().available_balance_usd, 10_000.0 + close.realized_pnl_usd)

    def test_recover_closed_position_returns_exact_durable_close(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex, client_id="NBV3E-close-recover")
        local = self.local_open(plan=p, fill=fill, stop=stop)
        self.market.set_quote("BTCUSDT", 110.0, 110.2, 3_000)
        close = ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
        ex2 = self.exchange()
        self.assertEqual(ex2.recover_closed_position(local), close)

    def test_recover_closed_position_without_evidence_fails_closed(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex)
        local = self.local_open(plan=p, fill=fill, stop=stop)
        with self.assertRaisesRegex(PaperExchangeError, "CLOSE_EVIDENCE_NOT_FOUND"):
            # Use a local identity that was never closed.
            ex.recover_closed_position(local)

    def test_recover_closed_inflight_entry_returns_exact_close(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex, client_id="NBV3E-inflight-close")
        inflight = EntryInflight(
            proposal_id="proposal-inflight",
            entry_authority="TEST",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
            plan=p,
            client_order_id=fill.client_order_id,
            started_at_ms=900,
            fill=fill,
        )
        self.market.set_quote("BTCUSDT", 110.0, 110.2, 3_000)
        close = ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
        ex2 = self.exchange()
        self.assertEqual(ex2.recover_closed_inflight_entry(inflight), close)

    def test_recover_closed_inflight_requires_confirmed_fill(self):
        ex = self.exchange()
        p = self.plan()
        inflight = EntryInflight(
            proposal_id="proposal-no-fill",
            entry_authority="TEST",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
            plan=p,
            client_order_id="NBV3E-no-fill",
            started_at_ms=900,
            fill=None,
        )
        with self.assertRaisesRegex(PaperExchangeError, "INFLIGHT_CLOSE_REQUIRES_FILL"):
            ex.recover_closed_inflight_entry(inflight)

    def test_second_close_request_while_flat_is_not_fabricated(self):
        ex = self.exchange()
        self.open_and_protect(ex)
        self.market.set_quote("BTCUSDT", 102.0, 102.2, 3_000)
        ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
        with self.assertRaisesRegex(PaperExchangeError, "POSITION_NOT_FOUND"):
            ex.close_position("BTCUSDT", "LONG", reason="MANUAL_AGAIN")

    def test_closed_account_survives_restart_flat_with_history(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex, client_id="NBV3E-history")
        local = self.local_open(plan=p, fill=fill, stop=stop)
        self.market.set_quote("BTCUSDT", 110.0, 110.2, 3_000)
        close = ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
        ex2 = self.exchange()
        self.assertIsNone(ex2.position_snapshot())
        self.assertEqual(ex2.recover_closed_position(local), close)

    def test_valid_orphan_stop_is_loaded_for_explicit_reconciliation_cleanup(self):
        ex = self.exchange()
        raw = json.loads(ex.account_path.read_text())
        raw["protective_stop"] = {
            "symbol": "BTCUSDT",
            "side": "LONG",
            "quantity": 1.0,
            "trigger_price": 90.0,
            "stop_id": "S-1",
            "client_stop_id": None,
        }
        ex.account_path.write_text(json.dumps(raw))
        ex2 = self.exchange()
        self.assertIsNotNone(ex2.protective_stop_snapshot("BTCUSDT"))
        self.assertEqual(ex2.cleanup_orphan_protective_stops(), 1)
        self.assertIsNone(ex2.protective_stop_snapshot("BTCUSDT"))

    def test_orphan_cleanup_returns_zero_when_none_exists(self):
        ex = self.exchange()
        self.assertEqual(ex.cleanup_orphan_protective_stops(), 0)

    def test_orphan_cleanup_never_removes_stop_from_open_position(self):
        ex = self.exchange()
        p, fill, stop = self.open_and_protect(ex)
        self.assertEqual(ex.cleanup_orphan_protective_stops(), 0)
        self.assertEqual(ex.protective_stop_snapshot(p.symbol), stop)

    def test_corrupt_orphan_stop_still_fails_closed_on_load(self):
        ex = self.exchange()
        raw = json.loads(ex.account_path.read_text())
        raw["protective_stop"] = {"symbol": "BTCUSDT"}
        ex.account_path.write_text(json.dumps(raw))
        with self.assertRaises(PaperExchangeError):
            self.exchange()


if __name__ == "__main__":
    unittest.main()
