# Phase 7.0 — Learning/Data Completeness Audit

Phase 7 must prove that learning improves trade selection.  At the `phase6b-final`
boundary, the learning/evaluation machinery already contains chronological
splits, independent market-event grouping, challenger training, calibration,
drift checks, and promotion gates.  The blocker is the completeness and meaning
of the inputs supplied to those tools.

## Source-level findings

1. `strategy/experiment_contract.py` still records `btc_regime`,
   `market_breadth`, `liquidity.spread_pct`, and
   `liquidity.quote_volume_usd` as `None`, with completeness
   `PARTIAL_PHASE5_5`.
2. The current `market_regime` / `trend_regime` fields are derived from the
   candidate symbol's structure fingerprint.  They are not a separate broad
   crypto-market regime.
3. The current model vector uses the nine symbol-local candidate features plus
   rule score, final score, direction, and pattern.  It does not consume market
   context, so merely filling context fields would not yet make model selection
   context-aware.
4. Virtual strategy cost estimation includes configured fees and slippage, but
   `spread_r` and `funding_r` remain `None`.
5. The existing reliable evaluator is already prepared to report BTC regime and
   liquidity groups, but those dimensions are mostly `UNKNOWN` while the source
   context stays incomplete.

## Null policy for Phase 7

Do not replace every `None` value mechanically.

- **Measure and populate** values that are real learning inputs and can be known
  at candidate time.
- **Keep null** when a field is genuinely not applicable (for example, a canary
  allocation identifier on a normal rules decision).
- **Keep historical unknown** when an old record cannot be reconstructed safely.
- **Never invent** missing market context.

## Phase 7 sequencing

1. Phase 7.0 — source and live-data completeness audit.
2. Phase 7.1 — versioned broad-market/BTC/breadth/liquidity context snapshot.
3. Phase 7.2 — context-aware learning feature/vector contract.
4. Phase 7.3 — dataset eligibility and historical-data policy for the new
   contract.
5. Phase 7.4 — time-safe challenger training and untouched-test validation.
6. Phase 7.5 — champion/challenger comparison by independent events and market
   regimes.
7. Phase 7.6 — calibration, drift, after-cost evidence, automatic reject/promote
   gates.
8. Phase 7.7 — prove the approved champion is suitable to become Phase 8 paper
   selection authority without changing Execution risk authority.

The audit module added in this step is observational only.  It grants no model,
paper, or execution authority.
