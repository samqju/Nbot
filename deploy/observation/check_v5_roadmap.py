"""Require an updated V5 development ledger in every V5-related PR.

Use on pull-request CI only; compares PR base against the proposed head.
No GitHub API dependency or Git mutation.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

ROADMAP = "docs/NBOT_V5_MASTER_DEVELOPMENT_PLAN.md"
V5_PATH_PREFIXES = (
    "nbot/observation/v5_",
    "tests/test_v5_",
    "deploy/observation/run_v5_",
    "deploy/observation/v5_",
    "docs/V5_",
)


def requires_roadmap(paths: list[str]) -> bool:
    return any(
        path.startswith(V5_PATH_PREFIXES) or path == ROADMAP
        for path in paths
    )


def check_paths(paths: list[str]) -> tuple[bool, str]:
    if not requires_roadmap(paths):
        return True, "V5 roadmap change not required"
    if ROADMAP not in paths:
        return False, f"V5 changes require same-PR update of {ROADMAP}"
    return True, "V5 roadmap updated alongside implementation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    arguments = parser.parse_args()
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR",
         f"{arguments.base_sha}...HEAD"],
        text=True, capture_output=True, check=False,
    )
    if proc.returncode:
        print(proc.stderr or "Could not compare against PR base", file=sys.stderr)
        return 2
    changed = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
    passed, reason = check_paths(changed)
    print(reason)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
