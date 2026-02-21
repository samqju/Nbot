# ==========================================================
# UNIVERSE MANAGER (MEMORY-DRIVEN GOVERNANCE)
# ==========================================================
# Owns:
# - Universe snapshot loading (startup recovery)
# - Internal universe regeneration (no cron required)
# - Structural validation
# - Strategy wiring
# - Strategy warmup
# - Safe governance reload (capital boundary aware)
# ==========================================================

import json
import os
import time
from datetime import datetime, timezone
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

    # ======================================================
    # STARTUP LOAD (RECOVERY FROM SNAPSHOT)
    # ======================================================

    def load(self):

        if not os.path.exists(UNIVERSE_SNAPSHOT_FILE):
            raise RuntimeError("UNIVERSE_SNAPSHOT_MISSING")

        with open(UNIVERSE_SNAPSHOT_FILE, "r") as f:
            snapshot = json.load(f)

        symbols = snapshot.get("symbols")
        generated_at = snapshot.get("generated_at")

        self._validate_symbols(symbols)

        self.symbols = sorted(symbols)
        self.generated_at = generated_at

        self.system_log.info(
            f"UNIVERSE_LOADED | count={len(self.symbols)} | generated_at={generated_at}"
        )

        self.strategy.set_universe(self.symbols)

    # ======================================================
    # INTERNAL BUILD (REPLACES CRON)
    # ======================================================

    def _build_universe(self):

        # Import locally to avoid circular dependency
        from universe_selector_testnet import build_universe

        symbols = build_universe()

        self._validate_symbols(symbols)

        return sorted(symbols)

    # ======================================================
    # STRICT VALIDATION
    # ======================================================

    def _validate_symbols(self, symbols):

        if not isinstance(symbols, list):
            raise RuntimeError("UNIVERSE_SYMBOLS_NOT_LIST")

        if len(symbols) != EXPECTED_UNIVERSE_SIZE:
            raise RuntimeError(
                f"UNIVERSE_INVALID_SIZE | expected={EXPECTED_UNIVERSE_SIZE} | actual={len(symbols)}"
            )

        for s in symbols:

            if not isinstance(s, str):
                raise RuntimeError("UNIVERSE_SYMBOL_NOT_STRING")

            if not s.isascii():
                raise RuntimeError(f"UNIVERSE_SYMBOL_NON_ASCII | {s}")

            if not s.endswith("USDT"):
                raise RuntimeError(f"UNIVERSE_SYMBOL_INVALID_SUFFIX | {s}")

            base = s.replace("USDT", "")

            if not base.isalnum():
                raise RuntimeError(f"UNIVERSE_SYMBOL_INVALID_CHARS | {s}")

    # ======================================================
    # ATOMIC SNAPSHOT PERSISTENCE
    # ======================================================

    def _persist_snapshot(self, symbols):

        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(symbols),
            "symbols": symbols,
        }

        tmp_path = UNIVERSE_SNAPSHOT_FILE + ".tmp"

        with open(tmp_path, "w") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)

        os.replace(tmp_path, UNIVERSE_SNAPSHOT_FILE)

    # ======================================================
    # PUBLIC WARMUP (USED BY CORE AT STARTUP)
    # ======================================================

    def warmup(self, exchange):
        """
        Warm entire universe (startup use).
        """
        self._warm_symbols(self.symbols, exchange)

        self.system_log.info(
            f"STRATEGY_WARMUP_COMPLETE | symbols={len(self.symbols)}"
        )

    # ======================================================
    # STRATEGY WARMUP
    # ======================================================

    def _warm_symbols(self, symbols, exchange):

        for symbol in symbols:

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

    # ======================================================
    # HOT RELOAD (MEMORY-DRIVEN)
    # ======================================================
    def maybe_reload(self, *, exchange, state, safety, force=False):

        now = time.time()

        if not force:
            if now - self._last_reload_ts < UNIVERSE_RELOAD_INTERVAL_SEC:
                return

        self._last_reload_ts = now

        # --------------------------------------------------
        # Build latest governance state (in memory)
        # --------------------------------------------------

        try:
            new_symbols = self._build_universe()
        except Exception as e:
            self.error_log.error(f"UNIVERSE_BUILD_FAILED | {e}")
            return

        # No change
        if new_symbols == self.symbols:
            self.system_log.info("UNIVERSE_RELOAD_NO_CHANGE")
            return

        # --------------------------------------------------
        # Capital Boundary Guards
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
        # Apply Delta
        # --------------------------------------------------

        old_symbols = set(self.symbols)
        new_set = set(new_symbols)

        added = new_set - old_symbols
        removed = old_symbols - new_set

        # Enforce leverage only for added symbols
        if added:
            exchange.enforce_leverage_for_universe(list(added))

        # Warm only new symbols
        if added:
            self._warm_symbols(list(added), exchange)

        # Update memory
        self.symbols = new_symbols
        self.generated_at = datetime.now(timezone.utc).isoformat()

        # Persist snapshot only AFTER successful reload
        self._persist_snapshot(self.symbols)

        # Inform strategy
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
