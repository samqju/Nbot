# NBOT V5 — clean-slate foundation (PR 1)

V5 is a **separate observation/research experiment**. This release does **not**
install a service, enable a timer, train a model, alter Telegram reporting,
admit a baseline Champion, or submit orders. Its order authority is `NONE`.
Existing V4 data, decisions and process state remain untouched.

## Immutable accounting contract

- Fee rates: entry `0.0005` (0.05%), exit `0.0005` (0.05%), exactly
  as confirmed. The exit fee is charged on the *exit* notional.
- Initial modeled slippage: `0.0001` per side (1 basis point, 0.01%).
  This is an assumption to evaluate, not a claim about real fills.
- Entry and exit **fill** prices already reflect bid/ask spread:
  LONG buy ask / sell bid; SHORT sell bid / buy ask. Do not charge spread twice.
- The initial price stop must be exactly the *definition* of `-1R`:
  `1R_quote = abs(entry_fill - initial_stop) * quantity`.
  Subsequent exits can lose worse than -1R after fees, slippage and gaps.
- `gross_quote = direction * (exit_fill - entry_fill) * quantity`;
  `net_quote = gross_quote - entry_fee - exit_fee - modeled_slippage + funding_cashflow`.
  Divide by `1R_quote` for R outcomes. 0.10% in fees is **not** 0.10R.
- Funding is derived from *confirmed* symbol-specific settlements with mark
  prices, not forecast snapshot rates. Positive funding rate: LONG pays, SHORT
  receives; negative rate: vice versa. Missing funding coverage is an error,
  **not** a fabricated zero charge. No fixed eight-hour funding assumption.
- Contract counts settlements only **strictly inside** entry and exit
  timestamps. Exact-boundary settlement chronology is ambiguous and rejected
  pending exchange-evidence resolution.
- The scorer assumes that the caller has independently verified price-path
  continuity, fill chronology and complete funding coverage. It does **not**
  prove those conditions or check which exit policy triggered.
- Old V4 outcomes retain their historical V4 fee/cost version, unchanged.

## Evidence isolation and safety

`V5EvidenceStore` defaults to `data/observation/v5/evidence.db`, never
the V4 database. Constructor/import do not write files; initialize is explicit.
SQLite evidence entries are append-only and content-addressed, accepting an
identical retry but refusing decision-ID or outcome-ID payload collisions.
One decision may have several independently scored exit-policy outcomes.
If evidence is missing, store an `UNSCORABLE` result with a reason; do not
manufacture R. No code path has exchange order authority.

## Next PRs (not implemented here)

1. Strict, explainable and **directional** candidate qualification, with
   explicit abstention; 100 becomes a capacity limit, not a fill target.
   Keep a separately marked exploration pool and rejected-candidate evidence.
2. Three future-data exit policies for identical qualified entries: fixed
   target, fixed-time, and current trailing baseline, all starting at -1R.
3. Chronological/purged ranking plus after-cost and severe-loss targets;
   explicit no-trade calibration and no automatic first-generation exception.
4. Forward paper contest and Champion governance on distinct held-out periods.

**Cutover:** Review and pass all tests first. Preserve V4 databases and WAL/SHM
with consistent SQLite backups before planned retirement of V4 research/paper
processes. Keep the existing collector running. Never restart live WSS research
paths casually: interrupted hypotheses can become unscorable.
