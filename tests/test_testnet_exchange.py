import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_execution
from nbot.execution import EntryPlan, ExchangePosition, Quote
from nbot.testnet_exchange import (
    ARM_FILE_CONTENT,
    REQUIRED_CONFIRMATION,
    AmbiguousExecutionError,
    BinanceTestnetExchange,
    TestnetExchangeConfig,
    TestnetExchangeError,
    TestnetTradingGuard,
)


class AdapterHarness(BinanceTestnetExchange):
    def __init__(self, config):
        super().__init__(config)
        self._filters = {
            "BTCUSDT": {
                "market_step": 0.001,
                "market_min": 0.001,
                "market_max": 1000.0,
                "lot_step": 0.001,
                "tick": 0.1,
            }
        }
        self.calls = []
        self.position = None
        self.orders = {}
        self.stops = []
        self.algo_history = {}
        self.trades = []
        self.income = []
        self.next_algo_id = 100
        self.next_order_id = 7
        self.fail_cancel_ids = set()

    def quote(self, symbol):
        return Quote(symbol, 99.9, 100.1, 1_000_000)

    def position_snapshot(self):
        return self.position

    def _signed_post(self, path, params, *, ambiguous=False):
        self.calls.append(("POST", path, dict(params), ambiguous))
        if path == "/fapi/v1/order":
            cid = params["newClientOrderId"]
            order_id = self.next_order_id
            self.next_order_id += 1
            order = {
                "orderId": order_id,
                "clientOrderId": cid,
                "symbol": params["symbol"],
                "status": "FILLED",
                "side": params["side"],
                "positionSide": "BOTH",
                "type": "MARKET",
                "origType": "MARKET",
                "origQty": str(params["quantity"]),
                "executedQty": str(params["quantity"]),
                "avgPrice": "100",
                "reduceOnly": params.get("reduceOnly") == "true",
                "time": 1_000_001,
                "updateTime": 1_000_001,
            }
            self.orders[cid] = order
            side = "LONG" if params["side"] == "BUY" else "SHORT"
            if params.get("reduceOnly") == "true":
                self.position = None
            else:
                self.position = ExchangePosition(params["symbol"], side, float(params["quantity"]), 100.0)
            return order
        if path == "/fapi/v1/algoOrder":
            algo_id = self.next_algo_id
            self.next_algo_id += 1
            row = {
                "algoId": algo_id,
                "clientAlgoId": params.get("clientAlgoId"),
                "algoType": "CONDITIONAL",
                "orderType": "STOP_MARKET",
                "reduceOnly": True,
                "triggerPrice": str(params["triggerPrice"]),
                "algoStatus": "NEW",
                "actualOrderId": "",
                "symbol": params["symbol"],
                "side": params["side"],
                "createTime": 1_000_010,
            }
            self.stops.append(row)
            self.algo_history[str(algo_id)] = row
            return {"algoId": algo_id, "clientAlgoId": params.get("clientAlgoId")}
        if path == "/fapi/v1/leverage":
            return {"leverage": params["leverage"]}
        raise AssertionError(path)

    def _signed_get(self, path, params=None):
        self.calls.append(("GET", path, dict(params or {}), False))
        if path == "/fapi/v1/openAlgoOrders":
            return list(self.stops)
        if path == "/fapi/v1/order":
            params = params or {}
            if params.get("origClientOrderId") is not None:
                return self.orders.get(params.get("origClientOrderId")) or self._missing_order()
            if params.get("orderId") is not None:
                for order in self.orders.values():
                    if int(order.get("orderId", -1)) == int(params["orderId"]):
                        return order
                return self._missing_order()
        if path == "/fapi/v1/userTrades":
            params = params or {}
            rows = list(self.trades)
            if params.get("orderId") is not None:
                rows = [row for row in rows if int(row.get("orderId", -1)) == int(params["orderId"])]
            if params.get("startTime") is not None:
                rows = [row for row in rows if int(row.get("time", 0)) >= int(params["startTime"])]
            if params.get("endTime") is not None:
                rows = [row for row in rows if int(row.get("time", 0)) <= int(params["endTime"])]
            return rows
        if path == "/fapi/v1/allOrders":
            params = params or {}
            rows = [dict(row) for row in self.orders.values()]
            if params.get("symbol") is not None:
                rows = [row for row in rows if row.get("symbol", "BTCUSDT") == params["symbol"]]
            if params.get("startTime") is not None:
                rows = [
                    row for row in rows
                    if int(row.get("updateTime") or row.get("time") or 0) >= int(params["startTime"])
                ]
            if params.get("endTime") is not None:
                rows = [
                    row for row in rows
                    if int(row.get("updateTime") or row.get("time") or 0) <= int(params["endTime"])
                ]
            return rows
        if path == "/fapi/v1/algoOrder":
            params = params or {}
            if params.get("algoId") is not None:
                row = self.algo_history.get(str(params["algoId"]))
            else:
                row = next((r for r in self.algo_history.values() if r.get("clientAlgoId") == params.get("clientAlgoId")), None)
            if row is None:
                raise TestnetExchangeError("REST_FAILED:GET:/fapi/v1/algoOrder:400:code=-2013 msg=Order does not exist")
            return dict(row)
        if path == "/fapi/v1/allAlgoOrders":
            params = params or {}
            rows = [dict(row) for row in self.algo_history.values()]
            if params.get("startTime") is not None:
                rows = [row for row in rows if int(row.get("createTime", 0) or 0) >= int(params["startTime"])]
            if params.get("endTime") is not None:
                rows = [row for row in rows if int(row.get("createTime", 0) or 0) <= int(params["endTime"])]
            return rows
        if path == "/fapi/v1/income":
            params = params or {}
            rows = [dict(row) for row in self.income]
            if params.get("symbol") is not None:
                rows = [row for row in rows if row.get("symbol") == params["symbol"]]
            if params.get("incomeType") is not None:
                rows = [row for row in rows if row.get("incomeType") == params["incomeType"]]
            if params.get("startTime") is not None:
                rows = [row for row in rows if int(row.get("time", 0) or 0) >= int(params["startTime"])]
            if params.get("endTime") is not None:
                rows = [row for row in rows if int(row.get("time", 0) or 0) <= int(params["endTime"])]
            return rows
        raise AssertionError(path)

    @staticmethod
    def _missing_order():
        raise TestnetExchangeError("REST_FAILED:GET:/fapi/v1/order:400:code=-2013 msg=Order does not exist")

    def _signed_delete(self, path, params):
        self.calls.append(("DELETE", path, dict(params), False))
        if path != "/fapi/v1/algoOrder":
            raise AssertionError(path)
        target = int(params["algoId"])
        if target in self.fail_cancel_ids:
            raise TestnetExchangeError("REST_TIMEOUT:DELETE:/fapi/v1/algoOrder")
        self.stops = [row for row in self.stops if int(row["algoId"]) != target]
        if str(target) in self.algo_history:
            self.algo_history[str(target)]["algoStatus"] = "CANCELED"
        return {"algoId": target}


class TestnetExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arm = Path(self.tmp.name) / "armed"
        self.cfg = TestnetExchangeConfig(
            api_key="key",
            api_secret="secret",
            arm_file=self.arm,
            guard_state_path=Path(self.tmp.name) / "guard.json",
            confirmation=REQUIRED_CONFIRMATION,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def arm_trading(self):
        self.arm.write_text(ARM_FILE_CONTENT + "\n")

    def initialize_disarmed_guard(self, cfg=None):
        guard = TestnetTradingGuard(cfg or self.cfg)
        report = guard.preflight()
        self.assertFalse(report["armed"])
        self.assertEqual(report["reason"], "ARM_FILE_MISSING")
        return guard

    def plan(self):
        return EntryPlan("BTCUSDT", "LONG", 10.0, 100.0, 99.0, 10.0, 1000.0, 5)

    def test_config_is_hard_pinned_to_futures_testnet_hosts(self):
        self.cfg.validate()
        with self.assertRaisesRegex(ValueError, "TESTNET_REST_HOST_INVALID"):
            TestnetExchangeConfig("k", "s", base_url="https://fapi.binance.com").validate()
        with self.assertRaisesRegex(ValueError, "TESTNET_WS_HOST_INVALID"):
            TestnetExchangeConfig("k", "s", ws_base_url="wss://fstream.binance.com/ws").validate()

    def test_explicit_arm_gate_is_required_only_for_entries(self):
        guard = self.initialize_disarmed_guard()
        with self.assertRaisesRegex(TestnetExchangeError, "TESTNET_TRADING_NOT_ARMED"):
            guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.arm_trading()
        guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.assertEqual(guard.preflight()["session_entries"], 1)

    def test_session_entry_count_survives_process_restart_and_enforces_limit(self):
        cfg = TestnetExchangeConfig(
            api_key="key", api_secret="secret", arm_file=self.arm,
            guard_state_path=Path(self.tmp.name) / "guard-limit.json",
            confirmation=REQUIRED_CONFIRMATION, max_session_entries=1,
        )
        self.initialize_disarmed_guard(cfg)
        self.arm_trading()
        first_process = TestnetTradingGuard(cfg)
        first_process.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.assertEqual(first_process.preflight()["session_entries"], 1)

        restarted_process = TestnetTradingGuard(cfg)
        self.assertEqual(restarted_process.preflight()["session_entries"], 1)
        with self.assertRaisesRegex(TestnetExchangeError, "TESTNET_SESSION_ENTRY_LIMIT_REACHED"):
            restarted_process.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)

    def test_explicit_rearm_starts_new_persistent_session(self):
        cfg = TestnetExchangeConfig(
            api_key="key", api_secret="secret", arm_file=self.arm,
            guard_state_path=Path(self.tmp.name) / "guard-rearm.json",
            confirmation=REQUIRED_CONFIRMATION, max_session_entries=1,
        )
        guard = self.initialize_disarmed_guard(cfg)
        self.arm_trading()
        guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.assertEqual(guard.preflight()["session_entries"], 1)

        self.arm.unlink()
        self.assertFalse(TestnetTradingGuard(cfg).preflight()["armed"])
        self.arm_trading()
        fresh_session = TestnetTradingGuard(cfg)
        report = fresh_session.preflight()
        self.assertTrue(report["armed"])
        self.assertEqual(report["session_entries"], 0)
        fresh_session.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.assertEqual(fresh_session.preflight()["session_entries"], 1)

    def test_missing_guard_state_while_already_armed_fails_closed(self):
        self.arm_trading()
        report = TestnetTradingGuard(self.cfg).preflight()
        self.assertFalse(report["armed"])
        self.assertEqual(report["reason"], "GUARD_STATE_MISSING_WHILE_ARMED")
        with self.assertRaisesRegex(TestnetExchangeError, "GUARD_STATE_MISSING_WHILE_ARMED"):
            TestnetTradingGuard(self.cfg).authorize_entry(
                symbol="BTCUSDT", quantity=1, price=100, position=None
            )

    def test_leverage_write_is_blocked_until_testnet_gate_is_armed(self):
        self.initialize_disarmed_guard()
        ex = AdapterHarness(self.cfg)
        with self.assertRaisesRegex(TestnetExchangeError, "TESTNET_TRADING_NOT_ARMED"):
            ex.set_leverage("BTCUSDT", 5)
        self.arm_trading()
        ex.set_leverage("BTCUSDT", 5)
        self.assertTrue(any(c[0] == "POST" and c[1] == "/fapi/v1/leverage" for c in ex.calls))

    def test_market_entry_uses_client_id_and_single_order_submission(self):
        self.initialize_disarmed_guard()
        self.arm_trading()
        ex = AdapterHarness(self.cfg)
        fill = ex.open_market(self.plan(), client_order_id="NBV28-ONE")
        posts = [c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/order"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][2]["newClientOrderId"], "NBV28-ONE")
        self.assertEqual(fill.client_order_id, "NBV28-ONE")

    def test_connect_does_not_require_balance_before_reconciliation(self):
        ex = BinanceTestnetExchange(self.cfg)
        ex._user_stream_ready.set()
        ex._user_stream_healthy = True
        with mock.patch.object(ex, "_public_get", return_value={}) as public_get, \
             mock.patch.object(ex, "_signed_get", return_value=[{"asset": "USDT", "availableBalance": "123.45"}]) as signed_get, \
             mock.patch.object(ex, "_load_filters"), \
             mock.patch.object(ex, "_start_user_stream"):
            ex.connect()
            public_get.assert_called_once_with("/fapi/v1/ping")
            signed_get.assert_not_called()
            self.assertTrue(ex.is_healthy())
            balance = ex.account_snapshot()
            self.assertEqual(balance.available_balance_usd, 123.45)
            signed_get.assert_called_once_with("/fapi/v3/balance")

    def test_protective_stop_snapshot_requires_one_canonical_active_stop(self):
        ex = AdapterHarness(self.cfg)
        ex.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        self.assertIsNone(ex.protective_stop_snapshot("BTCUSDT"))
        first = ex._place_stop("BTCUSDT", "LONG", 10.0, 99.0)
        active = ex.protective_stop_snapshot("BTCUSDT")
        self.assertEqual(active.algo_id, first.algo_id)
        ex._place_stop("BTCUSDT", "LONG", 10.0, 98.0)
        with self.assertRaisesRegex(TestnetExchangeError, "MULTIPLE_PROTECTIVE_STOPS_DETECTED"):
            ex.protective_stop_snapshot("BTCUSDT")

    def test_ambiguous_entry_queries_same_client_id_and_never_blind_resubmits(self):
        self.initialize_disarmed_guard()
        self.arm_trading()
        ex = AdapterHarness(self.cfg)
        original_post = ex._signed_post
        attempted = {"n": 0}

        def ambiguous_once(path, params, *, ambiguous=False):
            if path == "/fapi/v1/order" and params.get("reduceOnly") != "true":
                attempted["n"] += 1
                cid = params["newClientOrderId"]
                ex.orders[cid] = {
                    "orderId": 8, "clientOrderId": cid, "status": "FILLED",
                    "executedQty": str(params["quantity"]), "avgPrice": "100", "updateTime": 1_000_001,
                }
                ex.position = ExchangePosition("BTCUSDT", "LONG", float(params["quantity"]), 100.0)
                raise AmbiguousExecutionError("timeout")
            return original_post(path, params, ambiguous=ambiguous)

        ex._signed_post = ambiguous_once
        fill = ex.open_market(self.plan(), client_order_id="NBV28-AMB")
        self.assertEqual(fill.client_order_id, "NBV28-AMB")
        self.assertEqual(attempted["n"], 1)

    def test_stop_market_uses_current_algo_service_and_is_verified(self):
        ex = AdapterHarness(self.cfg)
        ex.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        ex.ensure_protective_stop("BTCUSDT", "LONG", 10.0, 99.0)
        posts = [c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/algoOrder"]
        self.assertEqual(len(posts), 1)
        payload = posts[0][2]
        self.assertEqual(payload["algoType"], "CONDITIONAL")
        self.assertEqual(payload["type"], "STOP_MARKET")
        self.assertEqual(payload["reduceOnly"], "true")

    def test_restart_recovers_exact_inflight_filled_entry_without_new_post(self):
        ex = AdapterHarness(self.cfg)
        cid = "NBV28-RECOVER-ENTRY"
        ex.orders[cid] = {
            "orderId": 8001, "clientOrderId": cid, "symbol": "BTCUSDT",
            "status": "FILLED", "side": "BUY", "positionSide": "BOTH",
            "type": "MARKET", "origType": "MARKET", "origQty": "10",
            "executedQty": "10", "avgPrice": "100", "reduceOnly": False,
            "time": 1_000_001, "updateTime": 1_000_001,
        }
        ex.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        fill = ex.recover_inflight_entry(self.plan(), client_order_id=cid)
        self.assertIsNotNone(fill)
        self.assertEqual(fill.order_id, "8001")
        self.assertEqual(fill.client_order_id, cid)
        self.assertFalse(any(c[0] == "POST" and c[1] == "/fapi/v1/order" for c in ex.calls))

    def test_restart_clears_inflight_when_exact_order_is_repeatedly_missing_and_exchange_flat(self):
        ex = AdapterHarness(self.cfg)
        with mock.patch("nbot.testnet_exchange.time.monotonic", side_effect=[0.0, 0.0, 11.0]), \
             mock.patch("nbot.testnet_exchange.time.sleep", return_value=None):
            fill = ex.recover_inflight_entry(self.plan(), client_order_id="NBV28-NEVER-SUBMITTED")
        self.assertIsNone(fill)
        self.assertFalse(any(c[0] == "POST" and c[1] == "/fapi/v1/order" for c in ex.calls))

    def test_stop_replacement_verifies_new_before_canceling_old(self):
        ex = AdapterHarness(self.cfg)
        ex.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        ex.ensure_protective_stop("BTCUSDT", "LONG", 10.0, 99.0)
        ex.calls.clear()
        ex.replace_protective_stop("BTCUSDT", "LONG", 10.0, 99.5)
        sequence = [(c[0], c[1]) for c in ex.calls]
        self.assertIn(("POST", "/fapi/v1/algoOrder"), sequence)
        self.assertIn(("DELETE", "/fapi/v1/algoOrder"), sequence)
        self.assertLess(sequence.index(("POST", "/fapi/v1/algoOrder")), sequence.index(("DELETE", "/fapi/v1/algoOrder")))
        self.assertEqual(len(ex.stops), 1)
        self.assertAlmostEqual(float(ex.stops[0]["triggerPrice"]), 99.5)

    def test_external_close_recovery_uses_user_trades_and_proves_known_stop(self):
        ex = AdapterHarness(self.cfg)
        stop = ex._place_stop("BTCUSDT", "LONG", 1.0, 99.0)
        self.assertIsNotNone(stop.algo_id)
        close_order_id = 9001
        ex.algo_history[str(stop.algo_id)]["algoStatus"] = "FINISHED"
        ex.algo_history[str(stop.algo_id)]["actualOrderId"] = str(close_order_id)
        ex.stops = []
        ex.trades = [
            {"id": 1, "orderId": 7001, "price": "100", "qty": "1", "realizedPnl": "0", "side": "BUY", "positionSide": "BOTH", "time": 1_000_001},
            {"id": 2, "orderId": close_order_id, "price": "99.1", "qty": "0.4", "realizedPnl": "-0.36", "side": "SELL", "positionSide": "BOTH", "time": 1_000_500},
            {"id": 3, "orderId": close_order_id, "price": "99.0", "qty": "0.6", "realizedPnl": "-0.60", "side": "SELL", "positionSide": "BOTH", "time": 1_000_600},
        ]
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0,
            "entry_timestamp_ms": 1_000_000, "entry_order_id": "7001",
            "protective_stop_algo_id": stop.algo_id,
            "protective_stop_client_algo_id": stop.client_algo_id,
        }
        close = ex.recover_closed_position(local)
        self.assertAlmostEqual(close.price, 99.04)
        self.assertAlmostEqual(close.realized_pnl_usd, -0.96)
        self.assertEqual(close.reason, "PROTECTIVE_STOP_TRIGGERED")
        self.assertEqual(close.order_ids, (str(close_order_id),))
        self.assertEqual(close.source, "USER_TRADES_RECOVERY")

    def test_external_close_recovery_accepts_zero_realized_break_even_fill(self):
        ex = AdapterHarness(self.cfg)
        ex.trades = [
            {"id": 1, "orderId": 7001, "price": "100", "qty": "1", "realizedPnl": "0", "side": "BUY", "positionSide": "BOTH", "time": 1_000_001},
            {"id": 2, "orderId": 9001, "price": "100", "qty": "1", "realizedPnl": "0", "side": "SELL", "positionSide": "BOTH", "time": 1_000_500},
        ]
        local = {"symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0, "entry_timestamp_ms": 1_000_000, "entry_order_id": "7001"}
        close = ex.recover_closed_position(local)
        self.assertEqual(close.realized_pnl_usd, 0.0)
        self.assertEqual(close.reason, "EXCHANGE_FLAT_RECOVERED_AFTER_RESTART")

    def test_external_close_recovery_rejects_position_mutation_while_offline(self):
        ex = AdapterHarness(self.cfg)
        ex.trades = [
            {"id": 1, "orderId": 7001, "price": "100", "qty": "1", "realizedPnl": "0", "side": "BUY", "positionSide": "BOTH", "time": 1_000_001},
            {"id": 2, "orderId": 7002, "price": "101", "qty": "0.5", "realizedPnl": "0", "side": "BUY", "positionSide": "BOTH", "time": 1_000_200},
            {"id": 3, "orderId": 9001, "price": "99", "qty": "1.5", "realizedPnl": "-2", "side": "SELL", "positionSide": "BOTH", "time": 1_000_500},
        ]
        local = {"symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0, "entry_timestamp_ms": 1_000_000, "entry_order_id": "7001"}
        with self.assertRaisesRegex(TestnetExchangeError, "POSITION_MUTATED_WHILE_EXECUTION_OFFLINE"):
            ex.recover_closed_position(local)

    def test_stop_methods_return_persistable_identity(self):
        ex = AdapterHarness(self.cfg)
        ex.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        ref = ex.ensure_protective_stop("BTCUSDT", "LONG", 10.0, 99.0)
        self.assertEqual(ref.trigger_price, 99.0)
        self.assertIsNotNone(ref.algo_id)
        self.assertTrue(ref.client_algo_id.startswith("NBV28SL-"))

    def test_ambiguous_stop_placement_recovers_same_client_algo_id_without_resubmit(self):
        ex = AdapterHarness(self.cfg)
        ex.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        original_post = ex._signed_post
        attempts = {"n": 0}

        def ambiguous_stop(path, params, *, ambiguous=False):
            if path == "/fapi/v1/algoOrder":
                attempts["n"] += 1
                result = original_post(path, params, ambiguous=ambiguous)
                raise AmbiguousExecutionError("timeout after exchange accepted stop")
            return original_post(path, params, ambiguous=ambiguous)

        ex._signed_post = ambiguous_stop
        ref = ex.ensure_protective_stop("BTCUSDT", "LONG", 10.0, 99.0)
        self.assertEqual(attempts["n"], 1)
        self.assertEqual(len(ex.stops), 1)
        self.assertIsNotNone(ref.algo_id)

    def test_ensure_stop_prunes_obsolete_stop_only_after_new_is_verified(self):
        ex = AdapterHarness(self.cfg)
        ex.position = ExchangePosition("BTCUSDT", "LONG", 10.0, 100.0)
        old = ex._place_stop("BTCUSDT", "LONG", 10.0, 98.0)
        ex.calls.clear()
        new = ex.ensure_protective_stop("BTCUSDT", "LONG", 10.0, 99.0)
        sequence = [(c[0], c[1]) for c in ex.calls]
        self.assertIn(("POST", "/fapi/v1/algoOrder"), sequence)
        self.assertIn(("DELETE", "/fapi/v1/algoOrder"), sequence)
        self.assertLess(sequence.index(("POST", "/fapi/v1/algoOrder")), sequence.index(("DELETE", "/fapi/v1/algoOrder")))
        self.assertNotEqual(old.algo_id, new.algo_id)
        self.assertEqual([str(row["algoId"]) for row in ex.stops], [str(new.algo_id)])

    def test_external_close_recovery_can_prove_replaced_stop_from_algo_history(self):
        ex = AdapterHarness(self.cfg)
        stop = ex._place_stop("BTCUSDT", "LONG", 1.0, 99.0)
        close_order_id = 9010
        history = ex.algo_history[str(stop.algo_id)]
        history["algoStatus"] = "FINISHED"
        history["actualOrderId"] = str(close_order_id)
        history["createTime"] = 1_000_100
        ex.stops = []
        ex.trades = [
            {"id": 1, "orderId": 7001, "price": "100", "qty": "1", "realizedPnl": "0", "side": "BUY", "positionSide": "BOTH", "time": 1_000_001},
            {"id": 2, "orderId": close_order_id, "price": "99", "qty": "1", "realizedPnl": "-1", "side": "SELL", "positionSide": "BOTH", "time": 1_000_500},
        ]
        # Simulate an operator/exchange stop replacement: local identity is
        # unavailable/stale, but Binance history can still prove which STOP_MARKET
        # created the exact closing child order.
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0,
            "entry_timestamp_ms": 1_000_000, "entry_order_id": "7001",
        }
        close = ex.recover_closed_position(local)
        self.assertEqual(close.reason, "PROTECTIVE_STOP_TRIGGERED")

    def test_external_close_recovery_falls_back_to_finished_algo_actual_order_and_income(self):
        ex = AdapterHarness(self.cfg)
        actual_order_id = 9011
        algo_id = 555
        ex.algo_history[str(algo_id)] = {
            "algoId": algo_id,
            "clientAlgoId": "aos-test-stop",
            "algoStatus": "FINISHED",
            "orderType": "STOP_MARKET",
            "side": "SELL",
            "positionSide": "BOTH",
            "quantity": "1.000",
            "actualQty": "1.000",
            "actualPrice": "101.50",
            "actualOrderId": str(actual_order_id),
            "reduceOnly": True,
            "createTime": 1_000_100,
            "updateTime": 1_000_700,
        }
        ex.orders["aos-test-stop"] = {
            "orderId": actual_order_id,
            "clientOrderId": "aos-test-stop",
            "status": "FILLED",
            "side": "SELL",
            "positionSide": "BOTH",
            "type": "MARKET",
            "origType": "MARKET",
            "origQty": "1.000",
            "executedQty": "1.000",
            "avgPrice": "101.50",
            "cumQuote": "101.50",
            "reduceOnly": True,
            "time": 1_000_690,
            "updateTime": 1_000_700,
        }
        ex.income = [
            {"symbol": "BTCUSDT", "incomeType": "REALIZED_PNL", "income": "0.50000000", "time": 1_000_000},
            {"symbol": "BTCUSDT", "incomeType": "REALIZED_PNL", "income": "1.00000000", "time": 1_000_000},
        ]
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0,
            "entry_price": 100.0, "entry_timestamp_ms": 1_000_000,
            "entry_order_id": "7001",
        }
        with mock.patch("nbot.testnet_exchange.time.time", return_value=1100.0):
            close = ex.recover_closed_position(local)
        self.assertEqual(close.reason, "PROTECTIVE_STOP_TRIGGERED")
        self.assertEqual(close.source, "ALGO_ACTUAL_ORDER_INCOME_RECOVERY")
        self.assertEqual(close.order_ids, (str(actual_order_id),))
        self.assertAlmostEqual(close.price, 101.5)
        self.assertAlmostEqual(close.realized_pnl_usd, 1.5)
        self.assertEqual(close.timestamp_ms, 1_000_700)

    def test_algo_settlement_matches_observed_testnet_split_realized_pnl_case(self):
        ex = AdapterHarness(self.cfg)
        ex.algo_history["1000000170503496"] = {
            "algoId": 1000000170503496,
            "clientAlgoId": "aos_cbRouQdEszR7On3g4XCu",
            "algoStatus": "FINISHED",
            "orderType": "STOP_MARKET",
            "side": "SELL",
            "positionSide": "BOTH",
            "quantity": "0.0157",
            "actualQty": "0.0157",
            "actualPrice": "63604.500000",
            "triggerPrice": "63605.00",
            "actualOrderId": "28544406888",
            "reduceOnly": True,
            "createTime": 1786973889265,
            "updateTime": 1786973905768,
        }
        ex.orders["aos_cbRouQdEszR7On3g4XCu"] = {
            "orderId": 28544406888,
            "clientOrderId": "aos_cbRouQdEszR7On3g4XCu",
            "status": "FILLED",
            "side": "SELL",
            "positionSide": "BOTH",
            "type": "MARKET",
            "origType": "MARKET",
            "origQty": "0.0157",
            "executedQty": "0.0157",
            "avgPrice": "63604.500000",
            "cumQuote": "998.590650",
            "reduceOnly": True,
            "time": 1786973905739,
            "updateTime": 1786973905747,
        }
        ex.income = [
            {"symbol": "BTCUSDT", "incomeType": "REALIZED_PNL", "income": "0.14360000", "time": 1786973905000},
            {"symbol": "BTCUSDT", "incomeType": "REALIZED_PNL", "income": "2.11092000", "time": 1786973905000},
        ]
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 0.0157,
            "entry_price": 63460.9, "entry_timestamp_ms": 1786972931985,
            "entry_order_id": "28544391514",
            "protective_stop_algo_id": "1000000170487957",
            "protective_stop_client_algo_id": "NBV28SL-3883fb3ef3ea45b480ea",
        }
        with mock.patch("nbot.testnet_exchange.time.time", return_value=1786974000.0):
            close = ex.recover_closed_position(local)
        self.assertAlmostEqual(close.price, 63604.5)
        self.assertAlmostEqual(close.realized_pnl_usd, 2.25452)
        self.assertEqual(close.reason, "PROTECTIVE_STOP_TRIGGERED")
        self.assertEqual(close.order_ids, ("28544406888",))
        self.assertEqual(close.source, "ALGO_ACTUAL_ORDER_INCOME_RECOVERY")

    def test_algo_settlement_trusts_exchange_realized_pnl_and_audits_local_variance(self):
        # Regression for the physical V2.8.3 failure: Binance accounting is
        # authoritative after identity/quantity/price are independently proven.
        # A local arithmetic difference is audit evidence, never a close veto.
        ex = AdapterHarness(self.cfg)
        actual_order_id = 9012
        ex.algo_history["556"] = {
            "algoId": 556, "clientAlgoId": "aos-mismatch", "algoStatus": "FINISHED",
            "orderType": "STOP_MARKET", "side": "SELL", "positionSide": "BOTH",
            "quantity": "0.0157", "actualQty": "0.0157", "actualPrice": "63604.50",
            "actualOrderId": str(actual_order_id), "reduceOnly": True,
            "createTime": 1_000_100, "updateTime": 1_000_700,
        }
        ex.orders["aos-mismatch"] = {
            "orderId": actual_order_id, "clientOrderId": "aos-mismatch", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "SELL", "positionSide": "BOTH",
            "executedQty": "0.0157", "avgPrice": "63604.50", "reduceOnly": True,
            "time": 1_000_690, "updateTime": 1_000_700,
        }
        ex.income = [{
            "symbol": "BTCUSDT", "incomeType": "REALIZED_PNL",
            "income": "4.80857500", "time": 1_000_000,
        }]
        # Choose the stored aggregate entry so the simple local reconstruction
        # is the exact 4.806393 value observed in the physical failure.
        local_entry = 63604.50 - (4.806393 / 0.0157)
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 0.0157,
            "entry_price": local_entry, "entry_timestamp_ms": 1_000_000,
            "entry_order_id": "7001",
        }
        close = ex._settle_local_position_from_finished_stop(local, 1_100_000)
        self.assertAlmostEqual(close.realized_pnl_usd, 4.808575)
        self.assertAlmostEqual(close.theoretical_pnl_usd, 4.806393)
        self.assertAlmostEqual(close.pnl_variance_usd, 0.002182)
        self.assertEqual(close.reason, "PROTECTIVE_STOP_TRIGGERED")

    def test_algo_settlement_rejects_ambiguous_multiple_finished_full_quantity_stops(self):
        ex = AdapterHarness(self.cfg)
        for algo_id, order_id, client in ((557, 9013, "aos-one"), (558, 9014, "aos-two")):
            ex.algo_history[str(algo_id)] = {
                "algoId": algo_id, "clientAlgoId": client, "algoStatus": "FINISHED",
                "orderType": "STOP_MARKET", "side": "SELL", "positionSide": "BOTH",
                "quantity": "1", "actualQty": "1", "actualPrice": "101",
                "actualOrderId": str(order_id), "reduceOnly": True,
                "createTime": 1_000_100 + algo_id, "updateTime": 1_000_700 + algo_id,
            }
            ex.orders[client] = {
                "orderId": order_id, "clientOrderId": client, "status": "FILLED",
                "side": "SELL", "positionSide": "BOTH", "executedQty": "1",
                "avgPrice": "101", "reduceOnly": True, "updateTime": 1_000_700 + algo_id,
            }
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0,
            "entry_price": 100.0, "entry_timestamp_ms": 1_000_000, "entry_order_id": "7001",
        }
        with self.assertRaisesRegex(TestnetExchangeError, "ALGO_CLOSE_EVIDENCE_AMBIGUOUS"):
            ex._settle_local_position_from_finished_stop(local, 2_000_000)

    def test_algo_settlement_rejects_unexpected_filled_order_even_when_pnl_exists(self):
        ex = AdapterHarness(self.cfg)
        ex.algo_history["559"] = {
            "algoId": 559, "clientAlgoId": "aos-close", "algoStatus": "FINISHED",
            "orderType": "STOP_MARKET", "side": "SELL", "positionSide": "BOTH",
            "quantity": "1", "actualQty": "1", "actualPrice": "101",
            "actualOrderId": "9015", "reduceOnly": True,
            "createTime": 1_000_100, "updateTime": 1_000_700,
        }
        ex.orders["aos-close"] = {
            "orderId": 9015, "clientOrderId": "aos-close", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "SELL", "positionSide": "BOTH",
            "executedQty": "1", "avgPrice": "101", "reduceOnly": True,
            "time": 1_000_690, "updateTime": 1_000_700,
        }
        # Any other fill while Execution was offline is a genuine identity /
        # position-mutation contradiction and remains fail-closed.
        ex.orders["unexpected"] = {
            "orderId": 7777, "clientOrderId": "unexpected", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "BUY", "positionSide": "BOTH",
            "executedQty": "0.1", "avgPrice": "100.5", "reduceOnly": False,
            "time": 1_000_500, "updateTime": 1_000_500,
        }
        ex.income = [{
            "symbol": "BTCUSDT", "incomeType": "REALIZED_PNL",
            "income": "1", "time": 1_000_000,
        }]
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0,
            "entry_price": 100.0, "entry_timestamp_ms": 1_000_000,
            "entry_order_id": "7001",
        }
        with self.assertRaisesRegex(TestnetExchangeError, "POSITION_MUTATED_WHILE_EXECUTION_OFFLINE"):
            ex._settle_local_position_from_finished_stop(local, 2_000_000)

    def test_external_manual_close_recovers_from_order_history_and_exchange_income(self):
        ex = AdapterHarness(self.cfg)
        ex.orders["entry"] = {
            "orderId": 7001, "clientOrderId": "entry", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "BUY", "positionSide": "BOTH",
            "executedQty": "1", "avgPrice": "100", "reduceOnly": False,
            "time": 1_000_001, "updateTime": 1_000_001,
        }
        ex.orders["manual-close"] = {
            "orderId": 9001, "clientOrderId": "manual-close", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "SELL", "positionSide": "BOTH",
            "executedQty": "1", "avgPrice": "101.25", "reduceOnly": False,
            "time": 1_000_700, "updateTime": 1_000_700,
        }
        ex.income = [{
            "symbol": "BTCUSDT", "incomeType": "REALIZED_PNL",
            "income": "1.2345", "time": 1_000_000,
        }]
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0,
            "entry_price": 100.0, "entry_timestamp_ms": 1_000_000,
            "entry_order_id": "7001",
        }
        with mock.patch("nbot.testnet_exchange.time.time", return_value=1100.0):
            close = ex.recover_closed_position(local)
        self.assertEqual(close.source, "ORDER_HISTORY_INCOME_RECOVERY")
        self.assertEqual(close.reason, "EXCHANGE_FLAT_RECOVERED_AFTER_RESTART")
        self.assertAlmostEqual(close.price, 101.25)
        self.assertAlmostEqual(close.realized_pnl_usd, 1.2345)
        self.assertEqual(close.order_ids, ("9001",))

    def test_order_history_recovery_rejects_same_side_position_mutation(self):
        ex = AdapterHarness(self.cfg)
        ex.orders["entry"] = {
            "orderId": 7001, "clientOrderId": "entry", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "BUY", "positionSide": "BOTH",
            "executedQty": "1", "avgPrice": "100", "reduceOnly": False,
            "time": 1_000_001, "updateTime": 1_000_001,
        }
        ex.orders["added-long"] = {
            "orderId": 7002, "clientOrderId": "added-long", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "BUY", "positionSide": "BOTH",
            "executedQty": "0.2", "avgPrice": "100.5", "reduceOnly": False,
            "time": 1_000_300, "updateTime": 1_000_300,
        }
        ex.orders["close"] = {
            "orderId": 9001, "clientOrderId": "close", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "SELL", "positionSide": "BOTH",
            "executedQty": "1.2", "avgPrice": "101", "reduceOnly": False,
            "time": 1_000_700, "updateTime": 1_000_700,
        }
        local = {
            "symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0,
            "entry_price": 100.0, "entry_timestamp_ms": 1_000_000,
            "entry_order_id": "7001",
        }
        with self.assertRaisesRegex(TestnetExchangeError, "POSITION_MUTATED_WHILE_EXECUTION_OFFLINE"):
            ex._settle_local_position_from_order_history(local, 2_000_000)

    def test_local_close_uses_filled_order_and_exchange_income_when_user_trades_empty(self):
        ex = AdapterHarness(self.cfg)
        position = ExchangePosition("BTCUSDT", "LONG", 1.0, 100.0)
        order = {
            "orderId": 9100, "clientOrderId": "close", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "SELL", "positionSide": "BOTH",
            "executedQty": "1", "avgPrice": "99.5", "reduceOnly": True,
            "time": 1_000_700, "updateTime": 1_000_700,
        }
        ex.income = [{
            "symbol": "BTCUSDT", "incomeType": "REALIZED_PNL",
            "income": "-0.4975", "time": 1_000_000,
        }]
        close = ex._settle_close_order(position, order, None, "OPERATOR_TESTNET_FLATTEN")
        self.assertEqual(close.source, "ORDER_INCOME_SETTLEMENT")
        self.assertAlmostEqual(close.realized_pnl_usd, -0.4975)
        self.assertAlmostEqual(close.theoretical_pnl_usd, -0.5)

    def test_local_close_without_exchange_accounting_never_invents_pnl(self):
        ex = AdapterHarness(self.cfg)
        position = ExchangePosition("BTCUSDT", "LONG", 1.0, 100.0)
        order = {
            "orderId": 9101, "clientOrderId": "close", "symbol": "BTCUSDT",
            "status": "FILLED", "side": "SELL", "positionSide": "BOTH",
            "executedQty": "1", "avgPrice": "99.5", "reduceOnly": True,
            "time": 1_000_700, "updateTime": 1_000_700,
        }
        from nbot.execution import Fill
        fallback = Fill(99.5, 1.0, "9101", "close", 1_000_700)
        with mock.patch("nbot.testnet_exchange.time.sleep", return_value=None):
            with self.assertRaisesRegex(TestnetExchangeError, "CLOSE_ACCOUNTING_UNAVAILABLE"):
                ex._settle_close_order(position, order, fallback, "OPERATOR_TESTNET_FLATTEN")

    def test_external_close_recovery_fails_if_orphan_stop_cannot_be_removed(self):
        ex = AdapterHarness(self.cfg)
        orphan = ex._place_stop("BTCUSDT", "LONG", 1.0, 99.0)
        ex.trades = [
            {"id": 1, "orderId": 7001, "price": "100", "qty": "1", "realizedPnl": "0", "side": "BUY", "positionSide": "BOTH", "time": 1_000_001},
            {"id": 2, "orderId": 9001, "price": "99", "qty": "1", "realizedPnl": "-1", "side": "SELL", "positionSide": "BOTH", "time": 1_000_500},
        ]
        ex.fail_cancel_ids.add(int(orphan.algo_id))
        local = {"symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0, "entry_timestamp_ms": 1_000_000, "entry_order_id": "7001"}
        with self.assertRaisesRegex(TestnetExchangeError, "OLD_STOP_CANCEL_UNRESOLVED"):
            ex.recover_closed_position(local)

    def test_incomplete_close_evidence_is_rejected_instead_of_inventing_zero_exit(self):
        ex = AdapterHarness(self.cfg)
        rows = [
            {"id": 1, "orderId": 7001, "price": "100", "qty": "1", "realizedPnl": "0", "side": "BUY", "positionSide": "BOTH", "time": 1_000_001},
            {"id": 2, "orderId": 9001, "price": "99", "qty": "0.4", "realizedPnl": "-0.4", "side": "SELL", "positionSide": "BOTH", "time": 1_000_500},
        ]
        local = {"symbol": "BTCUSDT", "side": "LONG", "quantity": 1.0, "entry_timestamp_ms": 1_000_000, "entry_order_id": "7001"}
        with self.assertRaisesRegex(TestnetExchangeError, "CLOSE_EVIDENCE_INCOMPLETE"):
            ex._settle_local_position_from_trades(local, rows)

    def test_position_snapshot_rejects_hedge_or_multiple_positions(self):
        ex = BinanceTestnetExchange(self.cfg)
        with mock.patch.object(ex, "_signed_get", return_value=[{
            "symbol": "BTCUSDT", "positionAmt": "1", "positionSide": "LONG", "entryPrice": "100",
        }]):
            with self.assertRaisesRegex(TestnetExchangeError, "HEDGE_MODE_UNSUPPORTED"):
                ex.position_snapshot()
        with mock.patch.object(ex, "_signed_get", return_value=[
            {"symbol": "BTCUSDT", "positionAmt": "1", "positionSide": "BOTH", "entryPrice": "100"},
            {"symbol": "ETHUSDT", "positionAmt": "1", "positionSide": "BOTH", "entryPrice": "50"},
        ]):
            with self.assertRaisesRegex(TestnetExchangeError, "MULTIPLE_POSITIONS_DETECTED"):
                ex.position_snapshot()

    def test_env_loader_uses_fixed_external_file_and_does_not_override_exported_value(self):
        path = Path(self.tmp.name) / ".env"
        path.write_text("TESTNET_API_KEY=file-key\nTESTNET_API_SECRET=file-secret\n")
        with mock.patch.dict(os.environ, {"TESTNET_API_KEY": "exported-key"}, clear=True):
            run_execution.load_env_file(path)
            self.assertEqual(os.environ["TESTNET_API_KEY"], "exported-key")
            self.assertEqual(os.environ["TESTNET_API_SECRET"], "file-secret")
        self.assertEqual(str(run_execution.DEFAULT_ENV_FILE), "/home/ubuntu/.config/nbot/.env")

    def test_mechanical_outcome_sink_marks_rows_non_research(self):
        path = Path(self.tmp.name) / "outcomes.jsonl"
        sink = run_execution.MechanicalOutcomeSink(path)
        from nbot.execution_protocol import ExecutionOutcome
        outcome = ExecutionOutcome.create(
            outcome_id="OUT-1", proposal_id="P-1", environment="TESTNET", symbol="BTCUSDT", side="LONG",
            entry_price=100, exit_price=101, quantity=1, initial_risk_usd=10, realized_pnl_usd=1, r_multiple=.1,
            mae_r=-.1, mfe_r=.2, entry_timestamp_ms=1, closed_timestamp_ms=2, exit_reason="TEST",
            entry_authority="TESTNET_MECHANICAL_CANARY_V1", model_version="NONE_MECHANICAL_CANARY",
            exit_policy_version="INTEGER_R_STEP_CONTROL", feature_version="NONE_MECHANICAL_CANARY",
            data_generation_id="TESTNET_MECHANICAL_CANARY_V1", market_event_id="MECH-1",
        )
        self.assertEqual(sink.send_outcome(outcome), "RECORDED")
        self.assertEqual(sink.send_outcome(outcome), "ALREADY_RECORDED")
        row = json.loads(path.read_text().strip())
        self.assertFalse(row["research_evidence"])
        self.assertEqual(row["evidence_class"], "TESTNET_MECHANICAL_ONLY")


if __name__ == "__main__":
    unittest.main()
