from __future__ import annotations

from pathlib import Path

from .validation import MachineRole


DIRECTORY_MODE = 0o700

_COMMON_DIRECTORIES = (
    "config/secrets",
    "data",
    "runtime",
    "logs",
)

_EXECUTION_DIRECTORIES = (
    "data/execution",
    "data/execution/testnet",
    "data/execution/testnet/pending_outcomes",
    "data/execution/paper",
    "data/execution/paper/pending_outcomes",
    "data/execution/real",
    "data/execution/real/pending_outcomes",
    "runtime/execution",
    "runtime/execution/testnet",
    "runtime/execution/paper",
    "runtime/execution/real",
    "logs/execution",
    "logs/execution/testnet",
    "logs/execution/paper",
    "logs/execution/real",
)

_OBSERVATION_DIRECTORIES = (
    "data/observation",
    "data/observation/live",
    "data/observation/live/backups",
    "data/observation/testnet",
    "data/observation/testnet/backups",
    "runtime/observation",
    "runtime/observation/live",
    "runtime/observation/testnet",
    "logs/observation",
    "logs/observation/live",
    "logs/observation/testnet",
)

_FORBIDDEN_BY_ROLE = {
    MachineRole.EXECUTION: (
        "data/observation",
        "runtime/observation",
        "logs/observation",
    ),
    MachineRole.OBSERVATION: (
        "data/execution",
        "runtime/execution",
        "logs/execution",
    ),
}


def required_directories(role: MachineRole) -> tuple[str, ...]:
    role_dirs = _EXECUTION_DIRECTORIES if role is MachineRole.EXECUTION else _OBSERVATION_DIRECTORIES
    return _COMMON_DIRECTORIES + role_dirs


def bootstrap_layout(repo_root: Path | str, role: MachineRole) -> tuple[str, ...]:
    """Create/normalize only the mutable directory layout owned by *role*.

    This function never creates credentials, databases, state files, arm files,
    locks, logs, orders, or opposite-role mutable directories.
    """
    root = Path(repo_root)
    if not root.is_dir():
        raise ValueError("NBOT_REPO_ROOT_MISSING")

    verified: list[str] = []
    for relative in required_directories(role):
        path = root / relative
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(DIRECTORY_MODE)
        verified.append(relative)
    return tuple(verified)


def validate_layout(repo_root: Path | str, role: MachineRole) -> tuple[str, ...]:
    root = Path(repo_root)
    problems: list[str] = []

    for relative in required_directories(role):
        path = root / relative
        if not path.is_dir():
            problems.append(f"MISSING:{relative}")
            continue
        mode = path.stat().st_mode & 0o777
        if mode != DIRECTORY_MODE:
            problems.append(f"MODE:{relative}:{mode:04o}:EXPECTED:{DIRECTORY_MODE:04o}")

    for relative in _FORBIDDEN_BY_ROLE[role]:
        if (root / relative).exists():
            problems.append(f"FORBIDDEN_ROLE_PATH:{relative}")

    return tuple(problems)
