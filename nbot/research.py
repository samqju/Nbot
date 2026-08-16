from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import ObserverConfig, ResearchConfig
from .db import EvidenceDB


FEATURE_COLUMNS = (
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

SIGNAL_VERSIONS = (
    "CSM_RANK_1H_4H_V1",
    "TSMOM_4H_VOL_ADJ_V1",
    "INTRADAY_CONDITIONAL_MOM_REV_V1",
)


@dataclass(frozen=True)
class FeatureBuildResult:
    feature_version: str
    research_ready_events: int
    pending_before: int
    attempted_events: int
    built_events: int
    feature_rows: int
    signal_annotations: int


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _definition_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _rows_digest(rows: Iterable[dict[str, Any]], fields: tuple[str, ...]) -> str:
    payload = [[row.get(field) for field in fields] for row in sorted(rows, key=lambda item: (item["symbol"], item.get("signal_version", "")))]
    return _definition_hash(payload)


def _percentiles(values: dict[str, float | None]) -> dict[str, float | None]:
    present = {symbol: float(value) for symbol, value in values.items() if value is not None}
    if not present:
        return {symbol: None for symbol in values}
    if len(present) == 1:
        only = next(iter(present))
        return {symbol: (0.5 if symbol == only else None) for symbol in values}

    ordered = sorted(present.values())
    result: dict[str, float | None] = {}
    denominator = len(ordered) - 1
    for symbol, raw in values.items():
        if raw is None:
            result[symbol] = None
            continue
        value = float(raw)
        less = sum(1 for candidate in ordered if candidate < value)
        equal = sum(1 for candidate in ordered if candidate == value)
        midrank = less + (equal - 1) / 2.0
        result[symbol] = midrank / denominator
    return result


def _return(current: float, previous: float | None) -> float | None:
    if previous is None or previous <= 0 or current <= 0:
        return None
    return current / previous - 1.0


def _realized_vol(closes: list[float] | None) -> float | None:
    if closes is None or len(closes) < 2 or any(value <= 0 for value in closes):
        return None
    returns = [math.log(closes[index] / closes[index - 1]) for index in range(1, len(closes))]
    return math.sqrt(sum(value * value for value in returns))


def _atr_pct(bars: list[tuple[float, float, float]] | None, current_close: float) -> float | None:
    # bars are (high, low, close), and 15 bars are required to produce 14 true ranges.
    if bars is None or len(bars) != 15 or current_close <= 0:
        return None
    true_ranges: list[float] = []
    for index in range(1, len(bars)):
        high, low, _close = bars[index]
        previous_close = bars[index - 1][2]
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return statistics.fmean(true_ranges) / current_close


class ResearchEngine:
    """Deterministic V2.2 feature and signal derivation from canonical raw evidence."""

    def __init__(self, observer_config: ObserverConfig, research_config: ResearchConfig, db: EvidenceDB):
        self.observer_config = observer_config
        self.config = research_config
        self.db = db
        self.interval_ms = observer_config.candle_interval_ms

    def feature_definition(self) -> dict[str, Any]:
        return {
            "feature_version": self.config.feature_version,
            "decision_clock": self.observer_config.candle_interval,
            "return_lookback_bars": list(self.config.return_lookback_bars),
            "realized_vol_1h_bars": self.config.realized_vol_1h_bars,
            "realized_vol_4h_bars": self.config.realized_vol_4h_bars,
            "atr_bars": self.config.atr_bars,
            "cross_section_percentile": "MIDRANK_0_TO_1",
            "units": {
                "returns": "DECIMAL_FRACTION",
                "realized_volatility": "DECIMAL_LOG_RETURN_MAGNITUDE",
                "atr14_frac": "DECIMAL_FRACTION_OF_CURRENT_CLOSE",
                "range_frac": "DECIMAL_FRACTION_OF_CURRENT_CLOSE",
                "spread_pct": "PERCENT",
                "funding_rate": "DECIMAL_FRACTION",
            },
            "funding_source": "POINT_IN_TIME_MARKET_SNAPSHOT_ONLY",
            "target_requirement": "EVENT_PROVENANCE_CONTEXT_COMPLETE_1",
            "history_rule": "ONLY_EVENT_OPEN_MS_LE_TARGET_EVENT",
        }

    def signal_definitions(self) -> dict[str, dict[str, Any]]:
        return {
            "CSM_RANK_1H_4H_V1": {
                "feature_version": self.config.feature_version,
                "formula": "0.4*(2*ret_1h_percentile-1)+0.6*(2*ret_4h_percentile-1)",
                "active_abs_score": self.config.csm_active_abs_score,
            },
            "TSMOM_4H_VOL_ADJ_V1": {
                "feature_version": self.config.feature_version,
                "formula": "ret_4h/realized_vol_4h",
                "active_abs_score": self.config.tsmom_active_abs_score,
            },
            "INTRADAY_CONDITIONAL_MOM_REV_V1": {
                "feature_version": self.config.feature_version,
                "directional_breadth_high": self.config.intraday_directional_breadth_high,
                "directional_breadth_low": self.config.intraday_directional_breadth_low,
                "balanced_breadth_low": self.config.intraday_balanced_breadth_low,
                "balanced_breadth_high": self.config.intraday_balanced_breadth_high,
                "momentum_percentile": self.config.intraday_momentum_percentile,
                "reversal_percentile": self.config.intraday_reversal_percentile,
            },
        }

    def initialize(self) -> None:
        self.db.initialize()
        feature_definition = self.feature_definition()
        feature_hash = _definition_hash(feature_definition)
        signal_definitions = self.signal_definitions()
        now_ms = int(time.time() * 1000)
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO feature_sets(
                    feature_version, definition_hash, definition_json, registered_at_ms
                ) VALUES (?, ?, ?, ?)
                """,
                (self.config.feature_version, feature_hash, _canonical_json(feature_definition), now_ms),
            )
            stored = conn.execute(
                "SELECT definition_hash FROM feature_sets WHERE feature_version=?",
                (self.config.feature_version,),
            ).fetchone()
            if stored is None or stored[0] != feature_hash:
                raise RuntimeError(
                    f"feature version {self.config.feature_version} already exists with a different definition"
                )

            for signal_version, definition in signal_definitions.items():
                signal_hash = _definition_hash(definition)
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
                        signal_hash,
                        _canonical_json(definition),
                        now_ms,
                    ),
                )
                row = conn.execute(
                    "SELECT definition_hash, feature_version FROM signal_sets WHERE signal_version=?",
                    (signal_version,),
                ).fetchone()
                if row is None or row[0] != signal_hash or row[1] != self.config.feature_version:
                    raise RuntimeError(f"signal version {signal_version} already exists with a different definition")

    def _eligible_events(self, conn, max_events: int, rebuild: bool) -> list[int]:
        sql = """
            SELECT p.event_open_ms
            FROM event_provenance p
            JOIN market_events e USING(event_open_ms)
            WHERE p.context_complete=1 AND e.status='COMPLETE'
        """
        params: list[Any] = []
        if not rebuild:
            sql += """
                AND NOT EXISTS (
                    SELECT 1 FROM feature_builds b
                    WHERE b.event_open_ms=p.event_open_ms AND b.feature_version=?
                )
            """
            params.append(self.config.feature_version)
        sql += " ORDER BY p.event_open_ms"
        if max_events > 0:
            sql += " LIMIT ?"
            params.append(max_events)
        return [int(row[0]) for row in conn.execute(sql, params).fetchall()]

    def _all_research_ready_count(self, conn) -> int:
        return int(
            conn.execute(
                """
                SELECT COUNT(*) FROM event_provenance p
                JOIN market_events e USING(event_open_ms)
                WHERE p.context_complete=1 AND e.status='COMPLETE'
                """
            ).fetchone()[0]
        )

    def _pending_count(self, conn) -> int:
        return int(
            conn.execute(
                """
                SELECT COUNT(*) FROM event_provenance p
                JOIN market_events e USING(event_open_ms)
                WHERE p.context_complete=1 AND e.status='COMPLETE'
                  AND NOT EXISTS (
                    SELECT 1 FROM feature_builds b
                    WHERE b.event_open_ms=p.event_open_ms AND b.feature_version=?
                  )
                """,
                (self.config.feature_version,),
            ).fetchone()[0]
        )

    def _load_history(self, conn, target_events: list[int], symbols: set[str]) -> dict[str, dict[int, tuple[float, float, float]]]:
        if not target_events or not symbols:
            return {}
        start_ms = min(target_events) - self.config.max_history_bars * self.interval_ms
        end_ms = max(target_events)
        placeholders = ",".join("?" for _ in symbols)
        params: list[Any] = [start_ms, end_ms, *sorted(symbols)]
        rows = conn.execute(
            f"""
            SELECT symbol, event_open_ms, high_price, low_price, close_price
            FROM candles_5m
            WHERE event_open_ms BETWEEN ? AND ?
              AND symbol IN ({placeholders})
            ORDER BY symbol, event_open_ms
            """,
            params,
        ).fetchall()
        history: dict[str, dict[int, tuple[float, float, float]]] = {}
        for symbol, event_open_ms, high, low, close in rows:
            history.setdefault(str(symbol), {})[int(event_open_ms)] = (float(high), float(low), float(close))
        return history

    def _base_feature(
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
        symbol_history = history.get(symbol, {})
        current = symbol_history.get(event_open_ms)
        if current is None:
            raise RuntimeError(f"research-ready event missing target candle for {symbol} at {event_open_ms}")
        current_high, current_low, current_close = current

        def prior_close(bars: int) -> float | None:
            row = symbol_history.get(event_open_ms - bars * self.interval_ms)
            return None if row is None else row[2]

        def exact_closes(bars: int) -> list[float] | None:
            result: list[float] = []
            for offset in range(bars, -1, -1):
                row = symbol_history.get(event_open_ms - offset * self.interval_ms)
                if row is None:
                    return None
                result.append(row[2])
            return result

        expected_opens = [
            event_open_ms - offset * self.interval_ms
            for offset in range(self.config.max_history_bars, -1, -1)
        ]
        available_opens = [value for value in expected_opens if value in symbol_history]
        history_bars = len(available_opens)
        source_min = min(available_opens) if available_opens else event_open_ms

        atr_source: list[tuple[float, float, float]] | None = []
        for offset in range(self.config.atr_bars, -1, -1):
            row = symbol_history.get(event_open_ms - offset * self.interval_ms)
            if row is None:
                atr_source = None
                break
            atr_source.append(row)

        minutes_to_next = None
        if next_funding_time_ms is not None:
            minutes_to_next = (int(next_funding_time_ms) - event_close_ms) / 60_000.0

        result = {
            "event_open_ms": event_open_ms,
            "symbol": symbol,
            "feature_version": self.config.feature_version,
            "computed_at_ms": computed_at_ms,
            "source_min_event_open_ms": source_min,
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
            "atr14_frac": _atr_pct(atr_source, current_close),
            "range_frac": None if current_close <= 0 else (current_high - current_low) / current_close,
            "quote_volume_24h_usd": float(quote_volume_24h_usd),
            "spread_pct": float(spread_pct),
            "funding_rate": None if funding_rate is None else float(funding_rate),
            "minutes_to_next_funding": minutes_to_next,
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
        return result

    def _complete_event_features(self, rows: list[dict[str, Any]], event_close_ms: int) -> None:
        liquidity = _percentiles({row["symbol"]: row["quote_volume_24h_usd"] for row in rows})
        ret_1h = _percentiles({row["symbol"]: row["ret_1h"] for row in rows})
        ret_4h = _percentiles({row["symbol"]: row["ret_4h"] for row in rows})
        volatility = _percentiles({row["symbol"]: row["realized_vol_1h"] for row in rows})

        by_symbol = {row["symbol"]: row for row in rows}
        btc = by_symbol.get("BTCUSDT")
        btc_ret_5m = None if btc is None else btc["ret_5m"]
        btc_ret_1h = None if btc is None else btc["ret_1h"]
        btc_ret_4h = None if btc is None else btc["ret_4h"]

        returns_5m = [row["ret_5m"] for row in rows if row["ret_5m"] is not None]
        returns_1h = [row["ret_1h"] for row in rows if row["ret_1h"] is not None]
        breadth_5m = None if not returns_5m else sum(value > 0 for value in returns_5m) / len(returns_5m)
        breadth_1h = None if not returns_1h else sum(value > 0 for value in returns_1h) / len(returns_1h)
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

    @staticmethod
    def _signal_row(
        row: dict[str, Any], signal_version: str, score: float | None,
        active: bool, direction: str, reason: str, metadata: dict[str, Any], computed_at_ms: int,
    ) -> dict[str, Any]:
        return {
            "event_open_ms": row["event_open_ms"],
            "symbol": row["symbol"],
            "feature_version": row["feature_version"],
            "signal_version": signal_version,
            "computed_at_ms": computed_at_ms,
            "score": score,
            "active": int(active),
            "direction": direction,
            "reason": reason,
            "metadata_json": _canonical_json(metadata),
        }

    def _signals_for_row(self, row: dict[str, Any], computed_at_ms: int) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []

        p1h = row["ret_1h_percentile"]
        p4h = row["ret_4h_percentile"]
        if p1h is None or p4h is None:
            signals.append(self._signal_row(row, SIGNAL_VERSIONS[0], None, False, "NONE", "INSUFFICIENT_HISTORY", {}, computed_at_ms))
        else:
            score = 0.4 * (2.0 * p1h - 1.0) + 0.6 * (2.0 * p4h - 1.0)
            active = abs(score) >= self.config.csm_active_abs_score
            direction = "LONG" if active and score > 0 else "SHORT" if active and score < 0 else "NONE"
            signals.append(self._signal_row(row, SIGNAL_VERSIONS[0], score, active, direction, "EXTREME_RANK" if active else "MIDDLE_RANK", {}, computed_at_ms))

        ret_4h = row["ret_4h"]
        vol_4h = row["realized_vol_4h"]
        if ret_4h is None or vol_4h is None or vol_4h <= 0:
            signals.append(self._signal_row(row, SIGNAL_VERSIONS[1], None, False, "NONE", "INSUFFICIENT_HISTORY", {}, computed_at_ms))
        else:
            score = ret_4h / vol_4h
            active = abs(score) >= self.config.tsmom_active_abs_score
            direction = "LONG" if active and score > 0 else "SHORT" if active and score < 0 else "NONE"
            signals.append(self._signal_row(row, SIGNAL_VERSIONS[1], score, active, direction, "VOL_ADJUSTED_TREND" if active else "WEAK_TREND", {}, computed_at_ms))

        breadth = row["breadth_positive_1h"]
        percentile = row["ret_1h_percentile"]
        if breadth is None or percentile is None or row["ret_1h"] is None:
            signals.append(self._signal_row(row, SIGNAL_VERSIONS[2], None, False, "NONE", "INSUFFICIENT_HISTORY", {"mode": "NONE"}, computed_at_ms))
        else:
            relative = 2.0 * percentile - 1.0
            active = False
            direction = "NONE"
            mode = "NONE"
            score = relative
            reason = "NO_CONDITION"
            if breadth >= self.config.intraday_directional_breadth_high and percentile >= self.config.intraday_momentum_percentile:
                active, direction, mode, reason = True, "LONG", "MOMENTUM", "BROAD_UP_AND_LEADER"
                score = abs(relative)
            elif breadth <= self.config.intraday_directional_breadth_low and percentile <= 1.0 - self.config.intraday_momentum_percentile:
                active, direction, mode, reason = True, "SHORT", "MOMENTUM", "BROAD_DOWN_AND_LAGGARD"
                score = -abs(relative)
            elif self.config.intraday_balanced_breadth_low <= breadth <= self.config.intraday_balanced_breadth_high:
                if percentile >= self.config.intraday_reversal_percentile:
                    active, direction, mode, reason = True, "SHORT", "REVERSAL", "BALANCED_MARKET_UP_EXTREME"
                    score = -abs(relative)
                elif percentile <= 1.0 - self.config.intraday_reversal_percentile:
                    active, direction, mode, reason = True, "LONG", "REVERSAL", "BALANCED_MARKET_DOWN_EXTREME"
                    score = abs(relative)
            signals.append(self._signal_row(row, SIGNAL_VERSIONS[2], score, active, direction, reason, {"mode": mode, "breadth_1h": breadth}, computed_at_ms))

        return signals

    def _insert_event(self, conn, event_open_ms: int, feature_rows: list[dict[str, Any]], signals: list[dict[str, Any]], rebuild: bool) -> tuple[int, int]:
        if rebuild:
            conn.execute(
                "DELETE FROM feature_builds WHERE event_open_ms=? AND feature_version=?",
                (event_open_ms, self.config.feature_version),
            )
            conn.execute(
                "DELETE FROM canonical_features WHERE event_open_ms=? AND feature_version=?",
                (event_open_ms, self.config.feature_version),
            )

        placeholders = ",".join("?" for _ in FEATURE_COLUMNS)
        conn.executemany(
            f"INSERT INTO canonical_features({','.join(FEATURE_COLUMNS)}) VALUES ({placeholders})",
            [[row[column] for column in FEATURE_COLUMNS] for row in feature_rows],
        )
        signal_fields = (
            "event_open_ms", "symbol", "feature_version", "signal_version", "computed_at_ms",
            "score", "active", "direction", "reason", "metadata_json",
        )
        conn.executemany(
            f"INSERT INTO signal_annotations({','.join(signal_fields)}) VALUES ({','.join('?' for _ in signal_fields)})",
            [[row[field] for field in signal_fields] for row in signals],
        )

        feature_digest_fields = tuple(column for column in FEATURE_COLUMNS if column != "computed_at_ms")
        signal_digest_fields = tuple(field for field in signal_fields if field != "computed_at_ms")
        feature_digest = _rows_digest(feature_rows, feature_digest_fields)
        signal_digest = _rows_digest(signals, signal_digest_fields)
        conn.execute(
            """
            INSERT INTO feature_builds(
                event_open_ms, feature_version, built_at_ms,
                feature_row_count, feature_digest, signal_annotation_count, signal_digest
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_open_ms,
                self.config.feature_version,
                int(time.time() * 1000),
                len(feature_rows),
                feature_digest,
                len(signals),
                signal_digest,
            ),
        )
        return len(feature_rows), len(signals)

    def build(self, *, max_events: int | None = None, rebuild: bool = False) -> FeatureBuildResult:
        self.initialize()
        limit = self.config.max_events_per_build if max_events is None else int(max_events)
        if limit < 0:
            raise ValueError("max_events must be >= 0")

        with self.db.connection() as conn:
            eligible_count = self._all_research_ready_count(conn)
            pending_before = self._pending_count(conn)
            target_events = self._eligible_events(conn, limit, rebuild)
            if not target_events:
                return FeatureBuildResult(self.config.feature_version, eligible_count, pending_before, 0, 0, 0, 0)

            placeholders = ",".join("?" for _ in target_events)
            snapshot_rows = conn.execute(
                f"""
                SELECT s.event_open_ms, s.symbol, s.universe_rank, s.quote_volume_24h_usd,
                       s.spread_pct, s.funding_rate, s.next_funding_time_ms, s.captured_at_ms
                FROM market_snapshots s
                JOIN event_provenance p USING(event_open_ms)
                WHERE s.event_open_ms IN ({placeholders}) AND p.context_complete=1
                ORDER BY s.event_open_ms, s.symbol
                """,
                target_events,
            ).fetchall()
            symbols = {str(row[1]) for row in snapshot_rows}
            symbols.add("BTCUSDT")
            history = self._load_history(conn, target_events, symbols)
            event_close = {
                int(row[0]): int(row[1])
                for row in conn.execute(
                    f"SELECT event_open_ms, event_close_ms FROM market_events WHERE event_open_ms IN ({placeholders})",
                    target_events,
                ).fetchall()
            }

        snapshots_by_event: dict[int, list[tuple[Any, ...]]] = {}
        for row in snapshot_rows:
            snapshots_by_event.setdefault(int(row[0]), []).append(tuple(row[1:]))

        built_events = 0
        feature_count = 0
        signal_count = 0
        for event_open_ms in target_events:
            computed_at_ms = int(time.time() * 1000)
            snapshots = snapshots_by_event.get(event_open_ms, [])
            rows = [
                self._base_feature(
                    event_open_ms=event_open_ms,
                    event_close_ms=event_close[event_open_ms],
                    snapshot=snapshot,
                    history=history,
                    computed_at_ms=computed_at_ms,
                )
                for snapshot in snapshots
            ]
            self._complete_event_features(rows, event_close[event_open_ms])
            signals = [signal for row in rows for signal in self._signals_for_row(row, computed_at_ms)]

            with self.db.connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                expected = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM market_snapshots WHERE event_open_ms=?",
                        (event_open_ms,),
                    ).fetchone()[0]
                )
                if expected != len(rows):
                    raise RuntimeError(
                        f"feature row count {len(rows)} does not match raw snapshot count {expected} for {event_open_ms}"
                    )
                if len(signals) != len(rows) * len(SIGNAL_VERSIONS):
                    raise RuntimeError("every feature row must receive every frozen signal annotation")
                row_features, row_signals = self._insert_event(conn, event_open_ms, rows, signals, rebuild)
            built_events += 1
            feature_count += row_features
            signal_count += row_signals

        return FeatureBuildResult(
            self.config.feature_version,
            eligible_count,
            pending_before,
            len(target_events),
            built_events,
            feature_count,
            signal_count,
        )

    def status(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            research_ready_events = self._all_research_ready_count(conn)
            built_events = int(conn.execute(
                "SELECT COUNT(*) FROM feature_builds WHERE feature_version=?",
                (self.config.feature_version,),
            ).fetchone()[0])
            feature_rows = int(conn.execute(
                "SELECT COUNT(*) FROM canonical_features WHERE feature_version=?",
                (self.config.feature_version,),
            ).fetchone()[0])
            full_history_rows = int(conn.execute(
                "SELECT COUNT(*) FROM canonical_features WHERE feature_version=? AND full_history_4h=1",
                (self.config.feature_version,),
            ).fetchone()[0])
            annotations = int(conn.execute(
                "SELECT COUNT(*) FROM signal_annotations WHERE feature_version=?",
                (self.config.feature_version,),
            ).fetchone()[0])
            active = int(conn.execute(
                "SELECT COUNT(*) FROM signal_annotations WHERE feature_version=? AND active=1",
                (self.config.feature_version,),
            ).fetchone()[0])
            no_active = int(conn.execute(
                """
                SELECT COUNT(*) FROM canonical_features f
                WHERE f.feature_version=? AND NOT EXISTS (
                    SELECT 1 FROM signal_annotations s
                    WHERE s.event_open_ms=f.event_open_ms AND s.symbol=f.symbol
                      AND s.feature_version=f.feature_version AND s.active=1
                )
                """,
                (self.config.feature_version,),
            ).fetchone()[0])
            latest = conn.execute(
                """
                SELECT event_open_ms, feature_row_count, signal_annotation_count,
                       feature_digest, signal_digest
                FROM feature_builds WHERE feature_version=?
                ORDER BY event_open_ms DESC LIMIT 1
                """,
                (self.config.feature_version,),
            ).fetchone()
            signal_counts = {
                row[0]: {"rows": int(row[1]), "active": int(row[2])}
                for row in conn.execute(
                    """
                    SELECT signal_version, COUNT(*), SUM(active)
                    FROM signal_annotations WHERE feature_version=?
                    GROUP BY signal_version ORDER BY signal_version
                    """,
                    (self.config.feature_version,),
                ).fetchall()
            }
        return {
            "feature_version": self.config.feature_version,
            "research_ready_events": research_ready_events,
            "built_events": built_events,
            "unbuilt_events": research_ready_events - built_events,
            "feature_rows": feature_rows,
            "full_history_4h_rows": full_history_rows,
            "signal_annotations": annotations,
            "active_signal_annotations": active,
            "feature_rows_with_no_active_signal": no_active,
            "signal_counts": signal_counts,
            "latest_build": latest,
        }

    def _stored_feature_digest(self, conn, event_open_ms: int) -> str:
        fields = tuple(column for column in FEATURE_COLUMNS if column != "computed_at_ms")
        rows = conn.execute(
            f"SELECT {','.join(fields)} FROM canonical_features WHERE event_open_ms=? AND feature_version=? ORDER BY symbol",
            (event_open_ms, self.config.feature_version),
        ).fetchall()
        dict_rows = [dict(zip(fields, row)) for row in rows]
        return _rows_digest(dict_rows, fields)

    def _stored_signal_digest(self, conn, event_open_ms: int) -> str:
        fields = (
            "event_open_ms", "symbol", "feature_version", "signal_version",
            "score", "active", "direction", "reason", "metadata_json",
        )
        rows = conn.execute(
            f"SELECT {','.join(fields)} FROM signal_annotations WHERE event_open_ms=? AND feature_version=? ORDER BY symbol, signal_version",
            (event_open_ms, self.config.feature_version),
        ).fetchall()
        dict_rows = [dict(zip(fields, row)) for row in rows]
        return _rows_digest(dict_rows, fields)

    def audit(self) -> dict[str, Any]:
        self.initialize()
        feature_hash = _definition_hash(self.feature_definition())
        signal_hashes = {version: _definition_hash(definition) for version, definition in self.signal_definitions().items()}
        with self.db.connection() as conn:
            ready = self._all_research_ready_count(conn)
            built = int(conn.execute(
                "SELECT COUNT(*) FROM feature_builds WHERE feature_version=?", (self.config.feature_version,)
            ).fetchone()[0])
            feature_rows = int(conn.execute(
                "SELECT COUNT(*) FROM canonical_features WHERE feature_version=?", (self.config.feature_version,)
            ).fetchone()[0])
            raw_snapshots = int(conn.execute("SELECT COUNT(*) FROM market_snapshots").fetchone()[0])
            feature_set_row = conn.execute(
                "SELECT definition_hash FROM feature_sets WHERE feature_version=?", (self.config.feature_version,)
            ).fetchone()
            feature_definition_mismatch = int(feature_set_row is None or feature_set_row[0] != feature_hash)
            signal_definition_mismatches = 0
            for version, expected_hash in signal_hashes.items():
                row = conn.execute(
                    "SELECT definition_hash, feature_version FROM signal_sets WHERE signal_version=?", (version,)
                ).fetchone()
                signal_definition_mismatches += int(
                    row is None or row[0] != expected_hash or row[1] != self.config.feature_version
                )

            context_incomplete_feature_rows = int(conn.execute(
                """
                SELECT COUNT(*) FROM canonical_features f
                JOIN event_provenance p USING(event_open_ms)
                WHERE f.feature_version=? AND p.context_complete!=1
                """, (self.config.feature_version,)
            ).fetchone()[0])
            feature_rows_without_snapshot = int(conn.execute(
                """
                SELECT COUNT(*) FROM canonical_features f
                LEFT JOIN market_snapshots s
                  ON s.event_open_ms=f.event_open_ms AND s.symbol=f.symbol
                WHERE f.feature_version=? AND s.symbol IS NULL
                """, (self.config.feature_version,)
            ).fetchone()[0])
            future_source_rows = int(conn.execute(
                """
                SELECT COUNT(*) FROM canonical_features
                WHERE feature_version=? AND (
                    source_max_event_open_ms > event_open_ms OR
                    source_min_event_open_ms > source_max_event_open_ms
                )
                """, (self.config.feature_version,)
            ).fetchone()[0])
            invalid_percentiles = int(conn.execute(
                """
                SELECT COUNT(*) FROM canonical_features WHERE feature_version=? AND (
                    (liquidity_percentile IS NOT NULL AND (liquidity_percentile < 0 OR liquidity_percentile > 1)) OR
                    (ret_1h_percentile IS NOT NULL AND (ret_1h_percentile < 0 OR ret_1h_percentile > 1)) OR
                    (ret_4h_percentile IS NOT NULL AND (ret_4h_percentile < 0 OR ret_4h_percentile > 1)) OR
                    (volatility_percentile IS NOT NULL AND (volatility_percentile < 0 OR volatility_percentile > 1))
                )
                """, (self.config.feature_version,)
            ).fetchone()[0])
            feature_row_count_mismatches = int(conn.execute(
                """
                SELECT COUNT(*) FROM feature_builds b
                WHERE b.feature_version=? AND b.feature_row_count != (
                    SELECT COUNT(*) FROM market_snapshots s WHERE s.event_open_ms=b.event_open_ms
                )
                """, (self.config.feature_version,)
            ).fetchone()[0])
            signal_rows_without_feature = int(conn.execute(
                """
                SELECT COUNT(*) FROM signal_annotations s
                LEFT JOIN canonical_features f
                  ON f.event_open_ms=s.event_open_ms AND f.symbol=s.symbol
                 AND f.feature_version=s.feature_version
                WHERE s.feature_version=? AND f.symbol IS NULL
                """, (self.config.feature_version,)
            ).fetchone()[0])
            annotation_count_mismatches = int(conn.execute(
                """
                SELECT COUNT(*) FROM canonical_features f
                WHERE f.feature_version=? AND (
                    SELECT COUNT(*) FROM signal_annotations s
                    WHERE s.event_open_ms=f.event_open_ms AND s.symbol=f.symbol
                      AND s.feature_version=f.feature_version
                ) != ?
                """, (self.config.feature_version, len(SIGNAL_VERSIONS))
            ).fetchone()[0])
            invalid_active_signals = int(conn.execute(
                """
                SELECT COUNT(*) FROM signal_annotations
                WHERE feature_version=? AND (
                    (active=1 AND (direction NOT IN ('LONG','SHORT') OR score IS NULL)) OR
                    (active=0 AND direction!='NONE')
                )
                """, (self.config.feature_version,)
            ).fetchone()[0])

            digest_mismatches = 0
            builds = conn.execute(
                "SELECT event_open_ms, feature_digest, signal_digest FROM feature_builds WHERE feature_version=? ORDER BY event_open_ms",
                (self.config.feature_version,),
            ).fetchall()
            for event_open_ms, feature_digest, signal_digest in builds:
                digest_mismatches += int(self._stored_feature_digest(conn, int(event_open_ms)) != feature_digest)
                digest_mismatches += int(self._stored_signal_digest(conn, int(event_open_ms)) != signal_digest)

        return {
            "feature_version": self.config.feature_version,
            "research_ready_events": ready,
            "built_events": built,
            "unbuilt_events": ready - built,
            "raw_snapshots": raw_snapshots,
            "feature_rows": feature_rows,
            "feature_definition_mismatch": feature_definition_mismatch,
            "signal_definition_mismatches": signal_definition_mismatches,
            "context_incomplete_feature_rows": context_incomplete_feature_rows,
            "feature_rows_without_snapshot": feature_rows_without_snapshot,
            "future_source_rows": future_source_rows,
            "invalid_percentiles": invalid_percentiles,
            "feature_row_count_mismatches": feature_row_count_mismatches,
            "signal_rows_without_feature": signal_rows_without_feature,
            "annotation_count_mismatches": annotation_count_mismatches,
            "invalid_active_signals": invalid_active_signals,
            "digest_mismatches": digest_mismatches,
        }
