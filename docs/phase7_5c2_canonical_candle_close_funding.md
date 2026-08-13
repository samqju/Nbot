# Phase 7.5C.2 — Canonical Candle-Close Funding Alignment

## Runtime diagnosis

After Phase 7.5C.1, live evidence improved but 158 of 303 new virtual outcomes
still had `funding_r=null` even though Observation emitted no cost-evidence
partial/retry/failure warnings. This means the shared funding snapshots were
globally complete, while individual virtual closures could still fail the
per-trade coverage check.

The remaining mismatch was timestamp semantics. Observation captured the shared
funding snapshot at the arrival timestamp of the first tick seen in a new
five-minute bucket, while Strategy closed each symbol's previous candle at that
symbol's later websocket tick-arrival timestamp. A symbol arriving milliseconds
or seconds later could therefore have `closed_at_ms` greater than the already
complete snapshot's `funding_coverage_end_ms`. The virtual cost engine correctly
failed that trade closed and produced `funding_r=null`.

## Fix

All work representing the same completed five-minute candle now uses the exact
exchange-time bucket boundary:

- Observation funding evidence ends at `bucket * 300000`.
- Strategy passes `bucket * 300000` as the completed candle's `closed_at_ms`.

Per-symbol websocket arrival latency no longer changes the economic close time
of an already completed candle or invalidates complete funding evidence.

## Safety and learning semantics unchanged

- Funding is never guessed.
- A proven interval with no funding event produces `funding_r=0.0`.
- Actual funding events in `(opened_at_ms, closed_at_ms]` remain included.
- Incomplete funding evidence still produces `funding_r=null` and remains
  rejected by the Phase-7 ledger.
- Candidate generation, scoring, stop/target rules, labels, feature schema,
  training thresholds, time split, challenger gates, paper authority, and
  Execution risk/order logic are unchanged.

## Runtime acceptance

After deployment, measure only new outcomes. Funding-null / `INCOMPLETE_COST`
should fall sharply from the pre-fix 52.15% rate. Do not tag complete if the
new funding-null rate remains materially high; inspect genuine provider-level
partial evidence instead.
