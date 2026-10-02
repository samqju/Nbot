"""Fail-closed two-VPS operator orchestration helpers.

This module is deliberately outside Execution's worker/reconciliation path.
It may be imported only by operator tooling.  SSH is bounded and is never a
capital-management dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import pwd
import re
import shlex
import subprocess
from typing import Mapping, Sequence


class ClusterOperatorError(ValueError):
    pass


@dataclass(frozen=True)
class ClusterProfileUnits:
    profile: str
    observation_control_unit: str
    tunnel_unit: str
    execution_unit: str | None
    expected_local_port: int
    expected_observation_port: int


@dataclass(frozen=True)
class ClusterSshTransport:
    unit: str
    service_user: str
    ssh_binary: str
    identity_file: str
    target: str
    local_host: str
    local_port: int
    observation_host: str
    observation_port: int


_PROFILE_UNITS = {
    "live-trade": ClusterProfileUnits(
        profile="live-trade", observation_control_unit="nbot-observation-live-trade-control.service",
        tunnel_unit="nbot-control-tunnel-live-trade.service", execution_unit=None,
        expected_local_port=18767, expected_observation_port=8767,
    ),
    "testnet-trade": ClusterProfileUnits(
        profile="testnet-trade",
        observation_control_unit="nbot-observation-testnet-control.service",
        tunnel_unit="nbot-control-tunnel-testnet.service",
        execution_unit=None,
        expected_local_port=18766,
        expected_observation_port=8766,
    ),
    "live-paper": ClusterProfileUnits(
        profile="live-paper",
        observation_control_unit="nbot-observation-live-paper-control.service",
        tunnel_unit="nbot-control-tunnel-live-paper.service",
        execution_unit="nbot-execution-live-paper.service",
        expected_local_port=18765,
        expected_observation_port=8765,
    ),
}


def cluster_profile_units(profile_name: str) -> ClusterProfileUnits:
    name = str(profile_name or "").strip()
    try:
        return _PROFILE_UNITS[name]
    except KeyError as exc:
        raise ClusterOperatorError(f"NBOT_CLUSTER_PROFILE_UNSUPPORTED:{name}") from exc


def _parse_forward(value: str) -> tuple[str, int, str, int]:
    parts = str(value).split(":")
    if len(parts) != 4:
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_FORWARD_INVALID")
    local_host, local_port_raw, remote_host, remote_port_raw = parts
    try:
        local_port = int(local_port_raw)
        remote_port = int(remote_port_raw)
    except ValueError as exc:
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_FORWARD_INVALID") from exc
    if not (1 <= local_port <= 65535 and 1 <= remote_port <= 65535):
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_FORWARD_INVALID")
    return local_host, local_port, remote_host, remote_port


def parse_tunnel_unit(
    text: str,
    *,
    units: ClusterProfileUnits,
) -> ClusterSshTransport:
    """Parse only the tracked strict SSH-tunnel shape from an installed unit."""

    raw = str(text or "")
    if not raw.strip():
        raise ClusterOperatorError(f"NBOT_CLUSTER_TUNNEL_UNIT_EMPTY:{units.tunnel_unit}")
    if "@NBOT_" in raw or "@OBSERVATION_" in raw:
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_UNIT_UNRENDERED")

    service_user = None
    exec_start = None
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("User=") and service_user is None:
            service_user = line.split("=", 1)[1].strip()
        elif line.startswith("ExecStart=") and exec_start is None:
            exec_start = line.split("=", 1)[1].strip()

    if not service_user or any(ch.isspace() for ch in service_user):
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_USER_INVALID")
    if not exec_start:
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_EXECSTART_MISSING")

    argv = shlex.split(exec_start)
    if not argv or Path(argv[0]).name != "ssh":
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_NOT_SSH")

    options: dict[str, str] = {}
    identity = None
    forward = None
    target = None
    index = 1
    while index < len(argv):
        token = argv[index]
        if token == "-NT" or token == "-TN" or token == "-N" or token == "-T":
            index += 1
            continue
        if token == "-o":
            if index + 1 >= len(argv):
                raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_OPTION_INVALID")
            raw_option = argv[index + 1]
            if "=" not in raw_option:
                raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_OPTION_INVALID")
            key, value = raw_option.split("=", 1)
            options[key] = value
            index += 2
            continue
        if token == "-i":
            if index + 1 >= len(argv):
                raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_IDENTITY_MISSING")
            identity = argv[index + 1]
            index += 2
            continue
        if token == "-L":
            if index + 1 >= len(argv):
                raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_FORWARD_MISSING")
            forward = argv[index + 1]
            index += 2
            continue
        if token.startswith("-"):
            raise ClusterOperatorError(f"NBOT_CLUSTER_TUNNEL_OPTION_UNEXPECTED:{token}")
        if target is not None:
            raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_REMOTE_COMMAND_FORBIDDEN")
        target = token
        index += 1

    for key, expected in {
        "BatchMode": "yes",
        "ExitOnForwardFailure": "yes",
        "StrictHostKeyChecking": "yes",
    }.items():
        if options.get(key) != expected:
            raise ClusterOperatorError(f"NBOT_CLUSTER_TUNNEL_REQUIRED_OPTION:{key}={expected}")

    if not identity or not Path(identity).is_absolute():
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_IDENTITY_INVALID")
    if not target or target.startswith("-") or any(ch.isspace() for ch in target):
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_TARGET_INVALID")
    if not forward:
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_FORWARD_MISSING")

    local_host, local_port, observation_host, observation_port = _parse_forward(forward)
    if local_host not in {"127.0.0.1", "localhost"}:
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_LOCAL_FORWARD_NOT_LOOPBACK")
    if observation_host not in {"127.0.0.1", "localhost"}:
        raise ClusterOperatorError("NBOT_CLUSTER_TUNNEL_REMOTE_FORWARD_NOT_LOOPBACK")
    if local_port != units.expected_local_port:
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_TUNNEL_LOCAL_PORT_MISMATCH:{local_port}:{units.expected_local_port}"
        )
    if observation_port != units.expected_observation_port:
        raise ClusterOperatorError(
            "NBOT_CLUSTER_TUNNEL_OBSERVATION_PORT_MISMATCH:"
            f"{observation_port}:{units.expected_observation_port}"
        )

    return ClusterSshTransport(
        unit=units.tunnel_unit,
        service_user=service_user,
        ssh_binary=argv[0],
        identity_file=identity,
        target=target,
        local_host=local_host,
        local_port=local_port,
        observation_host=observation_host,
        observation_port=observation_port,
    )


def installed_tunnel_transport(
    profile_name: str,
    *,
    timeout_seconds: float = 5.0,
) -> ClusterSshTransport:
    units = cluster_profile_units(profile_name)
    try:
        result = subprocess.run(
            ["systemctl", "cat", "--no-pager", units.tunnel_unit],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_TUNNEL_UNIT_UNAVAILABLE:{type(exc).__name__}:{exc}"
        ) from exc
    if result.returncode != 0:
        raise ClusterOperatorError(f"NBOT_CLUSTER_TUNNEL_UNIT_NOT_INSTALLED:{units.tunnel_unit}")
    transport = parse_tunnel_unit(result.stdout, units=units)
    if not Path(transport.identity_file).is_file():
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_SSH_IDENTITY_MISSING:{transport.identity_file}"
        )
    return transport


def _current_user() -> str:
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError as exc:
        raise ClusterOperatorError("NBOT_CLUSTER_LOCAL_USER_UNKNOWN") from exc


def ssh_argv(transport: ClusterSshTransport) -> list[str]:
    current = _current_user()
    prefix: list[str] = []
    if current != transport.service_user:
        prefix = ["sudo", "-n", "-H", "-u", transport.service_user]
    return [
        *prefix,
        transport.ssh_binary,
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=2",
        "-i", transport.identity_file,
        transport.target,
    ]


def run_remote_shell(
    transport: ClusterSshTransport,
    script: str,
    *,
    timeout_seconds: float = 15.0,
) -> subprocess.CompletedProcess[str]:
    command = "sh -lc " + shlex.quote(str(script))
    try:
        return subprocess.run(
            [*ssh_argv(transport), command],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_SSH_FAILED:{type(exc).__name__}:{exc}"
        ) from exc


def discover_observation_repo(
    transport: ClusterSshTransport,
    *,
    timeout_seconds: float = 10.0,
) -> str:
    script = r'''
set -eu
root="$(systemctl show -p WorkingDirectory --value nbot-observation-live.service)"
case "$root" in
  /*) ;;
  *) exit 41 ;;
esac
[ -f "$root/.nbot-role" ] || exit 42
role="$(tr -d '[:space:]' < "$root/.nbot-role")"
[ "$role" = "OBSERVATION" ] || exit 43
printf '%s\n' "$root"
'''.strip()
    result = run_remote_shell(transport, script, timeout_seconds=timeout_seconds)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", "|")[:300]
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_REMOTE_REPO_DISCOVERY_FAILED:{result.returncode}:{detail}"
        )
    root = result.stdout.strip()
    if not root.startswith("/") or "\n" in root or "\r" in root:
        raise ClusterOperatorError("NBOT_CLUSTER_REMOTE_REPO_INVALID")
    return root


def remote_nbotctl(
    transport: ClusterSshTransport,
    *,
    repo_root: str,
    arguments: Sequence[str],
    timeout_seconds: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    if not str(repo_root).startswith("/"):
        raise ClusterOperatorError("NBOT_CLUSTER_REMOTE_REPO_INVALID")
    allowed = {"status", "doctor"}
    args = [str(item) for item in arguments]
    if not args or args[0] not in allowed:
        raise ClusterOperatorError("NBOT_CLUSTER_REMOTE_NBOTCTL_ACTION_FORBIDDEN")
    if any("\n" in item or "\r" in item for item in args):
        raise ClusterOperatorError("NBOT_CLUSTER_REMOTE_NBOTCTL_ARGUMENT_INVALID")
    command = " ".join(
        ["./nbotctl", *(shlex.quote(item) for item in args)]
    )
    script = f"cd {shlex.quote(repo_root)} && {command}"
    return run_remote_shell(transport, script, timeout_seconds=timeout_seconds)


def privileged_systemctl_argv(action: str, unit: str) -> list[str]:
    action = str(action)
    if action not in {"start", "stop", "restart"}:
        raise ClusterOperatorError(f"NBOT_CLUSTER_SYSTEMCTL_ACTION_FORBIDDEN:{action}")
    if not re.fullmatch(r"nbot-[a-z0-9-]+\.service", str(unit)):
        raise ClusterOperatorError("NBOT_CLUSTER_SYSTEMCTL_UNIT_INVALID")
    prefix: list[str] = [] if os.geteuid() == 0 else ["sudo", "-n"]
    return [*prefix, "systemctl", action, unit]


def local_systemctl(action: str, unit: str, *, timeout_seconds: float = 30.0) -> None:
    try:
        result = subprocess.run(
            privileged_systemctl_argv(action, unit),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_LOCAL_SYSTEMCTL_FAILED:{type(exc).__name__}:{exc}"
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", "|")[:300]
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_LOCAL_SYSTEMCTL_FAILED:{action}:{unit}:{result.returncode}:{detail}"
        )


def remote_systemctl(
    transport: ClusterSshTransport,
    *,
    action: str,
    unit: str,
    timeout_seconds: float = 30.0,
) -> None:
    if action not in {"start", "stop", "restart"}:
        raise ClusterOperatorError(f"NBOT_CLUSTER_SYSTEMCTL_ACTION_FORBIDDEN:{action}")
    if not re.fullmatch(r"nbot-[a-z0-9-]+\.service", str(unit)):
        raise ClusterOperatorError("NBOT_CLUSTER_SYSTEMCTL_UNIT_INVALID")
    script = (
        'if [ "$(id -u)" -eq 0 ]; then '
        f"systemctl {action} {shlex.quote(unit)}; "
        "else sudo -n systemctl "
        f"{action} {shlex.quote(unit)}; fi"
    )
    result = run_remote_shell(transport, script, timeout_seconds=timeout_seconds)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", "|")[:300]
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_REMOTE_SYSTEMCTL_FAILED:{action}:{unit}:{result.returncode}:{detail}"
        )


def local_unit_state(unit: str) -> dict[str, object]:
    try:
        result = subprocess.run(
            ["systemctl", "show", unit, "-p", "LoadState", "-p", "ActiveState", "-p", "SubState", "--no-pager"],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClusterOperatorError(
            f"NBOT_CLUSTER_LOCAL_UNIT_STATE_FAILED:{type(exc).__name__}:{exc}"
        ) from exc
    values: dict[str, str] = {}
    if result.returncode == 0:
        for raw in result.stdout.splitlines():
            if "=" in raw:
                key, value = raw.split("=", 1)
                values[key] = value
    return {
        "unit": unit,
        "installed": values.get("LoadState") == "loaded",
        "active": values.get("ActiveState") == "active",
        "active_state": values.get("ActiveState", "unknown"),
        "sub_state": values.get("SubState", "unknown"),
    }


def remote_unit_state(
    transport: ClusterSshTransport,
    *,
    unit: str,
) -> dict[str, object]:
    if not re.fullmatch(r"nbot-[a-z0-9-]+\.service", str(unit)):
        raise ClusterOperatorError("NBOT_CLUSTER_SYSTEMCTL_UNIT_INVALID")
    script = (
        f"systemctl show {shlex.quote(unit)} -p LoadState -p ActiveState -p SubState --no-pager"
    )
    result = run_remote_shell(transport, script, timeout_seconds=10)
    values: dict[str, str] = {}
    if result.returncode == 0:
        for raw in result.stdout.splitlines():
            if "=" in raw:
                key, value = raw.split("=", 1)
                values[key] = value
    return {
        "unit": unit,
        "installed": values.get("LoadState") == "loaded",
        "active": values.get("ActiveState") == "active",
        "active_state": values.get("ActiveState", "unknown"),
        "sub_state": values.get("SubState", "unknown"),
    }


def execution_stop_guard(summary: Mapping[str, object]) -> tuple[bool, str]:
    state = str(summary.get("state") or "")
    if state.startswith("INVALID:") or not state:
        return False, "EXECUTION_STATE_INVALID"
    if summary.get("open_position") is not None:
        return False, "OPEN_POSITION"
    if summary.get("entry_inflight") is not None:
        return False, "ENTRY_INFLIGHT"
    if int(summary.get("pending_outcomes") or 0) != 0:
        return False, "PENDING_OUTCOME"
    if bool(summary.get("recovery_critical")):
        return False, "RECOVERY_CRITICAL"
    if bool(summary.get("entries_enabled")):
        return False, "ENTRIES_ENABLED"
    return True, "SAFE_FLAT"


def execution_cluster_start_guard(
    summary: Mapping[str, object],
    *,
    runtime_active: bool,
) -> tuple[bool, str]:
    if runtime_active:
        return True, "RUNTIME_ALREADY_ACTIVE"
    state = str(summary.get("state") or "")
    if state.startswith("INVALID:") or not state:
        return False, "EXECUTION_STATE_INVALID"
    if summary.get("open_position") is not None:
        return False, "OPEN_POSITION_REQUIRES_LOCAL_RECOVERY"
    if summary.get("entry_inflight") is not None:
        return False, "ENTRY_INFLIGHT_REQUIRES_LOCAL_RECOVERY"
    if int(summary.get("pending_outcomes") or 0) != 0:
        return False, "PENDING_OUTCOME_REQUIRES_LOCAL_RECOVERY"
    if bool(summary.get("recovery_critical")):
        return False, "RECOVERY_CRITICAL_REQUIRES_LOCAL_RECOVERY"
    return True, "SAFE_TO_ORCHESTRATE"
