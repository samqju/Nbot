import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from execution.paper_account import PaperAccount
from execution.paper_exchange import PaperExchange


class Log:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warning(self, message):
        self.warnings.append(message)


class Market:
    def __init__(self, ticks=None):
        self.ticks = list(ticks or [])
        self.connected = False

    def connect(self):
        self.connected = True
        return True

    def disconnect(self):
        self.connected = False

    def preflight(self, *, symbol, candle_limit):
        return {"environment": "LIVE", "auth": "NONE", "symbol": symbol, "last_price": 100.0, "spread_pct": 0.01, "completed_candles": candle_limit, "tick_size": 0.1}

    def price_stream(self):
        yield from self.ticks

    def quantize_price(self, symbol, price):
        return float(price)


class Phase16RecoveryTests(unittest.TestCase):
    def _account(self, root):
        return PaperAccount(
            starting_balance_usd=10000,
            state_path=str(root / "paper_state.json"),
            trades_path=str(root / "paper_trades.jsonl"),
            source="PAPER_LIVE",
        )

    def test_connect_restores_open_position_and_stop_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            account = self._account(root)
            account.load_or_create()
            account.open_position(
                symbol="BTCUSDT",
                side="LONG",
                qty=0.01,
                entry_price=100.0,
                stop_loss=95.0,
                opened_at_ms=1000,
                initial_risk_usd=0.05,
                entry_fee_usd=0.001,
                trade_id="trade-restart-1",
            )

            restored = self._account(root)
            log = Log()
            exchange = PaperExchange(
                market_client=Market(),
                account=restored,
                system_log=log,
            )
            exchange.connect()

            self.assertIsInstance(exchange._active_sl_order_id, int)
            self.assertGreater(exchange._active_sl_order_id, 0)

            self.assertTrue(log.warnings)
            self.assertIn("PAPER_POSITION_RECOVERED", log.warnings[0])
            self.assertIn("BTCUSDT", log.warnings[0])
            self.assertIn("stop=95.0", log.warnings[0])

    def test_connect_logs_flat_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = Log()
            exchange = PaperExchange(
                market_client=Market(),
                account=self._account(root),
                system_log=log,
            )
            exchange.connect()
            self.assertTrue(any("PAPER_ACCOUNT_READY" in x for x in log.infos))
            self.assertTrue(any("position=FLAT" in x for x in log.infos))

    def test_price_stream_emits_periodic_paper_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ticks = [
                SimpleNamespace(symbol="BTCUSDT", price=100.0, timestamp=1000),
                SimpleNamespace(symbol="ETHUSDT", price=200.0, timestamp=2000),
            ]
            log = Log()
            exchange = PaperExchange(
                market_client=Market(ticks),
                account=self._account(root),
                system_log=log,
            )
            exchange.connect()
            with patch(
                "execution.paper_exchange.PAPER_HEARTBEAT_INTERVAL_SECONDS",
                60.0,
            ), patch(
                "execution.paper_exchange.time.monotonic",
                side_effect=[100.0, 101.0],
            ):
                self.assertEqual(len(list(exchange.price_stream())), 2)
            heartbeats = [x for x in log.infos if "PAPER_HEARTBEAT" in x]
            self.assertEqual(len(heartbeats), 1)
            self.assertIn("position=FLAT", heartbeats[0])

    def test_invalid_heartbeat_interval_is_rejected(self):
        env = os.environ.copy()
        env.update(
            {
                "TRADING_ENV": "LIVE",
                "EXECUTION_MODE": "SHADOW",
                "PAPER_HEARTBEAT_INTERVAL_SECONDS": "1",
            }
        )
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PAPER_HEARTBEAT_INTERVAL_SECONDS", result.stderr)

    def test_heartbeat_uses_cached_open_symbol_price(self):
        with tempfile.TemporaryDirectory() as root:
            account = self._account(Path(root))
            account.load_or_create()
            account.open_position(
                symbol="WAXPUSDT",
                side="SHORT",
                qty=1000.0,
                entry_price=0.0042,
                stop_loss=0.0043,
                opened_at_ms=1,
                initial_risk_usd=1.0,
                entry_fee_usd=0.0,
                trade_id="trade-heartbeat-cache-1",
            )
            log = Log()
            exchange = PaperExchange(
                market_client=Market(),
                account=account,
                system_log=log,
            )
            exchange.on_market_tick(
                symbol="WAXPUSDT",
                price=0.0041,
                timestamp=2,
            )
            exchange._last_heartbeat_monotonic = 0.0
            exchange._maybe_log_heartbeat(
                tick=SimpleNamespace(
                    symbol="BTCUSDT",
                    price=62000.0,
                )
            )
            heartbeat = [x for x in log.infos if "PAPER_HEARTBEAT" in x][-1]
            self.assertIn("observed_price=0.0041", heartbeat)
            self.assertNotIn("observed_price=None", heartbeat)


if __name__ == "__main__":
    unittest.main()
