# NBOT V5 — Paired exit-policy research lab (Milestone 3 prototype)

This is a **research-only, synchronous, memory-bounded component**. There is
no automated V5 worker, no socket subscriber, no SQLite initialization on
import, no background service and no real-order authority. Existing V4
collector/research/paper systems are unaffected.

## Frozen experimental arms (not optimized, no claim of profit)

One qualified LONG/SHORT entry enters with exactly one fixed **initial stop at
-1R** (price difference at the entry bid/ask, excluding trading costs). Three
policy branches are evaluated against **one identical chronological 4h path**:

- `FIXED_2R_V1`: initial -1R stop and +2R take profit; if neither
  occurs, close at horizon; **no trailing**.
- `TIME_EXIT_V1`: -1R stop and four-hour horizon; **no trailing**
  and **no take profit**.
- `INTEGER_TRAIL_V1`: initial -1R stop, then at favorable integer-R
  peaks it moves to `floor(peak R)-1`, effective from the **next** tick;
  four-hour horizon, no fixed profit target.

At each chronological tick, a LONG can exit at the provided **bid**, and
a SHORT at the provided **ask**. A triggered stop uses that observed price
rather than an invented stop-limit fill. At the first eligible tick on or
within five seconds **after** the four-hour boundary, the remaining arms exit
by `HORIZON` before any stop/target is considered at the same tick. A closing
tick after the five-second grace is **not sufficient**. The path's first
tick must have aggregate ID equal to the explicitly supplied last pre-entry
anchor + 1, and every later ID must be contiguous.

Quote timestamps must not be future, must be within two seconds of each
trade, and quote update IDs must be nondecreasing. An explicit WSS disconnect,
reconnect uncertainty, aggregate-ID gap, out-of-order event, incorrect symbol,
stale quote or missing horizon witness makes **all three arms UNSCORABLE**,
even if one policy already closed. That policy prevents preferentially
discarding losing arms or comparing partial post-exit paths.

The lab always observes the shared path through four hours even if every
arm has already stopped. Each state is O(1) memory and the lab caps entries
at 100; this module contains no account access.

## After-cost settlement

A complete, caller-certified per-symbol funding-event range must be supplied
and exact event-order boundaries resolved, or results remain UNSCORABLE.
`v5_accounting.score_trade` supplies 0.05% entry and exit fee, 1 bp modeled
slippage per side, side-specific entry/exit prices and signed actual funding.
It charges funding only for settlement events strictly inside **each arm's**
distinct entry-to-exit interval. Funding coverage is a **caller proof
contract**, not something this module automatically proves from the
current collector. The full funding coverage verifier remains Milestone 4.

`persist_to_v5_ledger` appends three policy outcomes to the isolated V5
immutable ledger, always with the same complete-path SHA-256 digest. It
accepts exact retries and prevents ID mutation. The three rows are written
idempotently one at a time, **not atomically as a group**; callers must
only acknowledge/remove finalized results after all rows succeed.

## Requirements before safe deployment

- Build a V5 feed bridge that supplies anchored verified aggregate-trade
  sequences with synchronized executable bid/ask quote timestamps.
- Resolve WSS/restart continuity using prospective evidence and explicit
  persisted checkpoint identities. This pure component does **not** survive
  process restart; never infer missing ticks.
- Build end-to-end funding coverage verification and quote/settlement
  timestamp ordering; current boolean `funding_coverage_confirmed`
  is a trusted interface parameter only.
- Build durable intermediate state tracking, bounded pending result queue,
  comprehensive tests of real feed pauses and resource pressure.
- Wire qualified V5 entry decisions only after these gates, not using
  past V4 outcome paths. No service starts or VPS modification in this PR.

## Reproducibility

`PairedEntry` freezes symbol, side, entry bid/ask, initial stop, quantity,
entry-time quote and last verified aggregate-trade ID. Each `PairedTick`
contributes an append-only hash of its trade identity and executable quote.
One complete path hash is shared across all arms. Outputs retain policy ID,
exit timestamp/reason, gross/net R, fees, slippage, actual funding, MFE/MAE
in exit-quote R, final stop, event count and shared digest.

All thresholds/exit parameters in this release are *a priori experimental*
and will require genuinely new forward observations before any claim
of superior trading returns.
