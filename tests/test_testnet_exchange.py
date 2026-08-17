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
        self.next_algo_id = 100

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
                "algoType": "CONDITIONAL",
                "orderType": "STOP_MARKET",
                "reduceOnly": True,
                "triggerPrice": str(params["triggerPrice"]),
            }
            self.stops.append(row)
            return {"algoId": algo_id}
        if path == "/fapi/v1/leverage":
            return {"leverage": params["leverage"]}
        raise AssertionError(path)

    def _signed_get(self, path, params=None):
        self.calls.append(("GET", path, dict(params or {}), False))
        if path == "/fapi/v1/openAlgoOrders":
            return list(self.stops)
        if path == "/fapi/v1/order":
            return self.orders.get((params or {}).get("origClientOrderId")) or self._missing_order()
        raise AssertionError(path)

    @staticmethod
    def _missing_order():
        raise TestnetExchangeError("REST_FAILED:GET:/fapi/v1/order:400:code=-2013 msg=Order does not exist")

    def _signed_delete(self, path, params):
        self.calls.append(("DELETE", path, dict(params), False))
        if path != "/fapi/v1/algoOrder":
            raise AssertionError(path)
        target = int(params["algoId"])
        self.stops = [row for row in self.stops if int(row["algoId"]) != target]
        return {"algoId": target}


class TestnetExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arm = Path(self.tmp.name) / "armed"
        self.cfg = TestnetExchangeConfig(
            api_key="key",
            api_secret="secret",
            arm_file=self.arm,
            confirmation=REQUIRED_CONFIRMATION,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def arm_trading(self):
        self.arm.write_text(ARM_FILE_CONTENT + "\n")

    def plan(self):
        return EntryPlan("BTCUSDT", "LONG", 10.0, 100.0, 99.0, 10.0, 1000.0, 5)

    def test_config_is_hard_pinned_to_futures_testnet_hosts(self):
        self.cfg.validate()
        with self.assertRaisesRegex(ValueError, "TESTNET_REST_HOST_INVALID"):
            TestnetExchangeConfig("k", "s", base_url="https://fapi.binance.com").validate()
        with self.assertRaisesRegex(ValueError, "TESTNET_WS_HOST_INVALID"):
            TestnetExchangeConfig("k", "s", ws_base_url="wss://fstream.binance.com/ws").validate()

    def test_explicit_arm_gate_is_required_only_for_entries(self):
        guard = TestnetTradingGuard(self.cfg)
        self.assertFalse(guard.preflight()["armed"])
        with self.assertRaisesRegex(TestnetExchangeError, "TESTNET_TRADING_NOT_ARMED"):
            guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.arm_trading()
        guard.authorize_entry(symbol="BTCUSDT", quantity=1, price=100, position=None)
        self.assertEqual(guard.preflight()["session_entries"], 1)

    def test_leverage_write_is_blocked_until_testnet_gate_is_armed(self):
        ex = AdapterHarness(self.cfg)
        with self.assertRaisesRegex(TestnetExchangeError, "TESTNET_TRADING_NOT_ARMED"):
            ex.set_leverage("BTCUSDT", 5)
        self.arm_trading()
        ex.set_leverage("BTCUSDT", 5)
        self.assertTrue(any(c[0] == "POST" and c[1] == "/fapi/v1/leverage" for c in ex.calls))

    def test_market_entry_uses_client_id_and_single_order_submission(self):
        self.arm_trading()
        ex = AdapterHarness(self.cfg)
        fill = ex.open_market(self.plan(), client_order_id="NBV28-ONE")
        posts = [c for c in ex.calls if c[0] == "POST" and c[1] == "/fapi/v1/order"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][2]["newClientOrderId"], "NBV28-ONE")
        self.assertEqual(fill.client_order_id, "NBV28-ONE")

    def test_ambiguous_entry_queries_same_client_id_and_never_blind_resubmits(self):
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
