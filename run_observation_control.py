#!/usr/bin/env python3
"""Standalone Observation control plane for V3.8 LIVE_PAPER.

This process intentionally does not create or run an ObservationWorker and does
not acquire the canonical collector runtime lock. It reuses the existing LIVE
SQLite evidence database in WAL mode only for bounded recommendation/control
state, allowing the accepted LIVE collector process to continue uninterrupted.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import threading

from nbot.communication.server import ObservationControlServer
from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role, validate_role_profile
from nbot.observation import EvidenceDatabase, observation_config_for_profile
from nbot.observation.recommendation import ObservationControlTarget, RecommendationSupervisor


SUPPORTED_CONTROL_PROFILES = frozenset({"live-paper"})


def _git_sha(repo_root: Path) -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as exc:
        raise ValueError("NBOT_OBSERVATION_CONTROL_RELEASE_SHA_UNAVAILABLE") from exc
    if len(value) != 40:
        raise ValueError("NBOT_OBSERVATION_CONTROL_RELEASE_SHA_UNAVAILABLE")
    return value


def _optional_path(value: str | None) -> Path | None:
    text = str(value or "").strip()
    return None if not text else Path(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="NBOT V3.8 standalone LIVE_PAPER Observation control plane"
    )
    parser.add_argument("--profile", choices=sorted(SUPPORTED_CONTROL_PROFILES))
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, default=8765)
    parser.add_argument("--control-refresh-seconds", type=float, default=5.0)
    parser.add_argument("--control-tls-cert")
    parser.add_argument("--control-tls-key")
    args = parser.parse_args(argv)

    profile_name = args.profile or str(os.environ.get("NBOT_PROFILE", "")).strip()
    if profile_name not in SUPPORTED_CONTROL_PROFILES:
        parser.error("--profile or NBOT_PROFILE=live-paper is required")

    root = Path(__file__).resolve().parent
    os.chdir(root)
    role = detect_role(root)
    if role is not MachineRole.OBSERVATION:
        raise ValueError("NBOT_OBSERVATION_CONTROL_WRONG_MACHINE_ROLE")
    profile = get_profile(profile_name)
    validate_role_profile(
        repo_root=root,
        role=role,
        profile=profile,
        environment=os.environ,
    )

    auth_token = str(os.environ.get("NBOT_CONTROL_AUTH_TOKEN", "")).strip()
    if not auth_token:
        raise ValueError("NBOT_CONTROL_AUTH_TOKEN_REQUIRED")

    database = EvidenceDatabase(observation_config_for_profile(profile))
    target = ObservationControlTarget(
        database,
        profile,
        release_sha=_git_sha(root),
    )
    supervisor = RecommendationSupervisor(
        target,
        refresh_seconds=args.control_refresh_seconds,
    )
    server = ObservationControlServer(
        target=target,
        auth_token=auth_token,
        host=args.control_host,
        port=args.control_port,
        tls_certfile=_optional_path(args.control_tls_cert),
        tls_keyfile=_optional_path(args.control_tls_key),
    )

    stop = threading.Event()

    def request_stop(_signum, _frame) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    supervisor.start()
    try:
        address = server.start()
        print(
            json.dumps(
                {
                    "event": "NBOT_OBSERVATION_CONTROL_READY",
                    "phase": "V3.8",
                    "profile": profile.name,
                    "mode": "NON_PROMOTIONAL_DRY",
                    "address": f"{address[0]}:{address[1]}",
                    "order_authority": "NONE",
                    "collector_process_owned": False,
                    "database": str(profile.observation_db),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        while not stop.wait(1.0):
            pass
        return 0
    finally:
        server.stop()
        supervisor.stop()


if __name__ == "__main__":
    raise SystemExit(main())
