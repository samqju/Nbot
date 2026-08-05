"""Runtime exchange selection with fail-closed live-order policy."""

from config import (
    EXECUTION_MODE,
    PAPER_STARTING_BALANCE_USD,
    PAPER_STATE_PATH,
    PAPER_TRADES_PATH,
    TRADING_ENV,
    LIVE_ADAPTER_MODE,
    LIVE_ORDER_WRITES_ENABLED,
    LIVE_TRADING_ARM_FILE,
    LIVE_TRADING_CONFIRMATION,
)
from execution.binance_market_client import BinanceMarketClient
from execution.paper_account import PaperAccount
from execution.paper_exchange import PaperExchange


def build_exchange(*, system_log):
    """Build the only adapter allowed for the configured runtime mode."""
    if EXECUTION_MODE == "SHADOW":
        source = f"PAPER_{TRADING_ENV}"
        market_client = BinanceMarketClient(system_log=system_log)
        account = PaperAccount(
            starting_balance_usd=PAPER_STARTING_BALANCE_USD,
            state_path=PAPER_STATE_PATH,
            trades_path=PAPER_TRADES_PATH,
            source=source,
        )
        system_log.info(
            "PAPER_EXCHANGE_SELECTED | "
            f"market_environment={TRADING_ENV} | source={source}"
        )
        return PaperExchange(
            market_client=market_client,
            account=account,
            system_log=system_log,
        )

    if TRADING_ENV == "TESTNET" and EXECUTION_MODE == "TRADE":
        from execution.testnet_exchange import TestnetExchange

        system_log.info("TESTNET_EXCHANGE_SELECTED | execution=TRADE")
        return TestnetExchange(system_log=system_log)

    if TRADING_ENV == "LIVE" and EXECUTION_MODE == "TRADE":
        from execution.live_exchange import LiveExchange
        from execution.live_trading_guard import LiveTradingGuard

        exchange = LiveExchange(system_log=system_log)
        report = LiveTradingGuard(
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
            adapter_mode=LIVE_ADAPTER_MODE,
            confirmation=LIVE_TRADING_CONFIRMATION,
            writes_requested=LIVE_ORDER_WRITES_ENABLED,
            arm_file=LIVE_TRADING_ARM_FILE,
            adapter=exchange,
        ).validate_read_only()
        system_log.info(
            "LIVE_CAPABILITY_GATE_OK | "
            f"adapter_mode={report.adapter_mode} | "
            "writes_requested=false | writes_available=false | "
            "real_orders=BLOCKED"
        )
        system_log.info(
            "LIVE_EXCHANGE_SELECTED | mode=READ_ONLY | real_orders=BLOCKED"
        )
        return exchange

    raise RuntimeError(
        "EXCHANGE_MODE_UNSUPPORTED | "
        f"environment={TRADING_ENV} | execution_mode={EXECUTION_MODE}"
    )
