from __future__ import annotations

import unittest

from nbot.exchange.contracts import (
    AccountSnapshot,
    CloseFill,
    EntryPlan,
    ExchangePort,
    ExchangePosition,
    Fill,
    ProtectiveStopRef,
    Quote,
)
from nbot.execution.models import OpenPosition


class CompleteFakeExchange:
    def connect(self):
        return None

    def is_healthy(self):
        return True

    def quote(self, symbol):
        return Quote(symbol, 99.0, 101.0, 1)

    def account_snapshot(self):
        return AccountSnapshot(1000.0)

    def position_snapshot(self):
        return None

    def protective_stop_snapshot(self, symbol):
        return None

    def validate_protective_stop(self, symbol, side, stop_price):
        return True

    def set_leverage(self, symbol, leverage):
        return None

    def open_market(self, plan, *, client_order_id):
        return Fill(plan.expected_entry_price, plan.quantity, "1", client_order_id, 2)

    def recover_inflight_entry(self, plan, *, client_order_id):
        return None

    def ensure_protective_stop(self, symbol, side, quantity, stop_price):
        return ProtectiveStopRef(symbol, side, quantity, stop_price, stop_id="S")

    def replace_protective_stop(self, symbol, side, quantity, stop_price):
        return ProtectiveStopRef(symbol, side, quantity, stop_price, stop_id="S2")

    def close_position(self, symbol, side, *, reason):
        return CloseFill(100.0, 3, reason, realized_pnl_usd=0.0, order_ids=("2",))

    def recover_closed_position(self, local_position: OpenPosition):
        return CloseFill(100.0, 3, "RECOVERED", realized_pnl_usd=0.0, order_ids=("2",))


class IncompleteExchange:
    def connect(self):
        return None


class ExchangePortContractTests(unittest.TestCase):
    def test_complete_adapter_satisfies_runtime_protocol_shape(self):
        self.assertIsInstance(CompleteFakeExchange(), ExchangePort)

    def test_incomplete_adapter_does_not_satisfy_runtime_protocol_shape(self):
        self.assertNotIsInstance(IncompleteExchange(), ExchangePort)

    def test_port_supports_entry_and_exact_identity_recovery_boundary(self):
        exchange = CompleteFakeExchange()
        plan = EntryPlan("BTCUSDT", "LONG", 1.0, 100.0, 99.0, 1.0, 100.0, 2)
        fill = exchange.open_market(plan, client_order_id="NBOT-E-1")
        self.assertEqual(fill.client_order_id, "NBOT-E-1")
        self.assertIsNone(exchange.recover_inflight_entry(plan, client_order_id="NBOT-E-1"))

    def test_port_stop_ref_contains_recoverable_identity(self):
        exchange = CompleteFakeExchange()
        stop = exchange.ensure_protective_stop("BTCUSDT", "LONG", 1.0, 99.0)
        self.assertEqual(stop.stop_id, "S")
        replacement = exchange.replace_protective_stop("BTCUSDT", "LONG", 1.0, 100.0)
        self.assertEqual(replacement.stop_id, "S2")


if __name__ == "__main__":
    unittest.main()
