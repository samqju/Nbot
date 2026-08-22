"""Immutable canonical-feature research layer for NBOT V3.4.1.

The V3 feature contract is frozen separately from calculation.  This module
calculates V2-equivalent rows from complete point-in-time targets and objective
past candles, then may persist deterministic derived-only builds with immutable
source/output digests.  Raw V3.3 evidence remains immutable; candle-only
recovered events may supply past candle history but can never become feature
targets.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import statistics
import time
from datetime import datetime, timezone
from typing import Any

from .database import EvidenceDatabase


CANONICAL_FEATURE_VERSION = "CANONICAL_FEATURES_V3_V1"
V2_REFERENCE_FEATURE_VERSION = "CANONICAL_FEATURES_V1"

CANONICAL_FEATURE_FIELDS = (
    "event_open_ms",
    "symbol",
    "feature_version",
    "computed_at_ms",
    "source_min_event_open_ms",
    "source_max_event_open_ms",
    "history_bars",
    "full_history_4h",
    "close_price",
    "ret_5m",
    "ret_15m",
    "ret_30m",
    "ret_1h",
    "ret_2h",
    "ret_4h",
    "realized_vol_1h",
    "realized_vol_4h",
    "atr14_frac",
    "range_frac",
    "quote_volume_24h_usd",
    "spread_pct",
    "funding_rate",
    "minutes_to_next_funding",
    "selection_rank",
    "liquidity_percentile",
    "ret_1h_percentile",
    "ret_4h_percentile",
    "volatility_percentile",
    "btc_ret_5m",
    "btc_ret_1h",
    "btc_ret_4h",
    "breadth_positive_5m",
    "breadth_positive_1h",
    "median_ret_5m",
    "median_ret_1h",
    "utc_hour",
    "utc_minute",
    "utc_day_of_week",
    "context_delay_ms",
)

RESEARCH_FEATURE_TABLES = (
    "feature_sets",
    "canonical_features",
    "feature_builds",
)

FEATURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS feature_sets (
    feature_version TEXT PRIMARY KEY,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS canonical_features (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    computed_at_ms INTEGER NOT NULL,
    source_min_event_open_ms INTEGER NOT NULL,
    source_max_event_open_ms INTEGER NOT NULL,
    history_bars INTEGER NOT NULL CHECK (history_bars >= 1),
    full_history_4h INTEGER NOT NULL CHECK (full_history_4h IN (0, 1)),
    close_price REAL NOT NULL,
    ret_5m REAL,
    ret_15m REAL,
    ret_30m REAL,
    ret_1h REAL,
    ret_2h REAL,
    ret_4h REAL,
    realized_vol_1h REAL,
    realized_vol_4h REAL,
    atr14_frac REAL,
    range_frac REAL,
    quote_volume_24h_usd REAL NOT NULL,
    spread_pct REAL NOT NULL,
    funding_rate REAL,
    minutes_to_next_funding REAL,
    selection_rank INTEGER NOT NULL,
    liquidity_percentile REAL,
    ret_1h_percentile REAL,
    ret_4h_percentile REAL,
    volatility_percentile REAL,
    btc_ret_5m REAL,
    btc_ret_1h REAL,
    btc_ret_4h REAL,
    breadth_positive_5m REAL,
    breadth_positive_1h REAL,
    median_ret_5m REAL,
    median_ret_1h REAL,
    utc_hour INTEGER NOT NULL,
    utc_minute INTEGER NOT NULL,
    utc_day_of_week INTEGER NOT NULL,
    context_delay_ms INTEGER NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, feature_version),
    FOREIGN KEY (event_open_ms, symbol)
        REFERENCES market_snapshots(event_open_ms, symbol) ON DELETE CASCADE,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE TABLE IF NOT EXISTS feature_builds (
    event_open_ms INTEGER NOT NULL,
    feature_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    feature_row_count INTEGER NOT NULL CHECK (feature_row_count >= 0),
    source_digest TEXT NOT NULL,
    feature_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, feature_version),
    FOREIGN KEY (event_open_ms) REFERENCES market_events(event_open_ms) ON DELETE CASCADE,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE INDEX IF NOT EXISTS idx_canonical_features_symbol_time
    ON canonical_features(symbol, event_open_ms, feature_version);
CREATE INDEX IF NOT EXISTS idx_feature_builds_version_time
    ON feature_builds(feature_version, event_open_ms);
"""


class CanonicalFeatureError(RuntimeError):
    """Canonical feature definition/storage state is inconsistent."""


@dataclass(frozen=True)
class FeatureBuildResult:
    feature_version: str
    research_ready_events: int
    pending_before: int
    attempted_events: int
    built_events: int
    feature_rows: int


@dataclass(frozen=True)
class CanonicalFeatureConfig:
    """Frozen V3.4.1 feature semantics; operational build limits come later."""

    feature_version: str = CANONICAL_FEATURE_VERSION
    return_lookback_bars: tuple[int, ...] = (1, 3, 6, 12, 24, 48)
    realized_vol_1h_bars: int = 12
    realized_vol_4h_bars: int = 48
    atr_bars: int = 14
    max_history_bars: int = 48

    def validate(self) -> None:
        if self.feature_version != CANONICAL_FEATURE_VERSION:
            raise ValueError("NBOT_V341_FEATURE_VERSION_INVALID")
        if self.return_lookback_bars != (1, 3, 6, 12, 24, 48):
            raise ValueError("NBOT_V341_RETURN_LOOKBACKS_IMMUTABLE")
        if (self.realized_vol_1h_bars, self.realized_vol_4h_bars) != (12, 48):
            raise ValueError("NBOT_V341_REALIZED_VOL_LOOKBACKS_IMMUTABLE")
        if self.atr_bars != 14:
            raise ValueError("NBOT_V341_ATR_LOOKBACK_IMMUTABLE")
        if self.max_history_bars != 48:
            raise ValueError("NBOT_V341_HISTORY_WINDOW_IMMUTABLE")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _definition_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _rows_digest(rows: tuple[dict[str, Any], ...]) -> str:
    fields = tuple(field for field in CANONICAL_FEATURE_FIELDS if field != "computed_at_ms")
    payload = [
        [row[field] for field in fields]
        for row in sorted(rows, key=lambda item: item["symbol"])
    ]
    return _definition_hash(payload)


def _percentiles(values: dict[str, float | None]) -> dict[str, float | None]:
    present = {symbol: float(value) for symbol, value in values.items() if value is not None}
    if not present:
        return {symbol: None for symbol in values}
    if len(present) == 1:
        only = next(iter(present))
        return {symbol: (0.5 if symbol == only else None) for symbol in values}

    ordered = sorted(present.values())
    denominator = len(ordered) - 1
    result: dict[str, float | None] = {}
    for symbol, raw in values.items():
        if raw is None:
            result[symbol] = None
            continue
        value = float(raw)
        less = sum(1 for candidate in ordered if candidate < value)
        equal = sum(1 for candidate in ordered if candidate == value)
        result[symbol] = (less + (equal - 1) / 2.0) / denominator
    return result


def _return(current: float, previous: float | None) -> float | None:
    if previous is None or previous <= 0 or current <= 0:
        return None
    return current / previous - 1.0


def _realized_vol(closes: list[float] | None) -> float | None:
    if closes is None or len(closes) < 2 or any(value <= 0 for value in closes):
        return None
    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
    ]
    return math.sqrt(sum(value * value for value in returns))


def _atr_fraction(
    bars: list[tuple[float, float, float]] | None,
    current_close: float,
) -> float | None:
    if bars is None or len(bars) != 15 or current_close <= 0:
        return None
    true_ranges: list[float] = []
    for index in range(1, len(bars)):
        high, low, _close = bars[index]
        previous_close = bars[index - 1][2]
        true_ranges.append(
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        )
    return statistics.fmean(true_ranges) / current_close


class CanonicalFeatureStore:
    """Own only V3.4 derived feature metadata/tables over V3.3 truth."""

    def __init__(
        self,
        db: EvidenceDatabase,
        config: CanonicalFeatureConfig | None = None,
    ) -> None:
        self.db = db
        self.config = config or CanonicalFeatureConfig()
        self.config.validate()

    def feature_definition(self) -> dict[str, Any]:
        return {
            "feature_version": self.config.feature_version,
            "reference_definition": V2_REFERENCE_FEATURE_VERSION,
            "decision_clock": "COMPLETED_5M_EVENT",
            "fields": list(CANONICAL_FEATURE_FIELDS),
            "return_lookback_bars": list(self.config.return_lookback_bars),
            "realized_vol_1h_bars": self.config.realized_vol_1h_bars,
            "realized_vol_4h_bars": self.config.realized_vol_4h_bars,
            "atr_bars": self.config.atr_bars,
            "cross_section_percentile": "MIDRANK_0_TO_1",
            "target_requirement": {
                "market_event_status": "COMPLETE",
                "evidence_mode": "LIVE_POINT_IN_TIME",
                "context_complete": 1,
                "membership_quality": "POINT_IN_TIME",
                "snapshot_required": True,
            },
            "history_rule": "ONLY_EVENT_OPEN_MS_LE_TARGET_EVENT_AT_EXACT_5M_OFFSETS",
            "recovered_history_rule": (
                "CANDLE_ONLY_RECOVERY_MAY_SUPPLY_OBJECTIVE_PAST_CANDLES_"
                "BUT_NEVER_A_FEATURE_TARGET"
            ),
            "history_completeness": "history_bars_plus_full_history_4h",
            "raw_evidence_mutation": "FORBIDDEN",
        }

    @property
    def definition_hash(self) -> str:
        return _definition_hash(self.feature_definition())

    def initialize(self) -> None:
        """Create only derived research tables and register immutable semantics."""

        self.db.initialize()
        definition_json = _canonical_json(self.feature_definition())
        definition_hash = self.definition_hash
        with self.db.connection() as conn:
            conn.executescript(FEATURE_SCHEMA)
            build_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(feature_builds)")
            }
            if "source_digest" not in build_columns:
                existing_builds = int(
                    conn.execute("SELECT COUNT(*) FROM feature_builds").fetchone()[0]
                )
                if existing_builds:
                    raise CanonicalFeatureError(
                        "NBOT_V341_FEATURE_BUILD_SCHEMA_SOURCE_DIGEST_MISSING_NONEMPTY"
                    )
                conn.execute(
                    "ALTER TABLE feature_builds ADD COLUMN source_digest TEXT"
                )
            conn.execute(
                """
                INSERT OR IGNORE INTO feature_sets(
                    feature_version, definition_hash, definition_json, registered_at_ms
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    self.config.feature_version,
                    definition_hash,
                    definition_json,
                    int(time.time() * 1000),
                ),
            )
            stored = conn.execute(
                "SELECT definition_hash, definition_json FROM feature_sets WHERE feature_version=?",
                (self.config.feature_version,),
            ).fetchone()
        if stored != (definition_hash, definition_json):
            raise CanonicalFeatureError(
                "NBOT_V341_FEATURE_DEFINITION_HASH_MISMATCH:"
                f"{self.config.feature_version}"
            )

    def research_ready_event_opens(self) -> tuple[int, ...]:
        """Return only canonical point-in-time feature targets, oldest first."""

        self.initialize()
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT p.event_open_ms
                FROM event_provenance p
                JOIN market_events e USING(event_open_ms)
                WHERE e.status='COMPLETE'
                  AND p.evidence_mode='LIVE_POINT_IN_TIME'
                  AND p.context_complete=1
                  AND p.membership_quality='POINT_IN_TIME'
                ORDER BY p.event_open_ms
                """
            ).fetchall()
        return tuple(int(row[0]) for row in rows)

    def _load_history(
        self,
        conn,
        *,
        event_open_ms: int,
        symbols: set[str],
    ) -> dict[str, dict[int, tuple[float, float, float]]]:
        interval_ms = self.db.config.candle_interval_ms
        start_ms = event_open_ms - self.config.max_history_bars * interval_ms
        placeholders = ",".join("?" for _ in symbols)
        rows = conn.execute(
            f"""
            SELECT symbol, event_open_ms, high_price, low_price, close_price
            FROM candles_5m
            WHERE event_open_ms BETWEEN ? AND ?
              AND symbol IN ({placeholders})
            ORDER BY symbol, event_open_ms
            """,
            [start_ms, event_open_ms, *sorted(symbols)],
        ).fetchall()
        history: dict[str, dict[int, tuple[float, float, float]]] = {}
        for symbol, source_open_ms, high, low, close in rows:
            history.setdefault(str(symbol), {})[int(source_open_ms)] = (
                float(high),
                float(low),
                float(close),
            )
        return history

    def _base_feature_row(
        self,
        *,
        event_open_ms: int,
        event_close_ms: int,
        snapshot: tuple[Any, ...],
        history: dict[str, dict[int, tuple[float, float, float]]],
        computed_at_ms: int,
    ) -> dict[str, Any]:
        (
            symbol,
            selection_rank,
            quote_volume_24h_usd,
            spread_pct,
            funding_rate,
            next_funding_time_ms,
            snapshot_captured_at_ms,
        ) = snapshot
        symbol = str(symbol)
        interval_ms = self.db.config.candle_interval_ms
        symbol_history = history.get(symbol, {})
        current = symbol_history.get(event_open_ms)
        if current is None:
            raise CanonicalFeatureError(
                f"NBOT_V341_TARGET_CANDLE_MISSING:{event_open_ms}:{symbol}"
            )
        current_high, current_low, current_close = current

        def prior_close(bars: int) -> float | None:
            row = symbol_history.get(event_open_ms - bars * interval_ms)
            return None if row is None else row[2]

        def exact_closes(bars: int) -> list[float] | None:
            result: list[float] = []
            for offset in range(bars, -1, -1):
                row = symbol_history.get(event_open_ms - offset * interval_ms)
                if row is None:
                    return None
                result.append(row[2])
            return result

        expected_opens = [
            event_open_ms - offset * interval_ms
            for offset in range(self.config.max_history_bars, -1, -1)
        ]
        available_opens = [value for value in expected_opens if value in symbol_history]
        history_bars = len(available_opens)
        source_min_event_open_ms = min(available_opens)

        atr_source: list[tuple[float, float, float]] | None = []
        for offset in range(self.config.atr_bars, -1, -1):
            row = symbol_history.get(event_open_ms - offset * interval_ms)
            if row is None:
                atr_source = None
                break
            atr_source.append(row)

        minutes_to_next_funding = None
        if next_funding_time_ms is not None:
            minutes_to_next_funding = (
                int(next_funding_time_ms) - event_close_ms
            ) / 60_000.0

        return {
            "event_open_ms": event_open_ms,
            "symbol": symbol,
            "feature_version": self.config.feature_version,
            "computed_at_ms": computed_at_ms,
            "source_min_event_open_ms": source_min_event_open_ms,
            "source_max_event_open_ms": event_open_ms,
            "history_bars": history_bars,
            "full_history_4h": int(history_bars == self.config.max_history_bars + 1),
            "close_price": current_close,
            "ret_5m": _return(current_close, prior_close(1)),
            "ret_15m": _return(current_close, prior_close(3)),
            "ret_30m": _return(current_close, prior_close(6)),
            "ret_1h": _return(current_close, prior_close(12)),
            "ret_2h": _return(current_close, prior_close(24)),
            "ret_4h": _return(current_close, prior_close(48)),
            "realized_vol_1h": _realized_vol(exact_closes(self.config.realized_vol_1h_bars)),
            "realized_vol_4h": _realized_vol(exact_closes(self.config.realized_vol_4h_bars)),
            "atr14_frac": _atr_fraction(atr_source, current_close),
            "range_frac": (current_high - current_low) / current_close,
            "quote_volume_24h_usd": float(quote_volume_24h_usd),
            "spread_pct": float(spread_pct),
            "funding_rate": None if funding_rate is None else float(funding_rate),
            "minutes_to_next_funding": minutes_to_next_funding,
            "selection_rank": int(selection_rank),
            "liquidity_percentile": None,
            "ret_1h_percentile": None,
            "ret_4h_percentile": None,
            "volatility_percentile": None,
            "btc_ret_5m": None,
            "btc_ret_1h": None,
            "btc_ret_4h": None,
            "breadth_positive_5m": None,
            "breadth_positive_1h": None,
            "median_ret_5m": None,
            "median_ret_1h": None,
            "utc_hour": 0,
            "utc_minute": 0,
            "utc_day_of_week": 0,
            "context_delay_ms": int(snapshot_captured_at_ms) - event_close_ms,
        }

    @staticmethod
    def _complete_cross_section(
        rows: list[dict[str, Any]],
        *,
        event_close_ms: int,
    ) -> None:
        liquidity = _percentiles(
            {row["symbol"]: row["quote_volume_24h_usd"] for row in rows}
        )
        ret_1h = _percentiles({row["symbol"]: row["ret_1h"] for row in rows})
        ret_4h = _percentiles({row["symbol"]: row["ret_4h"] for row in rows})
        volatility = _percentiles(
            {row["symbol"]: row["realized_vol_1h"] for row in rows}
        )

        by_symbol = {row["symbol"]: row for row in rows}
        btc = by_symbol.get("BTCUSDT")
        btc_ret_5m = None if btc is None else btc["ret_5m"]
        btc_ret_1h = None if btc is None else btc["ret_1h"]
        btc_ret_4h = None if btc is None else btc["ret_4h"]

        returns_5m = [row["ret_5m"] for row in rows if row["ret_5m"] is not None]
        returns_1h = [row["ret_1h"] for row in rows if row["ret_1h"] is not None]
        breadth_5m = (
            None
            if not returns_5m
            else sum(value > 0 for value in returns_5m) / len(returns_5m)
        )
        breadth_1h = (
            None
            if not returns_1h
            else sum(value > 0 for value in returns_1h) / len(returns_1h)
        )
        median_5m = None if not returns_5m else statistics.median(returns_5m)
        median_1h = None if not returns_1h else statistics.median(returns_1h)
        dt = datetime.fromtimestamp(event_close_ms / 1000, tz=timezone.utc)

        for row in rows:
            symbol = row["symbol"]
            row["liquidity_percentile"] = liquidity[symbol]
            row["ret_1h_percentile"] = ret_1h[symbol]
            row["ret_4h_percentile"] = ret_4h[symbol]
            row["volatility_percentile"] = volatility[symbol]
            row["btc_ret_5m"] = btc_ret_5m
            row["btc_ret_1h"] = btc_ret_1h
            row["btc_ret_4h"] = btc_ret_4h
            row["breadth_positive_5m"] = breadth_5m
            row["breadth_positive_1h"] = breadth_1h
            row["median_ret_5m"] = median_5m
            row["median_ret_1h"] = median_1h
            row["utc_hour"] = dt.hour
            row["utc_minute"] = dt.minute
            row["utc_day_of_week"] = dt.weekday()

    def compute_event_rows(
        self,
        event_open_ms: int,
        *,
        computed_at_ms: int,
    ) -> tuple[dict[str, Any], ...]:
        """Calculate one research-ready event without persisting derived rows."""

        target = int(event_open_ms)
        computed = int(computed_at_ms)
        if computed < 0:
            raise ValueError("NBOT_V341_COMPUTED_AT_INVALID")

        self.initialize()
        with self.db.connection() as conn:
            event = conn.execute(
                """
                SELECT e.event_close_ms
                FROM market_events e
                JOIN event_provenance p USING(event_open_ms)
                WHERE e.event_open_ms=?
                  AND e.status='COMPLETE'
                  AND p.evidence_mode='LIVE_POINT_IN_TIME'
                  AND p.context_complete=1
                  AND p.membership_quality='POINT_IN_TIME'
                """,
                (target,),
            ).fetchone()
            if event is None:
                raise CanonicalFeatureError(
                    f"NBOT_V341_FEATURE_TARGET_NOT_RESEARCH_READY:{target}"
                )
            event_close_ms = int(event[0])

            snapshot_rows = conn.execute(
                """
                SELECT symbol, universe_rank, quote_volume_24h_usd, spread_pct,
                       funding_rate, next_funding_time_ms, captured_at_ms
                FROM market_snapshots
                WHERE event_open_ms=?
                ORDER BY symbol
                """,
                (target,),
            ).fetchall()
            if not snapshot_rows:
                raise CanonicalFeatureError(
                    f"NBOT_V341_FEATURE_TARGET_SNAPSHOTS_MISSING:{target}"
                )
            symbols = {str(row[0]) for row in snapshot_rows}
            symbols.add("BTCUSDT")
            history = self._load_history(
                conn,
                event_open_ms=target,
                symbols=symbols,
            )

        rows = [
            self._base_feature_row(
                event_open_ms=target,
                event_close_ms=event_close_ms,
                snapshot=tuple(snapshot),
                history=history,
                computed_at_ms=computed,
            )
            for snapshot in snapshot_rows
        ]
        self._complete_cross_section(rows, event_close_ms=event_close_ms)
        for row in rows:
            if tuple(row) != CANONICAL_FEATURE_FIELDS:
                raise CanonicalFeatureError("NBOT_V341_FEATURE_FIELD_ORDER_MISMATCH")

        return tuple(rows)

    def _source_digest(self, event_open_ms: int) -> str:
        """Digest only raw fields that can affect this event's feature rows."""

        target = int(event_open_ms)
        interval_ms = self.db.config.candle_interval_ms
        start_ms = target - self.config.max_history_bars * interval_ms
        with self.db.connection() as conn:
            event = conn.execute(
                """
                SELECT e.event_open_ms, e.event_close_ms, e.status,
                       p.evidence_mode, p.context_complete, p.membership_quality
                FROM market_events e
                JOIN event_provenance p USING(event_open_ms)
                WHERE e.event_open_ms=?
                """,
                (target,),
            ).fetchone()
            snapshots = conn.execute(
                """
                SELECT symbol, universe_rank, quote_volume_24h_usd, spread_pct,
                       funding_rate, next_funding_time_ms, captured_at_ms
                FROM market_snapshots
                WHERE event_open_ms=?
                ORDER BY symbol
                """,
                (target,),
            ).fetchall()
            symbols = {str(row[0]) for row in snapshots}
            symbols.add("BTCUSDT")
            placeholders = ",".join("?" for _ in symbols)
            candles = conn.execute(
                f"""
                SELECT symbol, event_open_ms, high_price, low_price, close_price
                FROM candles_5m
                WHERE event_open_ms BETWEEN ? AND ?
                  AND symbol IN ({placeholders})
                ORDER BY symbol, event_open_ms
                """,
                [start_ms, target, *sorted(symbols)],
            ).fetchall()

        payload = {
            "event": None if event is None else list(event),
            "snapshots": [list(row) for row in snapshots],
            "candles": [list(row) for row in candles],
        }
        return _definition_hash(payload)

    def _persist_event(
        self,
        *,
        event_open_ms: int,
        rows: tuple[dict[str, Any], ...],
        source_digest: str,
        feature_digest: str,
        rebuild: bool,
        built_at_ms: int,
    ) -> int:
        """Persist one derived event inside one short write transaction."""

        target = int(event_open_ms)
        placeholders = ",".join("?" for _ in CANONICAL_FEATURE_FIELDS)
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            ready = conn.execute(
                """
                SELECT 1
                FROM market_events e
                JOIN event_provenance p USING(event_open_ms)
                WHERE e.event_open_ms=?
                  AND e.status='COMPLETE'
                  AND p.evidence_mode='LIVE_POINT_IN_TIME'
                  AND p.context_complete=1
                  AND p.membership_quality='POINT_IN_TIME'
                """,
                (target,),
            ).fetchone()
            if ready is None:
                raise CanonicalFeatureError(
                    f"NBOT_V341_FEATURE_TARGET_NOT_RESEARCH_READY_AT_WRITE:{target}"
                )
            expected = int(
                conn.execute(
                    "SELECT COUNT(*) FROM market_snapshots WHERE event_open_ms=?",
                    (target,),
                ).fetchone()[0]
            )
            if expected != len(rows):
                raise CanonicalFeatureError(
                    f"NBOT_V341_FEATURE_ROW_COUNT_MISMATCH:{target}:{len(rows)}:{expected}"
                )
            if any(int(row["source_max_event_open_ms"]) > target for row in rows):
                raise CanonicalFeatureError(
                    f"NBOT_V341_FEATURE_FUTURE_SOURCE_AT_WRITE:{target}"
                )

            existing = conn.execute(
                """
                SELECT 1 FROM feature_builds
                WHERE event_open_ms=? AND feature_version=?
                """,
                (target, self.config.feature_version),
            ).fetchone()
            if existing is not None and not rebuild:
                return 0
            if rebuild:
                conn.execute(
                    """
                    DELETE FROM feature_builds
                    WHERE event_open_ms=? AND feature_version=?
                    """,
                    (target, self.config.feature_version),
                )
                conn.execute(
                    """
                    DELETE FROM canonical_features
                    WHERE event_open_ms=? AND feature_version=?
                    """,
                    (target, self.config.feature_version),
                )

            conn.executemany(
                f"""
                INSERT INTO canonical_features({','.join(CANONICAL_FEATURE_FIELDS)})
                VALUES ({placeholders})
                """,
                [
                    [row[field] for field in CANONICAL_FEATURE_FIELDS]
                    for row in rows
                ],
            )
            conn.execute(
                """
                INSERT INTO feature_builds(
                    event_open_ms, feature_version, built_at_ms,
                    feature_row_count, source_digest, feature_digest
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    target,
                    self.config.feature_version,
                    int(built_at_ms),
                    len(rows),
                    str(source_digest),
                    str(feature_digest),
                ),
            )
        return len(rows)

    def _stored_feature_digest(self, conn, event_open_ms: int) -> str:
        """Digest persisted feature values using the frozen output contract."""

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
            (int(event_open_ms), self.config.feature_version),
        ).fetchall()
        payload = [list(row) for row in rows]
        return _definition_hash(payload)

    def audit(self) -> dict[str, Any]:
        """Read-only lineage audit for persisted V3.4.1 feature builds."""

        expected_definition_json = _canonical_json(self.feature_definition())
        expected_definition_hash = self.definition_hash
        with self.db.connection() as conn:
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing_tables = tuple(
                table for table in RESEARCH_FEATURE_TABLES if table not in tables
            )
            if missing_tables:
                return {
                    "feature_version": self.config.feature_version,
                    "definition_hash": expected_definition_hash,
                    "missing_tables": missing_tables,
                    "feature_definition_mismatch": 1,
                    "research_ready_events": 0,
                    "built_events": 0,
                    "unbuilt_events": 0,
                    "feature_rows": 0,
                    "non_research_ready_builds": 0,
                    "feature_rows_without_build": 0,
                    "feature_rows_without_snapshot": 0,
                    "future_source_rows": 0,
                    "feature_row_count_mismatches": 0,
                    "source_digest_mismatches": 0,
                    "feature_digest_mismatches": 0,
                    "healthy": False,
                }

            definition = conn.execute(
                """
                SELECT definition_hash, definition_json
                FROM feature_sets
                WHERE feature_version=?
                """,
                (self.config.feature_version,),
            ).fetchone()
            feature_definition_mismatch = int(
                definition != (expected_definition_hash, expected_definition_json)
            )

            ready_rows = conn.execute(
                """
                SELECT p.event_open_ms
                FROM event_provenance p
                JOIN market_events e USING(event_open_ms)
                WHERE e.status='COMPLETE'
                  AND p.evidence_mode='LIVE_POINT_IN_TIME'
                  AND p.context_complete=1
                  AND p.membership_quality='POINT_IN_TIME'
                ORDER BY p.event_open_ms
                """
            ).fetchall()
            ready = {int(row[0]) for row in ready_rows}
            builds = conn.execute(
                """
                SELECT event_open_ms, feature_row_count, source_digest, feature_digest
                FROM feature_builds
                WHERE feature_version=?
                ORDER BY event_open_ms
                """,
                (self.config.feature_version,),
            ).fetchall()
            built = {int(row[0]) for row in builds}
            retention_present = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_event_ledger'"
            ).fetchone() is not None
            compacted = (
                {int(row[0]) for row in conn.execute(
                    "SELECT event_open_ms FROM research_event_ledger WHERE state='COMPACTED'"
                )}
                if retention_present else set()
            )
            feature_rows = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM canonical_features
                    WHERE feature_version=?
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            non_research_ready_builds = sum(
                int(int(row[0]) not in ready) for row in builds
            )
            feature_rows_without_build = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM canonical_features f
                    LEFT JOIN feature_builds b
                      ON b.event_open_ms=f.event_open_ms
                     AND b.feature_version=f.feature_version
                    WHERE f.feature_version=? AND b.event_open_ms IS NULL
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            feature_rows_without_snapshot = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM canonical_features f
                    LEFT JOIN market_snapshots s
                      ON s.event_open_ms=f.event_open_ms AND s.symbol=f.symbol
                    WHERE f.feature_version=? AND s.symbol IS NULL
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            future_source_rows = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM canonical_features
                    WHERE feature_version=? AND (
                        source_max_event_open_ms > event_open_ms OR
                        source_min_event_open_ms > source_max_event_open_ms
                    )
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )

            feature_row_count_mismatches = 0
            feature_digest_mismatches = 0
            for event_open_ms, expected_count, _source_digest, feature_digest in builds:
                event_open_ms = int(event_open_ms)
                actual_count = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM canonical_features
                        WHERE event_open_ms=? AND feature_version=?
                        """,
                        (event_open_ms, self.config.feature_version),
                    ).fetchone()[0]
                )
                raw_snapshot_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM market_snapshots WHERE event_open_ms=?",
                        (event_open_ms,),
                    ).fetchone()[0]
                )
                feature_row_count_mismatches += int(
                    actual_count != int(expected_count)
                    or raw_snapshot_count != int(expected_count)
                )
                feature_digest_mismatches += int(
                    self._stored_feature_digest(conn, event_open_ms)
                    != str(feature_digest)
                )

        source_digest_mismatches = sum(
            int(self._source_digest(int(event_open_ms)) != str(source_digest))
            for event_open_ms, _count, source_digest, _feature_digest in builds
        )
        counters = (
            feature_definition_mismatch,
            non_research_ready_builds,
            feature_rows_without_build,
            feature_rows_without_snapshot,
            future_source_rows,
            feature_row_count_mismatches,
            source_digest_mismatches,
            feature_digest_mismatches,
        )
        return {
            "feature_version": self.config.feature_version,
            "definition_hash": expected_definition_hash,
            "missing_tables": (),
            "feature_definition_mismatch": feature_definition_mismatch,
            "research_ready_events": len(ready),
            "built_events": len(built),
            "compacted_events": len(ready & compacted),
            "unbuilt_events": len(ready - built - compacted),
            "feature_rows": feature_rows,
            "non_research_ready_builds": non_research_ready_builds,
            "feature_rows_without_build": feature_rows_without_build,
            "feature_rows_without_snapshot": feature_rows_without_snapshot,
            "future_source_rows": future_source_rows,
            "feature_row_count_mismatches": feature_row_count_mismatches,
            "source_digest_mismatches": source_digest_mismatches,
            "feature_digest_mismatches": feature_digest_mismatches,
            "healthy": all(value == 0 for value in counters),
        }

    def build(
        self,
        *,
        max_events: int = 1,
        rebuild: bool = False,
    ) -> FeatureBuildResult:
        """Build oldest eligible events; heavy calculation happens outside writes."""

        limit = int(max_events)
        if limit < 0:
            raise ValueError("NBOT_V341_FEATURE_MAX_EVENTS_INVALID")
        self.initialize()
        ready = self.research_ready_event_opens()
        with self.db.connection() as conn:
            built = {
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT event_open_ms FROM feature_builds
                    WHERE feature_version=?
                    """,
                    (self.config.feature_version,),
                )
            }
        with self.db.connection() as conn:
            retention_present = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='research_event_ledger'"
            ).fetchone() is not None
            compacted = (
                {int(row[0]) for row in conn.execute(
                    "SELECT event_open_ms FROM research_event_ledger WHERE state='COMPACTED'"
                )}
                if retention_present else set()
            )
        pending = tuple(event for event in ready if event not in built and event not in compacted)
        candidates = tuple(event for event in ready if event not in compacted) if rebuild else pending
        targets = candidates if limit == 0 else candidates[:limit]

        built_events = 0
        feature_rows = 0
        for target in targets:
            computed_at_ms = int(time.time() * 1000)
            rows = self.compute_event_rows(
                target,
                computed_at_ms=computed_at_ms,
            )
            source_digest = self._source_digest(target)
            feature_digest = _rows_digest(rows)
            inserted = self._persist_event(
                event_open_ms=target,
                rows=rows,
                source_digest=source_digest,
                feature_digest=feature_digest,
                rebuild=bool(rebuild),
                built_at_ms=computed_at_ms,
            )
            if inserted:
                built_events += 1
                feature_rows += inserted

        return FeatureBuildResult(
            feature_version=self.config.feature_version,
            research_ready_events=len(ready),
            pending_before=len(pending),
            attempted_events=len(targets),
            built_events=built_events,
            feature_rows=feature_rows,
        )
