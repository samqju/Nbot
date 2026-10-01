from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path

from nbot.config.profiles import Profile


LIVE_PUBLIC_REST_BASE_URL = "https://fapi.binance.com"
TESTNET_PUBLIC_REST_BASE_URL = "https://demo-fapi.binance.com"
OBSERVATION_SCHEMA_VERSION = "NBOT_V3_MARKET_EVIDENCE_V1"
OBSERVATION_COLLECTOR_VERSION = "NBOT_V3_OBSERVER_EVIDENCE_V1"


@dataclass(frozen=True)
class ObservationConfig:
    """Non-secret V3.3 public-market evidence configuration.

    This configuration deliberately contains no order credentials, private
    account settings, research cost assumptions, model settings, or
    recommendation authority.
    """

    market_environment: str
    binance_public_base_url: str
    database_path: Path
    backup_directory: Path

    candle_interval: str = "5m"
    candle_interval_ms: int = 5 * 60 * 1000
    capture_settle_seconds: float = 4.0
    retry_seconds: float = 30.0

    observation_universe_size: int = 200
    min_quote_volume_24h_usd: float = 3_000_000.0
    max_spread_pct: float = 0.50

    request_timeout_seconds: float = 12.0
    candle_fetch_workers: int = 16
    max_server_clock_skew_ms: int = 5_000
    max_live_context_delay_ms: int = 30_000

    gap_recovery_enabled: bool = True
    gap_recovery_max_events_per_cycle: int = 24
    funding_sync_interval_seconds: int = 5 * 60

    schema_version: str = OBSERVATION_SCHEMA_VERSION
    collector_version: str = OBSERVATION_COLLECTOR_VERSION

    @property
    def canonical_live_research(self) -> bool:
        return self.market_environment == "LIVE"

    def validate(self) -> None:
        if self.market_environment not in {"LIVE", "TESTNET"}:
            raise ValueError("NBOT_OBSERVATION_MARKET_ENVIRONMENT_INVALID")
        expected_url = (
            LIVE_PUBLIC_REST_BASE_URL
            if self.market_environment == "LIVE"
            else TESTNET_PUBLIC_REST_BASE_URL
        )
        if self.binance_public_base_url != expected_url:
            raise ValueError("NBOT_OBSERVATION_PUBLIC_ENDPOINT_MISMATCH")
        expected_db = (
            Path("data/observation/live/observer.db")
            if self.market_environment == "LIVE"
            else Path("data/observation/testnet/observer.db")
        )
        if self.database_path != expected_db:
            raise ValueError("NBOT_OBSERVATION_DATABASE_PATH_MISMATCH")
        if self.backup_directory != expected_db.parent / "backups":
            raise ValueError("NBOT_OBSERVATION_BACKUP_PATH_MISMATCH")
        if self.candle_interval != "5m" or self.candle_interval_ms != 300_000:
            raise ValueError("NBOT_OBSERVATION_CANONICAL_CLOCK_INVALID")
        if self.capture_settle_seconds < 0:
            raise ValueError("NBOT_OBSERVATION_SETTLE_DELAY_INVALID")
        if self.retry_seconds <= 0:
            raise ValueError("NBOT_OBSERVATION_RETRY_DELAY_INVALID")
        if not 1 <= self.observation_universe_size <= 500:
            raise ValueError("NBOT_OBSERVATION_UNIVERSE_SIZE_INVALID")
        if self.min_quote_volume_24h_usd < 0:
            raise ValueError("NBOT_OBSERVATION_LIQUIDITY_THRESHOLD_INVALID")
        if not 0 < self.max_spread_pct <= 5:
            raise ValueError("NBOT_OBSERVATION_SPREAD_THRESHOLD_INVALID")
        if self.request_timeout_seconds <= 0:
            raise ValueError("NBOT_OBSERVATION_REQUEST_TIMEOUT_INVALID")
        if not 1 <= self.candle_fetch_workers <= 64:
            raise ValueError("NBOT_OBSERVATION_CANDLE_WORKERS_INVALID")
        if self.max_server_clock_skew_ms <= 0:
            raise ValueError("NBOT_OBSERVATION_CLOCK_SKEW_LIMIT_INVALID")
        if self.max_live_context_delay_ms <= 0:
            raise ValueError("NBOT_OBSERVATION_CONTEXT_DELAY_LIMIT_INVALID")
        if self.gap_recovery_max_events_per_cycle < 0:
            raise ValueError("NBOT_OBSERVATION_GAP_RECOVERY_LIMIT_INVALID")
        if self.funding_sync_interval_seconds <= 0:
            raise ValueError("NBOT_OBSERVATION_FUNDING_SYNC_INTERVAL_INVALID")
        if self.schema_version != OBSERVATION_SCHEMA_VERSION:
            raise ValueError("NBOT_OBSERVATION_SCHEMA_VERSION_INVALID")
        if self.collector_version != OBSERVATION_COLLECTOR_VERSION:
            raise ValueError("NBOT_OBSERVATION_COLLECTOR_VERSION_INVALID")


def observation_config_for_profile(profile: Profile) -> ObservationConfig:
    if profile.market_environment == "LIVE":
        base_url = LIVE_PUBLIC_REST_BASE_URL
    elif profile.market_environment == "TESTNET":
        base_url = TESTNET_PUBLIC_REST_BASE_URL
    else:
        raise ValueError("NBOT_OBSERVATION_PROFILE_ENVIRONMENT_INVALID")

    config = ObservationConfig(
        market_environment=profile.market_environment,
        binance_public_base_url=base_url,
        database_path=profile.observation_db,
        backup_directory=profile.observation_db.parent / "backups",
    )
    resource_profile = os.environ.get("NBOT_OBSERVATION_RESOURCE_PROFILE", "standard")
    if resource_profile not in {"standard", "tiny"}:
        raise ValueError("NBOT_OBSERVATION_RESOURCE_PROFILE_INVALID")
    if resource_profile == "tiny":
        config = replace(config, observation_universe_size=20, candle_fetch_workers=2,
                         gap_recovery_max_events_per_cycle=4)
    config.validate()
    return config
