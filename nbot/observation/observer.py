"""Canonical completed-5m Observation collection for NBOT V3.3.

This module coordinates only point-in-time public market capture.  It does not
run research, recommendations, communication, or order logic.  Funding-history synchronization, database audits, and the long-running worker
are added by later V3.3 patches.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .config import ObservationConfig
from .database import EvidenceDatabase
from .models import UniverseCapture
from .public_market import PublicMarketClient


class ObservationCollectionError(RuntimeError):
    """A live evidence collection cycle could not be trusted."""


class ObservationCollectionNotReady(ObservationCollectionError):
    """The latest closed candle has not yet passed the configured settle delay."""

    def __init__(self, wait_ms: int) -> None:
        self.wait_ms = max(0, int(wait_ms))
        super().__init__(f"NBOT_OBSERVATION_COLLECTION_NOT_READY:wait_ms={self.wait_ms}")


def latest_completed_open_time_ms(server_time_ms: int, interval_ms: int = 300_000) -> int:
    """Return the open time of the latest fully closed interval."""

    server_time = int(server_time_ms)
    interval = int(interval_ms)
    if interval <= 0:
        raise ValueError("NBOT_OBSERVATION_CLOCK_INTERVAL_INVALID")
    if server_time < interval:
        raise ValueError("NBOT_OBSERVATION_SERVER_TIME_TOO_EARLY")
    return ((server_time // interval) - 1) * interval


@dataclass(frozen=True)
class CanonicalCollectionClock:
    """Server-time-aware completed-candle clock with an explicit settle delay."""

    interval_ms: int = 300_000
    settle_delay_ms: int = 4_000

    def __post_init__(self) -> None:
        if self.interval_ms <= 0:
            raise ValueError("NBOT_OBSERVATION_CLOCK_INTERVAL_INVALID")
        if self.settle_delay_ms < 0:
            raise ValueError("NBOT_OBSERVATION_SETTLE_DELAY_INVALID")

    @classmethod
    def from_config(cls, config: ObservationConfig) -> "CanonicalCollectionClock":
        config.validate()
        return cls(
            interval_ms=config.candle_interval_ms,
            settle_delay_ms=int(config.capture_settle_seconds * 1000),
        )

    def event_open_ms(self, server_time_ms: int) -> int:
        event_open = latest_completed_open_time_ms(server_time_ms, self.interval_ms)
        ready_at_ms = event_open + self.interval_ms + self.settle_delay_ms
        if int(server_time_ms) < ready_at_ms:
            raise ObservationCollectionNotReady(ready_at_ms - int(server_time_ms))
        return event_open

    def seconds_until_next_collection(self, server_time_ms: int) -> float:
        server_time = int(server_time_ms)
        if server_time < 0:
            raise ValueError("NBOT_OBSERVATION_SERVER_TIME_INVALID")
        boundary = (server_time // self.interval_ms) * self.interval_ms
        current_target = boundary + self.settle_delay_ms
        if server_time < current_target:
            target = current_target
        else:
            target = boundary + self.interval_ms + self.settle_delay_ms
        return max(0.0, (target - server_time) / 1000.0)


@dataclass(frozen=True)
class CollectionResult:
    event_open_ms: int
    requested_symbols: int
    stored_symbols: int
    errors: int
    status: str
    skipped: bool
    capture_duration_ms: int
    context_delay_ms: int | None
    clock_skew_before_ms: int
    clock_skew_after_ms: int | None


@dataclass(frozen=True)
class GapRecoveryResult:
    missing: int
    selected: int
    attempted: int
    recovered: int
    failed: int
    unrecoverable: int


class MarketEvidenceCollector:
    """Capture one canonical point-in-time market event at a time."""

    def __init__(
        self,
        config: ObservationConfig,
        client: PublicMarketClient,
        database: EvidenceDatabase,
    ) -> None:
        config.validate()
        self.config = config
        self.client = client
        self.database = database
        self.clock = CanonicalCollectionClock.from_config(config)

    def seconds_until_next_collection(self) -> float:
        return self.clock.seconds_until_next_collection(self.client.server_time_ms())

    def _record_capture_failure(
        self,
        *,
        event_open_ms: int,
        capture_started_at_ms: int,
        requested_symbols: int,
        captured_symbols: int,
        error_count: int,
        exc: Exception,
    ) -> None:
        try:
            finished = max(capture_started_at_ms, int(self.client.local_time_ms()))
        except Exception:
            finished = capture_started_at_ms
        self.database.record_collection_attempt(
            event_open_ms=event_open_ms,
            attempted_at_ms=finished,
            requested_symbols=requested_symbols,
            stored_symbols=captured_symbols,
            error_count=max(1, error_count),
            result="CAPTURE_FAILED",
            capture_duration_ms=max(0, finished - capture_started_at_ms),
            detail=f"{type(exc).__name__}: {exc}",
        )

    def latest_recovery_open_ms(self, server_time_ms: int) -> int | None:
        """Return the latest event old enough for honest historical recovery."""

        adjusted = int(server_time_ms) - self.clock.settle_delay_ms
        if adjusted < self.config.candle_interval_ms:
            return None
        return latest_completed_open_time_ms(adjusted, self.config.candle_interval_ms)

    def recover_gaps(self, max_events: int | None = None) -> GapRecoveryResult:
        """Recover candle-only gaps using prior observed universe membership.

        Historical point-in-time spread, liquidity, premium-index, or ranking
        context is never requested or fabricated here. Recovered events remain
        context-incomplete in the database by construction.
        """

        if not self.config.gap_recovery_enabled:
            return GapRecoveryResult(0, 0, 0, 0, 0, 0)

        server_time_ms = int(self.client.server_time_ms())
        latest_open_ms = self.latest_recovery_open_ms(server_time_ms)
        if latest_open_ms is None:
            return GapRecoveryResult(0, 0, 0, 0, 0, 0)

        missing = self.database.missing_event_opens(latest_open_ms)
        limit = (
            self.config.gap_recovery_max_events_per_cycle
            if max_events is None
            else max(0, int(max_events))
        )
        selected = missing[:limit]
        if not selected:
            return GapRecoveryResult(len(missing), 0, 0, 0, 0, 0)

        groups: dict[tuple[int, tuple[tuple[str, int], ...]], list[int]] = defaultdict(list)
        unrecoverable = 0
        for event_open_ms in selected:
            source = self.database.point_in_time_universe_before(event_open_ms)
            if source is None:
                unrecoverable += 1
                attempted_at_ms = max(0, int(self.client.local_time_ms()))
                self.database.record_collection_attempt(
                    event_open_ms=event_open_ms,
                    attempted_at_ms=attempted_at_ms,
                    requested_symbols=0,
                    stored_symbols=0,
                    error_count=1,
                    result="RECOVERY_UNRECOVERABLE",
                    capture_duration_ms=0,
                    detail=(
                        "no prior context-complete point-in-time universe exists; "
                        "historical membership/context not fabricated"
                    ),
                )
                continue
            source_event_open_ms, membership = source
            groups[(source_event_open_ms, membership)].append(event_open_ms)

        attempted = 0
        recovered = 0
        failed = 0
        recovery_reason = (
            "Observer gap: canonical candles recovered using inherited prior "
            "point-in-time universe membership; historical spread, 24h liquidity, "
            "ranking and premium-index context intentionally not fabricated"
        )

        for (source_event_open_ms, membership), event_opens in groups.items():
            symbols = tuple(symbol for symbol, _rank in membership)
            group_started_at_ms = max(0, int(self.client.local_time_ms()))
            try:
                history, errors = self.client.historical_candles_for_symbols(
                    symbols, tuple(event_opens)
                )
            except Exception as exc:
                group_finished_at_ms = max(
                    group_started_at_ms, int(self.client.local_time_ms())
                )
                duration_ms = group_finished_at_ms - group_started_at_ms
                for event_open_ms in event_opens:
                    attempted += 1
                    failed += 1
                    self.database.record_collection_attempt(
                        event_open_ms=event_open_ms,
                        attempted_at_ms=group_finished_at_ms,
                        requested_symbols=len(symbols),
                        stored_symbols=0,
                        error_count=max(1, len(symbols)),
                        result="RECOVERY_FETCH_FAILED",
                        capture_duration_ms=duration_ms,
                        detail=f"{type(exc).__name__}: {exc}",
                    )
                continue

            group_finished_at_ms = max(
                group_started_at_ms, int(self.client.local_time_ms())
            )
            duration_ms = group_finished_at_ms - group_started_at_ms
            error_map = {str(key): str(value) for key, value in errors.items()}
            for event_open_ms in event_opens:
                attempted += 1
                event_candles = {
                    symbol: rows[event_open_ms]
                    for symbol, rows in history.items()
                    if event_open_ms in rows
                }
                status = self.database.store_recovered_event(
                    event_open_ms=event_open_ms,
                    source_universe_event_open_ms=source_event_open_ms,
                    membership=membership,
                    candles=event_candles,
                    candle_errors=error_map,
                    captured_at_ms=group_finished_at_ms,
                    capture_duration_ms=duration_ms,
                    recovery_reason=recovery_reason,
                )
                if status == "COMPLETE":
                    recovered += 1
                elif status != "ALREADY_COMPLETE":
                    failed += 1

        return GapRecoveryResult(
            missing=len(missing),
            selected=len(selected),
            attempted=attempted,
            recovered=recovered,
            failed=failed,
            unrecoverable=unrecoverable,
        )

    def collect_once(self) -> CollectionResult:
        capture_started_at_ms = int(self.client.local_time_ms())
        server_time_before_ms = int(self.client.server_time_ms())
        clock_skew_before_ms = abs(capture_started_at_ms - server_time_before_ms)
        if clock_skew_before_ms > self.config.max_server_clock_skew_ms:
            raise ObservationCollectionError(
                "NBOT_OBSERVATION_CLOCK_SKEW_BEFORE_CAPTURE:"
                f"skew_ms={clock_skew_before_ms}:"
                f"limit_ms={self.config.max_server_clock_skew_ms}"
            )

        event_open_ms = self.clock.event_open_ms(server_time_before_ms)
        event_close_ms = event_open_ms + self.config.candle_interval_ms - 1

        if self.database.has_complete_event(event_open_ms):
            return CollectionResult(
                event_open_ms=event_open_ms,
                requested_symbols=0,
                stored_symbols=0,
                errors=0,
                status="ALREADY_COMPLETE",
                skipped=True,
                capture_duration_ms=0,
                context_delay_ms=None,
                clock_skew_before_ms=clock_skew_before_ms,
                clock_skew_after_ms=None,
            )

        requested_symbols = 0
        captured_symbols = 0
        errors: dict[str, str] = {}
        context_delay_ms: int | None = None

        try:
            universe_capture: UniverseCapture = self.client.eligible_universe_capture()
            requested_symbols = len(universe_capture.rows)
            if requested_symbols == 0:
                errors["__EMPTY_UNIVERSE__"] = "point-in-time eligible universe is empty"

            if universe_capture.source_captures:
                context_captured_at_ms = max(
                    capture.finished_at_ms for capture in universe_capture.source_captures
                )
                context_delay_ms = context_captured_at_ms - event_close_ms
                if context_delay_ms > self.config.max_live_context_delay_ms:
                    errors["__LATE_CONTEXT__"] = (
                        f"point-in-time context delay {context_delay_ms} ms exceeds "
                        f"limit {self.config.max_live_context_delay_ms} ms"
                    )

            candles = {}
            if not errors:
                symbols = tuple(row.symbol for row in universe_capture.rows)
                candles_raw, candle_errors = self.client.closed_candles(symbols, event_open_ms)
                candles = dict(candles_raw)
                errors.update({str(key): str(value) for key, value in candle_errors.items()})
                captured_symbols = len(candles)

            server_time_after_ms = int(self.client.server_time_ms())
            capture_finished_at_ms = int(self.client.local_time_ms())
            clock_skew_after_ms = abs(capture_finished_at_ms - server_time_after_ms)

            if server_time_after_ms < server_time_before_ms:
                errors["__SERVER_TIME_REGRESSION__"] = (
                    f"server time regressed from {server_time_before_ms} to {server_time_after_ms}"
                )
            if clock_skew_after_ms > self.config.max_server_clock_skew_ms:
                errors["__CLOCK_SKEW_AFTER__"] = (
                    f"final local/Binance skew {clock_skew_after_ms} ms exceeds "
                    f"limit {self.config.max_server_clock_skew_ms} ms"
                )
            if event_close_ms >= server_time_after_ms:
                errors["__EVENT_NOT_CLOSED__"] = (
                    "event candle is not closed according to final Binance server time"
                )
        except Exception as exc:
            self._record_capture_failure(
                event_open_ms=event_open_ms,
                capture_started_at_ms=capture_started_at_ms,
                requested_symbols=requested_symbols,
                captured_symbols=captured_symbols,
                error_count=len(errors),
                exc=exc,
            )
            raise ObservationCollectionError(
                f"NBOT_OBSERVATION_CAPTURE_FAILED:{type(exc).__name__}:{exc}"
            ) from exc

        status = self.database.store_live_event(
            event_open_ms=event_open_ms,
            universe_capture=universe_capture,
            candles=candles,
            candle_errors=errors,
            capture_started_at_ms=capture_started_at_ms,
            capture_finished_at_ms=capture_finished_at_ms,
            server_time_before_ms=server_time_before_ms,
            server_time_after_ms=server_time_after_ms,
        )

        return CollectionResult(
            event_open_ms=event_open_ms,
            requested_symbols=requested_symbols,
            stored_symbols=captured_symbols if status == "COMPLETE" else 0,
            errors=len(errors),
            status=status,
            skipped=False,
            capture_duration_ms=max(0, capture_finished_at_ms - capture_started_at_ms),
            context_delay_ms=context_delay_ms,
            clock_skew_before_ms=clock_skew_before_ms,
            clock_skew_after_ms=clock_skew_after_ms,
        )
