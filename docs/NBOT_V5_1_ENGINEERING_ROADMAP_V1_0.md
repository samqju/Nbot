# NBOT V5.1 — Detailed Engineering and Recovery Roadmap

**Roadmap version:** 1.1  
**Date:** 15 October 2026  
**Status:** DESIGN / OFFLINE PREPARATION ONLY — NOT IMPLEMENTED, NOT RELEASED  
**Repository / future development branch:** samqju/Nbot / nbot-v5.1  
**Product authority:** NBOT Complete Product Vision V1.9, copied **verbatim** to this branch  
**Owner-friendly companion:** NBOT V5.1 Plain-Language Development Roadmap V1.0

## 0. Authority, scope and development philosophy

**Product target:** A coherent, resource-bounded, evidence-first Binance USD-M USDT-perpetual, single-position trading bot with seven product stages:

**Observation → Exploration → Research → Learning → Training → Promoter/Retainer → Trading Decisions**; feedback is a cross-stage loop, not a new daemon.

The latest relevant Vision sections, **8G and 8H**, govern intended **100 lightweight discovery symbols → 20 deep original-source symbols → rolling up to 40 concurrent virtual experiments → at most one actual global exchange position or NO TRADE**. Vision V1.9 also contains older, superseded 50-only and 200→50 planning discussions, and references to original engineering G1–G10 gates. Do not silently treat obsolete numeric assumptions as current. Preserve Vision file contents unchanged unless the owner explicitly authorizes a revised blueprint.

**Development policy: CLEAN FOUNDATION + SELECTIVE REUSE.** The new V5.1 branch begins documentation-only; do not copy the old repository working tree, DB dumps, caches, dependencies or historical strategy ensemble into it. Inventory/read-only inspect originals. Port/reimplement only separately reviewed components with proven scope, pinned source origin and independent regression tests. Keep old branches and data unmodified. Don't operate on the user's laptop.

**Safety mode at kickoff:** Documentation / offline synthetic only. No VPS service starts, live/paper order placement, exchange credentials, automated PR merge, data deletion or release permission. A new development milestone, test success or approved paper experiment must never create real-money authority.

**Definitions:** "Paper" is a constrained simulated portfolio run through an independent guardian. "Virtual" is Research's prospective hypothetical experiment population; it is not a portfolio or exchange fill. "Live" requires separately authorized real exchange permission and confirmed fills. A quote-constrained simulation is not an executed order.

## 0A. Mandatory selective copying from older NBOT branches

**Explicit build instruction: the new V5.1 application WILL be assembled partly by copying approved, needed components or functions from older V4/V5 GitHub branches into NEW V5.1 files.** We are *not* committing to reimplement every working component; equally, we must *not* wholesale-copy the old repository, any branch's complete working tree, or unreviewed directories.

For **each** candidate to be copied, follow this mandatory mini-checklist and tick items independently when completed:

- [ ] Identify the exact old **branch + commit SHA + original path + symbols/functions**, and record the intended V5.1 module and purpose.
- [ ] Read dependencies, imports, runtime side effects, data contracts, old strategy assumptions, test coverage and credential/network/order reachability. Decide **COPY-AND-ADAPT / REIMPLEMENT / DISCARD / KEEP AS REFERENCE** with a short reason.
- [ ] Confirm the component is compatible with Vision V1.9: 100 lightweight/20 deep, 24 pattern tags not 24 proven strategies, honest source/economic grades, rolling 40 virtual intents, guarded paper-only/one-actual-position boundaries.
- [ ] Copy **only the necessary source code** into freshly designed paths **on nbot-v5.1**, adapting imports and interfaces without carrying dead dependencies or legacy databases. Do not modify the source branch and do not touch the user's laptop.
- [ ] Add/copy only relevant **approved tests**, augment with negative, source-gap, permission and compatibility cases, and run them safely **offline**, without trading/network side effects.
- [ ] Record original provenance and new destination/commit, results, remaining issues and approval status in a versioned **Legacy Component Reuse Register**. Tick the module/task on its stage checklist only when its stated acceptance tests pass.

If safe transfer is not established, leave the task **[ ]** and record HOLD; do not quietly replace it with fabricated success or missing assertions. Simple verbatim file copies are acceptable only when dependency review confirms the *entire file* is required and safe; otherwise copy just the necessary functions and rewrite surrounding structure.

**Branch independence:** The legacy branches and their commits remain intact. The new branch's working tree begins with documentation only, despite its Git ancestry. Adding new application files to nbot-v5.1 in later explicitly authorized phases is expected and does not require copying unwanted historical files.

**Explicit order:** Read-only inventory first → component-level owner review → approved targeted copying/new coding → offline tests → evidence-backed checklist update → advance to next gate.

## 1. Sources, project inheritance and known conflicts to investigate

Historic reference repository: samqju/Nbot. Original documentation lives on branch docs/nbot-complete-vision-20261015, and the historical V5 roadmap on docs/NBOT_V5_MARKET_INTELLIGENCE_ARCHITECTURE_AND_ROADMAP_2026-10-13.md. These are references, not files to copy into V5.1.

**Candidate legacy reuse targets (inspection only; no automatic inclusion):**

| Function / former source | Possible value | Qualification concerns |
| --- | --- | --- |
| nbot/v5/public_market.py | Exchange eligibility, 24h quoteVolume and finalized-candle validation | Hard-coded 50-symbol designs; no 100-lightweight vs 20-deep split |
| nbot/v5/stream_buffer.py and observation contracts | Bounded latest-state and 96 closed-five-minute candle ring | Memory-only state is not source custody; old route/protocol assumptions require tests |
| nbot/v5/g1f_runner.py, g1f_journal.py and g2_population_audit.py | Immutable five-minute event candidate denominator, gap markers and restart evidence | Frozen old 50-cohort, 100-side population; V5.1 requires new 100-broad / 20-deep schemas |
| nbot/v5/g3_market_context.py and V4 detector adapter | BTC regimes, coin structure and 24 pattern detector outputs | All features must be causally available at decision time; detector counts are NOT economic evidence |
| nbot/v5/g4_segmented_source.py, g4_incremental_path.py, g4_segment_quotes.py | Compressed hash-chained source custody and bounded source-path replay | No guarantee of production-validated source-grade qualification, archival rotation or unlimited disk |
| nbot/v5/g4_research_ledger.py and g4_economics.py | Immutable frozen research labels and quote-constrained net-R contract | Only qualified original after-cost outcomes may reach Learning |
| nbot/v5/continuous_research.py | Candidate/label/economic queue ideas | Must prove genuine full pipeline without backfilled fixture labels or per-candidate full-archive rescans |
| nbot/v5/guarded_paper.py | Two event-sourced books and independent veto/reconciliation | Old G7 unlock code appears to require **two** models, conflicting with intended first-Champion-only paper lifecycle |
| Existing unit/CI fixtures | Regression, disconnected-source tests and governance lessons | Distinguish unit/synthetic pass from authentic prospective data quality |

V4's **24 detectors are pattern hypotheses, not 24 profitable proven strategies**. Old virtual successes, synthetic candidate fixtures and preliminary G4 price-only path labels must never qualify as scientific net-return data without an independent audit. The historical G1–G7 and proposed G8–G10 gates remain historical engineering terms; do not conflate their numbering with the seven owner-facing product stages.

**Special investigation:** Existing G4 path/cost handoff and G7 first-Champion release conflict. Resolve through reviewed design and tests; no bypass of old safety checks by merely renaming functions.

## 2. Desired runtime architecture and trust boundaries

### Observation VPS — market brain and bounded research laboratory

- One **lightweight discovery intake** for up to 100 unique, currently eligible USDT-quoted and margined perpetual symbols, BTC mandatory.
- Completed five-minute OHLCV, verified clock/source status, BTC regime, overall-market breadth; snapshots are cheap and durable as needed. **Do not start full high-frequency streams for all 100 by default.**
- Capacity-aware causal exploration, coin features and 24 original detector states. Every skipped full-book evaluation receives an explicit capacity reason, never a manufactured NO_MATCH.
- A separate **deep 20-symbol source tier** with verified original trade/quote/mark/funding custody, controlled source epochs, source-gaps and per-symbol shared processing.
- Research admissions and **rolling up to 40 active virtual intents**; one per symbol+direction under first policy. Terminal first-touch events may occur between five-minute decisions and are recorded at source-supported time.
- Source-verified economic outcome audit and immutable progress cursors. Asynchronous low-priority Learning/Training only on genuinely qualified, finalized evidence.
- Frozen approved Champion/Challenger inference on valid five-minute candidates, and Stage 6 comparison using **compact paper summaries**.
- Original high-frequency receipts are batched/compressed/hash-protected and subject to finite disk quotas/archival proof; never one SQLite insert per raw WSS frame.

### Execution VPS — independent guardian, limited paper books, future gated live

- Accepts authenticated and mode-scoped recommendations only from approved frozen model versions, with event/source identity, expiration, idempotency and relevant quote/cost/risk evidence.
- One paper engine with logically independent **Champion Paper** and **Challenger Paper** books; at most one simulated open position per book under first approved design; no common equity or combined result grade.
- Lightweight relevant-price/stop/trailing-stop management for open paper positions. Independently verifies safety and position state; no full model Training or duplicate 100/20 archive.
- Future actual order executor remains **absent or hard-locked** pending separately owner-authorized release. One actual position globally, counting unresolved pending, partial and orphaned orders; guardian has unconditional VETO.
- Prefer independently reconciled exchange-side protective mechanisms for any future real exposure. A five-minute scan is NEVER the sole protective stop-loss facility.

### Two operating clocks / workload allocation

1. **Price events:** Read validated original streams when required; update bounded latest quote, source-health cursor, stop/target first touch and favorable excursion, trailing-stop transitions, and needed compressed source evidence. No repeated detector pass or per-tick SQLite row.
2. **Five-minute closed event:** Verify BTC/market/source, reconcile verified exits and available virtual/paper/live slots, run **heavy new-candidate Exploration and inference only if a relevant independently authorized capacity exists**. If full, keep compact source snapshot and explicit NOT_EVALUATED_CAPACITY labels.
3. **Low-priority science:** Periodic bounded source-evidence replay, maturity/audit, Learning, Training and Stage 6 comparison on immutable source snapshots.

**Important asymmetry:** Virtual full slots do not prevent a Champion paper opportunity if its paper slot is free; Challenger's occupied paper book does not prevent independent virtual Research. A real open position never stops virtual observation/research. Independent guardian/position safety always runs when active exposure exists.

## 3. Required data contracts before application code

**D0. Universe manifests:** BTC inclusion, per-coin eligibility, exchange contract properties, turnover/gainer/loser overlapping group tags, as-of clock, 100-broad and 20-deep cohort epoch versions, rejection reasons, selection algorithm SHA and source provenance. Proposed discovery mix: 50 high-turnover, 25 gainers, 25 losers, deduplicated, with fallback to qualifying liquid names only.

**D1. Source envelopes and epochs:** Connection route; symbol, exchange event time, local receive time, sequence/aggregate trade IDs, source-grade, original witness SHA, gap/replay/stale flags and reconnect markers. No continuity granted across unknown uptime or missing trade IDs.

**D2. Closed five-minute event:** Deterministic event ID, reference BTC and cross-market state, finalized candles, per-symbol validity, decision as-of time, source-source hashes. Avoid future candles/features.

**D3. Exploration observations:** Full observed symbol/direction denominator under the declared evaluation policy; direction LONG/SHORT, all **24 versioned detector states**, structures (forming/confirmed/failed/unavailable where supported), BTC and coin regime, liquidity/cost feature state, original category tags, source admissibility, explicit NO_TRADE, NOT_EVALUATED_CAPACITY, NOT_EVALUATED_SOURCE, and recorded sampling/inclusion probability where applicable. Never interpret an unevaluated feature as a failed detector or as a model's abstention.

**D4. Research virtual-intent state machine:** Proposed statuses to map to reviewed code: PROPOSED → ADMITTED / REJECTED → FROZEN_INTENT → ACTIVE → PATH_CLOSED or PATH_HOLD → COST_PENDING → SCORED / PATH_ONLY / CENSORED / UNRESOLVED / HOLD. Immutable entry convention, side, stop, target, duration, trailing policy, initial R, quote/cost witnesses, cohort and feature SHA. Outcomes use independent evidence grades; no magic promotion from path-crossing to executable fill.

**D5. Rolling slots:** Atomic idempotent active-index by symbol+direction; strict total active ≤40 and ≤1 per symbol+side; reconcile confirmed close before reusing at five-minute boundary; leave vacancies if no eligible replacement; active path states cannot simply vanish after a restart; durable orphan/gap handling. Open trade status and cost-verification status are deliberately separate.

**D6. Modes and books:** Disjoint VIRTUAL_RESEARCH, CHAMPION_PAPER, CHALLENGER_PAPER, future CHAMPION_PAPER_MIRROR and authorized REAL. Each has separate IDs, filled-versus-simulated economics, equity/risk/cost, management policy, and evidence quality. Distinguish proposal, model abstention, guardian veto, paper fill, actual partial fill and scientific censored terminal.

**D7. Frozen model and contest:** Code+data cutoffs, training/feature hashes, model SHA, calibration, uncertainty and lower-bound after-cost condition, NO_TRADE logic, risk/entry/exit policy, deployment signature, active Champion version, separate Challenger paper-only scope, common forward time and evaluated market groups, promotion/retention recommendation.

**D8. Recovery and checkpoints:** Durable source head, source epoch, completed candles, active virtual state+trailing stops, pending economic audits, paper books, stale-source flags, actual execution state only when separately authorized. Recovery never manufactures a missed intrasecond ordering or cached bid/ask.

**D9. Proof provenance:** Every source reference has URI/content SHA, bounded time interval, contract/version/role and retrievability; observer output can be used by guardian only under allowed message signatures and expiry.

**D10. Event journal and reports:** Append-only immutable decision logs, stop changes, rejections, metrics, model promotion recommendations, approval acts and audit reports. No secret values or API keys in GitHub files.

**Schema requirement:** Formalize stable JSON or typed contracts and explicit version migration tests before converting code; do not mix old G1 V5 table layouts with untested new 100/20 storage structures.

## 4. Release gates and acceptance: detailed ordered plan

Every gate remains **TODO/HOLD** until independently evidenced. No PASS inherited merely from old V5.

### G0 — Preserve legacy, authorize scope and take a read-only inventory

Deliverables:
- Branch inventory, active and historic PRs, file map, tests and source contracts from GitHub in read-only mode.
- Optional VPS read-only service/storage/secret-availability metadata assessment **only with fresh owner permission**. Do not read secrets, restart services or touch the laptop.
- Legacy Component Reuse Register: exact source commit/file/function, usefulness, dependencies, data-grade assumptions, KEEP / REIMPLEMENT / DISCARD recommendation, test evidence and security/potential hidden I/O.
- Conflict register: prior 50-cohort, old 100 candidate denominators vs new 200, old G7 two-model unlock, 1-second-Futures-kline endpoint uncertainty, G4 exact original after-cost label handoff, finite archive and promotion policy.

Gate: Owner reviews clean starting scope, approved components and no forbidden side effects.

### G1 — Clean skeleton and nontrading boundaries

Deliverables: a minimal package structure only after owner approval, a narrow source interface, durable journal interface, verified clock/identity helpers, scientific grade enum, guardian proposal envelope, configuration by mode, read-only default and no accessible live order action. Small deterministic tests; pinned dependencies; no legacy module import through unintended paths.

Gate: Offline tests prove no network/account/order reachability without independent explicit enablement; all interfaces versioned.

### G2 — Source custody, time and 100-coin lightweight Observation

Deliverables:
- Read-only public USD-M eligibility and exact 50 high-turnover/25 gainer/25 loser deduplicated discovery snapshot plus BTC, source/clock proof, deterministic fallback and rejection log.
- Bounded completed five-minute candle histories for 100; BTC/breadth health; point-in-time membership; invalid symbol/source/quota cases explicit HOLD.
- One chronological event clock with closed-only finality and correct as-of times; source route/session and mismatch evidence, no retroactive features.
- Stress with 100 symbols and rate limits; report p95/p99 event latency, RSS, CPU, disk and gaps.

Gate: Deterministic 100-coin fixtures, no false future features, no missing/duplicated denominator, failure tests and measured capacity. No network run without owner permission.

### G3 — Capacity-aware Exploration, causal 24-detector integration

Deliverables: 100 discovery coins and both directions (up to 200 records per complete event), BTC+market+coin structures, 24 versioned original V4 detectors, full/partial-source flags, explicit skipped-scoring masks and NO_TRADE distinction. Reuse detector calculations only after behavior, version and data-leakage tests.

Gate: All matches/nonmatches/unavailable/unevaluated states correct, no future leakage, no pattern count becomes economic recommendation and capacity-based missingness preserved for statistical audits.

### G4 — Choose 20 deep research coins and maintain authentic original sources

Deliverables: shortlist policy mixing valid liquidity, causal structures, previously matured evidence and deliberately reserved coverage/controls; BTC mandatory, 20 max, cohort digest, eligibility/inclusion probabilities and no hindsight changes; freeze source-ready after warm-up.

Add one bounded original trade/quote/mark/funding stream per relevant monitored coin/source route, compressed hash-chained segments, no raw per-frame SQLite writes, and active source quota. Original segment replay and independent source-integrity audit have separate roles. Robust headroom monitor/archival design; measured trade-message and bandwidth distributions (not guesses) before continuous operation.

Gate: 100→20 decision replay, all 40 coin-side directions, no duplicate per-pattern virtual trades, fail on unverified source; 20-market stress within the small-VPS budget; finite archive and recovery declared.

### G5 — Rolling research book, first-touch and trailing-stop policies

Deliverables: max 40 active virtual intents across the 20 source-ready coins, max one per coin+side; idempotent prospective intent with frozen stop/target/horizon/cost/trailing policy; stream incremental price/quote source per coin and update all active hypotheses without storing entire tick buffers in RAM.

At every **completed five-minute event**: verify which virtual paths genuinely closed, count vacancies (40 minus active), admit only qualified replacements, up to free eligible coin-side slots; no fixed eight starts and no quota to force a virtual trade. Trigger the expensive opportunity pass only when relevant slots exist; keep sufficient source-health/candle custody otherwise.

A path can hit a stop at 10:03 and close then, but new research slot replacement waits for the 10:05 audited event. Existing path closure and later independent after-cost qualification are separate.

Gate: ≤40 always, ≤1 active per coin+side, correct simultaneous closures, no false reopening, no backdating entry, trailing stop only moves in safe direction, correct cost-pending versus active status, no first-touch claim through gap or ambiguous candle.

### G6 — Recovery, economics, original evidence grading and storage endurance

Deliverables:
- Correct source-epoch and ABRUPT_RESTART_HOLD on interrupted feed or lost unsynced RAM tail; immutable candle audits, segment replay/hashes and journal idempotence.
- Recovery of finalized candles from independently overlapping trusted source; optionally original aggregate trades with validated ranges/IDs and documented source grade.
- One-second candle fallback **only after exact Binance USD-M Futures endpoint, supported intervals/history, limits and data provenance verification**. OHLC cannot prove intrasecond stop-versus-target or bid/ask; ambiguous cases stay scientific HOLD.
- Original entry/exit bid-ask/source timestamps, declared slippage, fee and settled funding evidence for independently source-verified after-cost net-R. Reject default-zero economics or complete-by-fixture training counts.
- Disk/archive quotas, safe sealed-file rotation, independently restored off-host custody or an explicit finite-capture HOLD. Crash-before/after-fsync and backup corruption tests.

Gate: Genuine source grade remains locked unless exact path and costs qualify. Verify repeated crash tests, source gaps, disk-full, resume, unresolved counts and finite-capacity stops. No paper release merely from synthetic economics.

### G7 — Learning with a scientifically sound complete population

Deliverables: join feature evidence at original decision time to genuinely matured, after-cost and independent outcomes. Preserve NO_TRADE, selection probabilities, held/unresolved outcomes, shared BTC time clusters and pattern overlaps. Establish no-trade/economically simpler baselines, chronological purged/embargoed validation and out-of-regime drift checks.

Checkpoint: **2,000 independent genuinely qualified matured outcomes** as initial research review policy, with independently assessed regime spread and event dependency; not a magic proof of advantage, not 2,000 paper trades, and not a forced quota.

Gate: No leak, no fake grade, no survivor bias, stable conditional edge with uncertainty, and explicit recommendation to continue learning/abstain when inconclusive.

### G8 — Training and freeze of the initial Champion

Deliverables: predeclared model family, bounded memory/CPU process on science snapshot, training cutoff, risk/cost policies, version and checksum; separate later holdout; realistic net-R calibration and downside/uncertainty; abstention. Default to minimal model complexity.

Gate: Qualified science and frozen model reproducible on independent later events; owner/reviewer approves a candidate to enter separately scoped PAPER release only when guardian controls pass.

### G9 — Paper engine and Guardian, first Champion

Deliverables: independent signed proposals, frozen Champion routing, guardian checks for freshness, source/quote/fee/funding, leverage/size/stop/exposure limits, single open simulated position in Champion Paper book, protected exit/trailing-stop state and durable cash/fill/account reconciliation.

**Resolve historic G7 conflict:** Existing guarded_paper.py appears to require two qualified models before paper unlock; the owner-approved lifecycle is first **one qualified Champion-only paper phase**, later dual model competition. Redesign the new release contract under independent tests, never silently weaken security.

Gate: PAPER-ONLY scope explicitly approved; no exchange order authority; faults, stale tokens, repeated entries, crashes, malformed economics and position limits are vetoed.

### G10 — Challenger and Promoter/Retainer fair paper comparison

Deliverables: another properly qualified candidate after a further **2,000 newly matured independent source-qualified outcomes** (review checkpoint, not guaranteed production quota); freeze both models and forward contest rules; separate Champion/Challenger cash, stops and positions; common forward conditions and comparable risk/cost, including abstentions.

Review at **at least 100 settled paper trades per model where meaningful and sufficient common evaluation period/regime diversity**, without forcing trades simply to hit 100. Compare after-cost returns, risk-adjusted performance, drawdown, exposure, source quality, selection confidence and cross-model dependence.

Gate: RETAIN, REJECT, HOLD/SUSPEND or RECOMMEND_PROMOTE only. No automatic self-promotion or unauthorized routing change. A retired Champion is preserved for approved rollback.

### G11 — Whole-loop integration and bounded performance

Deliverables: one truly integrated synthetic-grade end-to-end seven-stage scenario with genuine code seams, source/market/order mode separation, paper book fairness, model drift, NO_TRADE and all recovery branches; no injected fake-original label to count as G7 success.

Test CPU/RAM/disk, I/O jitter, at-5m boundary latency, 100 discovery + 20 deep, 40 active intents, two guarded paper books, streaming first-touch, fsync, source segments, compaction, off-host restore and multi-day projected usage. **No online validation claims without owner authorization.**

Gate: A reviewer can audit each event back to correct source and label; documentation and code versions align; tests protect nontrading default; results meet measured hardware budgets with headroom.

### G12 — Optional, owner-separate live trading project

NOT INCLUDED in V5.1 initial implementation authorization. Deliverables only after fresh owner request and independent review: exchange order permissions, exchange-side stop protections, stale-order/idempotent reconciliation, one global live position including open pending/partial, kill controls, funding/fee ledger, separate paper mirror, approval and rollback procedures.

Gate: No live trading unless a distinct, explicit decision and technical safety acceptance authorizes it.

## 4A. Permanent milestone AND micro-task checklist — update as work completes

**This checklist is mandatory in every future V5.1 development session.** A big milestone is **[ ]** until its *own* acceptance gate passes and every required small task beneath it is **[x]**. A small task may be ticked **[x] immediately once independently verified**, even while its parent milestone remains [ ]. NEVER wait for the whole stage to finish before recording a small achievement. NEVER tick a gate just because older NBOT previously had similar functionality.

**How to maintain it:**

1. At the **start** of every session, read this checklist and the owner-friendly checklist and report the exact last completed item and next open item.
2. Work in small, auditable increments. **Add new subtasks to the correct gate as soon as they are discovered** (including fixes, tests and blockers), rather than hiding work between broad headings.
3. Immediately upon completion of **each** small subtask, change its checkbox from **[ ] to [x]** and append a dated proof record: exact GitHub **commit or PR**, passing test or review evidence, and any source-data grade. An action is complete only when required evidence exists. If blocked, leave [ ] and add **HOLD + reason**, rather than ticking.
4. When every required subtask and gate acceptance rule passes, tick the corresponding **top-level G milestone** and log the evidence. Keep any optional/future authority **locked** if never separately approved; do not label its tasks done by using fake credentials or synthetic results.
5. **Update both engineering and owner checklists together** whenever progress changes, so the owner can see small and big achievements in plain English. Both files must remain synchronized in meaning; record exact filenames and GitHub commits, never a vague claim that it is "done".
6. Preserve previous evidence and note any regression explicitly. If tests later fail, mark the affected completion **REOPENED / HOLD**, untick it, record the reason, and re-qualify before PASS.
7. At the end of a session summarize **newly ticked items, unticked/blocked items, test results, modified files, exact branch/commit, current mode and next smallest task**. Don't create a manual worksheet outside GitHub to track progress.

**G0-01 verified documentation work (not proof that G0 is complete):**

- [x] **G0-01:** Commit the versioned register **docs/NBOT_V5_1_LEGACY_COMPONENT_REUSE_REGISTER_V1_0.md** with pinned historical source snapshots, 27 component candidates R01–R27, 12 conflicts C01–C12, test evidence grades and V5.1-only runtime identifier policy. **Date:** 15 Oct 2026 IST. **Evidence commit:** **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**; GitHub file retrieved and checked. **Tests:** document/file check only; no application/unit tests, source-quality audit, VPS or deployment activity during this task.
- [ ] **G0-02:** First selected component's complete dependency/security/source-grade/test audit, plus precise reviewed V5.1 destination.
- [ ] **G0-03:** VPS preservation and capacity inventory (without cleanup pending verified backup/rollback), despite new broad maintenance permission; no real-money release.

**Initial verified seed work (not proof that G0 is complete):**

- [x] **SEED-01:** Created new documentation-only **nbot-v5.1** branch without importing legacy working files; verified its first tree contained three documents (15 Oct 2026, initial branch commit **472c3f54415e06715f8b28673eee7d3b545338d4**).
- [x] **SEED-02:** Copied original Complete Vision **V1.9** byte-for-byte (Git blob **e965d63ae85467a6156cf6134ea001906c8ebe67**); owner and engineering roadmap V1.0 created (same commit).
- [ ] **G0 — Read-only recovery and legacy inventory complete**
  - [x] Record old relevant branches and pin original source commits, historical CI/test status and available GitHub evidence — 15 Oct 2026, preliminary inventory in register commit **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**; no new tests executed.
  - [x] Create Legacy Component Reuse Register covering candidate V4/V5 modules, origin, preliminary dependencies, named tests and COPY-AND-ADAPT / REIMPLEMENT / DISCARD / REFERENCE decisions — 27 entries, GitHub verified **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**.
  - [x] Identify baseline risks: 50-vs-100/20/40, source-grade evidence gaps, archival pressure, first-Champion paper unlock mismatch, stale V3/V3.9/V4/V5 imports/IDs — C01–C12, same commit.
  - [ ] G0-02: complete **per-selected-component** transitive import, hidden network/credential/order/DB side-effect audit with exact source blob, old test fixtures and new interface contract; register findings remain preliminary.
  - [ ] G0-03: with owner's newly granted VPS authority, first assess existing service/storage/backup/pin/retention metadata safely and document preservation/rollback before any cleanup; no destructive or operational VPS work in G0-01.
  - [ ] Present exact G1-01 first-port scope for owner review and obtain approval for the **first narrowly scoped application-code task**; G0-01 authorized documentation only.
- [ ] **G1 — New safe application foundation complete**
  - [ ] Agree minimal V5.1 module/interface tree and source/mode authority contracts.
  - [ ] Create approved clean files; port only reviewed source helpers with exact lineage.
  - [ ] Add and pass offline smoke, no-order, no-network, data-schema and import-isolation tests.
  - [ ] Audit accidental old dependencies and document initial measured resource footprint.
- [ ] **G2 — Lightweight 100-coin Observation complete**
  - [ ] Implement verified Binance USD-M eligibility, 50/25/25 overlapping groups, deduplication and BTC inclusion.
  - [ ] Add reliable completed-five-minute data, historical bootstrap, source-health, clock, source-epoch and gaps.
  - [ ] Persist compact event/selection records, as-of times and explicit unscorable reasons.
  - [ ] Pass mock 100-market rate, duplicate, disconnect, source-lag and RAM/CPU tests.
- [ ] **G3 — Causal Exploration and 24 detector states complete**
  - [ ] Independently verify exact old V4 24-detector list, semantics and safe selective adapter copying.
  - [ ] Encode BTC, market and individual-coin structures without future-data leakage.
  - [ ] Represent up to 200 directional possibilities with MATCH / NO_MATCH / UNAVAILABLE and capacity-skipped states.
  - [ ] Pass deterministic known-at feature tests, complete-denominator tests and no-forced-trade tests.
- [ ] **G4 — Select 20 and establish authentic deep market sources**
  - [ ] Implement transparent eligibility, source quality, regime diversity and Research/control-slot shortlist rules, BTC included.
  - [ ] Record frozen 20-symbol membership, source warm-up, decisions and rejected coins.
  - [ ] Integrate audited shared per-symbol original trade, quote and funding source custody with compressed hash-chained segments.
  - [ ] Demonstrate gap handling, safe disk quota, replay, source identity and representative deep-20 workload.
- [ ] **G5 — Rolling 40 virtual trades and trailing management complete**
  - [ ] Implement prospective frozen intent/entry/stop/target/trailing/horizon and one active experiment per coin+side.
  - [ ] Implement at-most-40 global active, verified intra-candle exits and forward source-first-touch tracking.
  - [ ] Reconcile at closed five-minute events and admit suitable replacements only into proven vacancies; no eight-new-trade quota.
  - [ ] Pass tests for all slots full, partial replacements, no valid candidate, trailing reversals, concurrency and idempotent restart.
- [ ] **G6 — Independent virtual economics, data recovery and archival complete**
  - [ ] Verify end-to-end original price-path, separate entry/exit quote, fee, slippage and settled-funding witnesses.
  - [ ] Add interrupted WSS/crash/unsynced RAM source-epoch HOLD and honest unresolved/ambiguous outcomes.
  - [ ] Validate exact USD-M historical second-candle or aggregate-trade retrieval assumptions **before using** them for recovery.
  - [ ] Implement and prove bounded durable storage, hash-chain archive rotation/restore or declared HOLD on quota.
  - [ ] Pass independent no-fake-fill/no-fake-label, gap, corruption, rate-limit, restart and disk-full tests.
- [ ] **G7 — Learning from mature, qualified after-cost evidence complete**
  - [ ] Build clean joining of historical known-at features to only genuinely qualified later outcomes.
  - [ ] Preserve sample-inclusion masks, NO_TRADE, source missingness and shared BTC event dependence.
  - [ ] Produce baseline and regime-conditional evaluation with chronological purged validation and uncertainty.
  - [ ] Independently review 2,000-qualified-outcome checkpoint and scientific quality; HOLD if unmet.
- [ ] **G8 — First frozen trained-model candidate complete**
  - [ ] Establish training cutoff, eligible model family and bounded science job, with no order authority.
  - [ ] Train only on qualified evidence and evaluate on later untouched market events.
  - [ ] Freeze reproducible model artifact, features, policy hashes and NO_TRADE logic.
  - [ ] Pass independent validation/approval or record reject/hold honestly.
- [ ] **G9 — Independently guarded FIRST Champion-only paper test complete**
  - [ ] Resolve the original V5 G7 two-model-first-paper contradiction under reviewed policy.
  - [ ] Implement secure mode-scoped proposal and separate Champion Paper one-position ledger/guardian.
  - [ ] Pass quote age, cost, trailing stop, accounting, risk veto, replay, restart and paper reconciliation tests.
  - [ ] Obtain distinct **paper-only** owner release authorization and confirm NO real-order capability.
- [ ] **G10 — Fair Challenger paper comparison and reviewed model promotion complete**
  - [ ] Qualify/freeze Challenger from another independently reviewed prospective outcome cohort.
  - [ ] Create separate Challenger Paper book using the same forward event window with independent cash/risk.
  - [ ] Evaluate settled after-cost trades, drawdown, common-period risk and abstentions without forced trading.
  - [ ] Produce RETAIN / HOLD / REJECT / RECOMMEND_PROMOTE with independent owner routing review; no autonomous model promotion.
- [ ] **G11 — End-to-end integration and low-resource endurance complete**
  - [ ] Show complete seven-stage synthetic-only path without fabricating original-grade evidence.
  - [ ] Prove 100 lightweight, 20 deep, rolling 40, two paper books and one-position safety invariants together.
  - [ ] Pass failures, security checks, source-grade gates and finite storage/restore scenarios.
  - [ ] Report bounded VPS RAM/CPU/I/O/disk/latency and obtain reviewed paper-operational GO/HOLD.
- [ ] **G12 — Future real trading release (NOT APPROVED; remains locked)**
  - [ ] Obtain distinct, explicit owner authorization for a separately scoped real trading project.
  - [ ] Review exchange account permissions, protective-order handling and actual pending/partial/position reconciliation.
  - [ ] Independently prove one global real position and risk kill/veto/rollback behavior.
  - [ ] Separate signed real-money release and production acceptance; no paper model can grant it.

**Proof register format (append one record per tick, including tiny tasks):**

| Date (IST) | Task ID | [x] or REOPENED/HOLD | Commit/PR or evidence | Test/result | Owner-facing explanation |
| --- | --- | --- | --- | --- | --- |
| 2026-10-15 | SEED-01 | [x] | 472c3f54415e06715f8b28673eee7d3b545338d4 | Git tree: 3 docs, no application files | New clean V5.1 branch exists; old sources remain on their branches |
| 2026-10-15 | SEED-02 | [x] | 472c3f54415e06715f8b28673eee7d3b545338d4 | Vision source/copy blob SHA match | The approved Vision V1.9 was carried over unchanged |
| 2026-10-15 | G0-01 source and conflict register | [x] | **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**; [register](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_LEGACY_COMPONENT_REUSE_REGISTER_V1_0.md) | GitHub source/document review verified 27 candidates, 12 conflicts; no application tests | Safe parts identified without importing legacy or claiming scientific validation |
| *Next* | G0-02 component-level dependency/side-effect audit | [ ] | *To be completed* | Require exact source blob and tests | Verify one safe pure component before writing V5.1 application code |

**Do not interpret SEED or G0-01 checks as passing G0, G1 or any engineering/science/release gate.** The branch began with only three docs; G0-01 added this fourth document. The owner has since permitted potential VPS inspection and maintenance, but G0-01 performed no VPS operations. No explicit first application-code component approval, paper-release authorization or real-money trading release follows from this documentation approval.

## 5. Work management: each gate's report format

Each gate should produce a concise owner-facing summary and an auditable engineering appendix:

- Gate ID / purpose / present status: TODO, IN PROGRESS, PASS, HOLD, BLOCKED, or REJECTED.
- Exact code/contract changed, GitHub commit and test evidence; no destructive edits or default-branch merges.
- Specific old source copied, if any, with SHA and reason for selection; any rejected legacy dependency.
- Source provenance grade, dataset time windows, synthetic/original distinctions, sample count, missingness and limitations.
- Risk/permission implications: always list whether any paper or live authority changed (normally NONE).
- RAM/CPU/disk/latency test measurements when relevant, before claiming readiness.
- Explicit remaining failures and the narrow next step, identifying fresh owner approvals needed.

**PASS means demonstration with credible evidence**, not a check mark from a predecessor version. Any missing original economic witnesses yield HOLD.

## 6. File layout to propose after G0/G1 approval — not yet created

Small, deliberately conceptual initial namespace (subject to inventory and code review):

- core: event clock, types, feature/source ID hashes, permission policies.
- observation: 100-broad universe and five-minute causal market snapshots.
- exploration: 24-pattern adapter, regime/coin structures and explicit non-evaluation masking.
- research: shortlist admission, 20-deep stream custody, 40-active rolling virtual pool, trailing/source evidence and economic outcomes.
- learning: qualified evidence population, chronology-aware evaluation, after-cost score and uncertainty.
- training: frozen model artifact, training metadata, calibrated outputs and abstention.
- promotion: Champion/Challenger comparison and independent approval recommendations.
- decisions: frozen Champion/Challenger inference and NO_TRADE.
- guardian: independent paper ledger, mode-scoped permissions, stop/risk checks and future separately authorized live interface.
- tests: deterministic source/corruption/crash/performance/economic contract tests.

Do **not** create all modules at once. Build the smallest vertical slice with sound source and permission boundaries, then add gates incrementally.

## 7. Immediate first assignment for a new ChatGPT session

**Task:** Perform the read-only **Legacy Component Reuse Assessment** for NBOT V5.1.

1. Open only authorized GitHub branches and the new three-document V5.1 branch. Do not touch user laptop or remote VPSs.
2. Inventory relevant V4/V5 modules, automated tests, contracts and known source/economic hold gates from GitHub.
3. Produce a precise component reuse register and map current code to **G0–G12**: what exists, what can be ported, what must be rewritten or newly implemented.
4. Investigate current hard 50-market capacity, missing 100/20 bridge, full 24 detector adapter quality, raw-source archival, true after-cost label flow and first-Champion paper unlock mismatch.
5. Propose the narrowest safe **first code change** only after inventory and owner authorization. Do not write code or open any PR on the first read-only session unless explicitly instructed.

**Keep in view:** No laptop changes, VPS commands, service starts, paper/live orders, deletions, old-branch edits, secrets, merges or release authority without new explicit owner approval.

---

**Engineering success criterion:** Build the smallest safe closed evidence loop in which every price-derived claim can be traced to authentic known-at source and every actual future order remains independently guarded.
