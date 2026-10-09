"""Point-in-time V3 research vs execution universe separation."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping


@dataclass(frozen=True)
class UniverseCandidate:
    symbol: str
    quote_volume_24h_usd: float
    spread_pct: float
    trading: bool = True
    perpetual: bool = True
    quote_asset: str = "USDT"
    history_bars: int = 0


@dataclass(frozen=True)
class UniverseSelection:
    research_symbols: tuple[str, ...]
    execution_symbols: tuple[str, ...]
    rejected: Mapping[str, str]


def select_universes(rows: Iterable[UniverseCandidate], *, research_size: int = 200,
                     execution_allowlist: Iterable[str] = (), min_quote_volume_24h_usd: float = 3_000_000,
                     max_spread_pct: float = 0.50, min_history_bars: int = 576) -> UniverseSelection:
    if not 1 <= research_size <= 500 or min_quote_volume_24h_usd < 0 or not 0 < max_spread_pct <= 5:
        raise ValueError("V3_UNIVERSE_CONFIG_INVALID")
    allowed = set(execution_allowlist)
    accepted: list[UniverseCandidate] = []
    rejected: dict[str, str] = {}
    for row in rows:
        if not row.symbol or row.symbol != row.symbol.upper():
            raise ValueError("V3_UNIVERSE_SYMBOL_INVALID")
        if not (math.isfinite(row.quote_volume_24h_usd) and math.isfinite(row.spread_pct)):
            rejected[row.symbol] = "NONFINITE_MARKET_CONTEXT"
            continue
        if not row.trading or not row.perpetual or row.quote_asset != "USDT":
            rejected[row.symbol] = "CONTRACT_NOT_ELIGIBLE"
            continue
        if row.quote_volume_24h_usd < min_quote_volume_24h_usd:
            rejected[row.symbol] = "LIQUIDITY_BELOW_MIN"
            continue
        if row.spread_pct > max_spread_pct:
            rejected[row.symbol] = "SPREAD_ABOVE_MAX"
            continue
        if row.history_bars < min_history_bars:
            rejected[row.symbol] = "INSUFFICIENT_HISTORY"
            continue
        accepted.append(row)
    accepted.sort(key=lambda r: (-r.quote_volume_24h_usd, r.spread_pct, r.symbol))
    research = tuple(r.symbol for r in accepted[:research_size])
    execution = tuple(s for s in research if s in allowed)
    return UniverseSelection(research, execution, rejected)
