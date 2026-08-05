"""Single entrypoint for the configured trading environment."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from config import EXECUTION_MODE, TRADING_ENV
from runtime_runner import run_environment


def runtime_description() -> tuple[str, str]:
    if TRADING_ENV == "TESTNET" and EXECUTION_MODE == "TRADE":
        return "Binance Futures Testnet", "Binance testnet orders"

    if TRADING_ENV == "TESTNET" and EXECUTION_MODE == "SHADOW":
        return "Binance Futures Testnet", "Local paper orders"

    if TRADING_ENV == "LIVE" and EXECUTION_MODE == "SHADOW":
        return "Binance Futures Mainnet", "Local paper orders"

    if TRADING_ENV == "LIVE" and EXECUTION_MODE == "TRADE":
        return "Binance Futures Mainnet", "Live exchange orders"

    return "UNKNOWN", "UNKNOWN"


def confirm_start(*, assume_yes: bool) -> bool:
    market, orders = runtime_description()

    print("Starting:\n")
    print(f"Environment : {TRADING_ENV}")
    print(f"Execution   : {EXECUTION_MODE}")
    print(f"Market      : {market}")
    print(f"Orders      : {orders}")

    if assume_yes:
        print("Confirmation: --yes")
        return True

    if not sys.stdin.isatty():
        print(
            "\nSTART_CONFIRMATION_REQUIRED | "
            "run interactively or pass --yes",
            file=sys.stderr,
        )
        return False

    answer = input("\nContinue? (y/N): ").strip().lower()
    return answer in {"y", "yes"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start the configured trading bot"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm startup without an interactive prompt",
    )
    args = parser.parse_args(argv)

    if not confirm_start(assume_yes=args.yes):
        print("Startup cancelled.")
        return 1

    run_environment(expected_environment=TRADING_ENV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
