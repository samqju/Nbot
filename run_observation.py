#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from nbot.config.validation import MachineRole, detect_role


def main() -> int:
    root = Path(__file__).resolve().parent
    role = detect_role(root)
    if role is not MachineRole.OBSERVATION:
        raise SystemExit("NBOT_OBSERVATION_WRONG_MACHINE_ROLE")
    raise SystemExit(
        "NBOT_V3_OBSERVATION_NOT_IMPLEMENTED: complete V3.3 before starting Observation"
    )


if __name__ == "__main__":
    raise SystemExit(main())
