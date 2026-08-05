"""Broad observation-universe ranking for Phase 3.6B.2.

This module uses public Binance Futures metadata only. It does not authenticate,
place orders, or modify account state.
"""

from __future__ import annotations

import math
import os
from collections import Counter
from typing import Iterable

import requests

from config import (
    OBSERVATION_UNIVERSE_CORE_SIZE,
    OBSERVATION_UNIVERSE_MAX_SPREAD_PCT,
    OBSERVATION_UNIVERSE_MIN_QUOTE_VOLUME,
    OBSERVATION_UNIVERSE_SIZE,
    OBSERVATION_UNIVERSE_MARKET_BASE_URL,
    TRADING_ENV,
)


def _base_url() -> str:
    value = OBSERVATION_UNIVERSE_MARKET_BASE_URL.strip().rstrip("/")
    if value:
        return value
    raise RuntimeError(
        "OBSERVATION_UNIVERSE_BASE_URL_MISSING | "
        f"environment={TRADING_ENV}"
    )


def _get_json(session, url: str):
    response = session.get(url, timeout=15)
    response.raise_for_status()
    return response.json()


def _normalize(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if high <= low:
        return {symbol: 1.0 for symbol in values}
    scale = high - low
    return {
        symbol: (value - low) / scale
        for symbol, value in values.items()
    }


def _regime(change_pct: float) -> str:
    if change_pct <= 2.0:
        return "LOW_ACTIVITY"
    if change_pct >= 8.0:
        return "HIGH_ACTIVITY"
    return "BALANCED"


def build_observation_universe(
    execution_symbols: Iterable[str],
    *,
    session=requests,
    target_size: int = OBSERVATION_UNIVERSE_SIZE,
    core_size: int = OBSERVATION_UNIVERSE_CORE_SIZE,
    require_execution_eligible: bool = True,
) -> list[str]:
    """Rank a broad learning pool.

    When ``require_execution_eligible`` is false, execution symbols that fail
    observation filters are omitted so the caller can replace them from the
    eligible ranked pool.
    """
    execution = {
        str(symbol).strip().upper()
        for symbol in execution_symbols
    }
    if not execution:
        raise ValueError("OBSERVATION_EXECUTION_UNIVERSE_EMPTY")
    if core_size > target_size:
        raise ValueError("OBSERVATION_CORE_EXCEEDS_TARGET")

    base_url = _base_url()
    exchange_info = _get_json(
        session,
        f"{base_url}/fapi/v1/exchangeInfo",
    )
    tickers = _get_json(
        session,
        f"{base_url}/fapi/v1/ticker/24hr",
    )
    books = _get_json(
        session,
        f"{base_url}/fapi/v1/ticker/bookTicker",
    )

    supported = {
        row.get("symbol")
        for row in exchange_info.get("symbols", [])
        if (
            row.get("contractType") == "PERPETUAL"
            and row.get("quoteAsset") == "USDT"
            and row.get("status") == "TRADING"
        )
    }
    book_by_symbol = {
        row.get("symbol"): row
        for row in books
        if isinstance(row, dict)
    }

    rows = {}
    for ticker in tickers:
        if not isinstance(ticker, dict):
            continue
        symbol = ticker.get("symbol")
        if (
            not isinstance(symbol, str)
            or not symbol.isascii()
            or not symbol.endswith("USDT")
            or not symbol.replace("USDT", "").isalnum()
            or symbol not in supported
        ):
            continue

        book = book_by_symbol.get(symbol, {})
        try:
            quote_volume = float(ticker.get("quoteVolume", 0))
            change_pct = abs(
                float(ticker.get("priceChangePercent", 0))
            )
            trade_count = float(ticker.get("count", 0))
            last_price = float(ticker.get("lastPrice", 0))
            bid = float(book.get("bidPrice", 0))
            ask = float(book.get("askPrice", 0))
        except (TypeError, ValueError):
            continue

        if (
            quote_volume < OBSERVATION_UNIVERSE_MIN_QUOTE_VOLUME
            or last_price <= 0
            or bid <= 0
            or ask < bid
        ):
            continue

        spread_pct = ((ask - bid) / last_price) * 100.0
        if spread_pct > OBSERVATION_UNIVERSE_MAX_SPREAD_PCT:
            continue

        rows[symbol] = {
            "quote_volume": quote_volume,
            "change_pct": min(change_pct, 50.0),
            "trade_count": max(0.0, trade_count),
            "spread_pct": spread_pct,
            "regime": _regime(change_pct),
        }

    missing_execution = execution - set(rows)
    if missing_execution and require_execution_eligible:
        raise RuntimeError(
            "OBSERVATION_EXECUTION_SYMBOLS_INELIGIBLE | "
            f"symbols={sorted(missing_execution)}"
        )

    # In compatibility mode only eligible execution symbols remain mandatory.
    # UniverseManager will replace the missing symbols before final validation.
    mandatory_execution = execution & set(rows)

    if len(rows) < len(mandatory_execution):
        raise RuntimeError(
            "OBSERVATION_UNIVERSE_INSUFFICIENT_ELIGIBLE_SYMBOLS"
        )

    liquidity_volume = _normalize({
        symbol: math.log1p(data["quote_volume"])
        for symbol, data in rows.items()
    })
    activity_trades = _normalize({
        symbol: math.log1p(data["trade_count"])
        for symbol, data in rows.items()
    })
    activity_move = _normalize({
        symbol: data["change_pct"]
        for symbol, data in rows.items()
    })

    regime_counts = Counter(
        data["regime"] for data in rows.values()
    )
    max_regime_count = max(regime_counts.values())

    ranked = []
    for symbol, data in rows.items():
        spread_quality = max(
            0.0,
            1.0
            - (
                data["spread_pct"]
                / OBSERVATION_UNIVERSE_MAX_SPREAD_PCT
            ),
        )
        liquidity_score = (
            0.80 * liquidity_volume[symbol]
            + 0.20 * spread_quality
        )

        # Prefer useful movement around 6%, while still retaining calm and
        # fast regimes through the diversity component.
        volatility_quality = max(
            0.0,
            1.0 - abs(data["change_pct"] - 6.0) / 20.0,
        )
        activity_score = (
            0.60 * activity_move[symbol]
            + 0.40 * activity_trades[symbol]
        )
        diversity_score = (
            1.0
            - (
                regime_counts[data["regime"]]
                / max_regime_count
            )
            if max_regime_count
            else 0.0
        )

        composite = (
            0.35 * liquidity_score
            + 0.30 * volatility_quality
            + 0.20 * activity_score
            + 0.15 * diversity_score
        )
        ranked.append(
            (
                symbol,
                composite,
                data["regime"],
            )
        )

    ranked.sort(key=lambda item: (-item[1], item[0]))

    effective_target = min(target_size, len(ranked))
    effective_core = min(core_size, effective_target)

    selected = [
        symbol
        for symbol, _, _ in ranked[:effective_core]
    ]
    selected_set = set(selected)

    # Fill diversity slots in round-robin regime order.
    by_regime = {
        regime: [
            item for item in ranked[effective_core:]
            if item[2] == regime
        ]
        for regime in (
            "LOW_ACTIVITY",
            "BALANCED",
            "HIGH_ACTIVITY",
        )
    }
    while len(selected) < effective_target:
        added = False
        for regime in (
            "LOW_ACTIVITY",
            "HIGH_ACTIVITY",
            "BALANCED",
        ):
            pool = by_regime[regime]
            while pool and pool[0][0] in selected_set:
                pool.pop(0)
            if not pool:
                continue
            symbol, _, _ = pool.pop(0)
            selected.append(symbol)
            selected_set.add(symbol)
            added = True
            if len(selected) >= effective_target:
                break
        if not added:
            break

    # Fill any remaining slots by the original deterministic ranking.
    for symbol, _, _ in ranked:
        if len(selected) >= effective_target:
            break
        if symbol not in selected_set:
            selected.append(symbol)
            selected_set.add(symbol)

    # Execution symbols are mandatory. Replace the weakest non-execution
    # symbols if a mandatory symbol fell below the observation cutoff.
    for symbol in sorted(mandatory_execution):
        if symbol in selected_set:
            continue
        replacement_index = None
        for index in range(len(selected) - 1, -1, -1):
            if selected[index] not in mandatory_execution:
                replacement_index = index
                break
        if replacement_index is None:
            selected.append(symbol)
        else:
            selected_set.remove(selected[replacement_index])
            selected[replacement_index] = symbol
        selected_set.add(symbol)

    return sorted(selected)
