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
- [x] **G0-02:** Selected source `nbot/v5/observation_contract.py` blob `99b9544fe32239e7b707b6ea09a87a452210034b`, helper/test/package SHA audit and complete *selected pure-helper* standard-library call graph reviewed; exclude `MAX_SYMBOLS=50`, SQLite, legacy imports and `nbot/__init__.py` V3.0.0. Proposed `nbot_v5_1/{__init__.py,core.py}`, `tests/test_v5_1_core.py` with 12 negative/positive checks. **15 Oct 2026**, register audit commit **2ebcc62f9f13aa4c7ed532cca108d9c359c77363**. **Static review only: zero code imported/tests run.**
- [x] **G0-03:** **Read-only live VPS preservation and backup assessment complete 15 Oct 2026.** Report **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28** (both authorized PuTTY profiles). Execution paper receipts=253, observation DB 15 tables and sqlite-wal/shm intact, read-only quick_check=ok, old observation unit disabled/inactive, legacy Git head 47dd5fa on both, RAM 952 MiB each, root disk 40/90 GiB available. No verified product backup or restore. **This checks the INVENTORY, not backup readiness.**
- [x] **G0-03-R1 owner waiver DECISION:** Owner expressly rejected creating or verifying any backup/restore for unneeded old NBOT VPS files. **N/A BY OWNER WAIVER, NOT BACKUP PASS**; accepts permanent loss of old SQLite/WAL, legacy data and paper receipts. 15 Oct 2026, waiver commit **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc**.
- [x] **G0-03-R2 owner decision:** Abandonment / future NBOT-only cleanup without old backups is owner-authorized in principle. **No VPS deletion was performed by G0-03.** 15 Oct 2026, same waiver commit.
- [x] **G0-CLEANUP-01/02:** Separate successful owner PuTTY cleanup outputs received for Execution-VPS and Observation-VPS, 15 Oct 2026; full proof **81dadf68a9949b847fd8f38336c5d532eab861cd**.
- [x] **G0-CLEANUP-03/04:** Independent read-only SSH rechecks at 05:30:38Z (Execution) and 05:30:43Z (Observation) verified two old NBOT program directories, markers and retired service path absent; no matching systemd NBOT unit/process; SSH functioning; verifier exit 0.
- [x] **G0-CLEANUP-05 / G0-03-CLEANUP-EXEC:** **PASS** for named legacy installations, 15 Oct 2026; [full after-state](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_CLEANUP_COMPLETION_20261015.md), commit **81dadf68a9949b847fd8f38336c5d532eab861cd**. No old backups (owner waiver).

**Initial verified seed work (not proof that G0 is complete):**

- [x] **SEED-01:** Created new documentation-only **nbot-v5.1** branch without importing legacy working files; verified its first tree contained three documents (15 Oct 2026, initial branch commit **472c3f54415e06715f8b28673eee7d3b545338d4**).
- [x] **SEED-02:** Copied original Complete Vision **V1.9** byte-for-byte (Git blob **e965d63ae85467a6156cf6134ea001906c8ebe67**); owner and engineering roadmap V1.0 created (same commit).
- [x] **G0 — Legacy audit, owner-authorized fresh start, verified VPS cleanup and first-code scope COMPLETE (15 Oct 2026).** Exact named old NBOT files/services independently absent from both VPSs; GitHub evidence **81dadf68a9949b847fd8f38336c5d532eab861cd**; historical backups explicitly waived. G1 and future gates unchanged.
  - [x] Record old relevant branches and pin original source commits, historical CI/test status and available GitHub evidence — 15 Oct 2026, preliminary inventory in register commit **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**; no new tests executed.
  - [x] Create Legacy Component Reuse Register covering candidate V4/V5 modules, origin, preliminary dependencies, named tests and COPY-AND-ADAPT / REIMPLEMENT / DISCARD / REFERENCE decisions — 27 entries, GitHub verified **5d5133766b96ad3b21ab8b4c553e08740c3c7adb**.
  - [x] Identify baseline risks: 50-vs-100/20/40, source-grade evidence gaps, archival pressure, first-Champion paper unlock mismatch, stale V3/V3.9/V4/V5 imports/IDs — C01–C12, same commit.
  - [x] G0-02: complete first **selected pure helpers** transitive standard-library call graph, exclude hidden network/credential/order/DB/old package effects, pin full old blob/test hashes and define new interface + T01–T12 test plan — register commit **2ebcc62f9f13aa4c7ed532cca108d9c359c77363**, 15 Oct 2026; static review only. **Other R01–R27 future port audits remain open.**
  - [x] G0-03: Using newly authorized NBOT-scoped saved PuTTY connections, inventory both VPSs, legacy source/data, service status, backup gaps, source DB/WAL and host resource budgets; preservation and rollback **plan documented** — 15 Oct 2026, report commit **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28**; no destructive commands, no services started or stopped, no exchange calls.
  - [x] G0-03-R1/R2 **owner decision closed**, 15 Oct 2026: legacy backup/restore **waived, not performed**, old NBOT-only VPS data may be abandoned, subject to separately logged cleanup execution; recorded in **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc**. This does not waive new V5.1 runtime crash/source custody or authorization gates.
  - [x] **G0-CLEANUP-01–05 / G0-03-CLEANUP-EXEC:** Owner-run manual cleanup separately confirmed by exact-path/retired-unit absence, service/process name check and SSH access on both VPSs. 15 Oct 2026, independently verified **81dadf68a9949b847fd8f38336c5d532eab861cd**; no backups made (waived), no old GitHub branch change.
  - [x] **G0-04-F1:** New package `nbot_v5_1` and exactly three new first-code file paths approved, 15 Oct 2026 — **7c624de187e274fe40172e64d03b8697f6e1f7aa**.
  - [x] **G0-04-F2:** Pinned pure-helper source lineage, transitive imports and explicit legacy exclusions accepted — **7c624de187e274fe40172e64d03b8697f6e1f7aa**.
  - [x] **G0-04-F3:** V5.1 clock/evidence/hold/hash/no-order API fixed as pure stdlib-only contracts — **7c624de187e274fe40172e64d03b8697f6e1f7aa**.
  - [x] **G0-04-F4:** T01–T12 offline test matrix and real proof gate specified (not yet executed) — **7c624de187e274fe40172e64d03b8697f6e1f7aa**.
  - [x] **G0-04-CLOSE:** Owner explicitly requested G0-04 first-code scope finalized **meanwhile** manual old VPS cleanup proceeds. Scope approval complete, 15 Oct 2026, **7c624de187e274fe40172e64d03b8697f6e1f7aa**. Do not confuse with G1-01 implementation, deployment or cleanup acceptance.
- [ ] **G1 — New safe application foundation complete**
  - [x] **G1-01 preliminary approved interface/scope:** `nbot_v5_1/__init__.py`, `nbot_v5_1/core.py`, `tests/test_v5_1_core.py` and fixed source/mode authority API — G0-04 **7c624de187e274fe40172e64d03b8697f6e1f7aa**, 15 Oct 2026. This is design acceptance only.
  - [x] **G1-01-A:** Create only three independent new files in `nbot-v5.1`: `nbot_v5_1/__init__.py` (commit `e22b55abcc0631b603b5357a8be9122008bb1ef0`), `nbot_v5_1/core.py` (commit `5d9fc0e22e0cc113353cd20593cce0cb687be2c1`), `tests/test_v5_1_core.py` (commit `f859f7f92a9614267fd4e7bfbc5cb6701bdb5288`). **15 Oct 2026**. Adapted only G0-02 audited pure behaviors, no old namespace/SQLite/50-coin imports.
  - [x] **G1-01-B:** Execute **T01–T12 offline** with command `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1_core.py' -v`: **12 run, 12 PASS, 0 failures/errors** on Python **3.13.5**, 15 Oct 2026. Negative cases cover premature/future/noninteger clocks, malformed source, missing BTC, nonfinite values and forbidden trading imports. **Only synthetic fixtures**.
  - [x] **G1-01-C:** Static AST import review PASS: pure core imports only `__future__`, `dataclasses`, `enum`, `hashlib`, `json`, `re`; no SQLite, file-writer, socket, exchange SDK, old 50 limit or old `nbot` import. Local 12-test process `/usr/bin/time` wall **0.78s**, maximum RSS **99,728 KiB** (tool/Python test overhead included, **not a VPS capacity benchmark**). Python 3.12 syntax parsing of all 3 files PASS; **Python 3.12 runtime suite NOT executed**.
  - [x] **G1-01-D:** Read back all three GitHub files; their Git blob hashes match the offline-tested local bytes (listed in the G1-01 evidence appendix below). GitHub compare from closed G0 HEAD `466446aa4e720ac85b5dd9c6c5d93c9e1aa81e1e` shows **only these 3 source/test files** changed, no documents/services/legacy files in code commits.
  - [x] **G1-01 — First safe pure-core implementation and tests COMPLETE**, 15 Oct 2026; proof/limitations in §G1-01 appendix below. No VPS service, market connection, paper/real order, exchange credential or deployment used.
  - [x] **G1-02-A — Locked mode configuration:** New `nbot_v5_1/foundation.py`, immutable OFFLINE default; OBSERVATION descriptor only without network; VIRTUAL/PAPER/REAL mode declarations cannot be activated. **15 Oct 2026**, [G1-02 proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_02_FOUNDATION_ACCEPTANCE_20261015.md), commit **88c0f8acfec85eaf75b80529fd22b1274922baac**; F01–F03 PASS.
  - [x] **G1-02-B — Conservative evidence grades:** UNKNOWN/SYNTHETIC/METADATA_ONLY permitted; ORIGINAL_VERIFIED and AFTER_COST_QUALIFIED declared only, **cannot be issued** by G1. F07/F12 PASS, same proof.
  - [x] **G1-02-C — Immutable proposal, independent veto guardian:** strict known-at symbol, event/expiry, model fingerprint; guardian ALWAYS authority NONE, NO_TRADE, with source/btc/malformed evidence/attestation reason codes; F04–F06/F08–F15 PASS. Same proof.
  - [x] **G1-02-D — Bounded metadata audit journal:** New `nbot_v5_1/journal.py`, versioned `JournalEvent`, private file, linked digest, append-only fsync, duplicate-id replay, 4 MiB default quota; J01–J04/J12 PASS, same proof.
  - [x] **G1-02-E — Fail-closed recovery/multiwriter tests:** torn-tail, changed SHA, unsupported schema, wrong sequence, symlink/hardlink/mode permissions, restart replay, guardian veto audit, and three concurrent child writer processes verified by J05–J11/J13–J18. This is **bounded audit journal testing, not full product crash/host failover**.
  - [x] **G1-02-F — Combined G1 regression tests:** Final `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1_*.py' -v` ran **45/45 PASS, 0 failures/errors** on Python 3.13.5 Linux; timed wall 2.44s, max RSS ~100,624 KiB including test runner. All 7 current Python files parse with 3.12 grammar; **Python 3.12 runtime NOT tested**. Same proof.
  - [x] **G1-02-G — GitHub byte/source audit:** All 5 changed files' Git blob SHA-1 match actual offline-tested copies, and `compare` from G1-01 head `2544f6af438ca9b30e986fec59e7a2b41a121ec3` shows exactly two new modules, two new test files, and one existing test-harness repair. No deployment/services.
  - [x] **G1-02-H — G1-01 cross-suite import regression fix:** Old T01 safety harness reloaded globally shared Python dataclasses; moved test to isolated blocked-I/O subprocess; whole 45-suite PASS. Existing production `core.py` unchanged.
  - [x] **G1-02 — MODE / JOURNAL / GUARDIAN FOUNDATION COMPLETE**, 15 Oct 2026. Report **88c0f8acfec85eaf75b80529fd22b1274922baac**; pure-mode guarded code, synthetic tests, and exact GitHub source hashes verified. **No exchange API, raw market capture, service deployment or trading approval.**
  - [ ] **G1-03 — G1 remaining recovery/integration acceptance:** independently check full interface/composition, directory-fsync/durable first-file creation, crash/restart/rotations, Python target runtime, failure injection, and no-order guard before marking parent G1 PASS. **NOT STARTED.**
  - [ ] **G1 parent engineering acceptance:** complete later G1 tasks and an independent full offline integration/safety acceptance before marking G1 [x]. **HOLD** until proven.
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
| 2026-10-15 | G0-02 first pure-helper dependency/security/test audit | [x] | **2ebcc62f9f13aa4c7ed532cca108d9c359c77363**; [G0-02 appendix](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_LEGACY_COMPONENT_REUSE_REGISTER_V1_0.md) §8 | Complete selected-helper GitHub static source/test/package review; 12 *planned* offline tests, none executed | Identified a safe limited source of behavior; rejected old DB, fixed-50 and V3 package identity |
| 2026-10-15 | G0-03 live preservation and backup assessment | [x] | **aea9a21776d4fcf4521ac4d55ca9aa083f5fdf28**; [full report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_03_VPS_PRESERVATION_BACKUP_ASSESSMENT_20261015.md) | Both SSH inspections PASS; old DB mode=ro SQLite quick_check=ok; 15 tables, 253 paper receipts, SHA hashes; no backup restore attempted | We know which historical data must be protected and which backups are missing |
| 2026-10-15 | G0-03-R1/R2 owner waiver decision | [x] (WAIVED / NO BACKUP DONE) | **7e9c2e6eb83bb9d3112386dad936e45e373dbcfc**; original assessment + §8 owner override | Verified owner instruction and GitHub document update only; 0 backups, 0 restorations, 0 VPS deletions | Owner chose to start fresh and accept loss of old VPS-only history; no mandatory legacy backup remains |
| 2026-10-15 | G0-04-F1/F2/F3/F4 and first-code scope closed | [x] | **7c624de187e274fe40172e64d03b8697f6e1f7aa**; [scope V1.0](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_04_FIRST_CODE_SCOPE_V1_0.md) | 3 file paths, pinned lineage, pure interfaces and 12 planned tests independently documented; **no tests/code run** | Tiny safe V5.1 foundation scope approved while owner performs manual old-VPS cleanup |
| 2026-10-15 | G0-04 proposed code scope | [x] DRAFT ONLY | **697b55f4201e7d4f76daaa0bde0efc113b3c99f7**; [scope document](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_04_FIRST_CODE_SCOPE_V1_0.md) | Three future files, 12 test cases specified; no code/tests run | Clear first tiny V5.1 foundation is ready for review after cleanup |
| 2026-10-15 | G0-CLEANUP-01–05 / G0-03-CLEANUP-EXEC | [x] | **81dadf68a9949b847fd8f38336c5d532eab861cd**; [independent two-host cleanup report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G0_CLEANUP_COMPLETION_20261015.md) | Both user PuTTY successes; remote read-only verifier exits 0; old checked paths, service unit and name-matched processes absent | All known old NBOT installations cleared; no backups created by explicit owner choice |
| 2026-10-15 | G0 parent full gate | [x] | **81dadf68a9949b847fd8f38336c5d532eab861cd**, earlier G0-01/G0-02/G0-03 and G0-04 commits | Documentation, first-helper safety review, owner waiver, VPS after-state and first-code API scope all evidenced | We can safely begin the *development stage*, not trading |
| 2026-10-15 | G1-01 first independent V5.1 package and core | [x] | `e22b55abcc0631b603b5357a8be9122008bb1ef0`; `5d9fc0e22e0cc113353cd20593cce0cb687be2c1` | Static imports audited; 5-min immutable event, HOLD source validator, version/domain-safe digest, order authority NONE implemented | First actual V5.1 source code exists without old V3/V4/V5 modules |
| 2026-10-15 | G1-01 T01–T12 offline tests | [x] | `f859f7f92a9614267fd4e7bfbc5cb6701bdb5288`; tested SHA blobs listed in appendix | **12/12 tests PASS**, Python3.13.5, no network, DB, exchange or trading; Python3.12 syntax PASS but not 3.12 runtime tested | Safe first foundations passed synthetic negative/positive tests |
| 2026-10-15 | G1-01 hash audit, no-old-dependencies and local resource check | [x] | All three GitHub blobs match offline-tested bytes; scope exactly 3 files | AST/no-order/import checks PASS; local test wall 0.78s, maxRSS 99,728 KiB; no VPS load qualification | Code is traceable, small, and deliberately unable to trade |
| 2026-10-15 | G1-01 child completion | [x] | Same 3 application/test commits, synthetic offline evidence | All G1-01 criteria PASS; parent G1 **remains [ ]** | First engineering coding step finished, but the full bot is not yet built |
| 2026-10-15 | G1-02-A/B/C safe configuration, source grades, guardian envelopes | [x] | **88c0f8acfec85eaf75b80529fd22b1274922baac**, `foundation.py` SHA `b2f191b478125cf06937e1498f059737d0081a58` | 15 offline tests F01–F15 PASS; paper/real modes locked, NO_TRADE veto and malformed BTC/time/model source HOLD | Future modes are described safely, but none can start trading |
| 2026-10-15 | G1-02-D/E journal and failure/restart tests | [x] | **88c0f8acfec85eaf75b80529fd22b1274922baac**, `journal.py` SHA `be47689791602b9c4d607ff4437c90e16710b2f8` | 18 offline J01–J18 PASS; private append-only, bounded, fsync, hash tamper/dedup, broken tails and three concurrent writers | A small metadata audit trail now exists; it is not the market source archive |
| 2026-10-15 | G1-02-F/G/H regression/byte-identical commit proof | [x] | **88c0f8acfec85eaf75b80529fd22b1274922baac**, exact verified GitHub hashes for all five files; full combined suite | **45/45 PASS**, Python 3.13.5; 3.12 syntax PASS (not 3.12 runtime); corrected in-process module reload test | The new components and old core work together in synthetic offline checks |
| 2026-10-15 | G1-02 child milestone completed | [x] | **88c0f8acfec85eaf75b80529fd22b1274922baac**, [full G1-02 test report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_02_FOUNDATION_ACCEPTANCE_20261015.md) | No network/order interface and no VPS code deployment; parent G1 remains [ ] | Safe foundation parts added; full integration and new evidence recovery not yet accepted |
| *Next* | G1-03 / parent G1 integration and recovery acceptance | [ ] | NOT STARTED | Target Python runtime, crash/first-file durability and whole-G1 fail-closed integration still require proof | Finish all foundation checks before enabling any services |
| 2026-10-15 | G0-04 owner review of first G1-01 code scope | [x] SCOPE ONLY | **7c624de187e274fe40172e64d03b8697f6e1f7aa**; latest user instruction | Approved exact no-order pure package and test contract; **0 application files** | First code path now decided; actual implementation still requires separate G1 evidence |

**Latest verified status (15 Oct 2026): G0 parent COMPLETE**, after old VPS cleanup was performed by the owner and independently verified, in addition to the earlier G0-01 register, G0-02 first-helper review, G0-03 source inventory/old-backup waiver and G0-04 three-file scope approval. **81dadf68a9949b847fd8f38336c5d532eab861cd**. G0 was documentary and server-preparation work, **not an application test**. **G1-01 code/tests and all subsequent gates remain OPEN; paper and real trading LOCKED.** Legacy GitHub branches unchanged. NEW V5.1 source custody, scientific after-cost provenance and recovery obligations remain mandatory.

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

1. **Historical initial-session instruction (completed):** GitHub-only review of the former three-document V5.1 seed. Later, the owner authorized controlled PuTTY/VPS maintenance; follow G0-03 preservation and safety rules, not this old read-only first-session constraint.
2. Inventory relevant V4/V5 modules, automated tests, contracts and known source/economic hold gates from GitHub.
3. Produce a precise component reuse register and map current code to **G0–G12**: what exists, what can be ported, what must be rewritten or newly implemented.
4. Investigate current hard 50-market capacity, missing 100/20 bridge, full 24 detector adapter quality, raw-source archival, true after-cost label flow and first-Champion paper unlock mismatch.
5. Propose the narrowest safe **first code change** only after inventory and owner authorization. Do not write code or open any PR on the first read-only session unless explicitly instructed.

**Current boundaries and later owner override 15 Oct 2026:** GitHub work and NBOT-scoped use of PuTTY sessions `Execution-VPS` and `Observation-VPS` are permitted for development/maintenance; avoid unrelated laptop files and never reveal/move private keys. The owner **waived backup/restore of old-version NBOT-only VPS material**, and accepted irreversible loss; its removal may be scoped and tracked separately without an old-backup gate. Preserve old **GitHub** reference branches, Ubuntu/SSH/unrelated files, and all new V5.1 source/cost/recovery safety contracts. Never merge to main, enable paper release, or place/authorize real exchange orders without distinct review. G0-03 waiver update used GitHub only.

---

**Engineering success criterion:** Build the smallest safe closed evidence loop in which every price-derived claim can be traced to authentic known-at source and every actual future order remains independently guarded.


**G0 final verification, 15 Oct 2026:** The initial blocked remote command is historical. The owner later performed manual cleanup on both VPSs and provided PuTTY success logs. Subsequent read-only SSH checks verified old NBOT directories/markers absent, retired Observation unit absent, matching NBOT unit/process checks empty and SSH still accessible on each server; report commit **81dadf68a9949b847fd8f38336c5d532eab861cd**. Both owner and engineering G0 parent milestones, G0-03-CLEANUP-EXEC and G0-04 scope are now **[x]**. **G1-01 code/tests [ ]**; no deployment, paper, testnet or live trading approval. Historical old-VPS backups were waived and not performed.


## G1-01 implementation evidence appendix — 15 October 2026

**Outcome: G1-01 PASS (only this narrow first-code slice); G1 parent stays [ ].** Exactly the approved three new files were committed to the isolated `nbot-v5.1` branch and independently read back; compared with their locally run working copies by Git blob SHA:

| File | GitHub commit introducing it | Verified Git blob SHA-1 | Role |
| --- | --- | --- | --- |
| `nbot_v5_1/__init__.py` | `e22b55abcc0631b603b5357a8be9122008bb1ef0` | `0957a162d15a2a4bfdf0297fa006ac19138a6123` | Version `5.1.0` with no import-time startup |
| `nbot_v5_1/core.py` | `5d9fc0e22e0cc113353cd20593cce0cb687be2c1` | `86d82f5d495606bef7274edd29035a8461b06b1b` | Frozen close-only five-minute event, HOLD reasons, strict canonical SHA-256 IDs, NONE/NO_TRADE enums |
| `tests/test_v5_1_core.py` | `f859f7f92a9614267fd4e7bfbc5cb6701bdb5288` | `596d15de9f3f8d823a14dcbb359719c4f2d1a02e` | Exactly 12 named offline tests with subtests |

**Test command:** `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_v5_1_core.py' -v` executed from an isolated local verification worktree containing exact matching GitHub blob bytes. **Final run: 12 tests, 12 PASS, 0 errors, 0 failures**, elapsed about 0.007 seconds (unittest reported), runner wall 0.78 seconds (includes Python/test startup), peak process RSS ~99,728 KiB. Interpreter Python 3.13.5 on Linux; Python 3.12 AST syntax compatibility PASS, **not a Python 3.12 runtime run**. These are local synthetic unit tests, **not** GitHub CI, actual source-grade market evidence, Binance accounts or a target VPS load test.

| Test | Final result | Meaning |
| --- | --- | --- |
| T01 | [x] PASS | Module reload under blocked network, SQLite, subprocess, OS command, file-write hooks; no order side effects |
| T02 | [x] PASS | Isolated V5.1 package and schema/version identity; no old package import or startup |
| T03 | [x] PASS | Closed five-minute boundary and frozen event records |
| T04 | [x] PASS | Bool/float/negative/misaligned/open event, stale/future timestamp fail-closed |
| T05 | [x] PASS | Missing BTC/symbol, stale/future candle, unhealthy/unknown route/epoch/digest HOLD |
| T06 | [x] PASS | Missing or malformed digest cannot imply source custody or after-cost profit |
| T07 | [x] PASS | Deterministic, domain- and V5.1-version-separated SHA-256 IDs |
| T08 | [x] PASS | Reject float/NaN/Infinity, non-JSON objects, bad keys, circular references |
| T09 | [x] PASS | Stable, sorted, deduplicated reason codes and strict prefix validation |
| T10 | [x] PASS | Only NONE trading authority, OBSERVE_ONLY/HOLD/NO_TRADE dispositions, no order interface |
| T11 | [x] PASS | AST/core import dependency audit excludes old code, fixed 50, SQLite, old database hooks |
| T12 | [x] PASS | Repeated synthetic offline deterministic evaluation and no application filesystem effects |

**Quality note:** An initial pre-commit test-harness run surfaced 5 errors caused by reloading the module while retaining the prior test class references; the **test harness** was corrected to rebind fresh types after reload. The *final* 12/12 run then passed and the exact corrected test source was committed. No failing application behavior was concealed or claimed as scientific proof.

**Limits/next gate:** G1-01 does **not** implement a market socket, 100-symbol discovery, 20 deep original-source capture, 40 research slots, 24 V4 detectors, storage/journal, model, executor or any order. A source hash is an identity aid, not independent custody. New V5.1 original source must be preserved/verified in later stages (owner waiver concerned only OLD VPS data). Neither VPS was deployed to; no existing service was started. **Paper, testnet/real-money releases are LOCKED; G1 parent and G2+ [ ].**


## G1-02 acceptance addendum — 15 Oct 2026

The owner authorized completion of G1-02 after verified G1-01. The exact new-code scope is **two modules** (`foundation.py`, `journal.py`), **two new test modules** (`test_v5_1_foundation.py`, `test_v5_1_journal.py`) and a narrow repair to the previous G1-01 T01 test harness, not to the production core. [Dated G1-02 report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_02_FOUNDATION_ACCEPTANCE_20261015.md), commit **88c0f8acfec85eaf75b80529fd22b1274922baac**. Every SHA matches the final locally executed 45-test source set.

**Verified:** **12 core + 15 mode/guardian + 18 journal tests = 45/45 PASS**; Python 3.13.5 local isolated Linux only, 3.12 grammar parsing of seven files successful, no 3.12 interpreter run, no CI or VPS tests. Guardian is irrevocably NONE/NO_TRADE; configs cannot enable PAPER/REAL or network, and new evidence grades cannot be falsely promoted. Journal is small/private/hash-linked with fsync and replay/tamper failures, NOT an original market archive or provably WORM chain. Changes made only on `nbot-v5.1`; no laptop copy, old-version module import, VPS service, exchange account or order.

**G1-02 [x] PASSED**. **G1 parent [ ] NOT PASSED**: additional integration/bootstrap/host-crash/directory-fsync/target Python verification and future source custody gates remain open. Owner legacy-backup waiver applies only to deleted OLD data; it never reduces new V5.1 evidence durability requirements. Paper/REAL stay LOCKED.
