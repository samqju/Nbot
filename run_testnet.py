# ==========================================================
# TESTNET ENGINE RUNNER (LOGGING ALIGNED)
# ==========================================================
# Bootstrap boundary for TESTNET execution.
# ==========================================================
# SECTION 1 — ENVIRONMENT (MUST LOAD BEFORE OTHER IMPORTS)
# ==========================================================

from dotenv import load_dotenv
load_dotenv()  # Must execute before adapter import

import os
import sys

from engine import TradingEngine
from execution.testnet_exchange import TestnetExchange

from utils.logger import (
    system_logger,
    trade_logger,
    error_logger,
)

from utils.telegram_notifier import (
    configure,
    send_message,
    inject_loggers,
)

# ==========================================================
# SECTION 2 — LOGGER INITIALIZATION
# ==========================================================

system_log = system_logger()
trade_log = trade_logger()
error_log = error_logger()

# ==========================================================
# SECTION 3 — TELEGRAM CONFIGURATION
# ==========================================================

inject_loggers(system_log, error_log)

def configure_notifications():
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if tg_token and tg_chat_id:
        configure(tg_token, tg_chat_id)
        system_log.info("TELEGRAM_CONFIGURED")
    else:
        error_log.error("TELEGRAM_NOT_CONFIGURED")

# ==========================================================
# SECTION 4 — ADAPTER FACTORY
# ==========================================================

def build_exchange():
    system_log.info("TESTNET_EXCHANGE_BUILD_START")
    try:
        exchange = TestnetExchange(
            system_log=system_log,
            error_log=error_log,
        )
        system_log.info("TESTNET_EXCHANGE_INITIALIZED")
        return exchange
    except Exception as e:
        error_log.error(
            f"TESTNET_EXCHANGE_INIT_FAILED | {e}"
        )
        error_log.error("BOOTSTRAP_ABORTING")
        sys.exit(1)

# ==========================================================
# SECTION 5 — ENGINE FACTORY
# ==========================================================

def build_engine(exchange):
    system_log.info("ENGINE_BUILD_START")
    try:
        engine = TradingEngine(
            exchange=exchange,
            system_log=system_log,
            trade_log=trade_log,
            error_log=error_log,
        )
        system_log.info("ENGINE_BUILD_SUCCESS")
        return engine
    except Exception as e:
        error_log.error(f"ENGINE_BUILD_FAILED | {e}")
        error_log.error("BOOTSTRAP_ABORTING")
        sys.exit(1)

# ==========================================================
# SECTION 6 — EXECUTION LIFECYCLE
# ==========================================================

def run_engine(engine):

    system_log.info("ENGINE_STARTING")

    try:
        engine.start()

        # If engine.start() ever returns cleanly
        system_log.info("ENGINE_EXITED_NORMALLY")

    except KeyboardInterrupt:

        system_log.info("KEYBOARD_INTERRUPT | shutting down")

        try:
            state_snapshot = engine.state.get_state()
            open_position = state_snapshot.get("open_position")

            if open_position:
                error_log.error(
                    "ENGINE_STOP_WITH_OPEN_POSITION | "
                    f"symbol={open_position['symbol']} | "
                    f"entry={open_position['entry_price']} | "
                    f"qty={open_position['qty']}"
                )

        except Exception:
            pass

        send_message(
            "🟡 <b>ENGINE STOPPED (MANUAL)</b>\n\n"
            "Reason: KeyboardInterrupt (Ctrl+C)\n"
            "Status: STOPPED\n"
        )

    except Exception as e:

        error_log.error(f"FATAL_ENGINE_ERROR | {e}")

        # Let crash propagate after logging
        raise

# ==========================================================
# ENTRYPOINT
# ==========================================================

def main():

    system_log.info("BOOTSTRAP_START | environment=TESTNET")

    configure_notifications()

    exchange = build_exchange()
    engine = build_engine(exchange)

    run_engine(engine)


if __name__ == "__main__":
    main()
