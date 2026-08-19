from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import fcntl
import shutil
import subprocess
from typing import Mapping

from .profiles import Profile


class MachineRole(str, Enum):
    EXECUTION = "EXECUTION"
    OBSERVATION = "OBSERVATION"


FORBIDDEN_OBSERVATION_SECRET_MARKERS = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "BINANCE_SECRET_KEY",
    "BINANCE_PRIVATE_KEY",
    "EXECUTION_BINANCE_API_KEY",
    "EXECUTION_BINANCE_API_SECRET",
    "LIVE_BINANCE_API_KEY",
    "LIVE_BINANCE_API_SECRET",
    "TESTNET_BINANCE_API_KEY",
    "TESTNET_BINANCE_API_SECRET",
    # Current V3.2 Execution Testnet credential names.  Observation must reject
    # the actual names used by the deployed Execution adapter, not only legacy
    # aliases.
    "TESTNET_API_KEY",
    "TESTNET_API_SECRET",
)


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    checks: tuple[str, ...]
    warnings: tuple[str, ...]


def detect_role(repo_root: Path | str) -> MachineRole:
    path = Path(repo_root) / ".nbot-role"
    if not path.is_file():
        raise ValueError("NBOT_ROLE_FILE_MISSING")
    value = path.read_text(encoding="utf-8").strip().upper()
    try:
        return MachineRole(value)
    except ValueError as exc:
        raise ValueError("NBOT_ROLE_INVALID") from exc


def arm_path(repo_root: Path | str, profile: Profile) -> Path:
    root = Path(repo_root)
    if profile.name == "testnet-trade":
        return root / "runtime/execution/testnet/TESTNET_TRADING_ARMED"
    if profile.name == "live-trade":
        return root / "runtime/execution/real/LIVE_TRADING_ARMED"
    raise ValueError("NBOT_PROFILE_HAS_NO_ARM_GATE")


def profile_is_armed(repo_root: Path | str, profile: Profile) -> bool:
    return (not profile.requires_arm_gate) or arm_path(repo_root, profile).is_file()


def arm_state(repo_root: Path | str, role: MachineRole, profile: Profile) -> str:
    if role is MachineRole.OBSERVATION or not profile.requires_arm_gate:
        return "NOT_REQUIRED"
    return "ARMED" if profile_is_armed(repo_root, profile) else "DISARMED"


def forbidden_observation_secrets(environment: Mapping[str, str] | None = None) -> tuple[str, ...]:
    env = os.environ if environment is None else environment
    found = [key for key in FORBIDDEN_OBSERVATION_SECRET_MARKERS if str(env.get(key, "")).strip()]
    return tuple(sorted(found))


def forbidden_observation_secret_files(repo_root: Path | str) -> tuple[str, ...]:
    root = Path(repo_root) / "config/secrets"
    if not root.is_dir():
        return ()
    found: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        keys = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key in FORBIDDEN_OBSERVATION_SECRET_MARKERS:
                keys.append(key)
        if keys:
            found.append(f"{path.relative_to(Path(repo_root))}:{','.join(sorted(set(keys)))}")
    return tuple(found)


def _clock_synchronized() -> bool | None:
    try:
        result = subprocess.run(
            ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip().lower()
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    return None


def _git_worktree_clean(repo_root: Path) -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return not bool(result.stdout.strip())


def validate_host_foundation(
    *,
    repo_root: Path | str,
    role: MachineRole,
    minimum_free_bytes: int = 512 * 1024 * 1024,
) -> DoctorResult:
    from .bootstrap import validate_layout

    root = Path(repo_root)
    checks: list[str] = []
    warnings: list[str] = []
    ok = True

    if not (root / ".venv/bin/python").is_file():
        warnings.append("PYTHON_VENV_MISSING")
        ok = False
    else:
        checks.append("PYTHON_VENV_PRESENT")

    if not (root / "requirements.txt").is_file():
        warnings.append("REQUIREMENTS_FILE_MISSING")
        ok = False
    else:
        checks.append("REQUIREMENTS_FILE_PRESENT")

    layout_problems = validate_layout(root, role)
    if layout_problems:
        warnings.extend(f"LAYOUT_{item}" for item in layout_problems)
        ok = False
    else:
        checks.append("ROLE_RUNTIME_LAYOUT_VALID")

    legacy_envs = [path for path in (root / ".env",) if path.exists()]
    legacy_envs.extend(sorted(root.glob(".env.*")))
    legacy_envs = [p for p in legacy_envs if p.name != ".env.example"]
    if legacy_envs:
        warnings.append("LEGACY_ROOT_ENV_FORBIDDEN:" + ",".join(p.name for p in legacy_envs))
        ok = False
    else:
        checks.append("LEGACY_ROOT_ENV_ABSENT")

    secret_dir = root / "config/secrets"
    if secret_dir.is_dir() and (secret_dir.stat().st_mode & 0o777) == 0o700:
        checks.append("SECRET_DIRECTORY_MODE_0700")
    else:
        warnings.append("SECRET_DIRECTORY_MODE_INVALID")
        ok = False

    if role is MachineRole.OBSERVATION:
        secret_files = forbidden_observation_secret_files(root)
        if secret_files:
            warnings.append("OBSERVATION_PRIVATE_SECRET_FILE_FORBIDDEN:" + "|".join(secret_files))
            ok = False
        else:
            checks.append("OBSERVATION_PRIVATE_SECRET_FILE_ABSENT")

    free_bytes = shutil.disk_usage(root).free
    if free_bytes < minimum_free_bytes:
        warnings.append(f"DISK_FREE_TOO_LOW:{free_bytes}")
        ok = False
    else:
        checks.append(f"DISK_FREE_OK:{free_bytes}")

    clock = _clock_synchronized()
    if clock is True:
        checks.append("CLOCK_SYNCHRONIZED")
    elif clock is False:
        warnings.append("CLOCK_NOT_SYNCHRONIZED")
        ok = False
    else:
        warnings.append("CLOCK_SYNC_STATUS_UNAVAILABLE")
        ok = False

    clean = _git_worktree_clean(root)
    if clean is True:
        checks.append("GIT_WORKTREE_CLEAN")
    elif clean is False:
        warnings.append("GIT_WORKTREE_DIRTY")
        ok = False
    else:
        warnings.append("GIT_STATUS_UNAVAILABLE")
        ok = False

    # Phase-specific readiness is layered by nbotctl.  Foundation validation
    # keeps only checks that genuinely belong to later architecture phases.
    if role is MachineRole.OBSERVATION:
        warnings.append("OBSERVATION_DATABASE_INTEGRITY_CHECK_DEFERRED_UNTIL_V3_3")
    warnings.append("CROSS_VPS_PROTOCOL_CHECK_DEFERRED_UNTIL_V3_6")

    return DoctorResult(ok=ok, checks=tuple(checks), warnings=tuple(warnings))



def _execution_lock_available(path: Path) -> bool:
    """Probe a pre-existing lock file without claiming persistent authority."""
    if not path.exists():
        return True
    try:
        handle = path.open("a+", encoding="utf-8")
    except OSError:
        return False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return True
    finally:
        handle.close()


def validate_execution_v31(
    *,
    repo_root: Path | str,
    profile: Profile,
    environment: Mapping[str, str] | None = None,
) -> DoctorResult:
    """Validate V3.1 Execution artifacts without placing orders.

    This check is deliberately read-mostly.  It validates any existing durable
    state/history/outbox, Testnet endpoint pinning, profile adapter boundaries,
    and the single-instance lock.  A local OPEN/inflight state is reported as
    requiring startup reconciliation rather than blocking the very runtime that
    must perform that reconciliation.
    """
    root = Path(repo_root)
    env = os.environ if environment is None else environment
    checks: list[str] = []
    warnings: list[str] = []
    ok = True

    try:
        if profile.name == "testnet-trade":
            from nbot.exchange.binance_testnet import (
                TESTNET_REST_BASE_URL,
                TESTNET_WS_BASE_URL,
                TestnetExchangeConfig,
            )

            cfg = TestnetExchangeConfig(
                api_key=str(env.get("TESTNET_API_KEY", "")).strip(),
                api_secret=str(env.get("TESTNET_API_SECRET", "")).strip(),
                repo_root=root,
                base_url=str(env.get("TESTNET_BASE_URL", TESTNET_REST_BASE_URL)).strip(),
                ws_base_url=str(env.get("TESTNET_WS_BASE_URL", TESTNET_WS_BASE_URL)).strip(),
            )
            cfg.validate(require_credentials=False)
            checks.append("EXECUTION_TESTNET_ENDPOINTS_PINNED")
            if cfg.api_key and cfg.api_secret:
                checks.append("EXECUTION_TESTNET_CREDENTIALS_PRESENT")
            else:
                warnings.append("EXECUTION_TESTNET_CREDENTIALS_REQUIRED_FOR_V3_2_RUNTIME")
        elif profile.name == "live-paper":
            from nbot.exchange.paper import PaperExchangeConfig

            PaperExchangeConfig()
            if profile.binance_order_writes or profile.real_capital:
                raise ValueError("LIVE_PAPER_ORDER_AUTHORITY_INVALID")
            checks.append("EXECUTION_PAPER_EXCHANGE_AVAILABLE")
            checks.append("LIVE_PAPER_BINANCE_WRITES_DISABLED_BY_PROFILE")
            warnings.append("LIVE_PAPER_PUBLIC_MARKET_RUNTIME_DEFERRED_UNTIL_V3_8")
        elif profile.name == "live-trade":
            warnings.append("LIVE_TRADE_ADAPTER_FORBIDDEN_BEFORE_V3_10")
            ok = False
        else:
            raise ValueError("EXECUTION_PROFILE_UNSUPPORTED")
    except Exception as exc:
        warnings.append(f"EXECUTION_EXCHANGE_CONTRACT_INVALID:{type(exc).__name__}:{exc}")
        ok = False

    try:
        from nbot.execution.outcomes import ExecutionHistoryStore, PendingOutcomeOutbox
        from nbot.execution.state import ExecutionStatePaths, ExecutionStateStore

        paths = ExecutionStatePaths.for_profile(root, profile.name)
        state_present = paths.state_file.is_file()
        history_present = paths.history_file.is_file()

        state = None
        if state_present:
            state = ExecutionStateStore(
                paths.state_file,
                profile=profile.name,
                market_environment=profile.market_environment,
            )
            checks.append("EXECUTION_STATE_INTEGRITY_VALID")
        else:
            checks.append("EXECUTION_STATE_CLEAN_START_READY")

        if history_present:
            ExecutionHistoryStore(paths.history_file).records()
            checks.append("EXECUTION_HISTORY_INTEGRITY_VALID")
        else:
            checks.append("EXECUTION_HISTORY_EMPTY")

        outbox = PendingOutcomeOutbox(paths.pending_outcomes_dir)
        pending_count = outbox.pending_count()
        checks.append(f"EXECUTION_PENDING_OUTCOMES:{pending_count}")

        if not state_present and (history_present or pending_count):
            warnings.append("EXECUTION_STATE_MISSING_WITH_DURABLE_EVIDENCE")
            ok = False
        if pending_count:
            warnings.append(f"EXECUTION_PENDING_OUTCOMES_BLOCK_NEW_REQUEST:{pending_count}")
        if state is not None:
            if state.open_position is not None:
                warnings.append("EXECUTION_OPEN_POSITION_REQUIRES_STARTUP_RECONCILIATION")
            if state.entry_inflight is not None:
                warnings.append("EXECUTION_ENTRY_INFLIGHT_REQUIRES_STARTUP_RECONCILIATION")
            if state.recovery.critical:
                warnings.append(
                    "EXECUTION_CRITICAL_RECOVERY_STATE:"
                    + str(state.recovery.critical_reason or "UNKNOWN")
                )
    except Exception as exc:
        warnings.append(f"EXECUTION_DURABLE_STATE_INVALID:{type(exc).__name__}:{exc}")
        ok = False

    leaf = {
        "testnet-trade": "testnet",
        "live-paper": "paper",
        "live-trade": "real",
    }[profile.name]
    lock_path = root / "runtime" / "execution" / leaf / "execution.lock"
    if _execution_lock_available(lock_path):
        checks.append("EXECUTION_SINGLE_INSTANCE_LOCK_AVAILABLE")
    else:
        warnings.append("EXECUTION_SINGLE_INSTANCE_LOCK_HELD")

    checks.append("EXECUTION_V3_1_COMPONENTS_PRESENT")
    return DoctorResult(ok=ok, checks=tuple(checks), warnings=tuple(warnings))

def validate_role_profile(
    *,
    repo_root: Path | str,
    role: MachineRole,
    profile: Profile,
    environment: Mapping[str, str] | None = None,
) -> DoctorResult:
    checks: list[str] = []
    warnings: list[str] = []
    ok = True
    profile.validate()
    checks.append(f"PROFILE_VALID:{profile.name}")
    checks.append(f"ROLE_VALID:{role.value}")

    root = Path(repo_root)
    if not root.is_dir():
        raise ValueError("NBOT_REPO_ROOT_MISSING")
    checks.append("REPO_ROOT_PRESENT")

    if role is MachineRole.OBSERVATION:
        forbidden = forbidden_observation_secrets(environment)
        if forbidden:
            raise ValueError("NBOT_OBSERVATION_PRIVATE_CREDENTIAL_FORBIDDEN:" + ",".join(forbidden))
        checks.append("OBSERVATION_PRIVATE_ORDER_SECRET_ABSENT")

    if role is MachineRole.EXECUTION and profile.requires_arm_gate and not profile_is_armed(root, profile):
        warnings.append("PROFILE_DISARMED")
        ok = False
    else:
        checks.append("ARM_GATE_SATISFIED_OR_NOT_REQUIRED")

    return DoctorResult(ok=ok, checks=tuple(checks), warnings=tuple(warnings))
