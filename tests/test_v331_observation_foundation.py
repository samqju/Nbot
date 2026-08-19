from __future__ import annotations

import ast
from dataclasses import fields, replace
from pathlib import Path
import unittest

from nbot.config.profiles import get_profile
from nbot.observation.config import (
    LIVE_PUBLIC_REST_BASE_URL,
    TESTNET_PUBLIC_REST_BASE_URL,
    ObservationConfig,
    observation_config_for_profile,
)
from nbot.observation.models import (
    Candle,
    FundingEvent,
    SourceCapture,
    UniverseCapture,
    UniverseRow,
    spread_pct,
)
from nbot.observation.public_market import PublicMarketClient


REPO = Path(__file__).resolve().parents[1]


def row(symbol: str = "BTCUSDT", rank: int = 1) -> UniverseRow:
    bid = 100.0
    ask = 100.1
    return UniverseRow(
        symbol=symbol,
        universe_rank=rank,
        quote_volume_24h_usd=10_000_000.0,
        bid_price=bid,
        ask_price=ask,
        spread_pct=spread_pct(bid, ask),
        mark_price=100.05,
        index_price=100.04,
        funding_rate=0.0001,
        next_funding_time_ms=1_800_000,
    )


class CompletePublicClient:
    def server_time_ms(self):
        return 900_000

    def local_time_ms(self):
        return 900_001

    def eligible_universe_capture(self):
        return UniverseCapture((row(),), (SourceCapture("ticker_24h", 1, 2),))

    def closed_candles(self, symbols, open_time_ms):
        return {}, {}

    def historical_candles_for_symbols(self, symbols, open_times_ms):
        return {}, {}

    def funding_history(self, start_time_ms, end_time_ms):
        return ()


class IncompletePublicClient:
    def server_time_ms(self):
        return 900_000


class V331ObservationFoundationTests(unittest.TestCase):
    def test_live_profile_builds_canonical_live_public_config(self):
        cfg = observation_config_for_profile(get_profile("live-paper"))
        self.assertEqual(cfg.market_environment, "LIVE")
        self.assertEqual(cfg.binance_public_base_url, LIVE_PUBLIC_REST_BASE_URL)
        self.assertEqual(cfg.database_path, Path("data/observation/live/observer.db"))
        self.assertTrue(cfg.canonical_live_research)
        self.assertEqual(cfg.candle_interval, "5m")
        self.assertEqual(cfg.observation_universe_size, 200)

    def test_live_trade_and_live_paper_share_public_observation_config(self):
        paper = observation_config_for_profile(get_profile("live-paper"))
        trade = observation_config_for_profile(get_profile("live-trade"))
        self.assertEqual(paper, trade)

    def test_testnet_public_config_is_separate_and_not_canonical_research(self):
        cfg = observation_config_for_profile(get_profile("testnet-trade"))
        self.assertEqual(cfg.market_environment, "TESTNET")
        self.assertEqual(cfg.binance_public_base_url, TESTNET_PUBLIC_REST_BASE_URL)
        self.assertEqual(cfg.database_path, Path("data/observation/testnet/observer.db"))
        self.assertFalse(cfg.canonical_live_research)

    def test_observation_config_contains_no_private_or_order_credentials(self):
        names = {field.name.lower() for field in fields(ObservationConfig)}
        forbidden_fragments = ("api_key", "secret", "private", "order_write", "leverage", "risk_per_trade")
        self.assertFalse(any(fragment in name for name in names for fragment in forbidden_fragments))

    def test_config_fails_closed_on_endpoint_and_clock_drift_from_contract(self):
        cfg = observation_config_for_profile(get_profile("live-paper"))
        with self.assertRaisesRegex(ValueError, "PUBLIC_ENDPOINT_MISMATCH"):
            replace(cfg, binance_public_base_url=TESTNET_PUBLIC_REST_BASE_URL).validate()
        with self.assertRaisesRegex(ValueError, "CANONICAL_CLOCK_INVALID"):
            replace(cfg, candle_interval="1m", candle_interval_ms=60_000).validate()

    def test_config_fails_closed_on_wrong_database_path(self):
        cfg = observation_config_for_profile(get_profile("live-paper"))
        with self.assertRaisesRegex(ValueError, "DATABASE_PATH_MISMATCH"):
            replace(cfg, database_path=Path("data/observer.db")).validate()

    def test_candle_enforces_completed_five_minute_shape(self):
        candle = Candle(
            "BTCUSDT", 600_000, 899_999, 100.0, 101.0, 99.0, 100.5,
            10.0, 1_000.0, 20, 5.0, 500.0,
        )
        self.assertEqual(candle.close_time_ms, 899_999)
        with self.assertRaisesRegex(ValueError, "CANDLE_INTERVAL_INVALID"):
            replace(candle, close_time_ms=899_998)

    def test_universe_capture_requires_unique_symbols_and_contiguous_ranks(self):
        one = row("BTCUSDT", 1)
        two = row("ETHUSDT", 2)
        capture = UniverseCapture((one, two), (SourceCapture("ticker_24h", 1, 2),))
        self.assertEqual(tuple(item.symbol for item in capture.rows), ("BTCUSDT", "ETHUSDT"))
        with self.assertRaisesRegex(ValueError, "SYMBOL_DUPLICATE"):
            UniverseCapture((one, replace(one, universe_rank=2)), ())
        with self.assertRaisesRegex(ValueError, "RANK_NONDETERMINISTIC"):
            UniverseCapture((one, replace(two, universe_rank=3)), ())

    def test_universe_row_rejects_inconsistent_spread(self):
        with self.assertRaisesRegex(ValueError, "SPREAD_PCT_INCONSISTENT"):
            replace(row(), spread_pct=9.0)

    def test_source_capture_and_funding_event_validate_time(self):
        SourceCapture("book_ticker", 100, 101)
        FundingEvent("BTCUSDT", 100, 0.0001, 100.0)
        with self.assertRaisesRegex(ValueError, "SOURCE_CAPTURE_TIME_INVALID"):
            SourceCapture("book_ticker", 101, 100)
        with self.assertRaisesRegex(ValueError, "FUNDING_TIME_INVALID"):
            FundingEvent("BTCUSDT", -1, 0.0001, 100.0)

    def test_public_market_protocol_is_explicit_and_runtime_checkable(self):
        self.assertIsInstance(CompletePublicClient(), PublicMarketClient)
        self.assertNotIsInstance(IncompletePublicClient(), PublicMarketClient)

    def test_observation_foundation_has_no_capital_or_later_phase_imports(self):
        forbidden_prefixes = (
            "nbot.execution",
            "nbot.exchange",
            "nbot.communication",
        )
        for path in sorted((REPO / "nbot/observation").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: list[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module)
            bad = [name for name in imported if name.startswith(forbidden_prefixes)]
            self.assertEqual(bad, [], f"{path.name}: {bad}")


if __name__ == "__main__":
    unittest.main()
