"""Phase 7.1 read-only broad market context collection.

The provider performs two bulk public Binance reads only when a completed
five-minute decision cycle is ready.  It never changes candidate ranking,
model scores, paper selection, risk, or execution authority.
"""

from __future__ import annotations

import math
import statistics
import time
from typing import Iterable


_MIN_BROAD_COVERAGE = 0.80


def _finite(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _btc_regime(change_pct: float | None) -> str | None:
    if change_pct is None:
        return None
    if change_pct >= 5.0:
        return "STRONG_BULLISH"
    if change_pct >= 1.0:
        return "BULLISH"
    if change_pct <= -5.0:
        return "STRONG_BEARISH"
    if change_pct <= -1.0:
        return "BEARISH"
    return "SIDEWAYS"


def _broad_regime(*, advancing_fraction: float, declining_fraction: float, median_change: float) -> str:
    if advancing_fraction >= 0.60 and median_change > 0:
        return "BULLISH"
    if declining_fraction >= 0.60 and median_change < 0:
        return "BEARISH"
    return "SIDEWAYS"


def _volatility_regime(median_abs_change: float) -> str:
    if median_abs_change < 2.0:
        return "LOW"
    if median_abs_change < 5.0:
        return "NORMAL"
    if median_abs_change < 10.0:
        return "HIGH"
    return "EXTREME"


class ObservationMarketContextProvider:
    """Build one frozen market snapshot for one completed decision cycle."""

    def __init__(self, *, market_client, system_log=None):
        self.market_client = market_client
        self.system_log = system_log

    def snapshot(self, *, symbols: Iterable[str], candle_bucket: int) -> dict:
        requested = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
        if not requested:
            raise ValueError("MARKET_CONTEXT_SYMBOLS_EMPTY")

        observed_at_ms = int(time.time() * 1000)
        rows = self.market_client.get_market_context_rows(symbols=requested)
        if not isinstance(rows, dict):
            raise ValueError("MARKET_CONTEXT_ROWS_INVALID")

        usable = {}
        for symbol in requested:
            row = rows.get(symbol)
            if not isinstance(row, dict):
                continue
            change = _finite(row.get("price_change_pct_24h"))
            spread = _finite(row.get("spread_pct"))
            quote_volume = _finite(row.get("quote_volume_usd"))
            if change is None:
                continue
            usable[symbol] = {
                "price_change_pct_24h": change,
                "spread_pct": spread,
                "quote_volume_usd": quote_volume,
            }

        coverage = len(usable) / len(requested)
        changes = [row["price_change_pct_24h"] for row in usable.values()]
        broad_ready = bool(changes) and coverage >= _MIN_BROAD_COVERAGE

        market_regime = None
        volatility_regime = None
        breadth = None
        if broad_ready:
            advancing = sum(1 for value in changes if value > 0)
            declining = sum(1 for value in changes if value < 0)
            unchanged = len(changes) - advancing - declining
            median_change = statistics.median(changes)
            median_abs_change = statistics.median(abs(value) for value in changes)
            advancing_fraction = advancing / len(changes)
            declining_fraction = declining / len(changes)
            unchanged_fraction = unchanged / len(changes)
            market_regime = _broad_regime(
                advancing_fraction=advancing_fraction,
                declining_fraction=declining_fraction,
                median_change=median_change,
            )
            volatility_regime = _volatility_regime(median_abs_change)
            breadth = {
                "symbols_expected": len(requested),
                "symbols_observed": len(usable),
                "coverage": coverage,
                "advancing_fraction": advancing_fraction,
                "declining_fraction": declining_fraction,
                "unchanged_fraction": unchanged_fraction,
                "median_change_pct_24h": median_change,
                "median_abs_change_pct_24h": median_abs_change,
            }

        btc = usable.get("BTCUSDT")
        btc_change = None if btc is None else btc.get("price_change_pct_24h")
        btc_regime = _btc_regime(_finite(btc_change))

        liquidity_by_symbol = {
            symbol: {
                "spread_pct": row.get("spread_pct"),
                "quote_volume_usd": row.get("quote_volume_usd"),
            }
            for symbol, row in usable.items()
        }

        snapshot = {
            "schema_version": 1,
            "source": "BINANCE_BULK_24H_AND_BOOK_TICKER",
            "observed_at_ms": observed_at_ms,
            "candle_bucket": int(candle_bucket),
            "symbols_expected": len(requested),
            "symbols_observed": len(usable),
            "coverage": coverage,
            "market_regime": market_regime,
            "trend_regime": market_regime,
            "volatility_regime": volatility_regime,
            "btc_regime": btc_regime,
            "btc_change_pct_24h": _finite(btc_change),
            "market_breadth": breadth,
            "liquidity_by_symbol": liquidity_by_symbol,
            "completeness": (
                "COMPLETE_PHASE7_1"
                if broad_ready and btc_regime is not None
                else "PARTIAL_PHASE7_1"
            ),
        }
        self._log(
            "debug",
            "PHASE7_MARKET_CONTEXT_SNAPSHOT | "
            f"bucket={int(candle_bucket)} | coverage={coverage:.3f} | "
            f"market={market_regime or 'UNKNOWN'} | "
            f"btc={btc_regime or 'UNKNOWN'} | "
            f"volatility={volatility_regime or 'UNKNOWN'}",
        )
        return snapshot

    def _log(self, level: str, message: str) -> None:
        if self.system_log is None:
            return
        getattr(self.system_log, level, lambda *_args, **_kwargs: None)(message)
