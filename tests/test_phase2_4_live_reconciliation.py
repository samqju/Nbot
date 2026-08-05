import unittest
from types import SimpleNamespace

from execution.live_reconciliation import LiveReconciler


class Log:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, message):
        self.infos.append(message)

    def error(self, message):
        self.errors.append(message)


class Exchange:
    def __init__(self, positions=None, orders=None, stops=None):
        self.positions = positions or []
        self.orders = orders or []
        self.stops = stops or []

    def list_open_positions(self):
        return list(self.positions)

    def list_open_orders(self):
        return list(self.orders)

    def list_protective_stops(self):
        return list(self.stops)


class Phase24LiveReconciliationTests(unittest.TestCase):
    def test_flat_local_and_flat_exchange_is_safe(self):
        log = Log()
        report = LiveReconciler(
            exchange=Exchange(),
            system_log=log,
        ).run(local_position=None)
        self.assertTrue(report.safe)
        self.assertEqual(report.status, "SAFE")
        self.assertTrue(any("status=SAFE" in x for x in log.infos))

    def test_unexpected_live_position_fails_closed(self):
        report = LiveReconciler(
            exchange=Exchange(
                positions=[{
                    "symbol": "BTCUSDT",
                    "side": "LONG",
                    "qty": 0.01,
                    "entry_price": 60000.0,
                }]
            ),
            system_log=Log(),
        ).run(local_position=None)
        self.assertIn("UNEXPECTED_LIVE_POSITION", report.issues)
        with self.assertRaisesRegex(
            RuntimeError,
            "LIVE_RECONCILIATION_UNSAFE",
        ):
            report.require_safe()

    def test_expected_position_and_stop_are_safe(self):
        exchange = Exchange(
            positions=[{
                "symbol": "BTCUSDT",
                "side": "LONG",
                "qty": 0.01,
                "entry_price": 60000.0,
            }],
            stops=[{
                "symbol": "BTCUSDT",
                "algo_id": 7,
                "side": "SELL",
                "reduce_only": True,
                "stop_price": 59000.0,
            }],
        )
        local = SimpleNamespace(
            symbol="BTCUSDT",
            side="LONG",
            qty=0.01,
            entry_price=60000.0,
            stop_loss=59000.0,
        )
        report = LiveReconciler(
            exchange=exchange,
            system_log=Log(),
        ).run(local_position=local)
        self.assertTrue(report.safe)

    def test_side_quantity_and_stop_mismatches_are_reported(self):
        exchange = Exchange(
            positions=[{
                "symbol": "BTCUSDT",
                "side": "SHORT",
                "qty": 0.02,
                "entry_price": 60000.0,
            }],
        )
        report = LiveReconciler(
            exchange=exchange,
            system_log=Log(),
        ).run(local_position={
            "symbol": "BTCUSDT",
            "side": "LONG",
            "qty": 0.01,
            "entry_price": 60000.0,
            "stop_loss": 59000.0,
        })
        self.assertIn("POSITION_SIDE_MISMATCH", report.issues)
        self.assertIn("POSITION_QTY_MISMATCH", report.issues)
        self.assertIn("PROTECTIVE_STOP_MISSING", report.issues)

    def test_orphan_stop_and_non_reduce_only_order_are_unsafe(self):
        exchange = Exchange(
            orders=[{
                "symbol": "ETHUSDT",
                "order_id": 1,
                "reduce_only": False,
            }],
            stops=[{
                "symbol": "ETHUSDT",
                "algo_id": 2,
                "reduce_only": True,
                "stop_price": 3000.0,
            }],
        )
        report = LiveReconciler(
            exchange=exchange,
            system_log=Log(),
        ).run(local_position=None)
        self.assertIn("ORPHAN_PROTECTIVE_STOP", report.issues)
        self.assertIn("NON_REDUCE_ONLY_OPEN_ORDER", report.issues)

    def test_multiple_live_positions_are_unsafe(self):
        exchange = Exchange(
            positions=[
                {"symbol": "BTCUSDT", "side": "LONG", "qty": 0.01},
                {"symbol": "ETHUSDT", "side": "SHORT", "qty": 0.1},
            ]
        )
        report = LiveReconciler(
            exchange=exchange,
            system_log=Log(),
        ).run(local_position=None)
        self.assertIn("MULTIPLE_LIVE_POSITIONS", report.issues)


if __name__ == "__main__":
    unittest.main()
