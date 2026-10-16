"""Pure local tests for M1 Binance public-market preflight; no requests."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nbot_m1_preflight", ROOT / "scripts/m1_market_preflight.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

NOW = 1_800_000_000_000
HOUR = 3_600_000


def kline(start_ms, delta, volume="10"):
    return [start_ms, "100", "102", "99", "101", volume, start_ms + delta - 1]


def fixture(old_data=True, gaps=False, active=True, valid=True):
    config = {
        "dry_run": True, "trading_mode": "futures",
        "exchange": {"pair_whitelist": ["BTC/USDT:USDT"]},
    }
    metadata = {"symbols": [{
        "symbol": "BTCUSDT",
        "contractType": "PERPETUAL" if valid else "CURRENT_QUARTER",
        "status": "TRADING" if active else "BREAK",
        "quoteAsset": "USDT",
        "marginAsset": "USDT",
        "onboardDate": NOW - 400 * 24 * HOUR,
    }]}
    cutoff = NOW - 60 * 24 * HOUR

    def fetch(path, query):
        if path != "/fapi/v1/klines":
            raise AssertionError("Only public kline queries expected")
        delta = module.INTERVAL_MS[query["interval"]]
        if query.get("limit") == 1:
            return [kline(cutoff, delta)] if old_data else []
        start = NOW - 4 * delta
        rows = [kline(start + i * delta, delta) for i in range(3)]
        if gaps:
            rows[1][0] += delta
            rows[1][6] += delta
        return rows

    return config, metadata, fetch


class BinancePreflightTests(unittest.TestCase):
    def test_25_configured_candidates_are_valid_public_pair_types(self):
        cfg = json.loads((ROOT / "user_data" / "config.json").read_text())
        symbols = [module.pair_symbol(p) for p in cfg["exchange"]["pair_whitelist"]]
        self.assertEqual(len(symbols), 25)
        self.assertEqual(len(set(symbols)), 25)
        self.assertIn("BTCUSDT", symbols)

    def test_public_endpoint_only(self):
        with self.assertRaises(ValueError):
            module.public_json("https://evil.example/fapi/v1/klines")
        with self.assertRaises(ValueError):
            module.public_json("/fapi/v2/order")

    def test_all_qualifying_data_passes_without_trading(self):
        config, metadata, fetch = fixture()
        report = module.review(config, metadata, fetch, NOW)
        self.assertEqual(report["pairs_count"], 1)
        self.assertEqual(report["preflight_pass"], 1)
        self.assertEqual(report["preflight_fail"], 0)
        row = report["results"][0]
        self.assertTrue(row["eligible_for_history_download_preflight"])
        self.assertTrue(row["candles"]["5m"]["history_60d_probe"])
        self.assertTrue(row["candles"]["1h"]["history_60d_probe"])

    def test_preflight_fails_closed_for_missing_old_history(self):
        config, metadata, fetch = fixture(old_data=False)
        report = module.review(config, metadata, fetch, NOW)
        self.assertEqual(report["preflight_fail"], 1)
        self.assertIn("5m_OLDER_HISTORY_NOT_SEEN",
                      report["results"][0]["contract_checks"])

    def test_contract_not_trading_is_rejected_before_fetch(self):
        config, metadata, fetch = fixture(active=False)
        def forbidden_fetch(*args, **kwargs):
            self.fail("Untradeable coin must never trigger candle requests")
        report = module.review(config, metadata, forbidden_fetch, NOW)
        self.assertEqual(report["preflight_fail"], 1)
        self.assertIn("NOT_TRADING", report["results"][0]["contract_checks"])

    def test_wrong_futures_contract_is_rejected(self):
        config, metadata, fetch = fixture(valid=False)
        report = module.review(config, metadata, fetch, NOW)
        self.assertEqual(report["preflight_fail"], 1)
        self.assertIn("NOT_PERPETUAL", report["results"][0]["contract_checks"])

    def test_invalid_gap_is_rejected(self):
        config, metadata, fetch = fixture(gaps=True)
        report = module.review(config, metadata, fetch, NOW)
        self.assertEqual(report["preflight_fail"], 1)
        self.assertGreater(report["results"][0]["candles"]["5m"]["recent_gaps"], 0)


if __name__ == "__main__":
    unittest.main()
