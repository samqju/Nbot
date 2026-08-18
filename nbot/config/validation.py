from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Mapping

from .profiles import Profile


class MachineRole(str, Enum):
    EXECUTION = "EXECUTION"
    OBSERVATION = "OBSERVATION"


FORBIDDEN_OBSERVATION_SECRET_MARKERS = (
    "BINANCE_API_SECRET",
    "BINANCE_SECRET_KEY",
    "BINANCE_PRIVATE_KEY",
    "EXECUTION_BINANCE_API_SECRET",
    "LIVE_BINANCE_API_SECRET",
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


def forbidden_observation_secrets(environment: Mapping[str, str] | None = None) -> tuple[str, ...]:
    env = os.environ if environment is None else environment
    found = [key for key in FORBIDDEN_OBSERVATION_SECRET_MARKERS if str(env.get(key, "")).strip()]
    return tuple(sorted(found))


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
