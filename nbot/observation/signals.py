"""Deterministic research signal annotations for NBOT V3.4.2.

Signals are derived only from persisted canonical V3.4.1 features.  They are
research annotations, never evidence gates, recommendations, or order commands.
Every persisted feature row receives one annotation for each frozen signal
family, including explicit inactive / insufficient-history states.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time
from typing import Any

from .database import EvidenceDatabase
from .features import (
    CANONICAL_FEATURE_FIELDS,
    CANONICAL_FEATURE_VERSION,
    CanonicalFeatureStore,
)


SIGNAL_VERSIONS = (
    "CSM_RANK_1H_4H_V1",
    "TSMOM_4H_VOL_ADJ_V1",
    "INTRADAY_CONDITIONAL_MOM_REV_V1",
)

SIGNAL_ANNOTATION_FIELDS = (
    "event_open_ms",
    "symbol",
    "feature_version",
    "signal_version",
    "computed_at_ms",
    "score",
    "active",
    "direction",
    "reason",
    "metadata_json",
)

RESEARCH_SIGNAL_TABLES = (
    "signal_sets",
    "signal_annotations",
    "signal_builds",
)

SIGNAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS signal_sets (
    signal_version TEXT PRIMARY KEY,
    signal_name TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    registered_at_ms INTEGER NOT NULL,
    FOREIGN KEY (feature_version) REFERENCES feature_sets(feature_version)
);

CREATE TABLE IF NOT EXISTS signal_annotations (
    event_open_ms INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    signal_version TEXT NOT NULL,
    computed_at_ms INTEGER NOT NULL,
    score REAL,
    active INTEGER NOT NULL CHECK (active IN (0, 1)),
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT', 'NONE')),
    reason TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, symbol, signal_version),
    FOREIGN KEY (event_open_ms, symbol, feature_version)
        REFERENCES canonical_features(event_open_ms, symbol, feature_version)
        ON DELETE CASCADE,
    FOREIGN KEY (signal_version) REFERENCES signal_sets(signal_version)
);

CREATE TABLE IF NOT EXISTS signal_builds (
    event_open_ms INTEGER NOT NULL,
    feature_version TEXT NOT NULL,
    built_at_ms INTEGER NOT NULL,
    feature_row_count INTEGER NOT NULL CHECK (feature_row_count >= 0),
    signal_annotation_count INTEGER NOT NULL CHECK (signal_annotation_count >= 0),
    source_digest TEXT NOT NULL,
    signal_digest TEXT NOT NULL,
    PRIMARY KEY (event_open_ms, feature_version),
    FOREIGN KEY (event_open_ms, feature_version)
        REFERENCES feature_builds(event_open_ms, feature_version)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_signal_annotations_event_version
    ON signal_annotations(event_open_ms, feature_version, signal_version);
CREATE INDEX IF NOT EXISTS idx_signal_annotations_active
    ON signal_annotations(signal_version, active, event_open_ms);
CREATE INDEX IF NOT EXISTS idx_signal_builds_version_time
    ON signal_builds(feature_version, event_open_ms);
"""


class ResearchSignalError(RuntimeError):
    """Signal definition, feature lineage, or derived storage is inconsistent."""


@dataclass(frozen=True)
class SignalBuildResult:
    feature_version: str
    feature_events: int
    pending_before: int
    attempted_events: int
    built_events: int
    signal_annotations: int


@dataclass(frozen=True)
class ResearchSignalConfig:
    """Frozen V2-equivalent V3.4.2 signal semantics."""

    feature_version: str = CANONICAL_FEATURE_VERSION
    csm_active_abs_score: float = 0.60
    tsmom_active_abs_score: float = 0.50
    intraday_directional_breadth_high: float = 0.65
    intraday_directional_breadth_low: float = 0.35
    intraday_balanced_breadth_low: float = 0.45
    intraday_balanced_breadth_high: float = 0.55
    intraday_momentum_percentile: float = 0.65
    intraday_reversal_percentile: float = 0.90

    def validate(self) -> None:
        expected = ResearchSignalConfig()
        if self != expected:
            raise ValueError("NBOT_V342_SIGNAL_DEFINITION_IMMUTABLE")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _definition_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _signal_rows_digest(rows: tuple[dict[str, Any], ...]) -> str:
    fields = tuple(
        field for field in SIGNAL_ANNOTATION_FIELDS if field != "computed_at_ms"
    )
    payload = [
        [row[field] for field in fields]
        for row in sorted(rows, key=lambda item: (item["symbol"], item["signal_version"]))
    ]
    return _definition_hash(payload)


class ResearchSignalStore:
    """Build and audit research-only annotations over canonical feature rows."""

    def __init__(
        self,
        db: EvidenceDatabase,
        config: ResearchSignalConfig | None = None,
    ) -> None:
        self.db = db
        self.config = config or ResearchSignalConfig()
        self.config.validate()
        self.feature_store = CanonicalFeatureStore(db)

    def signal_definitions(self) -> dict[str, dict[str, Any]]:
        return {
            "CSM_RANK_1H_4H_V1": {
                "feature_version": self.config.feature_version,
                "v2_reference_signal_version": "CSM_RANK_1H_4H_V1",
                "formula": "0.4*(2*ret_1h_percentile-1)+0.6*(2*ret_4h_percentile-1)",
                "active_abs_score": self.config.csm_active_abs_score,
                "inactive_direction": "NONE",
            },
            "TSMOM_4H_VOL_ADJ_V1": {
                "feature_version": self.config.feature_version,
                "v2_reference_signal_version": "TSMOM_4H_VOL_ADJ_V1",
                "formula": "ret_4h/realized_vol_4h",
                "active_abs_score": self.config.tsmom_active_abs_score,
                "inactive_direction": "NONE",
            },
            "INTRADAY_CONDITIONAL_MOM_REV_V1": {
                "feature_version": self.config.feature_version,
                "v2_reference_signal_version": "INTRADAY_CONDITIONAL_MOM_REV_V1",
                "directional_breadth_high": self.config.intraday_directional_breadth_high,
                "directional_breadth_low": self.config.intraday_directional_breadth_low,
                "balanced_breadth_low": self.config.intraday_balanced_breadth_low,
                "balanced_breadth_high": self.config.intraday_balanced_breadth_high,
                "momentum_percentile": self.config.intraday_momentum_percentile,
                "reversal_percentile": self.config.intraday_reversal_percentile,
                "inactive_direction": "NONE",
            },
        }

    @property
    def definition_hashes(self) -> dict[str, str]:
        return {
            version: _definition_hash(definition)
            for version, definition in self.signal_definitions().items()
        }

    def initialize(self) -> None:
        """Create only derived signal tables and register frozen definitions."""

        self.feature_store.initialize()
        definitions = self.signal_definitions()
        now_ms = int(time.time() * 1000)
        with self.db.connection() as conn:
            conn.executescript(SIGNAL_SCHEMA)
            for signal_version in SIGNAL_VERSIONS:
                definition = definitions[signal_version]
                definition_json = _canonical_json(definition)
                definition_hash = _definition_hash(definition)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO signal_sets(
                        signal_version, signal_name, feature_version,
                        definition_hash, definition_json, registered_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal_version,
                        signal_version.rsplit("_V1", 1)[0],
                        self.config.feature_version,
                        definition_hash,
                        definition_json,
                        now_ms,
                    ),
                )
                stored = conn.execute(
                    """
                    SELECT feature_version, definition_hash, definition_json
                    FROM signal_sets WHERE signal_version=?
                    """,
                    (signal_version,),
                ).fetchone()
                expected = (
                    self.config.feature_version,
                    definition_hash,
                    definition_json,
                )
                if stored != expected:
                    raise ResearchSignalError(
                        "NBOT_V342_SIGNAL_DEFINITION_HASH_MISMATCH:"
                        f"{signal_version}"
                    )

    def feature_event_opens(self) -> tuple[int, ...]:
        """Return persisted canonical-feature events, oldest first."""

        self.initialize()
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT event_open_ms
                FROM feature_builds
                WHERE feature_version=?
                ORDER BY event_open_ms
                """,
                (self.config.feature_version,),
            ).fetchall()
        return tuple(int(row[0]) for row in rows)

    def _stored_feature_digest(self, conn, event_open_ms: int) -> str:
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
        return _definition_hash([list(row) for row in rows])

    def _feature_source_digest(self, event_open_ms: int) -> str:
        target = int(event_open_ms)
        with self.db.connection() as conn:
            build = conn.execute(
                """
                SELECT feature_row_count, feature_digest
                FROM feature_builds
                WHERE event_open_ms=? AND feature_version=?
                """,
                (target, self.config.feature_version),
            ).fetchone()
            if build is None:
                raise ResearchSignalError(
                    f"NBOT_V342_FEATURE_BUILD_MISSING:{target}"
                )
            actual_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM canonical_features
                    WHERE event_open_ms=? AND feature_version=?
                    """,
                    (target, self.config.feature_version),
                ).fetchone()[0]
            )
            actual_feature_digest = self._stored_feature_digest(conn, target)
        if actual_count != int(build[0]):
            raise ResearchSignalError(
                f"NBOT_V342_FEATURE_ROW_COUNT_MISMATCH:{target}"
            )
        if actual_feature_digest != str(build[1]):
            raise ResearchSignalError(
                f"NBOT_V342_FEATURE_DIGEST_MISMATCH:{target}"
            )
        return _definition_hash(
            {
                "feature_version": self.config.feature_version,
                "feature_definition_hash": self.feature_store.definition_hash,
                "feature_digest": actual_feature_digest,
            }
        )

    @staticmethod
    def _signal_row(
        row: tuple[Any, ...],
        *,
        signal_version: str,
        score: float | None,
        active: bool,
        direction: str,
        reason: str,
        metadata: dict[str, Any],
        computed_at_ms: int,
    ) -> dict[str, Any]:
        event_open_ms, symbol, feature_version = row[:3]
        return {
            "event_open_ms": int(event_open_ms),
            "symbol": str(symbol),
            "feature_version": str(feature_version),
            "signal_version": signal_version,
            "computed_at_ms": int(computed_at_ms),
            "score": score,
            "active": int(active),
            "direction": direction,
            "reason": reason,
            "metadata_json": _canonical_json(metadata),
        }

    def _signals_for_feature_row(
        self,
        row: tuple[Any, ...],
        *,
        computed_at_ms: int,
    ) -> tuple[dict[str, Any], ...]:
        (
            _event_open_ms,
            _symbol,
            _feature_version,
            ret_1h_percentile,
            ret_4h_percentile,
            ret_4h,
            realized_vol_4h,
            breadth_positive_1h,
            ret_1h,
        ) = row
        result: list[dict[str, Any]] = []

        if ret_1h_percentile is None or ret_4h_percentile is None:
            result.append(
                self._signal_row(
                    row,
                    signal_version=SIGNAL_VERSIONS[0],
                    score=None,
                    active=False,
                    direction="NONE",
                    reason="INSUFFICIENT_HISTORY",
                    metadata={},
                    computed_at_ms=computed_at_ms,
                )
            )
        else:
            score = (
                0.4 * (2.0 * float(ret_1h_percentile) - 1.0)
                + 0.6 * (2.0 * float(ret_4h_percentile) - 1.0)
            )
            active = abs(score) >= self.config.csm_active_abs_score
            direction = (
                "LONG" if active and score > 0
                else "SHORT" if active and score < 0
                else "NONE"
            )
            result.append(
                self._signal_row(
                    row,
                    signal_version=SIGNAL_VERSIONS[0],
                    score=score,
                    active=active,
                    direction=direction,
                    reason="EXTREME_RANK" if active else "MIDDLE_RANK",
                    metadata={},
                    computed_at_ms=computed_at_ms,
                )
            )

        if ret_4h is None or realized_vol_4h is None or float(realized_vol_4h) <= 0:
            result.append(
                self._signal_row(
                    row,
                    signal_version=SIGNAL_VERSIONS[1],
                    score=None,
                    active=False,
                    direction="NONE",
                    reason="INSUFFICIENT_HISTORY",
                    metadata={},
                    computed_at_ms=computed_at_ms,
                )
            )
        else:
            score = float(ret_4h) / float(realized_vol_4h)
            active = abs(score) >= self.config.tsmom_active_abs_score
            direction = (
                "LONG" if active and score > 0
                else "SHORT" if active and score < 0
                else "NONE"
            )
            result.append(
                self._signal_row(
                    row,
                    signal_version=SIGNAL_VERSIONS[1],
                    score=score,
                    active=active,
                    direction=direction,
                    reason="VOL_ADJUSTED_TREND" if active else "WEAK_TREND",
                    metadata={},
                    computed_at_ms=computed_at_ms,
                )
            )

        if (
            breadth_positive_1h is None
            or ret_1h_percentile is None
            or ret_1h is None
        ):
            result.append(
                self._signal_row(
                    row,
                    signal_version=SIGNAL_VERSIONS[2],
                    score=None,
                    active=False,
                    direction="NONE",
                    reason="INSUFFICIENT_HISTORY",
                    metadata={"mode": "NONE"},
                    computed_at_ms=computed_at_ms,
                )
            )
        else:
            breadth = float(breadth_positive_1h)
            percentile = float(ret_1h_percentile)
            relative = 2.0 * percentile - 1.0
            active = False
            direction = "NONE"
            mode = "NONE"
            score = relative
            reason = "NO_CONDITION"
            if (
                breadth >= self.config.intraday_directional_breadth_high
                and percentile >= self.config.intraday_momentum_percentile
            ):
                active = True
                direction = "LONG"
                mode = "MOMENTUM"
                reason = "BROAD_UP_AND_LEADER"
                score = abs(relative)
            elif (
                breadth <= self.config.intraday_directional_breadth_low
                and percentile <= 1.0 - self.config.intraday_momentum_percentile
            ):
                active = True
                direction = "SHORT"
                mode = "MOMENTUM"
                reason = "BROAD_DOWN_AND_LAGGARD"
                score = -abs(relative)
            elif (
                self.config.intraday_balanced_breadth_low
                <= breadth
                <= self.config.intraday_balanced_breadth_high
            ):
                if percentile >= self.config.intraday_reversal_percentile:
                    active = True
                    direction = "SHORT"
                    mode = "REVERSAL"
                    reason = "BALANCED_MARKET_UP_EXTREME"
                    score = -abs(relative)
                elif percentile <= 1.0 - self.config.intraday_reversal_percentile:
                    active = True
                    direction = "LONG"
                    mode = "REVERSAL"
                    reason = "BALANCED_MARKET_DOWN_EXTREME"
                    score = abs(relative)
            result.append(
                self._signal_row(
                    row,
                    signal_version=SIGNAL_VERSIONS[2],
                    score=score,
                    active=active,
                    direction=direction,
                    reason=reason,
                    metadata={"mode": mode, "breadth_1h": breadth},
                    computed_at_ms=computed_at_ms,
                )
            )

        return tuple(result)

    def compute_event_annotations(
        self,
        event_open_ms: int,
        *,
        computed_at_ms: int | None = None,
    ) -> tuple[dict[str, Any], ...]:
        """Calculate all three annotations for every persisted feature row."""

        self.initialize()
        target = int(event_open_ms)
        computed = int(time.time() * 1000) if computed_at_ms is None else int(computed_at_ms)
        self._feature_source_digest(target)
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT event_open_ms, symbol, feature_version,
                       ret_1h_percentile, ret_4h_percentile,
                       ret_4h, realized_vol_4h,
                       breadth_positive_1h, ret_1h
                FROM canonical_features
                WHERE event_open_ms=? AND feature_version=?
                ORDER BY symbol
                """,
                (target, self.config.feature_version),
            ).fetchall()
        if not rows:
            raise ResearchSignalError(
                f"NBOT_V342_FEATURE_ROWS_MISSING:{target}"
            )

        annotations: list[dict[str, Any]] = []
        for row in rows:
            annotations.extend(
                self._signals_for_feature_row(
                    tuple(row),
                    computed_at_ms=computed,
                )
            )
        if len(annotations) != len(rows) * len(SIGNAL_VERSIONS):
            raise ResearchSignalError(
                f"NBOT_V342_SIGNAL_ANNOTATION_COUNT_INVALID:{target}"
            )
        if any(tuple(row) != SIGNAL_ANNOTATION_FIELDS for row in annotations):
            raise ResearchSignalError("NBOT_V342_SIGNAL_FIELD_ORDER_MISMATCH")
        return tuple(annotations)

    def _persist_event(
        self,
        *,
        event_open_ms: int,
        annotations: tuple[dict[str, Any], ...],
        source_digest: str,
        signal_digest: str,
        rebuild: bool,
        built_at_ms: int,
    ) -> int:
        target = int(event_open_ms)
        placeholders = ",".join("?" for _ in SIGNAL_ANNOTATION_FIELDS)
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            feature_build = conn.execute(
                """
                SELECT feature_row_count, feature_digest
                FROM feature_builds
                WHERE event_open_ms=? AND feature_version=?
                """,
                (target, self.config.feature_version),
            ).fetchone()
            if feature_build is None:
                raise ResearchSignalError(
                    f"NBOT_V342_FEATURE_BUILD_MISSING_AT_WRITE:{target}"
                )
            actual_feature_digest = self._stored_feature_digest(conn, target)
            if actual_feature_digest != str(feature_build[1]):
                raise ResearchSignalError(
                    f"NBOT_V342_FEATURE_DIGEST_MISMATCH_AT_WRITE:{target}"
                )
            current_source_digest = _definition_hash(
                {
                    "feature_version": self.config.feature_version,
                    "feature_definition_hash": self.feature_store.definition_hash,
                    "feature_digest": actual_feature_digest,
                }
            )
            if current_source_digest != source_digest:
                raise ResearchSignalError(
                    f"NBOT_V342_SIGNAL_SOURCE_CHANGED_DURING_BUILD:{target}"
                )
            expected_annotations = int(feature_build[0]) * len(SIGNAL_VERSIONS)
            if len(annotations) != expected_annotations:
                raise ResearchSignalError(
                    f"NBOT_V342_SIGNAL_ROW_COUNT_MISMATCH:{target}:"
                    f"{len(annotations)}:{expected_annotations}"
                )

            existing = conn.execute(
                """
                SELECT 1 FROM signal_builds
                WHERE event_open_ms=? AND feature_version=?
                """,
                (target, self.config.feature_version),
            ).fetchone()
            if existing is not None and not rebuild:
                return 0
            if rebuild:
                conn.execute(
                    """
                    DELETE FROM signal_builds
                    WHERE event_open_ms=? AND feature_version=?
                    """,
                    (target, self.config.feature_version),
                )
                conn.execute(
                    """
                    DELETE FROM signal_annotations
                    WHERE event_open_ms=? AND feature_version=?
                    """,
                    (target, self.config.feature_version),
                )

            conn.executemany(
                f"""
                INSERT INTO signal_annotations({','.join(SIGNAL_ANNOTATION_FIELDS)})
                VALUES ({placeholders})
                """,
                [
                    [annotation[field] for field in SIGNAL_ANNOTATION_FIELDS]
                    for annotation in annotations
                ],
            )
            conn.execute(
                """
                INSERT INTO signal_builds(
                    event_open_ms, feature_version, built_at_ms,
                    feature_row_count, signal_annotation_count,
                    source_digest, signal_digest
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target,
                    self.config.feature_version,
                    int(built_at_ms),
                    int(feature_build[0]),
                    len(annotations),
                    source_digest,
                    signal_digest,
                ),
            )
        return len(annotations)

    def build(
        self,
        *,
        max_events: int = 1,
        rebuild: bool = False,
    ) -> SignalBuildResult:
        """Build oldest feature-backed events; never gate or mutate raw evidence."""

        limit = int(max_events)
        if limit < 0:
            raise ValueError("NBOT_V342_SIGNAL_MAX_EVENTS_INVALID")
        self.initialize()
        feature_events = self.feature_event_opens()
        with self.db.connection() as conn:
            built = {
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT event_open_ms FROM signal_builds
                    WHERE feature_version=?
                    """,
                    (self.config.feature_version,),
                )
            }
        pending = tuple(event for event in feature_events if event not in built)
        candidates = feature_events if rebuild else pending
        targets = candidates if limit == 0 else candidates[:limit]

        built_events = 0
        annotation_count = 0
        for target in targets:
            computed_at_ms = int(time.time() * 1000)
            annotations = self.compute_event_annotations(
                target,
                computed_at_ms=computed_at_ms,
            )
            source_digest = self._feature_source_digest(target)
            signal_digest = _signal_rows_digest(annotations)
            inserted = self._persist_event(
                event_open_ms=target,
                annotations=annotations,
                source_digest=source_digest,
                signal_digest=signal_digest,
                rebuild=bool(rebuild),
                built_at_ms=computed_at_ms,
            )
            if inserted:
                built_events += 1
                annotation_count += inserted

        return SignalBuildResult(
            feature_version=self.config.feature_version,
            feature_events=len(feature_events),
            pending_before=len(pending),
            attempted_events=len(targets),
            built_events=built_events,
            signal_annotations=annotation_count,
        )

    def _stored_signal_digest(self, conn, event_open_ms: int) -> str:
        fields = tuple(
            field for field in SIGNAL_ANNOTATION_FIELDS if field != "computed_at_ms"
        )
        rows = conn.execute(
            f"""
            SELECT {','.join(fields)}
            FROM signal_annotations
            WHERE event_open_ms=? AND feature_version=?
            ORDER BY symbol, signal_version
            """,
            (int(event_open_ms), self.config.feature_version),
        ).fetchall()
        return _definition_hash([list(row) for row in rows])

    def audit(self) -> dict[str, Any]:
        """Read-only signal definition, source-lineage, and output-lineage audit."""

        definitions = self.signal_definitions()
        expected_hashes = self.definition_hashes
        expected_json = {
            version: _canonical_json(definition)
            for version, definition in definitions.items()
        }
        feature_audit = self.feature_store.audit()
        with self.db.connection() as conn:
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            missing_tables = tuple(
                table for table in RESEARCH_SIGNAL_TABLES if table not in tables
            )
            if missing_tables:
                return {
                    "feature_version": self.config.feature_version,
                    "signal_versions": SIGNAL_VERSIONS,
                    "definition_hashes": expected_hashes,
                    "missing_tables": missing_tables,
                    "feature_audit_healthy": bool(feature_audit["healthy"]),
                    "signal_definition_mismatches": len(SIGNAL_VERSIONS),
                    "feature_events": 0,
                    "built_events": 0,
                    "unbuilt_events": 0,
                    "signal_annotations": 0,
                    "signal_builds_without_feature_build": 0,
                    "signal_rows_without_feature": 0,
                    "signal_rows_without_build": 0,
                    "annotation_set_mismatches": 0,
                    "annotation_count_mismatches": 0,
                    "invalid_annotation_states": 0,
                    "unexpected_signal_versions": 0,
                    "source_digest_mismatches": 0,
                    "signal_digest_mismatches": 0,
                    "healthy": False,
                }

            signal_definition_mismatches = 0
            for signal_version in SIGNAL_VERSIONS:
                stored = conn.execute(
                    """
                    SELECT feature_version, definition_hash, definition_json
                    FROM signal_sets WHERE signal_version=?
                    """,
                    (signal_version,),
                ).fetchone()
                expected = (
                    self.config.feature_version,
                    expected_hashes[signal_version],
                    expected_json[signal_version],
                )
                signal_definition_mismatches += int(stored != expected)

            feature_events = {
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT event_open_ms FROM feature_builds
                    WHERE feature_version=?
                    """,
                    (self.config.feature_version,),
                )
            }
            builds = conn.execute(
                """
                SELECT event_open_ms, feature_row_count, signal_annotation_count,
                       source_digest, signal_digest
                FROM signal_builds
                WHERE feature_version=?
                ORDER BY event_open_ms
                """,
                (self.config.feature_version,),
            ).fetchall()
            built_events = {int(row[0]) for row in builds}
            signal_annotations = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM signal_annotations
                    WHERE feature_version=?
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            signal_builds_without_feature_build = sum(
                int(int(row[0]) not in feature_events) for row in builds
            )
            signal_rows_without_feature = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM signal_annotations s
                    LEFT JOIN canonical_features f
                      ON f.event_open_ms=s.event_open_ms
                     AND f.symbol=s.symbol
                     AND f.feature_version=s.feature_version
                    WHERE s.feature_version=? AND f.symbol IS NULL
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            signal_rows_without_build = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM signal_annotations s
                    LEFT JOIN signal_builds b
                      ON b.event_open_ms=s.event_open_ms
                     AND b.feature_version=s.feature_version
                    WHERE s.feature_version=? AND b.event_open_ms IS NULL
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            expected_placeholders = ",".join("?" for _ in SIGNAL_VERSIONS)
            unexpected_signal_versions = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) FROM signal_annotations
                    WHERE feature_version=?
                      AND signal_version NOT IN ({expected_placeholders})
                    """,
                    (self.config.feature_version, *SIGNAL_VERSIONS),
                ).fetchone()[0]
            )
            annotation_set_mismatches = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM canonical_features f
                    WHERE f.feature_version=?
                      AND EXISTS (
                          SELECT 1 FROM signal_builds b
                          WHERE b.event_open_ms=f.event_open_ms
                            AND b.feature_version=f.feature_version
                      )
                      AND (
                          SELECT COUNT(*) FROM signal_annotations s
                          WHERE s.event_open_ms=f.event_open_ms
                            AND s.symbol=f.symbol
                            AND s.feature_version=f.feature_version
                            AND s.signal_version IN ({expected_placeholders})
                      ) != ?
                    """,
                    (
                        self.config.feature_version,
                        *SIGNAL_VERSIONS,
                        len(SIGNAL_VERSIONS),
                    ),
                ).fetchone()[0]
            )
            invalid_annotation_states = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM signal_annotations
                    WHERE feature_version=? AND (
                        (active=1 AND (direction NOT IN ('LONG','SHORT') OR score IS NULL)) OR
                        (active=0 AND direction!='NONE')
                    )
                    """,
                    (self.config.feature_version,),
                ).fetchone()[0]
            )

            annotation_count_mismatches = 0
            signal_digest_mismatches = 0
            for event_open_ms, expected_feature_rows, expected_annotations, _source_digest, signal_digest in builds:
                target = int(event_open_ms)
                actual_feature_rows = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM canonical_features
                        WHERE event_open_ms=? AND feature_version=?
                        """,
                        (target, self.config.feature_version),
                    ).fetchone()[0]
                )
                actual_annotations = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM signal_annotations
                        WHERE event_open_ms=? AND feature_version=?
                        """,
                        (target, self.config.feature_version),
                    ).fetchone()[0]
                )
                annotation_count_mismatches += int(
                    actual_feature_rows != int(expected_feature_rows)
                    or actual_annotations != int(expected_annotations)
                    or int(expected_annotations)
                    != int(expected_feature_rows) * len(SIGNAL_VERSIONS)
                )
                signal_digest_mismatches += int(
                    self._stored_signal_digest(conn, target) != str(signal_digest)
                )

        source_digest_mismatches = 0
        for event_open_ms, _feature_rows, _annotations, source_digest, _signal_digest in builds:
            try:
                actual_source_digest = self._feature_source_digest(int(event_open_ms))
            except ResearchSignalError:
                source_digest_mismatches += 1
            else:
                source_digest_mismatches += int(
                    actual_source_digest != str(source_digest)
                )

        counters = (
            signal_definition_mismatches,
            signal_builds_without_feature_build,
            signal_rows_without_feature,
            signal_rows_without_build,
            annotation_set_mismatches,
            annotation_count_mismatches,
            invalid_annotation_states,
            unexpected_signal_versions,
            source_digest_mismatches,
            signal_digest_mismatches,
        )
        healthy = bool(feature_audit["healthy"]) and all(
            value == 0 for value in counters
        )
        return {
            "feature_version": self.config.feature_version,
            "signal_versions": SIGNAL_VERSIONS,
            "definition_hashes": expected_hashes,
            "missing_tables": (),
            "feature_audit_healthy": bool(feature_audit["healthy"]),
            "signal_definition_mismatches": signal_definition_mismatches,
            "feature_events": len(feature_events),
            "built_events": len(built_events),
            "unbuilt_events": len(feature_events - built_events),
            "signal_annotations": signal_annotations,
            "signal_builds_without_feature_build": signal_builds_without_feature_build,
            "signal_rows_without_feature": signal_rows_without_feature,
            "signal_rows_without_build": signal_rows_without_build,
            "annotation_set_mismatches": annotation_set_mismatches,
            "annotation_count_mismatches": annotation_count_mismatches,
            "invalid_annotation_states": invalid_annotation_states,
            "unexpected_signal_versions": unexpected_signal_versions,
            "source_digest_mismatches": source_digest_mismatches,
            "signal_digest_mismatches": signal_digest_mismatches,
            "healthy": healthy,
        }
