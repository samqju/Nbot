"""NBOT V3 Observation evidence foundation.

V3.3 owns credential-free market evidence only. Recommendation, research,
learning, communication, and order authority are introduced only by later
canonical roadmap phases.
"""

from .binance_public import BinancePublicMarketError, BinanceUsdMPublicClient
from .config import ObservationConfig, observation_config_for_profile
from .database import EvidenceDatabase, EvidenceDatabaseError, FundingCoverage
from .models import Candle, FundingEvent, SourceCapture, UniverseCapture, UniverseRow
from .observer import (
    CanonicalCollectionClock,
    CollectionResult,
    FundingSyncResult,
    GapRecoveryResult,
    MarketEvidenceCollector,
    ObservationCollectionError,
    ObservationCollectionNotReady,
    latest_completed_open_time_ms,
)
from .public_market import PublicMarketClient

__all__ = [
    "BinancePublicMarketError",
    "BinanceUsdMPublicClient",
    "Candle",
    "CanonicalCollectionClock",
    "CollectionResult",
    "EvidenceDatabase",
    "EvidenceDatabaseError",
    "FundingCoverage",
    "FundingEvent",
    "FundingSyncResult",
    "GapRecoveryResult",
    "MarketEvidenceCollector",
    "ObservationCollectionError",
    "ObservationCollectionNotReady",
    "ObservationConfig",
    "PublicMarketClient",
    "SourceCapture",
    "UniverseCapture",
    "UniverseRow",
    "latest_completed_open_time_ms",
    "observation_config_for_profile",
]