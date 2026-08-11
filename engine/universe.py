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
from config import (
    LEVERAGE,
    OBSERVATION_UNIVERSE_REFRESH_SECONDS,
    OBSERVATION_UNIVERSE_SIZE,
    OBSERVATION_UNIVERSE_SNAPSHOT_PATH,
    TRADING_ENV,
    UNIVERSE_SNAPSHOT_PATH,
)
from utils.telegram_notifier import send_info

UNIVERSE_SNAPSHOT_FILE = UNIVERSE_SNAPSHOT_PATH
OBSERVATION_UNIVERSE_SNAPSHOT_FILE = (
    OBSERVATION_UNIVERSE_SNAPSHOT_PATH
)
EXPECTED_UNIVERSE_SIZE = 30
MAX_OBSERVATION_UNIVERSE_SIZE = OBSERVATION_UNIVERSE_SIZE

class UniverseManager:

    def __init__(self, strategy, system_log):
        self.strategy = strategy
        self.system_log = system_log
        self.symbols = []
        self.observation_symbols = []
        self.generated_at = None
        self.observation_generated_at = None
        self._last_observation_refresh_monotonic = 0.0
        self._execution_selection_metadata = {}
        self._ranked_observation_symbols = []
        self._last_reload_status = "NOT_RUN"

    # ======================================================
    # STARTUP LOAD (RECOVERY FROM SNAPSHOT)
    # ======================================================

    def load(self):

        if not os.path.exists(UNIVERSE_SNAPSHOT_FILE):
            self.system_log.warning(
                "UNIVERSE_ENV_SNAPSHOT_MISSING | "
                f"environment={TRADING_ENV} | "
                f"path={UNIVERSE_SNAPSHOT_FILE} | action=BUILD"
            )
            symbols = self._build_universe()
            self._persist_snapshot(symbols)

        with open(UNIVERSE_SNAPSHOT_FILE, "r") as f:
            snapshot = json.load(f)

        snapshot_environment = snapshot.get("environment")
        if snapshot_environment not in {None, TRADING_ENV}:
            raise RuntimeError(
                "UNIVERSE_SNAPSHOT_ENVIRONMENT_MISMATCH | "
                f"expected={TRADING_ENV} | "
                f"actual={snapshot_environment}"
            )

        symbols = snapshot.get("symbols")
        generated_at = snapshot.get("generated_at")

        self._validate_symbols(symbols)

        self.symbols = sorted(symbols)
        self.generated_at = generated_at
        self._execution_selection_metadata = snapshot.get(
            "selection",
            {},
        )

        self.system_log.info(
            "UNIVERSE_LOADED | "
            f"environment={TRADING_ENV} | "
            f"path={UNIVERSE_SNAPSHOT_FILE} | "
            f"count={len(self.symbols)} | "
            f"generated_at={generated_at}"
        )

        self.observation_symbols = (
            self._load_or_build_observation_universe()
        )
        self._ranked_observation_symbols = list(
            self.observation_symbols
        )

        self.system_log.info(
            "OBSERVATION_UNIVERSE_LOADED | "
            f"count={len(self.observation_symbols)} | "
            f"target={MAX_OBSERVATION_UNIVERSE_SIZE} | "
            f"generated_at={self.observation_generated_at}"
        )

        self.strategy.set_universes(
            execution_symbols=self.symbols,
            observation_symbols=self.observation_symbols,
        )
        self._last_observation_refresh_monotonic = (
            time.monotonic()
        )

    # ======================================================
    # INTERNAL BUILD (REPLACES CRON)
    # ======================================================

    def _build_universe(self):

        # Import locally to avoid circular dependency
        from universe_selector import (
            build_universe,
            get_last_build_metadata,
        )

        symbols = build_universe()
        self._execution_selection_metadata = (
            get_last_build_metadata()
        )

        self._validate_symbols(symbols)

        return sorted(symbols)

    def _build_observation_universe(self):
        from observation_universe import build_observation_universe

        original_execution = list(self.symbols)
        symbols = build_observation_universe(
            original_execution,
            require_execution_eligible=False,
        )
        eligible = set(symbols)
        missing = sorted(set(original_execution) - eligible)

        if missing:
            retained = [
                symbol for symbol in original_execution
                if symbol in eligible
            ]
            replacements = [
                symbol for symbol in symbols
                if symbol not in set(original_execution)
            ]
            required = EXPECTED_UNIVERSE_SIZE - len(retained)
            if len(replacements) < required:
                raise RuntimeError(
                    "EXECUTION_UNIVERSE_REPLACEMENT_INSUFFICIENT | "
                    f"missing={missing} | required={required} | "
                    f"available={len(replacements)}"
                )

            replacement_symbols = replacements[:required]
            self.symbols = sorted(retained + replacement_symbols)
            self._validate_symbols(self.symbols)
            self._persist_snapshot(self.symbols)

            self.system_log.warning(
                "EXECUTION_UNIVERSE_OBSERVATION_RECONCILED | "
                f"environment={TRADING_ENV} | "
                f"removed={missing} | "
                f"replacements={replacement_symbols}"
            )

            # Rebuild strictly so the final observation snapshot is guaranteed
            # to contain every corrected execution symbol.
            symbols = build_observation_universe(
                self.symbols,
                require_execution_eligible=True,
            )

        self._validate_observation_symbols(symbols)
        return sorted(symbols)

    def _load_or_build_observation_universe(self):
        if os.path.exists(OBSERVATION_UNIVERSE_SNAPSHOT_FILE):
            try:
                with open(
                    OBSERVATION_UNIVERSE_SNAPSHOT_FILE,
                    "r",
                ) as f:
                    snapshot = json.load(f)
                snapshot_environment = snapshot.get("environment")
                if snapshot_environment not in {None, TRADING_ENV}:
                    raise RuntimeError(
                        "OBSERVATION_UNIVERSE_SNAPSHOT_ENVIRONMENT_MISMATCH | "
                        f"expected={TRADING_ENV} | "
                        f"actual={snapshot_environment}"
                    )
                symbols = snapshot.get("symbols")
                self._validate_observation_symbols(symbols)
                self.observation_generated_at = snapshot.get(
                    "generated_at"
                )
                return sorted(symbols)
            except Exception as e:
                self.system_log.warning(
                    "OBSERVATION_UNIVERSE_SNAPSHOT_REJECTED | "
                    f"error={e}"
                )

        symbols = self._build_observation_universe()
        self.observation_generated_at = (
            datetime.now(timezone.utc).isoformat()
        )
        self._persist_observation_snapshot(symbols)
        return symbols

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

    def _validate_observation_symbols(self, symbols):
        if not isinstance(symbols, list):
            raise RuntimeError(
                "OBSERVATION_UNIVERSE_SYMBOLS_NOT_LIST"
            )
        if not (
            EXPECTED_UNIVERSE_SIZE
            <= len(symbols)
            <= MAX_OBSERVATION_UNIVERSE_SIZE
        ):
            raise RuntimeError(
                "OBSERVATION_UNIVERSE_INVALID_SIZE | "
                f"actual={len(symbols)} | "
                f"max={MAX_OBSERVATION_UNIVERSE_SIZE}"
            )
        if not set(self.symbols).issubset(set(symbols)):
            raise RuntimeError(
                "EXECUTION_UNIVERSE_MISSING_FROM_OBSERVATION"
            )
        for symbol in symbols:
            if (
                not isinstance(symbol, str)
                or not symbol.isascii()
                or not symbol.endswith("USDT")
                or not symbol.replace("USDT", "").isalnum()
            ):
                raise RuntimeError(
                    "OBSERVATION_UNIVERSE_SYMBOL_INVALID | "
                    f"symbol={symbol}"
                )

    # ======================================================
    # ATOMIC SNAPSHOT PERSISTENCE
    # ======================================================

    def _persist_snapshot(self, symbols):

        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(symbols),
            "symbols": symbols,
            "selection": self._execution_selection_metadata,
            "environment": TRADING_ENV,
        }

        os.makedirs(
            os.path.dirname(UNIVERSE_SNAPSHOT_FILE) or ".",
            exist_ok=True,
        )
        tmp_path = UNIVERSE_SNAPSHOT_FILE + ".tmp"

        with open(tmp_path, "w") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)

        os.replace(tmp_path, UNIVERSE_SNAPSHOT_FILE)

    def _persist_observation_snapshot(self, symbols):
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(symbols),
            "target_count": MAX_OBSERVATION_UNIVERSE_SIZE,
            "symbols": sorted(symbols),
            "environment": TRADING_ENV,
        }
        os.makedirs(
            os.path.dirname(OBSERVATION_UNIVERSE_SNAPSHOT_FILE) or ".",
            exist_ok=True,
        )
        tmp_path = OBSERVATION_UNIVERSE_SNAPSHOT_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)
        os.replace(
            tmp_path,
            OBSERVATION_UNIVERSE_SNAPSHOT_FILE,
        )

    # ======================================================
    # PUBLIC WARMUP (USED BY CORE AT STARTUP)
    # ======================================================

    def warmup(self, exchange):
        """
        Warm entire universe (startup use).
        """
        self._warm_symbols(self.observation_symbols, exchange)

        self.system_log.info(
            "STRATEGY_WARMUP_COMPLETE | "
            f"execution_symbols={len(self.symbols)} | "
            f"observation_symbols={len(self.observation_symbols)}"
        )

    # ======================================================
    # STRATEGY WARMUP
    # ======================================================

    def _warm_symbols(self, symbols, exchange):

        required = self.strategy.WARMUP_WINDOW
        request_limit = max(required + 10, 60)

        for symbol in symbols:

            candles = exchange.get_historical_candles(
                symbol=symbol,
                interval="5m",
                limit=request_limit,
            )

            seeded = self.strategy.seed_candle_history(
                symbol=symbol,
                candles=candles,
            )

            if seeded < required:
                raise RuntimeError(
                    f"SYMBOL_WARMUP_INSUFFICIENT | symbol={symbol} | "
                    f"seeded={seeded} | required={required}"
                )

            getattr(self.system_log, "debug", lambda *_args, **_kwargs: None)(
                f"SYMBOL_WARMUP_READY | symbol={symbol} | "
                f"completed_candles={seeded}"
            )

    def _observation_refresh_due(self, *, force=False):
        if force:
            return True
        elapsed = (
            time.monotonic()
            - self._last_observation_refresh_monotonic
        )
        return elapsed >= OBSERVATION_UNIVERSE_REFRESH_SECONDS

    def _build_effective_observation_universe(
        self,
        ranked_symbols,
    ):
        retained = self.strategy.get_retained_observation_symbols()
        effective = sorted(set(ranked_symbols) | set(retained))
        return effective, retained

    # ======================================================
    # HOT RELOAD (MEMORY-DRIVEN)
    # ======================================================
    def maybe_reload(self, *, exchange, force=False):
        """Refresh execution and observation universes safely.

        The persisted observation snapshot contains only the ranked pool.
        The in-memory effective pool may be larger while unfinished virtual
        trades or forward simulations still require candle updates.
        """
        self._last_reload_status = "IN_PROGRESS"
        observation_build_failed = False
        try:
            new_execution = self._build_universe()
        except Exception as e:
            self._last_reload_status = "FAILED_EXECUTION_BUILD"
            self.system_log.error(f"UNIVERSE_BUILD_FAILED | {e}")
            return

        execution_changed = new_execution != self.symbols

        observation_due = self._observation_refresh_due(force=force)
        ranked_observation = None

        if observation_due:
            original_execution = self.symbols
            try:
                # The observation builder must include the prospective
                # execution universe, not only the previous one.
                self.symbols = sorted(new_execution)
                ranked_observation = (
                    self._build_observation_universe()
                )
                # _build_observation_universe may replace prospective execution
                # symbols that fail observation eligibility. Preserve that
                # reconciled result before restoring the current universe.
                new_execution = list(self.symbols)
            except Exception as e:
                observation_build_failed = True
                self._last_reload_status = "FAILED_OBSERVATION_BUILD"
                self.system_log.error(
                    "OBSERVATION_UNIVERSE_BUILD_FAILED | "
                    f"error={e}"
                )
            finally:
                self.symbols = original_execution

        if ranked_observation is None:
            ranked_observation = list(
                self.observation_symbols
            )

        # Prospective execution symbols are mandatory even when the broad
        # observation refresh was skipped or failed.
        ranked_observation = sorted(
            set(ranked_observation) | set(new_execution)
        )

        effective_observation, retained = (
            self._build_effective_observation_universe(
                ranked_observation
            )
        )

        execution_changed = new_execution != self.symbols
        observation_changed = (
            effective_observation != self.observation_symbols
        )

        if not execution_changed and not observation_changed:
            if observation_due:
                self._last_observation_refresh_monotonic = (
                    time.monotonic()
                )
                if not observation_build_failed:
                    self._ranked_observation_symbols = list(
                        ranked_observation
                    )
            if not observation_build_failed:
                self._last_reload_status = "NO_CHANGE"
            getattr(self.system_log, "debug", lambda *_args, **_kwargs: None)("UNIVERSE_RELOAD_NO_CHANGE")
            return

        old_execution = set(self.symbols)
        new_execution_set = set(new_execution)
        execution_added = new_execution_set - old_execution
        execution_removed = old_execution - new_execution_set

        old_observation = set(self.observation_symbols)
        new_observation_set = set(effective_observation)
        observation_added = new_observation_set - old_observation
        observation_removed = old_observation - new_observation_set

        # Warm only symbols that are genuinely new to the candle universe.
        if observation_added:
            self._warm_symbols(
                sorted(observation_added),
                exchange,
            )

        self.symbols = sorted(new_execution)
        self.observation_symbols = sorted(effective_observation)
        now_iso = datetime.now(timezone.utc).isoformat()
        self.generated_at = now_iso

        if execution_changed:
            self._persist_snapshot(self.symbols)

        if observation_due:
            self.observation_generated_at = now_iso
            self._persist_observation_snapshot(
                sorted(ranked_observation)
            )
            self._last_observation_refresh_monotonic = (
                time.monotonic()
            )
            if not observation_build_failed:
                self._ranked_observation_symbols = list(
                    ranked_observation
                )

        self.strategy.set_universes(
            execution_symbols=self.symbols,
            observation_symbols=self.observation_symbols,
        )

        if not observation_build_failed:
            self._last_reload_status = "SUCCESS"

        self.system_log.info(
            "DUAL_UNIVERSE_RELOADED | "
            f"execution_count={len(self.symbols)} | "
            f"execution_added={len(execution_added)} | "
            f"execution_removed={len(execution_removed)} | "
            f"observation_ranked={len(ranked_observation)} | "
            f"observation_effective={len(self.observation_symbols)} | "
            f"observation_added={len(observation_added)} | "
            f"observation_removed={len(observation_removed)} | "
            f"retained={len(retained)} | "
            f"refresh_due={str(observation_due).lower()} | "
            f"execution_selector="
            f"{self._execution_selection_metadata.get('mode', 'UNKNOWN')}"
        )

    def scale_composition_snapshot(self):
        """Return read-only ranked/effective/retention composition telemetry."""
        try:
            retained = set(
                self.strategy.get_retained_observation_symbols()
            )
            ranked = set(
                self._ranked_observation_symbols
                or self.observation_symbols
            )
            effective = set(self.observation_symbols)
            return {
                "ranked_universe_count": len(ranked),
                "effective_universe_count": len(effective),
                "retained_symbol_count": len(retained),
                "retained_extra_count": len(effective - ranked),
                "execution_symbol_count": len(self.symbols),
                "last_reload_status": self._last_reload_status,
            }
        except Exception:
            return {}
