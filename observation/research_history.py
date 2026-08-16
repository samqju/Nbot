"""Point-in-time multi-horizon public market history for strategy research.

Phase 7.5D.2B.2 deliberately stops at the data boundary. It does not create
strategy candidates, virtual trades, model features, recommendations, or order
authority.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass


HOURLY_INTERVAL = "1h"
DAILY_INTERVAL = "1d"

# 90 completed days of hourly bars gives the intraday research family a much
# broader window than the old 50 x 5m setup history. Pagination is required
# because Binance caps one kline response at 1500 rows.
HOURLY_REQUIRED_BARS = 90 * 24
DAILY_REQUIRED_BARS = 365
MAX_KLINES_PER_REQUEST = 1500

# Minimum complete history required by the initial benchmark catalog.
MIN_CROSS_SECTIONAL_DAILY_BARS = 15
MIN_TSMOM_DAILY_BARS = 29
MIN_INTRADAY_HOURLY_BARS = 7 * 24


@dataclass(frozen=True)
class ResearchHistorySnapshot:
    symbol: str
    as_of_ms: int
    hourly_bars: tuple[dict, ...]
    daily_bars: tuple[dict, ...]
    cross_sectional_ready: bool
    time_series_momentum_ready: bool
    intraday_ready: bool
    completeness: str

    def to_summary(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of_ms": self.as_of_ms,
            "hourly_bars": len(self.hourly_bars),
            "daily_bars": len(self.daily_bars),
            "cross_sectional_ready": self.cross_sectional_ready,
            "time_series_momentum_ready": self.time_series_momentum_ready,
            "intraday_ready": self.intraday_ready,
            "completeness": self.completeness,
            "hourly_oldest_open_ms": (
                self.hourly_bars[0]["open_time_ms"] if self.hourly_bars else None
            ),
            "hourly_latest_close_ms": (
                self.hourly_bars[-1]["close_time_ms"] if self.hourly_bars else None
            ),
            "daily_oldest_open_ms": (
                self.daily_bars[0]["open_time_ms"] if self.daily_bars else None
            ),
            "daily_latest_close_ms": (
                self.daily_bars[-1]["close_time_ms"] if self.daily_bars else None
            ),
        }


class MultiHorizonResearchHistoryProvider:
    """Fetch deterministic completed 1h/1d public history as of one timestamp."""

    def __init__(
        self,
        *,
        market_client,
        hourly_required_bars: int = HOURLY_REQUIRED_BARS,
        daily_required_bars: int = DAILY_REQUIRED_BARS,
        max_klines_per_request: int = MAX_KLINES_PER_REQUEST,
    ):
        self.market_client = market_client
        self.hourly_required_bars = int(hourly_required_bars)
        self.daily_required_bars = int(daily_required_bars)
        self.max_klines_per_request = int(max_klines_per_request)

        if self.hourly_required_bars < MIN_INTRADAY_HOURLY_BARS:
            raise ValueError("RESEARCH_HOURLY_HISTORY_TOO_SHORT")
        if self.daily_required_bars < MIN_TSMOM_DAILY_BARS:
            raise ValueError("RESEARCH_DAILY_HISTORY_TOO_SHORT")
        if not (1 <= self.max_klines_per_request <= 1500):
            raise ValueError("RESEARCH_PAGE_LIMIT_INVALID")

    def snapshot(
        self,
        *,
        symbol: str,
        as_of_ms: int | None = None,
    ) -> ResearchHistorySnapshot:
        symbol = str(symbol or "").strip().upper()
        if not symbol:
            raise ValueError("RESEARCH_SYMBOL_INVALID")

        as_of = int(as_of_ms) if as_of_ms is not None else int(time.time() * 1000)
        if as_of <= 0:
            raise ValueError("RESEARCH_AS_OF_INVALID")

        hourly = self._fetch_completed_history(
            symbol=symbol,
            interval=HOURLY_INTERVAL,
            required_bars=self.hourly_required_bars,
            as_of_ms=as_of,
        )
        daily = self._fetch_completed_history(
            symbol=symbol,
            interval=DAILY_INTERVAL,
            required_bars=self.daily_required_bars,
            as_of_ms=as_of,
        )

        cross_ready = self._cross_sectional_ready(daily)
        tsmom_ready = len(daily) >= MIN_TSMOM_DAILY_BARS
        intraday_ready = len(hourly) >= MIN_INTRADAY_HOURLY_BARS
        complete = (
            len(hourly) >= self.hourly_required_bars
            and len(daily) >= self.daily_required_bars
            and cross_ready
        )

        return ResearchHistorySnapshot(
            symbol=symbol,
            as_of_ms=as_of,
            hourly_bars=tuple(hourly),
            daily_bars=tuple(daily),
            cross_sectional_ready=cross_ready,
            time_series_momentum_ready=tsmom_ready,
            intraday_ready=intraday_ready,
            completeness=(
                "COMPLETE_PHASE7_5D2B2" if complete else "PARTIAL_PHASE7_5D2B2"
            ),
        )

    def _fetch_completed_history(
        self,
        *,
        symbol: str,
        interval: str,
        required_bars: int,
        as_of_ms: int,
    ) -> list[dict]:
        by_open_time: dict[int, dict] = {}
        cursor = int(as_of_ms)
        previous_cursor = None

        while len(by_open_time) < required_bars:
            remaining = required_bars - len(by_open_time)
            page_limit = min(self.max_klines_per_request, remaining)

            page = self.market_client.get_historical_research_bars(
                symbol=symbol,
                interval=interval,
                limit=page_limit,
                end_time_ms=cursor,
            )
            if not page:
                break

            normalized = self._validate_page(page=page, as_of_ms=as_of_ms)
            for bar in normalized:
                by_open_time[int(bar["open_time_ms"])] = bar

            oldest_open = min(int(bar["open_time_ms"]) for bar in normalized)
            next_cursor = oldest_open

            if previous_cursor is not None and next_cursor >= previous_cursor:
                raise RuntimeError("RESEARCH_HISTORY_PAGINATION_STALLED")
            previous_cursor = next_cursor
            cursor = next_cursor

        rows = sorted(
            by_open_time.values(),
            key=lambda row: int(row["open_time_ms"]),
        )
        if len(rows) > required_bars:
            rows = rows[-required_bars:]
        return rows

    @staticmethod
    def _validate_page(*, page: list[dict], as_of_ms: int) -> list[dict]:
        rows = []
        last_open = None

        for raw in page:
            if not isinstance(raw, dict):
                raise RuntimeError("RESEARCH_HISTORY_ROW_SCHEMA_INVALID")

            required = (
                "open_time_ms",
                "close_time_ms",
                "open",
                "high",
                "low",
                "close",
                "quote_volume",
            )
            if any(key not in raw for key in required):
                raise RuntimeError("RESEARCH_HISTORY_ROW_SCHEMA_INVALID")

            open_time = int(raw["open_time_ms"])
            close_time = int(raw["close_time_ms"])
            o = float(raw["open"])
            h = float(raw["high"])
            l = float(raw["low"])
            c = float(raw["close"])
            quote_volume = float(raw["quote_volume"])

            if (
                open_time <= 0
                or close_time <= open_time
                or close_time >= int(as_of_ms)
                or min(o, h, l, c) <= 0
                or h < max(o, c)
                or l > min(o, c)
                or not math.isfinite(quote_volume)
                or quote_volume < 0
            ):
                raise RuntimeError("RESEARCH_HISTORY_ROW_VALUES_INVALID")

            if last_open is not None and open_time <= last_open:
                raise RuntimeError("RESEARCH_HISTORY_ORDER_INVALID")
            last_open = open_time
            rows.append(dict(raw))

        return rows

    @staticmethod
    def _cross_sectional_ready(daily: list[dict]) -> bool:
        if len(daily) < MIN_CROSS_SECTIONAL_DAILY_BARS:
            return False

        recent = daily[-MIN_CROSS_SECTIONAL_DAILY_BARS:]
        return all(float(bar.get("quote_volume", 0.0)) > 0 for bar in recent[1:])
