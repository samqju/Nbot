#!/usr/bin/env python3
"""NBOT V3 Observation research administration CLI.

V3.4 research commands are intentionally Observation-only and LIVE-evidence
only.  They build/audit derived research state; none imports Execution or has
order authority.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
from typing import Any

from nbot.common.logging import configure_logging, observation_log_paths
from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role
from nbot.observation.binance_public import BinanceUsdMPublicClient
from nbot.observation.champion import WalkForwardChampionEvaluator
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
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("NBOT_V384_EPOCH_COMMAND_LOCK_HELD") from exc
        try:
            yield
        finally:
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
    db = _db()
    if args.component == "policies":
        return _emit(ExitPolicyLab(db).report())
    if args.component == "selection":
        return _emit(EntrySelectionLab(db).report())
    if args.component == "champion":
        return _emit(WalkForwardChampionEvaluator(db).report())
    raise ValueError("NBOT_ADMIN_REPORT_COMPONENT_INVALID")


def cmd_champion_evaluate(args: argparse.Namespace) -> int:
    _legacy_mixed_research_guard()
    return _emit(WalkForwardChampionEvaluator(_db()).evaluate(rebuild=args.rebuild))


def cmd_champion_status(_args: argparse.Namespace) -> int:
    if _v384_active():
        return _emit({
            "authority": "RESEARCH_ONLY_NO_EXECUTION",
            "source": "V3_8_4_PERMANENT_RESEARCH_MEMORY",
            "memory": _memory().status(),
            "research_champion_evaluations": _memory().artifact("research_champion_evaluations"),
            "research_champions": _memory().artifact("research_champions"),
        })
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
            "status": "V3_8_4_COMPACT_MEMORY_READY_V3_9_TRAINING_NOT_YET_ENABLED",
            "memory": _memory().status(),
            "legacy_learning_foundation": _memory().artifact("learning_foundations"),
            "legacy_model_registry": _memory().artifact("model_registry"),
            "legacy_challenger_registry": _memory().artifact("challenger_registry"),
        })
    return _emit(ContinuousLearningFoundation(_db()).status())




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


def cmd_research_epoch_status(_args: argparse.Namespace) -> int:
    processor = _epoch_processor()
    return _emit({
        "epoch_version": "RESEARCH_EPOCH_V1",
        "authority": "RESEARCH_ONLY_NO_EXECUTION",
        "plan": asdict(processor.plan()),
        "memory": _memory().status(),
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
            report = processor.run_once()
            if report.get("status") == "PASS" and args.prune_raw:
                report["raw_prune"] = processor.prune_raw()
    except Exception as exc:
        research_log.exception("RESEARCH_EPOCH_FAILED")
        telegram.send_critical(
            "RESEARCH EPOCH FAILED", f"{type(exc).__name__}: {exc}\nOrder authority: NONE"
        )
        raise
    research_log.info("RESEARCH_EPOCH_RESULT %s", json.dumps(report, sort_keys=True, default=_jsonable))
    if report.get("status") == "PASS":
        memory = report.get("memory") if isinstance(report.get("memory"), dict) else {}
        telegram.send_info(
            "RESEARCH EPOCH COMPLETE",
            f"Status: PASS\nEpoch: {report.get('epoch_id', 'N/A')}\n"
            f"Memory events: {memory.get('events', 'N/A')}\nAuthority: RESEARCH_ONLY_NO_EXECUTION",
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

    research_audit = sub.add_parser("research-audit")
    research_audit.set_defaults(func=cmd_research_audit)

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
