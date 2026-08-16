# Phase 7.5D.2B.1 — Research Strategy Benchmark Catalog

## Decision

The ten original NBOT hand-written setup families are **shelved from the new
research path** after the Phase 7.5D.2A audits. They are not deleted and this
phase does not alter `RULE_SYSTEM_V1` runtime or capital authority.

The replacement research path begins with three documented strategy families:

1. liquidity-conditioned cross-sectional momentum;
2. time-series momentum / trend following;
3. conditional intraday momentum and reversal.

No catalog entry is production-approved. The catalog is metadata only.

## Why "research-backed", not "guaranteed profitable"

Published evidence is not a guarantee of future profitability. Crypto momentum
research is not unanimous across samples and methodologies. NBOT must reproduce
the signal with point-in-time data, include spread/fees/funding, use chronological
validation, and require fresh forward evidence before any authority change.

## Family 1 — Liquidity-conditioned cross-sectional momentum

Primary reference:
- Begušić & Kostanjčar (2019), *Momentum and liquidity in cryptocurrencies*,
  arXiv:1904.00890.

The paper measures 14-day cumulative return, sorts coins into loser/neutral/winner
groups, measures 14-day Amihud illiquidity, and reports that momentum is strongest
among liquid cryptocurrencies. Its liquid-winner long-only portfolio is the first
reference benchmark.

NBOT adaptation:
- preserve the 14-day ranking and liquidity conditioning;
- emit qualifying liquid winners as research candidates;
- do not pretend NBOT's eventual one-position choice is the same as the paper's
  equal-weighted portfolio.

## Family 2 — Time-series momentum / trend following

Primary references:
- Liu & Tsyvinski, *Risks and Returns of Cryptocurrency*, NBER w24877 /
  Review of Financial Studies.
- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*.
- Rozario et al. (2020), *A Decade of Evidence of Trend Following Investing in
  Cryptocurrencies*, arXiv:2009.12155.

Crypto evidence reports weekly return persistence over one- to four-week forward
horizons. The first NBOT reference benchmark therefore uses a transparent sign-of-
past-return trend signal, while the exact formation/holding protocol must be frozen
before historical testing.

## Family 3 — Conditional intraday momentum and reversal

Primary references:
- Wen, Bouri, Xu & Zhao (2022), *Intraday return predictability in the
  cryptocurrency markets: Momentum, reversal, or both*, SSRN 4080253 /
  North American Journal of Economics and Finance.
- Zaremba et al. (2021), *Up or down? Short-term reversal, momentum, and
  liquidity effects in cryptocurrency markets*, International Review of
  Financial Analysis 78:101908.

The key lesson is that intraday crypto predictability is not one universal
"momentum" or "reversal" rule. Relationships can change with liquidity, jumps,
and market state. NBOT must reproduce frozen predictor pairs and conditions before
enabling this family.

## Breakouts

"Breakout" is not introduced as a fourth independent evidence claim in D.2B.1.
A breakout can be an implementation of trend-following. If later tested, it must
be a frozen implementation underneath the time-series momentum/trend family rather
than another arbitrary hand-written setup.

## Safety boundary

This phase:
- does not generate candidates;
- does not create virtual trades;
- does not change automatic training;
- does not alter model promotion;
- does not alter `RULE_SYSTEM_V1`;
- does not touch Execution;
- grants no paper or real-order authority.

The next phase must solve the data-horizon problem before these families can be
tested fairly, because daily/weekly research cannot be represented faithfully by
the old ~50 five-minute-candle setup window.
