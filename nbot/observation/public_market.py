from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol, runtime_checkable

from .models import Candle, FundingEvent, UniverseCapture


@runtime_checkable
class PublicMarketClient(Protocol):
    """Credential-free market-data boundary for the V3 Observation worker."""

    def server_time_ms(self) -> int:
        """Return authoritative Binance/server time in milliseconds."""
        ...

    def local_time_ms(self) -> int:
        """Return local wall-clock time in milliseconds for capture provenance."""
        ...

    def eligible_universe_capture(self) -> UniverseCapture:
        """Capture the deterministic point-in-time eligible universe context."""
        ...

    def closed_candles(
        self,
        symbols: Iterable[str],
        open_time_ms: int,
    ) -> tuple[Mapping[str, Candle], Mapping[str, str]]:
        """Return canonical candles and explicit per-symbol errors for one event."""
        ...

    def historical_candles_for_symbols(
        self,
        symbols: Iterable[str],
        open_times_ms: Iterable[int],
    ) -> tuple[Mapping[str, Mapping[int, Candle]], Mapping[str, str]]:
        """Return objectively recoverable historical candles and explicit errors."""
        ...

    def funding_history(
        self,
        start_time_ms: int,
        end_time_ms: int,
    ) -> Iterable[FundingEvent]:
        """Return timestamped historical funding events for an auditable range."""
        ...
