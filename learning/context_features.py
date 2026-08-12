"""Phase 7.2 market-context feature contract for challenger learning.

The local nine candidate features remain versioned by ``strategy.features``.
This module adds a separate context schema so old artifacts can continue to
score candidates while new challengers explicitly declare that they require
complete Phase-7.1 market context.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


CONTEXT_FEATURE_SCHEMA_VERSION = 1
REQUIRED_MARKET_CONTEXT_COMPLETENESS = "COMPLETE_PHASE7_1"

MARKET_REGIMES = ("BULLISH", "BEARISH", "SIDEWAYS")
VOLATILITY_REGIMES = ("LOW", "NORMAL", "HIGH", "EXTREME")
BTC_REGIMES = (
    "STRONG_BULLISH",
    "BULLISH",
    "SIDEWAYS",
    "BEARISH",
    "STRONG_BEARISH",
)

CONTEXT_FEATURE_NAMES = (
    "ctx_btc_change_pct_24h",
    "ctx_market_advancing_fraction",
    "ctx_market_declining_fraction",
    "ctx_market_unchanged_fraction",
    "ctx_market_median_change_pct_24h",
    "ctx_market_median_abs_change_pct_24h",
    "ctx_market_coverage",
    "ctx_spread_pct",
    "ctx_log10_quote_volume_usd",
    *(f"ctx_market_regime::{name}" for name in MARKET_REGIMES),
    *(f"ctx_volatility_regime::{name}" for name in VOLATILITY_REGIMES),
    *(f"ctx_btc_regime::{name}" for name in BTC_REGIMES),
)


class ContextFeatureError(ValueError):
    pass


def market_context_from_row(row: Mapping[str, Any]) -> dict:
    direct = row.get("market_context")
    if isinstance(direct, Mapping):
        return dict(direct)
    experiment = row.get("experiment_context")
    if isinstance(experiment, Mapping):
        nested = experiment.get("market_context")
        if isinstance(nested, Mapping):
            return dict(nested)
    return {}


def market_context_from_candidate(candidate: Any) -> dict:
    experiment = getattr(candidate, "experiment_context", None)
    if not isinstance(experiment, Mapping):
        return {}
    nested = experiment.get("market_context")
    return dict(nested) if isinstance(nested, Mapping) else {}


def is_complete_market_context(context: Any) -> bool:
    try:
        context_feature_vector(context)
    except ContextFeatureError:
        return False
    return True


def context_feature_mapping(context: Any) -> dict[str, float]:
    values = context_feature_vector(context)
    return dict(zip(CONTEXT_FEATURE_NAMES, values, strict=True))


def context_feature_vector(context: Any) -> list[float]:
    """Return the fixed Phase-7.2 vector or fail closed on partial context."""
    if not isinstance(context, Mapping):
        raise ContextFeatureError("CONTEXT_FEATURE_MARKET_CONTEXT_MISSING")
    if context.get("completeness") != REQUIRED_MARKET_CONTEXT_COMPLETENESS:
        raise ContextFeatureError("CONTEXT_FEATURE_MARKET_CONTEXT_INCOMPLETE")

    breadth = context.get("market_breadth")
    liquidity = context.get("liquidity")
    if not isinstance(breadth, Mapping):
        raise ContextFeatureError("CONTEXT_FEATURE_BREADTH_MISSING")
    if not isinstance(liquidity, Mapping):
        raise ContextFeatureError("CONTEXT_FEATURE_LIQUIDITY_MISSING")

    market_regime = _category(context.get("market_regime"), MARKET_REGIMES, "MARKET_REGIME")
    volatility_regime = _category(
        context.get("volatility_regime"), VOLATILITY_REGIMES, "VOLATILITY_REGIME"
    )
    btc_regime = _category(context.get("btc_regime"), BTC_REGIMES, "BTC_REGIME")

    btc_change = _finite(context.get("btc_change_pct_24h"), "BTC_CHANGE")
    advancing = _fraction(breadth.get("advancing_fraction"), "ADVANCING_FRACTION")
    declining = _fraction(breadth.get("declining_fraction"), "DECLINING_FRACTION")
    unchanged = _fraction(breadth.get("unchanged_fraction"), "UNCHANGED_FRACTION")
    median_change = _finite(
        breadth.get("median_change_pct_24h"), "MEDIAN_CHANGE"
    )
    median_abs_change = _finite(
        breadth.get("median_abs_change_pct_24h"), "MEDIAN_ABS_CHANGE"
    )
    coverage = _fraction(
        context.get("context_coverage", breadth.get("coverage")),
        "MARKET_COVERAGE",
    )
    spread = _finite(liquidity.get("spread_pct"), "SPREAD_PCT")
    quote_volume = _finite(
        liquidity.get("quote_volume_usd"), "QUOTE_VOLUME_USD"
    )
    if spread < 0:
        raise ContextFeatureError("CONTEXT_FEATURE_SPREAD_NEGATIVE")
    if quote_volume <= 0:
        raise ContextFeatureError("CONTEXT_FEATURE_QUOTE_VOLUME_NONPOSITIVE")

    vector = [
        btc_change,
        advancing,
        declining,
        unchanged,
        median_change,
        median_abs_change,
        coverage,
        spread,
        math.log10(max(1.0, quote_volume)),
    ]
    vector.extend(1.0 if market_regime == name else 0.0 for name in MARKET_REGIMES)
    vector.extend(
        1.0 if volatility_regime == name else 0.0
        for name in VOLATILITY_REGIMES
    )
    vector.extend(1.0 if btc_regime == name else 0.0 for name in BTC_REGIMES)
    if len(vector) != len(CONTEXT_FEATURE_NAMES):
        raise ContextFeatureError("CONTEXT_FEATURE_VECTOR_LENGTH_INVALID")
    return [float(value) for value in vector]


def _category(value: Any, allowed: tuple[str, ...], name: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in allowed:
        raise ContextFeatureError(f"CONTEXT_FEATURE_{name}_INVALID")
    return normalized


def _finite(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContextFeatureError(f"CONTEXT_FEATURE_{name}_INVALID") from exc
    if not math.isfinite(result):
        raise ContextFeatureError(f"CONTEXT_FEATURE_{name}_INVALID")
    return result


def _fraction(value: Any, name: str) -> float:
    result = _finite(value, name)
    if result < 0.0 or result > 1.0:
        raise ContextFeatureError(f"CONTEXT_FEATURE_{name}_OUT_OF_RANGE")
    return result
