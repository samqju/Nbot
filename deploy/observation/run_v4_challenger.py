#!/usr/bin/env python3
"""Operator entry point for the paper-only V4 ranking challenger."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from nbot.observation.ranking_v4 import V4RankingChallenger
from nbot.observation.research_memory import ResearchMemoryStore


def git_sha(root: Path) -> str:
    value = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if len(value) != 40:
        raise ValueError("V4_RELEASE_SHA_UNAVAILABLE")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", action="store_true")
    parser.add_argument(
        "--memory",
        default="data/observation/live/research_memory.db",
    )
    parser.add_argument(
        "--ledger",
        default="data/observation/live/decision_outcomes.db",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    memory = ResearchMemoryStore(root / args.memory)
    learner = V4RankingChallenger(
        memory,
        release_sha=git_sha(root),
        ledger_path=root / args.ledger,
    )
    result = learner.train_if_needed() if args.train else learner.status()
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
