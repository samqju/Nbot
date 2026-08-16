#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from nbot.execution import ExecutionConfig, NO_ENTRY_AUTHORITY


def main() -> int:
    parser = argparse.ArgumentParser(description="NBOT V2.7 Execution boundary")
    parser.add_argument("--self-check", action="store_true", help="validate the V2.7 fail-closed execution configuration")
    args = parser.parse_args()
    cfg = ExecutionConfig()
    cfg.validate()
    if not args.self_check:
        print("NBOT_V2_7_EXECUTION_NOT_STARTED: no exchange adapter is enabled until the V2.8 Testnet mechanical canary")
        return 2
    print(json.dumps({
        "phase": "V2.7",
        "role": "EXECUTION_CAPITAL_BOUNDARY",
        "environment": cfg.environment,
        "entry_authority": NO_ENTRY_AUTHORITY,
        "approved_exit_policies": list(cfg.allowed_exit_policies),
        "order_adapter": "NONE_UNTIL_V2_8",
        "status": "PASS_FAIL_CLOSED",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
