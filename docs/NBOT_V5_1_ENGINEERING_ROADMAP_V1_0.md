# NBOT V5.1 — Detailed Engineering and Recovery Roadmap

**Roadmap version:** 1.0  
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
