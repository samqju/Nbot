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

UNIVERSE_SNAPSHOT_FILE = "universe_snapshot.json"
EXPECTED_UNIVERSE_SIZE = 30


class UniverseManager:

    def __init__(self, strategy, system_log):
        self.strategy = strategy
        self.system_log = system_log

        self.symbols = []
        self.generated_at = None

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
            f"UNIVERSE_LOADED | count={len(symbols)}"
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
