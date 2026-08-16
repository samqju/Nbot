from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ObserverConfig:
    """Version-controlled, non-secret V2.0 Observation configuration."""

    role: str = "OBSERVER_RESEARCH"
    market_environment: str = "LIVE_PUBLIC"
    binance_base_url: str = "https://fapi.binance.com"

    candle_interval: str = "5m"
    candle_interval_ms: int = 5 * 60 * 1000
    capture_settle_seconds: float = 4.0
    retry_seconds: float = 30.0

    observation_universe_size: int = 200
    min_quote_volume_24h_usd: float = 3_000_000.0
    max_spread_pct: float = 0.50

    request_timeout_seconds: float = 12.0
    candle_fetch_workers: int = 16

    database_path: Path = Path("data/observer.db")
    schema_version: str = "NBOT_V2_MARKET_EVIDENCE_V1"
    collector_version: str = "NBOT_V2_OBSERVER_FOUNDATION_V1"

    # Stored now so every later simulation uses one explicit cost contract.
    taker_fee_rate: float = 0.0005
    entry_slippage_bps: float = 2.0
    exit_slippage_bps: float = 2.0

    def validate(self) -> None:
        if self.role != "OBSERVER_RESEARCH":
            raise ValueError("V2.0 permits only OBSERVER_RESEARCH")
        if self.market_environment != "LIVE_PUBLIC":
            raise ValueError("V2.0 collects only LIVE public market evidence")
        if self.binance_base_url != "https://fapi.binance.com":
            raise ValueError("V2.0 Binance base URL must be the LIVE USD-M public endpoint")
        if self.candle_interval != "5m" or self.candle_interval_ms != 300_000:
            raise ValueError("V2.0 decision clock is fixed to completed 5-minute candles")
        if not 1 <= self.observation_universe_size <= 500:
            raise ValueError("observation_universe_size must be between 1 and 500")
        if self.min_quote_volume_24h_usd < 0:
            raise ValueError("min_quote_volume_24h_usd must be non-negative")
        if not 0 < self.max_spread_pct <= 5:
            raise ValueError("max_spread_pct must be > 0 and <= 5 percent")
        if not 1 <= self.candle_fetch_workers <= 64:
            raise ValueError("candle_fetch_workers must be between 1 and 64")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if self.taker_fee_rate < 0 or self.entry_slippage_bps < 0 or self.exit_slippage_bps < 0:
            raise ValueError("cost assumptions must be non-negative")


CONFIG = ObserverConfig()
CONFIG.validate()
