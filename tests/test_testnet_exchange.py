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
        self.next_algo_id = 100
        self.fail_cancel_ids = set()

    def quote(self, symbol):
        return Quote(symbol, 99.9, 100.1, 1_000_000)

    def position_snapshot(self):
        return self.position

    def _signed_post(self, path, params, *, ambiguous=False):
        self.calls.append(("POST", path, dict(params), ambiguous))
        if path == "/fapi/v1/order":
            cid = params["newClientOrderId"]
            order = {
                "orderId": 7,
                "clientOrderId": cid,
                "status": "FILLED",
                "executedQty": str(params["quantity"]),
                "avgPrice": "100",
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
