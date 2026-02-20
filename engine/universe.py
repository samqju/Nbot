# ==========================================================
# UNIVERSE MANAGER
# ==========================================================
# Owns:
# - Universe snapshot loading
# - Structural validation
# - Strategy wiring
# - Strategy warmup
# ==========================================================

import json
import os
import time
from utils.telegram_notifier import send_info

UNIVERSE_SNAPSHOT_FILE = "universe_snapshot.json"
EXPECTED_UNIVERSE_SIZE = 30
UNIVERSE_RELOAD_INTERVAL_SEC = 30 * 60  # 30 minutes


class UniverseManager:

    def __init__(self, strategy, system_log, error_log):
        self.strategy = strategy
        self.system_log = system_log
        self.error_log = error_log
        self.symbols = []
        self.generated_at = None
        self._last_reload_ts = 0

    # --------------------------------------------------
    # Load Universe Snapshot
    # --------------------------------------------------

    def load(self):

        if not os.path.exists(UNIVERSE_SNAPSHOT_FILE):
            raise RuntimeError("UNIVERSE_SNAPSHOT_MISSING")

        with open(UNIVERSE_SNAPSHOT_FILE, "r") as f:
            snapshot = json.load(f)

        symbols = snapshot.get("symbols")
        generated_at = snapshot.get("generated_at")

        assert isinstance(symbols, list)
        assert len(symbols) == EXPECTED_UNIVERSE_SIZE

        for s in symbols:
            assert isinstance(s, str)
            assert s.endswith("USDT")

        self.symbols = symbols
        self.generated_at = generated_at

        self.system_log.info(
            f"UNIVERSE_LOADED | count={len(symbols)} | generated_at={generated_at}"
        )

        # Inform strategy
        self.strategy.set_universe(symbols)

    # --------------------------------------------------
    # Warmup Strategy
    # --------------------------------------------------

    def warmup(self, exchange):

        WARMUP_INTERVAL = "1m"
        WARMUP_LIMIT = 50

        for symbol in self.symbols:

            candles = exchange.get_historical_candles(
                symbol=symbol,
                interval=WARMUP_INTERVAL,
                limit=WARMUP_LIMIT,
            )

            for ts, o, h, l, c in candles:
                self.strategy.seed_candle(
                    symbol=symbol,
                    o=o,
                    h=h,
                    l=l,
                    c=c,
                    timestamp=ts,
                )

        self.system_log.info(
            f"STRATEGY_WARMUP_COMPLETE | symbols={len(self.symbols)}"
        )

    # --------------------------------------------------
    # Hot Reload (Safe Governance Reload)
    # --------------------------------------------------

    def maybe_reload(self, *, exchange, state, safety):

        now = time.time()

        if now - self._last_reload_ts < UNIVERSE_RELOAD_INTERVAL_SEC:
            return

        self._last_reload_ts = now

        # --------------------------------------------------
        # Safety Gates
        # --------------------------------------------------

        if state.get_open_position() is not None:
            self.system_log.info("UNIVERSE_RELOAD_SKIPPED_POSITION_OPEN")
            return

        if not safety.is_safe():
            return

        engine_state = state.get_state().get("engine_state")
        if engine_state != "RUNNING":
            return

        # --------------------------------------------------
        # Attempt Reload
        # --------------------------------------------------

        try:
            old_symbols = set(self.symbols)

            # Load snapshot again
            self.load()

            new_symbols = set(self.symbols)

            added = new_symbols - old_symbols
            removed = old_symbols - new_symbols

            if not added and not removed:
                self.system_log.info("UNIVERSE_RELOAD_NO_CHANGE")
                return

            # Enforce leverage for new symbols
            if added:
                exchange.enforce_leverage_for_universe(list(added))

            # Warmup only new symbols
            for symbol in added:
                candles = exchange.get_historical_candles(
                    symbol=symbol,
                    interval="1m",
                    limit=50,
                )
                for ts, o, h, l, c in candles:
                    self.strategy.seed_candle(
                        symbol=symbol,
                        o=o,
                        h=h,
                        l=l,
                        c=c,
                        timestamp=ts,
                    )

            # Atomically update strategy universe
            self.strategy.set_universe(self.symbols)

            self.system_log.info(
                f"UNIVERSE_RELOADED | "
                f"added={len(added)} | removed={len(removed)} | "
                f"added_symbols={sorted(list(added))} | "
                f"removed_symbols={sorted(list(removed))}"
            )

            send_info(
                "UNIVERSE RELOADED",
                f"Added: {len(added)}\nRemoved: {len(removed)}"
            )

        except Exception as e:
            self.error_log.error(
                f"UNIVERSE_RELOAD_FAILED | {e}"
            )
