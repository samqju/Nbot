#!/usr/bin/env python3
"""Render portable Observation systemd units for a replacement/current VPS."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess

UNIT_NAMES = (
    "nbot-observation.service",
    "nbot-auto-training.service",
    "nbot-promotion-controller.service",
    "nbot-paper-canary-controller.service",
)


def render_units(*, repo: Path, python: Path, user: str, destination: Path) -> list[Path]:
    repo = repo.resolve()
    # Keep the configured interpreter launcher path instead of resolving its
    # symlink target. Virtual environments commonly expose bin/python as a
    # symlink to the system interpreter; systemd must execute the venv path so
    # Python discovers pyvenv.cfg and the NBOT dependency environment.
    python = Path(os.path.abspath(os.path.expanduser(str(python))))
    if not repo.is_dir():
        raise ValueError(f"NBOT_REPO_NOT_FOUND:{repo}")
    if not python.is_file():
        raise ValueError(f"NBOT_PYTHON_NOT_FOUND:{python}")
    if any(ch.isspace() for ch in str(repo)) or any(ch.isspace() for ch in str(python)):
        raise ValueError("NBOT_DEPLOY_PATH_WHITESPACE_UNSUPPORTED")
    user = str(user or "").strip()
    if not user:
        raise ValueError("NBOT_SERVICE_USER_REQUIRED")

    template_root = Path(__file__).resolve().parent
    destination.mkdir(parents=True, exist_ok=True)
    written = []
    for unit in UNIT_NAMES:
        template = (template_root / f"{unit}.in").read_text(encoding="utf-8")
        rendered = (
            template.replace("@NBOT_REPO@", str(repo))
            .replace("@NBOT_PYTHON@", str(python))
            .replace("@NBOT_USER@", user)
        )
        if "@NBOT_" in rendered:
            raise RuntimeError(f"NBOT_DEPLOY_TEMPLATE_UNRESOLVED:{unit}")
        target = destination / unit
        target.write_text(rendered, encoding="utf-8")
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--destination", default="/etc/systemd/system")
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()

    written = render_units(
        repo=Path(args.repo),
        python=Path(args.python),
        user=args.user,
        destination=Path(args.destination),
    )
    for path in written:
        print(f"WROTE {path}")

    if Path(args.destination).resolve() == Path("/etc/systemd/system"):
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        if args.enable or args.start:
            subprocess.run(["systemctl", "enable", *UNIT_NAMES], check=True)
        if args.start:
            subprocess.run(["systemctl", "start", *UNIT_NAMES], check=True)
    elif args.enable or args.start:
        raise ValueError("NBOT_ENABLE_REQUIRES_SYSTEMD_DESTINATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
