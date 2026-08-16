from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ObserverConfig:
    """Version-controlled, non-secret V2.1 Observation configuration."""

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
    max_server_clock_skew_ms: int = 5_000
    max_live_context_delay_ms: int = 30_000

    database_path: Path = Path("data/observer.db")
    backup_directory: Path = Path("data/backups")
    schema_version: str = "NBOT_V2_MARKET_EVIDENCE_V2_6"
    collector_version: str = "NBOT_V2_OBSERVER_EVIDENCE_V2_1"

    # Recovery never fabricates historical live spread/volume context. It may
    # recover canonical candles using the most recent preceding point-in-time
    # universe only, and marks those events as context-incomplete.
    gap_recovery_enabled: bool = True
    gap_recovery_max_events_per_cycle: int = 24

    # Exact funding history is synced independently from current premium-index
    # context. The public funding endpoint is timestamped and therefore safe to
    # ingest retrospectively.
    funding_sync_interval_seconds: int = 5 * 60

    # Stored now so every later simulation uses one explicit cost contract.
    taker_fee_rate: float = 0.0005
    entry_slippage_bps: float = 2.0
    exit_slippage_bps: float = 2.0

    def validate(self) -> None:
        if self.role != "OBSERVER_RESEARCH":
            raise ValueError("V2.1 permits only OBSERVER_RESEARCH")
        if self.market_environment != "LIVE_PUBLIC":
            raise ValueError("V2.1 collects only LIVE public market evidence")
        if self.binance_base_url != "https://fapi.binance.com":
            raise ValueError("V2.1 Binance base URL must be the LIVE USD-M public endpoint")
        if self.candle_interval != "5m" or self.candle_interval_ms != 300_000:
            raise ValueError("V2.1 decision clock is fixed to completed 5-minute candles")
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
        if self.max_server_clock_skew_ms <= 0:
            raise ValueError("max_server_clock_skew_ms must be positive")
        if self.max_live_context_delay_ms <= 0:
            raise ValueError("max_live_context_delay_ms must be positive")
        if self.gap_recovery_max_events_per_cycle < 0:
            raise ValueError("gap_recovery_max_events_per_cycle must be non-negative")
        if self.funding_sync_interval_seconds <= 0:
            raise ValueError("funding_sync_interval_seconds must be positive")
        if self.taker_fee_rate < 0 or self.entry_slippage_bps < 0 or self.exit_slippage_bps < 0:
            raise ValueError("cost assumptions must be non-negative")


@dataclass(frozen=True)
class ResearchConfig:
    """Version-controlled V2.2 canonical feature and signal definitions."""

    feature_version: str = "CANONICAL_FEATURES_V1"
    return_lookback_bars: tuple[int, ...] = (1, 3, 6, 12, 24, 48)
    realized_vol_1h_bars: int = 12
    realized_vol_4h_bars: int = 48
    atr_bars: int = 14
    max_history_bars: int = 48
    max_events_per_build: int = 500

    csm_active_abs_score: float = 0.60
    tsmom_active_abs_score: float = 0.50

    intraday_directional_breadth_high: float = 0.65
    intraday_directional_breadth_low: float = 0.35
    intraday_balanced_breadth_low: float = 0.45
    intraday_balanced_breadth_high: float = 0.55
    intraday_momentum_percentile: float = 0.65
    intraday_reversal_percentile: float = 0.90

    def validate(self) -> None:
        if self.feature_version != "CANONICAL_FEATURES_V1":
            raise ValueError("V2.2 initial feature version is frozen as CANONICAL_FEATURES_V1")
        if self.return_lookback_bars != (1, 3, 6, 12, 24, 48):
            raise ValueError("V2.2 return lookbacks are frozen")
        if self.max_history_bars < max(self.return_lookback_bars):
            raise ValueError("max_history_bars must cover all return lookbacks")
        if self.realized_vol_4h_bars > self.max_history_bars:
            raise ValueError("4h volatility lookback exceeds max history")
        if self.atr_bars <= 0 or self.realized_vol_1h_bars <= 0:
            raise ValueError("volatility lookbacks must be positive")
        if self.max_events_per_build <= 0:
            raise ValueError("max_events_per_build must be positive")
        for name, value in (
            ("csm_active_abs_score", self.csm_active_abs_score),
            ("tsmom_active_abs_score", self.tsmom_active_abs_score),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        for name, value in (
            ("intraday_directional_breadth_high", self.intraday_directional_breadth_high),
            ("intraday_directional_breadth_low", self.intraday_directional_breadth_low),
            ("intraday_balanced_breadth_low", self.intraday_balanced_breadth_low),
            ("intraday_balanced_breadth_high", self.intraday_balanced_breadth_high),
            ("intraday_momentum_percentile", self.intraday_momentum_percentile),
            ("intraday_reversal_percentile", self.intraday_reversal_percentile),
        ):
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if not self.intraday_directional_breadth_low < self.intraday_directional_breadth_high:
            raise ValueError("directional breadth bounds are invalid")
        if not self.intraday_balanced_breadth_low <= self.intraday_balanced_breadth_high:
            raise ValueError("balanced breadth bounds are invalid")


@dataclass(frozen=True)
class OutcomeConfig:
    """Version-controlled V2.3 future-path / outcome definition."""

    outcome_version: str = "FUTURE_PATH_4H_V1"
    feature_version: str = "CANONICAL_FEATURES_V1"
    forward_horizon_bars: tuple[int, ...] = (1, 3, 6, 12, 24, 48)
    max_horizon_bars: int = 48
    risk_unit_version: str = "ATR14_1X_RESEARCH_R_V1"
    barrier_r_multiples: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0)
    cost_version: str = "TAKER_SPREAD_SLIPPAGE_FUNDING_PROXY_V1"
    max_events_per_build: int = 100

    def validate(self) -> None:
        if self.outcome_version != "FUTURE_PATH_4H_V1":
            raise ValueError("V2.3 initial outcome version is frozen as FUTURE_PATH_4H_V1")
        if self.feature_version != "CANONICAL_FEATURES_V1":
            raise ValueError("V2.3 is tied to CANONICAL_FEATURES_V1")
        if self.forward_horizon_bars != (1, 3, 6, 12, 24, 48):
            raise ValueError("V2.3 forward horizons are frozen")
        if self.max_horizon_bars != max(self.forward_horizon_bars):
            raise ValueError("max_horizon_bars must equal the largest frozen horizon")
        if self.barrier_r_multiples != (0.5, 1.0, 2.0, 3.0):
            raise ValueError("V2.3 R barriers are frozen")
        if self.max_events_per_build <= 0:
            raise ValueError("max_events_per_build must be positive")


@dataclass(frozen=True)
class PolicyConfig:
    """Version-controlled V2.4 exit-policy laboratory definition."""

    lab_version: str = "EXIT_POLICY_LAB_V1"
    feature_version: str = "CANONICAL_FEATURES_V1"
    outcome_version: str = "FUTURE_PATH_4H_V1"
    risk_unit_version: str = "ATR14_1X_RESEARCH_R_V1"
    max_horizon_bars: int = 48
    max_events_per_build: int = 50

    def validate(self) -> None:
        if self.lab_version != "EXIT_POLICY_LAB_V1":
            raise ValueError("V2.4 initial lab version is frozen as EXIT_POLICY_LAB_V1")
        if self.feature_version != "CANONICAL_FEATURES_V1":
            raise ValueError("V2.4 is tied to CANONICAL_FEATURES_V1")
        if self.outcome_version != "FUTURE_PATH_4H_V1":
            raise ValueError("V2.4 is tied to FUTURE_PATH_4H_V1")
        if self.risk_unit_version != "ATR14_1X_RESEARCH_R_V1":
            raise ValueError("V2.4 is tied to the V2.3 ATR14 research risk unit")
        if self.max_horizon_bars != 48:
            raise ValueError("V2.4 initial policy horizon is frozen at 48 bars")
        if self.max_events_per_build <= 0:
            raise ValueError("max_events_per_build must be positive")



CONFIG = ObserverConfig()
CONFIG.validate()
RESEARCH_CONFIG = ResearchConfig()
RESEARCH_CONFIG.validate()
OUTCOME_CONFIG = OutcomeConfig()
OUTCOME_CONFIG.validate()
POLICY_CONFIG = PolicyConfig()
POLICY_CONFIG.validate()
