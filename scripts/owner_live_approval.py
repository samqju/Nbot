#!/usr/bin/env python3
"""Explicit on-VPS owner approval. NEVER callable through Telegram.

A timed approval authorizes entries in a separately configured Freqtrade live
process. This does not start the process, change dry_run, configure keys,
promote a model, modify positions, or certify that M1-M7 are complete.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile

PRIVATE_DIR = Path(__file__).resolve().parents[1] / "live_private"
APPROVAL = PRIVATE_DIR / "approval.json"
MAX_HOURS = 24
CHALLENGE = "I AUTHORIZE REAL BINANCE FUTURES TRADING"


def make_approval(owner: str, model_id: str, hours: int, issued_at: int) -> dict:
    if not re.fullmatch(r"[1-9]\d{4,19}", owner):
        raise ValueError("Owner must be one positive private Telegram user/chat ID")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{3,90}", model_id):
        raise ValueError("Invalid model identifier")
    if type(hours) is not int or not 1 <= hours <= MAX_HOURS:
        raise ValueError("Approval duration must be 1–24 hours")
    return {
        "approval": "NBOT_V6_OWNER_ARMED",
        "owner_telegram_id": owner,
        "model_identifier": model_id,
        "issued_at": issued_at,
        "expires_at": issued_at + 3600 * hours,
    }


def write_private_approval(directory: Path, data: dict) -> Path:
    """Atomic file; user-only permissions. Fail if directory is a symlink."""
    if directory.is_symlink():
        raise ValueError("Live private directory cannot be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    target = directory / "approval.json"
    if target.is_symlink():
        raise ValueError("Approval cannot be a symlink")
    fd, name = tempfile.mkstemp(prefix=".approval-", suffix=".json", dir=str(directory))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(data, output)
            output.write("\n")
        os.replace(name, target)
        return target
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--arm", action="store_true")
    action.add_argument("--revoke", action="store_true")
    action.add_argument("--status", action="store_true")
    parser.add_argument("--owner-telegram-id", default="")
    parser.add_argument("--model-identifier", default="")
    parser.add_argument("--hours", type=int, default=8)
    args = parser.parse_args(argv)

    if args.revoke:
        APPROVAL.unlink(missing_ok=True)
        print("Live arm file revoked. NEW live entries are blocked; existing exits remain managed.")
        return 0
    if args.status:
        if not APPROVAL.exists():
            print("NOT ARMED")
        else:
            # Only prints expiration, no auth credentials.
            try:
                data = json.loads(APPROVAL.read_text(encoding="utf-8"))
                end = datetime.fromtimestamp(data["expires_at"], timezone.utc)
                print(f"Arm record exists, expires {end.isoformat()}; live runtime must recheck all gates.")
            except (OSError, ValueError, KeyError, TypeError):
                print("Arm record unreadable or invalid; live entries must be denied.")
        return 0

    try:
        approved = make_approval(
            args.owner_telegram_id, args.model_identifier,
            args.hours, int(datetime.now(timezone.utc).timestamp())
        )
    except ValueError as e:
        parser.error(str(e))
    print("REAL MONEY RISK. This does not validate trading performance or strategy.")
    print("Owner authorization is intended ONLY after formal M7 acceptance.")
    response = input(f"Type exactly '{CHALLENGE}' to create a time-limited local arm: ")
    if response != CHALLENGE:
        print("Refused: no approval created.")
        return 1
    path = write_private_approval(PRIVATE_DIR, approved)
    print(f"ARM FILE CREATED at {path} (user-only permission, duration <=24h).")
    print("No exchange orders placed. Telegram cannot create an arm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
