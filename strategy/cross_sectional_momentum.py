"""Phase 7.5D.2B.3 research-only liquidity-conditioned momentum signal.

This is a signal-reproduction boundary only. It does not create StrategyCandidate
objects, enroll virtual trades, change RULE_SYSTEM_V1, train models, or grant
paper/real order authority.

Reference family:
Begušić & Kostanjčar (2019), "Momentum and liquidity in cryptocurrencies".

NBOT adaptation:
- daily price/volume source is Binance USDT perpetual futures;
- quote volume in USDT is used as the traded-value denominator;
- NBOT's point-in-time observation universe replaces the paper's market-cap
  inclusion screen;
- a 26-week listing-history minimum is retained;
- the first benchmark is LONG-only liquid winners.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Mapping, Sequence


STRATEGY_ID = "CSM_LIQUID_WINNERS_14D_V1"
FAMILY = "CROSS_SECTIONAL_MOMENTUM_WITH_LIQUIDITY"
DIRECTION = "LONG"
AUTHORITY = "NONE"
RUNTIME_ACTIVATION = "DISABLED"
IMPLEMENTATION_STATUS = "SIGNAL_ONLY_RESEARCH"

FORMATION_DAYS = 14
ILLIQUIDITY_DAYS = 14
MIN_EXISTENCE_DAYS = 26 * 7
WINNER_FRACTION = 0.30
LIQUID_FRACTION = 0.30

# Protective research exclusion mirroring the paper's stablecoin exclusion.
# This is intentionally explicit and bounded rather than inferred from price.
DEFAULT_STABLECOIN_BASES = frozenset({
    "BUSD",
    "DAI",
    "FDUSD",
    "TUSD",
    "USDC",
    "USDE",
    "USDP",
    "USDS",
    "USD1",
})


@dataclass(frozen=True)
class CrossSectionalMomentumMeasure:
    symbol: str
    momentum_14d: float
    amihud_14d: float
    latest_close: float
    history_bars: int


@dataclass(frozen=True)
class CrossSectionalMomentumSignal:
    symbol: str
    direction: str
    strategy_id: str
    momentum_14d: float
    amihud_14d: float
    momentum_rank: int
    liquidity_rank: int
    universe_size: int
    bucket_size: int
    as_of_ms: int
    authority: str = AUTHORITY
    runtime_activation: str = RUNTIME_ACTIVATION
    implementation_status: str = IMPLEMENTATION_STATUS


@dataclass(frozen=True)
class CrossSectionalMomentumResult:
    as_of_ms: int
    input_symbols: int
    measured_symbols: int
    winner_symbols: tuple[str, ...]
    liquid_symbols: tuple[str, ...]
    signals: tuple[CrossSectionalMomentumSignal, ...]
    excluded: tuple[tuple[str, str], ...]


def _finite_positive(value) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("CROSS_SECTIONAL_VALUE_INVALID")
    return number


def base_asset(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if not value.endswith("USDT") or len(value) <= 4:
        return ""
    return value[:-4]


def is_stablecoin_symbol(
    symbol: str,
    *,
    stablecoin_bases=DEFAULT_STABLECOIN_BASES,
) -> bool:
    base = base_asset(symbol)
    return bool(base and base in set(stablecoin_bases))


def measure_symbol(
    *,
    symbol: str,
    daily_bars: Sequence[Mapping],
    as_of_ms: int,
    min_existence_days: int = MIN_EXISTENCE_DAYS,
) -> CrossSectionalMomentumMeasure:
    """Calculate the paper-family 14d momentum and Amihud measurements.

    Momentum:
        (P_t - P_{t-14}) / P_{t-14}

    Amihud illiquidity:
        mean(|R_t| / traded_value_t) over the same 14 daily returns.

    The latest 15 completed daily bars are needed for 14 daily return intervals.
    A longer history minimum preserves the paper's 26-week existence criterion.
    """
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        raise ValueError("CROSS_SECTIONAL_SYMBOL_INVALID")

    as_of_ms = int(as_of_ms)
    min_bars = max(FORMATION_DAYS + 1, int(min_existence_days))
    bars = [dict(row) for row in daily_bars]

    if len(bars) < min_bars:
        raise ValueError("CROSS_SECTIONAL_HISTORY_INSUFFICIENT")

    previous_open = None
    for row in bars:
        open_ms = int(row["open_time_ms"])
        close_ms = int(row["close_time_ms"])
        if (
            open_ms <= 0
            or close_ms <= open_ms
            or close_ms >= as_of_ms
            or (previous_open is not None and open_ms <= previous_open)
        ):
            raise ValueError("CROSS_SECTIONAL_HISTORY_BOUNDARY_INVALID")
        previous_open = open_ms

    recent = bars[-(FORMATION_DAYS + 1):]
    closes = [_finite_positive(row["close"]) for row in recent]
    momentum = (closes[-1] - closes[0]) / closes[0]

    daily_returns = []
    amihud_terms = []
    for index in range(1, len(recent)):
        ret = (closes[index] - closes[index - 1]) / closes[index - 1]
        volume = _finite_positive(recent[index]["quote_volume"])
        daily_returns.append(ret)
        amihud_terms.append(abs(ret) / volume)

    if len(daily_returns) != FORMATION_DAYS:
        raise ValueError("CROSS_SECTIONAL_FORMATION_INTERVAL_INVALID")

    return CrossSectionalMomentumMeasure(
        symbol=symbol,
        momentum_14d=float(momentum),
        amihud_14d=float(statistics.fmean(amihud_terms)),
        latest_close=float(closes[-1]),
        history_bars=len(bars),
    )


def build_liquid_winner_signals(
    *,
    daily_history_by_symbol: Mapping[str, Sequence[Mapping]],
    as_of_ms: int,
    winner_fraction: float = WINNER_FRACTION,
    liquid_fraction: float = LIQUID_FRACTION,
    min_existence_days: int = MIN_EXISTENCE_DAYS,
    exclude_stablecoins: bool = True,
) -> CrossSectionalMomentumResult:
    """Form the long-only liquid-winner intersection deterministically."""
    if not (0.0 < float(winner_fraction) < 0.5):
        raise ValueError("CROSS_SECTIONAL_WINNER_FRACTION_INVALID")
    if not (0.0 < float(liquid_fraction) < 0.5):
        raise ValueError("CROSS_SECTIONAL_LIQUID_FRACTION_INVALID")

    measures = []
    excluded = []

    for raw_symbol in sorted(daily_history_by_symbol):
        symbol = str(raw_symbol or "").strip().upper()

        if not symbol:
            excluded.append((str(raw_symbol), "SYMBOL_INVALID"))
            continue

        if exclude_stablecoins and is_stablecoin_symbol(symbol):
            excluded.append((symbol, "STABLECOIN_EXCLUDED"))
            continue

        try:
            measures.append(
                measure_symbol(
                    symbol=symbol,
                    daily_bars=daily_history_by_symbol[raw_symbol],
                    as_of_ms=as_of_ms,
                    min_existence_days=min_existence_days,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            excluded.append((symbol, str(exc)))
            continue

    n = len(measures)
    if n < 4:
        raise ValueError("CROSS_SECTIONAL_UNIVERSE_INSUFFICIENT")

    winner_count = max(1, int(math.floor(n * float(winner_fraction))))
    liquid_count = max(1, int(math.floor(n * float(liquid_fraction))))

    momentum_order = sorted(
        measures,
        key=lambda row: (-row.momentum_14d, row.symbol),
    )
    liquidity_order = sorted(
        measures,
        key=lambda row: (row.amihud_14d, row.symbol),
    )

    winners = momentum_order[:winner_count]
    liquid = liquidity_order[:liquid_count]

    momentum_rank = {
        row.symbol: index + 1
        for index, row in enumerate(momentum_order)
    }
    liquidity_rank = {
        row.symbol: index + 1
        for index, row in enumerate(liquidity_order)
    }
    liquid_set = {row.symbol for row in liquid}

    selected = [
        row
        for row in winners
        if row.symbol in liquid_set
    ]

    signals = tuple(
        CrossSectionalMomentumSignal(
            symbol=row.symbol,
            direction=DIRECTION,
            strategy_id=STRATEGY_ID,
            momentum_14d=row.momentum_14d,
            amihud_14d=row.amihud_14d,
            momentum_rank=momentum_rank[row.symbol],
            liquidity_rank=liquidity_rank[row.symbol],
            universe_size=n,
            bucket_size=winner_count,
            as_of_ms=int(as_of_ms),
        )
        for row in selected
    )

    return CrossSectionalMomentumResult(
        as_of_ms=int(as_of_ms),
        input_symbols=len(daily_history_by_symbol),
        measured_symbols=n,
        winner_symbols=tuple(row.symbol for row in winners),
        liquid_symbols=tuple(row.symbol for row in liquid),
        signals=signals,
        excluded=tuple(excluded),
    )
