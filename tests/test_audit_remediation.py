"""Regression tests for the source-audit corrections.

Windows tests exercise state transitions with persistence replaced in memory;
they do not claim to validate POSIX durability or process locks.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from nbot.common.atomic_io import atomic_write_json
from nbot.execution.state import ExecutionStateStore
from nbot.exchange.limits import ExchangeCooldown, RequestBudget
from nbot.exchange.binance_testnet import BinanceTestnetExchange
from nbot.exchange.contracts import EntryPlan, ExchangePosition


class AuditStateTests(unittest.TestCase):
    def test_permission_failure_closes_temporary_file_and_preserves_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            target.write_text('{"safe": true}')
            with patch("nbot.common.atomic_io.os.chmod", side_effect=PermissionError("denied")):
                with self.assertRaises(PermissionError):
                    atomic_write_json(target, {"replacement": True})
            self.assertEqual(json.loads(target.read_text()), {"safe": True})
            self.assertEqual(list(Path(tmp).iterdir()), [target])

    def test_gate_change_cannot_overwrite_a_concurrent_reservation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(ExecutionStateStore, "_persist"):
            state = ExecutionStateStore(Path(tmp) / "state.json", profile="live-paper", market_environment="LIVE")
            entered, release, disabled = threading.Event(), threading.Event(), threading.Event()
            def persist(snapshot):
                if snapshot.processed_proposal_ids and not release.is_set():
                    entered.set()
                    if not release.wait(3):
                        raise AssertionError("reservation test timed out")
            state._persist = persist
            def disable():
                state.set_entries_enabled(False)
                disabled.set()
            with ThreadPoolExecutor(2) as pool:
                reservation = pool.submit(state.reserve_proposal, "order-A")
                self.assertTrue(entered.wait(2))
                gate = pool.submit(disable)
                self.assertFalse(disabled.wait(0.05))
                release.set()
                self.assertTrue(reservation.result(timeout=2))
                gate.result(timeout=2)
            self.assertEqual(state.snapshot.processed_proposal_ids, ("order-A",))
            self.assertFalse(state.snapshot.entries_enabled)

    def test_concurrent_atomic_writes_have_unique_temporary_paths(self):
        with tempfile.TemporaryDirectory() as tmp, patch("nbot.common.atomic_io._fsync_directory"):
            target = Path(tmp) / "operator.json"
            barrier = threading.Barrier(2)
            import nbot.common.atomic_io as io
            real_replace = io.os.replace
            sources = []
            def replace(source, destination):
                sources.append(str(source))
                barrier.wait(timeout=3)
                real_replace(source, destination)
            with patch.object(io.os, "replace", side_effect=replace), ThreadPoolExecutor(2) as pool:
                jobs = [pool.submit(atomic_write_json, target, {"value": n}) for n in (1, 2)]
                for job in jobs:
                    job.result(timeout=5)
            self.assertEqual(len(set(sources)), 2)
            self.assertIn(json.loads(target.read_text())["value"], (1, 2))

    def test_nonfinite_json_never_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch("nbot.common.atomic_io._fsync_directory"):
            target = Path(tmp) / "state.json"
            atomic_write_json(target, {"safe": True})
            with self.assertRaises(ValueError):
                atomic_write_json(target, {"unsafe": float("nan")})
            self.assertEqual(json.loads(target.read_text()), {"safe": True})


class AuditBudgetTests(unittest.TestCase):
    def test_ban_and_budget_survive_new_process_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            now = [1000.0]
            kwargs = dict(state_path=Path(tmp) / "budget.db", wall_clock=lambda: now[0], ceiling=10)
            first = RequestBudget(**kwargs)
            first.acquire(8)
            with self.assertRaises(ExchangeCooldown):
                RequestBudget(**kwargs).acquire(3)
            first.observe({"Retry-After": "120"}, 418)
            now[0] += 70
            with self.assertRaisesRegex(ExchangeCooldown, "COOLDOWN"):
                RequestBudget(**kwargs).acquire(1)
            now[0] += 51
            RequestBudget(**kwargs).acquire(1)

    def test_corrupt_budget_blocks_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.db"
            path.write_text("corrupt")
            with self.assertRaisesRegex(ExchangeCooldown, "STORAGE"):
                RequestBudget(state_path=path).acquire(1)

    def test_live_public_cooldown_uses_adapter_error_and_sends_no_request(self):
        from nbot.exchange.binance_public import BinanceLivePublicMarketData, BinanceLivePublicMarketError
        network = Mock()
        client = BinanceLivePublicMarketData(urlopen_fn=network)
        budget = RequestBudget()
        budget.observe({"Retry-After": "60"}, 429)
        with patch("nbot.exchange.binance_public.budget_for", return_value=budget):
            with self.assertRaisesRegex(BinanceLivePublicMarketError, "COOLDOWN"):
                client._get("/fapi/v1/time")
        network.assert_not_called()

    def test_cooldown_blocks_all_callers_until_deadline(self):
        now = [0.0]
        budget = RequestBudget(clock=lambda: now[0])
        budget.observe({"Retry-After": "20"}, 429)
        with self.assertRaises(ExchangeCooldown):
            budget.acquire(1)
        now[0] = 20
        budget.acquire(1)


class AuditRecoveryTests(unittest.TestCase):
    def test_missing_order_after_ambiguous_write_is_not_treated_as_unfilled(self):
        exchange = self.exchange()
        exchange._query_order = Mock(return_value=None)
        exchange.position_snapshot = Mock(return_value=None)
        from nbot.exchange.binance_testnet import TestnetExchangeError
        with patch("nbot.exchange.binance_testnet.time.monotonic", side_effect=[0, 0, 2]), patch("nbot.exchange.binance_testnet.time.sleep"):
            with self.assertRaisesRegex(TestnetExchangeError, "UNRESOLVED"):
                exchange.recover_inflight_entry(self.plan(), client_order_id="entry-A")

    def test_income_total_cannot_replace_missing_close_fills(self):
        from nbot.exchange.binance_testnet import TestnetExchangeError
        exchange = self.exchange()
        exchange._signed_get = Mock(return_value=[])
        exchange._realized_pnl_income = Mock(return_value=999)
        with self.assertRaisesRegex(TestnetExchangeError, "ACCOUNTING_UNAVAILABLE"):
            exchange._settle_close_order(ExchangePosition("BTCUSDT", "LONG", 2, 100), self.order(), "TEST")
        exchange._realized_pnl_income.assert_not_called()

    def test_order_fill_pagination_uses_progressing_trade_ids(self):
        exchange = self.exchange()
        page = [{"id": n, "orderId": 7, "symbol": "BTCUSDT", "qty": 0.001,
                 "price": 101, "realizedPnl": 0.001, "time": 2000} for n in range(1000)]
        exchange._signed_get = Mock(side_effect=[page, [dict(page[-1], id=1000)]])
        self.assertEqual(len(exchange._order_trades("BTCUSDT", "7")), 1001)
        self.assertEqual(exchange._signed_get.call_args_list[1].args[1]["fromId"], 1000)

    def exchange(self):
        exchange = object.__new__(BinanceTestnetExchange)
        exchange.config = SimpleNamespace(entry_resolution_timeout_seconds=1, close_settlement_retries=2, close_settlement_retry_seconds=0)
        exchange._filters = {"BTCUSDT": {"market_step": 0.01}}
        return exchange

    def plan(self):
        return EntryPlan(symbol="BTCUSDT", side="LONG", quantity=2, expected_entry_price=100,
                         initial_stop_price=95, initial_risk_usd=10, notional_usd=200, leverage=2)

    def order(self, *, status="FILLED", quantity=2):
        return {"status": status, "executedQty": quantity, "avgPrice": 100, "cumQuote": quantity * 100,
                "orderId": 7, "clientOrderId": "entry-A", "updateTime": 1000}

    def test_historical_fill_is_recovered_even_when_now_flat(self):
        exchange = self.exchange()
        exchange._query_order = Mock(return_value=self.order())
        exchange.position_snapshot = Mock(return_value=None)
        fill = exchange.recover_inflight_entry(self.plan(), client_order_id="entry-A")
        self.assertEqual(fill.quantity, 2)
        self.assertEqual(fill.order_id, "7")

    def test_terminal_partial_fill_is_not_discarded(self):
        exchange = self.exchange()
        exchange._query_order = Mock(return_value=self.order(status="EXPIRED", quantity=1))
        exchange.position_snapshot = Mock(return_value=ExchangePosition("BTCUSDT", "LONG", 1, 100))
        fill = exchange.recover_inflight_entry(self.plan(), client_order_id="entry-A")
        self.assertEqual(fill.quantity, 1)

    def test_pending_partial_is_protected_before_cancel(self):
        exchange = self.exchange()
        exchange._query_order = Mock(side_effect=[self.order(status="PARTIALLY_FILLED", quantity=1), self.order(status="CANCELED", quantity=1)])
        exchange.position_snapshot = Mock(return_value=ExchangePosition("BTCUSDT", "LONG", 1, 100))
        events = []
        exchange.ensure_protective_stop = lambda *a: events.append("protect")
        exchange._signed_delete = lambda *a, **kw: events.append("cancel")
        fill = exchange.recover_inflight_entry(self.plan(), client_order_id="entry-A")
        self.assertEqual(events, ["protect", "cancel"])
        self.assertEqual(fill.quantity, 1)

    def test_close_accounting_waits_for_all_fill_quantity(self):
        exchange = self.exchange()
        first = {"symbol": "BTCUSDT", "orderId": 7, "qty": 1, "price": 101, "realizedPnl": 1, "time": 2000}
        exchange._signed_get = Mock(side_effect=[[first], [first, dict(first, time=2001)]])
        exchange._realized_pnl_income = Mock(return_value=None)
        close = exchange._settle_close_order(ExchangePosition("BTCUSDT", "LONG", 2, 100), self.order(), "TEST")
        self.assertEqual(exchange._signed_get.call_count, 2)
        self.assertEqual(close.realized_pnl_usd, 2)

    def test_remote_usage_counts_against_local_budget(self):
        budget = RequestBudget(ceiling=100)
        budget.observe({"X-MBX-USED-WEIGHT-1M": "99"})
        with self.assertRaises(ExchangeCooldown):
            budget.acquire(2)

    def test_malformed_retry_after_is_conservative(self):
        budget = RequestBudget()
        budget.observe({"Retry-After": "nan"}, 418)
        with self.assertRaises(ExchangeCooldown):
            budget.acquire(1)


class AuditLearningTests(unittest.TestCase):
    def rows(self, value=1.0):
        from nbot.observation.selection import FEATURE_VECTOR_NAMES
        return [{"feature_vector_json": json.dumps(dict.fromkeys(FEATURE_VECTOR_NAMES, value)), "target_net_r": value}]

    def test_unknown_labels_cannot_change_an_earlier_prediction(self):
        from nbot.observation.selection import RidgeSufficientStatistics
        from nbot.observation.causal_ridge import LABEL_HORIZON_MS
        left, right = RidgeSufficientStatistics.empty(), RidgeSufficientStatistics.empty()
        for event in range(1, 81):
            left.add_event(event * 300_000, self.rows(1))
            right.add_event(event * 300_000, self.rows(999 if event > 32 else 1))
        a, b = left.for_decision(81 * 300_000), right.for_decision(81 * 300_000)
        self.assertEqual(a.event_count, 32)
        self.assertLess(a.through_event_ms + LABEL_HORIZON_MS, 81 * 300_000)
        self.assertEqual(a.fit(10), b.fit(10))

    def test_delayed_queue_survives_restart(self):
        from nbot.observation.selection import RidgeSufficientStatistics
        state = RidgeSufficientStatistics.empty()
        for event in range(1, 81):
            state.add_event(event * 300_000, self.rows(event))
        restored = RidgeSufficientStatistics.from_payload(json.loads(json.dumps(state.to_payload())))
        self.assertEqual(state.for_decision(81 * 300_000).fit(10), restored.for_decision(81 * 300_000).fit(10))
        self.assertLessEqual(len(restored.pending), 49)

    def test_centered_moments_preserve_small_variance_at_large_offset(self):
        from nbot.observation.causal_ridge import CenteredMoments
        full = CenteredMoments(1)
        for event in range(1, 101):
            full.merge(CenteredMoments.event(event, [[1e9 - 1], [1e9 + 1]], [-1, 1]))
        self.assertAlmostEqual(full.cross_xx[0][0] / full.row_count, 1.0)
        self.assertAlmostEqual(full.cross_xy[0] / full.row_count, 1.0)

    def test_legacy_statistics_require_explicit_migration(self):
        from nbot.observation.selection import RidgeSufficientStatistics, EntrySelectionError
        with self.assertRaisesRegex(EntrySelectionError, "MIGRATION_REQUIRED"):
            RidgeSufficientStatistics.from_payload({"sum_y": 0})
