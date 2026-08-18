from __future__ import annotations

import json
import math
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from nbot.exchange.binance_testnet import (
    AmbiguousExecutionError,
    BinanceTestnetExchange,
    TESTNET_REST_BASE_URL,
    TESTNET_WS_BASE_URL,
    TestnetExchangeConfig,
    TestnetExchangeError,
    TestnetTradingGuard,
    initialize_testnet_guard_for_arm,
)
from nbot.exchange.contracts import EntryPlan, ExchangePort, ProtectiveStopRef
from nbot.execution.models import EntryInflight, OpenPosition
from nbot.execution.entry import EntryLifecycle, EntryLifecycleConfig, EntryProposal
from nbot.execution.emergency import EmergencyFlattener
from nbot.execution.risk import RiskManager
from nbot.execution.state import ExecutionStateStore
from nbot.execution.reconciliation import ReconciliationExchangePort


def plan(side="LONG", qty=1.0, entry=100.0, stop=None):
    if stop is None:
        stop = 90.0 if side == "LONG" else 110.0
    return EntryPlan(
        symbol="BTCUSDT",
        side=side,
        quantity=qty,
        expected_entry_price=entry,
        initial_stop_price=stop,
        initial_risk_usd=abs(entry - stop) * qty,
        notional_usd=entry * qty,
        leverage=5,
    )


class Harness(BinanceTestnetExchange):
    def __init__(self, config):
        self.calls = []
        self.bid = 99.0
        self.ask = 101.0
        self.balance = 10000.0
        self.positions = []
        self.orders = {}
        self.algos = {}
        self.user_trades = []
        self.incomes = []
        self.next_order = 1000
        self.next_algo = 2000
        self.fail_ping = False
        self.ambiguous_entry = False
        self.ambiguous_stop = False
        self.ambiguous_close = False
        self.close_leaves_position = False
        self.cancel_ambiguous_after_commit = False
        self.cancel_ambiguous_without_commit = False
        self.raw_position_rows = None
        self.raw_open_algos = None
        super().__init__(config)

    def _exchange_info(self):
        return {
            "symbols": [{
                "symbol": "BTCUSDT",
                "filters": [
                    {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "100"},
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "100"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"},
                ],
            }]
        }

    def _position_rows(self):
        if self.raw_position_rows is not None:
            return self.raw_position_rows
        return list(self.positions)

    def _open_algos(self, symbol=None):
        if self.raw_open_algos is not None:
            rows = list(self.raw_open_algos)
        else:
            rows = [v for v in self.algos.values() if v.get("algoStatus") == "NEW"]
        if symbol:
            rows = [r for r in rows if r.get("symbol") == symbol]
        return rows

    def _request(self, method, path, params=None, *, signed=False, ambiguous_write=False):
        params = dict(params or {})
        self.calls.append((method, path, dict(params), signed, ambiguous_write))
        if path == "/fapi/v1/ping":
            if self.fail_ping:
                raise TestnetExchangeError("PING_FAIL")
            return {}
        if path == "/fapi/v1/exchangeInfo":
            return self._exchange_info()
        if path == "/fapi/v1/ticker/bookTicker":
            return {"symbol": params.get("symbol"), "bidPrice": str(self.bid), "askPrice": str(self.ask), "time": 1_800_000_000_000}
        if path == "/fapi/v3/balance":
            return [{"asset": "USDT", "availableBalance": str(self.balance)}]
        if path == "/fapi/v3/positionRisk":
            return self._position_rows()
        if path == "/fapi/v1/leverage" and method == "POST":
            return {"leverage": int(params["leverage"])}
        if path == "/fapi/v1/order" and method == "GET":
            if "origClientOrderId" in params:
                for row in self.orders.values():
                    if row.get("clientOrderId") == params["origClientOrderId"]:
                        return dict(row)
            if "orderId" in params:
                row = self.orders.get(str(params["orderId"]))
                if row:
                    return dict(row)
            raise TestnetExchangeError("REST_FAILED:GET:/fapi/v1/order:400:code=-2013 msg=Order does not exist")
        if path == "/fapi/v1/order" and method == "POST":
            cid = str(params["newClientOrderId"])
            for row in self.orders.values():
                if row.get("clientOrderId") == cid:
                    return dict(row)
            self.next_order += 1
            oid = str(self.next_order)
            qty = float(params["quantity"])
            is_close = str(params.get("reduceOnly", "false")).lower() == "true"
            if is_close:
                if not self.positions:
                    raise TestnetExchangeError("NO_POSITION")
                p = self.positions[0]
                position_amt = float(p["positionAmt"])
                px = self.bid if position_amt > 0 else self.ask
                entry = float(p["entryPrice"])
                pnl = (px - entry) * qty if position_amt > 0 else (entry - px) * qty
                row = {"symbol": "BTCUSDT", "orderId": oid, "clientOrderId": cid, "status": "FILLED", "executedQty": str(qty), "avgPrice": str(px), "cumQuote": str(px * qty), "side": params["side"], "positionSide": "BOTH", "time": 1_800_000_000_100, "updateTime": 1_800_000_000_100}
                self.orders[oid] = row
                self.user_trades.append({"symbol": "BTCUSDT", "orderId": int(oid), "side": params["side"], "positionSide": "BOTH", "qty": str(qty), "price": str(px), "realizedPnl": str(pnl), "time": 1_800_000_000_100})
                self.incomes.append({"symbol": "BTCUSDT", "incomeType": "REALIZED_PNL", "income": str(pnl), "time": 1_800_000_000_100})
                if not self.close_leaves_position:
                    self.positions = []
                if self.ambiguous_close:
                    self.ambiguous_close = False
                    raise AmbiguousExecutionError("AMBIGUOUS_CLOSE")
                return dict(row)
            side = params["side"]
            px = self.ask if side == "BUY" else self.bid
            row = {"symbol": "BTCUSDT", "orderId": oid, "clientOrderId": cid, "status": "FILLED", "executedQty": str(qty), "avgPrice": str(px), "cumQuote": str(px * qty), "side": side, "positionSide": "BOTH", "time": 1_800_000_000_000, "updateTime": 1_800_000_000_000}
            self.orders[oid] = row
            self.positions = [{"symbol": "BTCUSDT", "positionAmt": str(qty if side == "BUY" else -qty), "entryPrice": str(px), "positionSide": "BOTH"}]
            if self.ambiguous_entry:
                self.ambiguous_entry = False
                raise AmbiguousExecutionError("AMBIGUOUS_ENTRY")
            return dict(row)
        if path == "/fapi/v1/openAlgoOrders" and method == "GET":
            return [dict(r) for r in self._open_algos(params.get("symbol"))]
        if path == "/fapi/v1/algoOrder" and method == "GET":
            if "algoId" in params:
                row = self.algos.get(str(params["algoId"]))
                if row:
                    return dict(row)
            if "clientAlgoId" in params:
                for row in self.algos.values():
                    if row.get("clientAlgoId") == params["clientAlgoId"]:
                        return dict(row)
            raise TestnetExchangeError("REST_FAILED:GET:/fapi/v1/algoOrder:400:code=-2013 msg=Order does not exist")
        if path == "/fapi/v1/algoOrder" and method == "POST":
            cid = str(params["clientAlgoId"])
            for row in self.algos.values():
                if row.get("clientAlgoId") == cid and row.get("algoStatus") == "NEW":
                    return {"algoId": int(row["algoId"]), "clientAlgoId": cid}
            self.next_algo += 1
            aid = str(self.next_algo)
            row = {"algoId": aid, "clientAlgoId": cid, "algoType": "CONDITIONAL", "orderType": "STOP_MARKET", "symbol": params["symbol"], "side": params["side"], "positionSide": "BOTH", "quantity": str(params["quantity"]), "triggerPrice": str(params["triggerPrice"]), "reduceOnly": True, "algoStatus": "NEW", "createTime": 1_800_000_000_010, "updateTime": 1_800_000_000_010, "actualOrderId": ""}
            self.algos[aid] = row
            if self.ambiguous_stop:
                self.ambiguous_stop = False
                raise AmbiguousExecutionError("AMBIGUOUS_STOP")
            return {"algoId": int(aid), "clientAlgoId": cid}
        if path == "/fapi/v1/algoOrder" and method == "DELETE":
            target = None
            if "algoId" in params:
                target = self.algos.get(str(params["algoId"]))
            else:
                target = next((r for r in self.algos.values() if r.get("clientAlgoId") == params.get("clientAlgoId")), None)
            if target is not None and not self.cancel_ambiguous_without_commit:
                target["algoStatus"] = "CANCELED"
            if self.cancel_ambiguous_after_commit or self.cancel_ambiguous_without_commit:
                self.cancel_ambiguous_after_commit = False
                self.cancel_ambiguous_without_commit = False
                raise AmbiguousExecutionError("AMBIGUOUS_CANCEL")
            return {"code": "200"}
        if path == "/fapi/v1/userTrades":
            rows = list(self.user_trades)
            if "orderId" in params:
                rows = [r for r in rows if int(r["orderId"]) == int(params["orderId"])]
            if "startTime" in params:
                rows = [r for r in rows if int(r["time"]) >= int(params["startTime"])]
            if "endTime" in params:
                rows = [r for r in rows if int(r["time"]) <= int(params["endTime"])]
            return [dict(r) for r in rows]
        if path == "/fapi/v1/allOrders":
            return [dict(r) for r in self.orders.values()]
        if path == "/fapi/v1/allAlgoOrders":
            return [dict(r) for r in self.algos.values()]
        if path == "/fapi/v1/income":
            return [dict(r) for r in self.incomes]
        raise AssertionError((method, path, params))


def arm(config: TestnetExchangeConfig, *, sha="abc", armed_at="2026-08-18T12:00:00Z"):
    path = config.resolved_arm_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"profile=testnet-trade\nsha={sha}\narmed_at={armed_at}\n")
    TestnetTradingGuard(config).initialize_new_arm_session()


def loaded_exchange(tmp: Path, **cfg_overrides):
    cfg = TestnetExchangeConfig(api_key="key", api_secret="secret", repo_root=tmp, entry_resolution_timeout_seconds=0.01, stop_resolution_timeout_seconds=0.01, close_settlement_retries=1, close_settlement_retry_seconds=0.0, **cfg_overrides)
    ex = Harness(cfg)
    ex._load_filters()
    return ex


class V319ConfigTests(unittest.TestCase):
    def test_default_hosts_are_pinned_demo_hosts(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=Path(td))
            self.assertEqual(cfg.base_url, TESTNET_REST_BASE_URL)
            self.assertEqual(cfg.ws_base_url, TESTNET_WS_BASE_URL)
            cfg.validate()

    def test_rejects_live_rest_host(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=Path(td), base_url="https://fapi.binance.com")
            with self.assertRaisesRegex(ValueError, "TESTNET_REST_HOST_INVALID"):
                cfg.validate()

    def test_rejects_lookalike_rest_host(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=Path(td), base_url="https://demo-fapi.binance.com.evil.test")
            with self.assertRaises(ValueError):
                cfg.validate()

    def test_rejects_rest_path_injection(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=Path(td), base_url="https://demo-fapi.binance.com/evil")
            with self.assertRaisesRegex(ValueError, "TESTNET_REST_URL_INVALID"):
                cfg.validate()

    def test_rejects_wrong_ws_host(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=Path(td), ws_base_url="wss://fstream.binance.com")
            with self.assertRaisesRegex(ValueError, "TESTNET_WS_HOST_INVALID"):
                cfg.validate()

    def test_missing_credentials_fail(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = TestnetExchangeConfig(api_key="", api_secret="", repo_root=Path(td))
            with self.assertRaisesRegex(ValueError, "TESTNET_CREDENTIALS_MISSING"):
                cfg.validate()

    def test_recv_window_over_60000_fails(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=Path(td), recv_window_ms=60001)
            with self.assertRaisesRegex(ValueError, "TESTNET_RECV_WINDOW_INVALID"):
                cfg.validate()

    def test_signature_is_stable_hmac_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            got = ex._signature({"symbol": "BTCUSDT", "timestamp": 123})
            import hashlib, hmac
            expected = hmac.new(b"secret", b"symbol=BTCUSDT&timestamp=123", hashlib.sha256).hexdigest()
            self.assertEqual(got, expected)

    def test_stop_quantization_never_loosens_requested_risk_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            self.assertEqual(ex._stop_price("BTCUSDT", "LONG", 99.01), 99.1)
            self.assertEqual(ex._stop_price("BTCUSDT", "SHORT", 100.09), 100.0)


class V319GuardTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.cfg = TestnetExchangeConfig(api_key="a", api_secret="b", repo_root=self.root, max_session_entries=2, max_entry_notional_usd=200.0)

    def tearDown(self):
        self.td.cleanup()

    def test_unarmed_initial_state_is_created(self):
        guard = TestnetTradingGuard(self.cfg)
        guard.initialize_unarmed_state()
        report = guard.preflight()
        self.assertFalse(report["armed"])
        self.assertEqual(report["session_entries"], 0)

    def test_arm_without_bound_state_fails_closed(self):
        self.cfg.resolved_arm_file.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.resolved_arm_file.write_text("profile=testnet-trade\nsha=x\narmed_at=t\n")
        report = TestnetTradingGuard(self.cfg).preflight()
        self.assertFalse(report["armed"])
        self.assertIn("MISSING_WHILE_ARMED", report["reason"])

    def test_arm_initialization_binds_session(self):
        arm(self.cfg)
        report = TestnetTradingGuard(self.cfg).preflight()
        self.assertTrue(report["armed"])
        self.assertEqual(report["session_entries"], 0)

    def test_rearm_without_state_rebind_fails(self):
        arm(self.cfg, armed_at="one")
        self.cfg.resolved_arm_file.write_text("profile=testnet-trade\nsha=abc\narmed_at=two\n")
        report = TestnetTradingGuard(self.cfg).preflight()
        self.assertFalse(report["armed"])
        self.assertIn("MISMATCH", report["reason"])

    def test_explicit_rearm_resets_count(self):
        arm(self.cfg, armed_at="one")
        guard = TestnetTradingGuard(self.cfg)
        guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.assertEqual(guard.preflight()["session_entries"], 1)
        arm(self.cfg, armed_at="two")
        self.assertEqual(TestnetTradingGuard(self.cfg).preflight()["session_entries"], 0)

    def test_count_survives_guard_restart(self):
        arm(self.cfg)
        TestnetTradingGuard(self.cfg).authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.assertEqual(TestnetTradingGuard(self.cfg).preflight()["session_entries"], 1)

    def test_session_limit_enforced(self):
        arm(self.cfg)
        guard = TestnetTradingGuard(self.cfg)
        guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        with self.assertRaisesRegex(TestnetExchangeError, "SESSION_ENTRY_LIMIT"):
            guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)

    def test_notional_limit_enforced(self):
        arm(self.cfg)
        with self.assertRaisesRegex(TestnetExchangeError, "NOTIONAL_LIMIT"):
            TestnetTradingGuard(self.cfg).authorize_entry(symbol="BTCUSDT", quantity=3, price=100, position=None)

    def test_existing_position_blocks(self):
        arm(self.cfg)
        from nbot.exchange.contracts import ExchangePosition
        pos = ExchangePosition("BTCUSDT", "LONG", 1, 100)
        with self.assertRaisesRegex(TestnetExchangeError, "POSITION_EXISTS"):
            TestnetTradingGuard(self.cfg).authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=pos)

    def test_corrupt_guard_state_fails_closed(self):
        arm(self.cfg)
        self.cfg.resolved_guard_state_path.write_text("not json")
        report = TestnetTradingGuard(self.cfg).preflight()
        self.assertFalse(report["armed"])
        self.assertIn("GUARD_STATE_INVALID", report["reason"])

    def test_helper_initializes_current_nbotctl_arm(self):
        self.cfg.resolved_arm_file.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.resolved_arm_file.write_text("profile=testnet-trade\nsha=abc\narmed_at=now\n")
        initialize_testnet_guard_for_arm(self.root)
        self.assertTrue(TestnetTradingGuard(self.cfg).preflight()["armed"])


class V319TruthAndLockTests(unittest.TestCase):
    def test_connect_acquires_single_instance_and_disconnect_releases(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = loaded_exchange(root)
            second = loaded_exchange(root)
            first.connect()
            self.assertTrue(first.is_healthy())
            with self.assertRaisesRegex(TestnetExchangeError, "INSTANCE_LOCK_HELD"):
                second.connect()
            first.disconnect()
            second.connect()
            self.assertTrue(second.is_healthy())
            second.disconnect()

    def test_connect_failure_releases_instance_lock(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = loaded_exchange(root)
            first.fail_ping = True
            with self.assertRaisesRegex(TestnetExchangeError, "PING_FAIL"):
                first.connect()
            second = loaded_exchange(root)
            second.connect()
            second.disconnect()

    def test_quote_balance_and_flat_position(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            q = ex.quote("BTCUSDT")
            self.assertEqual((q.bid, q.ask), (99.0, 101.0))
            self.assertEqual(ex.account_snapshot().available_balance_usd, 10000.0)
            self.assertIsNone(ex.position_snapshot())

    def test_long_and_short_position_truth(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            ex.positions = [{"symbol": "BTCUSDT", "positionAmt": "2", "entryPrice": "100", "positionSide": "BOTH"}]
            self.assertEqual(ex.position_snapshot().side, "LONG")
            ex.positions = [{"symbol": "BTCUSDT", "positionAmt": "-2", "entryPrice": "100", "positionSide": "BOTH"}]
            self.assertEqual(ex.position_snapshot().side, "SHORT")

    def test_hedge_mode_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            ex.raw_position_rows = [{"symbol": "BTCUSDT", "positionAmt": "1", "entryPrice": "100", "positionSide": "LONG"}]
            with self.assertRaisesRegex(TestnetExchangeError, "HEDGE_MODE_UNSUPPORTED"):
                ex.position_snapshot()

    def test_multiple_positions_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            ex.raw_position_rows = [
                {"symbol": "BTCUSDT", "positionAmt": "1", "entryPrice": "100", "positionSide": "BOTH"},
                {"symbol": "ETHUSDT", "positionAmt": "1", "entryPrice": "50", "positionSide": "BOTH"},
            ]
            with self.assertRaisesRegex(TestnetExchangeError, "MULTIPLE_POSITIONS"):
                ex.position_snapshot()

    def test_validate_stop_uses_executable_side(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            self.assertTrue(ex.validate_protective_stop("BTCUSDT", "LONG", 90))
            self.assertFalse(ex.validate_protective_stop("BTCUSDT", "LONG", 100))
            self.assertTrue(ex.validate_protective_stop("BTCUSDT", "SHORT", 110))
            self.assertFalse(ex.validate_protective_stop("BTCUSDT", "SHORT", 100))


class V319EntryTests(unittest.TestCase):
    def test_open_long_preserves_caller_deterministic_id(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config)
            fill = ex.open_market(plan(), client_order_id="NBV3E-123")
            self.assertEqual(fill.client_order_id, "NBV3E-123")
            self.assertEqual(ex.position_snapshot().side, "LONG")

    def test_open_short(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config)
            fill = ex.open_market(plan("SHORT"), client_order_id="NBV3E-SHORT")
            self.assertEqual(fill.price, 99.0)
            self.assertEqual(ex.position_snapshot().side, "SHORT")

    def test_ambiguous_entry_not_blindly_resubmitted_and_exact_recovery_works(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config); ex.ambiguous_entry = True
            with self.assertRaises(AmbiguousExecutionError):
                ex.open_market(plan(), client_order_id="NBV3E-AMB")
            post_count = len([c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/order"])
            recovered = ex.recover_inflight_entry(plan(), client_order_id="NBV3E-AMB")
            self.assertEqual(recovered.client_order_id, "NBV3E-AMB")
            self.assertEqual(len([c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/order"]), post_count)

    def test_ambiguous_attempt_consumes_durable_session_slot(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config); ex.ambiguous_entry = True
            with self.assertRaises(AmbiguousExecutionError):
                ex.open_market(plan(), client_order_id="NBV3E-AMB")
            self.assertEqual(TestnetTradingGuard(ex.config).preflight()["session_entries"], 1)

    def test_recover_known_missing_flat_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config)
            self.assertIsNone(ex.recover_inflight_entry(plan(), client_order_id="MISSING"))

    def test_recover_filled_but_exchange_flat_requires_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config)
            ex.open_market(plan(), client_order_id="FILLED")
            ex.positions = []
            with self.assertRaisesRegex(TestnetExchangeError, "FILLED_BUT_POSITION_FLAT"):
                ex.recover_inflight_entry(plan(), client_order_id="FILLED")

    def test_set_leverage_requires_arm(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); ex.guard.initialize_unarmed_state()
            with self.assertRaisesRegex(TestnetExchangeError, "NOT_ARMED"):
                ex.set_leverage("BTCUSDT", 5)

    def test_set_leverage_confirms_exchange_response(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config)
            ex.set_leverage("BTCUSDT", 5)


class V319StopTests(unittest.TestCase):
    def _open(self, root, side="LONG"):
        ex = loaded_exchange(root); arm(ex.config)
        ex.open_market(plan(side), client_order_id="ENTRY")
        return ex

    def test_deterministic_stop_client_id_is_stable_and_bounded(self):
        a = BinanceTestnetExchange.deterministic_stop_client_id("BTCUSDT", "LONG", 1.0, 90.0)
        b = BinanceTestnetExchange.deterministic_stop_client_id("BTCUSDT", "LONG", 1.0, 90.0)
        c = BinanceTestnetExchange.deterministic_stop_client_id("BTCUSDT", "LONG", 1.0, 91.0)
        self.assertEqual(a, b); self.assertNotEqual(a, c); self.assertLessEqual(len(a), 36)

    def test_place_and_snapshot_long_stop(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            ref = ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            self.assertEqual(ref.side, "LONG")
            self.assertEqual(ex.protective_stop_snapshot("BTCUSDT"), ref)

    def test_place_short_stop(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td), "SHORT")
            ref = ex.ensure_protective_stop("BTCUSDT", "SHORT", 1, 110)
            self.assertEqual(ref.side, "SHORT")

    def test_ambiguous_stop_recovers_exact_client_identity(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td)); ex.ambiguous_stop = True
            ref = ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            self.assertTrue(ref.client_stop_id.startswith("NBV3SL-"))
            self.assertEqual(len([c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/algoOrder"]), 1)

    def test_existing_tighter_stop_is_not_loosened_by_ensure(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            first = ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 95)
            second = ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            self.assertEqual(first, second)

    def test_replacement_would_loosen_long_fails(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 95)
            with self.assertRaisesRegex(TestnetExchangeError, "WOULD_LOOSEN"):
                ex.replace_protective_stop("BTCUSDT", "LONG", 1, 94)

    def test_replacement_places_new_before_old_cancel(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            old = ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            ex.calls.clear()
            new = ex.replace_protective_stop("BTCUSDT", "LONG", 1, 95)
            post_i = next(i for i,c in enumerate(ex.calls) if c[0] == "POST" and c[1] == "/fapi/v1/algoOrder")
            delete_i = next(i for i,c in enumerate(ex.calls) if c[0] == "DELETE" and c[1] == "/fapi/v1/algoOrder")
            self.assertLess(post_i, delete_i)
            self.assertNotEqual(old.stop_id, new.stop_id)
            self.assertEqual(ex.protective_stop_snapshot("BTCUSDT").stop_id, new.stop_id)

    def test_ambiguous_cancel_after_commit_is_verified_safe(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            ex.cancel_ambiguous_after_commit = True
            ref = ex.replace_protective_stop("BTCUSDT", "LONG", 1, 95)
            self.assertEqual(ex.protective_stop_snapshot("BTCUSDT").stop_id, ref.stop_id)

    def test_ambiguous_cancel_without_commit_fails_closed_with_both_stops(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            ex.cancel_ambiguous_without_commit = True
            with self.assertRaisesRegex(TestnetExchangeError, "PRUNE_UNVERIFIED"):
                ex.replace_protective_stop("BTCUSDT", "LONG", 1, 95)

    def test_multiple_active_stops_fail_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            ex.algos["999"] = {"algoId":"999","clientAlgoId":"x","algoType":"CONDITIONAL","orderType":"STOP_MARKET","symbol":"BTCUSDT","side":"SELL","positionSide":"BOTH","quantity":"1","triggerPrice":"91","reduceOnly":True,"algoStatus":"NEW"}
            with self.assertRaisesRegex(TestnetExchangeError, "MULTIPLE_PROTECTIVE"):
                ex.protective_stop_snapshot("BTCUSDT")

    def test_orphan_cleanup_requires_flat_and_verifies_removal(self):
        with tempfile.TemporaryDirectory() as td:
            ex = self._open(Path(td))
            ex.ensure_protective_stop("BTCUSDT", "LONG", 1, 90)
            with self.assertRaisesRegex(TestnetExchangeError, "POSITION_OPEN"):
                ex.cleanup_orphan_protective_stops()
            ex.positions = []
            self.assertEqual(ex.cleanup_orphan_protective_stops(), 1)
            self.assertEqual(ex._active_stops(None), [])


class V319CloseRecoveryTests(unittest.TestCase):
    def _open_with_stop(self, root, side="LONG"):
        ex = loaded_exchange(root); arm(ex.config)
        fill = ex.open_market(plan(side), client_order_id="ENTRY")
        stop = ex.ensure_protective_stop("BTCUSDT", side, 1, 90 if side == "LONG" else 110)
        local = OpenPosition("proposal", "BTCUSDT", side, fill, 10.0, 90 if side == "LONG" else 110, stop, "AUTH", "INTEGER_R_STEP_CONTROL")
        return ex, local

    def test_close_long_returns_authoritative_user_trade_pnl(self):
        with tempfile.TemporaryDirectory() as td:
            ex, _local = self._open_with_stop(Path(td), "LONG")
            close = ex.close_position("BTCUSDT", "LONG", reason="TEST")
            self.assertAlmostEqual(close.realized_pnl_usd, -2.0)
            self.assertEqual(close.source, "USER_TRADES_ORDER")
            self.assertIsNone(ex.position_snapshot())

    def test_close_short(self):
        with tempfile.TemporaryDirectory() as td:
            ex, _local = self._open_with_stop(Path(td), "SHORT")
            close = ex.close_position("BTCUSDT", "SHORT", reason="TEST")
            self.assertAlmostEqual(close.realized_pnl_usd, -2.0)

    def test_close_response_is_not_flatness_proof(self):
        with tempfile.TemporaryDirectory() as td:
            ex, _local = self._open_with_stop(Path(td)); ex.close_leaves_position = True
            with self.assertRaisesRegex(TestnetExchangeError, "NOT_CONFIRMED_FLAT"):
                ex.close_position("BTCUSDT", "LONG", reason="TEST")

    def test_ambiguous_close_recovers_exact_order_without_second_post(self):
        with tempfile.TemporaryDirectory() as td:
            ex, _local = self._open_with_stop(Path(td)); ex.ambiguous_close = True
            close = ex.close_position("BTCUSDT", "LONG", reason="EMERGENCY")
            self.assertIsNotNone(close.realized_pnl_usd)
            close_posts = [c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/order" and c[2].get("reduceOnly") == "true"]
            self.assertEqual(len(close_posts), 1)

    def test_deterministic_close_id_stable(self):
        from nbot.exchange.contracts import ExchangePosition
        p = ExchangePosition("BTCUSDT", "LONG", 1, 100)
        a = BinanceTestnetExchange.deterministic_close_client_id(p, "RISK")
        b = BinanceTestnetExchange.deterministic_close_client_id(p, "RISK")
        self.assertEqual(a, b); self.assertLessEqual(len(a), 36)

    def test_recover_exchange_side_close_from_user_trades(self):
        with tempfile.TemporaryDirectory() as td:
            ex, local = self._open_with_stop(Path(td))
            ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
            # close_position already pruned stops; recovery must still settle exact history.
            close = ex.recover_closed_position(local)
            self.assertAlmostEqual(close.realized_pnl_usd, -2.0)

    def test_recover_uses_order_and_income_when_user_trades_missing(self):
        with tempfile.TemporaryDirectory() as td:
            ex, local = self._open_with_stop(Path(td))
            ex.close_position("BTCUSDT", "LONG", reason="MANUAL")
            ex.user_trades = []
            close = ex.recover_closed_position(local)
            self.assertEqual(close.source, "ORDER_HISTORY_INCOME_RECOVERY")
            self.assertAlmostEqual(close.realized_pnl_usd, -2.0)

    def test_recover_finished_algo_stop_when_user_trades_missing(self):
        with tempfile.TemporaryDirectory() as td:
            ex, local = self._open_with_stop(Path(td))
            stop = ex.protective_stop_snapshot("BTCUSDT")
            ex.next_order += 1; oid = str(ex.next_order)
            px = 90.0; qty = 1.0; pnl = (px - local.entry_price) * qty
            ex.orders[oid] = {"symbol":"BTCUSDT","orderId":oid,"clientOrderId":"algo-child","status":"FILLED","executedQty":"1","avgPrice":str(px),"cumQuote":str(px),"side":"SELL","positionSide":"BOTH","time":1_800_000_000_100,"updateTime":1_800_000_000_100}
            algo = ex.algos[stop.stop_id]
            algo.update({"algoStatus":"FINISHED","actualOrderId":oid,"actualQty":"1","actualPrice":str(px)})
            ex.positions = []
            ex.incomes = [{"symbol":"BTCUSDT","incomeType":"REALIZED_PNL","income":str(pnl),"time":1_800_000_000_100}]
            ex.user_trades = []
            close = ex.recover_closed_position(local)
            self.assertEqual(close.source, "ALGO_ACTUAL_ORDER_INCOME_RECOVERY")
            self.assertEqual(close.reason, "PROTECTIVE_STOP_TRIGGERED")

    def test_missing_close_evidence_never_invents_zero_pnl(self):
        with tempfile.TemporaryDirectory() as td:
            ex, local = self._open_with_stop(Path(td))
            ex.positions = []; ex.orders = {local.entry_order_id: ex.orders[local.entry_order_id]}; ex.user_trades=[]; ex.incomes=[]; ex.algos={}
            with self.assertRaisesRegex(TestnetExchangeError, "SETTLEMENT_FAILED"):
                ex.recover_closed_position(local)

    def test_inflight_filled_then_closed_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config)
            fill = ex.open_market(plan(), client_order_id="ENTRY")
            inflight = EntryInflight("p","AUTH","INTEGER_R_STEP_CONTROL",plan(),"ENTRY",1_800_000_000_000,fill)
            ex.close_position("BTCUSDT", "LONG", reason="EMERGENCY")
            close = ex.recover_closed_inflight_entry(inflight)
            self.assertIsNotNone(close.realized_pnl_usd)


class V319BoundaryTests(unittest.TestCase):
    def test_runtime_protocols_are_satisfied(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            self.assertIsInstance(ex, ExchangePort)
            self.assertIsInstance(ex, ReconciliationExchangePort)

    def test_preflight_is_testnet_operational_only(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td)); arm(ex.config); ex.connect()
            report = ex.preflight_report()
            self.assertFalse(report["real_money"])
            self.assertFalse(report["research_evidence"])
            self.assertEqual(report["evidence_lineage"], "TESTNET_OPERATIONAL_ONLY")
            self.assertEqual(report["rest_host"], "demo-fapi.binance.com")
            ex.disconnect()

    def test_module_contains_no_observation_research_learning_strategy_import(self):
        source = (Path(__file__).resolve().parents[1] / "nbot/exchange/binance_testnet.py").read_text()
        for forbidden in ("nbot.observation", "nbot.research", "nbot.learning", "nbot.strategy"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

class V319TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = TestnetExchangeConfig(api_key="key123", api_secret="secret456", repo_root=self.root)
        self.ex = BinanceTestnetExchange(self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_signed_request_carries_api_key_timestamp_recvwindow_and_valid_signature(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{}'

        captured = {}
        def fake_urlopen(req, timeout):
            captured["req"] = req
            captured["timeout"] = timeout
            return Response()

        with mock.patch("nbot.exchange.binance_testnet.time.time", return_value=1234.567), \
             mock.patch("nbot.exchange.binance_testnet.urlopen", side_effect=fake_urlopen):
            self.ex._signed_get("/fapi/v2/account", {"foo": "bar"})

        req = captured["req"]
        self.assertEqual(req.get_header("X-mbx-apikey"), "key123")
        self.assertEqual(captured["timeout"], self.config.request_timeout_seconds)
        from urllib.parse import parse_qs, urlsplit
        params = parse_qs(urlsplit(req.full_url).query)
        self.assertEqual(params["foo"], ["bar"])
        self.assertEqual(params["timestamp"], ["1234567"])
        self.assertEqual(params["recvWindow"], ["5000"])
        supplied = params.pop("signature")[0]
        unsigned = {k: v[0] for k, v in params.items()}
        self.assertEqual(supplied, self.ex._signature(unsigned))

    def test_http_503_unknown_write_is_ambiguous_not_failed(self):
        import io
        from urllib.error import HTTPError
        err = HTTPError(
            url="https://demo-fapi.binance.com/fapi/v1/order",
            code=503,
            msg="Service Unavailable",
            hdrs=None,
            fp=io.BytesIO(b'{"code":-1008,"msg":"Unknown error, please check your request or try again later."}'),
        )
        with mock.patch("nbot.exchange.binance_testnet.urlopen", side_effect=err):
            with self.assertRaises(AmbiguousExecutionError):
                self.ex._signed_post("/fapi/v1/order", {"symbol": "BTCUSDT"}, ambiguous=True)

    def test_network_timeout_on_write_is_ambiguous(self):
        with mock.patch("nbot.exchange.binance_testnet.urlopen", side_effect=TimeoutError("timeout")):
            with self.assertRaises(AmbiguousExecutionError):
                self.ex._signed_post("/fapi/v1/order", {"symbol": "BTCUSDT"}, ambiguous=True)

    def test_network_timeout_on_read_is_normal_exchange_error(self):
        with mock.patch("nbot.exchange.binance_testnet.urlopen", side_effect=TimeoutError("timeout")):
            with self.assertRaises(TestnetExchangeError) as ctx:
                self.ex._signed_get("/fapi/v2/account")
        self.assertIn("REST_NETWORK", str(ctx.exception))

class V319RealLifecycleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.cfg = TestnetExchangeConfig(
            api_key="key",
            api_secret="secret",
            repo_root=self.root,
            max_session_entries=5,
            max_entry_notional_usd=2_000.0,
            entry_resolution_timeout_seconds=0.01,
            stop_resolution_timeout_seconds=0.01,
            close_settlement_retries=1,
            close_settlement_retry_seconds=0.0,
        )
        arm(self.cfg)

    def tearDown(self):
        self.td.cleanup()

    def _execute(self, side: str):
        ex = Harness(self.cfg)
        ex.bid = 99.9
        ex.ask = 100.1
        ex.connect()
        self.addCleanup(ex.disconnect)
        state = ExecutionStateStore(
            self.root / "data/execution/testnet/execution_state.json",
            profile="testnet-trade",
            market_environment="TESTNET",
        )
        state.set_entries_enabled(True)
        lifecycle = EntryLifecycle(
            exchange=ex,
            state=state,
            risk=RiskManager(),
            emergency=EmergencyFlattener(exchange=ex, sleep=lambda _: None),
            config=EntryLifecycleConfig(
                profile="testnet-trade",
                market_environment="TESTNET",
                allowed_entry_authorities=frozenset({"TESTNET_MECHANICAL_ONLY"}),
                allowed_exit_policies=frozenset({"INTEGER_R_STEP_CONTROL"}),
            ),
        )
        proposal = EntryProposal(
            proposal_id=f"proposal-testnet-integration-{side.lower()}",
            generated_at_ms=1_799_999_999_900,
            expires_at_ms=1_800_000_001_000,
            profile="testnet-trade",
            market_environment="TESTNET",
            symbol="BTCUSDT",
            side=side,
            reference_price=100.0,
            entry_authority="TESTNET_MECHANICAL_ONLY",
            exit_policy_version="INTEGER_R_STEP_CONTROL",
        )
        opened = lifecycle.execute(proposal, now_ms=1_800_000_000_000)
        return ex, state, opened

    def test_real_entry_lifecycle_long_against_testnet_adapter(self):
        ex, state, opened = self._execute("LONG")
        self.assertEqual(state.open_position, opened)
        self.assertIsNone(state.entry_inflight)
        self.assertEqual(ex.position_snapshot().side, "LONG")
        stop = ex.protective_stop_snapshot("BTCUSDT")
        self.assertIsNotNone(stop)
        self.assertEqual(stop.side, "LONG")

    def test_real_entry_lifecycle_short_against_testnet_adapter(self):
        ex, state, opened = self._execute("SHORT")
        self.assertEqual(state.open_position, opened)
        self.assertIsNone(state.entry_inflight)
        self.assertEqual(ex.position_snapshot().side, "SHORT")
        stop = ex.protective_stop_snapshot("BTCUSDT")
        self.assertIsNotNone(stop)
        self.assertEqual(stop.side, "SHORT")
