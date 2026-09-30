"""V3.8.3 bounded LIVE research catch-up controller.

The controller turns the physically-proven V3.8.2 manual lifecycle into one
fail-closed operation:

    bounded derive -> selection -> seal -> compact -> audit -> repeat

It never evaluates/promotes a Champion, never changes research definitions,
and has no recommendation or execution authority.  The realtime LIVE evidence
collector remains a separate process and must be demonstrably alive while
catch-up runs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import time
from pathlib import Path
from typing import Any, Callable

from .binance_public import BinanceUsdMPublicClient
from .champion import WalkForwardChampionEvaluator
from .database import EvidenceDatabase
from .features import CanonicalFeatureStore
from .learning import ContinuousLearningFoundation
from .outcomes import FuturePathStore
from .policies import ExitPolicyLab
from .retention import ResearchRetentionManager, RETENTION_CONFIG
from .selection import EntrySelectionLab, SELECTION_CONFIG
from .signals import ResearchSignalStore
from .worker import observation_runtime_lock_path


AUTHORITY = "RESEARCH_ONLY_NO_EXECUTION"
CONTROLLER_VERSION = "BOUNDED_RESEARCH_CATCHUP_V1"


class ResearchCatchupError(RuntimeError):
    """Bounded catch-up cannot proceed without weakening a frozen gate."""

    def __init__(self, code: str, report: dict[str, Any] | None = None):
        super().__init__(code)
        self.code = str(code)
        self.report = report or {}


@dataclass(frozen=True)
class CatchupConfig:
    controller_version: str = CONTROLLER_VERSION
    max_batch_selection_events: int = 8
    operating_live_bytes: int = 943_718_400  # physically proven 900 MiB ceiling
    min_build_headroom_bytes: int = 67_108_864  # 64 MiB reserve for one proven batch
    collector_max_capture_age_ms: int = 15 * 60 * 1000
    max_cycles_per_invocation: int = 32

    def validate(self) -> None:
        if self.controller_version != CONTROLLER_VERSION:
            raise ValueError("NBOT_V383_CONTROLLER_VERSION_IMMUTABLE")
        if self.max_batch_selection_events != 8:
            raise ValueError("NBOT_V383_MAX_BATCH_IMMUTABLE")
        if self.operating_live_bytes != 943_718_400:
            raise ValueError("NBOT_V383_OPERATING_CEILING_IMMUTABLE")
        if self.operating_live_bytes >= RETENTION_CONFIG.hard_live_bytes:
            raise ValueError("NBOT_V383_OPERATING_CEILING_NOT_BELOW_HARD_CAP")
        if self.min_build_headroom_bytes != 67_108_864:
            raise ValueError("NBOT_V383_BUILD_HEADROOM_IMMUTABLE")
        if self.min_build_headroom_bytes >= self.operating_live_bytes:
            raise ValueError("NBOT_V383_BUILD_HEADROOM_INVALID")
        if self.collector_max_capture_age_ms < 10 * 60 * 1000:
            raise ValueError("NBOT_V383_COLLECTOR_AGE_GATE_TOO_TIGHT")
        if self.max_cycles_per_invocation <= 0:
            raise ValueError("NBOT_V383_MAX_CYCLES_INVALID")


CATCHUP_CONFIG = CatchupConfig()
CATCHUP_CONFIG.validate()


class ResearchCatchupLock:
    """Prevent two research catch-up controllers from writing concurrently."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._handle = None

    def __enter__(self) -> "ResearchCatchupLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ResearchCatchupError("NBOT_V383_CATCHUP_ALREADY_RUNNING") from exc
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    return value


class BoundedResearchCatchupController:
    """Advance LIVE research only in small, retention-bounded batches."""

    def __init__(
        self,
        database: EvidenceDatabase,
        repo_root: Path,
        *,
        config: CatchupConfig = CATCHUP_CONFIG,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        config.validate()
        self.database = database
        self.repo_root = Path(repo_root)
        self.config = config
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))

        self.features = CanonicalFeatureStore(database)
        self.signals = ResearchSignalStore(database)
        self.outcomes = FuturePathStore(
            database,
            BinanceUsdMPublicClient(database.config),
        )
        self.policies = ExitPolicyLab(database)
        self.selection = EntrySelectionLab(database)
        self.champion = WalkForwardChampionEvaluator(database)
        self.learning = ContinuousLearningFoundation(database)
        self.retention = ResearchRetentionManager(database)

    @property
    def lock_path(self) -> Path:
        return (
            self.repo_root
            / "runtime"
            / "observation"
            / "live"
            / "research-catchup.lock"
        )

    def _fail(self, code: str, **fields: Any) -> None:
        raise ResearchCatchupError(
            code,
            {
                "controller_version": self.config.controller_version,
                "authority": AUTHORITY,
                "healthy": False,
                "error": code,
                **fields,
            },
        )

    def _collector_health(self) -> dict[str, Any]:
        """Verify the separate LIVE collector owns its runtime lock and is fresh."""
        lock_path = observation_runtime_lock_path(self.repo_root, "LIVE")
        lock_held = False
        if lock_path.exists():
            handle = lock_path.open("a+", encoding="utf-8")
            try:
                try:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    lock_held = True
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

        with self.database.connection() as conn:
            latest = conn.execute(
                "SELECT event_open_ms,captured_at_ms FROM market_events "
                "ORDER BY event_open_ms DESC LIMIT 1"
            ).fetchone()
        latest_event = None if latest is None else int(latest[0])
        latest_capture = None if latest is None else int(latest[1])
        age_ms = None if latest_capture is None else max(0, self._now_ms() - latest_capture)
        healthy = bool(
            lock_held
            and latest_capture is not None
            and age_ms is not None
            and age_ms <= self.config.collector_max_capture_age_ms
        )
        return {
            "healthy": healthy,
            "runtime_lock_held": lock_held,
            "runtime_lock": str(lock_path),
            "latest_event_open_ms": latest_event,
            "latest_capture_ms": latest_capture,
            "capture_age_ms": age_ms,
            "max_capture_age_ms": self.config.collector_max_capture_age_ms,
        }

    def _sqlite_integrity(self) -> dict[str, Any]:
        with self.database.connection() as conn:
            quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
            foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        return {
            "healthy": quick == "ok" and not foreign_keys,
            "quick_check": quick,
            "foreign_key_errors": len(foreign_keys),
        }

    def _lifecycle_counts(self) -> dict[str, int]:
        with self.database.connection() as conn:
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "research_event_ledger" not in tables:
                return {
                    "ledger_events": 0,
                    "sealed_events": 0,
                    "compacted_events": 0,
                    "detailed_selection_events": 0,
                    "pending_unsealed_events": 0,
                    "compactable_events": 0,
                }
            ledger_rows = [
                (int(row[0]), str(row[1]))
                for row in conn.execute(
                    "SELECT event_open_ms,state FROM research_event_ledger "
                    "ORDER BY event_open_ms"
                )
            ]
            ledger = len(ledger_rows)
            sealed = sum(state == "SEALED" for _, state in ledger_rows)
            compacted = sum(state == "COMPACTED" for _, state in ledger_rows)
            detail_events = {
                int(row[0])
                for row in conn.execute(
                    "SELECT event_open_ms FROM entry_selection_builds "
                    "WHERE lab_version=?",
                    (SELECTION_CONFIG.lab_version,),
                )
            }
            pending = int(conn.execute(
                "SELECT COUNT(*) FROM entry_selection_builds b "
                "WHERE b.lab_version=? AND NOT EXISTS ("
                "SELECT 1 FROM research_event_ledger l "
                "WHERE l.event_open_ms=b.event_open_ms)",
                (SELECTION_CONFIG.lab_version,),
            ).fetchone()[0])

        ordered_events = [event for event, _ in ledger_rows]
        frozen = set(ordered_events[: RETENTION_CONFIG.frozen_detail_selection_events])
        recent = set(ordered_events[-RETENTION_CONFIG.recent_detail_selection_events :])
        protected = frozen | recent
        compactable = sum(
            state == "SEALED" and event not in protected and event in detail_events
            for event, state in ledger_rows
        )
        return {
            "ledger_events": ledger,
            "sealed_events": sealed,
            "compacted_events": compacted,
            "detailed_selection_events": len(detail_events),
            "pending_unsealed_events": pending,
            "compactable_events": compactable,
        }

    def _champion_fingerprint(self) -> dict[str, Any]:
        status = self.champion.status()
        evaluation = status.get("evaluation")
        champion = status.get("champion")
        return {
            "authority": status.get("authority"),
            "evaluation": None if evaluation is None else list(evaluation),
            "champion": None if champion is None else list(champion),
        }

    def _research_audit(self) -> dict[str, Any]:
        reports = {
            "features": self.features.audit(),
            "signals": self.signals.audit(),
            "outcomes": self.outcomes.audit(),
            "policies": self.policies.audit(),
            "selection": self.selection.audit(),
            "champion": self.champion.audit(),
            "learning": self.learning.audit(),
            "retention": self.retention.audit(),
        }
        healthy = all(bool(report.get("healthy")) for report in reports.values())
        return {"healthy": healthy, "reports": reports}

    def _gate(
        self, baseline_champion: dict[str, Any], *, stage: str,
        deep_research: bool = True, require_build_headroom: bool = False,
    ) -> dict[str, Any]:
        collector = self._collector_health()
        if not collector["healthy"]:
            self._fail("NBOT_V383_COLLECTOR_UNHEALTHY", stage=stage, collector=collector)

        integrity = self._sqlite_integrity()
        if not integrity["healthy"]:
            self._fail("NBOT_V383_SQLITE_INTEGRITY_FAILED", stage=stage, integrity=integrity)

        retention = self.retention.audit()
        if not bool(retention.get("healthy")):
            self._fail("NBOT_V383_RETENTION_AUDIT_FAILED", stage=stage, retention=retention)
        live_bytes = int(retention.get("live_bytes", 0))
        if live_bytes >= self.config.operating_live_bytes:
            self._fail(
                "NBOT_V383_OPERATING_STORAGE_CEILING_REACHED",
                stage=stage,
                live_bytes=live_bytes,
                operating_live_bytes=self.config.operating_live_bytes,
            )
        if require_build_headroom:
            available = self.config.operating_live_bytes - live_bytes
            if available < self.config.min_build_headroom_bytes:
                self._fail(
                    "NBOT_V383_BUILD_HEADROOM_INSUFFICIENT",
                    stage=stage,
                    live_bytes=live_bytes,
                    operating_live_bytes=self.config.operating_live_bytes,
                    required_headroom_bytes=self.config.min_build_headroom_bytes,
                    available_headroom_bytes=available,
                )

        research: dict[str, Any] | None = None
        if deep_research:
            research = self._research_audit()
            if not research["healthy"]:
                self._fail("NBOT_V383_RESEARCH_AUDIT_FAILED", stage=stage, research=research)
            selection_report = research["reports"]["selection"]
            if int(selection_report.get("ridge_state_mismatches", 0)) != 0:
                self._fail("NBOT_V383_RIDGE_STATE_MISMATCH", stage=stage, selection=selection_report)

        champion = self._champion_fingerprint()
        if champion != baseline_champion:
            self._fail(
                "NBOT_V383_CHAMPION_FINGERPRINT_CHANGED",
                stage=stage,
                expected_champion=baseline_champion,
                actual_champion=champion,
            )
        return {
            "collector": collector,
            "integrity": integrity,
            "retention_live_bytes": live_bytes,
            "research_healthy": None if research is None else True,
            "champion": champion,
        }

    def _build_component(self, component: str, batch_events: int) -> Any:
        if component == "features":
            return self.features.build(max_events=batch_events)
        if component == "signals":
            return self.signals.build(max_events=batch_events)
        if component == "outcomes":
            return self.outcomes.build(max_events=batch_events)
        if component == "policies":
            return self.policies.build(max_events=batch_events)
        if component == "selection":
            return self.selection.build(max_events=batch_events)
        raise ValueError("NBOT_V383_COMPONENT_INVALID")

    def _recover_lifecycle(
        self, batch_events: int, baseline_champion: dict[str, Any]
    ) -> dict[str, Any] | None:
        before = self._lifecycle_counts()
        pending = int(before["pending_unsealed_events"])
        compactable = int(before["compactable_events"])
        if pending == 0 and compactable == 0:
            return None
        if pending > batch_events:
            self._fail(
                "NBOT_V383_PENDING_UNSEALED_EXCEEDS_BATCH",
                pending_unsealed_events=pending,
                batch_events=batch_events,
                counts=before,
            )
        if compactable > batch_events:
            self._fail(
                "NBOT_V383_COMPACTION_BACKLOG_EXCEEDS_BATCH",
                compactable_events=compactable,
                batch_events=batch_events,
                counts=before,
            )

        operations: list[dict[str, Any]] = []
        if pending > 0:
            report = self.retention.maintain(
                seal_max_events=pending,
                compact_max_events=batch_events,
            )
            operations.append({"operation": "SEAL_PENDING_AND_COMPACT", "report": report})

        middle = self._lifecycle_counts()
        remaining_compactable = int(middle["compactable_events"])
        if remaining_compactable > 0:
            if remaining_compactable > batch_events:
                self._fail(
                    "NBOT_V383_COMPACTION_BACKLOG_EXCEEDS_BATCH_AFTER_SEAL",
                    compactable_events=remaining_compactable,
                    batch_events=batch_events,
                    counts=middle,
                )
            report = self.retention.compact(max_events=remaining_compactable)
            operations.append({"operation": "COMPACT_RECOVERY_BACKLOG", "report": report})

        self._gate(baseline_champion, stage="POST_LIFECYCLE_RECOVERY")
        after = self._lifecycle_counts()
        if (
            int(after["pending_unsealed_events"]) != 0
            or int(after["compactable_events"]) != 0
        ):
            self._fail(
                "NBOT_V383_LIFECYCLE_RECOVERY_INCOMPLETE",
                before=before,
                after=after,
                operations=operations,
            )
        return {
            "before": before,
            "operations": operations,
            "after": after,
        }

    def run(self, *, batch_events: int = 8, max_cycles: int = 1) -> dict[str, Any]:
        batch_events = int(batch_events)
        max_cycles = int(max_cycles)
        if batch_events <= 0 or batch_events > self.config.max_batch_selection_events:
            raise ValueError("NBOT_V383_BATCH_EVENTS_MUST_BE_1_TO_8")
        if max_cycles <= 0 or max_cycles > self.config.max_cycles_per_invocation:
            raise ValueError("NBOT_V383_MAX_CYCLES_OUT_OF_RANGE")

        with ResearchCatchupLock(self.lock_path):
            # Retention tables are an accepted V3.8.2 precondition.  Do not
            # silently initialize lifecycle state inside the catch-up command.
            retention = self.retention.audit()
            if not bool(retention.get("healthy")):
                self._fail("NBOT_V383_RETENTION_NOT_READY", retention=retention)

            baseline_champion = self._champion_fingerprint()
            start_gate = self._gate(baseline_champion, stage="START")
            recovery = self._recover_lifecycle(batch_events, baseline_champion)

            cycles: list[dict[str, Any]] = []
            final_status = "MAX_CYCLES_REACHED"

            for cycle_index in range(1, max_cycles + 1):
                pre_gate = self._gate(
                    baseline_champion,
                    stage=f"CYCLE_{cycle_index}_PRE_BUILD",
                    deep_research=False,
                    require_build_headroom=True,
                )
                before = self._lifecycle_counts()
                if (
                    int(before["pending_unsealed_events"]) != 0
                    or int(before["compactable_events"]) != 0
                ):
                    self._fail(
                        "NBOT_V383_LIFECYCLE_NOT_CLEAN_BEFORE_BUILD",
                        cycle=cycle_index,
                        counts=before,
                    )

                builds: dict[str, Any] = {}
                for component in ("features", "signals", "outcomes", "policies", "selection"):
                    try:
                        builds[component] = _jsonable(
                            self._build_component(component, batch_events)
                        )
                    except Exception as exc:
                        self._fail(
                            "NBOT_V383_BUILD_FAILED",
                            cycle=cycle_index,
                            component=component,
                            error_type=type(exc).__name__,
                            detail=str(exc),
                            completed_builds=builds,
                        )

                after_build = self._lifecycle_counts()
                new_events = int(after_build["pending_unsealed_events"])
                detail_delta = (
                    int(after_build["detailed_selection_events"])
                    - int(before["detailed_selection_events"])
                )

                if new_events == 0:
                    # Not an error: raw evidence may simply not have another
                    # fully mature 4-hour label/policy/selection event yet.
                    cycles.append({
                        "cycle": cycle_index,
                        "status": "WAIT_FOR_MATURE_EVIDENCE",
                        "before": before,
                        "builds": builds,
                        "after_build": after_build,
                        "selection_events_built": 0,
                        "pre_gate": pre_gate,
                    })
                    final_status = "WAIT_FOR_MATURE_EVIDENCE"
                    break

                if new_events > batch_events or detail_delta != new_events:
                    self._fail(
                        "NBOT_V383_SELECTION_DELTA_INVALID",
                        cycle=cycle_index,
                        batch_events=batch_events,
                        before=before,
                        after_build=after_build,
                        new_events=new_events,
                        detail_delta=detail_delta,
                    )

                maintain = self.retention.maintain(
                    seal_max_events=new_events,
                    compact_max_events=new_events,
                )
                after = self._lifecycle_counts()
                if int(after["pending_unsealed_events"]) != 0:
                    self._fail(
                        "NBOT_V383_SEAL_INCOMPLETE",
                        cycle=cycle_index,
                        after=after,
                        retention=maintain,
                    )
                ledger_delta = int(after["ledger_events"]) - int(before["ledger_events"])
                compact_delta = int(after["compacted_events"]) - int(before["compacted_events"])
                expected_detail = (
                    int(before["detailed_selection_events"])
                    + new_events
                    - compact_delta
                )
                if ledger_delta != new_events or int(after["detailed_selection_events"]) != expected_detail:
                    self._fail(
                        "NBOT_V383_LIFECYCLE_ACCOUNTING_MISMATCH",
                        cycle=cycle_index,
                        before=before,
                        after_build=after_build,
                        after=after,
                        ledger_delta=ledger_delta,
                        compact_delta=compact_delta,
                        expected_detail=expected_detail,
                    )

                protected_limit = (
                    RETENTION_CONFIG.frozen_detail_selection_events
                    + RETENTION_CONFIG.recent_detail_selection_events
                )
                if int(after["ledger_events"]) >= protected_limit:
                    if int(after["detailed_selection_events"]) > protected_limit:
                        self._fail(
                            "NBOT_V383_DETAILED_WORKING_SET_UNBOUNDED",
                            cycle=cycle_index,
                            after=after,
                            protected_limit=protected_limit,
                        )

                post_gate = self._gate(
                    baseline_champion,
                    stage=f"CYCLE_{cycle_index}_POST_MAINTAIN",
                )
                cycles.append({
                    "cycle": cycle_index,
                    "status": "PASS",
                    "before": before,
                    "builds": builds,
                    "after_build": after_build,
                    "selection_events_built": new_events,
                    "retention": maintain,
                    "after": after,
                    "ledger_delta": ledger_delta,
                    "compacted_delta": compact_delta,
                    "pre_gate": pre_gate,
                    "post_gate": post_gate,
                })

            final_counts = self._lifecycle_counts()
            final_gate = self._gate(
                baseline_champion, stage="FINAL", deep_research=False
            )
            return {
                "controller_version": self.config.controller_version,
                "authority": AUTHORITY,
                "healthy": True,
                "status": final_status,
                "batch_events": batch_events,
                "max_cycles": max_cycles,
                "completed_cycles": sum(cycle["status"] == "PASS" for cycle in cycles),
                "recovery": recovery,
                "baseline_champion": baseline_champion,
                "start_gate": start_gate,
                "cycles": cycles,
                "final_counts": final_counts,
                "final_gate": final_gate,
                "operating_live_bytes": self.config.operating_live_bytes,
                "min_build_headroom_bytes": self.config.min_build_headroom_bytes,
                "retention_hard_live_bytes": RETENTION_CONFIG.hard_live_bytes,
            }
