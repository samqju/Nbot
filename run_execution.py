#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import time
from typing import Iterator, Mapping

from nbot.common.atomic_io import atomic_write_text
from nbot.common.time import utc_iso
from nbot.communication.integration import (
    TESTNET_OPERATIONAL_CANARY_AUTHORITY,
    build_integrated_control_client,
    build_v37_testnet_client,
    run_v36_disarmed_cycle,
)
from nbot.config.loader import merged_environment
from nbot.config.profiles import get_profile
from nbot.config.validation import MachineRole, detect_role, profile_is_armed
from nbot.exchange.binance_public import (
    BinanceLivePublicMarketConfig,
    BinanceLivePublicMarketData,
)
from nbot.exchange.binance_testnet import (
    TESTNET_REST_BASE_URL,
    TESTNET_WS_BASE_URL,
    BinanceTestnetExchange,
    TestnetExchangeConfig,
)
from nbot.exchange.contracts import ExchangePort
from nbot.exchange.paper import PaperExchange, PaperExchangeConfig
from nbot.execution.canary import (
    MechanicalCanaryEmergencyFlattener,
    MechanicalCanaryEntryLifecycle,
    MechanicalCanaryOutcomeClient,
    MechanicalCanaryReconciliationLifecycle,
    MechanicalCanaryTelemetry,
    MechanicalCanaryTestnetExchange,
    OneShotMechanicalProposalClient,
    TESTNET_MECHANICAL_AUTHORITY,
    make_mechanical_proposal,
    mechanical_outcome_path,
)
from nbot.execution.emergency import EmergencyFlattener
from nbot.execution.entry import EntryLifecycle, EntryLifecycleConfig
from nbot.execution.execution import (
    ExecutionWorker,
    ExecutionWorkerError,
    OutcomeClient,
    ProposalClient,
)
from nbot.execution.fault_campaign import fault_campaign_summary
from nbot.execution.outcomes import ExecutionDurableStore
from nbot.execution.position import INTEGER_R_STEP_CONTROL, PositionLifecycle
from nbot.execution.reconciliation import ReconciliationLifecycle
from nbot.execution.risk import RiskManager


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


LIVE_PAPER_DRY_SENTINEL_AUTHORITY = "NON_PROMOTIONAL_DRY_NO_ENTRY"


@contextmanager
def _live_paper_runtime_lock(repo_root: Path) -> Iterator[None]:
    """Kernel-backed single-instance lock for the local PAPER execution runtime."""
    path = repo_root / "runtime/execution/paper/execution.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    handle = path.open("a+", encoding="utf-8")
    os.chmod(path, 0o600)
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("NBOT_LIVE_PAPER_EXECUTION_LOCK_HELD") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


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


def build_testnet_exchange(
    repo_root: Path,
    environment: Mapping[str, str],
    *,
    telemetry: MechanicalCanaryTelemetry | None = None,
) -> BinanceTestnetExchange:
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
    if telemetry is not None:
        return MechanicalCanaryTestnetExchange(cfg, telemetry)
    return BinanceTestnetExchange(cfg)


def build_live_paper_exchange(
    repo_root: Path,
    environment: Mapping[str, str],
) -> tuple[PaperExchange, BinanceLivePublicMarketData]:
    profile = get_profile("live-paper")
    market = BinanceLivePublicMarketData(
        BinanceLivePublicMarketConfig(
            request_timeout_seconds=_positive_float(
                environment, "LIVE_PUBLIC_REST_TIMEOUT_SECONDS", 3.0
            ),
            max_clock_skew_ms=_positive_int(
                environment, "LIVE_PUBLIC_MAX_CLOCK_SKEW_MS", 5_000
            ),
        )
    )
    exchange = PaperExchange(
        repo_root=repo_root,
        profile=profile,
        market_data=market,
        config=PaperExchangeConfig(),
    )
    return exchange, market


def build_execution_worker(
    *,
    repo_root: Path,
    profile_name: str,
    exchange: ExchangePort,
    proposal_client: ProposalClient | None = None,
    outcome_client: OutcomeClient | None = None,
    telemetry: MechanicalCanaryTelemetry | None = None,
    allowed_entry_authorities: frozenset[str] | None = None,
) -> ExecutionWorker:
    profile = get_profile(profile_name)
    if profile.name not in {"testnet-trade", "live-paper"}:
        raise ValueError("NBOT_EXECUTION_RUNTIME_PROFILE_UNSUPPORTED")

    durable = ExecutionDurableStore(repo_root, profile=profile.name)
    risk = RiskManager()
    if telemetry is None:
        emergency = EmergencyFlattener(exchange=exchange)
        entry_type = EntryLifecycle
        reconciliation_type = ReconciliationLifecycle
    else:
        emergency = MechanicalCanaryEmergencyFlattener(exchange=exchange, telemetry=telemetry)
        entry_type = MechanicalCanaryEntryLifecycle
        reconciliation_type = MechanicalCanaryReconciliationLifecycle
    entry_kwargs = dict(
        exchange=exchange,
        state=durable.state,
        risk=risk,
        emergency=emergency,
        config=EntryLifecycleConfig(
            profile=profile.name,
            market_environment=profile.market_environment,
            allowed_entry_authorities=(
                (
                    frozenset({TESTNET_MECHANICAL_AUTHORITY})
                    if profile.name == "testnet-trade"
                    else frozenset({LIVE_PAPER_DRY_SENTINEL_AUTHORITY})
                )
                if allowed_entry_authorities is None
                else allowed_entry_authorities
            ),
            allowed_exit_policies=frozenset({INTEGER_R_STEP_CONTROL}),
        ),
    )
    if telemetry is not None:
        entry_kwargs["telemetry"] = telemetry
    entry = entry_type(**entry_kwargs)
    position = PositionLifecycle(
        exchange=exchange,
        state=durable.state,
        risk=risk,
        emergency=emergency,
    )
    reconciliation_kwargs = dict(
        exchange=exchange,
        durable=durable,
        risk=risk,
        emergency=emergency,
    )
    if telemetry is not None:
        reconciliation_kwargs["telemetry"] = telemetry
    reconciliation = reconciliation_type(**reconciliation_kwargs)
    return ExecutionWorker(
        exchange=exchange,
        durable=durable,
        risk=risk,
        entry=entry,
        position=position,
        reconciliation=reconciliation,
        proposal_client=proposal_client,
        outcome_client=outcome_client,
    )


def self_check(repo_root: Path, profile_name: str) -> int:
    profile = get_profile(profile_name)
    if profile.name == "live-trade":
        status = "FORBIDDEN_BEFORE_V3_10"
    elif profile.name == "live-paper":
        BinanceLivePublicMarketConfig().validate()
        PaperExchangeConfig()
        status = "V3_8_NON_PROMOTIONAL_DRY_RUNTIME_READY"
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
                "phase": "V3.2",
                "role": "EXECUTION",
                "profile": profile.name,
                "status": status,
                "proposal_source": "NONE_V3_1_FAIL_CLOSED",
                "outcome_transport": "NONE_V3_1_DURABLE_LOCAL_ONLY",
                "v3_2_canary_proposal_source": "TESTNET_MECHANICAL_ONLY_EXPLICIT_INVOCATION",
                "v3_2_canary_outcome_transport": "TESTNET_MECHANICAL_LOCAL_ACK_ONLY",
                "v3_2_operator_actions": ["CANARY", "RECONCILE", "FORCE_CLOSE"],
                "v3_2_telemetry": "TESTNET_MECHANICAL_ONLY_JSONL",
                "v3_2_fault_campaign": fault_campaign_summary(),
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
        report["phase"] = "V3.2"
        report["runtime_authority"] = "TESTNET_MECHANICAL_ONLY"
        report["status"] = "PASS" if report.get("connected") else "FAIL"
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "PASS" else 2
    finally:
        exchange.disconnect()



def preflight_live_paper(
    *,
    repo_root: Path,
    environment: Mapping[str, str],
    symbol: str,
) -> int:
    profile = get_profile("live-paper")
    config = BinanceLivePublicMarketConfig(
        request_timeout_seconds=_positive_float(
            environment, "LIVE_PUBLIC_REST_TIMEOUT_SECONDS", 3.0
        ),
        max_clock_skew_ms=_positive_int(
            environment, "LIVE_PUBLIC_MAX_CLOCK_SKEW_MS", 5_000
        ),
    )
    market = BinanceLivePublicMarketData(config)
    # Construction validates the ignored authenticated control-link config but
    # performs no remote control request.
    build_integrated_control_client(
        repo_root=repo_root,
        profile_name=profile.name,
        environ=os.environ,
    )
    market.connect()
    try:
        quote = market.quote(symbol.upper())
        report = {
            "phase": "V3.8",
            "profile": profile.name,
            "mode": "NON_PROMOTIONAL_DRY",
            "market_environment": profile.market_environment,
            "paper_capital": True,
            "binance_private_order_writes": False,
            "public_base_url": config.base_url,
            "symbol": quote.symbol,
            "bid": quote.bid,
            "ask": quote.ask,
            "mid": quote.mid,
            "spread_pct": quote.spread_pct,
            "quote_timestamp_ms": quote.timestamp_ms,
            "recommendation_entry_enabled": False,
            "status": "PASS",
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    finally:
        market.disconnect()


def run_testnet_canary(
    *,
    repo_root: Path,
    environment: Mapping[str, str],
    symbol: str,
    side: str,
    confirmed: bool,
    open_poll_seconds: float,
) -> int:
    """Run one explicit standalone V3.2 Testnet mechanical canary.

    A fresh invocation may create at most one proposal.  If restart recovery
    finds an already-open protected position, no new proposal is created and
    the invocation resumes management of that existing capital state instead.
    """
    profile = get_profile("testnet-trade")
    if not confirmed:
        raise ValueError("NBOT_TESTNET_CANARY_REQUIRES_EXPLICIT_YES")
    if not profile_is_armed(repo_root, profile):
        raise ValueError("NBOT_TESTNET_CANARY_REQUIRES_EXPLICIT_ARM")
    if side not in {"LONG", "SHORT"}:
        raise ValueError("NBOT_TESTNET_CANARY_SIDE_INVALID")

    telemetry = MechanicalCanaryTelemetry(repo_root, action="CANARY")
    exchange = build_testnet_exchange(repo_root, environment, telemetry=telemetry)
    proposal_client = OneShotMechanicalProposalClient(telemetry)
    outcome_client = MechanicalCanaryOutcomeClient(mechanical_outcome_path(repo_root))
    worker = build_execution_worker(
        repo_root=repo_root,
        profile_name=profile.name,
        exchange=exchange,
        proposal_client=proposal_client,
        outcome_client=outcome_client,
        telemetry=telemetry,
    )

    try:
        prepared = worker.prepare()
        # Never inherit an enabled entry gate from a previous interrupted
        # operator session.  One explicit canary invocation owns one proposal.
        worker.disable_new_entries()

        if worker.state.open_position is None:
            # Deliver any already-completed standalone outcome first.  With the
            # gate disabled this cycle cannot create a new entry.
            worker.process_flat_cycle()
            if worker.durable.outbox.pending_count():
                raise ValueError("NBOT_TESTNET_CANARY_PENDING_OUTCOME_NOT_ACKED")

            quote = exchange.quote(symbol.upper())
            proposal_client.offer(make_mechanical_proposal(quote, side=side))
            worker.enable_new_entries()
            try:
                entry_result = worker.process_flat_cycle()
            finally:
                worker.disable_new_entries()
            if entry_result != "ENTRY_OPENED":
                print(
                    json.dumps(
                        {
                            "event": "NBOT_TESTNET_MECHANICAL_ENTRY_NOT_OPENED",
                            "phase": "V3.2",
                            "authority": TESTNET_MECHANICAL_AUTHORITY,
                            "entry_result": entry_result,
                            "prepared": prepared.status,
                        },
                        sort_keys=True,
                    )
                )
                telemetry.finish("ENTRY_NOT_OPENED")
                return 2
        else:
            entry_result = "RESUMED_EXISTING_POSITION"

        local = worker.state.open_position
        if local is None:
            raise ValueError("NBOT_TESTNET_CANARY_OPEN_STATE_MISSING")
        print(
            json.dumps(
                {
                    "event": "NBOT_TESTNET_MECHANICAL_POSITION_MANAGEMENT",
                    "phase": "V3.2",
                    "authority": TESTNET_MECHANICAL_AUTHORITY,
                    "evidence_class": "TESTNET_MECHANICAL_ONLY",
                    "entry_result": entry_result,
                    "symbol": local.symbol,
                    "side": local.side,
                    "proposal_id": local.proposal_id,
                    "entries_enabled": False,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        try:
            while worker.state.open_position is not None:
                current = worker.state.open_position
                assert current is not None
                quote = exchange.quote(current.symbol)
                worker.process_open_quote(quote)
                health = worker.state.health
                telemetry.observe_latency(
                    "position_management_ms",
                    health.last_position_manage_ms,
                    status="PASS",
                    durable_max_ms=health.max_position_manage_ms,
                )
                telemetry.sample_resources()
                time.sleep(open_poll_seconds)
        except KeyboardInterrupt:
            summary = telemetry.finish("INTERRUPTED_POSITION_LEFT_PROTECTED")
            print("TESTNET_MECHANICAL_CANARY_INTERRUPTED_POSITION_LEFT_PROTECTED", flush=True)
            print(json.dumps({"telemetry": summary}, sort_keys=True), flush=True)
            return 0

        # The close outcome is already durable locally.  ACK it into the
        # separate mechanical-only history before allowing a future invocation.
        worker.process_flat_cycle()
        if worker.durable.outbox.pending_count():
            raise ValueError("NBOT_TESTNET_CANARY_OUTCOME_ACK_FAILED")
        summary = telemetry.finish("CLOSED")
        print(
            json.dumps(
                {
                    "event": "NBOT_TESTNET_MECHANICAL_CANARY_CLOSED",
                    "phase": "V3.2",
                    "authority": TESTNET_MECHANICAL_AUTHORITY,
                    "evidence_class": "TESTNET_MECHANICAL_ONLY",
                    "research_evidence": False,
                    "telemetry": summary,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        if not telemetry.finished:
            telemetry.finish("EXITED_BEFORE_NORMAL_FINISH")
        try:
            exchange.disconnect()
        except Exception:
            pass


def run_testnet_reconcile(
    *,
    repo_root: Path,
    environment: Mapping[str, str],
    confirmed: bool,
) -> int:
    """Run one explicit capital-first Testnet reconciliation with telemetry."""
    profile = get_profile("testnet-trade")
    if not confirmed:
        raise ValueError("NBOT_TESTNET_RECONCILE_REQUIRES_EXPLICIT_YES")
    if not profile_is_armed(repo_root, profile):
        raise ValueError("NBOT_TESTNET_RECONCILE_REQUIRES_EXPLICIT_ARM")
    telemetry = MechanicalCanaryTelemetry(repo_root, action="RECONCILE")
    exchange = build_testnet_exchange(repo_root, environment, telemetry=telemetry)
    outcome_client = MechanicalCanaryOutcomeClient(mechanical_outcome_path(repo_root))
    worker = build_execution_worker(
        repo_root=repo_root,
        profile_name=profile.name,
        exchange=exchange,
        outcome_client=outcome_client,
        telemetry=telemetry,
    )
    try:
        result = worker.prepare()
        worker.disable_new_entries()
        if worker.state.open_position is None and worker.durable.outbox.pending_count():
            worker.process_flat_cycle()
        summary = telemetry.finish("PASS")
        print(
            json.dumps(
                {
                    "event": "NBOT_TESTNET_MECHANICAL_RECONCILE",
                    "phase": "V3.2",
                    "authority": TESTNET_MECHANICAL_AUTHORITY,
                    "result": result.status,
                    "open_position": None if worker.state.open_position is None else worker.state.open_position.symbol,
                    "pending_outcomes": worker.durable.outbox.pending_count(),
                    "telemetry": summary,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    finally:
        if not telemetry.finished:
            telemetry.finish("FAILED_OR_INTERRUPTED")
        try:
            exchange.disconnect()
        except Exception:
            pass


def run_testnet_force_close(
    *,
    repo_root: Path,
    environment: Mapping[str, str],
    confirmed: bool,
) -> int:
    """Verified operator Testnet flatten; never trusts the close request alone."""
    profile = get_profile("testnet-trade")
    if not confirmed:
        raise ValueError("NBOT_TESTNET_FORCE_CLOSE_REQUIRES_EXPLICIT_YES")
    if not profile_is_armed(repo_root, profile):
        raise ValueError("NBOT_TESTNET_FORCE_CLOSE_REQUIRES_EXPLICIT_ARM")
    telemetry = MechanicalCanaryTelemetry(repo_root, action="FORCE_CLOSE")
    exchange = build_testnet_exchange(repo_root, environment, telemetry=telemetry)
    outcome_client = MechanicalCanaryOutcomeClient(mechanical_outcome_path(repo_root))
    worker = build_execution_worker(
        repo_root=repo_root,
        profile_name=profile.name,
        exchange=exchange,
        outcome_client=outcome_client,
        telemetry=telemetry,
    )
    try:
        prepared = worker.prepare()
        worker.disable_new_entries()
        result = worker.force_close_open_position(reason="OPERATOR_TESTNET_FORCE_CLOSE")
        if worker.state.open_position is None and worker.durable.outbox.pending_count():
            worker.process_flat_cycle()
        if worker.state.open_position is not None:
            raise ValueError("NBOT_TESTNET_FORCE_CLOSE_LOCAL_STATE_NOT_FLAT")
        summary = telemetry.finish("CONFIRMED_FLAT")
        print(
            json.dumps(
                {
                    "event": "NBOT_TESTNET_MECHANICAL_FORCE_CLOSE",
                    "phase": "V3.2",
                    "authority": TESTNET_MECHANICAL_AUTHORITY,
                    "prepared": prepared.status,
                    "reconciliation": result.status,
                    "pending_outcomes": worker.durable.outbox.pending_count(),
                    "confirmed_flat": True,
                    "telemetry": summary,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    finally:
        if not telemetry.finished:
            telemetry.finish("FAILED_OR_INTERRUPTED")
        try:
            exchange.disconnect()
        except Exception:
            pass

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
    remote_client = build_v37_testnet_client(
        repo_root=repo_root,
        profile_name=profile.name,
        environ=os.environ,
    )
    worker = build_execution_worker(
        repo_root=repo_root,
        profile_name=profile.name,
        exchange=exchange,
        proposal_client=remote_client,
        outcome_client=remote_client,
        allowed_entry_authorities=frozenset({TESTNET_OPERATIONAL_CANARY_AUTHORITY}),
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
        # Start from a closed local entry gate even when the persisted state was
        # previously enabled.  The flat loop below re-opens it only while the
        # explicit Testnet arm file is present.  OPEN management never depends
        # on this gate or on remote-service availability.
        worker.disable_new_entries()
        atomic_write_text(
            ready,
            (
                f"profile={profile.name}\npid={os.getpid()}\nready_at={utc_iso()}\n"
                f"prepared={prepared.status}\nphase=V3.7\n"
                f"recommendation_authority={TESTNET_OPERATIONAL_CANARY_AUTHORITY}\n"
            ),
            mode=0o600,
        )
        print(
            json.dumps(
                {
                    "event": "NBOT_EXECUTION_READY",
                    "phase": "V3.7",
                    "profile": profile.name,
                    "prepared": prepared.status,
                    "pid": os.getpid(),
                    "entries_enabled": False,
                    "proposal_source": "REMOTE_CONTROL_LINK",
                    "outcome_transport": "REMOTE_CONTROL_ACK",
                    "recommendation_authority": TESTNET_OPERATIONAL_CANARY_AUTHORITY,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        while not stop_requested:
            local = worker.state.open_position
            if local is None:
                armed = profile_is_armed(repo_root, profile)
                if not armed:
                    if worker.state.snapshot.entries_enabled:
                        worker.disable_new_entries()
                elif not worker.state.snapshot.entries_enabled:
                    # Reconcile again immediately before re-opening the entry
                    # gate.  A re-arm can therefore never skip current exchange
                    # truth or the persisted daily-risk gate.
                    try:
                        worker.enable_new_entries()
                    except ExecutionWorkerError:
                        # A daily-risk gate is a normal flat fail-closed state,
                        # not a reason to kill the process.  Reconciliation
                        # failures still propagate because they are not wrapped
                        # as ExecutionWorkerError by enable_new_entries().
                        time.sleep(idle_poll_seconds)
                        continue
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


def run_live_paper_runtime(
    *,
    repo_root: Path,
    environment: Mapping[str, str],
    idle_poll_seconds: float,
    open_poll_seconds: float,
) -> int:
    """Run V3.8 LIVE_PAPER in explicit non-promotional dry mode.

    The process owns LIVE public market truth and durable local PAPER state,
    manages any already-open paper position independently, and delivers pending
    outcomes while flat.  New entries remain disabled by construction until a
    later reviewed patch explicitly translates a valid Research Champion into
    a paper-canary execution authority.
    """
    profile = get_profile("live-paper")
    exchange, market = build_live_paper_exchange(repo_root, environment)
    remote_client = build_integrated_control_client(
        repo_root=repo_root,
        profile_name=profile.name,
        environ=os.environ,
    )
    worker = build_execution_worker(
        repo_root=repo_root,
        profile_name=profile.name,
        exchange=exchange,
        proposal_client=remote_client,
        outcome_client=remote_client,
        allowed_entry_authorities=frozenset({LIVE_PAPER_DRY_SENTINEL_AUTHORITY}),
    )
    stop_requested = False

    def request_stop(_signum, _frame) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    ready = ready_path(repo_root, profile.name)
    ready.unlink(missing_ok=True)
    with _live_paper_runtime_lock(repo_root):
        try:
            prepared = worker.prepare()
            # This is the defining V3.8 foundation gate.  Do not auto-enable
            # entries merely because a Research Champion later appears.
            worker.disable_new_entries()
            atomic_write_text(
                ready,
                (
                    f"profile={profile.name}\npid={os.getpid()}\nready_at={utc_iso()}\n"
                    f"prepared={prepared.status}\nphase=V3.8\n"
                    "mode=NON_PROMOTIONAL_DRY\n"
                    "recommendation_entry_enabled=false\n"
                    "binance_private_order_writes=false\n"
                ),
                mode=0o600,
            )
            print(
                json.dumps(
                    {
                        "event": "NBOT_EXECUTION_READY",
                        "phase": "V3.8",
                        "profile": profile.name,
                        "mode": "NON_PROMOTIONAL_DRY",
                        "prepared": prepared.status,
                        "pid": os.getpid(),
                        "entries_enabled": False,
                        "proposal_source": "REMOTE_CONTROL_LINK_NOT_CONSUMED_WHILE_DRY",
                        "outcome_transport": "REMOTE_CONTROL_ACK_WHILE_FLAT",
                        "market_truth": "EXECUTION_OWN_BINANCE_LIVE_PUBLIC",
                        "capital": "LOCAL_PAPER",
                        "binance_private_order_writes": False,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

            while not stop_requested:
                local = worker.state.open_position
                if local is None:
                    # Reconcile and deliver any durable outcome first. Since the
                    # entry gate remains disabled, this can never request or
                    # execute a recommendation in the dry foundation.
                    worker.process_flat_cycle()
                    time.sleep(idle_poll_seconds)
                    continue

                quote = exchange.quote(local.symbol)
                worker.process_open_quote(quote)
                time.sleep(open_poll_seconds)
            return 0
        finally:
            ready.unlink(missing_ok=True)
            market.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(description="NBOT V3 Execution runtime")
    parser.add_argument(
        "--profile",
        choices=("testnet-trade", "live-paper", "live-trade"),
    )
    parser.add_argument("--secrets-file", type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--self-check", action="store_true")
    action.add_argument("--preflight-only", action="store_true")
    action.add_argument("--testnet-canary", action="store_true")
    action.add_argument("--testnet-reconcile", action="store_true")
    action.add_argument("--testnet-force-close", action="store_true")
    action.add_argument("--v36-dry-cycle", action="store_true")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--side", choices=("LONG", "SHORT"), default="LONG")
    parser.add_argument("--yes", action="store_true")
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
    environment = runtime_environment(root, profile.name, secret_file=args.secrets_file)
    if args.preflight_only:
        if profile.name == "live-paper":
            return preflight_live_paper(
                repo_root=root,
                environment=environment,
                symbol=args.symbol,
            )
        return preflight_testnet(
            repo_root=root,
            environment=environment,
            symbol=args.symbol,
        )
    if profile.name == "live-paper" and (
        args.testnet_reconcile or args.testnet_force_close or args.testnet_canary or args.v36_dry_cycle
    ):
        raise ValueError("NBOT_TESTNET_ACTION_REQUIRES_TESTNET_PROFILE")

    if args.testnet_reconcile:
        return run_testnet_reconcile(
            repo_root=root,
            environment=environment,
            confirmed=args.yes,
        )
    if args.testnet_force_close:
        return run_testnet_force_close(
            repo_root=root,
            environment=environment,
            confirmed=args.yes,
        )
    if args.testnet_canary:
        return run_testnet_canary(
            repo_root=root,
            environment=environment,
            symbol=args.symbol,
            side=args.side,
            confirmed=args.yes,
            open_poll_seconds=_positive_float(environment, "NBOT_EXECUTION_OPEN_POLL_SECONDS", 0.5),
        )
    if args.v36_dry_cycle:
        result = run_v36_disarmed_cycle(
            repo_root=root,
            profile_name=profile.name,
            environ=os.environ,
        )
        print(
            json.dumps(
                {
                    "event": "NBOT_V36_TWO_VPS_DRY_CYCLE",
                    "phase": "V3.6",
                    "profile": profile.name,
                    "integrated_order_gate": "DISARMED",
                    "order_write_attempted": False,
                    **result.to_dict(),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if result.status in {"DRY_PROPOSAL", "NO_TRADE"} else 2

    idle_poll = _positive_float(environment, "NBOT_EXECUTION_IDLE_POLL_SECONDS", 2.0)
    open_poll = _positive_float(environment, "NBOT_EXECUTION_OPEN_POLL_SECONDS", 0.5)
    if profile.name == "live-paper":
        return run_live_paper_runtime(
            repo_root=root,
            environment=environment,
            idle_poll_seconds=idle_poll,
            open_poll_seconds=open_poll,
        )
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
