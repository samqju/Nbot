"""Phase 7.3 read-only spread and funding evidence collection.

The provider is Observation-only. It performs public Binance reads and produces
one immutable snapshot for a five-minute bucket. Failure degrades learning-cost
completeness; it never grants trading authority and must not stop Observation.
"""

from __future__ import annotations

import copy
import math
import time
from typing import Iterable


_MIN_SPREAD_COVERAGE = 0.80


def _finite(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


class ObservationVirtualCostEvidenceProvider:
    def __init__(self, *, market_client, system_log=None):
        self.market_client = market_client
        self.system_log = system_log

    def snapshot(
        self,
        *,
        symbols: Iterable[str],
        candle_bucket: int,
        start_ms: int,
        end_ms: int,
    ) -> dict:
        requested = sorted({
            str(symbol).strip().upper()
            for symbol in symbols
            if str(symbol).strip()
        })
        if not requested:
            raise ValueError("VIRTUAL_COST_EVIDENCE_SYMBOLS_EMPTY")
        start_ms = int(start_ms)
        end_ms = int(end_ms)
        if start_ms < 0 or end_ms <= 0 or start_ms > end_ms:
            raise ValueError("VIRTUAL_COST_EVIDENCE_WINDOW_INVALID")

        rows = self.market_client.get_virtual_cost_evidence_rows(
            symbols=requested,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        if not isinstance(rows, dict):
            raise ValueError("VIRTUAL_COST_EVIDENCE_ROWS_INVALID")

        spread_by_symbol = {}
        raw_spreads = rows.get("spread_by_symbol")
        if isinstance(raw_spreads, dict):
            for symbol in requested:
                value = _finite(raw_spreads.get(symbol))
                if value is not None and value >= 0:
                    spread_by_symbol[symbol] = value

        raw_funding = rows.get("funding_events_by_symbol")
        funding_events_by_symbol = {}
        if isinstance(raw_funding, dict):
            for symbol in requested:
                events = raw_funding.get(symbol)
                if not isinstance(events, list):
                    continue
                clean = []
                for event in events:
                    if not isinstance(event, dict):
                        continue
                    rate = _finite(event.get("funding_rate"))
                    mark = _finite(event.get("mark_price"))
                    try:
                        funding_time = int(event.get("funding_time"))
                    except (TypeError, ValueError):
                        continue
                    if rate is None or mark is None or mark <= 0 or funding_time <= 0:
                        continue
                    clean.append({
                        "funding_time": funding_time,
                        "funding_rate": rate,
                        "mark_price": mark,
                        "rate_type": str(event.get("rate_type") or "Regular"),
                    })
                if clean:
                    clean.sort(key=lambda row: row["funding_time"])
                    funding_events_by_symbol[symbol] = clean

        spread_coverage = len(spread_by_symbol) / len(requested)
        history_complete = bool(rows.get("funding_history_complete", False))
        funding_start = int(rows.get("funding_coverage_start_ms", start_ms))
        funding_end = int(rows.get("funding_coverage_end_ms", end_ms))
        complete = (
            spread_coverage >= _MIN_SPREAD_COVERAGE
            and history_complete
            and funding_start <= start_ms
            and funding_end >= end_ms
        )
        snapshot = {
            "schema_version": 1,
            "source": "BINANCE_BOOK_TICKER_AND_FUNDING_HISTORY",
            "observed_at_ms": int(time.time() * 1000),
            "candle_bucket": int(candle_bucket),
            "symbols_expected": len(requested),
            "symbols_with_spread": len(spread_by_symbol),
            "spread_coverage": spread_coverage,
            "spread_by_symbol": spread_by_symbol,
            "funding_events_by_symbol": copy.deepcopy(funding_events_by_symbol),
            "funding_coverage_start_ms": funding_start,
            "funding_coverage_end_ms": funding_end,
            "funding_history_complete": history_complete,
            "funding_rows_returned": int(rows.get("funding_rows_returned", 0) or 0),
            "funding_pages": int(rows.get("funding_pages", 0) or 0),
            "funding_parse_errors": int(
                rows.get("funding_parse_errors", 0) or 0
            ),
            "completeness": (
                "COMPLETE_PHASE7_3" if complete else "PARTIAL_PHASE7_3"
            ),
        }
        self._log(
            "debug",
            "PHASE7_COST_EVIDENCE_SNAPSHOT | "
            f"bucket={int(candle_bucket)} | "
            f"spread_coverage={spread_coverage:.3f} | "
            f"funding_complete={str(history_complete).lower()} | "
            f"funding_rows={snapshot['funding_rows_returned']} | "
            f"funding_pages={snapshot['funding_pages']} | "
            f"funding_parse_errors={snapshot['funding_parse_errors']}",
        )
        return snapshot

    def _log(self, level: str, message: str) -> None:
        if self.system_log is None:
            return
        getattr(self.system_log, level, lambda *_a, **_k: None)(message)
