# NBOT V5.1 — Detailed Engineering and Recovery Roadmap

**Roadmap version:** 1.3 (G4 selected engineering and independent live source HOLD)  
**Date:** 15 October 2026  
**Status (current, 15 October 2026):** **G0–G3 [x] PASS**, **G4 [ ] HOLD — partly implemented**. Selected BTC-including 20 deep markets and implemented public USD-M WSS byte frame/segment/funding foundations; **186/186 Python3.12.3 tests PASS on BOTH VPSs**, both 3,600-frame source benchmark PASS. Real public 20-source one-shot capture **3,077 raw WSS frames replayed** but **47 TRADE ID discontinuity rejects and 19/20 accepted trade-feed symbols**, no long-duration production source/independent off-host archive. **G4-06-A/B/C/D/E remain [ ]; G5–G12 [ ], all trading/production releases LOCKED.** Prior dated sections reflect their earlier chronology.  
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
- [x] **G1 — New safe NONTRADING application foundation COMPLETE, 15 October 2026.** This is **offline G1 engineering acceptance**, not permission for market streaming, paper/testnet or real trading. Exact code/test SHA, both-target-Python verification and limits in [G1 final report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md), commit **bb0df4b727e5817d47fe693206baba91e2706456**.
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
  - [x] **G1-03-A — Source envelope contract:** New `source_contract.py` V5.1-only source route/epoch/sequence/time/digest types; source timestamps and gaps validated, **even perfect metadata remains SOURCE_UNAUTHENTICATED_G1**; G01–G05 PASS, 15 Oct 2026, proof **bb0df4b727e5817d47fe693206baba91e2706456**.
  - [x] **G1-03-B — Restart HOLD:** New `bootstrap.py` replay/immutable recovery assessment; every restart remains OFFLINE/authority NONE/disposition HOLD; corrupt journal refuses startup provenance; explicit idempotent RESTART_HOLD record; G06–G09 PASS.
  - [x] **G1-03-C — Durable journal first-create and retry:** `journal.py` parent-directory fsync, safe parent checks, idempotent retries re-sync file AND directory; simulated fsync error refuses false success; G10–G11 PASS.
  - [x] **G1-03-D — Failure injection/migration/finite disk:** Partial write/torn tail, changed hash, schema mismatch rejected with no unreviewed legacy migrations, quota full HOLD without silent rotation; G12–G15 PASS. **Real power-cut and offsite source restore are LATER gates, not falsely claimed**.
  - [x] **G1-03-E — Full composition and mode lock:** Strict restart inputs, guardian BTC/symbol/source time identity with veto-only order authority and journal append, abrupt subprocess exit/replay, no old imports/SDKs, runtime mode lock, unsafe shared parent rejection; G16–G22 PASS.
  - [x] **G1-03-F — Full local cross-module regression:** **67/67 PASS, no errors/failures** (12 core + 15 foundation + 18 journal + 22 G1-03) on Python 3.13.5; run wall 2.94s, max RSS 100,748 KiB test runner included; 10 Python modules parse for 3.12.
  - [x] **G1-03-G — Tested bytes committed:** GitHub G1-03 code base `c1408ff00ff05ec6349a85202ee877708df87cd0`, exactly 4 changed source/test files since G1-02; all four Git blob SHAs match tested local bytes; proof **bb0df4b727e5817d47fe693206baba91e2706456**.
  - [x] **G1-03 COMPLETE — Source/restart/journal durability/failure controls accepted offline**, 15 Oct 2026. No order, connection or permanent VPS checkout.
  - [x] **G1-04-A — Observation-VPS target-runtime acceptance:** Direct read-only SSH via saved profile confirmed Python **3.12.3** and transient exact-GitHub-checkout full suite **67/67 PASS** (1.383s), process exit 0, auto-cleaned; exact commit `c1408ff...`; proof **bb0df4b727e5817d47fe693206baba91e2706456**.
  - [x] **G1-04-B — Execution-VPS target-runtime acceptance:** Independent server, Python **3.12.3**, same exact commit, full **67/67 PASS** (1.504s), process exit 0, auto-cleaned; proof **bb0df4b727e5817d47fe693206baba91e2706456**.
  - [x] **G1-04-C — Independent no-release/no-deploy check:** No permanent `/home/ubuntu/Nbot` installed by testing, no NBOT application service started, no Binance account/order used, no legacy GitHub source branch changed.
  - [x] **G1-04-D — Owner safety/audit acceptance:** Complete G1-01/02/03 set, stdlib-only, versioned types, synthetic crash/metadata HOLD and 3.12 target-platform tests evidenced; physical power-cut, multi-host custody and real-source maturity **explicitly future gates**; proof **bb0df4b727e5817d47fe693206baba91e2706456**.
  - [x] **G1-04 final independent acceptance and G1 parent PASS**, 15 Oct 2026; source/clock, no-order guard, bounded audit/restart and tests fully reviewed. Paper/REAL release remain LOCKED. [Final report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md).
  **Chronology note:** G2 was originally the next stage after G1; it is NOW accepted separately below as a lightweight read-only engineering gate, NOT G1's source/custody outcome.
- [x] **G2 — Lightweight, read-only 100-coin Observation ENGINEERING GATE COMPLETE, 15 Oct 2026.** Code and public-source read-only acceptance, full **120/120 tests on BOTH target VPSs**, 100×96×120 stress metrics and final report **005d82324d7cb009e4939075b49e00e41e25f271**. This **DOES NOT** release any service, models, paper/live trading or independently authenticated trade/quote economic source grade.
  - [x] **G2-01-A:** Verified Binance USD-M TRADING/PERPETUAL/USDT-margin eligibility, finite 24h quote turnover, bid/ask spread, >=96 completed candle history, rejection reasons and source flags. **U01–U10 PASS**, [full G2 proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md).
  - [x] **G2-01-B:** Deterministic union of 50 high-turnover/25 gainers/25 losers, preserve overlapping tags, qualified BTC mandatory, fill gaps with other qualified liquid symbols; exactly 100 unique when eligible or honest smaller cohort; reproducible selection SHA.
  - [x] **G2-01-C:** Versioned point-in-time universe manifest; all three source raw byte SHA-256 witnesses, independent known-at times with <=15s skew and <=60s age, source digest and all qualifying/rejection reasons. **R01–R10 PASS** (decoded/raw mismatch, stale, private-path attempts HOLD).
  - [x] **G2-02-A:** Strict immutable completed five-minute Kline OHLCV validation, no forming/current/latest REST bar, no future timestamps or invalid numeric values. **O01–O03 PASS**.
  - [x] **G2-02-B:** Bounded per-symbol 96-finished-candle history ring for 100, explicit gap/route/source epoch, contiguous historical bootstrap and verified source-as-of. **O04–O10 PASS**, including wrong epoch/duplicate/delay.
  - [x] **G2-02-C:** Up-to-100 complete one-row-per-symbol as-of snapshot, source evidence state, BTC and market breadth, valid/HOLD reasons, no retroactive pattern features, distinct V5.1 event ID. **O11–O12 PASS**, 100/100 fixture denominator.
  - [x] **G2-03-A:** Durable owner-private compact event/manifest snapshots with versioned hash receipts, disk/permission/unknown-file guards, fsync data and parent, replay and no auto-truncate. **S01–S07 PASS**.
  - [x] **G2-03-B:** Separate byte-exact compressed *public REST* source archive with known-at URI, raw SHA, gzip replay, no silent rotation/repair and bounded storage; **A01–A10 PASS**. This does **not** qualify exchange trade/quote/funding source, remote WORM or future G4 economics.
  - [x] **G2-04-A:** Binance `fapi` GET-only exchangeInfo/ticker24h/bookTicker/5m-closed-klines client, default NET LOCK, explicit public opt-in, weight cap, payload/timeouts, no private URLs/redirects/credentials, bad source failures HOLD. **P01–P04/R09 PASS**.
  - [x] **G2-04-B:** Actual one-shot public 100-cohort acceptance on Observation-VPS 15 Oct 2026: 927 exchange symbols, 793 tickers, 795 book quotes; **100 verified candidates, BTC included, 96 continuous finished bars EACH, complete event 100 healthy/0 HOLD**; 103 original public source responses (~792,894 bytes compressed) hash-verified on temporary replay; request weight **246**, no account/order operations. Public-source grade strictly METADATA.
  - [x] **G2-05-A:** All previous G1 67 regression tests + 53 new G2 negative/positive cases = **120/120 PASS** Observation-VPS **Python3.12.3** (3.308s) and Execution-VPS **Python3.12.3** (3.377s), both exit 0 on same exact GitHub **4ba07385bb06ad8cde2460d83953448386f1a751** source.
  - [x] **G2-05-B:** 100×96 candles, 120 events and 10 forced disconnects tested **separately on both VPSs**; full cohort denominator held; p99 51.867ms (Observation) / 60.326ms (Execution), peak RSS 37,964 / 37,868 KiB, CPU 2.2465s / 2.1026s, disk 2,713,184 bytes; PASS under p99<1000ms, RSS<245760KiB, disk<33554432 bytes.
  - [x] **G2-05-C:** Code and failing-test corrections independently reviewed; first 100-test run revealed PosixPath and two fixture problems, later adversarial tests revealed decoded/raw source mismatch and private endpoint gap; both fixed and final 120/120 two-VPS suite PASS. Only **10 new G2 V5.1 source, tests, benchmark and probe files**, no old application import or deployed service. GitHub G2 code SHA **4ba073...**.
  - [x] **G2-06 — Independent final gate proof and roadmap decision:** Code, 120 regression/negative tests, both measured 100-coin VPS workloads and actual public read-only 100-coin/103-source-receipt check **ALL PASS**, [G2 final detailed report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md), commit **005d82324d7cb009e4939075b49e00e41e25f271**. **Parent G2 [x]**; G3/G4 deep original 20-source/trading later [ ]; full scientific custody and release permissions NOT implied.
- [x] **G3 — Full causal/read-only 24-detector Exploration engineering gate COMPLETE (15 Oct 2026)**, 157/157 tests separately on both Python3.12.3 VPSs, both 100×2×24 measured workload PASS, actual public 100-coin→200-direction capacity-mask check, final proof **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**. **Not** original trade/quote/cost custody or trading release.
  - [x] **G3-01-A — Historical source provenance R01:** Pinned original V4 `candidate_setups.py`, historical commit `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf`, blob `80eafb9da096633154a7d7095137414998eb37ee`; independent AST register SHA `17cf229ef8beb30e1bc54bc22a0025e2ffed65e3088b915cec17e51e032dad4b`, exact 24 identifiers, 5 context +19 technical.
  - [x] **G3-01-B — Historical source provenance R02:** V4 `context_learning.describe` blob `34b6b83bd115e44361eba2a7937f7872774c3c3d`; copied only five pure setup family thresholds, discarded legacy ridge training/calibration.
  - [x] **G3-01-C — Source audit R03/R10, refuse wholesale port:** Reviewed V5 `pattern_adapter.py` blob `0048eabcdf9008fe0499b3c1b233a6469358f4d2` and `g3_market_context.py` blob `d426ef75e143d9745006de16f16cdf219a599cab`; old 50-cap/obsolete V3/V4 imports excluded; fresh V5.1 adapter/market context independently written, version separated.
  - [x] **G3-01-D — Each exact detector independently audited:** 24 individual [G3-DET-01–24 ticks in legacy register](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_LEGACY_COMPONENT_REUSE_REGISTER_V1_0.md). H01 original catalog SHA PASS; H02 19 technical positives BOTH sides PASS; H03 all five context positives; H04–H07 flat, BTC, invalid gap, unconfirmed swing negatives PASS.
  - [x] **G3-02-A — G2 closed known-at history source contract:** Added read-only G2 `ObservationBook.history_asof` returning only 96 contiguous fully closed same-event bar records with validated source epoch/route and clock; future/stale/gapped events never contribute indicators.
  - [x] **G3-02-B — BTC/market/coin regimes and structure maturity:** V5.1 `exploration.py` classifies BTC and market context, per-coin up/down/range and causal range-break/failed-break/move proxies; forming/confirmed/failed/unconfirmed/unavailable maturity; missing BTC stays UNAVAILABLE.
  - [x] **G3-02-C — Independent source/cost/source-grade disclosures:** Preserve original 50/25/25 and BTC membership tags, known-at coin source hash/route/epoch, explicit `CLOSED_PUBLIC_CANDLE_METADATA_NOT_ORIGINAL` grade, liquidity metadata-only, fee/slippage/funding/quote witness UNVERIFIED. No match-to-profit promotion.
  - [x] **G3-02-D — Universe/source freshness:** Stale (>90min) universe/source/gaps and insufficient cross-section become explicit source or context HOLD; no future or retroactive features, no missing BTC substituted with zero.
  - [x] **G3-03-A — Full 100×2=200 observation denominator:** Freeze one LONG and one SHORT for each cohort symbol, every record has the 24 named versioned detector states and independent ID. E01–E04 and E13 PASS.
  - [x] **G3-03-B — Honest five-state availability mask:** MATCH, NO_MATCH, UNAVAILABLE, NOT_EVALUATED_CAPACITY and NOT_EVALUATED_SOURCE; separate row status and NO_TRADE, no invented detector failures or hidden dropped symbols. E02–E09 PASS.
  - [x] **G3-03-C — Capacity-vacancy gated scoring:** Default `capacity_slots=0` suppresses heavy detector evaluation and keeps all 200 capacity masks. A caller-supplied, strictly typed positive research vacancy may permit read-only evaluation; G3 itself never allocates G5 slots or opens positions.
  - [x] **G3-03-D — Fair recorded inclusion design:** Hash-rotated deterministic at-most-200 detector-evaluation cap; record prospective K/N policy for ALL eligible coin-side pairs including those not selected, zero only for source-ineligible/no-vacancy, with full source/capacity skipped counts. E05/E06/E17 PASS.
  - [x] **G3-03-E — No forced order or evidence of profit:** Immutable authority NONE / disposition NO_TRADE even on positive synthetic detector fixture, no live/paper/exchange order, no net-return fields. E10/E15 PASS.
  - [x] **G3-04-A — Bounded compressed G3 event receipts:** New `exploration_store.py`, 200×24 nested state / category / source / inclusion data fsynced in private gzip SHA receipts, file/directory sync, same-event conflict rejection, no auto-discard, 64 MiB default cap, strong negative replay.
  - [x] **G3-04-B — Tamper, quota, and interrupted fsync tests:** P01–P12 PASS for replay, identical retries, changed record hashes, false LIVE authority, forged after-cost/original-source grade, altered capacity mask even after rehash, permission/orphan records, finite disk and explicit retry after failed sync.
  - [x] **G3-05-A — Complete 157-test suite on TWO actual VPS Python versions:** 67 G1 regression +53 G2 regression +37 G3 historical/adapter/store = **157/157 PASS on Observation-VPS 3.12.3 in 11.928s**, and **157/157 PASS on Execution-VPS 3.12.3 in 12.310s**, no failures/errors. Exact code SHA `5d9707fe8521bbe17e96036aef0a5ec44a784a96`, both exit 0.
  - [x] **G3-05-B — Measured 100×2×24 two-VPS benchmark:** Each host processed **2,400 direction records** over 12 events (1,240 evaluated; 1,020 capacity skipped; 140 source skipped) under simulated source disconnects. G3 p99 **571.799ms Observation /549.342ms Execution**, RSS **42,884/43,164 KiB**, disk **198,781 bytes** each, 12 integrity-verified receipts; PASS under 1500ms p99, 256000KiB RSS, 33554432B disk.
  - [x] **G3-05-C — Identical code and negative-test audit:** All ten G3 new/modified Python files independently read back with pinned Git blobs, original 24 V4 IDs/hash verified. Initial tuple canonical-ID/test backdating, quota fixture and later source/cost/missingness hardening were corrected and FINAL **157 tests PASS** on both target hosts.
  - [x] **G3-06-A — Actual public source G3 acceptance without fake vacancy:** One-shot no-account no-order HTTPS USD-M Observation-VPS source check: **100 qualified symbols/BTC included/100 ready G2, 0 HOLD; 103 compressed original public REST receipts revalidated**. G3 **200 rows×24 states**, 0 source missing, all 200 capacity-skipped because no actual qualified G5 vacancies; no live pattern evaluation or trades; 17,825-byte G3 record replayed in temporary test directory; public weight 246.
  - [x] **G3-06-B — Final source/no-service limitation audit:** No permanent VPS NBOT application/services installed or started, no private Binance account/orders. Tests and read-only source probe used temporary checked-out trees and automatically removed all temporary test data. This is public REST metadata, NOT original G4 deep trade/quote/funding source.
  - [x] **G3-06-C — G3 parent independent acceptance SIGNED OFF:** All G3-01…G3-06 proof in [G3 final acceptance report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), commit **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**. Next gate **G4 [ ]**, paper/testnet/real release LOCKED.
- [ ] **G4 — Select 20 and establish independently authentic deep market sources — PARENT HOLD, NOT ACCEPTED.** Extensive code and [real source test evidence](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md) at **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, but 20/20 clean real trade+quote+mark source, long-run peak/disk, independent custody and off-host restore are still unproven.
  - [x] **G4-01-A — Frozen input/causal eligibility:** `deep_selection.py` takes only same-asof G2 qualified 100 and G3 full up-to-200 masks, rejects wrong source/clock/cohort hash; no future returns or detector-match-count ranking.
  - [x] **G4-01-B — Exactly up-to-20 including BTC:** Immutable selected and excluded lists, cohort ID SHA, source grade `WARMUP_HOLD_NOT_ORIGINAL_VERIFIED`, no virtual/paper/REAL actions.
  - [x] **G4-01-C — Cohort/source diversification/control coverage:** Original group tags, fixed gainer/loser/turnover/controls quotas, SHA rotating sample with prospective K/N inclusion probability for every eligible included/excluded coin. Validated against source-qualified denominator; real example frozen 20 in public one-shot.
  - [x] **G4-01-D — Independent eight deep-cohort tests:** S01–S08 PASS: BTC, 20 cap, fair frozen inclusion/exclusion, cohort mismatch, default no-vacancy no trade, smaller eligible cohort and input validation.
  - [x] **G4-02-A — Three currently documented public USD-M WSS routes:** `deep_source.stream_urls` public `bookTicker`; market `aggTrade` and `markPrice@1s`; 20 max per route. Confirmed [Binance USD-M source migration/routing docs](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect) last modified 14 Oct 2026. No `/private` source, account, order or key access.
  - [x] **G4-02-B — Causal source frame parser and source grade:** SHA of exact raw public WSS bytes, proper subscribed symbol/stream/kind, finite strict positive bid/ask, trade IDs, mark/indicative funding, receive and source-clock/epoch checks. `PUBLIC_TLS_WSS_LOCAL_RAW_NOT_EXCHANGE_SIGNED`, outcome count 0, no order authority.
  - [x] **G4-02-C — Per-symbol rather than route-level trade sequence:** Fixed and tested 20 interleaved coins with independent aggregate/underlying trade cursors and HOLD on gap/reorder/dup. F01–F05/A10–A11 PASS; reconnect/new epoch never silently repairs missing original trade path.
  - [x] **G4-03-A — Raw WSS compressed SHA-chain segments:** `deep_segments.py`, separate pure frame and writer contracts, fsynced owner-private gzip body + metadata, raw bytes preserved, bounded 1 MiB per segment and finite default 64 MiB quota, no hot-path per-frame SQLite and no automatic discard.
  - [x] **G4-03-B — Independent replay/crash/file errors:** Strict compressed hash, source bytes and per-symbol original trade chronology replayed, schema/permissions/orphans/partial file/finite quota tests, restart new epoch quarantined; A01–A11 PASS.
  - [x] **G4-04-A — Funding source separation:** `settled_funding.py` verifies raw public USD-M `/fapi/v1/fundingRate` 2-row results by source time/symbol/rate and raw SHA; WSS markPrice `r` is estimated future funding, public REST history is NOT position-specific charged funding. T01–T05 PASS.
  - [x] **G4-04-B — Real settled BTC funding public GET:** Observation-VPS 15 Oct 2026 08:01:29 UTC, HTTP200 public Binance fundingRate, 2 BTC past settlements (00:00 and 08:00 UTC), SHA `d3216c03de531ff7509958631b41d5be609a4c2606a965b12a052e0acf53c59e`, zero qualified virtual position cost.
  - [x] **G4-05-A — Whole G0–G4 186-case regression BOTH VPSs:** Observation **186/186 PASS in 14.882s**, Execution **186/186 PASS in 15.496s**, Python3.12.3 both, exact source revision **`07186992fdfc8b2fc1b66e39b6d78513ee23891e`**, exits 0 and 157 earlier G1–G3 cases retained.
  - [x] **G4-05-B — 20-deep *synthetic* CPU/RSS/disk throughput:** Separate actual host tests with 60 rounds ×20 markets×3 routes = **3,600 original-shaped fixtures**, 1,200 trade/1,200 book/1,200 mark, 60 strict gzip source segments and complete original-byte replay; G4 forced restart yields 20 source HOLD, p99 **53.325ms / 60.251ms**, peak RSS **36,408/36,396KiB**, 243,436 bytes compressed per host; PASS synthetic resource caps.
  - [x] **G4-05-C — Actual read-only Binance public 100→20 WSS sample recorded:** One-shot explicit public GET/WSS, 100 G2 qualified/BTC, freeze 20, 103 original public REST receipts, **QUOTE 2,673 valid (20/20), MARK 78 (20/20), TRADE 326 (19/20) plus 47 source-HOLD rejects**, 3,077 raw public WSS frames SHA-replayed in 2 segments (~211,071 bytes), then temporary capture removed. No authoritatively clean 20/20 original source proof from this test.
  - [x] **G4-05-D — No-order/no-install scope verified:** No signed/private/authenticated trading endpoint, account data, testnet/paper/live orders, permanent collector service or old V4/V5 installation in this G4 work. Only test-only temporary public source probes.
  - [ ] **G4-06-A — CLEAN 20/20 source epoch/cursor acceptance:** Actual trade sample failed: at least one selected symbol had no original aggregate-trade frame and **47 missing/reordered trade sequence reports**; qualify independently complete all 20 with BTC, original trade and bid/ask mark source witnesses. No hindsight REST kline or interpolated tick substitution.
  - [ ] **G4-06-B — Representative real high-rate 20-source endurance and storage:** Must prove actual (not simulated) message-rate tails, backpressure, multi-hour/24h route reconnect, WAL/disk burst and quota rollover, bandwidth and CPU/RAM/I/O limits before always-on activation.
  - [ ] **G4-06-C — Independent original/source-grade and funding/cost truth:** Local public TLS frame provenance alone not exchange-signed independent custody, no complete quote path/settled funding per intent; add capture network-session witness, distinct sources and independent audit/grade governance. No G6 executable fill/economic label authority.
  - [ ] **G4-06-D — Actual second-host archival and recovery:** Simulated restart and file SHA verification passed, but independent off-host source retention, restore comparison and actual crash/gap recovery of a full source epoch remain unverified. Owner's old-data backup waiver does NOT apply to new G4 evidence.
  - [ ] **G4-06-E — Parent G4 completion decision:** BLOCKED on 06-A..D; do NOT check parent, advance to G5 or start services/trading. [Full proof and exact handoff](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**.
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
| 2026-10-15 | G1-03-A/B Source envelope and restart HOLD | [x] | **bb0df4b727e5817d47fe693206baba91e2706456**; new `source_contract.py`, `bootstrap.py` | G01–G09 pass; strict known-at source never authenticated by metadata; journal corruption forces OFFLINE/HOLD/NONE | Source and reboot cannot accidentally authorize a trade |
| 2026-10-15 | G1-03-C/D First-file durability and failure injection | [x] | **bb0df4b727e5817d47fe693206baba91e2706456**; amended `journal.py` | G10–G15 pass: file/parent fsync, sync retry, torn write, tamper/schema, quota HOLD/no silent rotation | First-file audit durability strengthened and negative scenarios demonstrated |
| 2026-10-15 | G1-03-E/F/G Integration, local suite and exact SHA | [x] | **bb0df4b727e5817d47fe693206baba91e2706456**; G1-03 commit `c1408ff00ff05ec6349a85202ee877708df87cd0` | G16–G22 pass; full 67/67 on Python3.13.5; all four GitHub changed blobs match tested bytes | The modules integrate without unlocking any order and remain audited |
| 2026-10-15 | G1-04-A/B Independent actual VPS interpreter tests | [x] | **bb0df4b727e5817d47fe693206baba91e2706456**; exact c1408ff revision ephemeral git checkout on each VPS | **Observation 67/67 PASS** Python3.12.3, **Execution 67/67 PASS** Python3.12.3; both exit 0 and temp checkout auto removed | Both intended Linux runtimes can run the safe foundation correctly |
| 2026-10-15 | G1-04-C/D Final no-deploy and safety review | [x] | **bb0df4b727e5817d47fe693206baba91e2706456**; dated [G1 final acceptance](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md) | No new production service, no account or order; outage/source custody limits explicitly retained | Finished offline engineering preparation; no trade permission |
| 2026-10-15 | **G1 PARENT FINAL PASS** | **[x]** | **bb0df4b727e5817d47fe693206baba91e2706456**; G1-01, G1-02, G1-03 and G1-04 accepted | **67 of 67 tests PASS** locally and again on each of two VPS hosts; versioned contracts and guardian locks reviewed | Whole nontrading foundation is complete; next gate G2 Observation intake |
| 2026-10-15 | G2-01 eligibility/100-symbol selection/source-as-of proof | [x] | **005d82324d7cb009e4939075b49e00e41e25f271**, source blobs `universe.py`, `public_market.py` | Binance 50/25/25 groups, qualified BTC, 100 dedup, triple raw SHA and time-skew; U01–U10/R01–R10 PASS | Exactly which markets qualified is auditable without misleading duplicates or stale information |
| 2026-10-15 | G2-02 finalized candles/history/breadth/HOLD | [x] | **005d82324d7cb009e4939075b49e00e41e25f271**, `observation.py` | 96 finished candles per 100, route/epoch continuity, 100-row denominator, BTC market health and HOLD reasons; O01–O12 PASS | A five-minute event never silently uses a still-forming candle |
| 2026-10-15 | G2-03 compact snapshots and byte-exact public source evidence | [x] | **005d82324d7cb009e4939075b49e00e41e25f271**, `observation_store.py` and `source_archive.py` | S01–S07/A01–A10 PASS, fsync, source byte SHA/replay, quotas, tamper, no silent deletion | Can record small read-only evidence, but NOT independent high-frequency original trade/quote custody |
| 2026-10-15 | G2-04 opt-in only-public REST source smoke | [x] | **005d82324d7cb009e4939075b49e00e41e25f271**; exact live source SHA `4ba073...` | 100/100 96-bar closed histories; BTC; 100 healthy/0 HOLD; 103 replayed source receipts, weight 246; no API keys or orders | Read-only public USD-M 100-coin intake evidenced at a genuine as-of event |
| 2026-10-15 | G2-05 120 tests on two VPSs | [x] | **005d82324d7cb009e4939075b49e00e41e25f271**, committed source `4ba073...` | Observation 120/120 PASS and Execution 120/120 PASS on 3.12.3; 53 G2 failure cases + 67 G1 regression | Old offline safety gates remain protected by new code |
| 2026-10-15 | G2-05 100-coin resource stress on BOTH VPSs | [x] | **005d82324d7cb009e4939075b49e00e41e25f271**, `benchmarks/g2_observation_benchmark.py` | p99 51.867/60.326ms; RSS 37.1/37.0 MiB; disk 2.713MB, explicit ten source gaps HOLD; all performance budgets PASS | Lightweight source tier fits measured small VPS envelope in synthetic cases |
| 2026-10-15 | **G2-06 parent engineering COMPLETE** | **[x]** | [Full G2 proof](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md), commit **005d82324d7cb009e4939075b49e00e41e25f271** | All G2 subtasks checked from actual read-only test/source/host results; G3+ remains separate | Full G2 engineering passed without enabling paper/REAL, account services or persistent collector |
| 2026-10-15 | G3-01 24 original source catalog, 5 context/19 technical verification | **[x]** | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, V4 original commit `b1a3c4a...`, catalog `17cf229ef8be...` | H01–H07 PASS; individually ticked all 24 V1 IDs in legacy reuse register, 19 long/short golden examples | Hypotheses preserved without importing or trusting old V4 running code |
| 2026-10-15 | G3-02 causal BTC/market/coin structures and original tags | **[x]** | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, `observation.py` / `exploration.py` SHA-pinned | strict final-only 96-candle as-of, 90min universe age, 80% source coverage, BTC/coin regime, maturity, explicit cost/source UNKNOWN | Market descriptions are causal metadata, not future knowledge or profit claims |
| 2026-10-15 | G3-03 full 100×2 denominator and no-vacancy masks | **[x]** | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, 18 E-series cases | Exact 200 coin-side rows, each with 24 stable detector states; separate NO_MATCH/UNAVAILABLE/SOURCE/CAPACITY; fair K/N design inclusion, default NO_TRADE/NONE | No candidate disappears when missing source or full research capacity |
| 2026-10-15 | G3-04 durable 200-row replay and tamper negatives | **[x]** | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, 12 P-series cases, `exploration_store.py` | Compressed/fsynced bounded private receipts, refuses fake LIVE/order, after-cost/source-grade escalation, wrong mask, corrupt files and quota | Honest records survive restart test without promoting a pattern match to an order |
| 2026-10-15 | G3-05 157 full tests and measured 100×2×24 stress on BOTH VPSs | **[x]** | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, exact `5d9707fe...` code SHA | Observation and Execution EACH 157/157 PASS Python3.12.3, 2,400 records; p99 571.799/549.342ms, 42,884/43,164KiB RSS, 198,781B disk, all limits PASS | Full pattern/availability model fits tested small VPS envelope offline |
| 2026-10-15 | G3-06 real public as-of 100→200 no-order mask test | **[x]** | **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, one-shot `scripts/g3_readonly_probe.py --public-network` | 100 source-ready/BTC, 200 rows, 24 states each, 200 capacity-skips, 0 orders, 103 source receipts hash-replayed, 17,825B G3 record replay | Do not activate heavy exploration absent independently verified G5 vacancy |
| 2026-10-15 | **G3 parent FULL read-only Exploration PASS** | **[x]** | [G3 complete evidence](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1** | All subphases passed, old code not imported, no paper/live/model gain or current service | Ready for **G4 source and shortlist engineering**, not actual trading |
| 2026-10-15 | G4-01 frozen 100→20 BTC cohort/control/inclusion | [x] | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, `deep_selection.py`, S01–S08 | Fair as-of selection, all 100 accounted, BTC, source warm-up HOLD; no fake research slot | Every coin selection/exclusion auditable without claiming a strategy |
| 2026-10-15 | G4-02 pure 20-source frame/provenance | [x] | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, `deep_source.py`, F01–F05/A10–A11 | Official public WSS routes, symbol/time/epoch, per-coin trade cursor, lost ID HOLD | No original tick path is invented from candles |
| 2026-10-15 | G4-03 finite compressed source segments/replay | [x] | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, `deep_segments.py`, A01–A11 | 1 MiB bounded segments, SHA chain, fsync, corruption/restart/quota HOLD | Evidence tamper/restart fails rather than silently suggesting source continuity |
| 2026-10-15 | G4-04 public settled funding distinct from mark estimate | [x] | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, five T tests, actual BTC 2 settled records HTTP200 | Does not qualify simulated funding debit or after-cost returns | No made-up position-specific fees |
| 2026-10-15 | G4-05 186 tests and synthetic deep20 benchmark on BOTH VPSs | [x] | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, source revision `07186992...` | **186/186 PASS** each Python3.12.3, 3,600 frames/60 segments, p99 53.325/60.251ms and <37MiB RSS | Offline source software and sample capacity validated |
| 2026-10-15 | G4-05 genuine public 100→20 source capture | [x] | **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**, actual WSS 3,077 frames replayed | Real QUOTE/MARK 20 each; TRADE 19/20 and 47 gaps — **HOLD** | Truthful source quality, not hidden downtime |
| *Next* | G4-06-A **clean 20/20 original trade/quote/mark source** | [ ] | **HOLD**, [evidence](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md) | 47 ID gaps + missing trade symbol; then 06-B real duration, 06-C audit, 06-D off-host restore, 06-E parent | Do not start service or G5 unless full G4 gate passes |
| 2026-10-15 | G0-04 owner review of first G1-01 code scope | [x] SCOPE ONLY | **7c624de187e274fe40172e64d03b8697f6e1f7aa**; latest user instruction | Approved exact no-order pure package and test contract; **0 application files** | First code path now decided; actual implementation still requires separate G1 evidence |

**CURRENT VERIFIED STATUS 15 October 2026: G0, G1, G2 AND G3 each separately passed their authoritative engineering gates.** G3 has **157/157 tests PASS on both Python3.12.3 VPSs**, measured 100×2×24 complete 2,400-direction workload, exact 24 legacy detector IDs/provenance and read-only live 100-market→200-direction capacity-mask source test. [Full report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**; exact accepted code revision `5d9707fe8521bbe17e96036aef0a5ec44a784a96`. **G4–G12 remain OPEN; no original trade/quote/funding economic evidence, deployed always-on services, paper or live-money release.** Old data waiver does not apply to NEW source records.

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


## G1 final later-event gate closure — 15 Oct 2026

**The earlier G1-01/G1-02 appendices above describe their historical state at the time; their G1-parent HOLD statements were correct then and are superseded by this later G1-03/G1-04 work.** G1-03/G1-04 have now been implemented and verified through the final [G1 evidence report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G1_FINAL_ACCEPTANCE_20261015.md), commit **bb0df4b727e5817d47fe693206baba91e2706456**. No prior failures were silently relabeled: all 67 tests actually passed in local Python3.13.5 and independently on both target Python3.12.3 hosts from the same immutable G1 code commit `c1408ff...`.

- [x] **G1-03-A/B**: new versioned source identity known-at HOLD contract and default OFFLINE/HOLD reboot policy.
- [x] **G1-03-C/D**: fsync file + parent, retry durability, partial-write failure injection, reject tampering and unsupported migrations/rotation.
- [x] **G1-03-E/F/G**: end-to-end guardian/source/journal/recovery composition plus 67/67 regression and exact 4-file Git hash proof.
- [x] **G1-04-A**: Observation-VPS actual Python3.12.3, 67/67 PASS on exact G1 source, no permanent checkout.
- [x] **G1-04-B**: Execution-VPS actual Python3.12.3, 67/67 PASS on exact G1 source, no permanent checkout.
- [x] **G1-04-C/D**: no-order/no-network/no-deploy review, future-source and physical-power-outage limits classified to later product gates.
- [x] **G1 PARENT**: safe **nontrading, offline** V5.1 application foundation accepts versioned source interfaces, deterministic clock, private bounded journal, restart HOLD, safety guardian and explicitly disabled modes.
- [ ] **G2+**: first real public market ingestion and full future original-source custody, statistical learning, paper and real trading are still independently gated.

**G1 final decision: PASS within its authoritative offline scope.** A genuine host power loss, off-host source evidence archive/restore or live order was neither attempted nor inferred by G1; those distinct future product requirements are preserved. No authorization to start trading or enable Binance connectivity.


## G2 completed handoff and later status — 15 October 2026

After G1 closure, the owner directed completion of every G2 subphase and exhaustive testing, while retaining persistent roadmap evidence for the next chat. The previous G1 appendix correctly said G2 was future work *at that earlier time*; this later completion supersedes those historical NEXT markers. [Full G2 final evidence report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G2_FINAL_ACCEPTANCE_20261015.md), commit **005d82324d7cb009e4939075b49e00e41e25f271**, contains exact code blobs, closed-candle/100-coin source truth, 120-test two-VPS executions, full p95/p99/CPU/RSS/disk host results, actual public one-time market source receipt identities and all caveats.

- [x] **G2-01-A/B/C:** Eligible USD-M PERPETUAL + USDT quote/margin, qualified 50/25/25 deduplicated with BTC, strict point-in-time three-source hashes/as-of acceptance and complete rejection register.
- [x] **G2-02-A/B/C:** Bounded 96 × up-to-100 closed-only bars, historical finality/bootstrap, gaps/reconnect/epoch HOLD, one row per observed market and BTC/breadth reasons.
- [x] **G2-03-A/B:** Compact owner-private snapshot/event store and separate gzip byte-exact public source receipt store, both strict on corruption and disk limits; no automatic pruning.
- [x] **G2-04-A/B:** Explicit read-only HTTP public source adapter, no credentials/orders, Binance one-shot 100-symbol 96-closed-bar validation, **103 replayed public receipts** and **100 current METADATA_CLOSED/0 HOLD**.
- [x] **G2-05-A/B/C:** **120/120** real Python3.12.3 tests on BOTH VPSs, independent 100-symbol/120-event synthetic p95/p99/RSS/CPU/disk benchmarks, full G1 regression and adversarial source integrity checks.
- [x] **G2-06/PARENT:** Read-only G2 engineering gate PASSED with no service deployment or trading authorization.
- [ ] **G3-01 NEXT:** Audit original 24 V4 detectors and implement causal Exploration for both directions (200 possible symbol-side records), with no source-grade or cost label upgrade without separate independent evidence.

**No claim of independent original high-frequency source custody or continuous production monitoring at G2**: the live public sample archive was replayed then temporary files removed; code can persist bounded source receipts when a future separately approved operational runner is deployed. G4 deep-20 original-trade/quote/funding retention and G6 economics still require independent source authority, recoverability and off-host custody. G3–G12 and all paper/real money permissions remain locked.


### Permanent continuation pointer — 15 October 2026

- [x] **Current source-of-truth and next-chat handoff is maintained:** [Handoff](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_CURRENT_STATUS_NEXT_CHAT_HANDOFF_20261015.md) now includes **G0/G1/G2/G3 [x]**, complete G3 proof **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**, 157 passing tests on BOTH VPSs, exact G3 source revision `5d9707fe...`, actual public 100×2 capacity-mask test and next **G4 [ ]**. Historical G2 120-test evidence remains separately pinned.
- [x] **G1 final acceptance report clarified:** It now says **ENTIRE G1 PASSED** prominently and distinguishes historical G2-next wording from current G3-next status. No original G1 results were rewritten or reclassified as production/trading authorization.


### G3 detailed individual detector ticks and final later-event closure (15 Oct 2026)

**Current source of truth:** [G3 Final Acceptance Report](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G3_FINAL_ACCEPTANCE_20261015.md), commit **fae1e2edc5f9403ccaf4b23e596176e89a2cfaf1**. Test/benchmark/public-probe exact GitHub code HEAD `5d9707fe8521bbe17e96036aef0a5ec44a784a96`, Python3.12.3 **157/157 PASS on EACH VPS**, 100×2×24 p99/RSS/disk PASS, actual public no-vacancy 100-market/200-direction/103-source-receipt audit PASS. Prior G2 sections describe earlier stage status and are not current G3 HOLDs.

- [x] **G3-DET-01: `TREND_CONTINUATION_V1`** — source catalog digest/pinned old V1 identity verified, historical five-context golden H03 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-02: `TREND_PULLBACK_V1`** — source catalog digest/pinned old V1 identity verified, historical five-context golden H03 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-03: `STRETCHED_REVERSAL_V1`** — source catalog digest/pinned old V1 identity verified, historical five-context golden H03 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-04: `VOLATILITY_EXPANSION_V1`** — source catalog digest/pinned old V1 identity verified, historical five-context golden H03 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-05: `RELATIVE_STRENGTH_V1`** — source catalog digest/pinned old V1 identity verified, historical five-context golden H03 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-06: `DONCHIAN_BREAKOUT_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-07: `BREAKOUT_RETEST_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-08: `FAILED_BREAKOUT_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-09: `RANGE_EDGE_REJECTION_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-10: `BOLLINGER_REENTRY_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-11: `RSI_RECLAIM_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-12: `EMA_CROSS_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-13: `EMA_PULLBACK_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-14: `MACD_CROSS_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-15: `SQUEEZE_BREAKOUT_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-16: `VOLUME_BREAKOUT_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-17: `VWAP_RECLAIM_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-18: `INSIDE_BAR_BREAKOUT_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-19: `OUTSIDE_BAR_REVERSAL_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-20: `ENGULFING_REVERSAL_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-21: `PIN_BAR_REJECTION_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-22: `MULTITIMEFRAME_TREND_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-23: `CONFIRMED_SWING_CONTINUATION_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.
- [x] **G3-DET-24: `BTC_RELATIVE_MOMENTUM_V1`** — source catalog digest/pinned old V1 identity verified, historic LONG and mirrored SHORT technical golden H02 PASS, pure nontrading hypothesis only.

- [x] **G3 source/capacity provenance group:** Each eligible observed coin direction has 24 versioned states; explicit missing-BTC, insufficient cross section, source and capacity flags, original selection tags, present source grade, unavailable economics, K/N design propensity and immutable NO_TRADE/NONE authority.
- [x] **G3 final offline gate decision:** Full `G3-01..06` **PASS** and parent G3 **[x]**. No G4 original deep-20 source custody, virtual economics, Champion/Challenger paper or real-money release is implied.
- [ ] **G4 NEXT:** audited fair 100→20 source-ready research set with BTC, real bid/ask/trade/funding original witnesses and compressed bounded persisted source/restore proof. See G4 parent still open above.


## Later G4 evidence checkpoint and strict hold — 15 October 2026

[Complete G4 tested-code/source progress and blockers](https://github.com/samqju/Nbot/blob/nbot-v5.1/docs/NBOT_V5_1_G4_ENGINEERING_PROGRESS_AND_HOLD_20261015.md), commit **db4d3e77cbe854e21cba1d7d04d4b8d0b564f87b**. Source tested: **`07186992fdfc8b2fc1b66e39b6d78513ee23891e`**. Both target VPSs independently passed **186/186** Python 3.12.3 unit/integration/failure tests and 20 market ×3 raw stream ×60 synthetic cycle p99/RSS/CPU/disk benchmark. A real one-shot public Binance USD-M capture obtained **3,077 raw public WSS frames** with 20/20 quote+mark, **19/20 trade**, **47 trade-ID continuity warnings**. Public historic BTC settled-funding fetch also confirmed raw SHA and two historical settlements, but these are NOT proof of a simulated position-specific charge. No runtime/market service or order access enabled.

- [x] G4-01 fair 100→20 frozen BTS-including subset, auditable selection/exclusion/propensities.
- [x] G4-02 public-only routed USD-M original-trade/quote/mark format plus per-coin source-epoch ID HOLD, code and tests.
- [x] G4-03 byte-exact compressed finite source segment/replay, hash/fync, corruption/partial/ quota/ restart HOLD, code and tests.
- [x] G4-04 public historic settled funding grade separate from indicative mark and from account/virtual costs, tests + one real BTC REST witness.
- [x] G4-05 full 186-case two-host regression, 3,600-message synthetic deep-20 workload and actual 3,077-message one-shot public audit with limitations preserved.
- [ ] **G4-06-A FIRST OPEN:** real 20/20 fully warm original-source trade/quote/mark epochs, no unresolved trade-ID holes; reselect a fresh source-qualified cohort at a future as-of event if necessary, never rewrite prior membership in hindsight.
- [ ] G4-06-B real sustained peak traffic, reconnect and finite disk resource proof.
- [ ] G4-06-C independent source custody and funding-grade limitation release review.
- [ ] G4-06-D actually archived/restored off-host new source with independent hash verification, no legacy waiver.
- [ ] **G4 parent remains UNCHECKED. G5–G12 all OPEN; ALL services and trades remain LOCKED.**
