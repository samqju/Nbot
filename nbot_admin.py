#!/usr/bin/env python3
"""NBOT V3 Observation research administration CLI.

V3.4 research commands are intentionally Observation-only and LIVE-evidence
only.  They build/audit derived research state; none imports Execution or has
order authority.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

from nbot.common.logging import configure_logging, observation_log_paths
from nbot.communication.authorities import LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY
from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role
from nbot.observation.binance_public import BinanceUsdMPublicClient
from nbot.observation.champion import (
    MemoryWalkForwardChampionEvaluator,
    WalkForwardChampionEvaluator,
)
from nbot.observation.challengers import ContinuousChallengerCycle, CHALLENGER_PREFIX
from nbot.observation.governance import ModelGovernanceRegistry
from nbot.observation.market_regimes import MarketRegimeEvidence
from nbot.observation.operational_regimes import OperationalRegimeLedger
from nbot.observation.paper_champion import PaperChampionGate
from nbot.observation.research_champion import ResearchChampionPromotion
from nbot.observation.catchup import (
    BoundedResearchCatchupController,
    ResearchCatchupError,
)
from nbot.observation.config import observation_config_for_profile
from nbot.observation.database import EvidenceDatabase
from nbot.observation.features import CanonicalFeatureStore
from nbot.observation.learning import ContinuousLearningFoundation
from nbot.observation.epoch import (
    CUTOVER_CONFIRMATION,
    ResearchEpochProcessor,
    cutover_to_fresh_raw_generation,
)
from nbot.observation.research_memory import ResearchMemoryStore
from nbot.observation.outcomes import FuturePathStore
from nbot.observation.retention import ResearchRetentionManager
from nbot.observation.policies import ExitPolicyLab
from nbot.observation.selection import EntrySelectionLab
from nbot.observation.signals import ResearchSignalStore
from nbot.operator.telegram import TelegramClient, TelegramConfig
from nbot.observation.scalability import (
    REFERENCE_RESET_CONFIRMATION,
    ResearchScalabilityRecovery,
    verify_ridge_reference_equivalence,
)


ROOT = Path(__file__).resolve().parent
RESEARCH_PROFILE = "live-paper"
V384_GENERATION = "V3_8_4_EPOCH_GENERATION_V1"
V384_MEMORY_PATH = Path("data/observation/live/research_memory.db")
V384_EPOCH_LOCK_PATH = Path("runtime/observation/live/research_epoch.lock")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, tuple):
        return list(value)
    return value


def _emit(value: Any) -> int:
    print(json.dumps(_jsonable(value), indent=2, sort_keys=True))
    return 0


def _db() -> EvidenceDatabase:
    profile = get_profile(RESEARCH_PROFILE)
    config = observation_config_for_profile(profile)
    if config.market_environment != "LIVE":
        raise ValueError("NBOT_ADMIN_RESEARCH_REQUIRES_LIVE_EVIDENCE")
    return EvidenceDatabase(config)


def _future_store() -> FuturePathStore:
    db = _db()
    return FuturePathStore(db, BinanceUsdMPublicClient(db.config))


def _memory() -> ResearchMemoryStore:
    return ResearchMemoryStore(V384_MEMORY_PATH)


def _v384_active() -> bool:
    if not V384_MEMORY_PATH.exists():
        return False
    try:
        return _memory().metadata().get("memory_version") == "RESEARCH_MEMORY_V1"
    except Exception:
        return False




def _release_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _challenger_cycle() -> ContinuousChallengerCycle:
    if not _v384_active():
        raise RuntimeError("NBOT_V391_COMPACT_RESEARCH_MEMORY_REQUIRED")
    return ContinuousChallengerCycle(_memory(), release_sha=_release_sha())


def _selective_ml():
    from nbot.observation.selective_ml_v3 import SelectiveMLManager
    if not _v384_active():
        raise RuntimeError("SELECTIVE_ML_COMPACT_RESEARCH_MEMORY_REQUIRED")
    return SelectiveMLManager(_memory(), _db(), release_sha=_release_sha())


def _governance() -> ModelGovernanceRegistry:
    if not _v384_active():
        raise RuntimeError("NBOT_V392_COMPACT_RESEARCH_MEMORY_REQUIRED")
    return ModelGovernanceRegistry(
        _memory(), ROOT / "data/observation/live/model_artifacts/v39"
    )


def _market_regimes() -> MarketRegimeEvidence:
    if not _v384_active():
        raise RuntimeError("NBOT_V394_COMPACT_RESEARCH_MEMORY_REQUIRED")
    return MarketRegimeEvidence(_memory())


def _operational_regimes() -> OperationalRegimeLedger:
    if not _v384_active():
        raise RuntimeError("NBOT_V395_COMPACT_RESEARCH_MEMORY_REQUIRED")
    return OperationalRegimeLedger(_memory())


def _paper_champion_gate() -> PaperChampionGate:
    if not _v384_active():
        raise RuntimeError("NBOT_V396_COMPACT_RESEARCH_MEMORY_REQUIRED")
    return PaperChampionGate(_memory())


def _research_champion_promotion() -> ResearchChampionPromotion:
    if not _v384_active():
        raise RuntimeError("NBOT_V396B_COMPACT_RESEARCH_MEMORY_REQUIRED")
    return ResearchChampionPromotion(_memory(), _governance())


def _legacy_mixed_research_guard() -> None:
    if _v384_active():
        raise RuntimeError(
            "NBOT_V384_LEGACY_MIXED_RESEARCH_DISABLED_USE_RESEARCH_EPOCH"
        )


def _epoch_processor() -> ResearchEpochProcessor:
    return ResearchEpochProcessor(_db(), _memory(), ROOT)


@contextmanager
def _research_epoch_command_lock():
    path = ROOT / V384_EPOCH_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("NBOT_V384_EPOCH_COMMAND_LOCK_HELD") from exc
        try:
            yield
        finally:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _build_result(component: str, max_events: int, rebuild: bool) -> Any:
    _legacy_mixed_research_guard()
    db = _db()
    if component == "features":
        return CanonicalFeatureStore(db).build(max_events=max_events, rebuild=rebuild)
    if component == "signals":
        return ResearchSignalStore(db).build(max_events=max_events, rebuild=rebuild)
    if component == "outcomes":
        return _future_store().build(max_events=max_events, rebuild=rebuild)
    if component == "policies":
        return ExitPolicyLab(db).build(max_events=max_events, rebuild=rebuild)
    if component == "selection":
        return EntrySelectionLab(db).build(max_events=max_events, rebuild=rebuild)
    raise ValueError("NBOT_ADMIN_BUILD_COMPONENT_INVALID")


def _audit_result(component: str) -> dict[str, Any]:
    if component == "champion" and _v384_active():
        return MemoryWalkForwardChampionEvaluator(_memory()).audit()
    _legacy_mixed_research_guard()
    db = _db()
    if component == "features":
        return CanonicalFeatureStore(db).audit()
    if component == "signals":
        return ResearchSignalStore(db).audit()
    if component == "outcomes":
        return _future_store().audit()
    if component == "policies":
        return ExitPolicyLab(db).audit()
    if component == "selection":
        return EntrySelectionLab(db).audit()
    if component == "champion":
        return WalkForwardChampionEvaluator(db).audit()
    if component == "learning":
        return ContinuousLearningFoundation(db).audit()
    if component == "retention":
        return ResearchRetentionManager(db).audit()
    raise ValueError("NBOT_ADMIN_AUDIT_COMPONENT_INVALID")


def cmd_build(args: argparse.Namespace) -> int:
    return _emit(_build_result(args.component, args.max_events, args.rebuild))


def cmd_audit(args: argparse.Namespace) -> int:
    report = _audit_result(args.component)
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2


def cmd_report(args: argparse.Namespace) -> int:
    if args.component == "champion" and _v384_active():
        return _emit(MemoryWalkForwardChampionEvaluator(_memory()).report())
    db = _db()
    if args.component == "policies":
        return _emit(ExitPolicyLab(db).report())
    if args.component == "selection":
        return _emit(EntrySelectionLab(db).report())
    if args.component == "champion":
        return _emit(WalkForwardChampionEvaluator(db).report())
    raise ValueError("NBOT_ADMIN_REPORT_COMPONENT_INVALID")


def cmd_champion_evaluate(args: argparse.Namespace) -> int:
    if _v384_active():
        if args.rebuild:
            raise RuntimeError("NBOT_V39_COMPACT_CHAMPION_REBUILD_FORBIDDEN")
        return _emit(MemoryWalkForwardChampionEvaluator(_memory()).evaluate())
    return _emit(WalkForwardChampionEvaluator(_db()).evaluate(rebuild=args.rebuild))


def cmd_champion_status(_args: argparse.Namespace) -> int:
    if _v384_active():
        return _emit(MemoryWalkForwardChampionEvaluator(_memory()).status())
    return _emit(WalkForwardChampionEvaluator(_db()).status())


def cmd_learning_init(_args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    foundation = ContinuousLearningFoundation(_db())
    foundation.initialize()
    return _emit(foundation.status())


def cmd_learning_status(_args: argparse.Namespace) -> int:
    if _v384_active():
        return _emit({
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
            "status": "V3_9_CONTINUOUS_CHALLENGER_LEARNING_ENABLED",
            "memory": _memory().status(),
            "champion": MemoryWalkForwardChampionEvaluator(_memory()).status(),
            "challengers": _challenger_cycle().status(),
            "governance": _governance().status(),
            "market_regimes": _market_regimes().status(),
            "research_champion_promotion": _research_champion_promotion().review(),
            "paper_champion": _paper_champion_gate().status(),
            "legacy_learning_foundation": _memory().artifact("learning_foundations"),
            "legacy_model_registry": _memory().artifact("model_registry"),
            "legacy_challenger_registry": _memory().artifact("challenger_registry"),
        })
    return _emit(ContinuousLearningFoundation(_db()).status())






def _challenger_for_training_cutoff(
    memory: ResearchMemoryStore, training_cutoff_event_ms: int
) -> dict[str, Any] | None:
    cutoff = int(training_cutoff_event_ms)
    matches = [
        record
        for record in memory.list_artifacts(prefix=CHALLENGER_PREFIX)
        if int(record["payload"].get("training_cutoff_event_ms", -1)) == cutoff
    ]
    if len(matches) > 1:
        raise RuntimeError("NBOT_V39_EPOCH_TRANSITION_DUPLICATE_CUTOFF_CHALLENGER")
    return None if not matches else matches[0]


def _run_epoch_challenger_transition() -> dict[str, Any]:
    """Drain exactly one durable epoch->challenger transition.

    A challenger artifact whose immutable training cutoff equals the epoch end
    is the idempotency anchor.  If a prior attempt crashed after creating that
    artifact, retry skips the challenger cycle, replays governance/regime sync,
    and consumes the same transition rather than creating another challenger.
    """
    memory = _memory()
    pending = memory.pending_challenger_transition()
    if pending is None:
        return {
            "transition_version": "V39_EPOCH_CHALLENGER_TRANSITION_V1",
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
            "healthy": True,
            "status": "NO_PENDING_EPOCH_TRANSITION",
        }

    epoch_id = str(pending["epoch_id"])
    target_end_ms = int(pending["target_end_ms"])
    attempt = memory.begin_challenger_transition_attempt(epoch_id)
    try:
        anchored = _challenger_for_training_cutoff(memory, target_end_ms)
        cycle_report: dict[str, Any]
        replay_detected = anchored is not None
        if anchored is None:
            cycle_report = _challenger_cycle().cycle()
            anchored = _challenger_for_training_cutoff(memory, target_end_ms)
            if anchored is None and cycle_report.get("action") == "EVALUATE_WAIT":
                # New market evidence must keep accumulating while an existing
                # frozen model waits for its independent future test window.
                anchored = memory.artifact(CHALLENGER_PREFIX + cycle_report["challenger_version"])
            if anchored is None:
                raise RuntimeError(
                    "NBOT_V39_EPOCH_TRANSITION_CHALLENGER_NOT_ANCHORED:"
                    f"{cycle_report.get('action', cycle_report.get('status', 'UNKNOWN'))}"
                )
        else:
            cycle_report = {
                "action": "REPLAY_ANCHORED_CHALLENGER",
                "status": "SKIP_DUPLICATE_CHALLENGER_CYCLE",
                "challenger_version": anchored["payload"].get("challenger_version"),
                "training_cutoff_event_ms": target_end_ms,
                "authority": "RESEARCH_ONLY_NO_EXECUTION",
                "automatic_promotion": False,
            }

        challenger = anchored["payload"]
        challenger_version = str(challenger["challenger_version"])
        challenger_cutoff = int(challenger["training_cutoff_event_ms"])
        if challenger_cutoff > target_end_ms:
            raise RuntimeError("NBOT_V39_EPOCH_TRANSITION_CUTOFF_MISMATCH")

        governance = _governance().sync()
        market_regimes = _market_regimes().sync()
        completion = memory.complete_challenger_transition(
            epoch_id=epoch_id,
            challenger_version=challenger_version,
            training_cutoff_event_ms=challenger_cutoff,
        )
        return {
            "transition_version": "V39_EPOCH_CHALLENGER_TRANSITION_V1",
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
            "healthy": True,
            "status": "PASS",
            "epoch_id": epoch_id,
            "target_end_ms": target_end_ms,
            "attempt_count": int(attempt["attempt_count"]),
            "replay_detected": replay_detected,
            "challenger_version": challenger_version,
            "cycle": cycle_report,
            "governance_sync": governance,
            "market_regime_sync": market_regimes,
            "completion": completion,
        }
    except Exception as exc:
        memory.fail_challenger_transition(
            epoch_id, f"{type(exc).__name__}:{exc}"
        )
        raise


def cmd_challenger_cycle(_args: argparse.Namespace) -> int:
    research_log = configure_logging(
        role="OBSERVATION", profile=RESEARCH_PROFILE,
        log_path=observation_log_paths(ROOT)["research"], component="research",
    )
    try:
        with _research_epoch_command_lock():
            report = _run_epoch_challenger_transition()
    except Exception:
        research_log.exception("V39_EPOCH_CHALLENGER_TRANSITION_FAILED")
        raise
    research_log.info(
        "V39_EPOCH_CHALLENGER_TRANSITION_RESULT %s",
        json.dumps(report, sort_keys=True, default=_jsonable),
    )
    return _emit(report)


def cmd_challenger_status(_args: argparse.Namespace) -> int:
    report = _challenger_cycle().status()
    report["epoch_transition"] = _memory().challenger_transition_status()
    return _emit(report)


def cmd_selective_ml_train(args: argparse.Namespace) -> int:
    return _emit(_selective_ml().train_if_needed(force=bool(args.force)))


def cmd_selective_ml_status(_args: argparse.Namespace) -> int:
    return _emit(_selective_ml().status())


def cmd_shadow_report(args: argparse.Namespace) -> int:
    from nbot.observation.shadow import shadow_report
    from nbot.common.atomic_io import atomic_write_text
    sha = args.release_sha or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    text = shadow_report(_db(), release_sha=sha)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, text, mode=0o600)
    print(text)
    return 0


def cmd_paper_learning_report(args: argparse.Namespace) -> int:
    from nbot.observation.paper_learning_report import paper_learning_report
    from nbot.common.atomic_io import atomic_write_text
    sha = args.release_sha or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    text = paper_learning_report(_db(), release_sha=sha, now_ms=int(time.time()*1000))
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, text, mode=0o600)
    print(text)
    return 0


def cmd_learning_report(args: argparse.Namespace) -> int:
    from nbot.observation.learning_report import learning_report
    from nbot.common.atomic_io import atomic_write_text
    text = learning_report(_memory())
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, text, mode=0o600)
    print(text)
    return 0


def cmd_challenger_audit(_args: argparse.Namespace) -> int:
    report = _challenger_cycle().audit()
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2




def cmd_governance_sync(_args: argparse.Namespace) -> int:
    return _emit(_governance().sync())


def cmd_governance_status(_args: argparse.Namespace) -> int:
    return _emit(_governance().status())


def cmd_governance_audit(_args: argparse.Namespace) -> int:
    report = _governance().audit()
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2


def cmd_research_champion_sync(_args: argparse.Namespace) -> int:
    return _emit(_research_champion_promotion().sync())


def cmd_research_champion_review(_args: argparse.Namespace) -> int:
    return _emit(_research_champion_promotion().review())


def cmd_research_champion_promote(args: argparse.Namespace) -> int:
    return _emit(_research_champion_promotion().promote(confirm=args.confirm))


def cmd_research_champion_audit(_args: argparse.Namespace) -> int:
    report = _research_champion_promotion().audit()
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2


def cmd_market_regime_sync(_args: argparse.Namespace) -> int:
    return _emit(_market_regimes().sync())


def cmd_market_regime_status(_args: argparse.Namespace) -> int:
    return _emit(_market_regimes().status())


def cmd_market_regime_audit(_args: argparse.Namespace) -> int:
    report = _market_regimes().audit()
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2


def cmd_operational_regime_sync(_args: argparse.Namespace) -> int:
    return _emit(_operational_regimes().sync())


def cmd_operational_regime_status(_args: argparse.Namespace) -> int:
    return _emit(_operational_regimes().status())


def cmd_operational_regime_audit(_args: argparse.Namespace) -> int:
    report = _operational_regimes().audit()
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2


def cmd_paper_champion_sync(_args: argparse.Namespace) -> int:
    return _emit(_paper_champion_gate().sync())


def cmd_paper_champion_status(_args: argparse.Namespace) -> int:
    return _emit(_paper_champion_gate().status())


def cmd_paper_champion_audit(_args: argparse.Namespace) -> int:
    report = _paper_champion_gate().audit()
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2

def cmd_retention_init(_args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    manager = ResearchRetentionManager(_db())
    manager.initialize()
    return _emit(manager.status())

def cmd_retention_status(_args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    return _emit(ResearchRetentionManager(_db()).status())


def cmd_retention_maintain(args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    report = ResearchRetentionManager(_db()).maintain(
        seal_max_events=args.seal_max_events,
        compact_max_events=args.compact_max_events,
    )
    return _emit(report)

def cmd_scalability_status(_args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    return _emit(ResearchScalabilityRecovery(_db()).status())


def cmd_scalability_verify_reference(args: argparse.Namespace) -> int:
    report = verify_ridge_reference_equivalence(
        Path(args.reference_db),
        args.reference_sha256,
        score_tolerance=args.score_tolerance,
    )
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2


def cmd_scalability_reset_derived(args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    report = ResearchScalabilityRecovery(_db()).reset_derived(
        reference_db=Path(args.reference_db),
        reference_sha256=args.reference_sha256,
        confirmation=args.confirm,
    )
    return _emit(report)




def cmd_research_memory_migrate(args: argparse.Namespace) -> int:
    memory = _memory()
    memory.initialize(
        generation=V384_GENERATION,
        generation_floor_ms=int(args.generation_floor_ms),
    )
    return _emit(memory.migrate_legacy(
        Path(args.legacy_db), source_generation="V3_8_3_LEGACY_LEDGER",
    ))


def cmd_research_memory_status(_args: argparse.Namespace) -> int:
    return _emit(_memory().status())


def cmd_research_memory_init(_args: argparse.Namespace) -> int:
    """Initialize a fresh server without resetting or importing existing memory."""
    with _research_epoch_command_lock():
        memory = _memory()
        if memory.path.exists():
            if memory.metadata().get("memory_version") != "RESEARCH_MEMORY_V1":
                raise RuntimeError("RESEARCH_MEMORY_EXISTING_STORE_REQUIRES_REVIEW")
            return _emit({"status": "ALREADY_INITIALIZED", "metadata": memory.metadata()})
        raw = _db()
        raw.initialize()
        with raw.connection() as conn:
            earliest = conn.execute("SELECT MIN(event_open_ms) FROM market_events WHERE status='COMPLETE'").fetchone()[0]
        interval = raw.config.candle_interval_ms
        # Reserve enough past history before the first research target. Never
        # select the very first candle as a target that can never gain history.
        start = int(earliest) if earliest is not None else (int(time.time() * 1000) // interval) * interval
        memory.initialize(generation=V384_GENERATION, generation_floor_ms=start + 48 * interval)
        return _emit({"status": "INITIALIZED", "metadata": memory.metadata(), "order_authority": "NONE"})


def cmd_research_epoch_status(_args: argparse.Namespace) -> int:
    processor = _epoch_processor()
    memory = _memory()
    return _emit({
        "epoch_version": "RESEARCH_EPOCH_V1",
        "authority": "RESEARCH_ONLY_NO_EXECUTION",
        "plan": asdict(processor.plan()),
        "memory": memory.status(),
        "challenger_transition": memory.challenger_transition_status(),
    })


def cmd_research_epoch_run(args: argparse.Namespace) -> int:
    research_log = configure_logging(
        role="OBSERVATION", profile=RESEARCH_PROFILE,
        log_path=observation_log_paths(ROOT)["research"], component="research",
    )
    telegram = TelegramClient(
        TelegramConfig.from_environment(os.environ, prefix="OBSERVATION"), logger=research_log
    )
    try:
        with _research_epoch_command_lock():
            processor = _epoch_processor()
            memory = _memory()
            pending_before = memory.pending_challenger_transition()
            if pending_before is not None:
                transition = _run_epoch_challenger_transition()
                report = {
                    "epoch_version": "RESEARCH_EPOCH_V1",
                    "authority": "RESEARCH_ONLY_NO_EXECUTION",
                    "healthy": True,
                    "status": "PASS_PENDING_CHALLENGER_RECOVERY",
                    "challenger_transition_run": transition,
                    "plan": asdict(processor.plan()),
                    "memory": memory.status(),
                }
                if args.prune_raw:
                    report["raw_prune"] = processor.prune_raw()
            else:
                report = processor.run_once()
                if report.get("status") == "PASS":
                    report["challenger_transition_run"] = _run_epoch_challenger_transition()
                    try:
                        report["selective_ml"] = _selective_ml().train_if_needed()
                    except Exception as ml_exc:
                        # Selective ML is experimental and must never make the
                        # durable base research epoch disappear or corrupt memory.
                        research_log.exception("SELECTIVE_ML_TRAIN_FAILED")
                        report["selective_ml"] = {
                            "status": "ERROR",
                            "error": type(ml_exc).__name__ + ":" + str(ml_exc)[:240],
                        }
                    if args.prune_raw:
                        report["raw_prune"] = processor.prune_raw()
    except Exception as exc:
        research_log.exception("RESEARCH_EPOCH_FAILED")
        telegram.send_critical(
            "RESEARCH EPOCH FAILED", f"{type(exc).__name__}: {exc}\nOrder authority: NONE"
        )
        raise
    research_log.info("RESEARCH_EPOCH_RESULT %s", json.dumps(report, sort_keys=True, default=_jsonable))
    if report.get("status") == "PASS":
        memory_status = report.get("memory") if isinstance(report.get("memory"), dict) else {}
        transition = (
            report.get("challenger_transition_run")
            if isinstance(report.get("challenger_transition_run"), dict)
            else {}
        )
        telegram.send_info(
            "RESEARCH EPOCH COMPLETE",
            f"Status: PASS\nEpoch: {report.get('epoch_id', 'N/A')}\n"
            f"Memory events: {memory_status.get('events', 'N/A')}\n"
            f"Challenger transition: {transition.get('status', 'N/A')}\n"
            "Authority: RESEARCH_ONLY_NO_EXECUTION",
        )
    elif report.get("status") == "PASS_PENDING_CHALLENGER_RECOVERY":
        research_log.info(
            "V39_PENDING_CHALLENGER_TRANSITION_RECOVERED %s",
            json.dumps(report.get("challenger_transition_run", {}), sort_keys=True, default=_jsonable),
        )
    elif not bool(report.get("healthy")):
        telegram.send_critical(
            "RESEARCH EPOCH UNHEALTHY",
            f"Status: {report.get('status')}\nAuthority: RESEARCH_ONLY_NO_EXECUTION",
        )
    # WAIT_FOR_MATURE_EPOCH is intentionally not a Telegram event; the 15-minute
    # timer may emit it frequently and operator alerting must remain low-noise.
    _emit(report)
    return 0 if bool(report.get("healthy")) else 2


def cmd_research_raw_prune(_args: argparse.Namespace) -> int:
    with _research_epoch_command_lock():
        report = _epoch_processor().prune_raw()
    return _emit(report)


def cmd_research_generation_cutover(args: argparse.Namespace) -> int:
    report = cutover_to_fresh_raw_generation(
        _db(),
        _memory(),
        ROOT,
        Path(args.artifact_dir),
        generation=V384_GENERATION,
        confirmation=args.confirm,
    )
    return _emit(report)


def cmd_research_catchup(args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    controller = BoundedResearchCatchupController(_db(), ROOT)
    try:
        report = controller.run(
            batch_events=args.batch_events,
            max_cycles=args.max_cycles,
        )
    except ResearchCatchupError as exc:
        payload = dict(exc.report)
        if not payload:
            payload = {
                "controller_version": "BOUNDED_RESEARCH_CATCHUP_V1",
                "authority": "RESEARCH_ONLY_NO_EXECUTION",
                "healthy": False,
                "error": exc.code,
            }
        _emit(payload)
        return 2
    except KeyboardInterrupt:
        _emit({
            "controller_version": "BOUNDED_RESEARCH_CATCHUP_V1",
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
            "healthy": False,
            "status": "OPERATOR_STOPPED",
            "recovery": "NEXT_INVOCATION_SEALS_AT_MOST_ONE_PENDING_PROVEN_BATCH_BEFORE_NEW_WORK",
        })
        return 130
    return _emit(report)

def cmd_live_paper_canary_report(_args: argparse.Namespace) -> int:
    """Read-only V3.8 operational-canary trace/degradation report."""
    db = _db()
    with db.connection() as conn:
        proposal_rows = conn.execute(
            """
            SELECT proposal_id,proposal_json,first_served_at_ms,last_served_at_ms,
                   served_count,invalidated_at_ms,invalidation_reason,completed_outcome_id
            FROM served_execution_proposals
            WHERE profile='live-paper'
            ORDER BY first_served_at_ms
            """
        ).fetchall()
        veto_rows = conn.execute(
            """SELECT proposal_id,reason,received_at_ms FROM execution_veto_feedback
               ORDER BY received_at_ms"""
        ).fetchall()
        outcome_rows = conn.execute(
            """SELECT outcome_id,proposal_id,received_at_ms,payload_json
               FROM received_execution_outcomes
               WHERE profile='live-paper' ORDER BY received_at_ms"""
        ).fetchall()

    proposals = []
    proposal_ids = set()
    for row in proposal_rows:
        payload = json.loads(row[1])
        if payload.get("entry_authority") != LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY:
            continue
        proposal_ids.add(str(row[0]))
        proposals.append({
            "proposal_id": str(row[0]),
            "market_event_id": payload.get("market_event_id"),
            "symbol": payload.get("symbol"),
            "side": payload.get("side"),
            "generated_at_ms": payload.get("generated_at_ms"),
            "expires_at_ms": payload.get("expires_at_ms"),
            "reference_price": payload.get("reference_price"),
            "expected_after_cost_net_r": payload.get("expected_after_cost_net_r"),
            "first_served_at_ms": int(row[2]),
            "last_served_at_ms": int(row[3]),
            "served_count": int(row[4]),
            "invalidated_at_ms": row[5],
            "invalidation_reason": row[6],
            "completed_outcome_id": row[7],
        })

    vetoes = [
        {"proposal_id": str(row[0]), "reason": str(row[1]), "received_at_ms": int(row[2])}
        for row in veto_rows if str(row[0]) in proposal_ids
    ]
    outcomes = []
    for row in outcome_rows:
        if str(row[1]) not in proposal_ids:
            continue
        payload = json.loads(row[3])
        context = payload.get("experiment_context") or {}
        operational = dict(context.get("execution_operational") or {})
        if operational:
            operational["observation_recorded_at_ms"] = int(row[2])
            started = operational.get("outcome_delivery_started_at_ms")
            if isinstance(started, int):
                operational["outcome_transport_to_record_ms"] = max(0, int(row[2]) - started)
            closed = payload.get("closed_timestamp_ms")
            if isinstance(closed, int):
                operational["close_to_observation_record_ms"] = max(0, int(row[2]) - closed)
        outcomes.append({
            "outcome_id": str(row[0]),
            "proposal_id": str(row[1]),
            "received_at_ms": int(row[2]),
            "symbol": payload.get("symbol"),
            "side": payload.get("side"),
            "realized_pnl_usd": payload.get("realized_pnl_usd"),
            "realized_r": payload.get("r_multiple"),
            "mae_r": payload.get("mae_r"),
            "mfe_r": payload.get("mfe_r"),
            "holding_seconds": payload.get("holding_seconds"),
            "exit_reason": payload.get("exit_reason"),
            "operational": operational,
        })

    economic_ready = bool(outcomes) and all(
        item.get("operational", {}).get("expected_after_cost_net_r") is not None
        for item in outcomes
    )
    return _emit({
        "phase": "V3.8",
        "profile": "live-paper",
        "authority": LIVE_PAPER_OPERATIONAL_CANARY_AUTHORITY,
        "authority_class": "LIVE_PAPER_OPERATIONAL_ONLY",
        "research_evidence": False,
        "economic_claim": False,
        "proposals_served": len(proposals),
        "veto_count": len(vetoes),
        "completed_outcomes": len(outcomes),
        "economic_comparison_ready": economic_ready,
        "economic_deferred_reason": (
            None if economic_ready else "NO_RESEARCH_CHAMPION_EXPECTED_R_IN_OPERATIONAL_CANARY"
        ),
        "proposals": proposals[-20:],
        "vetoes": vetoes[-20:],
        "outcomes": outcomes[-20:],
    })


def cmd_research_audit(_args: argparse.Namespace) -> int:
    reports = {
        component: _audit_result(component)
        for component in (
            "features",
            "signals",
            "outcomes",
            "policies",
            "selection",
            "champion",
            "learning",
            "retention",
        )
    }
    healthy = all(bool(report.get("healthy")) for report in reports.values())
    payload = {
        "profile": RESEARCH_PROFILE,
        "market_environment": "LIVE",
        "healthy": healthy,
        "reports": reports,
    }
    _emit(payload)
    return 0 if healthy else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nbot_admin.py")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build a derived V3.4 research layer")
    build.add_argument(
        "component",
        choices=("features", "signals", "outcomes", "policies", "selection"),
    )
    build.add_argument("--max-events", type=int, default=0)
    build.add_argument("--rebuild", action="store_true")
    build.set_defaults(func=cmd_build)

    audit = sub.add_parser("audit", help="read-only audit a V3.4 research layer")
    audit.add_argument(
        "component",
        choices=(
            "features",
            "signals",
            "outcomes",
            "policies",
            "selection",
            "champion",
            "learning",
            "retention",
        ),
    )
    audit.set_defaults(func=cmd_audit)

    report = sub.add_parser("report")
    report.add_argument("component", choices=("policies", "selection", "champion"))
    report.set_defaults(func=cmd_report)

    champion = sub.add_parser("champion-evaluate")
    champion.add_argument("--rebuild", action="store_true")
    champion.set_defaults(func=cmd_champion_evaluate)

    champion_status = sub.add_parser("champion-status")
    champion_status.set_defaults(func=cmd_champion_status)

    learning_init = sub.add_parser("learning-init")
    learning_init.set_defaults(func=cmd_learning_init)

    learning_status = sub.add_parser("learning-status")
    learning_status.set_defaults(func=cmd_learning_status)

    challenger_cycle = sub.add_parser(
        "challenger-cycle",
        help="drain one durable V3.9 epoch-triggered challenger transition",
    )
    challenger_cycle.set_defaults(func=cmd_challenger_cycle)

    challenger_status = sub.add_parser("challenger-status")
    challenger_status.set_defaults(func=cmd_challenger_status)

    selective_ml_train = sub.add_parser(
        "selective-ml-train",
        help="train/update the bounded live-paper selective ML artifact",
    )
    selective_ml_train.add_argument("--force", action="store_true")
    selective_ml_train.set_defaults(func=cmd_selective_ml_train)

    selective_ml_status = sub.add_parser(
        "selective-ml-status",
        help="show selective ML dependency, artifact and validation status",
    )
    selective_ml_status.set_defaults(func=cmd_selective_ml_status)

    challenger_audit = sub.add_parser("challenger-audit")
    challenger_audit.set_defaults(func=cmd_challenger_audit)

    governance_sync = sub.add_parser(
        "governance-sync",
        help="materialize/synchronize V3.9.2 model registry and V3.9.3 rolling reports",
    )
    governance_sync.set_defaults(func=cmd_governance_sync)

    governance_status = sub.add_parser("governance-status")
    governance_status.set_defaults(func=cmd_governance_status)

    governance_audit = sub.add_parser("governance-audit")
    governance_audit.set_defaults(func=cmd_governance_audit)

    research_champion_sync = sub.add_parser(
        "research-champion-sync",
        help="freeze/materialize the V3.9.6B Research Champion promotion contract",
    )
    research_champion_sync.set_defaults(func=cmd_research_champion_sync)

    research_champion_review = sub.add_parser("research-champion-review")
    research_champion_review.set_defaults(func=cmd_research_champion_review)

    research_champion_promote = sub.add_parser(
        "research-champion-promote",
        help="explicitly promote the model from the frozen eligible three-window basis",
    )
    research_champion_promote.add_argument("--confirm", required=True)
    research_champion_promote.set_defaults(func=cmd_research_champion_promote)

    research_champion_audit = sub.add_parser("research-champion-audit")
    research_champion_audit.set_defaults(func=cmd_research_champion_audit)

    market_regime_sync = sub.add_parser(
        "market-regime-sync",
        help="materialize immutable V3.9.4 market-regime companion reports",
    )
    market_regime_sync.set_defaults(func=cmd_market_regime_sync)

    market_regime_status = sub.add_parser("market-regime-status")
    market_regime_status.set_defaults(func=cmd_market_regime_status)

    market_regime_audit = sub.add_parser("market-regime-audit")
    market_regime_audit.set_defaults(func=cmd_market_regime_audit)

    operational_regime_sync = sub.add_parser(
        "operational-regime-sync",
        help="initialize the V3.9.5 operational-regime evidence ledger",
    )
    operational_regime_sync.set_defaults(func=cmd_operational_regime_sync)

    operational_regime_status = sub.add_parser("operational-regime-status")
    operational_regime_status.set_defaults(func=cmd_operational_regime_status)

    operational_regime_audit = sub.add_parser("operational-regime-audit")
    operational_regime_audit.set_defaults(func=cmd_operational_regime_audit)

    paper_champion_sync = sub.add_parser(
        "paper-champion-sync",
        help="freeze/materialize the V3.9.6A Paper Champion acceptance contract",
    )
    paper_champion_sync.set_defaults(func=cmd_paper_champion_sync)

    paper_champion_status = sub.add_parser("paper-champion-status")
    paper_champion_status.set_defaults(func=cmd_paper_champion_status)

    paper_champion_audit = sub.add_parser("paper-champion-audit")
    paper_champion_audit.set_defaults(func=cmd_paper_champion_audit)

    research_audit = sub.add_parser("research-audit")
    research_audit.set_defaults(func=cmd_research_audit)

    canary_report = sub.add_parser(
        "live-paper-canary-report",
        help="read-only V3.8 LIVE/PAPER operational canary trace/degradation report",
    )
    canary_report.set_defaults(func=cmd_live_paper_canary_report)

    shadow_parser = sub.add_parser("shadow-report", help="separate read-only shadow candidate results")
    shadow_parser.add_argument("--output", help="also save a private Markdown report")
    shadow_parser.add_argument("--release-sha", help="older release cohort; default current Git commit")
    shadow_parser.set_defaults(func=cmd_shadow_report)

    paper_report = sub.add_parser("paper-learning-report", help="read-only settled paper-trade learning report")
    paper_report.add_argument("--output", help="also save a private Markdown report")
    paper_report.add_argument("--release-sha", help="review an older release cohort; default is current Git commit")
    paper_report.set_defaults(func=cmd_paper_learning_report)

    learning_report = sub.add_parser("learning-report", help="explain model progress and rejection reasons in plain English")
    learning_report.add_argument("--output", help="also save a private Markdown report")
    learning_report.set_defaults(func=cmd_learning_report)

    memory_init = sub.add_parser("research-memory-init", help="initialize fresh permanent learning memory without deleting data")
    memory_init.set_defaults(func=cmd_research_memory_init)

    memory_migrate = sub.add_parser(
        "research-memory-migrate",
        help="initialize V3.8.4 compact research memory from the accepted legacy ledger",
    )
    memory_migrate.add_argument("--legacy-db", required=True)
    memory_migrate.add_argument("--generation-floor-ms", type=int, required=True)
    memory_migrate.set_defaults(func=cmd_research_memory_migrate)

    memory_status = sub.add_parser("research-memory-status")
    memory_status.set_defaults(func=cmd_research_memory_status)

    epoch_status = sub.add_parser("research-epoch-status")
    epoch_status.set_defaults(func=cmd_research_epoch_status)

    epoch_run = sub.add_parser(
        "research-epoch-run",
        help="process one mature 96-event epoch in a disposable research workspace",
    )
    epoch_run.add_argument("--prune-raw", action="store_true")
    epoch_run.set_defaults(func=cmd_research_epoch_run)

    raw_prune = sub.add_parser("research-raw-prune")
    raw_prune.set_defaults(func=cmd_research_raw_prune)

    generation_cutover = sub.add_parser(
        "research-generation-cutover",
        help="one-time V3.8.4 clean reset to empty raw collector DB plus empty compact memory",
    )
    generation_cutover.add_argument("--artifact-dir", required=True)
    generation_cutover.add_argument("--confirm", required=True)
    generation_cutover.set_defaults(func=cmd_research_generation_cutover)

    research_catchup = sub.add_parser(
        "research-catchup",
        help="run bounded V3.8.3 LIVE research catch-up with retention gates",
    )
    research_catchup.add_argument("--batch-events", type=int, default=8)
    research_catchup.add_argument("--max-cycles", type=int, default=1)
    research_catchup.set_defaults(func=cmd_research_catchup)

    retention_init = sub.add_parser("retention-init")
    retention_init.set_defaults(func=cmd_retention_init)

    retention_status = sub.add_parser("retention-status")
    retention_status.set_defaults(func=cmd_retention_status)

    retention_maintain = sub.add_parser("retention-maintain")
    retention_maintain.add_argument("--seal-max-events", type=int, default=32)
    retention_maintain.add_argument("--compact-max-events", type=int, default=8)
    retention_maintain.set_defaults(func=cmd_retention_maintain)

    scalability_status = sub.add_parser("scalability-status")
    scalability_status.set_defaults(func=cmd_scalability_status)

    scalability_verify = sub.add_parser("scalability-verify-reference")
    scalability_verify.add_argument("--reference-db", required=True)
    scalability_verify.add_argument("--reference-sha256", required=True)
    scalability_verify.add_argument("--score-tolerance", type=float, default=1e-8)
    scalability_verify.set_defaults(func=cmd_scalability_verify_reference)

    scalability_reset = sub.add_parser("scalability-reset-derived")
    scalability_reset.add_argument("--reference-db", required=True)
    scalability_reset.add_argument("--reference-sha256", required=True)
    scalability_reset.add_argument(
        "--confirm",
        required=True,
        help=f"must equal {REFERENCE_RESET_CONFIRMATION}",
    )
    scalability_reset.set_defaults(func=cmd_scalability_reset_derived)
    return parser


def main() -> int:
    role = detect_role(ROOT)
    if role is not MachineRole.OBSERVATION:
        raise SystemExit("NBOT_ADMIN_OBSERVATION_ROLE_REQUIRED")
    args = build_parser().parse_args()
    if hasattr(args, "max_events") and args.max_events < 0:
        raise SystemExit("NBOT_ADMIN_MAX_EVENTS_INVALID")
    for field in ("seal_max_events", "compact_max_events"):
        if hasattr(args, field) and getattr(args, field) < 0:
            raise SystemExit("NBOT_ADMIN_RETENTION_LIMIT_INVALID")
    if hasattr(args, "batch_events") and not (1 <= args.batch_events <= 8):
        raise SystemExit("NBOT_ADMIN_CATCHUP_BATCH_EVENTS_INVALID")
    if hasattr(args, "max_cycles") and not (1 <= args.max_cycles <= 32):
        raise SystemExit("NBOT_ADMIN_CATCHUP_MAX_CYCLES_INVALID")
    try:
        return int(args.func(args))
    except (ValueError, RuntimeError) as exc:
        print(f"FAIL {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
