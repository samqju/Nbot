from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
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

    # Deferred checks are visible so V3 never mistakes a foundation doctor for
    # exchange/database/protocol readiness.
    if role is MachineRole.EXECUTION:
        warnings.extend(
            (
                "EXECUTION_EXCHANGE_ENDPOINT_CHECK_DEFERRED_UNTIL_V3_1",
                "EXECUTION_STATE_INTEGRITY_CHECK_DEFERRED_UNTIL_V3_1",
                "EXECUTION_LOCK_CHECK_DEFERRED_UNTIL_V3_1",
                "EXECUTION_PENDING_OUTCOME_CHECK_DEFERRED_UNTIL_V3_1",
            )
        )
    else:
        warnings.append("OBSERVATION_DATABASE_INTEGRITY_CHECK_DEFERRED_UNTIL_V3_3")
    warnings.append("CROSS_VPS_PROTOCOL_CHECK_DEFERRED_UNTIL_V3_5")

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

    # V3.0 intentionally has no exchange worker yet. Missing execution credentials
    # are therefore warnings, not fabricated readiness.
    if role is MachineRole.EXECUTION and profile.binance_order_writes:
        warnings.append("EXECUTION_ORDER_CREDENTIAL_CHECK_DEFERRED_UNTIL_EXCHANGE_PHASE")

    if role is MachineRole.EXECUTION and profile.requires_arm_gate and not profile_is_armed(root, profile):
        warnings.append("PROFILE_DISARMED")
        ok = False
    else:
        checks.append("ARM_GATE_SATISFIED_OR_NOT_REQUIRED")

    return DoctorResult(ok=ok, checks=tuple(checks), warnings=tuple(warnings))
