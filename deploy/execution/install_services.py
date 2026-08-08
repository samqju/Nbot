"""Render/install portable systemd units for the NBOT Execution VPS."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


UNIT_NAMES = (
    "nbot-observation-tunnel.service",
    "nbot-execution.service",
)


def _launcher_path(path: Path) -> Path:
    """Keep a virtualenv launcher path without resolving its symlink target."""
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _plain(value: str, *, field: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"NBOT_{field}_REQUIRED")
    if any(ch.isspace() for ch in value):
        raise ValueError(f"NBOT_{field}_WHITESPACE_UNSUPPORTED")
    return value


def _file(path: Path, *, field: str, preserve_symlink: bool = False) -> Path:
    result = _launcher_path(path) if preserve_symlink else path.expanduser().resolve()
    if not result.is_file():
        raise ValueError(f"NBOT_{field}_NOT_FOUND:{result}")
    if any(ch.isspace() for ch in str(result)):
        raise ValueError(f"NBOT_{field}_PATH_WHITESPACE_UNSUPPORTED")
    return result


def render_units(
    *,
    repo: Path,
    python: Path,
    user: str,
    ssh_bin: Path,
    identity_file: Path,
    known_hosts_file: Path,
    observer_host: str,
    observer_ssh_user: str,
    destination: Path,
    local_port: int = 8765,
    remote_port: int = 8765,
) -> list[Path]:
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"NBOT_REPO_NOT_FOUND:{repo}")
    if any(ch.isspace() for ch in str(repo)):
        raise ValueError("NBOT_REPO_PATH_WHITESPACE_UNSUPPORTED")

    python = _file(
        python,
        field="PYTHON",
        preserve_symlink=True,
    )
    ssh_bin = _file(ssh_bin, field="SSH_BIN")
    identity_file = _file(identity_file, field="IDENTITY_FILE")
    known_hosts_file = _file(
        known_hosts_file,
        field="KNOWN_HOSTS_FILE",
    )

    user = _plain(user, field="SERVICE_USER")
    observer_host = _plain(observer_host, field="OBSERVER_HOST")
    observer_ssh_user = _plain(
        observer_ssh_user,
        field="OBSERVER_SSH_USER",
    )

    local_port = int(local_port)
    remote_port = int(remote_port)
    if not (1 <= local_port <= 65535):
        raise ValueError("NBOT_LOCAL_PORT_INVALID")
    if not (1 <= remote_port <= 65535):
        raise ValueError("NBOT_REMOTE_PORT_INVALID")

    replacements = {
        "@NBOT_REPO@": str(repo),
        "@NBOT_PYTHON@": str(python),
        "@NBOT_USER@": user,
        "@NBOT_SSH_BIN@": str(ssh_bin),
        "@NBOT_IDENTITY_FILE@": str(identity_file),
        "@NBOT_KNOWN_HOSTS_FILE@": str(known_hosts_file),
        "@NBOT_OBSERVER_HOST@": observer_host,
        "@NBOT_OBSERVER_SSH_USER@": observer_ssh_user,
        "@NBOT_LOCAL_PORT@": str(local_port),
        "@NBOT_REMOTE_PORT@": str(remote_port),
    }

    template_root = Path(__file__).resolve().parent
    destination = destination.expanduser()
    destination.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for unit in UNIT_NAMES:
        source = template_root / f"{unit}.in"
        rendered = source.read_text(encoding="utf-8")
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)
        if "@NBOT_" in rendered:
            raise RuntimeError(
                f"NBOT_DEPLOY_TEMPLATE_UNRESOLVED:{unit}"
            )
        target = destination / unit
        target.write_text(rendered, encoding="utf-8")
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--ssh-bin", default="/usr/bin/ssh")
    parser.add_argument("--identity-file", required=True)
    parser.add_argument("--known-hosts-file", required=True)
    parser.add_argument("--observer-host", required=True)
    parser.add_argument(
        "--observer-ssh-user",
        default="nbot-tunnel",
    )
    parser.add_argument("--local-port", type=int, default=8765)
    parser.add_argument("--remote-port", type=int, default=8765)
    parser.add_argument(
        "--destination",
        default="/etc/systemd/system",
    )
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()

    written = render_units(
        repo=Path(args.repo),
        python=Path(args.python),
        user=args.user,
        ssh_bin=Path(args.ssh_bin),
        identity_file=Path(args.identity_file),
        known_hosts_file=Path(args.known_hosts_file),
        observer_host=args.observer_host,
        observer_ssh_user=args.observer_ssh_user,
        destination=Path(args.destination),
        local_port=args.local_port,
        remote_port=args.remote_port,
    )
    for path in written:
        print(f"WROTE {path}")

    systemd_destination = Path("/etc/systemd/system")
    if Path(args.destination).resolve() == systemd_destination:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        if args.enable or args.start:
            subprocess.run(
                ["systemctl", "enable", *UNIT_NAMES],
                check=True,
            )
        if args.start:
            subprocess.run(
                ["systemctl", "start", UNIT_NAMES[0]],
                check=True,
            )
            subprocess.run(
                ["systemctl", "start", UNIT_NAMES[1]],
                check=True,
            )
    elif args.enable or args.start:
        raise ValueError(
            "NBOT_ENABLE_REQUIRES_SYSTEMD_DESTINATION"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
