"""Phase 7.5D.2B.1 research strategy benchmark catalog.

This module is metadata only. It does not generate candidates, create virtual
trades, alter RULE_SYSTEM_V1, activate a model, or grant any order authority.

The catalog deliberately distinguishes:
- externally documented research evidence;
- NBOT-specific adaptations required by its one-position architecture;
- protocols that still need to be implemented and validated.

No strategy in this catalog is production-approved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


RESEARCH_ONLY = "RESEARCH_ONLY"
NO_ORDER_AUTHORITY = "NONE"
LEGACY_SHELVED = "LEGACY_SHELVED_FROM_NEW_RESEARCH"


@dataclass(frozen=True)
class ResearchStrategySpec:
    strategy_id: str
    family: str
    evidence_grade: str
    authority: str
    runtime_activation: str
    source_refs: Tuple[str, ...]
    evidence_summary: str
    signal_protocol: str
    direction_protocol: str
    horizon_protocol: str
    liquidity_protocol: str
    nbot_adaptation: str
    required_data: Tuple[str, ...]
    implementation_status: str = "CATALOG_ONLY_NOT_IMPLEMENTED"


LEGACY_SETUP_IDS: Tuple[str, ...] = (
    "PULLBACK_CONTINUATION",
    "MEAN_REVERSION",
    "FAKE_BREAKOUT",
    "LIQUIDITY_SWEEP",
    "SUPPORT_BOUNCE",
    "RESISTANCE_REJECTION",
    "MOMENTUM_EXHAUSTION",
    "TRIANGLE_BREAKOUT",
    "RANGE_BREAKOUT",
    "TREND_REVERSAL",
)


RESEARCH_STRATEGY_CATALOG: Tuple[ResearchStrategySpec, ...] = (
    ResearchStrategySpec(
        strategy_id="CSM_LIQUID_WINNERS_14D_V1",
        family="CROSS_SECTIONAL_MOMENTUM_WITH_LIQUIDITY",
        evidence_grade="PRIMARY_CRYPTO_RESEARCH_BACKED",
        authority=NO_ORDER_AUTHORITY,
        runtime_activation="DISABLED",
        source_refs=(
            "Begušić & Kostanjčar (2019), Momentum and liquidity in cryptocurrencies, arXiv:1904.00890",
            "Liu, Tsyvinski & Wu (2022), Common Risk Factors in Cryptocurrency, Journal of Finance / NBER w25882",
        ),
        evidence_summary=(
            "Published crypto research reports cross-sectional momentum, with "
            "stronger momentum evidence among liquid cryptocurrencies. The "
            "Begušić-Kostanjčar reference uses 14-day cumulative return and "
            "14-day Amihud illiquidity sorts, with liquid winners as a "
            "long-only research portfolio."
        ),
        signal_protocol=(
            "At each research rebalance, rank the eligible universe by prior "
            "14-day cumulative return and 14-day Amihud illiquidity. Research "
            "candidate set = upper 30% momentum names within the lower 30% "
            "illiquidity (most liquid) group."
        ),
        direction_protocol="LONG_ONLY_FOR_FIRST_REFERENCE_REPLICATION",
        horizon_protocol="14_DAY_FORMATION_AND_14_DAY_REBALANCE_REFERENCE",
        liquidity_protocol=(
            "Use dollar-volume-based Amihud illiquidity; retain the most liquid "
            "30% before selecting momentum winners."
        ),
        nbot_adaptation=(
            "NBOT may emit each qualifying liquid winner as a research candidate. "
            "Because NBOT executes one position rather than an equal-weighted "
            "portfolio, candidate ranking is a later, separate experiment and "
            "must not be claimed as an exact paper replication."
        ),
        required_data=(
            "14d price history",
            "14d quote/dollar volume history",
            "point-in-time eligible universe",
            "spread",
            "fees",
            "funding",
        ),
    ),
    ResearchStrategySpec(
        strategy_id="TSMOM_WEEKLY_SIGN_V1",
        family="TIME_SERIES_MOMENTUM_TREND",
        evidence_grade="PRIMARY_CRYPTO_PLUS_CLASSIC_TSMOM_RESEARCH_BACKED",
        authority=NO_ORDER_AUTHORITY,
        runtime_activation="DISABLED",
        source_refs=(
            "Liu & Tsyvinski (2021), Risks and Returns of Cryptocurrency, Review of Financial Studies / NBER w24877",
            "Moskowitz, Ooi & Pedersen (2012), Time Series Momentum, Journal of Financial Economics",
            "Rozario et al. (2020), A Decade of Evidence of Trend Following Investing in Cryptocurrencies, arXiv:2009.12155",
        ),
        evidence_summary=(
            "Crypto research reports that current weekly Bitcoin returns "
            "positively predict one- to four-week-ahead returns. Time-series "
            "momentum is also a well-established trend-following family across "
            "liquid futures markets, and crypto-specific work reports "
            "walk-forward trend-following evidence."
        ),
        signal_protocol=(
            "First reference benchmark uses the sign of completed prior-period "
            "return as the trend signal. Multi-lookback or adaptive trend "
            "variants are explicitly deferred until this simple benchmark is "
            "measured."
        ),
        direction_protocol=(
            "LONG when the frozen lookback return is positive; SHORT when it is "
            "negative. Zero/insufficient-history produces no candidate."
        ),
        horizon_protocol=(
            "WEEKLY_REFERENCE_HORIZON; exact formation/holding variants must be "
            "frozen before backtesting and must not be optimized on the current "
            "three-day Phase-7 ledger."
        ),
        liquidity_protocol=(
            "Only symbols passing NBOT's point-in-time liquidity/spread universe "
            "filter may create research candidates."
        ),
        nbot_adaptation=(
            "The sign rule is a transparent benchmark implementation of the "
            "time-series momentum family. Crypto paper evidence motivates the "
            "horizon, but NBOT must validate the exact implementation itself."
        ),
        required_data=(
            "multi-week price history",
            "point-in-time eligible universe",
            "spread",
            "fees",
            "funding",
            "realized volatility",
        ),
    ),
    ResearchStrategySpec(
        strategy_id="INTRADAY_CONDITIONAL_MOM_REV_V1",
        family="CONDITIONAL_INTRADAY_MOMENTUM_REVERSAL",
        evidence_grade="PRIMARY_CRYPTO_INTRADAY_RESEARCH_BACKED",
        authority=NO_ORDER_AUTHORITY,
        runtime_activation="DISABLED",
        source_refs=(
            "Wen, Bouri, Xu & Zhao (2022), Intraday return predictability in the cryptocurrency markets: Momentum, reversal, or both, North American Journal of Economics and Finance / SSRN 4080253",
            "Zaremba et al. (2021), Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets, International Review of Financial Analysis 78:101908",
        ),
        evidence_summary=(
            "High-frequency crypto research reports both intraday continuation "
            "and reversal rather than one universal direction rule, with the "
            "relationship changing with liquidity, jumps and market conditions."
        ),
        signal_protocol=(
            "Do not hard-code a generic reversal or momentum trigger. First "
            "reproduce predetermined hourly return-pair predictors and their "
            "conditioning variables from the research protocol; only statistically "
            "specified pairs become research candidates."
        ),
        direction_protocol=(
            "Direction follows the frozen sign of the published/reproduced "
            "predictive relationship: positive relation => continuation; negative "
            "relation => reversal."
        ),
        horizon_protocol=(
            "INTRADAY_HOURLY_REFERENCE_FROM_5M_SOURCE_CANDLES; half-hour variants "
            "remain separate research variants if later justified."
        ),
        liquidity_protocol=(
            "Record and stratify by contemporaneous liquidity; do not assume the "
            "same predictor works in every liquidity state."
        ),
        nbot_adaptation=(
            "This family fits NBOT's short-horizon architecture better than the "
            "weekly families, but the exact predictor pairs must be reproduced "
            "before any candidate generator is enabled."
        ),
        required_data=(
            "5m candles aggregated to hourly returns",
            "intraday jump measure",
            "liquidity measure",
            "spread",
            "fees",
            "funding",
            "market and BTC regime",
        ),
    ),
)


def get_research_strategy_catalog() -> Tuple[ResearchStrategySpec, ...]:
    """Return the immutable Phase 7.5D.2B.1 research-only catalog."""
    return RESEARCH_STRATEGY_CATALOG


def legacy_setup_status() -> dict[str, str]:
    """Return legacy setup research status without changing runtime behavior."""
    return {setup_id: LEGACY_SHELVED for setup_id in LEGACY_SETUP_IDS}
