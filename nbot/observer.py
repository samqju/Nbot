from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .binance import BinancePublicClient, latest_closed_open_time_ms
from .config import ObserverConfig
from .db import EvidenceDB


LOG = logging.getLogger("nbot.v2.observer")


@dataclass(frozen=True)
class CollectionResult:
    event_open_ms: int
    requested_symbols: int
    stored_symbols: int
    errors: int
    status: str
    skipped: bool
    capture_duration_ms: int


class MarketEvidenceObserver:
    def __init__(self, config: ObserverConfig, client: BinancePublicClient, db: EvidenceDB):
        self.config = config
        self.client = client
        self.db = db

    def collect_once(self) -> CollectionResult:
        started = time.monotonic()
        server_time_ms = self.client.server_time_ms()
        event_open_ms = latest_closed_open_time_ms(server_time_ms, self.config.candle_interval_ms)
        event_close_ms = event_open_ms + self.config.candle_interval_ms - 1

        if self.db.has_complete_event(event_open_ms):
            return CollectionResult(event_open_ms, 0, 0, 0, "COMPLETE", True, 0)

        universe = self.client.eligible_universe()
        if not universe:
            raise RuntimeError("eligible universe is empty")

        symbols = [row.symbol for row in universe]
        candles, errors = self.client.closed_candles(symbols, event_open_ms)
        captured_at_ms = self.client.now_ms()
        duration_ms = int((time.monotonic() - started) * 1000)
        status = self.db.store_event(
            event_open_ms=event_open_ms,
            event_close_ms=event_close_ms,
            captured_at_ms=captured_at_ms,
            requested_symbols=len(symbols),
            universe_rows=universe,
            candles=candles,
            error_count=len(errors),
            capture_duration_ms=duration_ms,
        )
        result = CollectionResult(
            event_open_ms=event_open_ms,
            requested_symbols=len(symbols),
            stored_symbols=len(candles),
            errors=len(errors),
            status=status,
            skipped=False,
            capture_duration_ms=duration_ms,
        )
        LOG.info(
            "MARKET_EVENT_%s event_open_ms=%s requested=%s stored=%s errors=%s duration_ms=%s",
            status,
            result.event_open_ms,
            result.requested_symbols,
            result.stored_symbols,
            result.errors,
            result.capture_duration_ms,
        )
        if errors:
            sample = list(sorted(errors.items()))[:5]
            LOG.warning("MARKET_EVENT_ERRORS sample=%s", sample)
        return result

    def seconds_until_next_collection(self) -> float:
        server_time_ms = self.client.server_time_ms()
        next_boundary_ms = ((server_time_ms // self.config.candle_interval_ms) + 1) * self.config.candle_interval_ms
        target_ms = next_boundary_ms + int(self.config.capture_settle_seconds * 1000)
        return max(1.0, (target_ms - server_time_ms) / 1000.0)

    def run_forever(self) -> None:
        self.db.initialize()
        LOG.info(
            "NBOT_V2_OBSERVER_READY role=%s market=%s database=%s universe_target=%s",
            self.config.role,
            self.config.market_environment,
            self.config.database_path,
            self.config.observation_universe_size,
        )
        while True:
            try:
                self.collect_once()
                time.sleep(self.seconds_until_next_collection())
            except KeyboardInterrupt:
                raise
            except Exception:
                LOG.exception("NBOT_V2_COLLECTION_FAILURE")
                time.sleep(self.config.retry_seconds)
