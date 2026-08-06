# Phase 5.6 — Automated Strategy Laboratory

## Purpose

Phase 5.6 tests a small approved set of virtual stop, target, and holding-time
policies for every already-valid strategy candidate. It is research-only.
Candidate ranking, paper-trade selection, paper risk controls, and real-order
capability are unchanged.

## Approved catalog

Every candidate keeps the existing baseline:

- `VIRTUAL_FIXED_2R_24C_V1` (or the configured baseline ID)
- 1.00× base stop distance
- +2R target
- 24 completed 5-minute candles

All patterns also receive:

- `VIRTUAL_FAST_TIGHT_1_5R_12C_V1`
- 0.75× base stop distance
- +1.5R target
- 12 completed candles

Breakout/continuation patterns additionally receive:

- `VIRTUAL_BREAKOUT_WIDE_2_5R_36C_V1`
- 1.25× base stop distance
- +2.5R target
- 36 completed candles

Reversion/reversal patterns additionally receive:

- `VIRTUAL_REVERSION_FAST_1_25R_8C_V1`
- 0.75× base stop distance
- +1.25R target
- 8 completed candles

The catalog is fixed and versioned as `PHASE5_6_APPROVED_V1`. The bot does not
create arbitrary parameter combinations.

## Cost-aware labels

Each completed variant records:

- gross exit R;
- configured entry and exit slippage in R;
- entry and exit taker fees in R;
- estimated total cost R;
- net exit R;
- net profitability.

Spread and funding are explicitly not included yet. The recorded completeness
value is `FEES_AND_CONFIGURED_SLIPPAGE_ONLY`.

Training rows use net R when it exists. Old records without net R remain
readable and continue using their earlier target field.

## Correlation control

The report shows raw candidate metrics and event-grouped metrics. Candidates
sharing the same `market_event_id` are averaged into one market-event result,
preventing a broad market move across many symbols from being treated as many
independent experiments. Duplicate candidate/variant outcomes are excluded.

## Recovery

Active Phase 5.5 virtual trades restore as legacy baseline experiments. They
finish normally but are excluded from the Phase 5.6 catalog report. New
candidates receive the approved Phase 5.6 variants. Multiple variants for one
candidate use a composite virtual-trade identity and survive restart.

## Advisory report

Run:

```bash
python3 -m scripts.learning.evaluate_strategy_lab
```

Default output:

- TESTNET: `data/strategy_lab_report_testnet.json`
- LIVE: `data/strategy_lab_report_live.json`

Possible per-variant verdicts:

- `COLLECT_MORE_DATA`
- `REJECT`
- `SHADOW_ELIGIBLE`

`SHADOW_ELIGIBLE` is advisory only. Runtime activation is disabled, paper
authority remains unchanged, and the existing rules still select paper trades.

## Default gates

- 200 completed variant outcomes;
- 50 unique market events;
- at least +0.02R average net expectancy in both raw and event-grouped results;
- no more than 30R maximum drawdown.

These are research gates, not live-money authorization.

## Configuration

Defaults work without `.env` changes. Optional overrides:

```env
VIRTUAL_LAB_ENABLED=true
VIRTUAL_LAB_CATALOG_VERSION=PHASE5_6_APPROVED_V1
VIRTUAL_LAB_MAX_ACTIVE=1500
STRATEGY_LAB_MIN_OUTCOMES=200
STRATEGY_LAB_MIN_MARKET_EVENTS=50
STRATEGY_LAB_MIN_AVG_NET_R=0.02
STRATEGY_LAB_MAX_DRAWDOWN_R=30
```
