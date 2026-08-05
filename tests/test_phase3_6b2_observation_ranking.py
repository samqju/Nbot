import os
import unittest
from unittest.mock import patch

import observation_universe


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payloads):
        self.payloads = list(payloads)

    def get(self, url, timeout):
        return Response(self.payloads.pop(0))


class Phase36B2ObservationRankingTests(unittest.TestCase):
    def _payloads(self, count=220):
        symbols = [
            {
                "symbol": f"C{index}USDT",
                "contractType": "PERPETUAL",
                "quoteAsset": "USDT",
                "status": "TRADING",
            }
            for index in range(count)
        ]
        tickers = [
            {
                "symbol": f"C{index}USDT",
                "quoteVolume": str(5_000_000 + index * 100_000),
                "priceChangePercent": str(1 + index % 12),
                "lastPrice": "10",
                "count": str(1000 + index * 10),
            }
            for index in range(count)
        ]
        books = [
            {
                "symbol": f"C{index}USDT",
                "bidPrice": "9.99",
                "askPrice": "10.01",
            }
            for index in range(count)
        ]
        return {"symbols": symbols}, tickers, books

    def test_builder_returns_target_and_execution_subset(self):
        session = Session(self._payloads())
        env = {
            "LIVE_BASE_URL": "https://example.invalid",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(
            observation_universe,
            "TRADING_ENV",
            "LIVE",
        ):
            result = observation_universe.build_observation_universe(
                {"C0USDT", "C1USDT"},
                session=session,
                target_size=200,
                core_size=150,
            )

        self.assertEqual(len(result), 200)
        self.assertEqual(result, sorted(result))
        self.assertIn("C0USDT", result)
        self.assertIn("C1USDT", result)

    def test_testnet_can_return_less_than_target_when_market_is_smaller(self):
        session = Session(self._payloads(count=45))
        env = {
            "TESTNET_BASE_URL": "https://example.invalid",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(
            observation_universe,
            "TRADING_ENV",
            "TESTNET",
        ):
            result = observation_universe.build_observation_universe(
                {"C0USDT"},
                session=session,
                target_size=200,
                core_size=150,
            )
        self.assertEqual(len(result), 45)

    def test_ineligible_execution_symbol_is_rejected(self):
        exchange_info, tickers, books = self._payloads(count=40)
        tickers[0]["quoteVolume"] = "1"
        session = Session((exchange_info, tickers, books))
        with patch.dict(
            os.environ,
            {"LIVE_BASE_URL": "https://example.invalid"},
            clear=False,
        ), patch.object(
            observation_universe,
            "TRADING_ENV",
            "LIVE",
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "OBSERVATION_EXECUTION_SYMBOLS_INELIGIBLE",
            ):
                observation_universe.build_observation_universe(
                    {"C0USDT"},
                    session=session,
                    target_size=30,
                    core_size=30,
                )

    def test_compatibility_mode_omits_ineligible_execution_symbol(self):
        exchange_info, tickers, books = self._payloads(count=40)
        tickers[0]["quoteVolume"] = "1"
        session = Session((exchange_info, tickers, books))
        with patch.dict(
            os.environ,
            {"LIVE_BASE_URL": "https://example.invalid"},
            clear=False,
        ), patch.object(
            observation_universe,
            "TRADING_ENV",
            "LIVE",
        ):
            result = observation_universe.build_observation_universe(
                {"C0USDT"},
                session=session,
                target_size=30,
                core_size=20,
                require_execution_eligible=False,
            )

        self.assertEqual(len(result), 30)
        self.assertNotIn("C0USDT", result)



if __name__ == "__main__":
    unittest.main()
