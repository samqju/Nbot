"""Shared bootstrap for LIVE and TESTNET engine runners."""

import os
import sys

from engine import TradingEngine
from execution.exchange_factory import build_exchange as build_runtime_exchange
from config import TRADING_ENV, EXECUTION_MODE
from utils.logger import system_logger, trade_logger
from utils.telegram_notifier import configure, send_message, inject_loggers
from utils.process_lock import (
    BotAlreadyRunningError,
    SingleInstanceLock,
)


def run_environment(*, expected_environment: str, require_trade_mode: bool = False) -> None:
    system_log = system_logger()
    trade_log = trade_logger()
    inject_loggers(system_log)

    instance_lock = SingleInstanceLock()
    try:
        instance_lock.acquire(
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
        )
    except BotAlreadyRunningError as exc:
        system_log.critical(str(exc))
        raise SystemExit(1) from exc

    system_log.info(
        "BOT_INSTANCE_LOCK_ACQUIRED | "
        f"path={instance_lock.path} | pid={os.getpid()}"
    )

    try:
        _run_environment_locked(
            expected_environment=expected_environment,
            require_trade_mode=require_trade_mode,
            system_log=system_log,
            trade_log=trade_log,
        )
    finally:
        instance_lock.release()
        system_log.info("BOT_INSTANCE_LOCK_RELEASED")


def _run_environment_locked(
    *,
    expected_environment: str,
    require_trade_mode: bool,
    system_log,
    trade_log,
) -> None:
    if TRADING_ENV != expected_environment:
        system_log.critical(
            "BOOTSTRAP_ENVIRONMENT_MISMATCH | "
            f"runner={expected_environment} | configured={TRADING_ENV}"
        )
        raise SystemExit(1)

    if require_trade_mode and EXECUTION_MODE != "TRADE":
        system_log.critical(
            "TESTNET_BOOTSTRAP_MODE_MISMATCH | "
            f"environment={TRADING_ENV} | execution_mode={EXECUTION_MODE} | "
            "required_execution_mode=TRADE"
        )
        raise SystemExit(1)

    start_event = (
        "TESTNET_BOOTSTRAP_START"
        if expected_environment == "TESTNET"
        else "BOOTSTRAP_START"
    )
    log = system_log.warning if expected_environment == "TESTNET" else system_log.info
    suffix = " | orders=REAL_TESTNET | real_money=false" if expected_environment == "TESTNET" else ""
    log(
        f"{start_event} | environment={TRADING_ENV} | "
        f"execution_mode={EXECUTION_MODE}{suffix}"
    )

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        configure(token, chat_id)
        system_log.info("TELEGRAM_CONFIGURED")
    else:
        system_log.warning("TELEGRAM_NOT_CONFIGURED")

    try:
        exchange = build_runtime_exchange(system_log=system_log)
        engine = TradingEngine(exchange=exchange, system_log=system_log, trade_log=trade_log)
    except Exception as exc:
        system_log.error(f"BOOTSTRAP_BUILD_FAILED | error={exc}")
        raise SystemExit(1) from exc

    system_log.info("ENGINE_STARTING")
    try:
        engine.start()
        system_log.info("ENGINE_EXITED_NORMALLY")
    except KeyboardInterrupt:
        system_log.info("KEYBOARD_INTERRUPT | shutting_down=true")
        try:
            position = engine.state.get_state().get("open_position")
            if position:
                system_log.error(
                    "ENGINE_STOP_WITH_OPEN_POSITION | "
                    f"symbol={position.get('symbol')} | "
                    f"entry={position.get('entry_price')} | qty={position.get('qty')}"
                )
        except Exception as exc:
            system_log.warning(f"ENGINE_STOP_STATE_CHECK_FAILED | error={exc}")
        send_message(
            "🟡 <b>ENGINE STOPPED (MANUAL)</b>\n\n"
            "Reason: KeyboardInterrupt (Ctrl+C)\nStatus: STOPPED\n"
        )
    except Exception as exc:
        system_log.error(f"FATAL_ENGINE_ERROR | {exc}")
        raise
