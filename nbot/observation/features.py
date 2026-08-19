"""Immutable canonical-feature foundation for NBOT V3.4.1.

This first V3.4.1 slice defines the derived feature contract and storage layer
without computing features yet.  Raw V3.3 evidence remains immutable and its
schema module is not changed.  Only complete point-in-time events are eligible
future feature targets; candle-only recovered events remain explicitly outside
that target set.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
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
