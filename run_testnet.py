# run_testnet.py
# ==========================================================
# Phase F.1 — Testnet Engine Runner (READ-ONLY)
# ==========================================================
# Purpose:
# - Wire TradingEngine to TestnetExchange
# - Validate:
#   • price stream
#   • position truth
#   • reconciliation
#   • halt semantics
# - NO trading allowed in this phase
#
# Engine remains the sole authority.
# ==========================================================

from dotenv import load_dotenv
load_dotenv()

from engine import TradingEngine
from execution.testnet_exchange import TestnetExchange
from utils.logger import system_logger
from utils.telegram_notifier import configure, send_message
import os

def main():
    log = system_logger()
    log.info("BOOTSTRAP_START | environment=TESTNET")

    # ------------------------------------------------------
    # Optional: Telegram configuration (safe if unset)
    # ------------------------------------------------------
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if tg_token and tg_chat_id:
        configure(tg_token, tg_chat_id)
        log.info("TELEGRAM_CONFIGURED")
    else:
        log.info("TELEGRAM_NOT_CONFIGURED")

    # ------------------------------------------------------
    # Initialize adapter (READ-ONLY)
    # ------------------------------------------------------
    try:
        exchange = TestnetExchange()
    except Exception as e:
        log.critical(f"TESTNET_EXCHANGE_INIT_FAILED | {e}")
        return

    # ------------------------------------------------------
    # Initialize engine
    # ------------------------------------------------------
    engine = TradingEngine(exchange=exchange)

    # ------------------------------------------------------
    # Start engine
    # ------------------------------------------------------
    try:
        engine.start()
    except KeyboardInterrupt:
        log.info("KEYBOARD_INTERRUPT | shutting down")
        send_message(
            "🟡 <b>ENGINE STOPPED (MANUAL)</b>\n\n"
            "Reason: KeyboardInterrupt (Ctrl+C)\n"
            "Status: STOPPED\n"
        )
    except Exception as e:
        log.critical(f"FATAL_ENGINE_ERROR | {e}")
        raise


if __name__ == "__main__":
    main()
