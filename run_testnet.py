# ==========================================================
# TESTNET ENGINE RUNNER
# ==========================================================
# Bootstrap boundary for TESTNET execution.
#
# Responsibilities:
# - Load environment
# - Configure notifications
# - Construct adapter
# - Construct engine
# - Start lifecycle
#
# No trading logic.
# No policy logic.
# No exchange logic.
# ==========================================================

# ==========================================================
# SECTION 1 — ENVIRONMENT (MUST LOAD BEFORE OTHER IMPORTS)
# ==========================================================

from dotenv import load_dotenv
load_dotenv()  # Critical: must execute before adapter import

import os
import sys

from engine import TradingEngine
from execution.testnet_exchange import TestnetExchange
from utils.logger import system_logger
from utils.telegram_notifier import configure, send_message


# ==========================================================
# SECTION 2 — TELEGRAM CONFIGURATION
# ==========================================================

def configure_notifications(log):
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if tg_token and tg_chat_id:
        configure(tg_token, tg_chat_id)
        log.info("TELEGRAM_CONFIGURED")
    else:
        log.info("TELEGRAM_NOT_CONFIGURED")


# ==========================================================
# SECTION 3 — ADAPTER FACTORY
# ==========================================================

def build_exchange(log):
    try:
        return TestnetExchange()
    except Exception as e:
        log.critical(f"TESTNET_EXCHANGE_INIT_FAILED | {e}")
        sys.exit(1)


# ==========================================================
# SECTION 4 — ENGINE FACTORY
# ==========================================================

def build_engine(exchange):
    return TradingEngine(exchange=exchange)


# ==========================================================
# SECTION 5 — EXECUTION LIFECYCLE
# ==========================================================

def run_engine(engine, log):
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


# ==========================================================
# ENTRYPOINT
# ==========================================================

def main():
    log = system_logger()

    log.info("BOOTSTRAP_START | environment=TESTNET")

    configure_notifications(log)

    exchange = build_exchange(log)
    engine = build_engine(exchange)

    run_engine(engine, log)


if __name__ == "__main__":
    main()
