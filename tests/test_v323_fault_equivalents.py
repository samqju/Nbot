from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nbot.exchange.binance_testnet import AmbiguousExecutionError, TestnetExchangeError
from nbot.exchange.contracts import ProtectiveStopRef
from tests.test_v319_testnet import Harness, loaded_exchange, plan


class TimeoutNoCommitHarness(Harness):
    """Testnet adapter fixture where an algo write times out before visible commit."""

    def _request(self, method, path, params=None, *, signed=False, ambiguous_write=False):
        if path == "/fapi/v1/algoOrder" and method == "POST":
            self.calls.append((method, path, dict(params or {}), signed, ambiguous_write))
            raise AmbiguousExecutionError("AMBIGUOUS_STOP_TIMEOUT_NO_COMMIT")
        return super()._request(
            method,
            path,
            params,
            signed=signed,
            ambiguous_write=ambiguous_write,
        )


def timeout_exchange(root: Path) -> TimeoutNoCommitHarness:
    base = loaded_exchange(root)
    ex = TimeoutNoCommitHarness(base.config)
    ex._load_filters()
    return ex


class V323AdapterFaultEquivalentTests(unittest.TestCase):
    def test_entry_quantity_quantization_edge_fails_before_order_write(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            with self.assertRaisesRegex(TestnetExchangeError, "MARKET_QUANTITY_OUT_OF_RANGE"):
                ex.open_market(
                    plan(qty=0.0009),
                    client_order_id="NBV3E-QUANTIZATION-EDGE",
                )
            writes = [
                call
                for call in ex.calls
                if call[0] == "POST" and call[1] == "/fapi/v1/order"
            ]
            self.assertEqual(writes, [])

    def test_stop_placement_timeout_fails_closed_when_identity_never_appears(self):
        with tempfile.TemporaryDirectory() as td:
            ex = timeout_exchange(Path(td))
            with self.assertRaisesRegex(TestnetExchangeError, "AMBIGUOUS_STOP_RESOLUTION_TIMEOUT"):
                ex.ensure_protective_stop("BTCUSDT", "LONG", 1.0, 90.0)
            self.assertIsNone(ex.protective_stop_snapshot("BTCUSDT"))

    def test_stop_replacement_timeout_preserves_old_known_protection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            normal = loaded_exchange(root)
            old = normal.ensure_protective_stop("BTCUSDT", "LONG", 1.0, 90.0)

            ex = TimeoutNoCommitHarness(normal.config)
            ex._filters = dict(normal._filters)
            ex.algos = {key: dict(value) for key, value in normal.algos.items()}
            with self.assertRaisesRegex(TestnetExchangeError, "AMBIGUOUS_STOP_RESOLUTION_TIMEOUT"):
                ex.replace_protective_stop("BTCUSDT", "LONG", 1.0, 95.0)

            remaining = ex.protective_stop_snapshot("BTCUSDT")
            self.assertIsNotNone(remaining)
            assert remaining is not None
            self.assertEqual(remaining.stop_id, old.stop_id)
            self.assertAlmostEqual(remaining.trigger_price, old.trigger_price)

    def test_replacement_timeout_never_attempts_old_stop_cancel(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            normal = loaded_exchange(root)
            normal.ensure_protective_stop("BTCUSDT", "LONG", 1.0, 90.0)

            ex = TimeoutNoCommitHarness(normal.config)
            ex._filters = dict(normal._filters)
            ex.algos = {key: dict(value) for key, value in normal.algos.items()}
            with self.assertRaises(TestnetExchangeError):
                ex.replace_protective_stop("BTCUSDT", "LONG", 1.0, 95.0)
            deletes = [
                call
                for call in ex.calls
                if call[0] == "DELETE" and call[1] == "/fapi/v1/algoOrder"
            ]
            self.assertEqual(deletes, [])

    def test_duplicate_stop_truth_is_not_collapsed_to_one_identity(self):
        with tempfile.TemporaryDirectory() as td:
            ex = loaded_exchange(Path(td))
            first = ex.ensure_protective_stop("BTCUSDT", "LONG", 1.0, 90.0)
            ex.next_algo += 1
            aid = str(ex.next_algo)
            ex.algos[aid] = {
                "algoId": aid,
                "clientAlgoId": "NBV3SL-DUPLICATE-SECOND",
                "algoType": "CONDITIONAL",
                "orderType": "STOP_MARKET",
                "symbol": "BTCUSDT",
                "side": "SELL",
                "positionSide": "BOTH",
                "quantity": "1.0",
                "triggerPrice": "91.0",
                "reduceOnly": True,
                "algoStatus": "NEW",
                "createTime": 1_800_000_000_020,
                "updateTime": 1_800_000_000_020,
                "actualOrderId": "",
            }
            self.assertIsInstance(first, ProtectiveStopRef)
            with self.assertRaisesRegex(TestnetExchangeError, "MULTIPLE_PROTECTIVE_STOPS"):
                ex.protective_stop_snapshot("BTCUSDT")


if __name__ == "__main__":
    unittest.main()
