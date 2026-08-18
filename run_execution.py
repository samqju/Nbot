#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time
from typing import Mapping

from nbot.common.atomic_io import atomic_write_text
from nbot.common.time import utc_iso
from nbot.config.loader import merged_environment
from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role, profile_is_armed
from nbot.exchange.binance_testnet import (
    TESTNET_REST_BASE_URL,
    TESTNET_WS_BASE_URL,
    BinanceTestnetExchange,
    TestnetExchangeConfig,
)
from nbot.execution.emergency import EmergencyFlattener
from nbot.execution.entry import EntryLifecycle, EntryLifecycleConfig
from nbot.execution.execution import ExecutionWorker
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.position import INTEGER_R_STEP_CONTROL, PositionLifecycle
from nbot.execution.reconciliation import ReconciliationLifecycle
from nbot.execution.risk import RiskManager

TESTNET_MECHANICAL_AUTHORITY = "TESTNET_MECHANICAL_ONLY"


def _positive_float(environment: Mapping[str, str], key: str, default: float) -> float:
    raw = str(environment.get(key, default)).strip()
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{key}_INVALID")
    return value


def _positive_int(environment: Mapping[str, str], key: str, default: int) -> int:
    raw = str(environment.get(key, default)).strip()
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{key}_INVALID")
    return value


def runtime_leaf(profile_name: str) -> str:
    mapping = {"testnet-trade": "testnet", "live-paper": "paper", "live-trade": "real"}
    try:
        return mapping[profile_name]
    except KeyError as exc:
        raise ValueError("NBOT_EXECUTION_PROFILE_UNSUPPORTED") from exc


def ready_path(repo_root: Path, profile_name: str) -> Path:
    return repo_root / "runtime" / "execution" / runtime_leaf(profile_name) / "execution.ready"


def default_secret_file(repo_root: Path, profile_name: str) -> Path | None:
    if profile_name == "testnet-trade":
        return repo_root / "config" / "secrets" / "execution-testnet.env"
    if profile_name == "live-trade":
        return repo_root / "config" / "secrets" / "execution-live.env"
    return None


def runtime_environment(
    repo_root: Path,
    profile_name: str,
    *,
    secret_file: Path | None = None,
) -> dict[str, str]:
    source = secret_file if secret_file is not None else default_secret_file(repo_root, profile_name)
    if source is None:
        return merged_environment(environ=os.environ)
    return merged_environment(source, environ=os.environ)


def build_testnet_exchange(repo_root: Path, environment: Mapping[str, str]) -> BinanceTestnetExchange:
    cfg = TestnetExchangeConfig(
        api_key=str(environment.get("TESTNET_API_KEY", "")).strip(),
        api_secret=str(environment.get("TESTNET_API_SECRET", "")).strip(),
        repo_root=repo_root,
        base_url=str(environment.get("TESTNET_BASE_URL", TESTNET_REST_BASE_URL)).strip(),
        ws_base_url=str(environment.get("TESTNET_WS_BASE_URL", TESTNET_WS_BASE_URL)).strip(),
        request_timeout_seconds=_positive_float(environment, "TESTNET_REST_TIMEOUT_SECONDS", 5.0),
        recv_window_ms=_positive_int(environment, "TESTNET_RECV_WINDOW_MS", 5_000),
        max_session_entries=_positive_int(environment, "TESTNET_MAX_SESSION_ENTRIES", 100),
        max_entry_notional_usd=_positive_float(environment, "TESTNET_MAX_ENTRY_NOTIONAL_USD", 1_000.0),
        entry_resolution_timeout_seconds=_positive_float(environment, "TESTNET_ENTRY_RESOLUTION_SECONDS", 10.0),
        stop_resolution_timeout_seconds=_positive_float(environment, "TESTNET_STOP_RESOLUTION_SECONDS", 10.0),
        close_settlement_retries=_positive_int(environment, "TESTNET_CLOSE_SETTLEMENT_RETRIES", 5),
        close_settlement_retry_seconds=float(environment.get("TESTNET_CLOSE_SETTLEMENT_RETRY_SECONDS", "0.5")),
    )
    cfg.validate()
    return BinanceTestnetExchange(cfg)


def build_execution_worker(
    *,
    repo_root: Path,
    profile_name: str,
    exchange: BinanceTestnetExchange,
) -> ExecutionWorker:
    profile = get_profile(profile_name)
    if profile.name != "testnet-trade":
        raise ValueError("NBOT_V3_1_RUNTIME_TESTNET_ONLY")

    durable = ExecutionDurableStore(repo_root, profile=profile.name)
    risk = RiskManager()
    emergency = EmergencyFlattener(exchange=exchange)
    entry = EntryLifecycle(
        exchange=exchange,
        state=durable.state,
        risk=risk,
        emergency=emergency,
        config=EntryLifecycleConfig(
            profile=profile.name,
            market_environment=profile.market_environment,
            allowed_entry_authorities=frozenset({TESTNET_MECHANICAL_AUTHORITY}),
            allowed_exit_policies=frozenset({INTEGER_R_STEP_CONTROL}),
        ),
    )
    position = PositionLifecycle(
        exchange=exchange,
        state=durable.state,
        risk=risk,
        emergency=emergency,
    )
    reconciliation = ReconciliationLifecycle(
        exchange=exchange,
        durable=durable,
        risk=risk,
        emergency=emergency,
    )
    return ExecutionWorker(
        exchange=exchange,
        durable=durable,
        risk=risk,
        entry=entry,
        position=position,
        reconciliation=reconciliation,
        proposal_client=None,
        outcome_client=None,
    )


def self_check(repo_root: Path, profile_name: str) -> int:
    profile = get_profile(profile_name)
    if profile.name == "live-trade":
        status = "FORBIDDEN_BEFORE_V3_10"
    elif profile.name == "live-paper":
        status = "PUBLIC_MARKET_RUNTIME_DEFERRED_UNTIL_V3_8"
    else:
        # Construction is intentionally not attempted because it would create
        # durable state.  This action is a code/config boundary check only.
        TestnetExchangeConfig(
            api_key="x", api_secret="x", repo_root=repo_root
        ).validate(require_credentials=False)
        status = "V3_1_EXECUTION_RUNTIME_READY_FOR_V3_2_TESTNET"
    print(
        json.dumps(
            {
                "phase": "V3.1",
                "role": "EXECUTION",
                "profile": profile.name,
                "status": status,
                "proposal_source": "NONE_V3_1_FAIL_CLOSED",
                "outcome_transport": "NONE_V3_1_DURABLE_LOCAL_ONLY",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def preflight_testnet(
    *,
    repo_root: Path,
    environment: Mapping[str, str],
    symbol: str,
) -> int:
    exchange = build_testnet_exchange(repo_root, environment)
    exchange.connect()
    try:
        report = exchange.preflight_report(symbol.upper())
        report["phase"] = "V3.1"
        report["runtime_authority"] = "TESTNET_MECHANICAL_ONLY"
        report["status"] = "PASS" if report.get("connected") else "FAIL"
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "PASS" else 2
    finally:
        exchange.disconnect()


def run_testnet_runtime(
    *,
    repo_root: Path,
    environment: Mapping[str, str],
    idle_poll_seconds: float,
    open_poll_seconds: float,
) -> int:
    profile = get_profile("testnet-trade")
    if not profile_is_armed(repo_root, profile):
        raise ValueError("NBOT_TESTNET_RUNTIME_REQUIRES_EXPLICIT_ARM")

    exchange = build_testnet_exchange(repo_root, environment)
    worker = build_execution_worker(
        repo_root=repo_root,
        profile_name=profile.name,
        exchange=exchange,
    )
    stop_requested = False

    def request_stop(_signum, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    ready = ready_path(repo_root, profile.name)
    ready.unlink(missing_ok=True)
    try:
        prepared = worker.prepare()
        # V3.1 runtime has no integrated recommendation authority.  A later V3.2
        # mechanical-canary invocation must explicitly enable entries around one
        # synthetic/manual proposal.  Restart recovery remains fully active.
        worker.disable_new_entries()
        atomic_write_text(
            ready,
            f"profile={profile.name}\npid={os.getpid()}\nready_at={utc_iso()}\nprepared={prepared.status}\n",
            mode=0o600,
        )
        print(
            json.dumps(
                {
                    "event": "NBOT_EXECUTION_READY",
                    "phase": "V3.1",
                    "profile": profile.name,
                    "prepared": prepared.status,
                    "pid": os.getpid(),
                    "entries_enabled": False,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        while not stop_requested:
            local = worker.state.open_position
            if local is None:
                result = worker.process_flat_cycle()
                if result == "POSITION_OPEN":
                    continue
                time.sleep(idle_poll_seconds)
                continue

            quote = exchange.quote(local.symbol)
            worker.process_open_quote(quote)
            time.sleep(open_poll_seconds)
        return 0
    finally:
        ready.unlink(missing_ok=True)
        try:
            exchange.disconnect()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="NBOT V3.1 Execution runtime")
    parser.add_argument(
        "--profile",
        choices=("testnet-trade", "live-paper", "live-trade"),
    )
    parser.add_argument("--secrets-file", type=Path)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()

    profile_name = args.profile or os.environ.get("NBOT_PROFILE", "").strip()
    if profile_name not in {"testnet-trade", "live-paper", "live-trade"}:
        parser.error("--profile or NBOT_PROFILE is required")
    args.profile = profile_name

    root = Path(__file__).resolve().parent
    role = detect_role(root)
    if role is not MachineRole.EXECUTION:
        raise SystemExit("NBOT_EXECUTION_WRONG_MACHINE_ROLE")

    if args.self_check:
        return self_check(root, args.profile)

    profile = get_profile(args.profile)
    if profile.name == "live-trade":
        raise SystemExit("NBOT_LIVE_TRADE_RUNTIME_FORBIDDEN_BEFORE_V3_10")
    if profile.name == "live-paper":
        raise SystemExit("NBOT_LIVE_PAPER_RUNTIME_DEFERRED_UNTIL_V3_8")

    environment = runtime_environment(root, profile.name, secret_file=args.secrets_file)
    if args.preflight_only:
        return preflight_testnet(
            repo_root=root,
            environment=environment,
            symbol=args.symbol,
        )

    idle_poll = _positive_float(environment, "NBOT_EXECUTION_IDLE_POLL_SECONDS", 2.0)
    open_poll = _positive_float(environment, "NBOT_EXECUTION_OPEN_POLL_SECONDS", 0.5)
    return run_testnet_runtime(
        repo_root=root,
        environment=environment,
        idle_poll_seconds=idle_poll,
        open_poll_seconds=open_poll,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
