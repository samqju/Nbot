#!/usr/bin/env python3
"""Render/install the V3.8 LIVE_PAPER Execution systemd unit."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


def _launcher(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def render_live_paper_unit(*, repo: Path, python: Path, user: str, destination: Path) -> Path:
    repo = Path(repo).resolve()
    python = _launcher(python)
    user = str(user or "").strip()
    if not repo.is_dir():
        raise ValueError(f"NBOT_REPO_MISSING:{repo}")
    if not python.is_file():
        raise ValueError(f"NBOT_PYTHON_MISSING:{python}")
    if not user or any(ch.isspace() for ch in user):
        raise ValueError("NBOT_USER_INVALID")
    template = repo / "deploy/systemd/nbot-execution-live-paper.service.in"
    text = (
        template.read_text(encoding="utf-8")
        .replace("@NBOT_ROOT@", str(repo))
        .replace("@NBOT_PYTHON@", str(python))
        .replace("@NBOT_USER@", user)
    )
    if "@NBOT_" in text:
        raise ValueError("NBOT_EXECUTION_UNIT_PLACEHOLDER_REMAINS")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "nbot-execution-live-paper.service"
    target.write_text(text, encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--destination", default="/etc/systemd/system")
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    if args.start:
        args.enable = True
    target = render_live_paper_unit(
        repo=Path(args.repo), python=Path(args.python), user=args.user,
        destination=Path(args.destination),
    )
    print(f"WROTE {target}")
    if Path(args.destination).resolve() != Path("/etc/systemd/system"):
        if args.enable or args.start:
            raise ValueError("NBOT_ENABLE_REQUIRES_SYSTEMD_DESTINATION")
        return 0
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    if args.enable:
        subprocess.run(["systemctl", "enable", "nbot-execution-live-paper.service"], check=True)
    if args.start:
        subprocess.run(["systemctl", "start", "nbot-execution-live-paper.service"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
