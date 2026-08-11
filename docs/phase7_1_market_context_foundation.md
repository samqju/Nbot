# Phase 7.1 — Market Context Foundation

Phase 7.1 makes new candidate observations remember the broad market context
that existed when the completed five-minute decision cycle was evaluated.
It is observational only: candidate rules, scores, model vectors, paper
selection, risk, and Execution authority are unchanged.

For each ready decision cycle Observation performs two bulk public Binance
reads: 24-hour ticker statistics and book ticker data.  The snapshot records:

- broad market direction (`BULLISH`, `BEARISH`, `SIDEWAYS`);
- broad market volatility (`LOW`, `NORMAL`, `HIGH`, `EXTREME`);
- BTC regime and BTC 24-hour change;
- market breadth and coverage across the active observation universe;
- each candidate symbol's current spread;
- each candidate symbol's 24-hour quote volume.

The old symbol-local structure fields are preserved separately as
`symbol_market_regime`, `symbol_trend_regime`, and
`symbol_volatility_regime`.  New broad fields therefore no longer pretend the
candidate's own structure is the whole crypto-market regime.

If the market-context read fails or coverage is insufficient, candidate
processing continues with explicitly partial context.  This preserves trading
semantics while making incomplete evidence visible.  Later Phase 7 work may
exclude partial records from model training/validation.

Historical Phase-5.5 records are not rewritten or backfilled.
