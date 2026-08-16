from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from .binance import BinancePublicClient, Candle, latest_closed_open_time_ms, validate_candle
from .config import ObserverConfig, OutcomeConfig
from .db import EvidenceDB


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


@dataclass(frozen=True)
class OutcomeBuildResult:
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
        for row in sorted(rows, key=lambda item: (int(item["event_open_ms"]), str(item["symbol"])))
    ]
    return _definition_hash(payload)



def _candle_source_digest(path: list[Candle]) -> str:
    payload = [
        [
            candle.open_time_ms, candle.close_time_ms, candle.open_price, candle.high_price,
            candle.low_price, candle.close_price, candle.base_volume, candle.quote_volume,
            candle.trade_count, candle.taker_buy_base_volume, candle.taker_buy_quote_volume,
        ]
        for candle in path
    ]
    return _definition_hash(payload)


def _future_realized_vol(entry_price: float, closes: list[float]) -> float:
    values = [entry_price, *closes]
    returns = [math.log(values[index] / values[index - 1]) for index in range(1, len(values))]
    return math.sqrt(sum(value * value for value in returns))


def _funding_range_covered(conn, start_ms: int, end_ms: int) -> bool:
    if end_ms < start_ms:
        return True
    ranges = conn.execute(
        "SELECT start_ms, end_ms FROM funding_sync_ranges "
        "WHERE end_ms >= ? AND start_ms <= ? ORDER BY start_ms",
        (start_ms, end_ms),
    ).fetchall()
    cursor = start_ms
    for raw_start, raw_end in ranges:
        left = max(start_ms, int(raw_start))
        right = min(end_ms, int(raw_end))
        if right < cursor:
            continue
        if left > cursor:
            return False
        cursor = max(cursor, right + 1)
        if cursor > end_ms:
            return True
    return cursor > end_ms


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
            elif adverse_bar is None or (favorable_bar is not None and favorable_bar < adverse_bar):
                first = "FAVORABLE_FIRST"
            elif favorable_bar is None or adverse_bar < favorable_bar:
                first = "ADVERSE_FIRST"
            else:
                first = "AMBIGUOUS_SAME_CANDLE"

            side_rows[f"{multiple:g}R"] = {
                "first": first,
                "favorable_bar": favorable_bar,
                "adverse_bar": adverse_bar,
                "favorable_minute": None if favorable_bar is None else favorable_bar * interval_minutes,
                "adverse_minute": None if adverse_bar is None else adverse_bar * interval_minutes,
            }
        result["sides"][side] = side_rows
    return result


def _continuation(path: list[Candle], horizons: tuple[tuple[str, int], ...]) -> dict[str, Any]:
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


class FuturePathEngine:
    """V2.3 labels: what happened after a V2.2 decision-time feature row."""

    def __init__(
        self,
        observer_config: ObserverConfig,
        outcome_config: OutcomeConfig,
        db: EvidenceDB,
        client: BinancePublicClient | Any,
    ):
        self.observer_config = observer_config
        self.config = outcome_config
        self.db = db
        self.client = client
        self.interval_ms = observer_config.candle_interval_ms
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
                "roundtrip_base": "2*taker_fee + entry_slippage + exit_slippage + decision_time_spread",
                "long_net": "gross_long - roundtrip_base - funding_rate_sum_crossed",
                "short_net": "gross_short - roundtrip_base + funding_rate_sum_crossed",
                "exit_spread": "DECISION_TIME_SPREAD_PROXY_NOT_HISTORICAL_EXIT_BOOK",
            },
            "future_candle_sources": ["CANONICAL_CANDLES_5M", "BINANCE_HISTORICAL_KLINE_LABEL_CACHE"],
            "lookahead_boundary": "FUTURE_PATH_TABLES_ARE_LABEL_ONLY_AND_NEVER_QUERIED_BY_V2_2_FEATURES",
        }

    def initialize(self) -> None:
        self.db.initialize()
        definition = self.definition()
        digest = _definition_hash(definition)
        now_ms = int(time.time() * 1000)
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO future_path_sets(
                    outcome_version, feature_version, definition_hash, definition_json, registered_at_ms
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    self.config.outcome_version,
                    self.config.feature_version,
                    digest,
                    _canonical_json(definition),
                    now_ms,
                ),
            )
            row = conn.execute(
                "SELECT definition_hash, feature_version FROM future_path_sets WHERE outcome_version=?",
                (self.config.outcome_version,),
            ).fetchone()
            if row is None or row[0] != digest or row[1] != self.config.feature_version:
                raise RuntimeError(
                    f"outcome version {self.config.outcome_version} already exists with a different definition"
                )

    def _event_counts(self, conn, latest_closed_open_ms: int) -> tuple[int, int, int, int]:
        feature_events = int(
            conn.execute(
                "SELECT COUNT(DISTINCT event_open_ms) FROM canonical_features WHERE feature_version=?",
                (self.config.feature_version,),
            ).fetchone()[0]
        )
        maturity_cutoff = latest_closed_open_ms - self.config.max_horizon_bars * self.interval_ms
        mature_events = int(
            conn.execute(
                "SELECT COUNT(DISTINCT event_open_ms) FROM canonical_features "
                "WHERE feature_version=? AND event_open_ms<=?",
                (self.config.feature_version, maturity_cutoff),
            ).fetchone()[0]
        )
        built = int(
            conn.execute(
                "SELECT COUNT(*) FROM future_path_builds WHERE outcome_version=?",
                (self.config.outcome_version,),
            ).fetchone()[0]
        )
        pending_build = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT f.event_open_ms
                    FROM canonical_features f
                    WHERE f.feature_version=? AND f.event_open_ms<=?
                      AND NOT EXISTS (
                          SELECT 1 FROM future_path_builds b
                          WHERE b.event_open_ms=f.event_open_ms AND b.outcome_version=?
                      )
                )
                """,
                (self.config.feature_version, maturity_cutoff, self.config.outcome_version),
            ).fetchone()[0]
        )
        return feature_events, mature_events, built, pending_build

    def _eligible_events(self, conn, latest_closed_open_ms: int, max_events: int, rebuild: bool) -> list[int]:
        maturity_cutoff = latest_closed_open_ms - self.config.max_horizon_bars * self.interval_ms
        sql = """
            SELECT DISTINCT f.event_open_ms
            FROM canonical_features f
            WHERE f.feature_version=? AND f.event_open_ms<=?
        """
        params: list[Any] = [self.config.feature_version, maturity_cutoff]
        if not rebuild:
            sql += """
                AND NOT EXISTS (
                    SELECT 1 FROM future_path_builds b
                    WHERE b.event_open_ms=f.event_open_ms AND b.outcome_version=?
                )
            """
            params.append(self.config.outcome_version)
        sql += " ORDER BY f.event_open_ms"
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
            SELECT event_open_ms, open_time_ms, close_time_ms, open_price, high_price, low_price,
                   close_price, base_volume, quote_volume, trade_count,
                   taker_buy_base_volume, taker_buy_quote_volume
            FROM candles_5m
            WHERE symbol=? AND event_open_ms BETWEEN ? AND ?
            """,
            (symbol, start_open, end_open),
        ).fetchall()
        cached_rows = conn.execute(
            """
            SELECT event_open_ms, open_time_ms, close_time_ms, open_price, high_price, low_price,
                   close_price, base_volume, quote_volume, trade_count,
                   taker_buy_base_volume, taker_buy_quote_volume
            FROM future_candle_cache
            WHERE symbol=? AND event_open_ms BETWEEN ? AND ?
            """,
            (symbol, start_open, end_open),
        ).fetchall()

        def parse(row: tuple[Any, ...]) -> tuple[int, Candle]:
            open_key = int(row[0])
            candle = Candle(
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
            validate_candle(candle, self.interval_ms)
            return open_key, candle

        result: dict[int, Candle] = {}
        fallback_opens: set[int] = set()
        for row in cached_rows:
            open_key, candle = parse(row)
            result[open_key] = candle
            fallback_opens.add(open_key)
        for row in canonical_rows:
            open_key, candle = parse(row)
            result[open_key] = candle
            fallback_opens.discard(open_key)
        return result, fallback_opens

    def _cache_missing_candles(
        self,
        event_open_ms: int,
        symbols: list[str],
        missing_by_symbol: dict[str, list[int]],
    ) -> tuple[int, dict[str, str]]:
        if not missing_by_symbol:
            return 0, {}
        fetched: dict[str, dict[int, Candle]] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=self.observer_config.candle_fetch_workers) as pool:
            futures = {
                pool.submit(
                    self.client.historical_candles,
                    symbol,
                    min(opens),
                    max(opens),
                ): (symbol, set(opens))
                for symbol, opens in missing_by_symbol.items()
            }
            for future in as_completed(futures):
                symbol, required = futures[future]
                try:
                    rows = future.result()
                    missing = required.difference(rows)
                    if missing:
                        raise RuntimeError(f"missing {len(missing)} required future candles")
                    fetched[symbol] = {open_ms: rows[open_ms] for open_ms in required}
                except Exception as exc:
                    errors[symbol] = f"{type(exc).__name__}: {exc}"

        if errors:
            return 0, errors

        ingested_at_ms = int(time.time() * 1000)
        count = 0
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for symbol in symbols:
                for open_ms, candle in sorted(fetched.get(symbol, {}).items()):
                    validate_candle(candle, self.interval_ms)
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO future_candle_cache(
                            symbol, event_open_ms, open_time_ms, close_time_ms,
                            open_price, high_price, low_price, close_price,
                            base_volume, quote_volume, trade_count,
                            taker_buy_base_volume, taker_buy_quote_volume,
                            source, ingested_at_ms
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BINANCE_HISTORICAL_KLINE', ?)
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
                    count += 1
        return count, {}

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
        forward_returns: dict[str, float] = {
            label: closes[bars - 1] / entry_price - 1.0
            for label, bars in HORIZON_LABELS
        }

        max_high = max(row.high_price for row in path)
        min_low = min(row.low_price for row in path)
        high_bar = next(index for index, row in enumerate(path, start=1) if row.high_price == max_high)
        low_bar = next(index for index, row in enumerate(path, start=1) if row.low_price == min_low)
        long_mfe = max(0.0, max_high / entry_price - 1.0)
        long_mae = max(0.0, 1.0 - min_low / entry_price)
        short_mfe = max(0.0, 1.0 - min_low / entry_price)
        short_mae = max(0.0, max_high / entry_price - 1.0)

        source_candle_digest = _candle_source_digest(path)

        barrier_hits = _barrier_hits(
            entry_price=entry_price,
            risk_unit_frac=risk_unit_frac,
            path=path,
            barriers=self.config.barrier_r_multiples,
            interval_minutes=self.interval_minutes,
        )
        continuation = _continuation(path, HORIZON_LABELS)

        funding_payload = [
            {"funding_time_ms": int(ts), "funding_rate": float(rate), "mark_price": mark}
            for ts, rate, mark in funding_events
        ]
        total_funding = float(sum(float(rate) for _ts, rate, _mark in funding_events))
        funding_source_digest = _definition_hash(funding_payload)
        roundtrip_base = (
            2.0 * self.observer_config.taker_fee_rate
            + (self.observer_config.entry_slippage_bps + self.observer_config.exit_slippage_bps) / 10_000.0
            + spread_pct / 100.0
        )

        net_long: dict[str, float] = {}
        net_short: dict[str, float] = {}
        for label, bars in HORIZON_LABELS:
            horizon_close_ms = event_open_ms + (bars + 1) * self.interval_ms - 1
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
            "source_max_event_open_ms": event_open_ms + self.config.max_horizon_bars * self.interval_ms,
            "future_candle_count": len(path),
            "fallback_candle_count": len(fallback_opens),
            "source_candle_digest": source_candle_digest,
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
        row["path_digest"] = _definition_hash([row[field] for field in PATH_DIGEST_FIELDS])
        return row

    def _insert_event(self, event_open_ms: int, rows: list[dict[str, Any]], rebuild: bool) -> None:
        event_digest = _rows_digest(rows, ("event_open_ms", "symbol", "path_digest"))
        fallback_count = sum(int(row["fallback_candle_count"]) for row in rows)
        with self.db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if rebuild:
                conn.execute(
                    "DELETE FROM future_path_builds WHERE event_open_ms=? AND outcome_version=?",
                    (event_open_ms, self.config.outcome_version),
                )
                conn.execute(
                    "DELETE FROM future_paths WHERE event_open_ms=? AND outcome_version=?",
                    (event_open_ms, self.config.outcome_version),
                )
            placeholders = ",".join("?" for _ in PATH_COLUMNS)
            conn.executemany(
                f"INSERT INTO future_paths({','.join(PATH_COLUMNS)}) VALUES ({placeholders})",
                [[row[column] for column in PATH_COLUMNS] for row in rows],
            )
            conn.execute(
                """
                INSERT INTO future_path_builds(
                    event_open_ms, outcome_version, built_at_ms,
                    path_row_count, path_digest, fallback_candle_count
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_open_ms,
                    self.config.outcome_version,
                    int(time.time() * 1000),
                    len(rows),
                    event_digest,
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
                    int(time.time() * 1000),
                    self.config.outcome_version,
                    len(rows),
                    len(rows),
                ),
            )

    def build(self, *, max_events: int | None = None, rebuild: bool = False) -> OutcomeBuildResult:
        self.initialize()
        limit = self.config.max_events_per_build if max_events is None else int(max_events)
        if limit < 0:
            raise ValueError("max_events must be >= 0")

        server_time_ms = int(self.client.server_time_ms())
        latest_closed = latest_closed_open_time_ms(server_time_ms, self.interval_ms)
        with self.db.connection() as conn:
            feature_events, mature_events, _built_count, pending_build = self._event_counts(conn, latest_closed)
            target_events = self._eligible_events(conn, latest_closed, limit, rebuild)
        pending_maturity = feature_events - mature_events

        attempted = 0
        built = 0
        path_rows_total = 0
        fallback_fetched_total = 0
        funding_incomplete = 0
        path_incomplete = 0

        needed_offsets = tuple(range(1, self.config.max_horizon_bars + 1))
        for event_open_ms in target_events:
            attempted += 1
            with self.db.connection() as conn:
                features = self._load_features(conn, event_open_ms)
                event_close_ms = int(
                    conn.execute(
                        "SELECT event_close_ms FROM market_events WHERE event_open_ms=?",
                        (event_open_ms,),
                    ).fetchone()[0]
                )
                max_horizon_close_ms = event_open_ms + (self.config.max_horizon_bars + 1) * self.interval_ms - 1
                if not _funding_range_covered(conn, event_close_ms + 1, max_horizon_close_ms):
                    funding_incomplete += 1
                    self._record_attempt(
                        event_open_ms=event_open_ms,
                        result="FUNDING_INCOMPLETE",
                        expected_symbols=len(features),
                        completed_symbols=0,
                        missing_candles=0,
                        detail="sync-funding must cover the complete 4h label window",
                    )
                    continue

            symbols = [str(row[0]) for row in features]
            missing_by_symbol: dict[str, list[int]] = {}
            for symbol in symbols:
                with self.db.connection() as conn:
                    existing, _fallback = self._load_path_candles(conn, symbol, event_open_ms)
                required = [event_open_ms + offset * self.interval_ms for offset in needed_offsets]
                missing = [open_ms for open_ms in required if open_ms not in existing]
                if missing:
                    missing_by_symbol[symbol] = missing

            fetched_count, fetch_errors = self._cache_missing_candles(event_open_ms, symbols, missing_by_symbol)
            fallback_fetched_total += fetched_count
            if fetch_errors:
                missing_total = sum(len(values) for values in missing_by_symbol.values())
                path_incomplete += 1
                detail = "; ".join(f"{symbol}={error}" for symbol, error in sorted(fetch_errors.items())[:10])
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
                for symbol, close_price, atr14_frac, spread_pct in features:
                    path_map, fallback_opens = self._load_path_candles(conn, str(symbol), event_open_ms)
                    opens = [event_open_ms + offset * self.interval_ms for offset in needed_offsets]
                    if any(open_ms not in path_map for open_ms in opens):
                        unresolved += sum(open_ms not in path_map for open_ms in opens)
                        continue
                    path = [path_map[open_ms] for open_ms in opens]
                    funding_rows = conn.execute(
                        """
                        SELECT funding_time_ms, funding_rate, mark_price
                        FROM funding_events
                        WHERE symbol=? AND funding_time_ms>? AND funding_time_ms<=?
                        ORDER BY funding_time_ms
                        """,
                        (str(symbol), event_close_ms, max_horizon_close_ms),
                    ).fetchall()
                    event_rows.append(
                        self._build_row(
                            event_open_ms=event_open_ms,
                            symbol=str(symbol),
                            entry_price=float(close_price),
                            risk_unit_frac=None if atr14_frac is None else float(atr14_frac),
                            spread_pct=float(spread_pct),
                            path=path,
                            fallback_opens=fallback_opens,
                            funding_events=[
                                (int(ts), float(rate), None if mark is None else float(mark))
                                for ts, rate, mark in funding_rows
                            ],
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
                    detail="event build is atomic; no partial future-path event was committed",
                )
                continue

            self._insert_event(event_open_ms, event_rows, rebuild)
            built += 1
            path_rows_total += len(event_rows)

        return OutcomeBuildResult(
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

    def status(self) -> dict[str, Any]:
        self.initialize()
        with self.db.connection() as conn:
            feature_events = int(
                conn.execute(
                    "SELECT COUNT(DISTINCT event_open_ms) FROM canonical_features WHERE feature_version=?",
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            feature_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM canonical_features WHERE feature_version=?",
                    (self.config.feature_version,),
                ).fetchone()[0]
            )
            built_events = int(
                conn.execute(
                    "SELECT COUNT(*) FROM future_path_builds WHERE outcome_version=?",
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            path_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE outcome_version=?",
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            fallback_cache = int(conn.execute("SELECT COUNT(*) FROM future_candle_cache").fetchone()[0])
            fallback_used = int(
                conn.execute(
                    "SELECT COALESCE(SUM(fallback_candle_count),0) FROM future_paths WHERE outcome_version=?",
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            risk_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE outcome_version=? AND risk_unit_frac IS NOT NULL",
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            attempts = int(
                conn.execute(
                    "SELECT COUNT(*) FROM future_path_attempts WHERE outcome_version=?",
                    (self.config.outcome_version,),
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
                          WHERE b.event_open_ms=a.event_open_ms AND b.outcome_version=a.outcome_version
                      )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            latest = conn.execute(
                """
                SELECT event_open_ms, path_row_count, fallback_candle_count, path_digest
                FROM future_path_builds
                WHERE outcome_version=?
                ORDER BY event_open_ms DESC LIMIT 1
                """,
                (self.config.outcome_version,),
            ).fetchone()
        return {
            "outcome_version": self.config.outcome_version,
            "feature_version": self.config.feature_version,
            "feature_events": feature_events,
            "feature_rows": feature_rows,
            "built_events": built_events,
            "path_rows": path_rows,
            "unbuilt_feature_events": feature_events - built_events,
            "risk_unit_rows": risk_rows,
            "fallback_cache_rows": fallback_cache,
            "fallback_candles_used": fallback_used,
            "attempts": attempts,
            "unresolved_attempt_events": unresolved_attempt_events,
            "latest_build": latest,
        }

    def audit(self) -> dict[str, Any]:
        self.initialize()
        expected_definition_hash = _definition_hash(self.definition())
        with self.db.connection() as conn:
            stored = conn.execute(
                "SELECT definition_hash FROM future_path_sets WHERE outcome_version=?",
                (self.config.outcome_version,),
            ).fetchone()
            definition_mismatch = int(stored is None or stored[0] != expected_definition_hash)
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
                        short_mfe_frac<0 OR short_mae_frac<0 OR future_realized_vol_4h<0 OR
                        funding_complete!=1 OR roundtrip_base_cost_frac<0 OR
                        (risk_unit_frac IS NOT NULL AND risk_unit_frac<=0)
                    )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            cost_version_mismatches = int(
                conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE outcome_version=? AND cost_version!=?",
                    (self.config.outcome_version, self.config.cost_version),
                ).fetchone()[0]
            )
            risk_version_mismatches = int(
                conn.execute(
                    "SELECT COUNT(*) FROM future_paths WHERE outcome_version=? AND risk_unit_version!=?",
                    (self.config.outcome_version, self.config.risk_unit_version),
                ).fetchone()[0]
            )
            build_row_mismatches = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM future_path_builds b
                    WHERE b.outcome_version=? AND b.path_row_count != (
                        SELECT COUNT(*) FROM future_paths p
                        WHERE p.event_open_ms=b.event_open_ms AND p.outcome_version=b.outcome_version
                    )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            cache_conflicts = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM future_candle_cache c
                    JOIN candles_5m r ON r.symbol=c.symbol AND r.event_open_ms=c.event_open_ms
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
                          WHERE b.event_open_ms=a.event_open_ms AND b.outcome_version=a.outcome_version
                      )
                    """,
                    (self.config.outcome_version,),
                ).fetchone()[0]
            )
            rows = conn.execute(
                f"SELECT {','.join(PATH_COLUMNS)} FROM future_paths WHERE outcome_version=? ORDER BY event_open_ms, symbol",
                (self.config.outcome_version,),
            ).fetchall()
            build_rows = conn.execute(
                "SELECT event_open_ms, path_digest FROM future_path_builds WHERE outcome_version=? ORDER BY event_open_ms",
                (self.config.outcome_version,),
            ).fetchall()

        path_digest_mismatches = 0
        event_groups: dict[int, list[dict[str, Any]]] = {}
        json_errors = 0
        for raw in rows:
            row = dict(zip(PATH_COLUMNS, raw))
            expected_path_digest = _definition_hash([row[field] for field in PATH_DIGEST_FIELDS])
            if expected_path_digest != row["path_digest"]:
                path_digest_mismatches += 1
            try:
                barrier = json.loads(row["barrier_hits_json"])
                continuation = json.loads(row["continuation_json"])
                funding = json.loads(row["funding_events_json"])
                if not isinstance(barrier, dict) or not isinstance(continuation, dict) or not isinstance(funding, list):
                    json_errors += 1
            except Exception:
                json_errors += 1
            event_groups.setdefault(int(row["event_open_ms"]), []).append(row)

        build_digest_mismatches = 0
        source_candle_digest_mismatches = 0
        funding_source_digest_mismatches = 0
        build_map = {int(event_open_ms): str(digest) for event_open_ms, digest in build_rows}
        for event_open_ms, event_rows in event_groups.items():
            expected = _rows_digest(event_rows, ("event_open_ms", "symbol", "path_digest"))
            if build_map.get(event_open_ms) != expected:
                build_digest_mismatches += 1

            symbols = sorted(str(row["symbol"]) for row in event_rows)
            if not symbols:
                continue
            start_open = event_open_ms + self.interval_ms
            end_open = event_open_ms + self.config.max_horizon_bars * self.interval_ms
            placeholders = ",".join("?" for _ in symbols)
            with self.db.connection() as conn:
                canonical = conn.execute(
                    f"""
                    SELECT symbol, event_open_ms, open_time_ms, close_time_ms, open_price, high_price,
                           low_price, close_price, base_volume, quote_volume, trade_count,
                           taker_buy_base_volume, taker_buy_quote_volume
                    FROM candles_5m
                    WHERE event_open_ms BETWEEN ? AND ? AND symbol IN ({placeholders})
                    """,
                    [start_open, end_open, *symbols],
                ).fetchall()
                cached = conn.execute(
                    f"""
                    SELECT symbol, event_open_ms, open_time_ms, close_time_ms, open_price, high_price,
                           low_price, close_price, base_volume, quote_volume, trade_count,
                           taker_buy_base_volume, taker_buy_quote_volume
                    FROM future_candle_cache
                    WHERE event_open_ms BETWEEN ? AND ? AND symbol IN ({placeholders})
                    """,
                    [start_open, end_open, *symbols],
                ).fetchall()
                event_close_ms = int(
                    conn.execute(
                        "SELECT event_close_ms FROM market_events WHERE event_open_ms=?",
                        (event_open_ms,),
                    ).fetchone()[0]
                )
                max_close_ms = end_open + self.interval_ms - 1
                funding_rows = conn.execute(
                    f"""
                    SELECT symbol, funding_time_ms, funding_rate, mark_price
                    FROM funding_events
                    WHERE funding_time_ms>? AND funding_time_ms<=? AND symbol IN ({placeholders})
                    ORDER BY symbol, funding_time_ms
                    """,
                    [event_close_ms, max_close_ms, *symbols],
                ).fetchall()

            candle_map: dict[str, dict[int, Candle]] = {symbol: {} for symbol in symbols}
            for raw_source in (cached, canonical):
                for raw in raw_source:
                    symbol = str(raw[0])
                    open_ms = int(raw[1])
                    candle_map[symbol][open_ms] = Candle(
                        symbol=symbol,
                        open_time_ms=int(raw[2]),
                        close_time_ms=int(raw[3]),
                        open_price=float(raw[4]),
                        high_price=float(raw[5]),
                        low_price=float(raw[6]),
                        close_price=float(raw[7]),
                        base_volume=float(raw[8]),
                        quote_volume=float(raw[9]),
                        trade_count=int(raw[10]),
                        taker_buy_base_volume=float(raw[11]),
                        taker_buy_quote_volume=float(raw[12]),
                    )

            funding_map: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in symbols}
            for symbol, funding_time_ms, funding_rate, mark_price in funding_rows:
                funding_map[str(symbol)].append(
                    {
                        "funding_time_ms": int(funding_time_ms),
                        "funding_rate": float(funding_rate),
                        "mark_price": None if mark_price is None else float(mark_price),
                    }
                )

            expected_opens = [
                event_open_ms + offset * self.interval_ms
                for offset in range(1, self.config.max_horizon_bars + 1)
            ]
            for row in event_rows:
                symbol = str(row["symbol"])
                if all(open_ms in candle_map[symbol] for open_ms in expected_opens):
                    path = [candle_map[symbol][open_ms] for open_ms in expected_opens]
                    if _candle_source_digest(path) != row["source_candle_digest"]:
                        source_candle_digest_mismatches += 1
                else:
                    source_candle_digest_mismatches += 1
                if _definition_hash(funding_map[symbol]) != row["funding_source_digest"]:
                    funding_source_digest_mismatches += 1

        return {
            "outcome_version": self.config.outcome_version,
            "definition_mismatch": definition_mismatch,
            "built_events": len(build_rows),
            "path_rows": len(rows),
            "paths_without_feature": paths_without_feature,
            "invalid_source_bounds": invalid_source_bounds,
            "invalid_path_values": invalid_path_values,
            "cost_version_mismatches": cost_version_mismatches,
            "risk_version_mismatches": risk_version_mismatches,
            "build_row_mismatches": build_row_mismatches,
            "future_cache_conflicts": cache_conflicts,
            "unresolved_attempt_events": unresolved_attempt_events,
            "json_errors": json_errors,
            "path_digest_mismatches": path_digest_mismatches,
            "build_digest_mismatches": build_digest_mismatches,
            "source_candle_digest_mismatches": source_candle_digest_mismatches,
            "funding_source_digest_mismatches": funding_source_digest_mismatches,
        }
