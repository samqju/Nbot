"""Start the capital-only NBOT Execution Worker."""

from __future__ import annotations

import argparse
import os
import sys

from communication.observation_client import ObservationClient
from config import EXECUTION_MODE, OBSERVATION_CONTROL_TOKEN, TRADING_ENV
from execution.exchange_factory import build_exchange
from utils.logger import (
    restrict_info_to_prefixes,
    system_logger,
    trade_logger,
)
from utils.process_lock import BotAlreadyRunningError, SingleInstanceLock
from utils.telegram_notifier import configure, inject_loggers, send_message
from workers.execution_worker import ExecutionWorker


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
    print("Starting Execution Worker:\n")
    print(f"Environment : {TRADING_ENV}")
    print(f"Execution   : {EXECUTION_MODE}")
    print(f"Market      : {market}")
    print(f"Orders      : {orders}")
    print("Observation : http://127.0.0.1:8765")

    if assume_yes:
        print("Confirmation: --yes")
        return True
    if not sys.stdin.isatty():
        print(
            "\nSTART_CONFIRMATION_REQUIRED | run interactively or pass --yes",
            file=sys.stderr,
        )
        return False
    return input("\nContinue? (y/N): ").strip().lower() in {"y", "yes"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Start the NBOT Execution Worker"
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

    system_log = system_logger()
    restrict_info_to_prefixes(
        system_log,
        (
            "EXECUTION_STARTED",
            "OPERATOR_",
            "PUBLIC_POSITION_WS_RECOVERED",
        ),
    )
    trade_log = trade_logger()
    inject_loggers(system_log)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        configure(token, chat_id)
        system_log.info("TELEGRAM_CONFIGURED")
    else:
        system_log.warning("TELEGRAM_NOT_CONFIGURED")

    lock = SingleInstanceLock(path=f"runtime/EXECUTION_{TRADING_ENV}.lock")
    try:
        lock.acquire(
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
        )
    except BotAlreadyRunningError as exc:
        system_log.critical(str(exc))
        return 1

    exchange = None
    worker = None
    try:
        system_log.info(
            "EXECUTION_INSTANCE_LOCK_ACQUIRED | "
            f"path={lock.path} | pid={os.getpid()}"
        )
        exchange = build_exchange(system_log=system_log)
        observation_client = ObservationClient(
            auth_token=OBSERVATION_CONTROL_TOKEN or None,
            system_log=system_log,
        )
        worker = ExecutionWorker(
            exchange=exchange,
            observation_client=observation_client,
            system_log=system_log,
            trade_log=trade_log,
        )
        worker.start()
        return 0
    except KeyboardInterrupt:
        system_log.info("EXECUTION_KEYBOARD_INTERRUPT | shutting_down=true")
        if worker is not None:
            try:
                position = worker.state.get_open_position()
                if position:
                    system_log.error(
                        "EXECUTION_STOP_WITH_OPEN_POSITION | "
                        f"symbol={position.get('symbol')} | "
                        f"entry={position.get('entry_price')} | "
                        f"qty={position.get('qty')}"
                    )
            except Exception as exc:
                system_log.warning(
                    f"EXECUTION_STOP_STATE_CHECK_FAILED | error={exc}"
                )
        send_message(
            "🟡 <b>EXECUTION WORKER STOPPED (MANUAL)</b>\n\n"
            "Reason: KeyboardInterrupt (Ctrl+C)\nStatus: STOPPED\n"
        )
        return 0
    except Exception as exc:
        system_log.critical(
            "EXECUTION_BOOTSTRAP_FAILED | "
            f"error={type(exc).__name__}:{exc}"
        )
        return 1
    finally:
        if exchange is not None:
            try:
                exchange.disconnect()
            except Exception as exc:
                system_log.warning(
                    f"EXECUTION_DISCONNECT_FAILED | error={exc}"
                )
        lock.release()
        system_log.info("EXECUTION_INSTANCE_LOCK_RELEASED")


if __name__ == "__main__":
    raise SystemExit(main())
