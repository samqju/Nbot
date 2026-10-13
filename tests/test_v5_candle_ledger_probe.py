"""Synthetic bounded live-REST-to-temp-SQLite smoke contracts."""
import unittest

from nbot.v5.candle_ledger import EvidenceHold
from nbot.v5.candle_ledger_probe import smoke_once
from tests.test_v5_public_market import (
    DONE, SERVER, exchange, klines, ticker,
)


def mocked_get(path, params=None):
    if path == "/fapi/v1/time":
        return {"serverTime": SERVER}
    if path == "/fapi/v1/exchangeInfo":
        return exchange()
    if path == "/fapi/v1/ticker/24hr":
        return ticker()
    if path == "/fapi/v1/klines":
        if params is None or params.get("limit") != "96":
            raise AssertionError("REST window must be exactly 96 bars")
        return klines()
    raise AssertionError("Unexpected route")


class CandleLedgerProbeTests(unittest.TestCase):
    def test_three_live_markets_seed_and_reopen_without_training(self):
        result = smoke_once(top=3, getter=mocked_get, clock_ms=lambda: DONE)
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["validated_symbols"], 3)
        self.assertEqual(result["validated_candles"], 288)
        self.assertTrue(result["temporary_database_removed"])
        self.assertFalse(result["research_ready"])
        self.assertFalse(result["live_final_wss_candle_confirmed"])
        self.assertFalse(result["durable_production_ingestion_enabled"])
        self.assertEqual(result["training_labels_created"], 0)
        self.assertEqual(result["order_authority"], "NONE")

    def test_stale_binance_clock_and_invalid_top_refuse_all_io(self):
        for top in (0, 13, True):
            with self.subTest(top=top), self.assertRaisesRegex(
                EvidenceHold, "UNIVERSE_BOUNDS"
            ):
                smoke_once(top=top, getter=lambda *_: self.fail("no calls"))
        with self.assertRaisesRegex(EvidenceHold, "CLOCK_SKEW"):
            smoke_once(top=3, getter=mocked_get, clock_ms=lambda: SERVER + 100_000)

    def test_missing_last_rest_candle_fails_whole_probe(self):
        def incomplete(path, params=None):
            if path == "/fapi/v1/klines":
                return klines()[:-1]
            return mocked_get(path, params)
        with self.assertRaises(EvidenceHold):
            smoke_once(top=3, getter=incomplete, clock_ms=lambda: DONE)


if __name__ == "__main__":
    unittest.main()
