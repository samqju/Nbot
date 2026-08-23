"""Deterministic future-path research outcomes for NBOT V3.4.3.

This is the first intentionally future-looking research layer.  It labels only
persisted canonical feature events after the full frozen 4-hour horizon has
matured.  Future candles may come from canonical V3.3 evidence or from a
strictly label-only historical-kline cache.  Feature and signal code never
imports or queries this module/cache, preserving the decision-time lookahead
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import time
from typing import Any, Iterable

from .database import EvidenceDatabase
from .features import (
    CANONICAL_FEATURE_FIELDS,
    CANONICAL_FEATURE_VERSION,
    CanonicalFeatureStore,
)
from .models import Candle
from .public_market import PublicMarketClient


OUTCOME_VERSION = "FUTURE_PATH_4H_V1"
RISK_UNIT_VERSION = "ATR14_1X_RESEARCH_R_V1"
COST_VERSION = "TAKER_SPREAD_SLIPPAGE_FUNDING_PROXY_V1"

HORIZON_LABELS: tuple[tuple[str, int], ...] = (
    ("5m", 1),
    ("15m", 3),
    ("30m", 6),
    ("1h", 12),
    ("2h", 24),
    ("4h", 48),
)

PATH_COLUMNS = (
    "event_open_ms",
    "symbol",
    "feature_version",
    "outcome_version",
    "built_at_ms",
    "entry_price",
    "source_min_event_open_ms",
    "source_max_event_open_ms",
    "future_candle_count",
    "fallback_candle_count",
    "source_candle_digest",
    "fwd_ret_5m",
    "fwd_ret_15m",
    "fwd_ret_30m",
    "fwd_ret_1h",
    "fwd_ret_2h",
    "fwd_ret_4h",
    "long_mfe_frac",
    "long_mae_frac",
    "short_mfe_frac",
    "short_mae_frac",
    "time_to_long_mfe_min",
    "time_to_long_mae_min",
    "time_to_short_mfe_min",
    "time_to_short_mae_min",
    "future_realized_vol_4h",
    "risk_unit_version",
    "risk_unit_frac",
    "barrier_hits_json",
    "continuation_json",
    "funding_complete",
    "funding_event_count",
    "funding_rate_sum",
    "funding_events_json",
    "funding_source_digest",
    "cost_version",
    "roundtrip_base_cost_frac",
    "net_long_5m",
    "net_long_15m",
    "net_long_30m",
    "net_long_1h",
    "net_long_2h",
    "net_long_4h",
    "net_short_5m",
    "net_short_15m",
    "net_short_30m",
    "net_short_1h",
    "net_short_2h",
    "net_short_4h",
    "path_digest",
)

PATH_DIGEST_FIELDS = tuple(
    field for field in PATH_COLUMNS if field not in {"built_at_ms", "path_digest"}
)

FUTURE_PATH_TABLES = (
    "future_path_sets",
    "future_candle_cache",
    "future_paths",
    "future_path_builds",
    "future_path_attempts",
)

FUTURE_PATH_SCHEMA = """
CREATE TABLE IF NOT EXISTS future_path_sets (
    outcome_version TEXT PRIMARY KEY,
    feature_version TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE TABLE IF NOT EXISTS future_candle_cache (
    symbol TEXT NOT NULL,
    event_open_ms INTEGER NOT NULL,
    open_time_ms INTEGER NOT NULL,
    close_time_ms INTEGER NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    base_volume REAL NOT NULL,
    quote_volume REAL NOT NULL,
    trade_count INTEGER NOT NULL,
    taker_buy_base_volume REAL NOT NULL,
    taker_buy_quote_volume REAL NOT NULL,
    source TEXT NOT NULL CHECK (source='BINANCE_HISTORICAL_KLINE'),
    ingested_at_ms INTEGER NOT NULL,
    PRIMARY KEY (symbol, event_open_ms)
);

CREATE TABLE IF NOT EXISTS future_paths (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    outcome_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    source_min_event_open_ms INTEGER NOT NULL,
    source_max_event_open_ms INTEGER NOT NULL,
    future_candle_count INTEGER NOT NULL,
    fallback_candle_count INTEGER NOT NULL,
    source_candle_digest TEXT NOT NULL,
    fwd_ret_5m REAL NOT NULL,
    fwd_ret_15m REAL NOT NULL,
    fwd_ret_30m REAL NOT NULL,
    fwd_ret_1h REAL NOT NULL,
    fwd_ret_2h REAL NOT NULL,
    fwd_ret_4h REAL NOT NULL,
    long_mfe_frac REAL NOT NULL,
    long_mae_frac REAL NOT NULL,
    short_mfe_frac REAL NOT NULL,
    short_mae_frac REAL NOT NULL,
    time_to_long_mfe_min INTEGER NOT NULL,
    time_to_long_mae_min INTEGER NOT NULL,
    time_to_short_mfe_min INTEGER NOT NULL,
    time_to_short_mae_min INTEGER NOT NULL,
    future_realized_vol_4h REAL NOT NULL,
    risk_unit_version TEXT NOT NULL,
    risk_unit_frac REAL,
    barrier_hits_json TEXT NOT NULL,
    continuation_json TEXT NOT NULL,
    funding_complete INTEGER NOT NULL CHECK (funding_complete IN (0,1)),
    funding_event_count INTEGER NOT NULL,
    funding_rate_sum REAL NOT NULL,
    funding_events_json TEXT NOT NULL,
    funding_source_digest TEXT NOT NULL,
    cost_version TEXT NOT NULL,
    roundtrip_base_cost_frac REAL NOT NULL,
    net_long_5m REAL NOT NULL,
    net_long_15m REAL NOT NULL,
    net_long_30m REAL NOT NULL,
    net_long_1h REAL NOT NULL,
    net_long_2h REAL NOT NULL,
    net_long_4h REAL NOT NULL,
    net_short_5m REAL NOT NULL,
    net_short_15m REAL NOT NULL,
    net_short_30m REAL NOT NULL,
    net_short_1h REAL NOT NULL,
    net_short_2h REAL NOT NULL,
    net_short_4h REAL NOT NULL,
    path_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, outcome_version),
    FOREIGN KEY (event_open_ms, symbol, feature_version)
        REFERENCES canonical_features(event_open_ms, symbol, feature_version) ON DELETE CASCADE,
    FOREIGN KEY (outcome_version) REFERENCES future_path_sets(outcome_version)
);

CREATE TABLE IF NOT EXISTS future_path_builds (
    event_open_ms INTEGER NOT NULL,
    outcome_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    path_row_count INTEGER NOT NULL CHECK (path_row_count >= 0),
    path_digest TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    fallback_candle_count INTEGER NOT NULL CHECK (fallback_candle_count >= 0),
    PRIMARY KEY (event_open_ms, outcome_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (outcome_version) REFERENCES future_path_sets(outcome_version)
);

CREATE TABLE IF NOT EXISTS future_path_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_open_ms INTEGER NOT NULL,
    attempted_at_ms INTEGER NOT NULL,
    outcome_version TEXT NOT NULL,
    result TEXT NOT NULL,
    expected_symbols INTEGER NOT NULL CHECK (expected_symbols >= 0),
    completed_symbols INTEGER NOT NULL CHECK (completed_symbols >= 0),
    missing_candles INTEGER NOT NULL CHECK (missing_candles >= 0),
    detail TEXT,
    FOREIGN KEY (outcome_version) REFERENCES future_path_sets(outcome_version)
);

CREATE INDEX IF NOT EXISTS idx_future_candle_cache_symbol_time
    ON future_candle_cache(symbol, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_future_paths_symbol_time
    ON future_paths(symbol, event_open_ms, outcome_version);
CREATE INDEX IF NOT EXISTS idx_future_path_attempts_event_time
    ON future_path_attempts(event_open_ms, attempted_at_ms);
"""


class FuturePathError(RuntimeError):
    """Future-path definition, source lineage, or persistence is inconsistent."""


@dataclass(frozen=True)
class FuturePathConfig:
    """Frozen V3.4.3 V2-equivalent future-path semantics."""

    outcome_version: str = OUTCOME_VERSION
    feature_version: str = CANONICAL_FEATURE_VERSION
    forward_horizon_bars: tuple[int, ...] = (1, 3, 6, 12, 24, 48)
    max_horizon_bars: int = 48
    risk_unit_version: str = RISK_UNIT_VERSION
    barrier_r_multiples: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0)
    cost_version: str = COST_VERSION
    taker_fee_rate: float = 0.0005
    entry_slippage_bps: float = 2.0
    exit_slippage_bps: float = 2.0

    def validate(self) -> None:
        if self.outcome_version != OUTCOME_VERSION:
            raise ValueError("NBOT_V343_OUTCOME_VERSION_IMMUTABLE")
        if self.feature_version != CANONICAL_FEATURE_VERSION:
            raise ValueError("NBOT_V343_FEATURE_VERSION_IMMUTABLE")
        if self.forward_horizon_bars != (1, 3, 6, 12, 24, 48):
            raise ValueError("NBOT_V343_FORWARD_HORIZONS_IMMUTABLE")
        if self.max_horizon_bars != 48:
            raise ValueError("NBOT_V343_MAX_HORIZON_IMMUTABLE")
        if self.risk_unit_version != RISK_UNIT_VERSION:
            raise ValueError("NBOT_V343_RISK_UNIT_IMMUTABLE")
        if self.barrier_r_multiples != (0.5, 1.0, 2.0, 3.0):
            raise ValueError("NBOT_V343_BARRIERS_IMMUTABLE")
        if self.cost_version != COST_VERSION:
            raise ValueError("NBOT_V343_COST_VERSION_IMMUTABLE")
        if (self.taker_fee_rate, self.entry_slippage_bps, self.exit_slippage_bps) != (
            0.0005,
            2.0,
            2.0,
        ):
            raise ValueError("NBOT_V343_COST_ASSUMPTIONS_IMMUTABLE")


@dataclass(frozen=True)
class FuturePathBuildResult:
    outcome_version: str
    feature_events: int
    mature_events: int
    pending_maturity_events: int
    pending_build_events: int
    attempted_events: int
    built_events: int
    path_rows: int
    fallback_candles_fetched: int
    funding_incomplete_events: int
    path_incomplete_events: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _definition_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _rows_digest(rows: Iterable[dict[str, Any]], fields: tuple[str, ...]) -> str:
    payload = [
        [row.get(field) for field in fields]
        for row in sorted(
            rows,
            key=lambda item: (int(item["event_open_ms"]), str(item["symbol"])),
        )
    ]
    return _definition_hash(payload)


def _candle_payload(candle: Candle) -> list[Any]:
    return [
        candle.open_time_ms,
        candle.close_time_ms,
        candle.open_price,
        candle.high_price,
        candle.low_price,
        candle.close_price,
        candle.base_volume,
        candle.quote_volume,
        candle.trade_count,
        candle.taker_buy_base_volume,
        candle.taker_buy_quote_volume,
    ]


def _candle_source_digest(path: list[Candle]) -> str:
    return _definition_hash([_candle_payload(candle) for candle in path])


def _future_realized_vol(entry_price: float, closes: list[float]) -> float:
    values = [entry_price, *closes]
    returns = [
        math.log(values[index] / values[index - 1])
        for index in range(1, len(values))
    ]
    return math.sqrt(sum(value * value for value in returns))


def _barrier_hits(
    *,
    entry_price: float,
    risk_unit_frac: float | None,
    path: list[Candle],
    barriers: tuple[float, ...],
    interval_minutes: int,
) -> dict[str, Any]:
    if risk_unit_frac is None or risk_unit_frac <= 0:
        return {
            "available": False,
            "reason": "ATR14_RISK_UNIT_UNAVAILABLE",
            "risk_unit_frac": None,
            "sides": {},
        }

    result: dict[str, Any] = {
        "available": True,
        "reason": "OK",
        "risk_unit_frac": risk_unit_frac,
        "sides": {},
    }
    for side in ("LONG", "SHORT"):
        side_rows: dict[str, Any] = {}
        for multiple in barriers:
            distance = risk_unit_frac * multiple
            if side == "LONG":
                favorable_price = entry_price * (1.0 + distance)
                adverse_price = entry_price * (1.0 - distance)
            else:
                favorable_price = entry_price * (1.0 - distance)
                adverse_price = entry_price * (1.0 + distance)

            favorable_bar = None
            adverse_bar = None
            for bar_index, candle in enumerate(path, start=1):
                favorable_hit = (
                    candle.high_price >= favorable_price
                    if side == "LONG"
                    else candle.low_price <= favorable_price
                )
                adverse_hit = (
                    candle.low_price <= adverse_price
                    if side == "LONG"
                    else candle.high_price >= adverse_price
                )
                if favorable_bar is None and favorable_hit:
                    favorable_bar = bar_index
                if adverse_bar is None and adverse_hit:
                    adverse_bar = bar_index
                if favorable_bar is not None and adverse_bar is not None:
                    break

            if favorable_bar is None and adverse_bar is None:
                first = "NONE"
            elif adverse_bar is None or (
                favorable_bar is not None and favorable_bar < adverse_bar
            ):
                first = "FAVORABLE_FIRST"
            elif favorable_bar is None or adverse_bar < favorable_bar:
                first = "ADVERSE_FIRST"
            else:
                first = "AMBIGUOUS_SAME_CANDLE"

            side_rows[f"{multiple:g}R"] = {
                "first": first,
                "favorable_bar": favorable_bar,
                "adverse_bar": adverse_bar,
                "favorable_minute": (
                    None if favorable_bar is None else favorable_bar * interval_minutes
                ),
                "adverse_minute": (
                    None if adverse_bar is None else adverse_bar * interval_minutes
                ),
            }
        result["sides"][side] = side_rows
    return result


def _continuation(
    path: list[Candle],
    horizons: tuple[tuple[str, int], ...],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for label, bars in horizons:
        exit_price = path[bars - 1].close_price
        remaining = path[bars:]
        if not remaining:
            long_extension = 0.0
            short_extension = 0.0
        else:
            max_high = max(row.high_price for row in remaining)
            min_low = min(row.low_price for row in remaining)
            long_extension = max(0.0, max_high / exit_price - 1.0)
            short_extension = max(0.0, 1.0 - min_low / exit_price)
        result[label] = {
            "exit_close": exit_price,
            "long_max_favorable_continuation_frac": long_extension,
            "short_max_favorable_continuation_frac": short_extension,
        }
    return result


def _latest_closed_open_ms(server_time_ms: int, interval_ms: int) -> int:
    if server_time_ms < interval_ms:
        return -1
    return (int(server_time_ms) // interval_ms) * interval_ms - interval_ms


class FuturePathStore:
    """Build and audit V3.4.3 future-path labels without recommendation authority."""

    def __init__(
        self,
        db: EvidenceDatabase,
        client: PublicMarketClient,
        config: FuturePathConfig | None = None,
    ) -> None:
        self.db = db
        self.client = client
        self.config = config or FuturePathConfig()
        self.config.validate()
        self.feature_store = CanonicalFeatureStore(db)
        self.interval_ms = db.config.candle_interval_ms
        self.interval_minutes = self.interval_ms // 60_000

    def definition(self) -> dict[str, Any]:
        return {
            "outcome_version": self.config.outcome_version,
            "feature_version": self.config.feature_version,
            "entry_reference": "DECISION_EVENT_CLOSE_PRICE",
            "future_horizons_bars": list(self.config.forward_horizon_bars),
            "future_horizons_labels": [label for label, _bars in HORIZON_LABELS],
            "path_window": "NEXT_48_COMPLETED_5M_CANDLES",
            "mfe_mae": "HIGH_LOW_PATH_BOTH_LONG_AND_SHORT",
            "risk_unit_version": self.config.risk_unit_version,
            "risk_unit": "DECISION_TIME_ATR14_FRACTION_1X_WHEN_AVAILABLE",
            "barrier_r_multiples": list(self.config.barrier_r_multiples),
            "same_candle_barrier_rule": "AMBIGUOUS_SAME_CANDLE",
            "continuation": "MAX_FAVORABLE_EXTENSION_AFTER_EACH_FROZEN_HORIZON_TO_4H",
            "funding": "EXACT_TIMESTAMPED_FUNDING_EVENTS_CROSSED_FROM_SYNCED_HISTORY",
            "cost_version": self.config.cost_version,
            "cost_formula": {
                "taker_fee_rate_each_side": self.config.taker_fee_rate,
                "entry_slippage_bps": self.config.entry_slippage_bps,
                "exit_slippage_bps": self.config.exit_slippage_bps,
                "roundtrip_base": (
                    "2*taker_fee + entry_slippage + exit_slippage + "
                    "decision_time_spread"
                ),
                "long_net": "gross_long - roundtrip_base - funding_rate_sum_crossed",
                "short_net": "gross_short - roundtrip_base + funding_rate_sum_crossed",
                "exit_spread": "DECISION_TIME_SPREAD_PROXY_NOT_HISTORICAL_EXIT_BOOK",
            },
            "future_candle_sources": [
                "CANONICAL_CANDLES_5M",
                "BINANCE_HISTORICAL_KLINE_LABEL_CACHE",
            ],
            "source_digest": (
                "CANONICAL_FEATURE_EVENT + EXACT_FUTURE_CANDLE_VALUES_AND_ORIGINS + "
                "CANONICALIZED_FUNDING_COVERAGE_AND_EVENTS"
            ),
            "lookahead_boundary": (
                "FUTURE_PATH_TABLES_ARE_LABEL_ONLY_AND_NEVER_QUERIED_BY_V3_4_1_FEATURES_"
                "OR_V3_4_2_SIGNALS"
            ),
        }

    @property
    def definition_hash(self) -> str:
        return _definition_hash(self.definition())

    def initialize(self) -> None:
        """Create derived-only outcome tables and register the immutable definition."""

        self.feature_store.initialize()
        definition_json = _canonical_json(self.definition())
        definition_hash = _definition_hash(self.definition())
        now_ms = int(time.time() * 1000)
        with self.db.connection() as conn:
            conn.executescript(FUTURE_PATH_SCHEMA)
            conn.execute(
                """
                INSERT OR IGNORE INTO future_path_sets(
                    outcome_version, feature_version, definition_hash,
                    definition_json, registered_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.config.outcome_version,
                    self.config.feature_version,
                    definition_hash,
                    definition_json,
                    now_ms,
                ),
            )
            stored = conn.execute(
                """
                SELECT feature_version, definition_hash, definition_json
                FROM future_path_sets WHERE outcome_version=?
                """,
                (self.config.outcome_version,),
            ).fetchone()
            expected = (
                self.config.feature_version,
                definition_hash,
                definition_json,
            )
            if stored != expected:
                raise FuturePathError(
                    "NBOT_V343_OUTCOME_DEFINITION_HASH_MISMATCH:"
                    f"{self.config.outcome_version}"
                )

    def _feature_event_digest(self, conn, event_open_ms: int) -> str:
        fields = tuple(
            field for field in CANONICAL_FEATURE_FIELDS if field != "computed_at_ms"
        )
        rows = conn.execute(
            f"""
            SELECT {','.join(fields)}
            FROM canonical_features
            WHERE event_open_ms=? AND feature_version=?
            ORDER BY symbol
            """,
            (event_open_ms, self.config.feature_version),
        ).fetchall()
        payload = [list(row) for row in rows]
        return _definition_hash(payload)

    @staticmethod
    def _parse_candle(symbol: str, row: tuple[Any, ...]) -> Candle:
        return Candle(
            symbol=symbol,
            open_time_ms=int(row[1]),
            close_time_ms=int(row[2]),
            open_price=float(row[3]),
            high_price=float(row[4]),
            low_price=float(row[5]),
            close_price=float(row[6]),
            base_volume=float(row[7]),
            quote_volume=float(row[8]),
            trade_count=int(row[9]),
            taker_buy_base_volume=float(row[10]),
            taker_buy_quote_volume=float(row[11]),
        )

    def _load_path_candles(
        self,
        conn,
        symbol: str,
        event_open_ms: int,
    ) -> tuple[dict[int, Candle], set[int]]:
        start_open = event_open_ms + self.interval_ms
        end_open = event_open_ms + self.config.max_horizon_bars * self.interval_ms
        canonical_rows = conn.execute(
            """
            SELECT event_open_ms, open_time_ms, close_time_ms, open_price, high_price,
                   low_price, close_price, base_volume, quote_volume, trade_count,
                   taker_buy_base_volume, taker_buy_quote_volume
            FROM candles_5m
            WHERE symbol=? AND event_open_ms BETWEEN ? AND ?
            ORDER BY event_open_ms
            """,
            (symbol, start_open, end_open),
        ).fetchall()
        cached_rows = conn.execute(
            """
            SELECT event_open_ms, open_time_ms, close_time_ms, open_price, high_price,
                   low_price, close_price, base_volume, quote_volume, trade_count,
                   taker_buy_base_volume, taker_buy_quote_volume
            FROM future_candle_cache
            WHERE symbol=? AND event_open_ms BETWEEN ? AND ?
            ORDER BY event_open_ms
            """,
            (symbol, start_open, end_open),
        ).fetchall()

        result: dict[int, Candle] = {}
        fallback_opens: set[int] = set()
        for row in cached_rows:
            key = int(row[0])
            result[key] = self._parse_candle(symbol, row)
            fallback_opens.add(key)
        for row in canonical_rows:
            key = int(row[0])
            result[key] = self._parse_candle(symbol, row)
            fallback_opens.discard(key)
        return result, fallback_opens

    def _load_path_candles_bulk(
        self,
        conn,
        symbols: list[str],
        event_open_ms: int,
    ) -> dict[str, tuple[dict[int, Candle], set[int]]]:
        """Load one event's future candles for all symbols in two queries.

        Canonical raw candles retain precedence over fallback cache exactly as
        the single-symbol loader does.  V3.8.4 uses this on the hot path to
        avoid O(events * symbols) SQLite round trips.
        """
        ordered = tuple(sorted({str(symbol) for symbol in symbols}))
        if not ordered:
            return {}
        start_open = event_open_ms + self.interval_ms
        end_open = event_open_ms + self.config.max_horizon_bars * self.interval_ms
        placeholders = ",".join("?" for _ in ordered)
        cols = (
            "symbol,event_open_ms,open_time_ms,close_time_ms,open_price,"
            "high_price,low_price,close_price,base_volume,quote_volume,"
            "trade_count,taker_buy_base_volume,taker_buy_quote_volume"
        )
        params = (*ordered, start_open, end_open)
        canonical_rows = conn.execute(
            f"SELECT {cols} FROM candles_5m WHERE symbol IN ({placeholders}) "
            "AND event_open_ms BETWEEN ? AND ? ORDER BY symbol,event_open_ms",
            params,
        ).fetchall()
        cached_rows = conn.execute(
            f"SELECT {cols} FROM future_candle_cache WHERE symbol IN ({placeholders}) "
            "AND event_open_ms BETWEEN ? AND ? ORDER BY symbol,event_open_ms",
            params,
        ).fetchall()
        result: dict[str, tuple[dict[int, Candle], set[int]]] = {
            symbol: ({}, set()) for symbol in ordered
        }
        for row in cached_rows:
            symbol = str(row[0])
            path_map, fallback = result[symbol]
            key = int(row[1])
            path_map[key] = self._parse_candle(symbol, tuple(row[1:]))
            fallback.add(key)
        for row in canonical_rows:
            symbol = str(row[0])
            path_map, fallback = result[symbol]
            key = int(row[1])
            path_map[key] = self._parse_candle(symbol, tuple(row[1:]))
            fallback.discard(key)
        return result

    def _load_funding_bulk(
        self,
        conn,
        symbols: list[str],
        start_exclusive_ms: int,
        end_inclusive_ms: int,
    ) -> dict[str, list[tuple[int, float, float | None]]]:
        ordered = tuple(sorted({str(symbol) for symbol in symbols}))
        if not ordered:
            return {}
        placeholders = ",".join("?" for _ in ordered)
        rows = conn.execute(
            "SELECT symbol,funding_time_ms,funding_rate,mark_price "
            f"FROM funding_events WHERE symbol IN ({placeholders}) "
            "AND funding_time_ms>? AND funding_time_ms<=? "
            "ORDER BY symbol,funding_time_ms",
            (*ordered, int(start_exclusive_ms), int(end_inclusive_ms)),
        ).fetchall()
        grouped: dict[str, list[tuple[int, float, float | None]]] = {
            symbol: [] for symbol in ordered
        }
        for symbol, ts, rate, mark in rows:
            grouped[str(symbol)].append((
                int(ts), float(rate), None if mark is None else float(mark),
            ))
        return grouped

    @staticmethod
    def _same_candle(left: Candle, right: Candle) -> bool:
        return _candle_payload(left) == _candle_payload(right)

    def _cache_missing_candles(
        self,
        missing_by_symbol: dict[str, list[int]],
    ) -> tuple[int, dict[str, str]]:
        if not missing_by_symbol:
            return 0, {}

        groups: dict[tuple[int, ...], list[str]] = {}
        for symbol, opens in missing_by_symbol.items():
            groups.setdefault(tuple(sorted(opens)), []).append(symbol)

        fetched: dict[str, dict[int, Candle]] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(
            max_workers=min(self.db.config.candle_fetch_workers, max(1, len(groups)))
        ) as pool:
            futures = {
                pool.submit(
                    self.client.historical_candles_for_symbols,
                    tuple(sorted(symbols)),
                    opens,
                ): (tuple(sorted(symbols)), opens)
                for opens, symbols in groups.items()
            }
            for future in as_completed(futures):
                symbols, opens = futures[future]
                try:
                    rows_by_symbol, fetch_errors = future.result()
                except Exception as exc:
                    detail = f"{type(exc).__name__}: {exc}"
                    for symbol in symbols:
                        errors[symbol] = detail
                    continue
                for symbol, detail in fetch_errors.items():
                    errors[str(symbol)] = str(detail)
                required = set(opens)
                for symbol in symbols:
                    if symbol in errors:
                        continue
                    rows = rows_by_symbol.get(symbol)
                    if rows is None or required.difference(rows):
                        errors[symbol] = (
                            "NBOT_V343_HISTORICAL_CANDLES_MISSING:"
                            f"{len(required.difference(rows or {}))}"
                        )
                        continue
                    fetched[symbol] = {open_ms: rows[open_ms] for open_ms in opens}

        if errors:
            return 0, errors

        ingested_at_ms = int(time.time() * 1000)
        inserted = 0
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for symbol in sorted(fetched):
                for open_ms, candle in sorted(fetched[symbol].items()):
                    if candle.symbol != symbol or candle.open_time_ms != open_ms:
                        raise FuturePathError(
                            f"NBOT_V343_FALLBACK_CANDLE_IDENTITY_INVALID:{symbol}:{open_ms}"
                        )

                    canonical = conn.execute(
                        """
                        SELECT event_open_ms, open_time_ms, close_time_ms, open_price,
                               high_price, low_price, close_price, base_volume,
                               quote_volume, trade_count, taker_buy_base_volume,
                               taker_buy_quote_volume
                        FROM candles_5m
                        WHERE symbol=? AND event_open_ms=?
                        """,
                        (symbol, open_ms),
                    ).fetchone()
                    if canonical is not None:
                        raw_candle = self._parse_candle(symbol, canonical)
                        if not self._same_candle(raw_candle, candle):
                            raise FuturePathError(
                                f"NBOT_V343_FALLBACK_CONFLICTS_RAW:{symbol}:{open_ms}"
                            )
                        continue

                    existing = conn.execute(
                        """
                        SELECT event_open_ms, open_time_ms, close_time_ms, open_price,
                               high_price, low_price, close_price, base_volume,
                               quote_volume, trade_count, taker_buy_base_volume,
                               taker_buy_quote_volume
                        FROM future_candle_cache
                        WHERE symbol=? AND event_open_ms=?
                        """,
                        (symbol, open_ms),
                    ).fetchone()
                    if existing is not None:
                        cached = self._parse_candle(symbol, existing)
                        if not self._same_candle(cached, candle):
                            raise FuturePathError(
                                f"NBOT_V343_FALLBACK_CACHE_CONFLICT:{symbol}:{open_ms}"
                            )
                        continue

                    conn.execute(
                        """
                        INSERT INTO future_candle_cache(
                            symbol, event_open_ms, open_time_ms, close_time_ms,
                            open_price, high_price, low_price, close_price,
                            base_volume, quote_volume, trade_count,
                            taker_buy_base_volume, taker_buy_quote_volume,
                            source, ingested_at_ms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                  'BINANCE_HISTORICAL_KLINE', ?)
                        """,
                        (
                            symbol,
                            open_ms,
                            candle.open_time_ms,
                            candle.close_time_ms,
                            candle.open_price,
                            candle.high_price,
                            candle.low_price,
                            candle.close_price,
                            candle.base_volume,
                            candle.quote_volume,
                            candle.trade_count,
                            candle.taker_buy_base_volume,
                            candle.taker_buy_quote_volume,
                            ingested_at_ms,
                        ),
                    )
                    inserted += 1
        return inserted, {}

    @staticmethod
    def _canonical_coverage_segments(conn, start_ms: int, end_ms: int) -> list[list[int]]:
        ranges = conn.execute(
            """
            SELECT start_ms, end_ms
            FROM funding_sync_ranges
            WHERE end_ms>=? AND start_ms<=?
            ORDER BY start_ms, end_ms
            """,
            (start_ms, end_ms),
        ).fetchall()
        merged: list[list[int]] = []
        for raw_start, raw_end in ranges:
            left = max(start_ms, int(raw_start))
            right = min(end_ms, int(raw_end))
            if right < left:
                continue
            if not merged or left > merged[-1][1] + 1:
                merged.append([left, right])
            else:
                merged[-1][1] = max(merged[-1][1], right)
        return merged

    def _event_source_digest(self, event_open_ms: int) -> str:
        start_open = event_open_ms + self.interval_ms
        end_open = event_open_ms + self.config.max_horizon_bars * self.interval_ms
        end_close = end_open + self.interval_ms - 1
        with self.db.connection() as conn:
            event = conn.execute(
                "SELECT event_close_ms FROM market_events WHERE event_open_ms=?",
                (event_open_ms,),
            ).fetchone()
            if event is None:
                raise FuturePathError(
                    f"NBOT_V343_TARGET_EVENT_MISSING:{event_open_ms}"
                )
            event_close_ms = int(event[0])
            feature_digest = self._feature_event_digest(conn, event_open_ms)
            symbols = [
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT symbol FROM canonical_features
                    WHERE event_open_ms=? AND feature_version=?
                    ORDER BY symbol
                    """,
                    (event_open_ms, self.config.feature_version),
                )
            ]
            coverage = self._canonical_coverage_segments(
                conn,
                event_close_ms + 1,
                end_close,
            )
            source_rows: list[list[Any]] = []
            for symbol in symbols:
                path_map, fallback_opens = self._load_path_candles(
                    conn,
                    symbol,
                    event_open_ms,
                )
                opens = [
                    event_open_ms + offset * self.interval_ms
                    for offset in range(1, self.config.max_horizon_bars + 1)
                ]
                if any(open_ms not in path_map for open_ms in opens):
                    raise FuturePathError(
                        f"NBOT_V343_SOURCE_PATH_INCOMPLETE:{event_open_ms}:{symbol}"
                    )
                path = [path_map[open_ms] for open_ms in opens]
                funding = conn.execute(
                    """
                    SELECT funding_time_ms, funding_rate, mark_price
                    FROM funding_events
                    WHERE symbol=? AND funding_time_ms>? AND funding_time_ms<=?
                    ORDER BY funding_time_ms
                    """,
                    (symbol, event_close_ms, end_close),
                ).fetchall()
                source_rows.append(
                    [
                        symbol,
                        _candle_source_digest(path),
                        sorted(fallback_opens),
                        [
                            [int(ts), float(rate), None if mark is None else float(mark)]
                            for ts, rate, mark in funding
                        ],
                    ]
                )

        return _definition_hash(
            {
                "feature_digest": feature_digest,
                "future_sources": source_rows,
                "funding_coverage": coverage,
            }
        )

    def _record_attempt(
        self,
        *,
        event_open_ms: int,
        result: str,
        expected_symbols: int,
        completed_symbols: int,
        missing_candles: int,
        detail: str | None,
    ) -> None:
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO future_path_attempts(
                    event_open_ms, attempted_at_ms, outcome_version, result,
                    expected_symbols, completed_symbols, missing_candles, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_open_ms,
                    int(time.time() * 1000),
                    self.config.outcome_version,
                    result,
                    expected_symbols,
                    completed_symbols,
                    missing_candles,
                    detail,
                ),
            )

    def _event_counts(
        self,
        conn,
        latest_closed_open_ms: int,
    ) -> tuple[int, int, int]:
        feature_events = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM feature_builds
                WHERE feature_version=?
                """,
                (self.config.feature_version,),
            ).fetchone()[0]
        )
        maturity_cutoff = (
            latest_closed_open_ms
            - self.config.max_horizon_bars * self.interval_ms
        )
        mature_events = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM feature_builds
                WHERE feature_version=? AND event_open_ms<=?
                """,
                (self.config.feature_version, maturity_cutoff),
            ).fetchone()[0]
        )
        pending_build = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM feature_builds f
                WHERE f.feature_version=? AND f.event_open_ms<=?
                  AND NOT EXISTS (
                      SELECT 1 FROM future_path_builds b
                      WHERE b.event_open_ms=f.event_open_ms
                        AND b.outcome_version=?
                  )
                """,
                (
                    self.config.feature_version,
                    maturity_cutoff,
                    self.config.outcome_version,
                ),
            ).fetchone()[0]
        )
        return feature_events, mature_events, pending_build

    def _eligible_events(
        self,
        conn,
        latest_closed_open_ms: int,
        max_events: int,
        rebuild: bool,
    ) -> list[int]:
        maturity_cutoff = (
            latest_closed_open_ms
            - self.config.max_horizon_bars * self.interval_ms
        )
        sql = """
            SELECT event_open_ms
            FROM feature_builds f
            WHERE f.feature_version=? AND f.event_open_ms<=?
        """
        params: list[Any] = [self.config.feature_version, maturity_cutoff]
        if not rebuild:
            sql += """
                AND NOT EXISTS (
                    SELECT 1 FROM future_path_builds b
                    WHERE b.event_open_ms=f.event_open_ms
                      AND b.outcome_version=?
                )
            """
            params.append(self.config.outcome_version)
        sql += " ORDER BY event_open_ms"
        if max_events > 0:
            sql += " LIMIT ?"
            params.append(max_events)
        return [int(row[0]) for row in conn.execute(sql, params).fetchall()]

    def _load_features(self, conn, event_open_ms: int) -> list[tuple[Any, ...]]:
        return conn.execute(
            """
            SELECT symbol, close_price, atr14_frac, spread_pct
            FROM canonical_features
            WHERE event_open_ms=? AND feature_version=?
            ORDER BY symbol
            """,
            (event_open_ms, self.config.feature_version),
        ).fetchall()

    def _build_row(
        self,
        *,
        event_open_ms: int,
        symbol: str,
        entry_price: float,
        risk_unit_frac: float | None,
        spread_pct: float,
        path: list[Candle],
        fallback_opens: set[int],
        funding_events: list[tuple[int, float, float | None]],
        built_at_ms: int,
    ) -> dict[str, Any]:
        closes = [row.close_price for row in path]
        forward_returns = {
            label: closes[bars - 1] / entry_price - 1.0
            for label, bars in HORIZON_LABELS
        }

        max_high = max(row.high_price for row in path)
        min_low = min(row.low_price for row in path)
        high_bar = next(
            index
            for index, row in enumerate(path, start=1)
            if row.high_price == max_high
        )
        low_bar = next(
            index
            for index, row in enumerate(path, start=1)
            if row.low_price == min_low
        )
        long_mfe = max(0.0, max_high / entry_price - 1.0)
        long_mae = max(0.0, 1.0 - min_low / entry_price)
        short_mfe = max(0.0, 1.0 - min_low / entry_price)
        short_mae = max(0.0, max_high / entry_price - 1.0)

        barrier_hits = _barrier_hits(
            entry_price=entry_price,
            risk_unit_frac=risk_unit_frac,
            path=path,
            barriers=self.config.barrier_r_multiples,
            interval_minutes=self.interval_minutes,
        )
        continuation = _continuation(path, HORIZON_LABELS)

        funding_payload = [
            {
                "funding_time_ms": int(ts),
                "funding_rate": float(rate),
                "mark_price": None if mark is None else float(mark),
            }
            for ts, rate, mark in funding_events
        ]
        total_funding = float(sum(float(rate) for _ts, rate, _mark in funding_events))
        funding_source_digest = _definition_hash(funding_payload)
        roundtrip_base = (
            2.0 * self.config.taker_fee_rate
            + (
                self.config.entry_slippage_bps + self.config.exit_slippage_bps
            )
            / 10_000.0
            + spread_pct / 100.0
        )

        net_long: dict[str, float] = {}
        net_short: dict[str, float] = {}
        for label, bars in HORIZON_LABELS:
            horizon_close_ms = (
                event_open_ms + (bars + 1) * self.interval_ms - 1
            )
            funding_sum = sum(
                float(rate)
                for ts, rate, _mark in funding_events
                if int(ts) <= horizon_close_ms
            )
            gross_long = forward_returns[label]
            gross_short = -forward_returns[label]
            net_long[label] = gross_long - roundtrip_base - funding_sum
            net_short[label] = gross_short - roundtrip_base + funding_sum

        row: dict[str, Any] = {
            "event_open_ms": event_open_ms,
            "symbol": symbol,
            "feature_version": self.config.feature_version,
            "outcome_version": self.config.outcome_version,
            "built_at_ms": built_at_ms,
            "entry_price": entry_price,
            "source_min_event_open_ms": event_open_ms + self.interval_ms,
            "source_max_event_open_ms": (
                event_open_ms + self.config.max_horizon_bars * self.interval_ms
            ),
            "future_candle_count": len(path),
            "fallback_candle_count": len(fallback_opens),
            "source_candle_digest": _candle_source_digest(path),
            "fwd_ret_5m": forward_returns["5m"],
            "fwd_ret_15m": forward_returns["15m"],
            "fwd_ret_30m": forward_returns["30m"],
            "fwd_ret_1h": forward_returns["1h"],
            "fwd_ret_2h": forward_returns["2h"],
            "fwd_ret_4h": forward_returns["4h"],
            "long_mfe_frac": long_mfe,
            "long_mae_frac": long_mae,
            "short_mfe_frac": short_mfe,
            "short_mae_frac": short_mae,
            "time_to_long_mfe_min": high_bar * self.interval_minutes,
            "time_to_long_mae_min": low_bar * self.interval_minutes,
            "time_to_short_mfe_min": low_bar * self.interval_minutes,
            "time_to_short_mae_min": high_bar * self.interval_minutes,
            "future_realized_vol_4h": _future_realized_vol(entry_price, closes),
            "risk_unit_version": self.config.risk_unit_version,
            "risk_unit_frac": risk_unit_frac,
            "barrier_hits_json": _canonical_json(barrier_hits),
            "continuation_json": _canonical_json(continuation),
            "funding_complete": 1,
            "funding_event_count": len(funding_events),
            "funding_rate_sum": total_funding,
            "funding_events_json": _canonical_json(funding_payload),
            "funding_source_digest": funding_source_digest,
            "cost_version": self.config.cost_version,
            "roundtrip_base_cost_frac": roundtrip_base,
            "net_long_5m": net_long["5m"],
            "net_long_15m": net_long["15m"],
            "net_long_30m": net_long["30m"],
            "net_long_1h": net_long["1h"],
            "net_long_2h": net_long["2h"],
            "net_long_4h": net_long["4h"],
            "net_short_5m": net_short["5m"],
            "net_short_15m": net_short["15m"],
            "net_short_30m": net_short["30m"],
            "net_short_1h": net_short["1h"],
            "net_short_2h": net_short["2h"],
            "net_short_4h": net_short["4h"],
        }
        row["path_digest"] = _definition_hash(
            [row[field] for field in PATH_DIGEST_FIELDS]
        )
        return row

    def _persist_event(
        self,
        *,
        event_open_ms: int,
        rows: list[dict[str, Any]],
        source_digest: str,
        rebuild: bool,
        built_at_ms: int,
    ) -> int:
        event_digest = _rows_digest(
            rows,
            ("event_open_ms", "symbol", "path_digest"),
        )
        fallback_count = sum(int(row["fallback_candle_count"]) for row in rows)
        placeholders = ",".join("?" for _ in PATH_COLUMNS)
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            feature_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM canonical_features
                    WHERE event_open_ms=? AND feature_version=?
                    """,
                    (event_open_ms, self.config.feature_version),
                ).fetchone()[0]
            )
            if feature_count != len(rows):
                raise FuturePathError(
                    f"NBOT_V343_PATH_ROW_COUNT_MISMATCH:{event_open_ms}:"
                    f"{len(rows)}:{feature_count}"
                )

            existing = conn.execute(
                """
                SELECT 1 FROM future_path_builds
                WHERE event_open_ms=? AND outcome_version=?
                """,
                (event_open_ms, self.config.outcome_version),
            ).fetchone()
            if existing is not None and not rebuild:
                return 0
            if rebuild:
                conn.execute(
                    """
                    DELETE FROM future_path_builds
                    WHERE event_open_ms=? AND outcome_version=?
                    """,
                    (event_open_ms, self.config.outcome_version),
                )
                conn.execute(
                    """
                    DELETE FROM future_paths
                    WHERE event_open_ms=? AND outcome_version=?
                    """,
                    (event_open_ms, self.config.outcome_version),
                )

            conn.executemany(
                f"""
                INSERT INTO future_paths({','.join(PATH_COLUMNS)})
                VALUES ({placeholders})
                """,
                [[row[field] for field in PATH_COLUMNS] for row in rows],
            )
            conn.execute(
                """
                INSERT INTO future_path_builds(
                    event_open_ms, outcome_version, built_at_ms,
                    path_row_count, path_digest, source_digest,
                    fallback_candle_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_open_ms,
                    self.config.outcome_version,
                    built_at_ms,
                    len(rows),
                    event_digest,
                    source_digest,
                    fallback_count,
                ),
            )
            conn.execute(
                """
                INSERT INTO future_path_attempts(
                    event_open_ms, attempted_at_ms, outcome_version, result,
                    expected_symbols, completed_symbols, missing_candles, detail
                ) VALUES (?, ?, ?, 'COMPLETE', ?, ?, 0, NULL)
                """,
                (
                    event_open_ms,
                    built_at_ms,
                    self.config.outcome_version,
                    len(rows),
                    len(rows),
                ),
            )
        return len(rows)

    def build(
        self,
        *,
        max_events: int = 0,
        rebuild: bool = False,
    ) -> FuturePathBuildResult:
        """Build mature labels oldest-first; zero means all currently eligible events."""

        limit = int(max_events)
        if limit < 0:
            raise ValueError("NBOT_V343_MAX_EVENTS_INVALID")
        self.initialize()
        server_time_ms = int(self.client.server_time_ms())
        latest_closed = _latest_closed_open_ms(server_time_ms, self.interval_ms)
        with self.db.connection() as conn:
            feature_events, mature_events, pending_build = self._event_counts(
                conn,
                latest_closed,
            )
            target_events = self._eligible_events(
                conn,
                latest_closed,
                limit,
                rebuild,
            )

        pending_maturity = feature_events - mature_events
        attempted = 0
        built = 0
        path_rows_total = 0
        fallback_fetched_total = 0
        funding_incomplete = 0
        path_incomplete = 0
        required_offsets = tuple(range(1, self.config.max_horizon_bars + 1))

        for event_open_ms in target_events:
            attempted += 1
            with self.db.connection() as conn:
                features = self._load_features(conn, event_open_ms)
                event_row = conn.execute(
                    "SELECT event_close_ms FROM market_events WHERE event_open_ms=?",
                    (event_open_ms,),
                ).fetchone()
                if event_row is None:
                    raise FuturePathError(
                        f"NBOT_V343_TARGET_EVENT_MISSING:{event_open_ms}"
                    )
                event_close_ms = int(event_row[0])
                max_horizon_close_ms = (
                    event_open_ms
                    + (self.config.max_horizon_bars + 1) * self.interval_ms
                    - 1
                )

            coverage = self.db.funding_coverage(
                event_close_ms + 1,
                max_horizon_close_ms,
            )
            if not coverage.complete:
                funding_incomplete += 1
                self._record_attempt(
                    event_open_ms=event_open_ms,
                    result="FUNDING_INCOMPLETE",
                    expected_symbols=len(features),
                    completed_symbols=0,
                    missing_candles=0,
                    detail="funding sync must cover the complete 4h label window",
                )
                continue

            symbols = [str(row[0]) for row in features]
            missing_by_symbol: dict[str, list[int]] = {}
            required = [
                event_open_ms + offset * self.interval_ms
                for offset in required_offsets
            ]
            with self.db.connection() as conn:
                bulk_paths = self._load_path_candles_bulk(
                    conn, symbols, event_open_ms
                )
                for symbol in symbols:
                    existing, _fallback = bulk_paths.get(symbol, ({}, set()))
                    missing = [value for value in required if value not in existing]
                    if missing:
                        missing_by_symbol[symbol] = missing

            fetched_count, fetch_errors = self._cache_missing_candles(
                missing_by_symbol
            )
            fallback_fetched_total += fetched_count
            if fetch_errors:
                missing_total = sum(len(values) for values in missing_by_symbol.values())
                path_incomplete += 1
                detail = "; ".join(
                    f"{symbol}={error}"
                    for symbol, error in sorted(fetch_errors.items())[:10]
                )
                self._record_attempt(
                    event_open_ms=event_open_ms,
                    result="FUTURE_CANDLE_FETCH_FAILED",
                    expected_symbols=len(features),
                    completed_symbols=len(features) - len(fetch_errors),
                    missing_candles=missing_total,
                    detail=detail,
                )
                continue

            built_at_ms = int(time.time() * 1000)
            event_rows: list[dict[str, Any]] = []
            unresolved = 0
            with self.db.connection() as conn:
                bulk_paths = self._load_path_candles_bulk(
                    conn, symbols, event_open_ms
                )
                funding_by_symbol = self._load_funding_bulk(
                    conn, symbols, event_close_ms, max_horizon_close_ms
                )
                for symbol, close_price, atr14_frac, spread_pct in features:
                    symbol_text = str(symbol)
                    path_map, fallback_opens = bulk_paths.get(
                        symbol_text, ({}, set())
                    )
                    if any(open_ms not in path_map for open_ms in required):
                        unresolved += sum(
                            open_ms not in path_map for open_ms in required
                        )
                        continue
                    path = [path_map[open_ms] for open_ms in required]
                    event_rows.append(
                        self._build_row(
                            event_open_ms=event_open_ms,
                            symbol=symbol_text,
                            entry_price=float(close_price),
                            risk_unit_frac=(
                                None if atr14_frac is None else float(atr14_frac)
                            ),
                            spread_pct=float(spread_pct),
                            path=path,
                            fallback_opens=fallback_opens,
                            funding_events=funding_by_symbol.get(symbol_text, []),
                            built_at_ms=built_at_ms,
                        )
                    )

            if unresolved or len(event_rows) != len(features):
                path_incomplete += 1
                self._record_attempt(
                    event_open_ms=event_open_ms,
                    result="FUTURE_PATH_INCOMPLETE",
                    expected_symbols=len(features),
                    completed_symbols=len(event_rows),
                    missing_candles=unresolved,
                    detail=(
                        "event build is atomic; no partial future-path event was committed"
                    ),
                )
                continue

            source_digest = self._event_source_digest(event_open_ms)
            persisted = self._persist_event(
                event_open_ms=event_open_ms,
                rows=event_rows,
                source_digest=source_digest,
                rebuild=rebuild,
                built_at_ms=built_at_ms,
            )
            if persisted:
                built += 1
                path_rows_total += persisted

        return FuturePathBuildResult(
            outcome_version=self.config.outcome_version,
            feature_events=feature_events,
            mature_events=mature_events,
            pending_maturity_events=pending_maturity,
            pending_build_events=pending_build,
            attempted_events=attempted,
            built_events=built,
            path_rows=path_rows_total,
            fallback_candles_fetched=fallback_fetched_total,
            funding_incomplete_events=funding_incomplete,
            path_incomplete_events=path_incomplete,
        )

    def audit(self) -> dict[str, Any]:
        """Read-only definition, source-lineage, and output-lineage audit."""

        feature_audit = self.feature_store.audit()
        expected_definition_json = _canonical_json(self.definition())
        expected_definition_hash = _definition_hash(self.definition())
        with self.db.connection() as conn:
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing_tables = tuple(
                table for table in FUTURE_PATH_TABLES if table not in tables
            )
            if missing_tables:
                return {
                    "outcome_version": self.config.outcome_version,
                    "feature_version": self.config.feature_version,
                    "definition_hash": expected_definition_hash,
                    "missing_tables": missing_tables,
                    "feature_audit_healthy": bool(feature_audit["healthy"]),
                    "definition_mismatch": 1,
                    "feature_events": 0,
                    "built_events": 0,
                    "path_rows": 0,
                    "unbuilt_feature_events": 0,
                    "paths_without_feature": 0,
                    "paths_without_build": 0,
                    "invalid_source_bounds": 0,
                    "invalid_path_values": 0,
                    "cost_version_mismatches": 0,
                    "risk_version_mismatches": 0,
                    "build_row_mismatches": 0,
                    "future_cache_conflicts": 0,
                    "path_digest_mismatches": 0,
                    "build_digest_mismatches": 0,
                    "source_digest_mismatches": 0,
                    "source_candle_digest_mismatches": 0,
                    "funding_source_digest_mismatches": 0,
                    "funding_coverage_mismatches": 0,
                    "json_errors": 0,
                    "unresolved_attempt_events": 0,
                    "healthy": False,
                }

            stored = conn.execute(
                """
                SELECT feature_version, definition_hash, definition_json
                FROM future_path_sets WHERE outcome_version=?
                """,
                (self.config.outcome_version,),
            ).fetchone()
            definition_mismatch = int(
                stored
                != (
                    self.config.feature_version,
                    expected_definition_hash,
                    expected_definition_json,
                )
            )
            feature_events = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM feature_builds
                    WHERE feature_version=?
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            built_events = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_path_builds
                    WHERE outcome_version=?
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            path_rows_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE outcome_version=?",
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            paths_without_feature = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_paths p
                    LEFT JOIN canonical_features f
                      ON f.event_open_ms=p.event_open_ms
                     AND f.symbol=p.symbol
                     AND f.feature_version=p.feature_version
                    WHERE p.outcome_version=? AND f.symbol IS NULL
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            paths_without_build = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_paths p
                    WHERE p.outcome_version=? AND NOT EXISTS (
                        SELECT 1 FROM future_path_builds b
                        WHERE b.event_open_ms=p.event_open_ms
                          AND b.outcome_version=p.outcome_version
                    )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            invalid_source_bounds = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_paths
                    WHERE outcome_version=? AND (
                        source_min_event_open_ms != event_open_ms + ? OR
                        source_max_event_open_ms != event_open_ms + ? OR
                        future_candle_count != ?
                    )
                    """,
                    (
                        self.config.outcome_version,
                        self.interval_ms,
                        self.config.max_horizon_bars * self.interval_ms,
                        self.config.max_horizon_bars,
                    ),
                ).fetchone()[0]
            )
            invalid_path_values = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_paths
                    WHERE outcome_version=? AND (
                        entry_price<=0 OR long_mfe_frac<0 OR long_mae_frac<0 OR
                        short_mfe_frac<0 OR short_mae_frac<0 OR
                        future_realized_vol_4h<0 OR funding_complete!=1 OR
                        roundtrip_base_cost_frac<0 OR
                        (risk_unit_frac IS NOT NULL AND risk_unit_frac<=0)
                    )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            cost_version_mismatches = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_paths
                    WHERE outcome_version=? AND cost_version!=?
                    """,
                    (self.config.outcome_version, self.config.cost_version),
                ).fetchone()[0]
            )
            risk_version_mismatches = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_paths
                    WHERE outcome_version=? AND risk_unit_version!=?
                    """,
                    (self.config.outcome_version, self.config.risk_unit_version),
                ).fetchone()[0]
            )
            build_row_mismatches = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_path_builds b
                    WHERE b.outcome_version=? AND b.path_row_count != (
                        SELECT COUNT(*) FROM future_paths p
                        WHERE p.event_open_ms=b.event_open_ms
                          AND p.outcome_version=b.outcome_version
                    )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            future_cache_conflicts = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM future_candle_cache c
                    JOIN candles_5m r
                      ON r.symbol=c.symbol AND r.event_open_ms=c.event_open_ms
                    WHERE ABS(c.open_price-r.open_price)>1e-12
                       OR ABS(c.high_price-r.high_price)>1e-12
                       OR ABS(c.low_price-r.low_price)>1e-12
                       OR ABS(c.close_price-r.close_price)>1e-12
                       OR ABS(c.base_volume-r.base_volume)>1e-12
                       OR ABS(c.quote_volume-r.quote_volume)>1e-12
                       OR c.trade_count!=r.trade_count
                       OR ABS(c.taker_buy_base_volume-r.taker_buy_base_volume)>1e-12
                       OR ABS(c.taker_buy_quote_volume-r.taker_buy_quote_volume)>1e-12
                    """
                ).fetchone()[0]
            )
            unresolved_attempt_events = int(
                conn.execute(
                    """
                    SELECT COUNT(DISTINCT a.event_open_ms)
                    FROM future_path_attempts a
                    WHERE a.outcome_version=? AND a.result!='COMPLETE'
                      AND NOT EXISTS (
                          SELECT 1 FROM future_path_builds b
                          WHERE b.event_open_ms=a.event_open_ms
                            AND b.outcome_version=a.outcome_version
                      )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            rows = conn.execute(
                f"""
                SELECT {','.join(PATH_COLUMNS)} FROM future_paths
                WHERE outcome_version=? ORDER BY event_open_ms, symbol
                """,
                (self.config.outcome_version,),
            ).fetchall()
            build_rows = conn.execute(
                """
                SELECT event_open_ms, path_digest, source_digest
                FROM future_path_builds
                WHERE outcome_version=? ORDER BY event_open_ms
                """,
                (self.config.outcome_version,),
            ).fetchall()

        event_groups: dict[int, list[dict[str, Any]]] = {}
        path_digest_mismatches = 0
        source_candle_digest_mismatches = 0
        funding_source_digest_mismatches = 0
        funding_coverage_mismatches = 0
        json_errors = 0

        for raw in rows:
            row = dict(zip(PATH_COLUMNS, raw))
            expected_path_digest = _definition_hash(
                [row[field] for field in PATH_DIGEST_FIELDS]
            )
            if expected_path_digest != row["path_digest"]:
                path_digest_mismatches += 1
            try:
                barrier = json.loads(row["barrier_hits_json"])
                continuation = json.loads(row["continuation_json"])
                funding = json.loads(row["funding_events_json"])
                if (
                    not isinstance(barrier, dict)
                    or not isinstance(continuation, dict)
                    or not isinstance(funding, list)
                ):
                    json_errors += 1
            except Exception:
                json_errors += 1
            event_groups.setdefault(int(row["event_open_ms"]), []).append(row)

        build_map = {
            int(event_open_ms): (str(path_digest), str(source_digest))
            for event_open_ms, path_digest, source_digest in build_rows
        }
        build_digest_mismatches = 0
        source_digest_mismatches = 0

        for event_open_ms, event_rows in event_groups.items():
            expected_build_digest = _rows_digest(
                event_rows,
                ("event_open_ms", "symbol", "path_digest"),
            )
            stored_build = build_map.get(event_open_ms)
            if stored_build is None or stored_build[0] != expected_build_digest:
                build_digest_mismatches += 1

            with self.db.connection() as conn:
                event_close_row = conn.execute(
                    "SELECT event_close_ms FROM market_events WHERE event_open_ms=?",
                    (event_open_ms,),
                ).fetchone()
                if event_close_row is None:
                    source_digest_mismatches += 1
                    continue
                event_close_ms = int(event_close_row[0])
                end_open = (
                    event_open_ms
                    + self.config.max_horizon_bars * self.interval_ms
                )
                end_close = end_open + self.interval_ms - 1
                coverage = self._canonical_coverage_segments(
                    conn,
                    event_close_ms + 1,
                    end_close,
                )
                if coverage != [[event_close_ms + 1, end_close]]:
                    funding_coverage_mismatches += 1

                for row in event_rows:
                    symbol = str(row["symbol"])
                    path_map, _fallback = self._load_path_candles(
                        conn,
                        symbol,
                        event_open_ms,
                    )
                    opens = [
                        event_open_ms + offset * self.interval_ms
                        for offset in range(1, self.config.max_horizon_bars + 1)
                    ]
                    if any(value not in path_map for value in opens):
                        source_candle_digest_mismatches += 1
                    else:
                        current_candle_digest = _candle_source_digest(
                            [path_map[value] for value in opens]
                        )
                        if current_candle_digest != row["source_candle_digest"]:
                            source_candle_digest_mismatches += 1

                    funding_rows = conn.execute(
                        """
                        SELECT funding_time_ms, funding_rate, mark_price
                        FROM funding_events
                        WHERE symbol=? AND funding_time_ms>? AND funding_time_ms<=?
                        ORDER BY funding_time_ms
                        """,
                        (symbol, event_close_ms, end_close),
                    ).fetchall()
                    funding_payload = [
                        {
                            "funding_time_ms": int(ts),
                            "funding_rate": float(rate),
                            "mark_price": None if mark is None else float(mark),
                        }
                        for ts, rate, mark in funding_rows
                    ]
                    if _definition_hash(funding_payload) != row["funding_source_digest"]:
                        funding_source_digest_mismatches += 1

            try:
                current_source_digest = self._event_source_digest(event_open_ms)
            except FuturePathError:
                source_digest_mismatches += 1
            else:
                if stored_build is None or stored_build[1] != current_source_digest:
                    source_digest_mismatches += 1

        healthy = all(
            value == 0
            for value in (
                definition_mismatch,
                paths_without_feature,
                paths_without_build,
                invalid_source_bounds,
                invalid_path_values,
                cost_version_mismatches,
                risk_version_mismatches,
                build_row_mismatches,
                future_cache_conflicts,
                path_digest_mismatches,
                build_digest_mismatches,
                source_digest_mismatches,
                source_candle_digest_mismatches,
                funding_source_digest_mismatches,
                funding_coverage_mismatches,
                json_errors,
                unresolved_attempt_events,
            )
        ) and bool(feature_audit["healthy"])

        return {
            "outcome_version": self.config.outcome_version,
            "feature_version": self.config.feature_version,
            "definition_hash": expected_definition_hash,
            "missing_tables": (),
            "feature_audit_healthy": bool(feature_audit["healthy"]),
            "definition_mismatch": definition_mismatch,
            "feature_events": feature_events,
            "built_events": built_events,
            "path_rows": path_rows_count,
            "unbuilt_feature_events": feature_events - built_events,
            "paths_without_feature": paths_without_feature,
            "paths_without_build": paths_without_build,
            "invalid_source_bounds": invalid_source_bounds,
            "invalid_path_values": invalid_path_values,
            "cost_version_mismatches": cost_version_mismatches,
            "risk_version_mismatches": risk_version_mismatches,
            "build_row_mismatches": build_row_mismatches,
            "future_cache_conflicts": future_cache_conflicts,
            "path_digest_mismatches": path_digest_mismatches,
            "build_digest_mismatches": build_digest_mismatches,
            "source_digest_mismatches": source_digest_mismatches,
            "source_candle_digest_mismatches": source_candle_digest_mismatches,
            "funding_source_digest_mismatches": funding_source_digest_mismatches,
            "funding_coverage_mismatches": funding_coverage_mismatches,
            "json_errors": json_errors,
            "unresolved_attempt_events": unresolved_attempt_events,
            "healthy": healthy,
        }
