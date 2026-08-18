#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from nbot.config.validation import MachineRole, detect_role


def main() -> int:
    root = Path(__file__).resolve().parent
    role = detect_role(root)
    if role is not MachineRole.EXECUTION:
        raise SystemExit("NBOT_EXECUTION_WRONG_MACHINE_ROLE")
    raise SystemExit(
        "NBOT_V3_EXECUTION_NOT_IMPLEMENTED: complete V3.1 before starting Execution"
    )


if __name__ == "__main__":
    raise SystemExit(main())
