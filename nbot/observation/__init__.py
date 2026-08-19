"""NBOT V3 Observation evidence foundation.

V3.3 owns credential-free market evidence only. Recommendation, research,
learning, communication, and order authority are introduced only by later
canonical roadmap phases.
"""

from .binance_public import BinancePublicMarketError, BinanceUsdMPublicClient
from .config import ObservationConfig, observation_config_for_profile
from .database import EvidenceDatabase, EvidenceDatabaseError
from .models import Candle, FundingEvent, SourceCapture, UniverseCapture, UniverseRow
from .public_market import PublicMarketClient

__all__ = [
    "BinancePublicMarketError",
    "BinanceUsdMPublicClient",
    "Candle",
    "EvidenceDatabase",
    "EvidenceDatabaseError",
    "FundingEvent",
    "ObservationConfig",
    "PublicMarketClient",
    "SourceCapture",
    "UniverseCapture",
    "UniverseRow",
    "observation_config_for_profile",
]
