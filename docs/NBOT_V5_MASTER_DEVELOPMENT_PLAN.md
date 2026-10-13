# NBOT V5 — Master Development Plan and Progress Ledger

> **Permanent handover document, updated in the same pull request as every V5 upgrade.**
> This is the single source of truth for scope, implementation status, rejected
> ideas, releases, validation gates, operational handovers, and pending work.
> No assistant chat history is needed to reconstruct the development plan.
>
> Repository: `samqju/Nbot`. Branch: `main`; new work goes through reviewed PRs.
> First PR: [#30](https://github.com/samqju/Nbot/pull/30).
> Last update: **2026-10-12**, PR #38 two P1 audit fixes verified on code head `64abdc6f` ([1,490 regression tests passed](https://github.com/samqju/Nbot/actions/runs/38280766303)); second independent audit pending.
>
> **Safety invariant: Research / Paper only. No order authority.**
> No change to Execution role, private Binance credentials or real-money order
> permissions is part of this roadmap. A future user-authorized live-execution
> project requires a separately approved, independently assessed plan.

## How to resume work after a new chat or context window

1. Read **this entire document**, then
   [the V5 accounting contract](V5_CLEAN_SLATE_FOUNDATION.md).
2. Check latest merged `main`, latest open PR, CI status, and recent PR changes.
3. Read **Current status** and **Milestone register** below.
4. Before changing code, identify exactly one target milestone, its contracts,
   tests, dependencies and roll-back procedure.
5. On EVERY PR that changes `nbot/observation/v5_*`,
   `tests/test_v5_*`, `deploy/observation/{run_v5_,v5_}*` or
   `docs/V5_*`, update **this file in the same PR** (a CI gate checks).
6. Change statuses and completion evidence only when truly verified. Never
   call a PR "complete" when its checks are running, or claim deployed code
   based merely on a GitHub merge.
7. Preserve older entries in the Decision log; add new entries, do not rewrite
   the rationale after the fact.
8. If a VPS has not verified a deployment, explicitly label it **not deployed**.
9. No environment may place an actual order without a separately approved
   execution design and explicit user authorization.

## Current status — 2026-10-13

**PR #38 V3 remediation supersedes the earlier path/funding certification claims
below.** The second independent audit failed H1–H5 (missed 50ms stop,
post-decision snapshot, reusable contradicted funding, premature horizon sealing,
lost stop after failed persistence), plus M1 snapshot supervision and M2 admission
race. The audited head was `9a8163c9c7d38cccdb2ae215746492e3d2898896`; its
1,490-test CI ([38281033032](https://github.com/samqju/Nbot/actions/runs/38281033032))
did not establish those missing properties. The supplied report is preserved in
[NBOT_PR38_SECOND_INDEPENDENT_AUDIT.md](NBOT_PR38_SECOND_INDEPENDENT_AUDIT.md).

V3 offers isolated **OBSERVED_STREAM** diagnostics only. Certified path scoring,
training, Champion/promotion and complete-path performance claims are unavailable.
Funding totals/net R stay unknown; two matching REST responses verify response
agreement, not publication finality. Legacy SCORED rows retain their historical
meaning and are excluded from certification. V1/V2 live checkpoints are rejected;
start V3 at a new filename and preserve old evidence. No V4/VPS changes or orders.

Implemented: atomic causal admission (all acquisition/snapshot/book-validation
watermarks), provisional horizons with later quarantine, durable funding
revocations, fail-closed persistence latch with explicit invalidating recovery,
restart quarantine, supervised snapshot tasks/deadlines, byte-aware buffers,
off-loop writes, chained event journaling with periodic checkpoints, atomic paired
publication and explicit V5 connection closure. See
[the actual architecture](V5_LIVE_EVIDENCE_BRIDGE.md) and
[closure matrix and verification record](V5_PR38_REMEDIATION_AUDIT.md).

Initial remediation verification: 90 focused V5 tests passed in 121.010s on an
isolated Windows host. Full final-head regression/CI and fresh-agent review are
tracked in the closure report; do not infer completion from this interim count.
Desktop benchmark: 300 mutations, 20 symbols, 1,000 levels/side, no hypotheses;
61.255 events/s, p95 18.017ms, p99 21.477ms, restart 0.120s, traced peak 1.085MB.
This is not measured process RSS or a one-GB VPS acceptance result.

**Next milestone:** independently review the reduced observed-research contract;
then design bounded archive/rotation, shared-IP request budgets and authorized
isolated multi-day capture/target-host resource acceptance. No available public
feed proof currently unlocks complete-path ML labels. Certified learning remains
blocked pending a technically sufficient new source/proof contract.

| Item | Status | Evidence / outstanding action |
|---|---|---|
| Legacy V4 main | IN PRODUCTION (Observation only) | `b1a3c4a` installed on Observation VPS; services active at last reported preflight |
| V4 live collector | PRESERVE | 60-symbol configuration, do not interrupt |
| V4 research factory | RUNNING (legacy) | 100 concurrent virtual paths; restarts can make paths unscorable |
| V4 paper contest | RUNNING (legacy) | Gen-1 contest; no Champion; not promoted |
| V4 raw and research DB | PRESERVE | `data/observation/v4` ~26 MiB at last preflight; never overwrite/delete |
| V5 Milestone 1 | MERGED, NOT DEPLOYED | PR #30 merged as `2b6bc33acf31978459cbca105b3ea1979562df30`. 1,428 tests passed on PR head and merged main (run 38250307646) |
| V5 Milestone 2 | PROTOTYPE MERGED / NOT DEPLOYED | PR #32 merge `19eec7f9436f9cd1c3b2acae3dcc008d8d7f574d`; 1,436 tests passed on PR head; metadata/depth and prospective validation remain outstanding |
| V5 market-quality bridge | PROTOTYPE MERGED / NOT DEPLOYED | PR #34 merge `0ad04e711d79c46047fa952cf249f3f429976ada`; 1,441 tests passed on PR head; merged-main full regression succeeded ([run 38259054293](https://github.com/samqju/Nbot/actions/runs/38259054293)) |
| V5 Milestone 3 | PROTOTYPE MERGED / NOT DEPLOYED | PR #36 merge `bece0864648cc3bdce0d24dbf842bbb3ebd6552f`, 1,456 clean PR-head tests, no worker; requires joint WSS feed/checkpoints/funding coverage |
| V5 live evidence/recovery | PR OPEN / NOT DEPLOYED | PR #38 implementation head `0f158bad7b869c45b3886977c2e086f6f20c8e39`: 1,485 clean regression tests passed ([run 38272931564](https://github.com/samqju/Nbot/actions/runs/38272931564)); routed WSS, quote-only exits, depth synchronization, REST trade recovery, checkpoints and public settlement reconciliation; later documentation-head CI must separately pass |
| V5 deployed | NO | Neither new services nor V5 data collection started |
| V5 champion | NONE | First generation must qualify, no baseline exception |
| V5 order authority | NONE | Permanently isolated in the V5 research/paper scope |

Last reported Observation VPS: about 954 MiB RAM total, 444 MiB
available, 1.9 GiB swap available, 90 GiB free disk. Resource numbers are
observations, not future availability guarantees. Do not run another full
100-position WSS factory in parallel indefinitely on a one-GB instance.

### Previous research evidence (legacy V4, not V5 training data)

- Initial 4,124 matured hypotheses: **-0.5224R average NET**,
  **-0.0663R average GROSS**, **0.4561R average modeled costs**, 22.9%
  positive net. 4,119 STOP and 5 HORIZON, where STOP also includes
  profitable trailing exits.
- Expensive low-ATR instruments can incur enormous fees expressed in R:
  PAXG worst -32.244R NET but +26.941R GROSS and 59.185R modeled costs.
  A cost-to-risk filter is worth studying but **not** sufficient: even the
  <=0.15R modeled-cost cohort has -0.195R mean NET and -0.102R mean GROSS.
- All seven setup families negative, matched technical setups historically
  weaker than unmatched in unadjusted aggregate; this does NOT establish
  causality or that every setup is unprofitable across future regimes.
- Both LONG and SHORT averages approximately -0.52R in legacy research.
- Gen-1 research validation -0.5582R / 25.0% positive / 8 validation events;
  Gen-2 -0.7124R / 13.6% / 22 events; Gen-3 -0.5813R / 20.6% / 34.
  Gen-1 was admitted to paper ONLY by a baseline exception; later models
  rejected. Early Gen-1 forward paper: 22 trades, -6.729R cumulative,
  -0.306R average, 18.2% positive. These metrics are snapshots, not live status.
- No guarantee of profitability; V5 must demonstrate new after-cost
  out-of-sample performance. V4 observations inform hypotheses and guardrails
  only. Do not silently pool V4 rows into V5 training sets.

## Design principles and non-negotiable invariants

1. **Entry quality before volume.** Maximum 100 concurrently active V5
   hypothesis *entries*, but never a quota: zero good opportunities means
   zero qualified entries. Do not fill vacancies with invented "model only"
   trades. Separately marked, bounded exploratory samples may observe
   rejected ideas to learn about false positives/negatives.
2. **Causality.** Features computed using only market evidence captured at
   or before decision time, complete and provably point-in-time 5-minute
   events. Never train on future features, leaked labels or overlapping
   train/validation outcome horizons.
3. **Independent labeling.** Model learns from gross/net returns and
   structurally defined entry/exit policies. Retain measured losing examples.
   Rejected candidates must be recorded with reason and sampling eligibility.
4. **Truthful fills/costs.** LONG enters at ask / exits at bid; SHORT enters
   at bid / exits at ask. Charge fees on actual entry and exit notionals.
   Do not double-count spread or slippage. Funding is event-specific,
   direction-signed; unproven funding coverage marks scoring unavailable.
5. **Initial -1R stop.** Initial stop-loss price is frozen and risk amount
   defined at entry for every exit-policy experiment. Prices may overshoot
   stops and all-in net loss may exceed -1R.
6. **Paired exit studies.** Same entry receives independently tracked
   policies on one continuously proven WSS/aggTrade path, each scored after
   costs, with clear accounting for fees, funding and any missing evidence.
7. **No hidden hindsight.** Any threshold developed by inspecting current
   legacy results must be evaluated as a new hypothesis on *fresh, prospective*
   data, alongside a comparable baseline.
8. **No-trade is valid.** A ranking score is not itself a profitability
   forecast. Abstention requires validated expected-value/calibration logic
   on held-out chronological data.
9. **Immutable evidence.** Freeze selection reason, symbol, direction, event,
   causal feature digest, initial risk, entry quote, alternative policies,
   policy version, trade path quality, and settlement evidence.
10. **Fail closed.** WSS gaps, stale/ambiguous snapshots, mismatched symbol,
    missing funding coverage, restart path loss or decision-ID collision must
    never be converted to a fictitious result. No deleting/restarting state
    to manufacture better training counts.
11. **No automatic promotions.** Candidate generations must pass research
    qualification and separate forward paper testing. No first-generation
    research exception. Champion requires explicit review.
12. **No live orders.** V5 research and V5 paper components do not expose
    usable order APIs and never inherit execution secrets. Preserve role
    separation: Observation VPS vs Execution VPS.
13. **Small host first.** Streaming O(active hypotheses) replay state,
    bounded WSS shards, disk budgets, RAM/CPU ceilings, no huge in-memory
    dataframe on the one-GB Observation VPS.
14. **Reproducibility.** Every new policy version, trained artifact and
    decision carries stable IDs/digests; repeatable tests and independent
    audit queries, with full diagnostic errors and clean successful CI dots.

## Milestone register — start to finish

Status words: `PLANNED`, `IN PROGRESS`, `PR OPEN`,
`MERGED`, `DEPLOYED`, `VERIFIED`, `BLOCKED`. These are
not interchangeable.

### Milestone 0 — Legacy investigation and safety baseline

**Status: VERIFIED (analysis only, 2026-10-12).**

- [x] Identify V4 candidate selector behavior: recognized setups and count
      priority, 100/100 virtual hypothesis refill, LONG/SHORT independent.
- [x] Review first three generations and initial forward-paper report.
- [x] Audit research R gross/net, cost buckets, exit types, symbols, families.
- [x] Confirm V4 collector and three main services reported active.
- [x] Confirm GitHub main release and V4 databases not erased.
- [ ] Independently reconcile worst low-ATR observations against the exact
      raw candle, mark price, quote timestamp and min tick-size requirements.
- **Gate to progress:** do not assume old V4 metrics are a V5 backtest.

### Milestone 1 — Isolated V5 foundation, accounting and durable roadmap

**Status: MERGED — PR [#30](https://github.com/samqju/Nbot/pull/30), merge SHA `2b6bc33acf31978459cbca105b3ea1979562df30`.**
**Code not yet deployed to Observation VPS.**

- [x] New namespaced V5 research-only source module.
- [x] V5 database path restricted to dedicated V5 folder;
      import and construction cause no database writes.
- [x] New immutable decision and multiple exit-outcome records;
      exact retry idempotent; mismatched ID payload rejected.
- [x] Versioned fee: 0.05% open, 0.05% close; initial modeled slippage
      0.01% each side; price inputs include spread; no double charge.
- [x] Signed, symbol-checked, chronological funding settlements requiring
      explicit evidence that funding coverage is complete; boundary
      ambiguities fail closed.
- [x] Freeze initial -1R price stop for accounting, retain quantities,
      entry/exit prices/times, gross/net/cost/funding R and settlement records.
- [x] Order-authority stub raises; no exchange operations.
- [x] Tests for fee-vs-R, LONG/SHORT, funding signs, ambiguous
      boundaries, immutable ledger and path isolation.
- [x] Quiet unittest runner: clean progress on passing tests; reproduce
      captured stdout/stderr only when suite fails.
- [x] CI gate requires this roadmap to change with every V5-related PR.
- [x] Write this extensive operational/development handover.
- [x] Latest PR-head full CI was **green**: [1,428 tests, OK](https://github.com/samqju/Nbot/actions/runs/38249999802).
- [x] Merge PR #30; merge SHA above. No independent human peer review claimed.
- [x] Merged-main full CI [run 38250307646](https://github.com/samqju/Nbot/actions/runs/38250307646) is green (1,428 tests).
- [ ] Plan safe VPS code-only pull at an appropriate time; NO restart.
- **Acceptance:** green CI, immutable ledger tests, fee/funding tests,
  no order authority, V4 untouched. Merely merging does not deploy.

### Milestone 2 — Explainable qualified entry and separate exploration

**Status: PROTOTYPE MERGED — [#32](https://github.com/samqju/Nbot/pull/32), merge SHA `19eec7f9436f9cd1c3b2acae3dcc008d8d7f574d`; [#34](https://github.com/samqju/Nbot/pull/34) market-quality bridge merge SHA `0ad04e711d79c46047fa952cf249f3f429976ada`. NOT DEPLOYED.**

Verified PR-head CI: [1,436 tests, OK](https://github.com/samqju/Nbot/actions/runs/38256910103). This does **not** close Milestone 2: point-in-time instrument metadata/depth and prospective validation are still pending. Merge-main CI must separately pass.

- [x] Implement prototype strict directional entry families, independently of V4; exact setup thresholds frozen for future evaluation.
- [x] Build pure candidate evaluation and abstaining capacity planner (no model or order authority).
- [x] Add read-only SQLite event/history adapter with causal provenance checks.
- [x] Reject invalid/stale symbol metadata; instrument metadata source remains future work.
- [x] Add deterministic bounded exploration with no qualification of near misses.
- [x] Create deterministic tests for positive/negative sides, bad data, abstention, economics and active capacity.
- [x] Formalize initial **experimental** entry families: continuation/pullback in trend,
      level-breakout/retest, bounded mean-reversion/rejection.
      Avoid selecting solely by count of overlapping indicators.
- [ ] Define market prerequisites: complete observed 5m event, causal
      4h history, valid bid<ask, stable symbol metadata and permissible
      tick sizes, minimum volume/depth, spread/funding quality.
- [x] Define directional entry triggers that use no future candles.
      LONG and SHORT get separate rationale, not automatic mirrored entry.
- [ ] Define regime classification from closed candles (trend,
      range, volatility/dispersion and market-relative context), with
      explicit `UNKNOWN` class and no retrospective regime labels.
- [x] Candidate lifecycle model: `SCANNED`, `QUALIFIED`,
      `REJECTED` with reason, `EXPLORATORY`, `SELECTED`.
- [x] Implement **abstention**: no qualifying candidates => open none.
      100 is a cap, not an obligated target. Preserve same-symbol/side
      exclusivity within qualified research.
- [x] Explore separately and transparently with deterministic reproducible
      sampling and capped concurrent experiments; log sampling probability
      to understand selection bias.
- [ ] Test candidates for repeated signals, BTC/macro correlation, unfair
      symbol concentration and inadvertent setup leakage.
- [x] Backward-compatible read-only candle/snapshot access to existing collector.
      Never mutate the collector's raw evidence.
- [x] Version decision explanation/feature digest and candidate universe.
- [x] Implement **opt-in credential-free public market-quality capture** for Binance exchangeInfo and depth with time-bounded parser; no collector mutation. PR #34 merged; [1,441 passing tests](https://github.com/samqju/Nbot/actions/runs/38258716067).
- [ ] Persist independently proven provenance and capture exchange metadata contemporaneously with future V5 decision timestamps before considering Milestone 2 fully live-ready.
- [x] Reject candidates without timely, matching and sufficiently deep **prospective** order-book snapshot; use a separately quoted $100 hypothetical probe, not a claimed live fill. (PR #34)
- [ ] Develop and validate market correlation/exposure caps, stronger full-depth book checks, and independent end-to-end causal snapshot capture.
- [ ] Independently evaluate thresholds and selection bias on fresh, unseen V5 observations.
- **Acceptance:** deterministic fixture-based examples and negative cases,
  no raw data writes, no magic slot refill, complete reject reasons.

### Milestone 3 — Path-complete paired exit-policy lab

**Status: PROTOTYPE MERGED — [#36](https://github.com/samqju/Nbot/pull/36), merge SHA `bece0864648cc3bdce0d24dbf842bbb3ebd6552f`. NOT DEPLOYED.**

Verified PR #36 head [CI run 38264782962](https://github.com/samqju/Nbot/actions/runs/38264782962): **1,456 tests passed, clean dots/OK**. Merged-main [CI run 38265101835](https://github.com/samqju/Nbot/actions/runs/38265101835) also passed the full regression suite. PR #38 now implements WSS quote-only stop evidence, checkpoints and public funding reconciliation. Its first independent review at `7d4fb915` found two blocking P1 defects: older depth quote overwrote newer bookTicker entry anchor; missing bookTicker source could still yield all three SCORED outcomes. **Do not merge** until corrected-head CI and second independent audit confirm these cases fail closed. This milestone is **not fully complete**: prospective evidence validation, host performance and real-time forward study remain outstanding.

PR #38 validation includes 29 new focused tests: causal capture receipts, routed transport/snapshot
buffering, trade recovery, quote-only LONG/SHORT stops, depth/horizon watermarks,
restart/partial recovery, failed writes/corruption/concurrent writers, permanent
decision IDs, pending ledger retries and settlement funding cases. Latest PR-head
full regression CI remains a release gate. Implementation head `0f158bad` passed
**1,485 tests, clean dots/OK**, including the roadmap gate, in
[run 38272931564](https://github.com/samqju/Nbot/actions/runs/38272931564).
This subsequent documentation-only revision requires its own latest-head CI;
no deployment or merge is claimed here. The remediation adds independent stream source tracking, conservative ticker-coverage watchdog and exact reproductions, but does not prove all sub-30-second silent packet loss detectable.

- [x] Implement research-only three-armed incremental tick state on a single shared entry and future market path.
- [x] Require anchored consecutive aggregate IDs, monotonic timestamps, fresh executable quotes, closing horizon witness; errors make all three arms unscorable.
- [x] Account independently for per-arm exit prices and signed funding through shared V5 accounting contract.
- [x] Keep constant-memory per hypothesis and capacity 100; bound the pending persistence cache at 100 completed sets, rejecting overflow without discarding active state; append immutable three-arm outcomes with shared SHA-256 digest.
- [x] Implement opt-in joint WSS quote/trade bridge, quote-only stops, durable checkpoint and public settlement-range reconciliation in PR #38. See [contract and limits](V5_LIVE_EVIDENCE_BRIDGE.md).
- [ ] Verify prospective host throughput, clock/stream behavior, funding publication timing and coverage before any VPS activation. PR #38 is not deployment or full Milestone 3 completion.

- [x] Retain starting stop at -1R for **all** policy arms (prototype).
- [x] Arm A: initial -1R stop, +2R target, fixed horizon (experimental).
- [x] Arm B: initial -1R stop, no target/trailing, fixed horizon.
- [x] Arm C: existing whole-R trailing, initial -1R stop, fixed horizon.
- [x] Use same entry, same quantity and same chronological verified
      trade feed for every arm; no path reconstruction from early
      stopped trade only.
- [ ] Parameterized horizons only from prespecified experimental grid,
      not tuned against the holdout.
- [x] Side-consistent fills at bid/ask; stop crosses on tick; handle
      gap/jump, simultaneous triggers and exchange timestamp ambiguity.
- [x] Each arm has its own outcome, exit timestamp/reason, max favorable
      and adverse excursion, initial risk, fees, slippage and funding.
- [x] Interface: disconnected WSS, unproven trade ID sequence or restart interrupt
      produce UNSCORABLE for affected arms.
- [x] Implement WAL/FULL atomic journal+checkpoint, preserved frozen arms and cursors, concurrent-writer rejection and durable pending results (PR #38). Restarts invalidate unfinished quote paths; REST recovers available aggregate IDs only, never historical quotes. Capacity remains 100 entries with 3 arms.
- [ ] Add real-host memory/CPU pressure tests, durable pending-result queues and bounded WSS behavior. (Unit stream-memory and capacity tests in PR #36.)
- **Acceptance:** deterministic, paired comparisons on identical future
  market events and strict evidence-integrity tests.

### Milestone 4 — Funding coverage bridge, risk economics and data audit

**Status: PLANNED; base pure accounting contract exists in PR #30.**

PR #38 implements a separate credential-free public funding-history bridge:
two exhaustive agreeing reads after publication grace, settled rate/time/charge
mark provenance, per-arm coverage, boundary/duplicate/conflict rejection.
This verifies venue settlement evidence for research; it does not verify private
account cash income or integrate legacy collector funding tables. Host timing,
schedule variations and prospective reconciliation remain acceptance gates.

- [ ] Map collector's `funding_events` and `funding_sync_ranges`
      to entry/exit time windows with symbol-specific completeness.
- [ ] Verify settlement rate, event timestamp and mark price provenance.
      Missing actual funding evidence is not zero funding.
- [ ] Clarify equality at entry/exit funding boundaries with event-order
      documentation and conservative fail-closed policy.
- [ ] Cross-check price levels and minimum tick size/quantity filters.
- [ ] Enforce prospective economic eligibility such as cost-to-risk ceiling,
      with thresholds selected before forward test (0.15R and 0.30R are
      examples, NOT approved optimal thresholds).
- [ ] Record rejected candidates and reasons and compare high- vs
      low-cost cohorts prospectively.
- [ ] Exclude all unscorable/gapped paths from scored target labels and
      separately report selection/evidence attrition.
- **Acceptance:** complete end-to-end reconciliation with independently
  computed fees and funding on deterministic multi-event cases.

### Milestone 5 — Entry learner, severity-sensitive objectives and abstention

**Status: PLANNED.**

- [ ] Candidate features: frozen causal price, trend, volume,
      spread, volatility, risk/cost and market-regime context.
- [ ] Label direction+setup outcomes after costs in actual R, preserving
      severe loss scale (do not collapse -0.6R and -32R into equivalent
      undifferentiated "bad" categories).
- [ ] Compare simple transparent baselines with regularized models;
      start with interpretable gate plus LightGBM only if data justifies it.
- [ ] Correct for setup overlap, multiple correlated simultaneous trades,
      outcome-driven selection, class imbalance and symbol dominance.
- [ ] Use group-by-market-event weighting and cluster sensitivity rather
      than assuming every hypothesis is independent.
- [ ] Train conditional forward policy for **select or abstain**; rank
      score cannot be treated as a probability or expected return without
      separate calibration.
- [ ] Define training cadence by sufficient independent market periods and
      complete outcomes, not a hard "always train after 1,000" rule.
- [ ] Log complete training dataset hashes, purges, feature sets, model
      hyperparameters, validation snapshots and random seeds.
- **Acceptance:** stable offline/repeated validation, no leakage, no
  optimistic in-sample profitability used to qualify.

### Milestone 6 — Learned exit-policy selection and robust validation

**Status: PLANNED.**

- [ ] Train a selector for one of the *tested* fixed policy arms.
- [ ] Distinguish entry quality from exit-policy quality; compare arm
      distribution and tail loss, not just mean R.
- [ ] Chronological, nested or walk-forward splits with four-hour
      (or chosen horizon) purging/embargo and proof labels matured
      before subsequent validation entries.
- [ ] Hold out entire calendar days and regimes; test for stale-quote
      and market-wide correlated-drawdown risk.
- [ ] Include fee/slippage stress (+ cost, delayed fill, wide spread)
      and adversarial sparse funding scenarios.
- [ ] Pre-register admission gate: positive **after-cost** mean
      and minimum positive-rate/coverage, enough validation events/days,
      no catastrophic tail, no reliance on one symbol or one time block.
      Final exact numerical thresholds to be approved before evaluation.
- [ ] A candidate that fails any research gate is RESEARCH_REJECTED,
      including Generation 1; no fallback BASELINE_READY bypass.
- **Acceptance:** truly out-of-sample testing and frozen generated artifacts;
  train/validation leakage and future availability tests.

### Milestone 7 — Forward-only paper examinations and Champion governance

**Status: PLANNED.**

- [ ] Paper executor remains observation-only and cannot submit orders.
- [ ] Freeze model artifact and all policy versions at paper start; rank
      and conditional exit policy run as actually available in real time.
- [ ] Paper decision may abstain; count opportunity windows and qualified
      selections separately from completed trades.
- [ ] Strict chronological independent paper data; enforce at least
      multiple UTC days/regimes, enough LONG and SHORT trades where relevant,
      profitable mean after costs, drawdown and severe-loss limits.
- [ ] Compare paired champion/challenger on same frozen opportunities and
      identical accounting.
- [ ] Interrupted/restarted WSS paths UNSCORABLE; never impute wins.
- [ ] Champion promotion **manual explicit approval** after full report;
      no automatic promotion and no implicit Execution authority.
- [ ] Review evidence against the pre-registered paper promotion criteria.
- **Acceptance:** paper-run ledger, reviewer-facing gates and complete tests.

### Milestone 8 — Operations, Telegram visibility and safety hardening

**Status: PLANNED.**

- [ ] Commands/status for V5 research candidates, rejection reasons,
      experiment counts, selected entry/exit policy, after-cost metrics,
      champion eligibility, data gaps and funding-coverage quality.
- [ ] Display V4 and V5 independently to avoid mixing incompatible
      versions; distinguish deployed SHA from GitHub HEAD.
- [ ] Service unit/cgroup resource limits for one-GB host, idempotent
      boot behavior, file ownership, file locks, full error reporting.
- [ ] No command should arm live orders; `/champion` requires explicit
      V5 review-gate configuration before enabling V5 status.
- [ ] Quiet success-test output; full failed-test traces and captured logs.
- [ ] Operational doctors, restart safety, cold start/mid-cycle faults,
      SQLite WAL consistency, WSS reconnect/evidence gaps.
- **Acceptance:** repeatable disaster recovery and monitored dry run.

### Milestone 9 — Safe Cutover, forward collection and controlled operation

**Status: PLANNED; do NOT initiate before previous gates.**

- [ ] Verify backup plan and stable GitHub release with green CI.
- [ ] Perform consistent **SQLite online backups** of V4 DBs including
      WAL content, never raw `cp` of busy database alone. Hash manifests.
- [ ] Inspect service state, active positions, WSS capture continuity,
      DB sizes, permissions, locks and free RAM/disk before cutover.
- [ ] Choose an explicit cutover window with user approval; stop/disable
      legacy V4 Research/Paper/Training only when prepared to lose any
      in-memory unscored paths; log unscorable outcomes, not fictitious trades.
- [ ] **Do not stop the existing market collector**; preserve raw
      point-in-time market truth and collector configuration.
- [ ] Install new V5 services with explicit role identity and unique
      paths, restart policies, startup cursor, resource limits, logs.
- [ ] Verify first 5m cycle, qualified/rejected reporting, simultaneous
      three-policy paths, funding event coverage and clean shutdown.
- [ ] Compare baseline V4 performance only as a historical benchmark;
      no reuse of V4 outcomes as V5 training without a new explicit
      decision and leakage analysis.
- [ ] Run prospective paper long enough to meet pre-registered evidence
      gates; retain a no-champion state if performance remains negative.
- [ ] Record actual deployed SHA, systemd unit hashes and backup locations.
- **Acceptance:** observed V5 evidence health, no Execution activation,
  no code/service/data ambiguity, no loss of raw collector coverage.

### Milestone 10 — Independent decision on any future Execution project

**Status: OUT OF SCOPE for V5.**

- V5 research success does not imply automatic real-money permission.
- Any future operational live-trading design requires explicit user
  authorization, venue-specific controls, independent safety verification
  and a separate architecture/PR/gate sequence. No assumptions today.

## Verification and release requirements for every milestone PR

Each PR must include all applicable items:

- [ ] Roadmap update with actual status, changed/unchanged components,
      new tests, dangers, pending dependencies and decision-log entry.
- [ ] Immutable/versioned behavior; do not silently rewrite old outcomes.
- [ ] Tests for normal flow, negative/invalid/future/missing evidence,
      no orders, restart or duplicate identity, and economic corner cases.
- [ ] Full CI green on **latest PR head**; merged-main CI also green.
- [ ] Positive evidence that V4 was not modified inadvertently.
- [ ] No deployed-worker restart unless approved at cutover.
- [ ] Explicit deployment status, release SHA and rollback plan.
- [ ] Changelog note for any changed fees, funding, eligibility or exits.
- [ ] At next completed stage update this table; do not tick future gates.

The pull-request workflow includes a `check_v5_roadmap.py` gate. It
compares PR base and head and refuses V5 code/test changes without an
accompanying edit to this document. The dedicated quiet test runner captures
all test stdout/stderr, including subprocess prints and FD writes, while
preserving actual unittest dot progress, error tracebacks and captured
diagnostics if tests fail. **No masking errors to achieve cosmetic silence.**

## PR #38 independent audit — remediation gates

- [x] First independent review at `7d4fb915` reproduced two merge-blocking P1 evidence defects.
- [x] Code correction: depth may not replace a newer bookTicker executable entry anchor; reject reversed/cross-source evidence and enforce two-source agreement for new admission.
- [x] Code correction: require ticker evidence for admission and horizon; track per-symbol, per-event-source receipts; transport keeps socket identity and uses a watchdog independent of busy queue traffic.
- [x] Add reproductions for stale SHORT entry, zero-bookTicker candidate, masked ticker silence, strict event-gap invalidation and apparent quote recovery after missing coverage.
- [x] Corrected code head `64abdc6f` passed [1,490-test full CI](https://github.com/samqju/Nbot/actions/runs/38280766303) with clean dots/OK and no operator noise; final docs-only revision gets its own CI.
- [ ] Perform **a second independent read-only audit** of corrected SHA; require both original P1 defects to be irreproducible before merge.
- [ ] Independently validate real Binance event timing, brief quote losses that evade silence watchdog, resource usage and settlement finality on isolated host. Until that acceptance, no live V5 scoring or VPS deployment.
- [ ] Merge PR #38 only after the second review and green latest SHA CI, then verify merged-main CI; keep V4 untouched.

## Decision log (append-only)

| Date | Decision | Why / implication |
|---|---|---|
| 2026-10-12 | V5 is clean-slate, separate from V4 | Legacy candidate/exit economics poor; keep old data as evidence, not V5 training |
| 2026-10-12 | Retain LIVE observation collector | Working 60-symbol point-in-time collection; avoid WSS interruption |
| 2026-10-12 | 100 research entries is a cap, not a quota | Strong directional entry qualification and valid no-trade outcome |
| 2026-10-12 | Start every exit arm at -1R | Freeze risk economics; allow exit arm testing and eventual learning |
| 2026-10-12 | 0.05% fee per side | User corrected 0.10% mistaken rate; 1bp/slippage side only an assumption |
| 2026-10-12 | Fund from actual settlement evidence | Both direction and settlement chronology matter; no fabricated zero |
| 2026-10-12 | No first-generation baseline qualification exception | Gen-1 V4 paper had already failed research economics |
| 2026-10-12 | Keep V5 development changes in PRs and roadmap updated alongside each | Preserve continuity beyond chat context window |
| 2026-10-12 | Successful CI shows clean dots only; failure shows full logs | Test prints/noisy subprocess output should not create false impression; no hiding faults |
| 2026-10-12 | PR #30 adds foundation, accounting, roadmap and CI infrastructure | Open pending final head CI; V4 and VPS untouched |
| 2026-10-12 | Quiet runner must add repository root to sys.path | Direct invocation otherwise fails collection imports; corrected and green at 1,428 tests |
| 2026-10-12 | PR #30 merged V5 milestone 1 foundation | Merge `2b6bc33`; safe, no VPS update, no V5 service running; document completion in PR #31 |
| 2026-10-12 | Begin PR #32 V5 qualified-entry prototype | Clear directional setup, abstention, cost/liquidity gates and sampled near misses; no raw DB writes, no service installation, no claim of profitable thresholds |
| 2026-10-12 | Merge PR #32 selector prototype | Merge `19eec7f`, 1,436 green PR-head tests; separate verified metadata/depth gate and prospective evaluation required before any V5 runtime |
| 2026-10-12 | Record PR #32 merge in PR #33 | Handover document updated after milestone code change; V5 remains not deployed |
| 2026-10-12 | Start PR #34 point-in-time market quality bridge | Public exchangeInfo PRICE_FILTER/LOT_SIZE/MIN_NOTIONAL, depth freshness, order-book sweep, fail-closed missing/stale evidence; not deployed, thresholds unproven |
| 2026-10-12 | Merge PR #34 quality bridge; record in PR #35 | Merge `0ad04e7`; clean 1,441-test CI at PR head, merged-main 38259054293 verified green; deployment and historical depth inference prohibited |
| 2026-10-12 | Start PR #36 paired exit research lab | Same full 4h continuous path for three arms, no fake horizon fill, prospective funding proof contract, immutable outcome ledger; NO VPS changes |
| 2026-10-12 | Merge PR #36 paired-exit prototype; record status in PR #37 | Merge `bece0864`, 1,456 green clean tests on PR head; quote-only crossings, actual WSS integration, funding proofs and state continuity remain; no V5 deployment |
| 2026-10-12 | Start PR #38 public live evidence and recovery bridge | Joint routed WSS and quote-only stops; bounded atomic WAL checkpoints and durable pending outcomes; REST aggregate recovery cannot repair missing historical quotes; public settled funding is research evidence, not account income; V4/VPS/order authority unchanged |
| 2026-10-12 | Verify PR #38 implementation CI | Head `0f158bad`, run 38272931564: 1,485 tests passed, clean dots/OK; 29 new tests including routed transport/recovery, depth horizon watermarks and causal capture receipt; record evidence in this documentation-only revision and recheck latest-head CI; not merged or deployed |

## Handover checklist for a fresh ChatGPT session

- PR #30 is merged at `2b6bc33`. Check its merge-main CI and whether V5
  code was deployed on Observation VPS; last verified VPS still at `b1a3c4a`.
- Confirm current services before suggesting any restart. A prior two-restart
  incident caused WSS path losses and 792 unresolved V4 outcomes.
- PR #32 prototype merged at `19eec7f`. PR #34 public quality prototype merged at `0ad04e7` (main CI must be separately verified). The opt-in functions are **not** running: capture persistence, matched real-time event/metadata/depth provenance, portfolio correlation caps and prospective validation remain before V5 activation.
- PR #36 experimental paired-exit prototype merged at `bece0864`. PR #38 adds the opt-in **joint WSS quote+aggTrade bridge**, quote-only crossings, checkpoints, aggregate recovery and public funding proof. Review [V5_LIVE_EVIDENCE_BRIDGE.md](V5_LIVE_EVIDENCE_BRIDGE.md) and latest-head CI. Next: independently measure resource budgets, funding publication timing, clock/stream integrity and prospective coverage. No service or VPS activation occurred; missed historical quotes remain unrecoverable.
- Identify next milestone by reading statuses, not by extrapolating chat.
- Never claim V5 is collecting or learning until services are actually
  installed, started and observed.
- Treat both RESEARCH and PAPER as no-order-authority, even if a Champion exists.
- If a PR changed a V5 contract, update this document **in the same PR**.

## 2026-10-13 decision-log addendum — PR #38 V3 remediation

The earlier milestone checkboxes record historical prototype work, not current
certification. A watchdog, depth-ID chain, horizon witness and agreeing funding
responses did not prove quote-path or settlement finality. V3 deliberately removes
unsupported certified scoring rather than tuning liveness to hide that limitation.

| Date | Decision | Why / implication |
|---|---|---|
| 2026-10-13 | Keep PR #38 open, unmerged and undeployed | User authorizes corrections/push only; independent review and latest CI remain gates |
| 2026-10-13 | Version observed versus certified evidence | Received bytes and reproducible simulations do not establish all actual market movements |
| 2026-10-13 | Disable certified V5 training/promotion consumers | Every current classification, including legacy SCORED and forged CERTIFIED_PATH, is rejected by the guard |
| 2026-10-13 | Retain immutable diagnostics with append-only revocation | Funding contradiction, late within-window evidence, uncertain restart and persistence recovery can veto all dependent arms without deleting history |
| 2026-10-13 | Journal inputs and checkpoint periodically | Avoid whole-shard serialization on each WSS event while verifying replay/head/checkpoint consistency |
| 2026-10-13 | Resource improvement is not deployment approval | Byte limits and desktop benchmark do not establish representative one-GB sustained capture capacity |
