#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    python = Path(args.python).resolve()
    template = (repo / "deploy/v2/nbot-observation-v2.service.in").read_text()
    unit = (
        template.replace("__REPO__", str(repo))
        .replace("__PYTHON__", str(python))
        .replace("__USER__", args.user)
    )
    target = Path("/etc/systemd/system/nbot-observation-v2.service")
    target.write_text(unit)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    if args.enable:
        subprocess.run(["systemctl", "enable", "nbot-observation-v2.service"], check=True)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
