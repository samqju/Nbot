#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
import signal
from typing import Mapping

from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role, validate_role_profile
from nbot.observation import (
    BinanceUsdMPublicClient,
    EvidenceDatabase,
    ObservationRuntimeLock,
    ObservationWorker,
    observation_config_for_profile,
    observation_runtime_lock_path,
)


SUPPORTED_OBSERVATION_PROFILES = frozenset({"live-paper", "testnet-trade"})


def _json_default(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def _emit(payload: Mapping[str, object]) -> None:
    print(
        json.dumps(dict(payload), sort_keys=True, default=_json_default),
        flush=True,
    )


def build_observation_worker(
    *,
    repo_root: Path,
    profile_name: str,
    environment: Mapping[str, str] | None = None,
) -> tuple[ObservationWorker, ObservationRuntimeLock]:
    role = detect_role(repo_root)
    if role is not MachineRole.OBSERVATION:
        raise ValueError("NBOT_OBSERVATION_WRONG_MACHINE_ROLE")

    profile = get_profile(profile_name)
    if profile.name == "live-trade":
        raise ValueError("NBOT_OBSERVATION_LIVE_TRADE_PROFILE_FORBIDDEN_BEFORE_V3_10")
    if profile.name not in SUPPORTED_OBSERVATION_PROFILES:
        raise ValueError("NBOT_OBSERVATION_PROFILE_UNSUPPORTED")

    validate_role_profile(
        repo_root=repo_root,
        role=role,
        profile=profile,
        environment=os.environ if environment is None else environment,
    )
    config = observation_config_for_profile(profile)
    database = EvidenceDatabase(config)
    client = BinanceUsdMPublicClient(config)
    worker = ObservationWorker(config, client, database, event_sink=_emit)
    lock = ObservationRuntimeLock(
        observation_runtime_lock_path(repo_root, config.market_environment)
    )
    return worker, lock


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NBOT V3.3 credential-free Observation evidence worker"
    )
    parser.add_argument("--profile", choices=sorted(SUPPORTED_OBSERVATION_PROFILES))
    parser.add_argument(
        "--once",
        action="store_true",
        help="complete one canonical worker cycle and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    profile_name = args.profile or str(os.environ.get("NBOT_PROFILE", "")).strip()
    if not profile_name:
        parser.error("--profile or NBOT_PROFILE is required")

    root = Path(__file__).resolve().parent
    os.chdir(root)
    worker, lock = build_observation_worker(
        repo_root=root,
        profile_name=profile_name,
        environment=os.environ,
    )

    def request_stop(_signum, _frame) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    with lock:
        _emit(
            {
                "event": "RUNTIME",
                "phase": "V3.3.8",
                "profile": profile_name,
                "authority": "RAW_EVIDENCE_ONLY_NO_RECOMMENDATION_NO_ORDERS",
            }
        )
        worker.run(max_cycles=1 if args.once else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
