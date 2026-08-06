# Phase 5.13 — Unified Non-Trader Operator Dashboard

## Mission

Phase 5.13 gives the operator one read-only explanation of the autonomous
learning loop. It does not create a second decision engine. The same atomic
status document powers:

- `python3 -m scripts.learning.status`;
- Telegram `/learning`;
- periodic governance-service log lines;
- `data/auto_learning_status_<environment>.json`.

The dashboard cannot train, promote, route, roll back, change risk, or submit an
order. It only reads existing append-only evidence and atomic governance files.

## Canonical status

Environment-specific paths are:

```text
data/auto_learning_status_live.json
data/auto_learning_status_testnet.json
```

The document is written with a temporary file, `fsync`, and `os.replace`. A
reader therefore sees either the previous complete status or the new complete
status, never a partially written JSON object.

## Required operator fields

The document and console view report:

- current paper champion and retained previous champion;
- current challenger and exact stage;
- completed baseline training outcomes;
- independent market-event count;
- matched forward comparisons;
- independent comparison events;
- disagreement events;
- champion and challenger after-cost average R;
- challenger lift over champion;
- current verdict;
- a plain-English reason;
- current challenger paper activation;
- current paper-routing authority;
- next automatic action;
- strategy-policy recommendation state;
- source freshness and integrity warnings;
- one-paper-position limit;
- permanent rules benchmark;
- `real_order_authority=NONE`.

Unavailable values are printed as `N/A`. Missing or malformed source files are
reported explicitly and are never replaced with invented performance values.

## Automatic refresh

The existing Phase 5.12 paper-governance service refreshes the unified document
after every controller cycle and writes a compact `AUTO_LEARNING_STATUS` line to
its journal. No additional long-running process is added.

The Telegram `/learning` command refreshes the same atomic document on demand
and returns its HTML-escaped operator view. It is read-only. Telegram listener or
status failures do not alter trading authority.

## Console

```bash
python3 -m scripts.learning.status
```

For the exact JSON:

```bash
python3 -m scripts.learning.status --json
```

## Phase 6 safety gate

The dashboard reports `READY_FOR_LIVE_SHADOW` only when:

```text
TRADING_ENV=LIVE
EXECUTION_MODE=SHADOW
```

In this mode the status states:

```text
paper position limit = 1
paper risk multiplier = 1.0
rules benchmark = PERMANENT
real order execution = IMPOSSIBLE
real order authority = NONE
```

Phase 5.13 adds no Binance signing, credentials, private order endpoint, or
exchange order-submission method.
