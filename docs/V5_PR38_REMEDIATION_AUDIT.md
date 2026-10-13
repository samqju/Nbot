# PR #38 V3 remediation and development audit

Date: 2026-10-13 (Asia/Calcutta). PR: [#38](https://github.com/samqju/Nbot/pull/38).
Audited starting head: `9a8163c9c7d38cccdb2ae215746492e3d2898896` (actual fetched
head matched the request; no subsequent work was discarded). Original implementation:
`7d4fb9157f1a6036c1a8e581af31ff5dfb752371`.

This is a **development self-audit**, not external independent signoff. The supplied
[second independent audit](NBOT_PR38_SECOND_INDEPENDENT_AUDIT.md) is preserved.
Its accompanying raw harness/evidence bundle was not supplied; its explicit
sequences were recreated in permanent tests. The architecture is documented in
[V5_LIVE_EVIDENCE_BRIDGE.md](V5_LIVE_EVIDENCE_BRIDGE.md).

## Root cause and reduction of unsupported functionality

V2 conflated received-event continuity/liveness with market-path completeness,
a horizon observation with source finality, and funding-response agreement with
settlement publication finality. Some causal checks ran outside admission locks;
rollback lost indispensable events without poisoning the callable interface.

V3 separates received bytes, observed simulation, certified proof and quarantine.
**No certified public-feed path validator exists.** Every complete-path training,
Champion, policy-promotion and performance consumer call is rejected. Live results
are stored atomically in a separate observed-pair table, never in legacy SCORED
outcomes. Final funding and after-funding net returns are unknown/null. This is
an explicit versioned removal of unsupported certification, not a renamed unsafe
score. Known observed exits/costs remain useful diagnostics.

## Closure matrix

| Finding | Original issue | Correction | Permanent regression | Result / remaining risk |
|---|---|---|---|---|
| P1-A | Late depth overwrote ticker anchor | Separate sources, stale-source rejection; all acquisition watermarks checked under admission lock | Existing `test_auditor_p1_late_depth_cannot_overwrite_newer_entry_anchor` | Passed; legitimate asynchronous skew may conservatively reject |
| P1-B | Zero ticker and hidden silence scored | Require ticker; per-symbol fault policy; no certified path claims | Existing no-ticker/per-symbol/busy-traffic tests; H1 production-threshold history | Passed; silent missing short movements remain indistinguishable |
| H1 | Omitted 50ms stop yielded three winners | Observed-only outcomes; unconditional certified consumer rejection | `test_h1_delivered_and_omitted_crossing_have_different_observed_results_neither_certified` | Passed; actual omitted market movement cannot be inferred |
| H2 | Snapshot completed after entry decision | Snapshot/book/receipt/actual validation availability in locked admission | Three `test_h2_*` cases; stale-depth and restart fixtures | Passed; production clock synchronization remains required |
| H3 | Funding contradiction reusable after restart | Pending/limited verification/revocation journal; quarantine overlay; null final funding | Two `test_h3_*` cases, pending ledger and restart tests | Passed; public funding finality remains unproven |
| H4 | Horizon witness ignored same-time conflict | Provisional window, continued checks, append-only late-evidence quarantine | Two `test_h4_*` cases | Passed; no authoritative closing watermark; conservative over-quarantine |
| H5 | Rolled-back stop followed by winner | Nonrollbackable fault latch, explicit invalidating recovery, restart quarantine | Two `test_h5_*` cases; checkpoint failure test | Passed; injected failures are not power-loss/real disk-full testing |
| M1 | Snapshot task exception discarded | Owned tasks with retrieved callbacks; bounded sync; cleanup preserves primary error | `test_m1_*`, sync/byte/count overflow and existing transport cases | Passed; actual network/library cancellation still needs acceptance |
| M2 | Disconnect between validation and mutation | Validation inside the same locked action and persistent CAS | Barrier-controlled `test_m2_*` | Passed; single current owner required |
| L1 | Connection context did not close SQLite | Explicit V5 connection contexts/reader closing; V5 fixture connections closed | Existing foundation/paired/selection cleanup; repeated isolated temp DB tests | Passed on Windows; Linux CI remains a separate gate |
| Paired publication | Partial immutable three-arm writes | One observed-pair row; one transaction for legacy paired writes | `test_legacy_partial_pair_write_rolls_back_every_arm`; observed ledger failure/retry | Passed; raw SQL is not a supported learning consumer |
| Resource/backpressure | Whole-shard checkpoint per tick; large decoded queue | Chained event journal, 128-event checkpoints, one-book rollback; raw byte caps; off-loop writes | Journal-tail/truncation/checkpoint/randomized tests, prompt overflow tests, offline benchmark | Improved; sustained target-host limits/retention remain unverified |
| Training contamination | Observed/legacy/revoked rows could become labels | Explicit guarded consumer API, separate tables and durable revocation authority | H1 ledger consumer calls and forged-class tests for all four purposes | Passed; no V5 learner is installed; future integrations must use guard |
| Fresh-review provenance finding | Caller could fabricate an observed paired set | Compare current finalized results; bind ledger to journal-covered immutable source payload/entry/head | `test_independent_review_fabricated_pair_cannot_bypass_source_provenance`, stale-authority and derived-index corruption tests | Corrected; fresh reviewer rechecked original negative |

## Tests executed and diagnostic history

- First focused synchronous run exposed five failures/three errors because existing
  tests required V2 SCORED/final-funding semantics. Mechanical exit-price, signed
  observed settlements and gross-R assertions were retained under V3. No production
  silence threshold was weakened.
- Monotonic receipt validation exposed one fixture delivering closing depth after
  a later receipt but backdating its receipt; its input now reflects actual arrival
  order. Restart expectations now require quarantine, including horizon witnesses.
- Windows fixture/reader connection leaks caused three temp-directory cleanup errors;
  explicit closure corrected them without changing V4 implementation.
- New fault tests initially used an UPDATE trigger against SQLite REPLACE checkpoint
  writes, and one stale-depth fixture violated entry quote-age construction before
  exercising admission. Corrected the injection/input, retaining the negative goal.
- Initial new transport deadline fixture used a future transaction time with an earlier
  receipt; corrected it to isolate an unsynchronized open socket.
- An intermediate focused run passed **90 tests in 121.010s**. Subsequent provenance
  corrections passed 34 focused tests, then three targeted source/index regressions.
- A restricted-sandbox asyncio run stalled and was interrupted; the audit documented
  the same Windows sandbox limitation. Outside that sandbox, all original mocked
  transport cases and the new supervision cases passed. No live Binance connections.
- Full-suite local and final-head CI results are recorded in the verification addendum.
  Pinned `lightgbm==4.7.0` and `websockets==17.2` were installed only in the isolated
  workspace. Full diagnostics are retained; passing old CI is not new-head evidence.

The randomized test uses a fixed seed for repeatable duplicate/order/fault sequences.
The H1 histories use production thresholds, regular 20-second observations through
the four-hour event-time horizon, and the actual durable journal. Synthetic clocks
are explicit; these are not four-hour wall-clock/live runs. Existing tests also
cover IDs/gaps/duplicates, depth faults, partial REST recovery, funding pagination,
signed LONG/SHORT accounting, early-exit shared-path invalidation and symbol isolation.

## Synthetic resource measurement

Command: `python deploy/observation/benchmark_v5_evidence.py --events 300`.
20 synthetic symbols, 1,000 levels on each book side, no active hypotheses,
one-symbol trade ingestion, SQLite WAL/FULL; traced allocations enabled.

| Measurement | Desktop result |
|---|---:|
| 300 durable mutations | 4.897556 s |
| Throughput | 61.255 events/s |
| p95 / p99 mutation | 18.017 / 21.477 ms |
| Traced peak allocations | 1,085,401 bytes |
| DB plus WAL | 1,708,032 bytes |
| Checkpoint | 510,936 bytes |
| Journal / rows | 640,834 bytes / 361 |
| Restart verification/replay | 0.119860 s |

The audit's 10.445/s measured a different run. This is not a controlled speedup
ratio, process RSS measurement, representative active depth workload or one-GB
VPS capacity claim. Concurrent tests ran on this desktop. Journals remain append-only
and bounded by stop-on-cap; no reviewed indefinite retention/export exists.

## Self-audit and independent-review boundary

Inspected all affected entry points, checkpoint restoration, foundation outcomes,
legacy paired persistence, selection/market quality and learner references. No V5
training reader existed; V3/V4 paths do not read these tables. No real-order API,
credentials, private endpoints, import-time writes or service registration added.
The fresh read-only review agent did not implement the correction. It independently
reproduced the fabricated-result bypass, confirmed training remained blocked, and
rechecked the corrected rejection. It also requested journal validation of derived
window/decision indexes, now implemented and regression-tested. Its final verdict
and exact reviewed revision are tracked in the addendum. Human/external signoff is
**PENDING**; a same-system agent review is not a human approval or economic proof.

## Verdicts and remaining gates

**A — Inactive research-only merge:** conditional on green final-head full CI and
fresh final-code review. H1–H5 are corrected or eliminated under explicit V3
observed-only functionality; no certified feature is claimed. Do not merge on the
intermediate test count. PR remains open and unmerged.

**B — Live Binance collection and scored research:** **NO deployment readiness**.
Certified scoring is unavailable. Isolated observed-stream capture could undergo
separate review, after authorized real source/timing/reconnect/rotation/funding
studies, representative one-GB Linux CPU/RSS/swap/disk-latency/coexistence testing,
shared-IP budgets and archive/retention acceptance. No live or VPS test was performed.

**C — ML consumption:** **No current evidence class is allowed.** Received,
observed, unscorable, revoked, legacy SCORED and caller-forged certified records
are rejected for training, Champion, promotion and complete-path performance.
Only a future CERTIFIED_PATH contract with a technically sufficient independently
reviewed validator could qualify; that capability is disabled today.

Required additional exercises: real socket ping/pong and more than 24h rotation,
publication revisions/variable settlement types, lost frames in actual libraries,
clock steps, abrupt kill/power-loss, actual disk exhaustion during cleanup,
representative many-active-symbol load, collector coexistence and target-host
acceptance. No finite suite proves absence of every defect. No orders, VPS access,
deployment, restart, V4 historical rewrite or automatic merge occurred.

## Verification addendum — final review and local full-suite limitations

A separate fresh read-only agent reviewed the final working-tree architecture.
It reported no remaining merge blocker after the additional publication/provenance
and derived-index fixes, conditional on latest-head CI. It independently ran:
initial 16 trust cases, updated 20 trust cases, four transport supervision cases,
and 32 foundation/paired/selection tests. Its original fabricated-result and
metadata-corruption negatives now reject. This is agent review, not human/external
signoff; human/external signoff remains **PENDING**.

The local full repository suite was actually attempted with pinned dependencies
and an observation-only fixture role: **1,418 tests in 459.850s; 22 failures,
653 errors, four skips**. It is **not green**. Existing non-V5 tests rely on Linux
permissions/file replacement/SQLite cleanup and execution-role fixtures; import
errors also reduce discovery counts. The retained log is approximately 1.65MB.
These failures are not hidden or corrected by changing V4/Execution safety code.
Final Linux GitHub CI is required to establish the full-suite result.

Automatic approval review rejected writing an EXECUTION role marker for local
regression setup; the safer OBSERVATION fixture was used. No production execution
role or service was modified. The existing GitHub test workflow itself is unchanged.

Final code/CI references will be recorded below after the validated correction is
pushed to the existing PR branch. PR remains open and unmerged.

Final local V5 validation: **98 tests passed in 114.133s**, including the roadmap
and quiet-runner infrastructure. A subsequent eight-test targeted run passed in
1.101s after the final transport budget-lifetime and checkpoint preflight edits.
Compilation and `git diff --check` passed. No V4 source/workflow/service changes.
