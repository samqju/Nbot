import unittest

from execution.exchange_contract import (
    REQUIRED_EXCHANGE_METHODS,
    inspect_exchange_adapter,
    validate_exchange_adapter,
)
from execution.paper_exchange import PaperExchange
from execution.testnet_exchange import TestnetExchange


class IncompleteAdapter:
    def connect(self):
        return None


class NonCallableMethodAdapter:
    pass


for _method_name in REQUIRED_EXCHANGE_METHODS:
    setattr(NonCallableMethodAdapter, _method_name, lambda self: None)
NonCallableMethodAdapter.emergency_exit = None


class Phase21ExchangeContractTests(unittest.TestCase):
    def test_contract_contains_complete_current_surface(self):
        self.assertEqual(len(REQUIRED_EXCHANGE_METHODS), 24)
        self.assertEqual(len(set(REQUIRED_EXCHANGE_METHODS)), 24)
        self.assertIn("position_price_stream", REQUIRED_EXCHANGE_METHODS)
        self.assertNotIn("price_stream", REQUIRED_EXCHANGE_METHODS)
        self.assertIn("get_historical_candles", REQUIRED_EXCHANGE_METHODS)
        self.assertIn("resolve_ambiguous_entry", REQUIRED_EXCHANGE_METHODS)
        self.assertIn("recover_active_stop_loss", REQUIRED_EXCHANGE_METHODS)
        self.assertIn("get_trade_realized_pnl", REQUIRED_EXCHANGE_METHODS)

    def test_paper_exchange_class_satisfies_contract(self):
        report = inspect_exchange_adapter(PaperExchange.__new__(PaperExchange))
        self.assertTrue(report.valid, report.missing_methods)

    def test_testnet_exchange_class_satisfies_contract(self):
        report = inspect_exchange_adapter(TestnetExchange.__new__(TestnetExchange))
        self.assertTrue(report.valid, report.missing_methods)

    def test_incomplete_adapter_fails_with_all_missing_methods(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "EXCHANGE_ADAPTER_CONTRACT_INVALID",
        ) as raised:
            validate_exchange_adapter(IncompleteAdapter())
        self.assertIn("disconnect", str(raised.exception))
        self.assertIn("emergency_exit", str(raised.exception))

    def test_non_callable_attribute_does_not_satisfy_contract(self):
        report = inspect_exchange_adapter(NonCallableMethodAdapter())
        self.assertFalse(report.valid)
        self.assertEqual(report.missing_methods, ("emergency_exit",))


if __name__ == "__main__":
    unittest.main()
