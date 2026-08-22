#!/usr/bin/env python3
"""NBOT V3 Observation research administration CLI.

V3.4 research commands are intentionally Observation-only and LIVE-evidence
only.  They build/audit derived research state; none imports Execution or has
order authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

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
from nbot.observation.outcomes import FuturePathStore
from nbot.observation.retention import ResearchRetentionManager
from nbot.observation.policies import ExitPolicyLab
from nbot.observation.selection import EntrySelectionLab
from nbot.observation.signals import ResearchSignalStore
from nbot.observation.scalability import (
    REFERENCE_RESET_CONFIRMATION,
    ResearchScalabilityRecovery,
    verify_ridge_reference_equivalence,
)


ROOT = Path(__file__).resolve().parent
RESEARCH_PROFILE = "live-paper"


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


def _build_result(component: str, max_events: int, rebuild: bool) -> Any:
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
    return _emit(WalkForwardChampionEvaluator(_db()).evaluate(rebuild=args.rebuild))


def cmd_champion_status(_args: argparse.Namespace) -> int:
    return _emit(WalkForwardChampionEvaluator(_db()).status())


def cmd_learning_init(_args: argparse.Namespace) -> int:
    foundation = ContinuousLearningFoundation(_db())
    foundation.initialize()
    return _emit(foundation.status())


def cmd_learning_status(_args: argparse.Namespace) -> int:
    return _emit(ContinuousLearningFoundation(_db()).status())




def cmd_retention_init(_args: argparse.Namespace) -> int:
    manager = ResearchRetentionManager(_db())
    manager.initialize()
    return _emit(manager.status())

def cmd_retention_status(_args: argparse.Namespace) -> int:
    return _emit(ResearchRetentionManager(_db()).status())


def cmd_retention_maintain(args: argparse.Namespace) -> int:
    report = ResearchRetentionManager(_db()).maintain(
        seal_max_events=args.seal_max_events,
        compact_max_events=args.compact_max_events,
    )
    return _emit(report)

def cmd_scalability_status(_args: argparse.Namespace) -> int:
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
    report = ResearchScalabilityRecovery(_db()).reset_derived(
        reference_db=Path(args.reference_db),
        reference_sha256=args.reference_sha256,
        confirmation=args.confirm,
    )
    return _emit(report)




def cmd_research_catchup(args: argparse.Namespace) -> int:
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
