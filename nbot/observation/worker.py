"""Long-running credential-free Observation evidence runtime for NBOT V3.3.

The worker only orchestrates already-proven raw-evidence operations:

* capture the latest settled completed 5-minute event;
* retry a fresh partial event before allowing historical degradation;
* recover older candle gaps without fabricating point-in-time context;
* synchronize objective funding history;
* keep LIVE and TESTNET runtime locks physically separate.

Research, recommendation, communication, and order authority are intentionally
absent from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Callable, Mapping

from .binance_public import BinancePublicMarketError
from .config import ObservationConfig
from .database import EvidenceDatabase, EvidenceDatabaseError
from .observer import (
    CollectionResult,
    FundingSyncResult,
    GapRecoveryResult,
    MarketEvidenceCollector,
    ObservationCollectionError,
    ObservationCollectionNotReady,
)
from .public_market import PublicMarketClient


class ObservationRuntimeError(RuntimeError):
    """Observation runtime cannot continue safely."""


class ObservationRuntimeAlreadyRunning(ObservationRuntimeError):
    """Another Observation process already owns this environment runtime."""


@dataclass(frozen=True)
class ObservationCycleResult:
    collection: CollectionResult
    gap_recovery: GapRecoveryResult | None
    funding_sync: FundingSyncResult | None
    retry_fresh_event: bool


class ObservationRuntimeLock:
    """Advisory single-instance lock scoped to one market environment."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ObservationRuntimeAlreadyRunning(
                f"NBOT_OBSERVATION_RUNTIME_LOCK_HELD:{self.path}"
            ) from exc
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> "ObservationRuntimeLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()


def observation_runtime_lock_path(repo_root: Path, market_environment: str) -> Path:
    environment = str(market_environment).strip().upper()
    if environment == "LIVE":
        leaf = "live"
    elif environment == "TESTNET":
        leaf = "testnet"
    else:
        raise ValueError("NBOT_OBSERVATION_RUNTIME_ENVIRONMENT_INVALID")
    return Path(repo_root) / "runtime" / "observation" / leaf / "observation.lock"


class ObservationWorker:
    """Run canonical evidence collection without research or capital authority."""

    def __init__(
        self,
        config: ObservationConfig,
        client: PublicMarketClient,
        database: EvidenceDatabase,
        *,
        event_sink: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.client = client
        self.database = database
        self.collector = MarketEvidenceCollector(config, client, database)
        self._stop_event = threading.Event()
        self._event_sink = event_sink

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def stop(self) -> None:
        self._stop_event.set()

    def _emit(self, event: str, **fields: object) -> None:
        if self._event_sink is None:
            return
        payload: dict[str, object] = {"event": event}
        payload.update(fields)
        try:
            self._event_sink(payload)
        except Exception:
            # Logging/telemetry is observational and must never become evidence
            # authority or crash the collection worker.
            return

    def initialize(self) -> None:
        self.database.initialize()
        integrity = self.database.integrity_check()
        if not bool(integrity.get("ok")):
            raise ObservationRuntimeError("NBOT_OBSERVATION_RUNTIME_DB_INTEGRITY_FAILED")
        self._emit(
            "STARTED",
            market_environment=self.config.market_environment,
            database=str(self.config.database_path),
        )

    def run_cycle(self) -> ObservationCycleResult:
        """Run one evidence cycle, always prioritizing fresh point-in-time truth."""

        collection = self.collector.collect_once()
        if collection.status not in {"COMPLETE", "ALREADY_COMPLETE", "PARTIAL_REJECTED"}:
            raise ObservationRuntimeError(
                f"NBOT_OBSERVATION_COLLECTION_STATUS_INVALID:{collection.status}"
            )
        if collection.status == "PARTIAL_REJECTED":
            # A just-failed live event remains eligible for a fresh retry.  Do
            # not immediately fill it as historical candle-only evidence and
            # thereby make the loss of point-in-time context permanent.
            result = ObservationCycleResult(
                collection=collection,
                gap_recovery=None,
                funding_sync=None,
                retry_fresh_event=True,
            )
            self._emit(
                "CYCLE",
                collection_status=collection.status,
                event_open_ms=collection.event_open_ms,
                retry_fresh_event=True,
            )
            return result

        recovery = self.collector.recover_gaps()
        funding = self.collector.sync_funding_history()
        result = ObservationCycleResult(
            collection=collection,
            gap_recovery=recovery,
            funding_sync=funding,
            retry_fresh_event=False,
        )
        self._emit(
            "CYCLE",
            collection_status=collection.status,
            event_open_ms=collection.event_open_ms,
            recovered=recovery.recovered,
            recovery_failed=recovery.failed,
            funding_rows=funding.rows,
            funding_reason=funding.reason,
            retry_fresh_event=False,
        )
        return result

    def _wait(self, seconds: float) -> None:
        self._stop_event.wait(max(0.0, float(seconds)))

    def run(self, *, max_cycles: int | None = None) -> int:
        """Run until stopped, returning the number of completed worker cycles.

        `max_cycles` exists for deterministic one-shot operation and tests.  A
        transient Binance/public collection failure is retried; database or
        programming failures remain fatal and fail closed.
        """

        if max_cycles is not None and int(max_cycles) <= 0:
            raise ValueError("NBOT_OBSERVATION_MAX_CYCLES_INVALID")
        self.initialize()
        completed_cycles = 0

        while not self.stopped:
            try:
                cycle = self.run_cycle()
            except ObservationCollectionNotReady as exc:
                self._emit("NOT_READY", wait_ms=exc.wait_ms)
                self._wait(exc.wait_ms / 1000.0)
                continue
            except (ObservationCollectionError, BinancePublicMarketError) as exc:
                self._emit(
                    "TRANSIENT_ERROR",
                    error_type=type(exc).__name__,
                    detail=str(exc),
                )
                self._wait(self.config.retry_seconds)
                continue
            except EvidenceDatabaseError:
                raise

            if cycle.retry_fresh_event:
                self._wait(self.config.retry_seconds)
                continue

            completed_cycles += 1
            if max_cycles is not None and completed_cycles >= int(max_cycles):
                break
            if self.stopped:
                break

            try:
                wait_seconds = self.collector.seconds_until_next_collection()
            except BinancePublicMarketError as exc:
                self._emit(
                    "TRANSIENT_ERROR",
                    error_type=type(exc).__name__,
                    detail=str(exc),
                )
                self._wait(self.config.retry_seconds)
                continue
            self._wait(wait_seconds)

        self._emit("STOPPED", completed_cycles=completed_cycles)
        return completed_cycles
