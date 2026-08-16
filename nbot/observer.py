from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass

from .binance import BinancePublicClient, UniverseCapture, latest_closed_open_time_ms
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
        started_monotonic = time.monotonic()
        capture_started_at_ms = self.client.now_ms()
        server_time_before_ms = self.client.server_time_ms()
        if abs(capture_started_at_ms - server_time_before_ms) > self.config.max_server_clock_skew_ms:
            raise RuntimeError(
                f"local/Binance clock skew exceeds {self.config.max_server_clock_skew_ms} ms"
            )
        event_open_ms = latest_closed_open_time_ms(server_time_before_ms, self.config.candle_interval_ms)
        event_close_ms = event_open_ms + self.config.candle_interval_ms - 1

        if self.db.has_complete_event(event_open_ms):
            return CollectionResult(event_open_ms, 0, 0, 0, "COMPLETE", True, 0)

        universe_capture: UniverseCapture = self.client.eligible_universe_capture()
        universe = list(universe_capture.rows)
        if not universe:
            raise RuntimeError("eligible universe is empty")

        symbols = [row.symbol for row in universe]
        context_captured_at_ms = max(
            (capture.finished_at_ms for capture in universe_capture.source_captures),
            default=self.client.now_ms(),
        )
        context_delay_ms = context_captured_at_ms - event_close_ms
        if context_delay_ms > self.config.max_live_context_delay_ms:
            candles = {}
            errors = {
                "__LATE_CONTEXT__": (
                    f"point-in-time context arrived {context_delay_ms} ms after candle close; "
                    f"limit={self.config.max_live_context_delay_ms} ms"
                )
            }
        else:
            candles, errors = self.client.closed_candles(symbols, event_open_ms)
        server_time_after_ms = self.client.server_time_ms()
        captured_at_ms = self.client.now_ms()
        duration_ms = int((time.monotonic() - started_monotonic) * 1000)
        if abs(captured_at_ms - server_time_after_ms) > self.config.max_server_clock_skew_ms:
            errors["__CLOCK_SKEW__"] = (
                f"local/Binance final clock skew exceeds {self.config.max_server_clock_skew_ms} ms"
            )

        if event_close_ms >= server_time_after_ms:
            errors["__EVENT_TIME__"] = "event candle was not closed according to final Binance server time"

        status = self.db.store_event(
            event_open_ms=event_open_ms,
            event_close_ms=event_close_ms,
            captured_at_ms=captured_at_ms,
            capture_started_at_ms=capture_started_at_ms,
            server_time_before_ms=server_time_before_ms,
            server_time_after_ms=server_time_after_ms,
            source_captures=universe_capture.source_captures,
            requested_symbols=len(symbols),
            universe_rows=universe,
            candles=candles,
            error_count=len(errors),
            capture_duration_ms=duration_ms,
            failure_detail="; ".join(f"{key}={value}" for key, value in sorted(errors.items())) or None,
        )
        result = CollectionResult(
            event_open_ms=event_open_ms,
            requested_symbols=len(symbols),
            stored_symbols=len(candles) if status == "COMPLETE" else 0,
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

    def recover_gaps(self, max_events: int | None = None) -> dict[str, int]:
        if not self.config.gap_recovery_enabled:
            return {"missing": 0, "attempted": 0, "recovered": 0, "failed": 0, "unrecoverable": 0}

        server_time_ms = self.client.server_time_ms()
        latest_open_ms = latest_closed_open_time_ms(server_time_ms, self.config.candle_interval_ms)
        missing = self.db.missing_event_opens(latest_open_ms)
        limit = self.config.gap_recovery_max_events_per_cycle if max_events is None else max(0, int(max_events))
        selected = missing[:limit]
        if not selected:
            return {"missing": len(missing), "attempted": 0, "recovered": 0, "failed": 0, "unrecoverable": 0}

        groups: dict[tuple[int, tuple[tuple[str, int], ...]], list[int]] = defaultdict(list)
        unrecoverable = 0
        for event_open_ms in selected:
            source = self.db.point_in_time_universe_before(event_open_ms)
            if source is None:
                unrecoverable += 1
                continue
            source_event_open_ms, membership = source
            groups[(source_event_open_ms, tuple(membership))].append(event_open_ms)

        recovered = 0
        failed = 0
        attempted = 0
        for (source_event_open_ms, membership_tuple), event_opens in groups.items():
            membership = list(membership_tuple)
            symbols = [symbol for symbol, _ in membership]
            group_started = time.monotonic()
            history, errors = self.client.historical_candles_for_symbols(symbols, event_opens)
            for event_open_ms in event_opens:
                attempted += 1
                event_candles = {
                    symbol: rows[event_open_ms]
                    for symbol, rows in history.items()
                    if event_open_ms in rows
                }
                duration_ms = int((time.monotonic() - group_started) * 1000)
                status = self.db.store_recovered_event(
                    event_open_ms=event_open_ms,
                    source_universe_event_open_ms=source_event_open_ms,
                    membership=membership,
                    candles=event_candles,
                    captured_at_ms=self.client.now_ms(),
                    capture_duration_ms=duration_ms,
                    recovery_reason=(
                        "Observer downtime/gap: canonical candles recovered; "
                        "historical spread, 24h ranking and premium-index context intentionally not fabricated"
                    ),
                )
                if status == "COMPLETE":
                    recovered += 1
                    LOG.info(
                        "MARKET_EVENT_RECOVERED event_open_ms=%s source_universe_event_open_ms=%s symbols=%s",
                        event_open_ms,
                        source_event_open_ms,
                        len(event_candles),
                    )
                else:
                    failed += 1
                    LOG.warning(
                        "MARKET_EVENT_RECOVERY_FAILED event_open_ms=%s source=%s candle_errors=%s",
                        event_open_ms,
                        source_event_open_ms,
                        len(errors),
                    )

        return {
            "missing": len(missing),
            "attempted": attempted,
            "recovered": recovered,
            "failed": failed,
            "unrecoverable": unrecoverable,
        }

    def sync_funding_history(self, *, force: bool = False) -> dict[str, int | bool]:
        now_ms = self.client.now_ms()
        if not force and not self.db.funding_sync_due(now_ms):
            return {"skipped": True, "rows": 0, "start_ms": 0, "end_ms": 0}
        start_ms = self.db.funding_sync_start_ms()
        if start_ms is None:
            return {"skipped": True, "rows": 0, "start_ms": 0, "end_ms": 0}
        end_ms = self.client.server_time_ms()
        if start_ms > end_ms:
            return {"skipped": True, "rows": 0, "start_ms": start_ms, "end_ms": end_ms}
        events = self.client.funding_history(start_ms, end_ms)
        rows = self.db.store_funding_sync(
            start_ms=start_ms,
            end_ms=end_ms,
            events=events,
            captured_at_ms=self.client.now_ms(),
        )
        LOG.info("FUNDING_HISTORY_SYNC start_ms=%s end_ms=%s rows=%s", start_ms, end_ms, rows)
        return {"skipped": False, "rows": rows, "start_ms": start_ms, "end_ms": end_ms}

    def seconds_until_next_collection(self) -> float:
        server_time_ms = self.client.server_time_ms()
        next_boundary_ms = ((server_time_ms // self.config.candle_interval_ms) + 1) * self.config.candle_interval_ms
        target_ms = next_boundary_ms + int(self.config.capture_settle_seconds * 1000)
        return max(1.0, (target_ms - server_time_ms) / 1000.0)

    def run_forever(self) -> None:
        self.db.initialize()
        LOG.info(
            "NBOT_V2_OBSERVER_READY role=%s market=%s database=%s universe_target=%s schema=%s",
            self.config.role,
            self.config.market_environment,
            self.config.database_path,
            self.config.observation_universe_size,
            self.config.schema_version,
        )
        while True:
            try:
                result = self.collect_once()
                if result.status == "COMPLETE":
                    recovery = self.recover_gaps()
                    if recovery["attempted"] or recovery["unrecoverable"]:
                        LOG.info("GAP_RECOVERY %s", recovery)
                    self.sync_funding_history(force=False)
                time.sleep(self.seconds_until_next_collection())
            except KeyboardInterrupt:
                raise
            except Exception:
                LOG.exception("NBOT_V2_COLLECTION_FAILURE")
                time.sleep(self.config.retry_seconds)
