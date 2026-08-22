"""V3.8.4 one-pass research epochs over bounded raw LIVE evidence.

Realtime collection remains in the canonical raw database.  Heavy derived
research is built only inside a disposable workspace for one mature 96-event
epoch.  The workspace is deleted after its compact qualified evidence and
cumulative Ridge state are committed to permanent research memory.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable

from .binance_public import BinanceUsdMPublicClient
from .database import EvidenceDatabase
from .features import CanonicalFeatureStore
from .outcomes import FuturePathStore
from .policies import ExitPolicyLab
from .research_memory import LEDGER_COLUMNS, RIDGE_COLUMNS, ResearchMemoryStore
from .retention import ResearchRetentionManager, AUTHORITY
from .selection import EntrySelectionLab, SELECTION_CONFIG
from .signals import ResearchSignalStore
from .worker import observation_runtime_lock_path

EPOCH_VERSION = "RESEARCH_EPOCH_V1"
CUTOVER_CONFIRMATION = "I_ACCEPT_V384_FRESH_RAW_GENERATION"


@dataclass(frozen=True)
class ResearchEpochConfig:
    epoch_events: int = 96
    history_context_bars: int = 48
    future_context_bars: int = 48
    target_runtime_seconds: float = 3600.0
    hard_runtime_seconds: float = 7200.0

    def validate(self) -> None:
        if self.epoch_events != 96:
            raise ValueError("NBOT_V384_EPOCH_EVENTS_IMMUTABLE")
        if self.history_context_bars != 48 or self.future_context_bars != 48:
            raise ValueError("NBOT_V384_CONTEXT_WINDOW_IMMUTABLE")
        if self.target_runtime_seconds <= 0 or self.hard_runtime_seconds < self.target_runtime_seconds:
            raise ValueError("NBOT_V384_RUNTIME_TARGET_INVALID")


EPOCH_CONFIG = ResearchEpochConfig()
EPOCH_CONFIG.validate()


@dataclass(frozen=True)
class EpochPlan:
    status: str
    target_events: tuple[int, ...]
    target_start_ms: int | None
    target_end_ms: int | None
    context_start_ms: int | None
    context_end_ms: int | None
    latest_raw_event_ms: int | None
    generation_floor_ms: int
    memory_latest_event_ms: int | None


class ResearchEpochProcessor:
    def __init__(
        self,
        raw_database: EvidenceDatabase,
        memory: ResearchMemoryStore,
        repo_root: Path,
        *,
        config: ResearchEpochConfig = EPOCH_CONFIG,
        now: Callable[[], float] | None = None,
        future_client_factory: Callable[[Any], Any] | None = None,
    ) -> None:
        config.validate()
        self.raw = raw_database
        self.memory = memory
        self.repo_root = Path(repo_root)
        self.config = config
        self._now = now or time.perf_counter
        self._future_client_factory = future_client_factory or BinanceUsdMPublicClient

    @property
    def workspace_dir(self) -> Path:
        return self.repo_root / "runtime" / "observation" / "live" / "research_epochs"

    def plan(self) -> EpochPlan:
        meta = self.memory.metadata()
        if meta.get("memory_version") is None:
            raise RuntimeError("NBOT_V384_MEMORY_NOT_INITIALIZED")
        floor = int(meta["generation_floor_ms"])
        memory_latest = self.memory.latest_event_ms()
        lower = floor - 1
        if memory_latest is not None and memory_latest >= floor:
            lower = memory_latest
        interval = int(self.raw.config.candle_interval_ms)
        with self.raw.connection() as conn:
            latest = conn.execute(
                "SELECT MAX(event_open_ms) FROM market_events WHERE status='COMPLETE'"
            ).fetchone()[0]
            latest_raw = None if latest is None else int(latest)
            if latest_raw is None:
                return EpochPlan("WAIT_FOR_RAW_EVIDENCE", (), None, None, None, None, None, floor, memory_latest)
            mature_through = latest_raw - self.config.future_context_bars * interval
            candidates = [int(row[0]) for row in conn.execute(
                "SELECT p.event_open_ms FROM event_provenance p "
                "JOIN market_events e USING(event_open_ms) "
                "WHERE p.context_complete=1 AND p.membership_quality='POINT_IN_TIME' "
                "AND e.status='COMPLETE' AND p.event_open_ms>? AND p.event_open_ms>=? "
                "AND p.event_open_ms<=? ORDER BY p.event_open_ms LIMIT ?",
                (lower, floor, mature_through, self.config.epoch_events),
            )]
            if len(candidates) < self.config.epoch_events:
                return EpochPlan(
                    "WAIT_FOR_MATURE_EPOCH", tuple(candidates),
                    candidates[0] if candidates else None,
                    candidates[-1] if candidates else None,
                    None, None, latest_raw, floor, memory_latest,
                )
            targets = tuple(candidates[: self.config.epoch_events])
            context_start = targets[0] - self.config.history_context_bars * interval
            context_end = targets[-1] + self.config.future_context_bars * interval
            earliest = conn.execute(
                "SELECT MIN(event_open_ms) FROM market_events WHERE status='COMPLETE'"
            ).fetchone()[0]
            if earliest is None or int(earliest) > context_start:
                return EpochPlan(
                    "WAIT_FOR_HISTORY_CONTEXT", targets, targets[0], targets[-1],
                    context_start, context_end, latest_raw, floor, memory_latest,
                )
            if latest_raw < context_end:
                return EpochPlan(
                    "WAIT_FOR_FUTURE_CONTEXT", targets, targets[0], targets[-1],
                    context_start, context_end, latest_raw, floor, memory_latest,
                )
        return EpochPlan(
            "READY", targets, targets[0], targets[-1], context_start,
            context_end, latest_raw, floor, memory_latest,
        )

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
        return [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]

    def _copy_raw_workspace(self, plan: EpochPlan, workspace: EvidenceDatabase) -> None:
        if plan.status != "READY" or not plan.target_events:
            raise RuntimeError("NBOT_V384_EPOCH_PLAN_NOT_READY")
        workspace.initialize()
        source = sqlite3.connect(f"file:{self.raw.path}?mode=ro", uri=True, timeout=30.0)
        source.execute("PRAGMA query_only=ON")
        target_set = set(plan.target_events)
        start = int(plan.context_start_ms)
        end = int(plan.context_end_ms)
        try:
            with workspace.connection() as dest:
                dest.execute("BEGIN IMMEDIATE")
                for table in (
                    "market_events", "candles_5m", "market_snapshots",
                    "event_provenance", "universe_membership", "source_captures",
                ):
                    cols = self._table_columns(source, table)
                    rows = list(source.execute(
                        f'SELECT {",".join(cols)} FROM "{table}" '
                        'WHERE event_open_ms BETWEEN ? AND ?', (start, end)
                    ))
                    if rows:
                        dest.executemany(
                            f'INSERT INTO "{table}"({",".join(cols)}) VALUES('
                            + ",".join("?" for _ in cols) + ")",
                            rows,
                        )
                # Context events provide candles/history only.  They are not
                # additional research targets inside this epoch workspace.
                placeholders = ",".join("?" for _ in target_set)
                if target_set:
                    dest.execute(
                        "UPDATE event_provenance SET context_complete=0,"
                        "membership_quality='RESEARCH_CONTEXT_ONLY' "
                        f"WHERE event_open_ms NOT IN ({placeholders})",
                        tuple(sorted(target_set)),
                    )
                funding_cols = self._table_columns(source, "funding_events")
                funding_rows = list(source.execute(
                    f'SELECT {",".join(funding_cols)} FROM funding_events '
                    'WHERE funding_time_ms BETWEEN ? AND ? ORDER BY symbol,funding_time_ms',
                    (start, end + self.raw.config.candle_interval_ms),
                ))
                if funding_rows:
                    dest.executemany(
                        f'INSERT INTO funding_events({",".join(funding_cols)}) VALUES('
                        + ",".join("?" for _ in funding_cols) + ")",
                        funding_rows,
                    )
                range_cols = self._table_columns(source, "funding_sync_ranges")
                range_rows = list(source.execute(
                    f'SELECT {",".join(range_cols)} FROM funding_sync_ranges '
                    'WHERE end_ms>=? AND start_ms<=? ORDER BY id',
                    (start, end + self.raw.config.candle_interval_ms),
                ))
                for row in range_rows:
                    values = list(row)
                    # Let the scratch DB allocate its own AUTOINCREMENT id.
                    if range_cols and range_cols[0] == "id":
                        cols = range_cols[1:]
                        values = values[1:]
                    else:
                        cols = range_cols
                    dest.execute(
                        f'INSERT INTO funding_sync_ranges({",".join(cols)}) VALUES('
                        + ",".join("?" for _ in cols) + ")",
                        values,
                    )
        finally:
            source.close()

    def _stage(self, timings: dict[str, float], name: str, fn):
        started = self._now()
        value = fn()
        timings[name] = self._now() - started
        return value

    def _source_digest(self, target_events: tuple[int, ...]) -> str:
        with self.raw.connection() as conn:
            rows = list(conn.execute(
                "SELECT event_open_ms,captured_at_ms,stored_symbols,collector_version "
                "FROM market_events WHERE event_open_ms BETWEEN ? AND ? ORDER BY event_open_ms",
                (target_events[0], target_events[-1]),
            ))
        raw = json.dumps([list(row) for row in rows], separators=(",", ":"), sort_keys=False).encode()
        return hashlib.sha256(raw).hexdigest()

    def run_once(self) -> dict[str, Any]:
        plan = self.plan()
        if plan.status != "READY":
            return {
                "epoch_version": EPOCH_VERSION,
                "authority": AUTHORITY,
                "healthy": True,
                "status": plan.status,
                "plan": asdict(plan),
            }
        target_events = plan.target_events
        epoch_id = f"EPOCH-{target_events[0]}-{target_events[-1]}"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        scratch_path = self.workspace_dir / f"{epoch_id}.db"
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(scratch_path) + suffix)
            if candidate.exists():
                candidate.unlink()
        workspace = EvidenceDatabase(self.raw.config, path_override=scratch_path)
        timings: dict[str, float] = {}
        started_total = self._now()
        success = False
        try:
            self._stage(timings, "workspace_copy", lambda: self._copy_raw_workspace(plan, workspace))
            features = self._stage(
                timings, "features",
                lambda: CanonicalFeatureStore(workspace).build(max_events=self.config.epoch_events),
            )
            signals = self._stage(
                timings, "signals",
                lambda: ResearchSignalStore(workspace).build(max_events=self.config.epoch_events),
            )
            outcomes = self._stage(
                timings, "outcomes",
                lambda: FuturePathStore(
                    workspace, self._future_client_factory(workspace.config)
                ).build(max_events=self.config.epoch_events),
            )
            policies = self._stage(
                timings, "policies",
                lambda: ExitPolicyLab(workspace).build(max_events=self.config.epoch_events),
            )
            selection_lab = EntrySelectionLab(workspace)
            base = self.memory.history_base()
            self._stage(
                timings, "seed_learning_state",
                lambda: selection_lab.seed_history_base(
                    through_event_ms=base["through_event_ms"],
                    training_event_count=base["event_count"],
                    training_row_count=base["row_count"],
                    source_digest=base["source_digest"],
                    ridge_state_row=base["ridge_state_row"],
                ),
            )
            selection = self._stage(
                timings, "selection",
                lambda: selection_lab.build(max_events=self.config.epoch_events),
            )
            retention = ResearchRetentionManager(workspace)
            self._stage(timings, "seal_init", retention.initialize)
            seal = self._stage(
                timings, "seal",
                lambda: retention.seal(max_events=self.config.epoch_events),
            )
            with workspace.connection() as conn:
                ledger_rows = list(conn.execute(
                    "SELECT " + ",".join(LEDGER_COLUMNS) +
                    " FROM research_event_ledger WHERE event_open_ms BETWEEN ? AND ? "
                    "ORDER BY event_open_ms",
                    (target_events[0], target_events[-1]),
                ))
                ridge = conn.execute(
                    "SELECT " + ",".join(RIDGE_COLUMNS) +
                    " FROM entry_selection_ridge_state WHERE lab_version=?",
                    (SELECTION_CONFIG.lab_version,),
                ).fetchone()
            if len(ledger_rows) != self.config.epoch_events:
                raise RuntimeError(
                    f"NBOT_V384_EPOCH_SEAL_COUNT_INVALID:{len(ledger_rows)}"
                )
            generation = self.memory.metadata()["generation"]
            imported = self._stage(
                timings, "memory_import",
                lambda: self.memory.import_ledger_rows(
                    ledger_rows, source_generation=generation
                ),
            )
            if ridge is None:
                raise RuntimeError("NBOT_V384_EPOCH_RIDGE_STATE_MISSING")
            self.memory.replace_ridge_state(tuple(ridge))
            elapsed = self._now() - started_total
            source_digest = self._source_digest(target_events)
            self.memory.record_epoch(
                epoch_id=epoch_id,
                generation=generation,
                target_start_ms=target_events[0],
                target_end_ms=target_events[-1],
                event_count=len(target_events),
                source_digest=source_digest,
                elapsed_seconds=elapsed,
            )
            success = True
            return {
                "epoch_version": EPOCH_VERSION,
                "authority": AUTHORITY,
                "healthy": True,
                "status": "PASS",
                "epoch_id": epoch_id,
                "plan": asdict(plan),
                "timings_seconds": timings,
                "elapsed_seconds": elapsed,
                "target_runtime_seconds": self.config.target_runtime_seconds,
                "hard_runtime_seconds": self.config.hard_runtime_seconds,
                "within_target_runtime": elapsed <= self.config.target_runtime_seconds,
                "within_hard_runtime": elapsed <= self.config.hard_runtime_seconds,
                "features": asdict(features),
                "signals": asdict(signals),
                "outcomes": asdict(outcomes),
                "policies": asdict(policies),
                "selection": asdict(selection),
                "seal": seal,
                "memory_rows_imported": imported,
                "memory": self.memory.status(),
            }
        finally:
            if success:
                for suffix in ("-wal", "-shm", ""):
                    candidate = Path(str(scratch_path) + suffix)
                    try:
                        candidate.unlink()
                    except FileNotFoundError:
                        pass

    def prune_raw(self) -> dict[str, Any]:
        latest = self.memory.latest_event_ms()
        if latest is None:
            return {"deleted_events": 0, "reason": "NO_QUALIFIED_MEMORY"}
        interval = self.raw.config.candle_interval_ms
        cutoff = latest - self.config.history_context_bars * interval
        deleted = 0
        with self.raw.connection() as conn:
            events = [int(row[0]) for row in conn.execute(
                "SELECT event_open_ms FROM market_events WHERE event_open_ms<? "
                "ORDER BY event_open_ms LIMIT ?",
                (cutoff, self.config.epoch_events),
            )]
            if events:
                conn.execute("BEGIN IMMEDIATE")
                conn.executemany(
                    "DELETE FROM market_events WHERE event_open_ms=?",
                    [(event,) for event in events],
                )
                conn.executemany(
                    "DELETE FROM collection_attempts WHERE event_open_ms=?",
                    [(event,) for event in events],
                )
                deleted = len(events)
            conn.execute("DELETE FROM funding_events WHERE funding_time_ms<?", (cutoff,))
            conn.execute("DELETE FROM funding_sync_ranges WHERE end_ms<?", (cutoff,))
        return {
            "deleted_events": deleted,
            "cutoff_event_open_ms": cutoff,
            "latest_qualified_event_ms": latest,
            "authority": AUTHORITY,
        }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _runtime_lock_is_held(repo_root: Path) -> bool:
    path = observation_runtime_lock_path(Path(repo_root), "LIVE")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return False
    finally:
        handle.close()


def cutover_to_fresh_raw_generation(
    database: EvidenceDatabase,
    memory: ResearchMemoryStore,
    repo_root: Path,
    artifact_dir: Path,
    *,
    generation: str,
    confirmation: str,
    seed_events: int = 48,
) -> dict[str, Any]:
    """Start a completely fresh V3.8.4 raw/research generation.

    The accepted pre-V3.8.4 mixed database is deliberately discarded rather
    than migrated.  Only a tiny reset manifest is retained.  The first
    research target is placed 48 fresh five-minute events after the old
    generation's last complete event, so the new generation accumulates its
    entire history context prospectively.
    """
    if str(confirmation) != CUTOVER_CONFIRMATION:
        raise RuntimeError("NBOT_V384_CUTOVER_CONFIRMATION_REQUIRED")
    if int(seed_events) != 48:
        raise RuntimeError("NBOT_V384_CUTOVER_HISTORY_EVENTS_IMMUTABLE")
    if _runtime_lock_is_held(repo_root):
        raise RuntimeError("NBOT_V384_CUTOVER_COLLECTOR_MUST_BE_STOPPED")

    canonical = Path(database.path)
    if not canonical.exists():
        raise RuntimeError("NBOT_V384_CUTOVER_LEGACY_DB_MISSING")
    if memory.path.exists():
        raise RuntimeError("NBOT_V384_CUTOVER_MEMORY_ALREADY_EXISTS")

    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    reset_manifest = artifact_dir / "discarded_v383_generation.json"
    temp_raw = canonical.with_name(canonical.name + ".v384-new")
    temp_memory = memory.path.with_name(memory.path.name + ".v384-new")
    targets = (
        reset_manifest, temp_raw, temp_memory,
        Path(str(temp_raw) + "-wal"), Path(str(temp_raw) + "-shm"),
        Path(str(temp_memory) + "-wal"), Path(str(temp_memory) + "-shm"),
    )
    for path in targets:
        if path.exists():
            raise RuntimeError(f"NBOT_V384_CUTOVER_TARGET_EXISTS:{path}")

    database.checkpoint()
    source = sqlite3.connect(f"file:{canonical}?mode=ro", uri=True, timeout=60.0)
    source.execute("PRAGMA query_only=ON")
    try:
        quick = str(source.execute("PRAGMA quick_check").fetchone()[0])
        fk = source.execute("PRAGMA foreign_key_check").fetchall()
        latest = source.execute(
            "SELECT MAX(event_open_ms) FROM market_events WHERE status='COMPLETE'"
        ).fetchone()[0]
        complete_events = int(source.execute(
            "SELECT COUNT(*) FROM market_events WHERE status='COMPLETE'"
        ).fetchone()[0])
        if quick != "ok" or fk or latest is None:
            raise RuntimeError("NBOT_V384_CUTOVER_LEGACY_DB_INVALID")
        latest = int(latest)
    finally:
        source.close()

    interval = int(database.config.candle_interval_ms)
    generation_floor = latest + (int(seed_events) + 1) * interval

    fresh = EvidenceDatabase(database.config, path_override=temp_raw)
    fresh.initialize()
    with fresh.connection() as conn:
        fresh_quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        fresh_fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        fresh_count = int(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0])
        derived = [str(row[0]) for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "(name LIKE 'canonical_%' OR name LIKE 'signal_%' OR name LIKE 'future_%' "
            "OR name LIKE 'exit_policy_%' OR name LIKE 'entry_selection_%' "
            "OR name LIKE 'research_event_ledger%')"
        )]
    if fresh_quick != "ok" or fresh_fk or fresh_count != 0 or derived:
        raise RuntimeError(
            f"NBOT_V384_CUTOVER_FRESH_RAW_INVALID:{fresh_quick}:{len(fresh_fk)}:{fresh_count}:{derived}"
        )
    fresh.checkpoint()

    temp_store = ResearchMemoryStore(temp_memory)
    temp_store.initialize(
        generation=generation,
        generation_floor_ms=generation_floor,
    )
    temp_status = temp_store.status()
    if int(temp_status.get("events", -1)) != 0:
        raise RuntimeError("NBOT_V384_CUTOVER_FRESH_MEMORY_NOT_EMPTY")
    with sqlite3.connect(temp_memory, timeout=30.0) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        memory_quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        memory_fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    if memory_quick != "ok" or memory_fk:
        raise RuntimeError("NBOT_V384_CUTOVER_FRESH_MEMORY_INVALID")

    manifest = {
        "discarded_generation": "V3_8_3_LEGACY_MIXED_DB",
        "discarded_database": str(canonical),
        "discarded_database_bytes": canonical.stat().st_size,
        "discarded_complete_events": complete_events,
        "discarded_latest_event_ms": latest,
        "new_generation": generation,
        "history_context_events": int(seed_events),
        "generation_floor_ms": generation_floor,
        "authority": AUTHORITY,
    }
    reset_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # The collector is stopped and both replacement stores are already fully
    # initialized and verified.  Replacing canonical now deliberately discards
    # the old mixed raw+derived generation without copying any historical row.
    for path in (
        Path(str(canonical) + "-wal"), Path(str(canonical) + "-shm"),
        Path(str(temp_raw) + "-wal"), Path(str(temp_raw) + "-shm"),
        Path(str(temp_memory) + "-wal"), Path(str(temp_memory) + "-shm"),
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    os.replace(temp_raw, canonical)
    os.replace(temp_memory, memory.path)

    final = EvidenceDatabase(database.config)
    with final.connection() as conn:
        final_quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        final_fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        final_count = int(conn.execute("SELECT COUNT(*) FROM market_events").fetchone()[0])
    final_memory = memory.status()
    if (
        final_quick != "ok" or final_fk or final_count != 0
        or int(final_memory.get("events", -1)) != 0
    ):
        raise RuntimeError("NBOT_V384_CUTOVER_FINAL_GENERATION_INVALID")

    return {
        "authority": AUTHORITY,
        "generation": generation,
        "generation_floor_ms": generation_floor,
        "discarded_legacy_database": True,
        "legacy_latest_event_ms": latest,
        "legacy_complete_events": complete_events,
        "reset_manifest": str(reset_manifest),
        "fresh_raw_events": final_count,
        "fresh_raw_quick_check": final_quick,
        "fresh_raw_fk_errors": len(final_fk),
        "fresh_memory": final_memory,
        "canonical_database": str(canonical),
    }
