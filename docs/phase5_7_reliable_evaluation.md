# Phase 5.7 — Reliable Evaluation Engine

Phase 5.7 is an offline, research-only evaluation layer. It does not rank live
candidates, activate a model, control paper trades, or enable real orders.

## Leakage controls

Every strategy-laboratory outcome has an observation start and a completion
 timestamp. A training or validation row is purged when its completion window
reaches the next chronological split. A configurable embargo then removes
signals near each boundary.

The fixed split remains:

```
oldest -> train
later  -> validation
newest -> untouched test
```

## Independent evidence

Candidate outcomes sharing one `market_event_id` are averaged into one market
event result. Raw candidate counts remain visible, but promotion-style gates
use event-grouped results.

## Walk-forward validation

The evaluator uses expanding windows:

```
train A       -> test B
train A+B     -> test C
train A+B+C   -> test D
```

Each fold applies the same purge and embargo protections.

## Regime diagnostics

The report separates results by:

- bullish, bearish, sideways, or unknown market direction;
- high, normal, low, or unknown volatility;
- long and short signals;
- BTC regime when available;
- liquid and less-liquid symbols when spread and quote volume are available;
- individual setup patterns.

Phase 5.5 intentionally stored unavailable BTC and liquidity context as null.
The evaluator reports those dimensions as `NOT_AVAILABLE`; it does not invent
values.

## Verdicts

Phase 5.7 may issue:

- `REJECT`
- `COLLECT_MORE_DATA`
- `OFFLINE_VALIDATED`
- `SHADOW_ELIGIBLE`

The common verdict vocabulary also includes `PAPER_CANARY_ELIGIBLE` and
`PAPER_CHAMPION_ELIGIBLE`, but the offline engine cannot issue them. Those
require later forward-shadow, paper-canary, monitoring, and rollback phases.

A `SHADOW_ELIGIBLE` verdict means only that a frozen challenger may begin a
fresh forward comparison. Paper authority remains unchanged.

## Command

Build the dataset first, then run:

```bash
python3 -m scripts.learning.evaluate_reliable
```

The environment-specific report is written to:

- `data/reliable_evaluation_report_testnet.json`, or
- `data/reliable_evaluation_report_live.json`.
