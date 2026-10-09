#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Mapping

from nbot.common.logging import configure_logging, observation_log_paths
from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role, validate_role_profile
from nbot.communication.server import ObservationControlServer
from nbot.observation.recommendation import ObservationControlTarget, RecommendationSupervisor
from nbot.operator.status_proxy import ObservationReadOnlyStatusProvider
from nbot.operator.telegram import TelegramClient, TelegramConfig, TelegramDispatcher
from nbot.observation.live_two_tier import LiveTwoTierResearchSupervisor
from nbot.observation import (
    BinanceUsdMPublicClient,
    EvidenceDatabase,
    ObservationRuntimeLock,
    ObservationWorker,
    observation_config_for_profile,
    observation_runtime_lock_path,
)


SUPPORTED_OBSERVATION_PROFILES = frozenset({"live-paper", "testnet-trade"})


def _git_sha(repo_root: Path) -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception as exc:
        raise ValueError("NBOT_OBSERVATION_RELEASE_SHA_UNAVAILABLE") from exc
    if not value:
        raise ValueError("NBOT_OBSERVATION_RELEASE_SHA_UNAVAILABLE")
    return value


def _optional_path(value: str | None) -> Path | None:
    text = str(value or "").strip()
    return None if not text else Path(text)


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
    event_sink=None,
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
    worker = ObservationWorker(config, client, database, event_sink=_emit if event_sink is None else event_sink)
    lock = ObservationRuntimeLock(
        observation_runtime_lock_path(repo_root, config.market_environment)
    )
    return worker, lock


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NBOT V3 Observation worker with optional V3.5 authenticated control API"
    )
    parser.add_argument("--profile", choices=sorted(SUPPORTED_OBSERVATION_PROFILES))
    parser.add_argument(
        "--once",
        action="store_true",
        help="complete one canonical worker cycle and exit",
    )
    parser.add_argument(
        "--control-api",
        action="store_true",
        help="start the authenticated V3.5 control API beside Observation",
    )
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, default=8765)
    parser.add_argument("--control-refresh-seconds", type=float, default=1.0)
    parser.add_argument("--control-tls-cert")
    parser.add_argument("--control-tls-key")
    parser.add_argument("--testnet-selection", choices=("learned", "mechanical"), default="learned",
                        help="learned uses LIVE-trained models; mechanical is an explicit order-plumbing test")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    profile_name = args.profile or str(os.environ.get("NBOT_PROFILE", "")).strip()
    if not profile_name:
        parser.error("--profile or NBOT_PROFILE is required")

    root = Path(__file__).resolve().parent
    os.chdir(root)
    log_path = observation_log_paths(root)["collector"]
    collector_log = configure_logging(
        role="OBSERVATION", profile=profile_name, log_path=log_path, component="collector"
    )
    telegram = TelegramClient(
        TelegramConfig.from_environment(os.environ, prefix="OBSERVATION"), logger=collector_log
    )
    telegram_dispatch = TelegramDispatcher(telegram, logger=collector_log)
    telegram_dispatch.start()
    last_alert: dict[str, float] = {}
    two_tier_supervisor = None

    def event_sink(payload: Mapping[str, object]) -> None:
        _emit(payload)
        encoded = json.dumps(dict(payload), sort_keys=True, default=_json_default)
        collector_log.info("OBSERVATION_EVENT %s", encoded)
        event = str(payload.get("event") or "")
        if event == "STARTED":
            telegram_dispatch.send_info(
                "OBSERVATION COLLECTOR STARTED",
                f"Profile: {profile_name}\nMarket: {payload.get('market_environment')}\nOrder authority: NONE",
            )
        elif event == "STOPPED":
            telegram_dispatch.send_info(
                "OBSERVATION COLLECTOR STOPPED",
                f"Completed cycles: {payload.get('completed_cycles')}\nOrder authority: NONE",
            )
        elif event == "CYCLE":
            supervisor = two_tier_supervisor
            if (
                supervisor is not None
                and payload.get("collection_status") in {"COMPLETE", "ALREADY_COMPLETE"}
                and payload.get("event_open_ms") is not None
            ):
                supervisor.on_completed_cycle(event_open_ms=int(payload["event_open_ms"]))
        elif event == "TRANSIENT_ERROR":
            now = time.monotonic()
            if now - last_alert.get(event, float("-inf")) >= 300.0:
                last_alert[event] = now
                telegram_dispatch.send_warning(
                    "OBSERVATION TRANSIENT ERROR",
                    f"{payload.get('error_type')}: {payload.get('detail')}\nCollection will retry automatically.",
                )

    worker, lock = build_observation_worker(
        repo_root=root,
        profile_name=profile_name,
        environment=os.environ,
        event_sink=event_sink,
    )
    two_tier_setting = str(os.environ.get("NBOT_TWO_TIER_RESEARCH", "1")).strip()
    if two_tier_setting not in {"0", "1"}:
        raise ValueError("NBOT_TWO_TIER_RESEARCH_INVALID")

    def request_stop(_signum, _frame) -> None:
        worker.stop()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    control_server = None
    recommendation_supervisor = None

    with lock:
        if profile_name == "live-paper" and two_tier_setting == "1":
            two_tier_supervisor = LiveTwoTierResearchSupervisor(
                worker.database,
                release_sha=_git_sha(root),
                event_sink=event_sink,
                enabled=True,
            )
        if args.control_api:
            auth_token = str(os.environ.get("NBOT_CONTROL_AUTH_TOKEN", ""))
            if not auth_token:
                raise ValueError("NBOT_CONTROL_AUTH_TOKEN_REQUIRED")
            from nbot.observation.learned_recommendation import testnet_recommendation_source
            release_sha = _git_sha(root)
            source = testnet_recommendation_source(worker.database, get_profile(profile_name), release_sha,
                                                   mode=args.testnet_selection)
            target = ObservationControlTarget(
                worker.database,
                get_profile(profile_name),
                release_sha=release_sha,
                learned_source=source,
            )
            recommendation_supervisor = RecommendationSupervisor(
                target,
                refresh_seconds=args.control_refresh_seconds,
            )
            recommendation_supervisor.start()
            operator_status_provider = ObservationReadOnlyStatusProvider(
                repo_root=root, target=target
            )
            control_server = ObservationControlServer(
                target=target,
                auth_token=auth_token,
                host=args.control_host,
                port=args.control_port,
                tls_certfile=_optional_path(args.control_tls_cert),
                tls_keyfile=_optional_path(args.control_tls_key),
                operator_status_provider=operator_status_provider.status,
            )
            address = control_server.start()
            _emit(
                {
                    "event": "CONTROL_API",
                    "phase": (
                        "V3.6" if profile_name == "testnet-trade" else "V3.5"
                    ),
                    "profile": profile_name,
                    "address": f"{address[0]}:{address[1]}",
                    "order_authority": "NONE",
                }
            )

        _emit(
            {
                "event": "RUNTIME",
                "phase": (
                    "V3.6"
                    if args.control_api and profile_name == "testnet-trade"
                    else ("V3.5" if args.control_api else "V3.3.8")
                ),
                "profile": profile_name,
                "authority": (
                    "TESTNET_OPERATIONAL_CANARY_OR_NOT_READY_NO_ORDERS"
                    if args.control_api
                    else "RAW_EVIDENCE_ONLY_NO_RECOMMENDATION_NO_ORDERS"
                ),
            }
        )
        try:
            worker.run(max_cycles=1 if args.once else None)
        finally:
            if control_server is not None:
                control_server.stop()
            if recommendation_supervisor is not None:
                recommendation_supervisor.stop()
            if two_tier_supervisor is not None:
                two_tier_supervisor.stop()
            telegram_dispatch.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
