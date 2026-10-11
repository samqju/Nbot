#!/usr/bin/env python3
"""Operator review CLI for V4 paper contests. No exchange order authority."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from nbot.observation.v4_paper_contest import V4PaperContestStore, V4PaperReviewAdmin


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("status", "promote", "reject"))
    args = parser.parse_args()

    if args.action == "status":
        result = {**V4PaperContestStore().status(),
                  "promotion_review": V4PaperReviewAdmin().promotion_status()}
    else:
        admin = V4PaperReviewAdmin()
        try:
            result = (admin.promote_challenger() if args.action == "promote"
                      else admin.reject_challenger())
        except ValueError as exc:
            print(json.dumps({"status": "BLOCKED", "reason": str(exc),
                              "promotion_review": admin.promotion_status(),
                              "order_authority": "NONE"}, sort_keys=True, indent=2))
            return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
