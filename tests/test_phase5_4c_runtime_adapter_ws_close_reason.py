import importlib
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class CaptureLog:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)

    def error(self, message):
        self.errors.append(message)

    def critical(self, message):
        self.errors.append(message)


class OneMessageSocket:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False

    def recv(self):
        return self.payload

    def close(self):
        self.closed = True


class ReconciliationState:
    def __init__(self):
        self.data = {
            "engine_state": "RUNNING",
            "balance": 10000.0,
            "active_trade_panel_message_id": None,
        }
        self.open_position = {
            "symbol": "BTCUSDT",
            "side": "LONG",
            "entry_price": None,
            "qty": None,
            "entry_timestamp": None,
        }

    def get_state(self):
        return self.data

    def get_open_position(self):
        return self.open_position

    def update_daily_realized(self, value):
        self.daily_realized = value

    def update_after_trade(self, *, balance, open_position, last_trade):
        self.open_position = open_position

    def save(self):
        self.saved = True

    def clear_shutdown_request(self):
        pass


class PositionState:
    def __init__(self):
        self.state = {
            "active_trade_panel_message_id": 123,
            "last_trade": None,
        }

    def get_state(self):
        return self.state

    def update_daily_realized(self, value):
        self.daily_realized = value

    def update_after_trade(self, *, balance, open_position, last_trade):
        self.state["balance"] = balance
        self.state["open_position"] = open_position
        self.state["last_trade"] = last_trade

    def clear_trade_panel_message_id(self):
        self.state["active_trade_panel_message_id"] = None

    def save(self):
        self.saved = True


class Phase54CRuntimeFixTests(unittest.TestCase):
    def test_live_legacy_market_url_is_migrated_and_used(self):
        env = {
            "TRADING_ENV": "LIVE",
            "EXECUTION_MODE": "SHADOW",
            "LIVE_BASE_URL": "https://fapi.binance.com",
            "LIVE_MARKET_WS_URL": (
                "wss://fstream.binance.com/ws/!ticker@arr"
            ),
        }
        with patch.dict(os.environ, env, clear=False):
            import config
            import execution.binance_market_client as module

            importlib.reload(config)
            module = importlib.reload(module)
            log = CaptureLog()
            client = module.BinanceMarketClient(system_log=log)

            expected = (
                "wss://fstream.binance.com/market/ws/!ticker@arr"
            )
            self.assertEqual(client.market_ws_url, expected)
            self.assertTrue(
                any("PUBLIC_WS_URL_MIGRATED" in x for x in log.warnings)
            )

            socket = OneMessageSocket(json.dumps([
                {"s": "BTCUSDT", "c": "65000.0"},
            ]))
            with patch.object(
                module.websocket,
                "create_connection",
                return_value=socket,
            ) as create_connection:
                stream = client.price_stream()
                tick = next(stream)
                stream.close()

            self.assertEqual(tick.symbol, "BTCUSDT")
            create_connection.assert_called_once_with(
                expected,
                timeout=config.PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS,
            )

    def test_shadow_reconciliation_skips_private_http_cleanup(self):
        from engine.reconciliation import ReconciliationLifecycle

        class PaperLikeExchange:
            def get_position(self):
                return None

            def get_trade_realized_pnl(self, **kwargs):
                return {"pnl": None, "exit_price": None}

        log = CaptureLog()
        trade_log = CaptureLog()
        state = ReconciliationState()
        lifecycle = ReconciliationLifecycle(
            exchange=PaperLikeExchange(),
            state=state,
            risk=SimpleNamespace(RISK_PER_TRADE_USD=10.0),
            emergency=SimpleNamespace(),
            universe=SimpleNamespace(maybe_reload=lambda **kwargs: None),
            system_log=log,
            trade_log=trade_log,
        )

        lifecycle.run(reason="TEST_STALE_SHADOW_STATE")

        self.assertTrue(
            any(
                "RECON_ORPHAN_SL_CLEANUP_NOT_APPLICABLE" in x
                for x in log.infos
            )
        )
        self.assertTrue(any("entry=0.0000" in x for x in trade_log.infos))
        self.assertTrue(any("qty=0.000000" in x for x in trade_log.infos))
        self.assertFalse(any("RECONCILIATION_FAILED" in x for x in log.errors))
        self.assertIsNone(state.open_position)

    def test_paper_trade_details_expose_actual_exit_reason(self):
        from execution.paper_exchange import PaperExchange

        exchange = PaperExchange.__new__(PaperExchange)
        exchange._last_trade = SimpleNamespace(
            symbol="RIFUSDT",
            net_pnl_usd=27.41,
            exit_price=0.07219444,
            exit_reason="STOP_LOSS",
        )

        details = exchange.get_trade_realized_pnl(symbol="RIFUSDT")

        self.assertEqual(details["exit_reason"], "STOP_LOSS")
        self.assertEqual(details["pnl"], 27.41)

    def test_position_close_panel_preserves_actual_exit_reason(self):
        from engine.position_lifecycle import PositionLifecycle

        exchange = SimpleNamespace(
            get_trade_realized_pnl=lambda **kwargs: {
                "pnl": 27.41,
                "exit_price": 0.07219444,
                "exit_reason": "STOP_LOSS",
            },
            get_available_balance=lambda: 10027.41,
        )
        state = PositionState()
        log = CaptureLog()
        trade_log = CaptureLog()
        lifecycle = PositionLifecycle(
            exchange=exchange,
            state=state,
            risk=SimpleNamespace(),
            emergency=SimpleNamespace(),
            reconciliation=SimpleNamespace(),
            universe=SimpleNamespace(maybe_reload=lambda **kwargs: None),
            system_log=log,
            trade_log=trade_log,
        )
        open_position = {
            "symbol": "RIFUSDT",
            "side": "SHORT",
            "entry_price": 0.07430514,
            "initial_stop_loss": 0.07504834,
            "stop_loss": 0.07207,
            "qty": 13455.32831,
            "initial_risk_usd": 10.0,
            "risk_usd": 10.0,
            "entry_timestamp": None,
            "mae": 0.0,
            "mfe": 30.0,
            "candidate_observation_id": None,
        }

        with patch(
            "engine.position_lifecycle.format_trade_close_panel",
            return_value="closed panel",
        ) as formatter, patch(
            "engine.position_lifecycle.edit_message"
        ) as edit_message:
            lifecycle._handle_close(open_position)

        self.assertEqual(
            formatter.call_args.kwargs["exit_reason"],
            "STOP_LOSS",
        )
        edit_message.assert_called_once_with(123, "closed panel")
        self.assertEqual(state.state["last_trade"]["exit_reason"], "STOP_LOSS")
        self.assertTrue(
            any("exit_reason=STOP_LOSS" in x for x in trade_log.infos)
        )


if __name__ == "__main__":
    unittest.main()
