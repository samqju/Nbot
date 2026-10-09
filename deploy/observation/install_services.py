#!/usr/bin/env python3
"""Render/install NBOT Observation base-role systemd units.

The base role is intentionally small:
- one continuous LIVE raw-evidence collector;
- one systemd timer for bounded 96-event research epochs.

The LIVE_PAPER control plane is rendered but remains opt-in until integrated
paper execution is deliberately enabled. Testnet control remains a separate
regression service and is not part of the base role.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess


BASE_UNIT_NAMES = (
    "nbot-observation-live.service",
    "nbot-research-epoch.service",
    "nbot-research-epoch.timer",
    "nbot-counterfactual-replay.service",
    "nbot-observer.target",
)
OPTIONAL_UNIT_NAMES = (
    "nbot-observation-live-trade-control.service",
    "nbot-observation-testnet-control.service",
    "nbot-observation-live-paper-control.service",
    "nbot-challenger-cycle.service",
)


def _launcher_path(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _plain(value: str, *, field: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"NBOT_{field}_REQUIRED")
    if any(ch.isspace() for ch in value):
        raise ValueError(f"NBOT_{field}_WHITESPACE_UNSUPPORTED")
    return value


def _render(text: str, *, repo: Path, python: Path, user: str) -> str:
    return (
        text.replace("@NBOT_ROOT@", str(repo))
        .replace("@NBOT_PYTHON@", str(python))
        .replace("@NBOT_USER@", user)
    )


def render_units(
    *,
    repo: Path,
    python: Path,
    user: str,
    destination: Path,
    resource_profile: str = "standard",
) -> list[Path]:
    if resource_profile not in {"standard", "tiny"}:
        raise ValueError("NBOT_OBSERVATION_RESOURCE_PROFILE_INVALID")
    repo = Path(repo).resolve()
    python = _launcher_path(python)
    user = _plain(user, field="USER")
    destination = Path(destination)

    if not repo.is_dir():
        raise ValueError(f"NBOT_REPO_MISSING:{repo}")
    if not python.is_file():
        raise ValueError(f"NBOT_PYTHON_MISSING:{python}")

    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for unit_name in BASE_UNIT_NAMES + OPTIONAL_UNIT_NAMES:
        template = repo / "deploy/systemd" / f"{unit_name}.in"
        if not template.is_file():
            raise ValueError(f"NBOT_SYSTEMD_TEMPLATE_MISSING:{template}")
        target = destination / unit_name
        rendered = _render(template.read_text(encoding="utf-8"), repo=repo, python=python, user=user)
        if resource_profile == "tiny" and "[Service]" in rendered:
            research = unit_name in {"nbot-research-epoch.service", "nbot-challenger-cycle.service"}
            settings = "\nEnvironment=NBOT_OBSERVATION_RESOURCE_PROFILE=tiny\n"
            settings += "MemoryHigh=256M\nMemoryMax=384M\nCPUQuota=60%\n" if research else "MemoryHigh=96M\nMemoryMax=160M\n"
            rendered = rendered.replace("[Service]\n", "[Service]" + settings, 1)
        target.write_text(rendered, encoding="utf-8")
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--destination", default="/etc/systemd/system")
    parser.add_argument("--resource-profile", choices=("standard", "tiny"), default="standard")
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--enable-live-paper-control", action="store_true")
    parser.add_argument("--start-live-paper-control", action="store_true")
    parser.add_argument("--enable-live-trade-control", action="store_true")
    parser.add_argument("--start-live-trade-control", action="store_true")
    parser.add_argument("--enable-testnet-control", action="store_true")
    parser.add_argument("--start-testnet-control", action="store_true")
    args = parser.parse_args()

    if args.start_live_paper_control:
        args.enable_live_paper_control = True
    if args.start_live_trade_control:
        args.enable_live_trade_control = True
    if args.start_testnet_control:
        args.enable_testnet_control = True
    written = render_units(
        repo=Path(args.repo),
        python=Path(args.python),
        user=args.user,
        destination=Path(args.destination),
        resource_profile=args.resource_profile,
    )
    for path in written:
        print(f"WROTE {path}")

    destination = Path(args.destination).resolve()
    systemd_destination = Path("/etc/systemd/system")
    wants_systemd_action = (
        args.enable
        or args.start
        or args.enable_live_paper_control
        or args.start_live_paper_control
        or args.enable_live_trade_control
        or args.start_live_trade_control
        or args.enable_testnet_control
        or args.start_testnet_control
    )
    if destination != systemd_destination:
        if wants_systemd_action:
            raise ValueError("NBOT_ENABLE_REQUIRES_SYSTEMD_DESTINATION")
        return 0

    subprocess.run(["systemctl", "daemon-reload"], check=True)

    if args.enable or args.start:
        subprocess.run(["systemctl", "enable", "nbot-observer.target"], check=True)
    if args.enable_live_paper_control:
        subprocess.run(
            ["systemctl", "enable", "nbot-observation-live-paper-control.service"],
            check=True,
        )
    if args.start:
        subprocess.run(["systemctl", "start", "nbot-observer.target"], check=True)
    if args.start_live_paper_control:
        subprocess.run(
            ["systemctl", "start", "nbot-observation-live-paper-control.service"],
            check=True,
        )
    if args.enable_testnet_control:
        subprocess.run(["systemctl", "enable", "nbot-observation-testnet-control.service"], check=True)
    if args.start_testnet_control:
        subprocess.run(["systemctl", "start", "nbot-observation-testnet-control.service"], check=True)
    if args.enable_live_trade_control:
        subprocess.run(["systemctl", "enable", "nbot-observation-live-trade-control.service"], check=True)
    if args.start_live_trade_control:
        subprocess.run(["systemctl", "start", "nbot-observation-live-trade-control.service"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
