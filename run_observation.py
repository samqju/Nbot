"""Start the public-data-only NBOT Observation Worker."""

from __future__ import annotations

import os

from communication.observation_server import ObservationHTTPServer
from config import EXECUTION_MODE, TRADING_ENV
from execution.binance_market_client import BinanceMarketClient
from utils.logger import system_logger
from utils.process_lock import BotAlreadyRunningError, SingleInstanceLock
from workers.observation_worker import ObservationWorker


def main() -> int:
    system_log = system_logger()
    lock = SingleInstanceLock(
        path=f"runtime/OBSERVATION_{TRADING_ENV}.lock"
    )
    try:
        lock.acquire(
            environment=TRADING_ENV,
            execution_mode=EXECUTION_MODE,
        )
    except BotAlreadyRunningError as exc:
        system_log.critical(str(exc))
        return 1

    system_log.info(
        "OBSERVATION_INSTANCE_LOCK_ACQUIRED | "
        f"path={lock.path} | pid={os.getpid()}"
    )
    market_client = BinanceMarketClient(system_log=system_log)
    worker = ObservationWorker(
        system_log=system_log,
        market_client=market_client,
    )
    api_server = ObservationHTTPServer(
        target=worker,
        host="127.0.0.1",
        port=8765,
        system_log=system_log,
    )
    api_server.start()
    try:
        worker.run_forever()
    except KeyboardInterrupt:
        system_log.info("OBSERVATION_KEYBOARD_INTERRUPT | shutting_down=true")
        return 0
    finally:
        api_server.stop()
        market_client.disconnect()
        lock.release()
        system_log.info("OBSERVATION_INSTANCE_LOCK_RELEASED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
