# NBOT V5 — Market Intelligence, Strategy Alignment and Learning Roadmap

**Document version:** 2.8.10  
**Date:** 2026-10-14 (IST); original roadmap issued 2026-10-13  
**CURRENT GOVERNANCE NOTE (v2.8.10, 2026-10-14):** The historical early-restart status below describes the original October 13 baseline, NOT today's deployment. Integrated G1/G2/G3 V5 is already RUNNING at pinned SHA `1e7c090d05dc118b290c764d58c2944f56ad4b3b`; G2/G3 initial production PASS, distinct new G1 24h soak pending. See §50 and linked immutable handoff for exact current state, simplified-folder plan, and permitted non-disruptive offline development. Never zero source data to 'clean up'.  
**Owner:** NBOT project owner  
**Repository:** samqju/Nbot  
**Publication:** V5 clean restart on GitHub branch `v5-clean-restart-20261013`; working mirror in laptop Downloads root  
**Forensic reference:** V4 source at commit b1a3c4a8d2a82c994669df7adb0d345e0415ffbf  
**Status:** **Owner-authorized clean V5 restart from pinned V4 source on an isolated GitHub branch. Earlier V5 prototype code is excluded from the new branch. VPS reset/deployment and any service start remain separately gated by owner-run PuTTY inspection and approval. No real-order authority.**  
**Related governance:** Existing V4-R2 F0 roadmap controls evidence preservation and changes to running systems. This V5 document is the architecture-design successor, **not** an automatic amendment to F0 operations.

> **Project north star:** Understand BTC and broader market conditions; classify each coin's latest price action and market structure; detect applicable strategies; learn whether a given strategy and LONG/SHORT direction works under those conditions; evaluate after-cost return and uncertainty; **trade selectively or abstain**. Filling a trading quota is never an objective.

> **Authoritative v1.1 lifecycle amendment:** §§17–26 define the owner's chosen two-VPS responsibilities, ~50-coin research universe, 2,000-matured training checkpoints, paper Champion/Challenger competition on one shared market period, and future three-portfolio live mirror. They supersede any earlier simplified lifecycle or paper-only service diagrams, **not** the F0 safety gates.

---

## 1. Executive decision and change of direction

We will **design NBOT V5 as a new, isolated, market-regime-aware research and paper-decision architecture**. The design responds to verified deficiencies of original V4: a capacity-filling research factory with model-free pattern-count priority, no demonstrated positive-after-cost entry gate, incomplete terminal observations, and unreliable historical ML validation.

**What changes in philosophy:**

1. **Observe broadly; trade narrowly.** Research may label many candidate opportunities, including poor ones; **paper execution** admits only those that clear explicit economic and integrity gates.
2. **Condition the strategy on the market**, rather than treating the 24 named technical patterns as 24 universally profitable standalone trading strategies.
3. **BTC is major context**, not an automatic veto or a universal predictor. Measure direction, shock risk, breadth, coin-BTC correlation, lead/lag and relative strength from information available at the decision time.
4. **Explicit no-trade option** is the default benchmark, even if all 100 symbols display technical patterns.
5. **No data or code inheritance by assumption.** Reuse individually proven components with lineage/tests; preserve the frozen V4 evidence, reject unjustified carry-over of Gen1–4 models or original model approvals.
6. **Realistic net economics and uncertainty**, not gross backtest win rates or matching-rule counts, determine whether any proposed policy is worth controlled paper examination.
7. **Closed-loop learning with safeguards.** More data may revise estimates and propose challengers; it must not promote models or change live/paper decisions without leakage-free evidence and explicit approval.

**Not decided:** Whether any of these pattern/condition combinations produces persistent positive economic expectancy. The roadmap is for testing that question, not presuming a profitable result.

**Relation to F0:** Formal V4 Phase A diagnostic closure on October 13 remains intact. Its independently owned F0 backup, continuity and ledger-integrity work **continues** and cannot be bypassed. The separate F0 owner alone controls service stops, database backups, service resumptions and operational remediation. This roadmap authorizes **documentation only**, not any runtime action.

## 2. Evidence ledger: what V4 taught us

Source levels: **Verified in pinned code**, **observed in dated frozen ledgers/tests**, **inference or new proposal**. Historical snapshots are not merged without a common cutoff.

| ID | Type | Finding and exact scope | V5 implication |
|---|---|---|---|
| E-01 | VERIFIED CODE | V4 research scanner builds LONG and SHORT hypotheses, prioritizes any setup tag, then number of tags, universe rank, deterministic tie. It targets **100 concurrent virtual hypotheses** and can admit zero-tag **MODEL_ONLY** cases; records **V4_BOOTSTRAP_NO_MODEL** without positive estimated net-R requirement. | Separate exhaustive **research labels** from economically qualified **paper entries**. Capacity is a ceiling, never a filling target. |
| E-02 | VERIFIED CODE | The 24 registered setups are technical/pattern detectors in **7 families**; matches overlap and do not constitute 24 independent validated profitable strategies. | Treat tags as candidate **features and hypotheses**, not evidence of profitability. |
| E-03 | OBSERVED | Later supplemental snapshot: **10,253 frozen decisions**, **9,177 usable scored** across **557 scored-event groups**; **976 unresolved** (484 GAP_UNRESOLVED, 492 V4_PROCESS_RESTART_PATH_LOST); **100 lacking a terminal record** at that observation cutoff. No sampled dual-terminal scored+unresolved record. | Missing outcome mechanism, prospective evidence continuity, and denominator accountability are release gates. Never score an unresolved outcome as a loss or fill. |
| E-04 | OBSERVED | Of 9,177 scored admitted decisions, **1,796 (19.6%) had no setup tag**. Their mean **gross −0.26455R**, **net −0.59110R**. | No-setup may still be an **observation**, but should not be assumed to qualify for a trade. |
| E-05 | OBSERVED | Net means by matching tags (0 / 1 / 2 / 3 / 4 / 5+): **−0.59110 / −0.49525 / −0.35175 / −0.41695 / −0.50219 / −0.44148R**. No monotone rise; 2- and 3-match groups had slightly positive gross but negative net. | Stop using number of pattern matches as an implied profit score. |
| E-06 | OBSERVED | Within-event per-extra-tag pooled net slope **+0.03622R**, but mean individual event slope **−0.01464R**; high-tag outcome better in 253 vs worse in 286 comparable events. | Sample/event weighting materially changes conclusions; require event-blocked uncertainty estimates. |
| E-07 | OBSERVED | On **444** fully scored events with >=2 **already admitted** candidates: recorded first rank net **−0.44881R**, uniform random among *admitted* expected **−0.41676R**; delta **−0.03206R**. | No demonstrated advantage in this restricted comparison; **NOT a true all-eligible random benchmark**. |
| E-08 | OBSERVED | At earlier cohort cutoff: **8,878 scored**/540 event groups, mean gross **−0.06043R**, modeled roundtrip cost **+0.39077R**, net **−0.45120R**; even cost <0.15R subgroup negative mean net. | Address entry quality **and** cost/exit/risk jointly. Do not attribute a percentage of losses solely to entry. |
| E-09 | OBSERVED | Same-day official Binance archive/source digest/original baseline replay: BTC Oct11 **27/27**, SOL Oct12 **84/84**, XRP Oct12 **101/101**. After-cost V4 and fixed TP 1.5/2/3R all negative in BTC/SOL/XRP pilot comparisons. XRP +2R did not improve simple mean vs original. | Exit-only replacement has no demonstrated cure. Recovered aggTrades prove price chronology, **not executable historical bid/ask fills**. |
| E-10 | OBSERVED | Selected tag cohorts (23 observed of 24) all had negative **net** mean under the original V4 exit. Some had positive gross mean (e.g. trend continuation +0.12212R, multitimeframe trend +0.04472R, range-edge rejection +0.27368R). | There might be predictive **conditional** information; unadjusted overlapping tag cohorts do not prove any strategy edge. |
| E-11 | VERIFIED CODE | BTC-relative setup requires **candidate_btc_available == 1**, but the V4 vector builder does not supply this flag, and the scanner does not add it. Observed BTC_RELATIVE_MOMENTUM matches: **0** in the 9,177 scored cohort. | Audit feature-contract completeness. Redesign explicit BTC availability, validity and missingness semantics; do not assume this setup would be profitable if enabled. |
| E-12 | VERIFIED/OBSERVED | Existing vector already includes side-aligned BTC returns over 5m, 1h, 4h; V4 did not empirically qualify a BTC-aware regime/strategy interaction. | Distinguish **feature exists** from **market-context model is validated**. |
| E-13 | VERIFIED/OBSERVED | Four V4 LightGBM generations failed fair original-priority comparisons on their analyzed subsets; Gen1–3 had training/validation label overlap, Gen4 avoided that particular overlap yet remained negative. | Freeze/reject old ML artifacts as decision authority; chronological purging, embargo, untouched holdout and no-model are mandatory. |
| E-14 | VERIFIED/OBSERVED | Operational faults: separate feed sockets share ambiguous health; sticky aggTrade gaps/reconnect deficiencies; abnormal dead-thread invalidation gap; scored/unresolved terminal-exclusivity hole reproducible in API sequence (no sampled historical contradiction); restarting research can lose chronology. Physical root cause of certain ping timeouts unproven. | Evidence quality and fail-closed pipelines must be repaired/tested **before V5 labels or shadow scorecards are trusted**. |
| E-15 | OBSERVED | Historical cost assumption **0.12% of notional per roundtrip** (two 5-bps taker fees + two 1-bps slippage), expressed in R by dividing by initial risk distance. Very tight risk distance can create >2R modeled cost. | Check **cost-to-R**, risk geometry, spread, liquidity, funding and worst-case slip before any entry. |
| E-16 | LIMITATION | Dataset contains only V4 **admitted** decisions; point-in-time archived candles, universe snapshots and quotes exist in observation stores, but complete **unselected eligible** population/outcome labels are not established. | V5 must record the *full eligible denominator* before model selection and random-benchmark claims. |

**Snapshot rule:** E-03 to E-07 describe later 9,177 scored decisions; E-08 describes an earlier 8,878-score snapshot. These are not conflicting populations; **never sum them**. All observational market events/trades may overlap by time, coin, direction and horizon.

## 3. Architecture blueprint

~~~text
Binance public market feeds + completed bars + quotes + BTC/market context
         |
         v
[1] Provenance / clock / data-quality gate
         |-- GAP / STALE / MISSING => UNOBSERVABLE, never invent labels
         v
[2] Global context: BTC regime, BTC shock, market breadth, correlation
         +
[3] Coin context: trend, range, volatility, liquidity, structure, relative strength
         |
         v
[4] Versioned candidate-pattern detector library (initial 24 rule hypotheses)
         |
         v
[5] Full candidate universe per completed 5m event:
    (event, coin, LONG/SHORT, market regime, structure, matches, quotes, cost)
         |
         +--> Research observation & eligible counterfactual lab
         |    with strict future-label maturation and missingness accounting
         |
         v
[6] Context-conditioned economic evaluation / uncertainty / ranking
         |
         +--> Explicit ABSTAIN / NO TRADE (0R benchmark)
         |
         v
[7] Portfolio/risk/safety gate (one position budget, cross-asset BTC exposure,
    max loss, spread/impact, data integrity, execution eligibility)
         |
         v
[8] Isolated shadow and paper simulator (NO real orders)
         |
         v
[9] Immutable after-cost outcomes + model monitoring + offline challenger training
         |
         v
[10] Reviewed promotion, retirement or revert — never automatic live money
~~~

**Explicit separation of powers:**

- **Observation service** produces timestamped market evidence; no order authority.
- **Candidate engine** lists possible setups **regardless of whether selected**; cannot order.
- **Research/label engine** scores only maturable, fully evidenced paths; missing = missing, not fake loss or win.
- **Selector/policy** proposes zero or one/few qualified paper actions, as capacity rules permit.
- **Risk guardian** can veto every proposal regardless of model output; cannot create alpha.
- **Paper engine** records economic and operational performance with actual paper position occupancy.
- **Offline trainer** produces immutable challenger artifacts; no self-deploy.
- **Governance/owner** controls promotions, rollback, future service operations and any future real-order authority separately.

## 4. BTC and market-context intelligence

### 4.1 Global BTC features (known at decision time)

- BTC returns and trend structure on closed **5m / 15m / 1h / 4h** bars; strength, acceleration, distance to recent levels.
- BTC realized volatility and sudden-move/shock flags, ATR/range expansion, gap/quote quality.
- BTC participation and changes in its relative movement versus median altcoin return; market breadth (share of eligible coins rising/falling).
- Rolling, **past-only** coin/BTC co-movement, signed beta, residual/relative strength and lag sensitivity; confidence interval/sample count, bounded missingness.
- Optional BTC dominance, market index or funding/liquidation context **only after** provenance, timing and availability are established. Never silently add unavailable third-party series.
- Treat BTCUSDT itself separately as a coin candidate; avoid self-relative comparisons and self-leakage.

### 4.2 Individual coin context

- Completed 5m/15m/1h/4h structure: higher highs/lows, lower highs/lows, confirmed swing points and support/resistance.
- Trend, range, breakout, retest, failed breakout, momentum exhaustion, low-volatility compression, volatility shock, ambiguous/transition regimes.
- Spread, executable quote freshness, book liquidity where available, turnover, volatility, funding, risk distance and estimated slippage.
- Coin-relative performance versus BTC and peers, correlation change, divergence, BTC-led versus idiosyncratic moves.
- Regime state as **multi-label or probabilistic**, not forced into exactly one bucket. Store uncertainty, time since regime transition and coverage flags.
- Look-ahead protection: pivots require confirmation only after their necessary future candles have **already closed**; do not mark a pivot at an earlier live decision time using future candles.

### 4.3 Key research questions, not fixed heuristics

- Does bullish pullback continuation have different after-cost expectancy when BTC is trending upward, flat, or undergoing a downward volatility shock?
- Which coins tend to amplify BTC moves versus lag or move independently? Is this stable out of sample?
- Can BTC market stress invalidate an otherwise promising long setup, or create justified short opportunities? Do not hardcode bias without evidence.
- Does a pattern's historical advantage survive after a change in BTC regime, coin spread, funding, execution slippage or liquidity?
- When samples are sparse or BTC feeds are stale, should the system **abstain** rather than guess? **Yes, by default**.

## 5. The 24 existing patterns: classification, not trade approval

The original candidate registry supplies these initial **hypothesis detectors**. Count below totals exactly 24; rule-specific parameterization/version and test data are mandatory before adoption into V5.

| Family | Count | Versioned V4 identifiers | Intended detection |
|---|---:|---|---|
| Momentum | 4 | TREND_CONTINUATION_V1; EMA_CROSS_V1; MACD_CROSS_V1; MULTITIMEFRAME_TREND_V1 | Alignment and directional momentum |
| Pullback | 2 | TREND_PULLBACK_V1; EMA_PULLBACK_V1 | Countertrend retracement inside a trend |
| Breakout | 6 | VOLATILITY_EXPANSION_V1; DONCHIAN_BREAKOUT_V1; BREAKOUT_RETEST_V1; SQUEEZE_BREAKOUT_V1; VOLUME_BREAKOUT_V1; INSIDE_BAR_BREAKOUT_V1 | Boundary crossing, compression release or retest |
| Reversal | 5 | STRETCHED_REVERSAL_V1; FAILED_BREAKOUT_V1; OUTSIDE_BAR_REVERSAL_V1; ENGULFING_REVERSAL_V1; PIN_BAR_REJECTION_V1 | Potential direction changes and failed moves |
| Mean reversion | 4 | RANGE_EDGE_REJECTION_V1; BOLLINGER_REENTRY_V1; RSI_RECLAIM_V1; VWAP_RECLAIM_V1 | Movement toward range/reference center |
| Relative momentum | 2 | RELATIVE_STRENGTH_V1; BTC_RELATIVE_MOMENTUM_V1 | Outperformance relative to peer/BTC |
| Structure | 1 | CONFIRMED_SWING_CONTINUATION_V1 | Confirmed swing continuation structure |
| **TOTAL** | **24** | | |

**Required per pattern:** side eligibility; explicit price-structure definition; history window; data sufficiency; compatible/incompatible regime hypotheses; versioned numeric thresholds; exact signal clock; entry and invalidation conditions; independently measurable outcome; costs; duplicate/overlap semantics; economic posterior and uncertainty. One decision may carry several tags; do **not** count its realized trade as multiple independent trades.

**Special source defect:** Original BTC_RELATIVE_MOMENTUM mandatory availability flag is missing from its feature vector. V5 must define **BTC_DATA_VALID / unavailable / stale** explicitly, verify the rule can activate on positive synthetic data and **cannot** activate on missing data. Do **not** patch live V4 or claim profitability from fixing this boolean.

**Do not delete nonwinning patterns based only on retrospective tag means.** Continue broad observation labeling, then decide which conditional pattern strategies deserve an economically gated paper test.

## 6. Canonical candidate/evidence/label contract

Every eligible symbol × side × completed event must have an immutable **candidate record**, even when not chosen for trading:

- Identity: experiment ID, event ID, decision timestamp (UTC), coin/side, source snapshot IDs, code SHA, candidate and feature-version digests.
- Eligibility: universe membership as-of event, history completeness, listing age, point-in-time rank, filters and reason for exclusion.
- Features: completed-bar pointers, quote/bid/ask with capture timestamps, BTC+coin market context, breadth, liquidity, volatility and regime confidence with **known-at** times.
- Pattern tags: all matching detectors, family IDs and versioned parameters, explicit zero-tag marker (observation possible; trade qualification independent).
- Risk/cost: frozen bid/ask entry convention, stop/R distance, spread, cost/R estimate, market-impact bounds, funding data validity, capacity and portfolio BTC factor exposure.
- Decision: selector ID/version, calibrated after-cost mean or distribution, lower confidence bound, abstain reason, feature-quality veto, risk-guardian veto, approval/paper authority.
- Research outcomes: gross/net R, MFE/MAE, exit policy/version, four-hour or declared horizon, full tick identity and source digest, exact quality status (**SCORED / UNRESOLVED / CENSORED / PENDING**), maturation clock.
- Truth separation: **historical aggTrade price-path replay**, **quote-constrained simulated executable outcome**, **forward paper**, and **actual trade** are four **distinct evidence grades**, not interchangeable.
- Immutability: decision ID idempotence and an **atomic mutually exclusive terminal state**. All corrections append a distinct documented superseding event; never rewrite the frozen past.
- Full-population denominator: every event records eligible candidates, rejected candidates, selected paper proposals, abstentions and data-quality exclusions; no survivorship-only evaluation.

**Zero-result rule:** Zero-trade is an explicit choice with 0R position PnL, not a completed winning trade. Missing quote/data does not transform into a loss or a successful exit.

## 7. Scientific research and learning method

### 7.1 First validate the observation process

- Recover as-of-event bars, quotes, universe membership and BTC history from existing observation evidence where actually available; compare reconstructed tags against immutable selected V4 tags in a nonmutating reference audit.
- For earlier missing/partial market events, label **UNRECONSTRUCTABLE**; do not splice future candles or invent quote capture timestamps.
- Recover point-in-time **unselected** candidates before evaluating any all-eligible random selector. If only selected labels exist, publish the limitation and use within-admitted comparisons solely as such.
- Historical archives may establish trade chronology and exploratory gross outcomes; **never** assert historic executable bid/ask fills based only on aggTrades.

### 7.2 Establish baselines *before* models

Compare the exact same eligible event universe, labels, costs, occupancy and horizons for:
1. **No trade / ABSTAIN**, 0R.
2. Original V4 deterministic priority, purely as a historical control.
3. Uniform reproducible **eligible-universe** random (only when every eligible counterfactual is qualified).
4. Liquidity/volatility/market-regime simple rule baselines.
5. BTC-aware relative-strength or trend baselines, without a learned ranker.
6. Conditional setup rule(s) with predeclared cost feasibility.
7. Only then, a model-based, confidence-aware selector.

Maintain separate exploratory, calibration, validation and **untouched forward** partitions. Hold out entire contiguous market time blocks, embargo overlapping four-hour labels, block correlated symbol/side episodes and audit action-availability latency. **No random row-level train/test split** on overlapping trades.

### 7.3 Conditional strategy learning

- Learn effectiveness of **(BTC regime, coin regime, pattern family/rule, side, risk/cost bucket)** without exploding into tiny unreliable cells; use hierarchical pooling/shrinkage and report samples and uncertainty.
- Quantify matched-tag interactions with suitable baselines; no naïve allocation of one realized outcome to each matched rule as if independent.
- Prevent outcome leakage, feature backfill, hindsight support/resistance, future funding and selection on later realized price.
- Include negative controls and regime transitions. Track coin- and BTC-factor concentration so one broad correlated move is not counted as 50 independent successes.
- Research label maturation and model training must use only outcomes completely available **strictly before** the scored event.
- Model scores must carry economic meaning or documented calibration. **LambdaRank alone** gives an ordering, not probability of success or positive expected net R.
- If evidence is insufficient, regime shifts, input data fail quality, or net edge lower bound is nonpositive, **ABSTAIN**.

### 7.4 Predeclared success/failure criteria

Before examining any untouched period, freeze: population; eligible symbols; setup definitions; BTC features; lookbacks; exits; cost/slippage/funding stress assumptions; risk and exposure caps; event-cluster dependence method; number of tested variants; performance tests; drawdown and stability limits; no-trade hurdle; missingness tolerances; acceptance thresholds. Numeric thresholds should be specified through a reviewed experiment design **before** the evaluation sample, not optimized on that sample.

A positive average in an in-sample retrospective is **not** a pass. Require robust after-cost performance relative to no-trade and relevant baselines, confidence-adjusted outcomes, repeatability across distinct periods and regimes, operational integrity and acceptable downside.

## 8. Strategy, risk and execution design (paper only until separate approval)

**Qualification order:**

1. As-of-event data and BTC context fully evidenced; no stale feed/gap or ambiguous time provenance.
2. Candidate belongs to frozen eligible universe; valid current coin structure and matched/versioned setup.
3. Side and pattern have adequate regime-conditional support; **positive, conservative expected after-cost advantage**, not just many matched indicators.
4. Entry/R distance is executable and costs affordable; include spread, entry/exit taker/maker assumptions, slip, liquidity, funding and conservative stress.
5. Portfolio factor and position constraints pass: overall open positions, symbol duplication, LONG/SHORT conflicts, BTC-correlation exposure, net/gross exposure and daily drawdown.
6. Predeclared stop/exit/timeout; risk guardian may veto and records WHY.
7. Paper action or no trade is immutable; exact subsequent data-quality status is reported.

**Risk requirements:** per-position risk caps; global drawdown kill-switch; daily exposure budget; adverse BTC shock protection only if test-qualified; reduce/abstain on missing BTC feed or stale quotes; fail closed on desync and reconnect; funding/fee changes; extreme spread/illiquidity; order/position reconciliation if real execution is ever separately authorized.

**No real orders in V5 development or paper-evaluation phases.** A distinct future live architecture (§21) is documented for design continuity only; it requires independent execution-security review, risk controls and explicit owner authorization, none of which is provided here.

## 9. New failure-hunt: investigate beyond selection, ordered by impact

These are **audit hypotheses or known test obligations**, not automatically claims that V4 had each fault.

| Area | Question / threat | Evidence to seek | Gate |
|---|---|---|---|
| Candidate denominator | Were many eligible candidates never recorded? Does capacity distort samples? | As-of-event full scanner reconstruction with exact admitted-vs-eligible counts | G2 |
| BTC availability | Did the BTC-relative rule silently fail? Are BTC features missing, stale or misaligned? | Reproduce original missing-flag condition; synthetic valid/missing/stale cases | G3 |
| Regime misclassification | Do labels use future swings/candles or shift with hindsight? | Point-in-time feature/event-time replay tests | G3 |
| Missing outcomes | Are 976 unresolved outcomes concentrated in certain market moves, sides or setups? | Exact reason/time/regime cross-tabs and censored-label method | G1/G4 |
| Data transport | Do quote and aggTrade sockets certify their own health independently? | Disconnect/reorder/dead-thread recovery failure injection | G1 |
| Restart safety | Can a restart reuse IDs, score after a gap, or revive old paths? | Restart, cursor and terminal-exclusivity invariant tests | G1 |
| Transaction costs | Are tight stops, funding, slip and spread enough to destroy apparent edge? | Per-decision cost/R + stressed executable paper paths | G4/G7 |
| Directionality | Does selecting LONG and SHORT on same event inflate hypothetical edge? | Side-aware duplication and mutually exclusive portfolio execution evaluation | G4/G7 |
| ML leakage | Were train/test examples labeled from overlapping future horizons? | Purged walk-forward/embargo and label-available-by-time assertions | G5 |
| Multiple testing | Did repeated setup/TP tweaks overfit a shared three-day sample? | Experiment registry, untouched holdout, multiplicity-aware review | G5 |
| Regime stability | Does conditional edge persist after BTC/volatility transitions? | Temporal regime-block sensitivity, drawdowns and drift checks | G5/G8 |
| Portfolio economics | Would rank-1 performance survive realistic occupancy and correlated exposure? | One-book chronological position simulator and capital/risk accounting | G7 |
| Execution | Does aggTrade price-crossing approximate real tradable fills? | Forward quote-constrained paper, spread/slip telemetry and no-fill states | G7/G8 |
| Operator safety | Could training compete with feed on small hardware? Could services restart unexpectedly? | Bounded profiling, offline training, cold-backup and no-resume gate review | G1/G8 |
| Governance | Can a model change its own authority, overfit, silently promote or place orders? | Immutable versions, explicit approvals, least-privilege/no-order tests | All |

## 10. Roadmap and acceptance gates

**Execution policy:** This is the **priority order** for design/research, not permission to run code, alter the live VPS or override the ongoing F0 cold-backup policy. Each gate is a STOP/GO decision with written evidence. Work on documents can proceed in parallel with F0; any tests/source changes need separate approval.

### V5-00 — Scope and historical freeze (DESIGN NOW)

**Work:** Approve V5 north star and isolated namespace; document V4 original SHA, frozen source/dataset snapshots and known failure register; classify reusable proven components vs unverified inheritance; specify what must remain read-only. Record F0 as external integrity dependency; preserve V4-R2 documents rather than overwrite or silently abandon them.

**Deliverables:** architecture decision record (ADR-001), contract map, V4-to-V5 migration/nonmigration table, evidence lineage manifest.

**Exit G0:** Owner accepts design-only V5 track, no operational migration or real-money authority implied; isolation and provenance specified.

### V5-01 — F0 integrity gate / minimal reliable platform (DEPENDENCY)

**Work:** The independently managed F0 workstream completes authorized off-VPS, restorable historical preservation before source changes; independent feed states, gap handling/new cohort, restart cursor, immutable terminal exclusivity and resource-safe diagnostics. Prospective missing-data behavior must be measurable.

**Deliverables:** backup/restore evidence, reviewed operational fixes in an isolated source branch, regression report, no-resume/restart policy; scoped owner deployment approvals.

**Exit G1:** Integrity proof on artifacts/copies; fail-closed transport and restart tests; no unsupported causal claims. **No V5 scoring against unverifiable data.**

**Critical authority:** As of this document, F0 was in planning of a cold backup, with destination/stop policy approved but **no inference that execution, backup, deployment, restart or service resumption has occurred**. The owner requires **explicit fresh approval for service resumption**. Only the other F0 workstream may update authoritative operational status.

### V5-02 — Reconstruct complete candidate universe (HIGHEST-PRIORITY RESEARCH)

**Work:** Verify timestamped BTC and all eligible coins' bars, quote snapshots and universe membership; reconstruct at each five-minute event **all eligible symbol × side** and their 24 rule matches **before opening positions**. Preserve unavailable/abstain reasons. Audit selected vs unselected membership; bound sampled reconstruction if history incomplete.

**Deliverables:** candidate-population schema and as-of-event full-denominator audit; attrition and coverage report; deterministic replay tests; controls against 100-slot selection bias.

**Exit G2:** Complete valid population for each accepted event; exact feature/source digests; no future data in feature/eligibility; every missing case explicitly excluded with reason. If archives cannot recover the full population, restrict claims accordingly.

### V5-03 — BTC-aware regime and coin structure engine

**Work:** Design global BTC context, breadth, multi-timeframe per-coin structure and relative momentum with explicit availability/age; define market-regime/transition/unknown states, confidence and no-hindsight swing confirmation. Repair **conceptual** BTC-relative feature contract in V5 isolated code, with positive and missing-data test cases.

**Deliverables:** feature specification, registry versions, condition taxonomy, reference synthetic fixtures, BTC-shock scenarios, data-validity matrix.

**Exit G3:** Causal reproducibility at frozen clocks; BTC stale/absent feeds lead to withheld/unknown decisions, not fabricated zero; source-path feature availability tested; regime labeling deterministic at each timestamp.

### V5-04 — Versioned strategy-pattern and counterfactual lab

**Work:** Port only independently verified detector behavior; annotate each of 24 patterns with prerequisites, regime hypotheses and side. Keep **all eligible opportunities** and predeclared exit/risk labels, including unselected candidates; digest independent price paths and quote/funding quality; handle overlapping tags and censoring.

**Deliverables:** pattern-contract v1, conditional strategy candidate dataset, maturity calendar, original-policy/alternate-policy comparison protocol, cost/R and no-trade accounting.

**Exit G4:** Independent archived price-path reproduction where available; no scored counterfactual lacking source/clock verification; executable-fill grade explicitly separate; missingness/restarts cannot create synthetic profits.

### V5-05 — Scientific baselines and regime-conditional viability

**Work:** Prespecify chronological periods, BTC regime slices, missingness, stop/exit and cost assumptions; compare no trade, V4 admitted priority, eligible random, simple regime and rule baselines on matched, overlapping-event-aware samples. Quantify gross, costs, net, risk and confidence; test whether any conditional pattern clears the net hurdle.

**Deliverables:** experiment registry, immutable baselines, per-regime/side/coin/family effect table, uncertainty and attrition report, formal GO/NO-GO.

**Exit G5:** Valid untouched chronological/out-of-regime evaluation; no unqualified use of selected-only baseline; evidence-backed gains after costs **or explicit finding of no edge**. A NO-EDGE outcome is a scientifically successful STOP.

### V5-06 — Calibrated learning, challengers and concept drift

**Work:** Only if G5 justifies further modeling: build interpretable baseline first, then hierarchical conditional estimators and parsimonious ML. Train offline with causal features and matured labels, purged embargo, group/event-aware scoring and economics-calibrated outputs. Track regime drift and champion challenger process; challenger cannot self-promote.

**Deliverables:** frozen feature/label contract, training cutoff manifest, ML leakage suite, compared models with no-model challenger, prospective drift/suspension policy.

**Exit G6:** Each selected model outperforms simple validated baselines on untouched data with uncertainty and stability; no leakage, no unsupported chance of profit. Otherwise reject/abstain.

### V5-07 — Selective paper decision engine + risk guardian

**Work:** Convert economic evidence into eligible paper proposals, with 0-trade default, cost/risk, portfolio factor exposure and quote freshness gates; simulate realistic capacity (not 100 forced simultaneous virtual fills), conflict resolution and capital occupancy. Quantify abstention rate and missed-opportunity uncertainty.

**Deliverables:** paper-only policy API, immutable proposal/veto ledger, no-trade reason codes, chronological realistic occupancy simulator, risk invariants.

**Exit G7:** All paper proposals pass fixed net/risk gates; deliberately bad feeds or nonpositive candidates produce **zero trades**; backtest matches chronological position accounting and stress limits.

### V5-08 — Isolated shadow and forward paper observation

**Work:** Deploy only an approved, **isolated paper-only** namespace after reliable F0 platform; score fresh real-time data with version-locked candidate set, BTC features, policies and model. Compare to frozen no-trade, eligible random, simple rules and old V4 baseline on same event times where methodologically fair. Preserve outcome censoring, quote/fill uncertainty, operational uptime and resource budgets.

**Deliverables:** immutable forward shadow scorecards, independently audited model and data digests, incident ledger, event-clustered net expectancy and risk report.

**Exit G8:** Prospective repeatability and after-cost risk-adjusted benefit relative to baseline across sufficient independent time/regimes, plus clean operational integrity. Without positive evidence, remain observing and abstaining; no paper-policy promotion.

### V5-09 — Owner review, rollback and any future authority

**Work:** Independently review prospective results, statistical uncertainty, capital/market-risk exposure, cybersecurity and operational incident history. Define rollback checkpoint and previous-state recovery. If someday real-money authority is considered, it must be a **separate future project approval**, including exchange restrictions, execution reconciliation, small-loss caps and kill-switch tests.

**Deliverables:** sign-off report, rejected alternatives, rollback/revert plan, final owner GO/NO-GO.

**Exit G9:** Owner authorizes only the exact scoped action. **Default is NO live trading permission.**

### V5-10 — Controlled continuous improvement

**Work:** Once approved paper is stable, preserve feature and model version history, periodic drift and missingness alerts, explicit challenger training windows and retirement decisions. Do not update candidate criteria from a recently observed loss while still scoring that same untouched period.

**Deliverables:** recurring evidence dashboard, immutable promotion log, safeguards against auto-tuning and experiment pollution.

**Exit G10:** Each change follows the same prospective tests and authorization as its predecessor. No shortcut around earlier gates.

## 11. Practical immediate priorities — exact next outputs

**P0 / NOW (documentation and analysis only; no VPS changes):**
- Publish this V5 roadmap as an independent document and preserve separate local copy.
- Write **ADR-001** approving the V5 approach over extending V4's ranking design; state that F0 operational backup and safety obligations remain intact.
- Design a versioned **full-universe candidate record** before writing a new selector.
- Draft the **BTC context + regime classification + strategy mapping specification**, including missing-data handling and a test for the original unreachable BTC-relative setup.
- Draft a **source-to-label feasibility matrix**: which historical as-of-event features, quotes and later full price paths can actually be recovered for *unselected* candidates? Do not claim all-eligible random results yet.
- Define no-trade and cost/R gates plus event-blocked evaluation protocol **before selecting target thresholds**.
- Assemble a separate F0 handover for the original BTC-relative unreachable rule and potential data contract risk, but do not edit F0's running service/roadmap without owner-approved transfer.

**P1 / AFTER G1 platform integrity:** bounded archival denominator reconstruction and synthetic BTC/regime fixtures in a clean V5 source namespace, with independent regressions.

**P2 / AFTER G2–G5 credible opportunity evidence:** conditional strategy modeling and candidate scoring that can *abstain*.

**P3 / AFTER G6–G7:** isolated paper shadow and forward evaluation, not real orders.

**P4 / ONLY AFTER G8 AND G9:** review whether broader paper promotion or a separately specified real-money proposal is justified.

## 12. Proposed module and artifact contracts (not code changes)

| Proposed V5 component | Responsibility | Output / key invariant |
|---|---|---|
| market_provenance | completed market data, source clocks, BTC/alt observations, quality/continuity | event/snapshot digest; fail closed on holes |
| market_context | BTC context, market breadth, coin correlation/lead-lag and regime features | valid-from timestamps, confidence, UNKNOWN state |
| market_structure | per-symbol swings, trend/range/breakout/compression, volatility/liquidity | point-in-time classification and confirmation |
| pattern_registry | original 24 as tested detectors; future rules versioned | all matched tags including zero-tag; no implicit profitability |
| candidate_universe | full eligible denominator for BOTH directions, including abstained/unselected | reproducible membership and exclusion reasons |
| counterfactual_lab | fixed entry/exit/risk experiment labels, censoring and source paths | price-path vs executable-simulation grades separated |
| conditional_edge | regime/strategy/side net R with uncertainty and stability | confidence-aware positive/net vs no-trade |
| selective_selector | ranked and quality-qualified candidates; abstain | cannot trade on pattern count alone |
| risk_guardian | position, cost, exposure, feed, loss, funding and portfolio caps | unconditional veto authority; never profit predictor |
| paper_book | realistic occupancy, paper entries/exits, cash and drawdown | immutable after-cost results; no exchange orders |
| offline_trainer | leak-free challengers, metadata, model auditing, rollback candidates | no unattended model activation |
| operator_governance | release, approval, checkpoint, kill-switch and postmortem | distinct human authorization for any migration |

**Resource rule:** Existing small live VPS hardware is not an appropriate place to simultaneously load large ZIP archives, retrain models and service WebSocket feeds. Use bounded batches, offline training/artifact evaluation and approved isolated compute; preserve stable observability and safe memory/headroom.

## 13. Regression / experiment acceptance checklist

For every implementation plan, link source/test/evidence under an immutable experiment ID.

- [ ] V5 installation cannot import private order credentials from observation/research namespace.
- [ ] All candidate eligibility/feature/quote timestamps are <= decision time (allow strictly defined completed-candle settle delay).
- [ ] Historical support/swing/structure features do not incorporate future candles.
- [ ] Same BTC features on matching event timestamps agree across eligible coins; stale BTC status is explicit.
- [ ] Synthetic BTC-relative valid case triggers when expected; stale/missing case cannot trigger.
- [ ] 24 detectors have deterministic valid/missing/edge-condition fixtures; no unwarranted requirement that a rule be always active.
- [ ] Full scanner population includes unselected eligible symbol/side alternatives and documented exclusions.
- [ ] Opposite-side and same-market-event outcomes cannot masquerade as independent evidence.
- [ ] If labels mature four hours later, no model sees them before verified maturation and purged/embargoed cutoff.
- [ ] Open replay with aggTrade gap/dead feed is unresolved, not silently scored; unaffected new cohort can recover with proper continuity.
- [ ] Independent socket health, restart cursor and atomic terminal-exclusivity behavior pass.
- [ ] Historical downloaded aggTrades may not substitute for unavailable executable bid/ask/funding evidence.
- [ ] Cost/R identity matches frozen entry/R and fees/slippage; worst-case cost is tested.
- [ ] Risk guardian blocks stale quotes, invalid stop geometry, correlated positions and excessive loss.
- [ ] Candidate matching five rules but with negative expected net R produces **ABSTAIN**.
- [ ] All candidates economically unqualified produces **zero paper orders** and a clear reason code.
- [ ] Reproducible eligible random baseline shares frozen population/horizon/cost/occupancy with selector.
- [ ] No-trade baseline is shown explicitly and dominates negative net mean selectors.
- [ ] Paper trade and research counterfactual labels are never conflated.
- [ ] Models without robust untouched uplift are rejected; no automatic promotion or real orders.
- [ ] Backup/restore/provenance gate is cleared before any production source deployment.
- [ ] Resources and CPU threads are bounded; failure under load is fail closed.
- [ ] Resumption of any paused original service requires explicit owner approval, irrespective of V5 design status.

## 14. Gate scorecard and progress register — as of 2026-10-13

| Gate | Current status | Owner-approved next decision |
|---|---|---|
| A (original V4 diagnostic) | **CLOSED — diagnostic only**, dated Oct 13 | No reopening needed for V5 design |
| Original F0 backup/repair | **INDEPENDENT WORKSTREAM / NOT YET PROVEN COMPLETE** at last reviewed roadmap snapshot | Follow its current owner authorization and approval record |
| G0 V5 architectural scope | **DESIGN DRAFT PUBLISHED; owner review of acceptance still required** | Approve V5 as target architecture, not deployment |
| G1 F0 reliable evidence | **BLOCKED / externally dependent** | Accept independent backup/restore and regression proof |
| G2 full universe | **NOT STARTED; recoverability unknown** | Approve bounded read-only feasibility then isolated development |
| G3 BTC/regime engine | **SPECIFIED CONCEPTUALLY; NOT IMPLEMENTED** | Review feature schema and synthetic fixtures |
| G4 conditional labeling | **NOT STARTED** | Approve frozen label/horizon/execution-grade contract |
| G5 economic baseline | **NOT STARTED** | Approve predeclared, untouched event-block protocol |
| G6 ML | **BLOCKED until economic evidence** | Train only if simple baselines justify it |
| G7 selector/risk/paper simulation | **BLOCKED** | Accept abstention, cost/portfolio risk acceptance |
| G8 prospective shadow/paper | **BLOCKED** | Isolated deployment authorization; no real orders |
| G9 future authority | **NOT AUTHORIZED** | Separate owner decision, never implied by V5 |
| G10 continued learning | **FUTURE** | Reviewed challenger changes only |

**Do not invent completion dates.** Advancement depends on measurable gate evidence and distinct approvals, not a fixed promised deadline.

## 15. Governance and handoff to the other workstream

1. **Separate owner and workspaces:** This standalone V5 design doc may be committed to GitHub main because the owner requested documentation publication. The active original F0 roadmap and its backup/runbooks remain owned by the separate F0 workstream; **do not edit or supersede them silently**.
2. **No operational authorization by implication:** A documentation commit is not approval for source change, tests on the live host, backup execution, stopping/restarting services, promoting a model or submitting Binance orders.
3. **Evidence snapshot versus live state:** V4 analysis is pinned to original SHA; active main branch and process-loaded code may differ. The last inspected F0 roadmap was version 0.2.16, documenting approved cold-backup policy but **not confirmed executed backup or owner-approved resumption**.
4. **Public repository hygiene:** Never publish host IPs, local home paths, private keys, environment secrets, API keys, account data or backup credentials in this document. Separate privileged runbooks stay in their authorized workspace.
5. **V4 reference stays immutable:** Preserve datasets/Gen1–4, original experimental outcomes and negative results. V5 starts with a new namespace and independently reviewed dependencies; no overwrite/reset of historical V4 records.
6. **Cross-workstream handover:** Share **findings and proposed requirements** with F0 owner; do not automatically add BTC market intelligence to F0's limited reliability scope. F0 provides integrity services; V5 owns new candidate intelligence after review.
7. **Decision log:** Every protocol edit records version, rationale, evidence cutoff, which data was already seen, affected gates, owner consent, and exact deployment authority.
8. **Stop conditions:** Incomplete point-in-time eligible universe, unresolved fill data, invalid cross-symbol dependence, nonpositive net lower confidence bound, broken observation integrity or insufficient samples => **HOLD/ABSTAIN**; no forced trade or fabricated score.

## 16. Decision register and next review

| Decision | Disposition | Reason |
|---|---|---|
| DR-V5-001: V5 as target architecture | **PROPOSED FOR OWNER DESIGN ACCEPTANCE** | Correct selection/regime intelligence rather than continuing V4 pattern-count priority |
| DR-V5-002: Keep V4 original evidence and F0 work | **MANDATORY PRECONDITION** | Prevent data destruction, unsafe deployment and false-label training |
| DR-V5-003: 24 setup rules become pattern hypotheses | **DESIGN PRINCIPLE** | Detection does not establish conditional economic advantage |
| DR-V5-004: BTC and altcoin context must be causal/versioned | **DESIGN PRINCIPLE** | Condition- and coin-dependent directional behavior; source bug in BTC-relative rule |
| DR-V5-005: Complete eligible universe and no-trade benchmark | **RESEARCH GATE** | Selected-only outcomes cannot prove random baseline or winning strategy |
| DR-V5-006: Cost-aware abstention and portfolio budget | **RESEARCH/PAPER GATE** | Net after friction and uncertainty determines action; no capacity filling |
| DR-V5-007: Training, testing, shadow and real orders | **SEPARATE FUTURE AUTHORIZATIONS** | Avoid leak, hidden promotions and unsafe trading |
| DR-V5-008: More V4 exit TP comparisons | **DEFERRED, NOT DELETED** | Existing BTC/SOL/XRP pilots already rule out simple TP-only rescue on observed sample |
| DR-V5-009: Other failure-hunt areas | **PRESPECIFIED IN §9** | Candidate design is primary hypothesis but no causal monopoly claimed |

### Immediate next review packet (design only)

1. Confirm owner accepts DR-V5-001–009 and the original F0/backup authority split.
2. Review **V5 full-candidate-universe contract** and historical recoverability before writing/running a new selector.
3. Review the **BTC + coin regime / strategy-family / conditional edge** feature specification with explicit missingness.
4. Freeze **V5 initial baselines and chronological evaluation plan** before any new strategy optimization.
5. Seek separately scoped authorization for isolated code/fixture development, **not live VPS modifications**.

---

### References and source provenance

- Frozen V4 source modules: **nbot/observation/candidate_setups.py**, **v4_research.py**, **v4_selection.py**, **v4_generation.py**, **decision_ledger.py**, **selection.py** at pinned SHA above.
- Original V4-R2 formal Phase A/F0 living roadmap (independently owned): version **0.2.16** last consulted October 13, 2026; owner-approved diagnostic closure and no service resumption without fresh approval.
- Supplemental Oct 13 user-run read-only audits: setup-count and 24-tag historical performance (9,177 scored), nonterminal coverage (976 unresolved, 100 no terminal), verified BTC-relative missing-flag code path.
- Supplemental E03/E04: official Binance aggTrade SHA and exact original price-path reproducibility for BTC Oct11 27, SOL Oct12 84, XRP Oct12 101; exit-policy comparisons all negative on examined after-cost historical cohorts.
- This document is **design and methodology**, not a software release, trading recommendation, profitability assertion or proof that V5 has been built.

### Change log

- **v1.0 — 2026-10-13:** New V5 regime-aware candidate intelligence and BTC-conditioned strategy-learning architecture; reconciled V4 empirical failures and limitations; established phased acceptance gates, F0 dependency, abstain-first policy, learning/regression controls, no-live-authority boundary; published separately from existing V4-R2/F0 roadmap.
- **v1.1 — 2026-10-13:** Added owner-selected two-VPS lifecycle and 2,000-matured research training checkpoints; initial paper baseline Champion; dual independent paper portfolios in one Execution engine; same-forward-market 100-trade review checkpoint, fairness and promotion; and explicitly future three-portfolio live/paper-mirror model with distinct order authority and safety approvals. See §§17–26.


---

## 17. V5-ADR-010 — Owner-selected two-VPS lifecycle and model competition (v1.1 authoritative amendment)

**Design status on 2026-10-13:** The owner and assistant agreed on the intended V5 design in discussion. This section **supersedes earlier conceptual descriptions of the model lifecycle, portfolio architecture and promotion workflow** wherever they differ; it does **not** supersede older forensic evidence, F0 permissions or G0–G10 safeguards. It is a **design decision**, not a functioning deployment or a claim of positive expectancy.

**Simplified loop:** **Observe → collect 2,000 trustworthy matured virtual research outcomes → train → validate → designate the first eligible paper-only baseline Champion → continue observing → train the next frozen Challenger after 2,000 further matured outcomes → compare Champion and Challenger on a common forward period with independent paper portfolios → retain, reject or recommend promotion → repeat.**

**Infrastructure separation:**

| Role | Observation/Learning VPS (“brain”) | Execution VPS (“executor”) |
|---|---|---|
| Public BTC+market context, coin-regime and 24 pattern detection | Owns source acquisition, canonical features, complete eligible candidate universe | May independently receive public market data solely to validate quotes and simulate/execute fills |
| Virtual research and full eligible-candidate counterfactual outcomes | Owns research ledger and label maturation | Does **not** train or invent research counterfactual labels |
| Training, validation, model artifacts, frozen Champion/Challenger inference | Owns models, eligibility/ranking, per-model recommendations, offline challenger training and outcome review | Does not retrain, choose winning model, or override model scores |
| Paper trade placement, risk and accounting | Sends version-locked paper recommendations, receives evidence and portfolio outcomes | Owns safety validation, paper entry/exit simulation, two separate paper books, trade outcomes and idempotence |
| Promotion | Evaluates comparable forward results, recommends retain/replace/suspend with evidence | Applies approved **paper model routing** only after authenticated, explicit authorization; no model self-promotion |
| Future live | Still produces only controlled, versioned Champion proposals; no Binance private order credentials | Only permitted service that could ever hold separately approved live order authority; separate real-order safety gate |

The Observation VPS **continues research while the Champion trades in paper mode**. Training must be offline/bounded and may not starve live market-data ingestion. Paper execution stays on the Execution VPS; virtual learning experiments stay on Observation. Both servers must safely tolerate the other being unavailable; an outage causes **fail-closed abstention**, not fallback to stale proposals.

**Keep the simple mental model:** Observation chooses *what might be worth trading*; Execution independently decides *whether it is safe and executable* and records what happened. The Champion/Challenger comparison is based on the Execution VPS's separately recorded outcomes, not predictions manufactured by the Observation VPS.

## 18. V5-ADR-011 — Top-50 observation universe and initial research cycle

### 18.1 Dynamic observation universe

- Observe **approximately 50 eligible, liquid coins** selected using point-in-time liquidity/volume/spread/market-quality requirements, **plus mandatory BTC market context**. Explicitly decide and version whether BTC itself consumes one of the 50 candidate slots; do not silently change the universe denominator.
- The 50-coin target is an **observation and eligible-candidate budget**, **not** 50 automatic paper trades or 50 mandatory open research positions. Document additions/removals and point-in-time membership; do not select tomorrow's winners using tomorrow's volume.
- Every completed five-minute event evaluates BTC conditions, breadth, each coin's market structure, possible LONG and SHORT hypothesis, matched strategies and estimated transaction costs.
- Research may **observe, classify, or virtually simulate** valid setup/direction candidates whether or not the eventual Champion would trade them. Preserve the full eligible denominator and separate nontrade observations from fully matured virtual trades. Do not claim 2,000 independent samples from 2,000 correlated symbol/direction/strategy variants.

### 18.2 2,000-outcome training checkpoint — explicit proposed policy

- **First training checkpoint:** collect **2,000 fully matured, source-verifiable virtual research outcomes** with immutable entry/risk/exit and modeled costs. This is a proposed generation threshold **not** a proof of sample sufficiency.
- Only **SCORED, chronologically complete** outcomes count toward 2,000. **PENDING, UNRESOLVED, censored and unverifiable** outcomes remain in denominators and must not be invented as wins or losses.
- Duplicate tags on one trade count as **one** outcome. Multiple simultaneous symbol/sides can be informative but are dependent; retain event IDs and BTC regime blocks for effective-sample-size checks.
- Declare **minimum independent market-event count, time-span, regime diversity and per-side coverage** in the experiment protocol before any first training sample is evaluated. If 2,000 rows arrive from effectively one regime, **HOLD**, accumulate more diverse evidence.
- Train with all **allowed prior matured historical data** using an immutable cutoff; after each additional **2,000 newly matured outcomes** propose the next Challenger, not necessarily train solely on the newest 2,000. Never train with competition-period labels while evaluating that competition.
- Every label needs the decision-time BTC/coin regime, side, named pattern tags, quote/cost/risk geometry, fill-evidence grade, and exact exit policy. The learning goal is **conditional after-cost economic performance and uncertainty**, not price memorization or a pure rank score.
- If the universe or historical labels cannot be recovered reliably, **HOLD training**; do not substitute a selected-only historical sample for the complete eligible population without explicitly restricting claims.

### 18.3 First model and first paper Champion

- A first trained model is a **Challenger candidate**, not automatically a worthwhile Champion because a counter passed 2,000.
- It must pass schema/source gates, purged chronological validation, positive-net confidence criteria *or an explicitly approved benchmark-only exploratory exception*, safety tests and no-trade behavior. Specify the quantitative rule before looking at its validation outcomes.
- If accepted, name it **baseline Champion 1** with **paper-only** routing to the Execution VPS. It can abstain from every event. **“Champion” means incumbent benchmark, not validated profitable or live-authorized system.**
- If initial validation fails, retain **NO_MODEL / NO_TRADE** and gather more research; do not force the first model into paper execution.
- Freeze exact model SHA, training-data cutoff, feature/setup/regime versions, cost method, decision thresholds and paper risk limits before paper activation.

## 19. V5-ADR-012 — Two paper portfolios on one Execution VPS during competitions

**Recommended default:** one audited paper-execution service capable of maintaining **two logically and financially isolated portfolio books**. Separate processes may be justified by reliability tests, but duplicating the entire trading/market-feed stack is not required merely to keep two paper books.

- **Portfolio A:** Champion Paper.
- **Portfolio B:** Challenger Paper.
- Both receive model-specific recommendations independently computed on Observation from the **same frozen eligible event stream** and identical point-in-time BTC/coin features.
- Each may select different coins, opposite or matching directions, different strategies, stop/exit levels, or **ABSTAIN**. Neither book blocks an identical symbol in the other; same-book position/risk constraints still apply.
- Both books use the **same starting equity, comparable risk-normalization, fees/slippage/funding model, fresh quote validity rules, position limits, and common market timeline**; their actual exposures and number of trades may differ because selection differs.
- Execution separately validates **each** proposal's freshness, idempotence, side, initial risk, cost/risk, symbol availability and global book limits. Reject reasons are immutable and forwarded with outcomes.
- Book A and B cannot transfer balance, share open positions or fund losses, and must not share portfolio-specific fill/accounting state. Deterministic path/cost simulations can reuse market data while preserving book isolation.
- Paper fill evidence is labeled **simulated**; no exchange execution or actual PnL is claimed.

**Service API (versioned, illustrative):** Every recommendation carries \`experiment_id\`, \`contest_id\` (nullable for baseline), \`model_id\` and SHA, \`portfolio_id\`, \`event_id\`, \`as_of_ms\`, \`expires_at_ms\`, \`symbol\`, \`side\`, \`strategy_tag_ids\`, \`btc_regime_version\`, \`coin_structure_version\`, \`expected_after_cost_net_r\`, confidence, \`entry_quote_reference\`, stop/risk envelope, execution-policy version, sequence number and unique idempotency key. **Paper abstentions and risk vetoes have their own records.** Use authenticated mTLS/signed channels or equivalent with replay prevention; never allow requests to grant a higher execution authority than their authenticated portfolio.

## 20. V5-ADR-013 — Fair Champion–Challenger 100-trade checkpoint

**Owner's intended benchmark:** approximately **100 paper trades per model** during a Champion-vs-Challenger competition. **Refinement for fairness:** Do not independently end the Champion's study at its 100th completed trade and the Challenger's at some other market date. Both must be compared under one frozen, **shared forward UTC event/time period**.

### 20.1 Competition initialization

1. Select the next **already independently validated** Challenger and freeze its model, features, strategy/risk policy and training cutoff. Keep the incumbent Champion unchanged.
2. Establish identical paper account starting equity/risk budget and **common start event**. Record fixed fee/slip/funding/latency assumptions, position and concurrency rules, contest rule version, maximum acceptable drawdown and review criteria.
3. Start both books simultaneously. At each new event, Observation independently scores the exact same eligible universe with each frozen model and emits zero or more recommendations; Execution separately evaluates each book.
4. Account for closed positions, rejected/abstained opportunities, equity curve, costs, drawdown, risk exposure and portfolio time-in-market. Unresolved outcomes are not fabricated.
5. **Proposed initial checkpoint:** at least **100 verifiably settled paper trades per model**, **plus minimum shared evaluation-event/time exposure** and enough independent BTC/market regimes as predeclared. The exact lower confidence bound, minimum duration and maximum contest horizon must be frozen **before** the competition starts.
6. If either model abstains so often that it has fewer than 100 trades, **do not force trades**. Extend only within the prespecified maximum observation window, then report an **inconclusive / low-activity / abstention-sensitive** outcome; there is no automatic replacement.
7. Both continue to the **same common endpoint**, with prescribed disposition for positions still open. Do not silently give one model more favorable post-cutoff price data.
8. Do not let competition profits/labels train or tune **either** frozen competitor while its contest is still running; later challengers get a separate versioned training cutoff.

### 20.2 Evaluation and promotion

Compare **realized after-cost net return on the same initial capital and window**, profit factor/expectancy only when statistically meaningful, max drawdown, volatility/drawdown-adjusted risk, tail losses, capital utilization, correlated BTC exposure, number of closed trades, percentage of abstentions, quote quality, rejection rate and uncertainty by independent market-event blocks.

| Evidence result | Policy |
|---|---|
| Challenger convincingly outperforms incumbent under predeclared after-cost/risk/uncertainty gates, and candidate quality + operational integrity pass | **RECOMMEND paper Champion replacement**; await separate explicit owner approval |
| Champion better | **RETAIN** incumbent; retire/archive Challenger |
| Both lose, confidence intervals overlap substantially, missingness excessive, or data integrity questionable | **HOLD / REVIEW / SUSPEND paper entries as needed**; never promote “least bad” as if profitable |
| Challenger earns more gross profit by extreme leverage, concentration, risk/fee assumption or unfairly different time exposure | **REJECT or HOLD** according to predeclared risk policy |
| Either side has market-feed gap, model-version drift, duplicated actions, unscorable exit or mismatched UTC chronology | **FAIL CLOSED**; stop that evaluation cohort, label as unscorable and investigate |

**Why shared window matters:** Models may choose **different symbols, directions, setup strategies and trade frequencies**, so same-timestamp opportunity exposure is necessary. A “first 100 fills each” comparison without a common window would select different BTC regimes and bias the outcome. The first 100 trades are **a review milestone, not a guaranteed adequate statistical sample**.

**Promotion governance:** Observation generates a signed evidence packet and *proposal*, but cannot secretly replace an Execution portfolio's model mapping. Human owner approval and a reviewed atomic paper-routing cutover with rollback are mandatory. A winning paper Challenger never acquires Binance real-order permission automatically.

## 21. V5-ADR-014 — Future LIVE phase: three independent portfolios

**This is a future design requirement only.** Live Binance trading remains **NOT AUTHORIZED**, and nothing in this roadmap requests live-API access, secret keys, transfers, leverage, or production order capability.

When and only when independent prospective paper evidence, security, exchange execution controls and owner authorization eventually permit real-money Champion trading, keep **three** independently accounted portfolios:

| Portfolio | Model | Authority | Purpose |
|---|---|---|---|
| **Champion Live** | Only explicitly owner-approved Champion | Actual Binance orders, under a separate least-privilege live execution engine and kill switches | Measure actual fills/fees/funding/slippage, balance, order outcomes and risk |
| **Champion Paper Mirror** | Identical frozen Champion proposals and timestamps | Paper simulation only, **no** exchange orders | Paired “same signal, live vs paper” execution-quality counterfactual |
| **Challenger Paper** | Frozen Challenger | Paper simulation only, **no** exchange orders | Model/strategy comparison under the **same paper-account assumptions** as Champion Paper |

**Three essential comparisons:**

1. **Champion Live vs Champion Paper Mirror:** Execution fidelity, e.g., bid/ask slip, maker/taker fee, funding, latency, partial fills, rejections, realized net, adverse selection; no interpretation that paper can reproduce every live fill. The paper mirror should record the same Champion decision requests and timestamps, including live refusal/no-fill as distinct outcomes, to prevent survivor-only “filled trade” comparisons.
2. **Champion Paper vs Challenger Paper:** **Primary model promotion test**, because both are controlled simulations on the same future events, same modeled execution standard and comparable capital. They may trade different coins/sides and have different turnover.
3. **Champion Live vs Challenger Paper:** An informative **operational** comparison, **not** the sole causal basis to replace models. Actual live costs differ and Challenger's live fill behavior is unobserved; require an appropriately conservative estimate of deployment costs.

**Safety and approval:** During a contest the existing live Champion stays frozen. The Challenger never has live order permission or secrets. Even if Challenger wins the paper competition, **paper-promotion and live-authority change are two separate approvals** with human sign-off, exchange position/order reconciliation, risk-budget check, rollback and possible small-scope live canary. A live Champion losing money can be suspended by the independently authorized safety guardian **without needing a winning Challenger**.

**Security:** Only Execution may hold future Binance credentials. Observation's proposals cannot request a “live” escalation. Live and paper portfolios have distinct permissions, ledger IDs, balances and audit trails; never let a paper-book software bug cause a live order or share the same irreversible order submission method.

## 22. V5-ADR-015 — Minimal coherent lifecycle state machine

Keep the public lifecycle understandable; retain safety complexity under explicit states.

~~~text
OBSERVE_AND_RESEARCH
  -> 2000_MATURED_VALID_LABELS (with effective-sample/regime-coverage review)
  -> TRAIN_CANDIDATE
  -> LEAKAGE_FREE_VALIDATE
  -> [REJECT and keep researching | APPROVE_INITIAL_PAPER_BASELINE]
  -> CHAMPION_PAPER_ACTIVE (can ABSTAIN)
  -> +2000_NEW_MATURED_LABELS
  -> TRAIN_AND_FREEZE_CHALLENGER
  -> INDEPENDENT_VALIDATION
  -> [REJECT | START_SHARED_FORWARD_CONTEST]
  -> CHAMPION_PAPER + CHALLENGER_PAPER (same market period)
  -> >=100_VERIFIED_SETTLED_TRADES_EACH + coverage/window gate
  -> REVIEW [RETAIN | PAPER_PROMOTE_WITH_OWNER_APPROVAL | HOLD/SUSPEND]
  -> RETURN_TO_OBSERVE_AND_RESEARCH

FUTURE_LIVE_GATE (explicit distinct approval, never implicit)
  -> CHAMPION_LIVE + CHAMPION_PAPER_MIRROR + CHALLENGER_PAPER
  -> PAPER_VS_PAPER model review; LIVE_VS_ITS_PAPER execution diagnostics
  -> LIVE_CHAMPION_SWAP only after separate authority/risk/rollback approval
~~~

**Allowed abstention at EVERY decision step.** The “2,000” and “100” are **design checkpoints** subject to independently defined coverage/uncertainty and max-duration criteria, not promises of profitability or automatic permission to deploy.

## 23. V5-ADR-016 — Service contracts, outages, accounting and source of truth

### 23.1 Message ownership

- **Observation → Execution:** signed versioned recommendation batches per \`model_id\` and portfolio, including explicit ABSTAIN; immutable event source reference, expiry and idempotency.
- **Execution → Observation:** immutable acceptance/rejection/paper-fill, paper stop/exit/unresolved and independent portfolio/equity reports. Later, if live permission ever exists, actual exchange-confirmed order/fill/cancel and cash/funding accounting are separate evidence channels.
- **Observation review:** can propose freeze/retain/promote; cannot rewrite Execution accounting or grant itself credentials.
- **Owner control plane:** explicit approval and logging for each deployment, cold-backup/resume, portfolio promotion, and future real-money authority.

### 23.2 Critical failure responses

- **Observation unavailable:** Execution must reject stale pending recommendations and follow a documented conservative open-position management/timeout policy; no fabricated new picks.
- **Execution unavailable:** Observation records **recommendation attempted / delivery unknown** separately from accepted actions. Never backfill simulated fills and call them delivered paper orders.
- **Duplicate/reordered deliveries or clock skew:** sequence, idempotency, expiry, event identity and signed model version fail closed.
- **Gap/stale BTC feed:** no silently substituted BTC-zero features; tag market context unknown and abstain until valid again.
- **Research 2,000 counter ambiguous:** count only strictly matured, unique, economically labeled outcomes; avoid duplicated tags, overlapping same-event pseudo-independent observations and unexpected data cutoffs.
- **Contest partial outages:** hold or restart under frozen prespecified policy; always disclose different valid event counts and effective sample size.
- **Capital/accounting differences:** normalize account equity/risk on the same time baseline, not simply mean R of a different trade count. R-based diagnostics remain supplementary.
- **Paper/live mirror mismatch:** report paired intent, simulated entry, actual exchange ack, partial/no fill, actual fees/funding and liquidation/stop behavior without imputing hypothetical exchange fills.

### 23.3 Model artifact & promotion records

Store complete artifact hash, training cutoff, immutable candidate-population/feature/pattern/BTC regime versions, blinded holdout ID, contest population/start/end timestamps, both paper portfolio risk settings, realized equity series, evaluation/uncertainty report, owner authorization and rollback target. Version changes require a new contest; never edit a competitor in place.

## 24. Implementation milestones amended by this v1.1 decision

The original **G0–G10** roadmap remains the safety/qualification backbone. The following concrete acceptance conditions are **added**, not substituted:

| Existing phase | V1.1 design deliverable | Acceptance before proceeding |
|---|---|---|
| G0 — scope | Signed ADR-010–016; role and data-flow diagram; initial paper-only authority matrix | User approves documentation scope; no live action |
| G1 — evidence integrity | F0 independent backup/restore + feed and restart fail-closed behavior | Other F0 workstream certifies; **no presumed completed backup or permission to restart** |
| G2 — full candidate universe | Approximate 50-coin + BTC eligibility, two-sided observed denominator, virtual research labeling | Chronological valid labels, full/censored case accounting |
| G3/G4 — BTC/pattern + cost labels | Regime-conditional structure, side, 24 detectors, BTC relative availability test and costs | Positive/synthetic cases, all timestamps known, robust absent-data states |
| G5 — baseline science | 2,000 verified outcome threshold, effective-sample and coverage contract, no-trade economic baseline | Experiment design frozen before validation |
| G6 — models | Initial baseline Champion gate; next frozen Challenger after 2,000 **additional** matured labels | Purged untouched validation and model/version immutability |
| G7 — paper execution | One engine, **two isolated book ledgers** with per-model recommendation authentication | Same market ticks, independent balances and risk, zero-trade veto |
| G8 — forward comparison | Both paper books share start/end window and proposed >=100 settled trades each when possible | Predeclared max duration, independent-event coverage, event-blocked uncertainty and fair drawdown/equity comparison |
| G9 — promotion | Owner-signed retain/reject/paper replace; explicit live-stage gating | No autonomous live authority; rollback tested |
| G10 — continued learning | Repeatable newly matured evidence and challenger formation | No leakage from running contest, no automatic model activation |
| **FUTURE, separate live gate** | Champion Live + Champion Paper Mirror + Challenger Paper | Owner live permission and independently verified exchange/risk controls, separate from any paper victory |

**Revised immediate V5 design build order:** (1) freeze two-VPS architecture, complete candidate-event contract and portfolio IDs; (2) confirm F0 evidence backup/integrity status with the other chat, without touching its files; (3) specify BTC/50-coin/regime and virtual research labels; (4) design 2,000-matured learning contract and leak-free training cutoffs; (5) specify single dual-book paper executor and idempotent recommendation/outcome protocol; (6) predeclare fair shared-forward 100-trade checkpoint, max window and promotion; (7) design future three-portfolio live mirror **without enabling live functions**.

## 25. Acceptance tests added for lifecycle and future live mode

- [ ] 50 monitored coins do **not** automatically cause 50 paper positions; even with hundreds of matches, ABSTAIN is respected.
- [ ] Different BTC regimes and coin-pattern/side tags are preserved on both **chosen and unchosen** eligible candidates.
- [ ] Two correlated rule tags on one virtual trade do not count as two of 2,000 outcomes.
- [ ] Unresolved/restart-gap/missing quote outcomes do not count toward the 2,000 maturations.
- [ ] Insufficient regime/event diversity after 2,000 labels holds training eligibility without fabricating independent samples.
- [ ] First model fails independent validation => no forced baseline Champion trade.
- [ ] Additional 2,000 *newly matured* labels triggers only Challenger **eligibility**, not automatic admission or promotion.
- [ ] Champion and Challenger choose different symbol/direction/strategy on same 5-minute event; both books settle independently.
- [ ] Champion and Challenger both choose same coin+side; duplicate orders are prevented **within each book**, not incorrectly blocked across books.
- [ ] Champion abstains / Challenger trades: shared common-window risk/equity statistics remain valid.
- [ ] One competitor cannot get a more favorable event period just by completing 100 trades first.
- [ ] A 100-trade checkpoint with overlapping or inconclusive evidence => HOLD, not automatic promotion.
- [ ] Only one paper-execution service is needed for independent dual-book accounting; isolated fault in book B does not corrupt A or real orders.
- [ ] Stale, duplicate, late, altered-model or unauthorized portfolio recommendation fails closed.
- [ ] Observational service outage does not produce stale/double paper entries.
- [ ] Model competition does not use its own outcome labels to retrain either frozen competitor.
- [ ] Both portfolios lose to NO-TRADE => no presumption the less-negative one is profitable.
- [ ] Live mode absent in default V5 build; public market research never requires Binance order credentials.
- [ ] Future Champion Live and Champion Paper Mirror receive **same frozen Champion intent** and log paired decision/fill/no-fill.
- [ ] Future Challenger Paper has zero permission to place a real Binance order.
- [ ] Winning paper Challenger **cannot automatically replace live Champion**.
- [ ] Rollback, reconciliation and independent live shutdown remain controlled by Execution and explicitly authorized owner gates.
- [ ] GitHub documentation update cannot start any VPS systemd service, resume timers or modify F0 backup state.

## 26. V1.1 change record and next-chat authority

- **2026-10-13 / v1.1:** Owner discussion accepted the conceptual two-VPS separation: Observation owns market intelligence, 24 pattern detections, about 50 coin observation, virtual research, 2,000-matured training cohorts, inference and champion/challenger model development; Execution owns one two-book paper engine and realistic fills/accounting; Observation evaluates unbiased common-forward competitions with a proposed 100-trade-per-model review checkpoint; owner's explicit approval controls paper promotion. A future, separately approved live architecture has **Champion Live + Champion Paper Mirror + Challenger Paper** with paper-vs-paper for model selection and live-vs-paper for execution diagnostics. No F0 operational permission, live authority, profitability evidence, source merge or deployment follows from this documentation.
- **Next chat starting point:** Treat sections **17–26** as the authoritative lifecycle/portfolio refinement, together with foundational evidence, G0–G10 and no-order rules in §§1–16. Start by reviewing source and drafting a **minimal executable design/specification and acceptance tests**, but **do not start coding, touch services, create VPS backups, promote a model or grant real-money authority** until the owner grants the specific scoped permission and independent F0 gates permit it.


---

## 27. V1.2 owner-authorized clean restart from V4 — 2026-10-13

**Supersedes previous V5 implementation attempts, not the approved architecture.** The owner directed a clean V5 start from the verified V4 source at `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf`, ignoring all earlier V5 experimental modules. This clean GitHub branch is `v5-clean-restart-20261013`, created from that historical V4 commit; it intentionally does not inherit the former main-branch `nbot/observation/v5_*` prototype code. Sections 17–26 remain the authoritative two-VPS lifecycle and portfolio design.

**Owner working arrangements:** Nontechnical explanations, concise exchanges; assistant can use the connected Windows laptop and GitHub for project changes. VPS actions are to be presented as one reviewed PuTTY command/stage at a time for the owner to execute and return output. No assistant-origin VPS SSH operations. The owner requests old active VPS data reset before starting fresh collection; first inspect exact paths, service/timer states, active writers and storage, then review a narrowly scoped removal plan. Never delete the verified laptop archive or other local files. No blanket recursive deletion of `data/`, model history or runtime state.

**Preservation evidence already completed (separate F0 workstream):** `F:\\NBOT_V4_R2_EVIDENCE_BACKUPS\\20261013T115137Z-288e9b1a` has a ten-file SHA256/size-verified archive (nine SQLite DBs plus one zero-byte original), and an independently tested nine-database SQLite restoration reported PASS in the V4-R2 roadmap v0.2.20 §30. This is per-database historical evidence preservation, not proof of cross-database transaction atomicity or rollback certification. The archive and its isolated restore must remain untouched. The legacy NBOT services/timers were deliberately stopped at last user-reported shutdown; their current state remains to be verified in PuTTY. Do not automatically start or resume anything; obtain the owner's fresh explicit permission before each service start.

**Clean source rule:** New V5 source is implemented in an isolated namespace, e.g. `nbot/v5/`, with new versioned contracts. V3/V4 primitives may be individually imported only after dependency, safety and reliability acceptance tests. No implicit inheritance of old V5 selectors, experiments, models, promotion logic, existing database contents or paper account state. No Binance real-order credentials in Observation, and no real-order capability in initial V5 development.

**First development sequence:** (0) inspect the paused VPS and confirm exact reset scope; (1) implement synthetic/offline complete 5-minute eligible-universe + BTC-context record contract (zero orders); (2) versioned 24-pattern detection and trustworthy virtual outcomes; (3) 2,000-matured train/validate/no-trade gate; (4) one Execution service with independent Champion/Challenger paper books; (5) shared forward contest and owner-governed promotion. All F0 source-health/restart integrity prerequisites remain applicable before relying on prospective feed outcomes. Checkpoint numbers are not automatic statistical approval.

**Initial status on new branch:** Roadmap imported and V5 restart authorized; NO new V5 source implemented, NO VPS database reset performed, NO service restarted, NO model trained or deployed. Next required action: owner-run read-only PuTTY inventory; only afterward prepare a targeted cleanup command for explicit confirmation.

**Change record — v1.2 / 2026-10-13:** Created a truly clean V4-based development branch; recorded user authorization, verified off-VPS backup provenance, no-order boundary and staged PuTTY-driven VPS reset plan. Documentation change only.


---

## 28. V1.3 Observation VPS database reset — user-run PASS, 2026-10-13

**Owner-provided PuTTY stdout (not independently re-executed by assistant):** `PREFLIGHT PASS - removing only approved old databases`; `OLD DATABASE RESET PASS: 25 files removed`; `Common operational database preserved: True`. This followed the user's read-only observation confirming source commit `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf`, seven named NBOT systemd services/timers/target inactive, expected database sizes, 89 GB free, and zero active NBOT process/database file users.

**Precisely scoped action reported complete:** Removed five former V4 SQLite files under `data/observation/v4/`, three former live-observation SQLite files under `data/observation/live/`, zero-byte `data/observation/live/observation.db`, and the 16 present SQLite WAL/SHM companions attached to the eight real database files: 9 base paths + 16 companions = **25 files**. The execution script rechecked exact base-file sizes, seven inactive unit states, and no `fuser` holders before unlinking the enumerated paths; its stdout reported PASS. Source code, configuration, service unit files and `data/common/binance_budget.sqlite` were not part of the removal list.

**Backup boundary:** Historical off-VPS F: archive and independent restore remain documented at `F:\\NBOT_V4_R2_EVIDENCE_BACKUPS\\20261013T115137Z-288e9b1a`. Deletion on the Observation VPS does not modify the laptop archive. A fresh post-reset live-VPS readback was not yet run; PASS is based on owner-reported script exit/output. Execution VPS state remains uninspected in this clean-restart activity.

**Important operating state:** Legacy V4 startup remains PROHIBITED because it may recreate old databases. No V5 VPS checkout, new schema, Observation service, paper book, model or real trade exists yet. Legacy services/timers must stay stopped. New V5 code must be developed/tested offline on the isolated branch, then deployed only with user-visible reviewed PuTTY steps and fresh owner authorization for starting named V5 units.

**Reset checkpoint: PASS (owner-reported). Next checkpoint:** create and test an isolated, no-order V5 candidate observation contract using synthetic closed-5-minute data, complete eligible symbol × LONG/SHORT coverage, BTC validity indicators, missing-evidence rejection, stable decision IDs and deterministic replay. GitHub main/V4 history and F: archival files remain untouched.

**Change record — v1.3 / 2026-10-13:** Recorded successful owner-run targeted Observation VPS reset and boundaries; documentation-only update. No assistant-origin VPS action.


---

## 29. V1.4 First isolated V5 observation contract — CI PASS, 2026-10-13

**GitHub branch:** `v5-clean-restart-20261013` based on pinned V4 source; current offline test commit `97d272ce987d95b6f723003742abdf21e189b5c4`. No commits made to main. Files added: `nbot/v5/__init__.py`, `nbot/v5/observation_contract.py`, `tests/test_v5_observation_contract.py`, and `.github/workflows/v5-isolated-observation.yml`. All use only Python standard library for the new functionality; no execution adapter, Binance access, model weights, API keys or startup services.

**Implemented so far:** An isolated candidate-record contract accepts a closed five-minute event, event-specific eligible symbol universe of 1–50 distinct symbols, separately supplied BTC market context, and per-symbol evidence. It creates one deterministic record per symbol for each of LONG and SHORT; for 50 symbols this is 100 independently attributable observation rows per event, not trades. The record stores all 24 legacy-named pattern identities as MATCH/NO_MATCH/UNAVAILABLE supplied evidence (actual V5 detectors not yet implemented), a BTC availability flag, explicit missing/stale/future-data refusal reasons, no-order authority, no trade action and status OBSERVED versus UNSCORABLE. This does not fabricate outcomes or increase a 2,000-matured training count. SQLite prototype persistence rejects updates/deletes and changed-payload replay for the same ID and wraps each batch atomically; tested only in disposable in-memory DBs.

**Validation evidence:** GitHub Actions run `38401434911`, URL `https://github.com/samqju/Nbot/actions/runs/38401434911`, concluded SUCCESS on the same source commit. Python 3.12 `python -m unittest -v tests.test_v5_observation_contract` reported **Ran 8 tests; OK**. Validated 50→100 directional rows, symmetric sides, missing symbol, stale BTC, incomplete/multiple pattern states, future source and invalid timing guards, duplicate universe refusal, repeatability/append-only and atomic rollback. This is *unit-level synthetic validation*, not production readiness, full technical-detector coverage, live market intelligence, proof of profitability or a guarantee of all required F0 safety invariants.

**Gate classification:** V5-G1a candidate-observation contract **PASS (synthetic / isolated)**. Full first observation milestone **IN PROGRESS** until read-only feed adaptation, all 24 actual detectors, time-continuity/provenance integration, eligible universe rules, deterministic replay of real archived-like fixtures, failure containment and runtime resource checks meet the roadmap. No VPS deployment, new VPS database creation, service/timer start, paper/live trading, model training, promotion or credentials authorized by this CI result.

**Next development checkpoint:** Extend offline tests with genuine detector output and canonical historical-candle interface under a conservative BTC-as-of gate; stay within small VPS memory/CPU limits, with no legacy V4 write path or order imports. Subsequently seek separate user-reviewed PuTTY deployment/start steps.

**Change record — v1.4 / 2026-10-13:** Recorded independently observed 8/8 GitHub CI result and precise limits of first V5 code. GitHub documentation only pending laptop mirror sync if Desktop Commander connection is unavailable.


---

## 30. V1.5 Full 24-pattern + BTC context offline adapter — CI PASS, 2026-10-13

**Source location:** clean GitHub branch `v5-clean-restart-20261013` only; no V5 deployment. Created `nbot/v5/pattern_adapter.py` and `tests/test_v5_pattern_adapter.py`; updated `nbot/v5/observation_contract.py` and isolated GitHub Actions test workflow. Last tested source commit `68a8170fec5249117cae29c8dbe0a0d3938ace9c`. GitHub main and the existing V4 runtime are unchanged. The former unsuccessful experimental V5 code was not imported.

**What now works in isolated, synthetic tests:** A closed-five-minute candle adapter validates at most 96 source candles per asset, requires at least 49 contiguous aligned past candles with positive finite OHLC and nonnegative volume, verifies source ends exactly at the decision event, and requires observation timing at/after candle close but not after decision. Invalid, future, missing, stale, gapped or distorted data are not scored. It computes event-causal 5m/15m/1h/4h returns, ATR, market-side breadth, volatility and cross-sectional ranks from already available candles. Separate `BTCUSDT` candles are required as BTC market context even when BTC is not one of the ~50 eligible symbol records. The five legacy context labels remain **mutually exclusive proxies**, not five independent profitable strategies; all nineteen other original technical conditions are actually evaluated using their pinned V4 definitions. This yields 24 named pattern states per eligible symbol/direction. Overlapping pattern matches are preserved without multiplying trades or learning outcomes. BTC-relative momentum uses the actual BTC one-hour return and stays `UNAVAILABLE` if BTC context is missing/stale. The adapter preserves V4 pattern catalog SHA-256 digest in its detector version; each candidate record also includes candle-source and BTC-source digests, explicit failure reasons and `OBSERVE_ONLY`/`order_authority=NONE`. The record schema version is now `NBOT_V5_CANDIDATE_OBSERVATION_V2`, before any production database exists.

**Conservative coverage policy for this prototype:** A valid cross-sectional context requires at least 10 valid eligible markets and at least 80% of the selected eligible universe; otherwise relevant pattern evidence is `UNAVAILABLE` and records are `UNSCORABLE`. This threshold is a synthetic-first engineering safeguard pending an approved complete market-universe policy, not a confirmed optimal trading threshold or profitability claim. Exact 50-coin eligibility/liquidity snapshot mechanism is still to be implemented.

**Testing outcome:** GitHub Actions run `38404033201`, `https://github.com/samqju/Nbot/actions/runs/38404033201`, **SUCCESS**, executed `python -m unittest -v tests.test_v5_observation_contract tests.test_v5_pattern_adapter` on Python 3.12. **22 tests passed** (eight original contract tests plus fourteen new adapter checks): 50 eligible→100 directional records, all 24 pattern IDs, actual overlapping breakout/volume matches, trend proxy, BTC relative momentum changing with actual BTC prices, context-only BTC, missing/stale BTC abstention, missing eligible coins remaining recorded, gapped/short/future/malformed candle refusal, future observation time not classifying technical patterns, deterministic replay, ledger tamper refusal, and refusal of unexpected symbol data. An intermediate added malformed-row test identified loss of a quality-specific error when its timestamp also failed validation; fixed and green in the stated final run. This is a positive example of test-driven fail-closed refinement, not proof of live-feed correctness or all 24 rules' statistical usefulness.

**Gate status:** V5 G1a candidate-record contract **PASS offline**; G1b 24-rule mapping/BTC-context adapter **PASS offline synthetic**. **NOT YET READY TO DEPLOY**: Must still validate actual read-only candle acquisition and as-of eligibility list, F0 trade/quote feed separate health, uninterrupted market-source events, restart-proof cursor, durable fresh V5 event ledger, CPU/RAM budgets, scheduled five-minute trigger, and safe no-orders runtime packaging. No model, 2,000-completed-outcome training checkpoint, paper competition or live-trading authority exists.

**Laptop sync status:** GitHub roadmap v1.5 is authoritative. Desktop Commander listed Sameer-Laptop **Offline** at the time of update, so synchronization of this newest roadmap to Downloads could not be verified and must be completed when that device reconnects. The laptop F: verified historical archive was not accessed or modified. No owner action required on PuTTY for this offline code gate.

**Change record — v1.5 / 2026-10-13:** Complete 24 original pattern rule integration with real synthetic candle computations and separate BTC context, observe-only safety tests 22/22 PASS; record explicit limitations and pending real-feed reliability gate.


---

## 31. V1.6 Binance public read-only market snapshot reader — MOCKED CI PASS, 2026-10-13

**Approved clean branch only:** `v5-clean-restart-20261013`; neither GitHub main nor running VPS source changed. Added `nbot/v5/public_market.py` and `tests/test_v5_public_market.py`; extended `.github/workflows/v5-isolated-observation.yml` to run the new tests. Last independently inspected CI commit `dd6b9cdef349175d882a9c96730299606cf73ebf`. GitHub Actions `https://github.com/samqju/Nbot/actions/runs/38405515406` **SUCCESS: 36 of 36 Python 3.12 tests PASS**, representing 8 candidate contract + 14 pattern adapter + 14 public-reader tests. **These tests use mocked Binance responses and perform no live networking**. They prove behavior under tested fixtures, not external connectivity or production correctness.

**Public read-only API:** `https://fapi.binance.com`, standard-library HTTPS GET, hard-allowed routes only `/fapi/v1/time`, `/fapi/v1/exchangeInfo`, `/fapi/v1/ticker/24hr` and `/fapi/v1/klines`; no API keys, private endpoints, order modules, websockets, database writes or background service. Fixed per-request timeout, finite bounded response size, errors fail conservatively without retries. Official market-data API reference: `https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data` (endpoints and weights subject to Binance changes).

**One-shot snapshot contract:** A completed 5-minute market event is derived from Binance's public time response, never the currently forming candle. Market eligibility is an event-observed **current** snapshot of Binance USDⓈ-M USDT-quoted/USDT-margined `TRADING` `PERPETUAL` symbols, sorted deterministically by latest retrieved 24-hour `quoteVolume`; request up to 50 eligible symbols (initial manual diagnostic defaults to 12). BTCUSDT is always retrieved separately for context even if outside the selected top-N. Each symbol requests exactly 96 previous 5-minute candles bounded explicitly by `startTime` and `endTime`; open time, close time, OHLCV, contiguity, completeness and time-closure are validated. Strict Binance-time versus machine-clock checks and refusal if the probe crosses into the next event prevent stale decisions. Incomplete symbol data stays visible as UNSCORABLE; missing BTC makes all outputs UNSCORABLE. All outputs are summary-only, `OBSERVATION_ONLY_NO_ORDERS`, `order_authority=NONE`, paper trades 0.

**Limitations:** 24-hour volume is a liquid-market proxy, not a final depth/spread/funding safety policy; observed eligibility is NOT retrospectively claimed for earlier market events. Real-time quote/trade source health (F0), as-of eligibility traceability, bounded retries/backoff, late-event coverage, durable event/candidate append-only ledger, and low-RAM/CPU soak tests remain undone. Zero real-world networking was performed by CI. No inference, trading, position accounting, model training or 2,000 mature label counting is present. The observation service is **not authorized to run**, and old V4 services must remain stopped.

**Next owner-run diagnostic gate, read-only:** Run a limited Python HTTPS GET check in Observation VPS PuTTY for the official public Binance server time and 5-minute BTCUSDT candles, with timeout and bounded output, no checkout modification, secrets, database or systemd commands. The owner sends the output; only a successful real-VPS response supports "live connectivity PASS". Then perform a separate narrowly scoped one-shot V5 module deployment/replay evaluation before any data collection service or startup, with explicit approval.

**Laptop roadmap mirror:** The previous v1.5 document had not been synchronized after Desktop Commander outage. Sync v1.6 to `C:\Users\Sam\Downloads\NBOT_V5_MARKET_INTELLIGENCE_ARCHITECTURE_AND_ROADMAP_2026-10-13.md` only after verifying connection and GitHub source. The historical verified archive on F: is not altered.

**Change record — v1.6 / 2026-10-13:** Market data REST contract & mocks 36/36 PASS; operational live-VPS API reachability not yet tested; service restarts, data writes and trading forbidden.


---

## 32. V1.7 Real Observation VPS Binance public connectivity — owner-run PASS, 2026-10-13

**Provenance:** Owner manually executed a one-shot, read-only Python HTTPS GET diagnostic in the Observation VPS PuTTY shell. It requested `GET https://fapi.binance.com/fapi/v1/time` and three recent `BTCUSDT` `5m` candles via `GET /fapi/v1/klines`, using an explicit event-open cutoff, three-row count check and Binance candle-close timestamp validation. The output was pasted by the owner; the assistant did not independently connect to the VPS or rerun the command.

**Exact owner-reported output:** `BINANCE PUBLIC CONNECTION: PASS`; `BTCUSDT CLOSED CANDLES: 3`; `LATEST CLOSED EVENT (UTC): 2026-10-13 13:25:00+00:00`; `LATEST BTC CLOSE: 83395.00`; `SERVER CLOCK DIFFERENCE (seconds): 0.3`; `OBSERVATION ONLY - NO TRADES`.

**Gate:** Basic remote public Binance USD-M Futures API reachability and timestamp/short BTC five-minute candle retrieval from the Observation VPS **PASS** at the stated instant. This is **not** proof of 96-bar/12-asset or 50-asset continuity, all-asset market eligibility, full production data stream, V5 code execution on VPS, feed-health correctness or readiness for trading. No database writes, code checkout, daemon restart, paper or live execution occurred in this diagnostic. Do not treat the BTC value as a continuously current market quote.

**Next gate:** A one-shot, bounded, user-visible PuTTY diagnostic of the public `exchangeInfo` + `ticker/24hr` eligibility snapshot and 96 consecutive *fully closed* 5-minute candles for the top 12 USDT-perpetual markets plus BTC when not selected. Count and list missing/stale symbols; never silently drop selected eligible symbols; inspect total network requests, runtime and clock agreement. No credentials, downloads, source edits, database changes or service/timer starts. Move to a separately authorized V5 module sandbox on VPS only after the live diagnostic and F0 safety controls are understood.

**Documentation:** This source branch roadmap v1.7 is canonical for the clean restart and shall be mirrored to the laptop `C:\\Users\\Sam\\Downloads\\NBOT_V5_MARKET_INTELLIGENCE_ARCHITECTURE_AND_ROADMAP_2026-10-13.md` when Desktop Commander is online. Preserve F: historical archive untouched.

**Change record — v1.7 / 2026-10-13:** Recorded owner-run read-only public Binance connectivity PASS with honest narrow scope; no operational changes performed by assistant.


---

## 33. V1.8 Twelve-market live Binance candle integrity — owner-run PASS, 2026-10-13

**Evidence source:** Owner pasted output of the bounded public-only, one-time Python HTTPS test executed in Observation VPS PuTTY; assistant has not independently accessed the VPS. The test queried Binance USD-M public `/time`, `/exchangeInfo`, `/ticker/24hr`, and `/klines` for 12 highest-ranked 24-hour quote-volume USDT-margined TRADING PERPETUAL markets; BTCUSDT was among those 12. Requested 96 complete consecutive 5-minute candles for each symbol, checked open/close time boundaries, finite positive OHLC, price bounds and nonnegative volume, and rejected intervals that rolled over while the check ran.

**Exact reported summary:** `Eligible coins tested: 12`; `Total symbols including BTC: 12`; `Complete 96-candle histories: 12`; `Failures: 0`; `Public API requests: 15`; `RESULT: PASS`; `OBSERVATION ONLY - NO TRADES OR DATABASE WRITES`. Selected symbols, in returned liquidity rank order: `BTCUSDT, ETHUSDT, SOLUSDT, ZECUSDT, NEARUSDT, XRPUSDT, HYPEUSDT, DOGEUSDT, STRKUSDT, GTCUSDT, SUIUSDT, ENAUSDT`.

**Gate completed:** Live Observation VPS public Binance API eligibility and candle retrieval for one 12-coin sample **PASS**. The result does not prove the full 50-market universe, live bid/ask quotes, continuous WebSocket health, runtime safety, research labels, learning, profitability, or that the **actual isolated V5 Python module** has run on the VPS. The original V4 directory, deleted historical database sources, stop-only services and laptop historical F: archive were unchanged by the one-shot read-only diagnostic.

**Next stage authorized for preparation:** Guide owner through a separate V5 sandbox checkout at `/home/ubuntu/nbot_v5_sandbox`, fetched from `v5-clean-restart-20261013`, with a pinned Git commit validation and explicit no-touch guarantee for `/home/ubuntu/Nbot`; no systemd starts, execution modules, trading keys or live orders. First run isolated Python offline tests, then a single `python3 -m nbot.v5.public_market --top 12` smoke check from sandbox. Its expected output is descriptive **observe-only summary**, no research/paper orders and no database files created. If the exact sandbox already exists, stop rather than overwrite it. The owner executes and returns the PuTTY output one stage at a time.

**Status:** Design and live public-data connectivity PASS for specified scopes; V5 VPS sandbox checkout and execution **NOT YET PERFORMED** at this entry; every old NBOT service remains intentionally stopped until owner authorizes a specifically named new service. No automatic startup or service migration.

**Change record — v1.8 / 2026-10-13:** Recorded owner-provided live 12/12 candle test and staged isolated V5 one-shot smoke plan. No VPS changes made by assistant.


---

## 34. V1.9 Primary WSS architecture and secondary REST recovery — offline PASS, 2026-10-13

**Owner decision:** Primary continuous Observation/Learning VPS market ingestion will be Binance USDⓈ-M Futures **WebSocket streams (WSS)**, not frequent REST polling. REST is an explicitly bounded secondary path for initial symbol-universe eligibility/snapshot, initial 96 closed-five-minute candles per coin, occasional independent source reconciliation, and approved historical gap recovery. REST must never substitute a reconstructed executable spread, quote freshness, missing trades, or presumed fills. On unresolved stream continuity, missing quote or trade source, or uncertain market history the bot will **abstain** and retain observable UNSCORABLE research states. No existing V4 daemon is authorized for restart; main branch and Execution VPS unchanged.

**Verified exchange routing (official Binance documentation last modified 2026-10-13):** USD-M market WSS is `wss://fstream.binance.com/market/stream?streams=...` for `<symbol>@aggTrade` and `<symbol>@kline_5m`; independent public WSS is `wss://fstream.binance.com/public/stream?streams=...` for `<symbol>@bookTicker`. These are different routed sockets, not one legacy unrouted endpoint; private/user streams are excluded from Observation. Supported server behavior includes 24-hour connection rotation, ping/pong and inbound message/connection limits; the production client must implement tested reconnect, backoff, bounded queues, per-socket liveness and explicit validated new cohorts. Source: `https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/websocket-market-streams/Connect` and `.../Important-WebSocket-Change-Notice` (both checked October 13).

**New isolated files:** `nbot/v5/ws_contract.py` encodes canonical public/market combined subscription URLs for the eligible 1–50 symbols plus BTCUSDT context. It has a strictly bounded event-envelope/parser contract for public bookTicker, aggTrade and 5m kline states, with timestamp, symbol, nonfinite price/volume, crossed-book and kline-finality refusal. `FeedStatus` tracks independent market/public connectivity, quotes, trades, candle cursors, sticky missing-trade IDs, and leaves prospective cohort validity **false until separately verified by a future module**; no automatic recovery or trading authority is implied by connection alone. A connect/disconnect invalidates the affected feed; future claims of full continuity require additional engineering. `nbot/v5/ws_probe.py` is a bounded **manual only**, 8–30 second, 1–3 coin public WSS route smoke script; connects to the two public-only endpoints, validates incoming frames, counts quote/trade/kline evidence, reports PASS/HOLD with refusal reasons, and writes no databases. It requires the existing pinned Python `websockets` dependency present on VPS, but does not install it. No daemon has been created or started.

**Evidence:** GitHub Actions isolated test run `38407891203` `https://github.com/samqju/Nbot/actions/runs/38407891203` on commit `dbcad49225a24f4f88126dc7c3bedb0a1537c33d` completed SUCCESS, 48/48 Python tests: previous 36 and 12 new WSS validation tests (route splitting, complete stream names, both-source gates, BTC inclusion, invalid/late frame handling, completed-candle-only semantics, sticky trade-gap rejection, reconnect/cohort invalidation, and bounded manual-probe mock). The same CI validated WSS module code and simulated probe only; **no live WSS network test yet**.

**Current gate:** Existing owner-run 12/12 live REST diagnostic PASS and actual V5 one-shot REST `24 observed / 0 unscorable / 76 pattern matches / 0 trades` are independently owner-reported. New WSS framing is tested offline only. This research observation is not proof of correct live source continuity, profitable setups, settled trades or model-training milestones. Neither WSS nor REST is currently a running continuous V5 service.

**Next user-controlled sandbox stage:** Update only `/home/ubuntu/nbot_v5_sandbox` to an exact pinned V5 commit from the clean GitHub branch after verifying no local changes and all V4 services remain inactive; rerun the full 48-test suite; run the bounded `python3 -m nbot.v5.ws_probe --symbols BTCUSDT,ETHUSDT --seconds 12` against real routed public/market WSS. It must write no DB and have no order authority. Collect stdout and classify any missing dependency, WSS error, malformed frame or unhealthy route as HOLD, then repair offline. Do **not** start V4 or any V5 systemd service. Subsequent milestone: low-resource streaming runtime with feed-generation continuity, message loss detection, REST-assisted historical candle reconciliation, durable event ledger and restart safety before unattended service start.

**Change record — v1.9 / 2026-10-13:** Owner's WSS-primary/REST-secondary choice explicitly frozen; correct October 2026 Binance market/public endpoint routing incorporated; 48 synthetic tests passed; next live PuTTY WSS validation authorized only as a bounded manual sandbox check.


---

## 35. V2.0 Live routed WSS verified; bounded high-rate ingestion offline gate PASS — 2026-10-13

**Owner-run live WSS proof (not assistant-operated):** In isolated sandbox `/home/ubuntu/nbot_v5_sandbox`, using separate Python venv `/home/ubuntu/nbot_v5_venv` with pinned `websockets==17.2`, owner reported 48/48 tests PASS and successful `python -m nbot.v5.ws_probe --symbols BTCUSDT,ETHUSDT --seconds 12`. Both routed sockets connected: MARKET `/market/stream` received 367 aggTrade + 51 kline_5m updates in 418 frames over ~14 seconds; PUBLIC `/public/stream` received 2,000 bookTicker frames over **5.24 seconds**, reaching the probe's explicit 2,000-frame cap; zero rejected frames, zero trades, zero databases written, no persistent service started. Result PASS for short-lived connectivity ONLY. The public quote feed **did not run for the requested full 12-second observation window** because the diagnostic hit its bounded frame cap; do not cite this as a 12-second sustained 2-feed reliability pass. No final 5-minute candle proof was observed in this 12-second sample; individual kline updates are not mature candle closures.

**Important engineering consequence:** Public `bookTicker` was ~382 messages/second even with just BTCUSDT and ETHUSDT and is expected to grow considerably with the ~50-coin universe. Do not persist every raw quote or create unbounded task queues or assume a low market-data load. Keep only the most recent validated per-symbol quote and update cursor in memory, store a limited number of actual closed candles, make trade data quality independent of quote quality, expose timing and memory capacity evidence, and declare overload/historical continuity HOLD rather than manufacture valid market decisions.

**New code on clean GitHub branch:** `nbot/v5/stream_buffer.py` introduces `BoundedObservationBuffer` holding at most **51 symbol states**, a **latest quote** and **latest aggregate-trade cursor** per symbol, and at most **96 strictly consecutive fully closed five-minute candles** per symbol. It seeds historical candles only from the separately validated 96-candle REST contract and cross-checks overlapping source values; raw WSS frames are not stored. Out-of-order bookTicker updates do not refresh quote freshness. Duplicate final candles are not counted again; contradictory final candles and skipped event opens freeze readiness and require manual investigation rather than silently moving the observation cursor. A market connection interruption invalidates previous historical-WSS continuity claims. Reconnect no longer clears recorded missing aggTrade-ID gaps (`nbot/v5/ws_contract.py` fix), even if new trade traffic arrives. Strictly quote/trade-fresh statuses and validated source generation/cohort remain **not yet verified** and no model/entry authority is implemented.

**Capacity probe:** `nbot/v5/ws_capacity_probe.py` provides a **manual-only bounded** primary WSS throughput/memory diagnostic for 1–50 public symbols plus BTC context, with 8–20 second duration; connection-specific 50,000 frame cap; reports socket health, event counters, actual quote storage, sticky aggTrade-ID gaps and approximate peak process RSS, and returns HOLD on invalid frames, socket errors, frame overload or missing basic trade/quote events. It creates no files, databases, paper trades or service units. It does not promise sustained 24-hour uptime, complete 5-minute finality, quote tick accuracy under network backpressure, guaranteed trade delivery or validated settled outcome labels.

**CI validation:** GitHub Actions run `38409924246` at `https://github.com/samqju/Nbot/actions/runs/38409924246`, source commit `37f3338e53fde2c05ecd12400e5a505dddfd50a3`, Python 3.12, concluded SUCCESS: **60 of 60 tests PASSED** (previous 48 + 12 bounded-stream tests). Checks include coalescing 2,000 quote messages to one latest-quote slot, out-of-order update refusal, incomplete kline rejection, validating exactly 96 historical 5m candles and one-time rolling handoff, time-gap freeze, contradiction hold, REST/WSS conflict hold, disconnection invalidation, trade-gap persistence, 51-state limit, and capacity-probe PASS/HOLD mocked routes. This is isolated synthetic coverage, not validation of a continuous production daemon.

**Next user-run VPS gate:** Verify clean V5 sandbox branch, stopped legacy NBOT services and pinned branch HEAD, update only isolated `/home/ubuntu/nbot_v5_sandbox` to GitHub roadmap commit, rerun 60 tests under the already installed V5 venv and run `python -m nbot.v5.ws_capacity_probe` on the same 12 prior observed eligible coins for 10 seconds. Record per-route frames/duration, quote-coalesced-state count, detected trade gaps, rejected messages, capped stream flags and peak RSS. Run exactly one short session; no systemd service start, no writes to `/home/ubuntu/Nbot`, no credentials and no orders. HOLD if any code version or safety check fails; never add `set -e` or top-level `exit` in user PuTTY commands.

**Gate:** WSS endpoint **basic live connectivity PASS**, bounded high-rate in-memory parser **synthetic PASS**. Full WSS 12/50-coin capacity, sustained continuity, restart-proof observed-event ledger, live REST reconciliation, explicit quality gate, durable labels and future service startup **NOT READY**.

**Change record — v2.0 / 2026-10-13:** Owner's live WSS results recorded with 2,000-frame limit caveat; bounded quote/candle handling, sticky trade gap protection, bounded real-WSS stress diagnostic and 60/60 offline validation committed. No persistent V5 service started.


---

## 36. V2.1 Twelve-market WSS quote overload / 500ms depth alternative — 2026-10-13

**User-run live capacity test report** (not assistant-run): Isolated V5 sandbox on Observation VPS was successfully fast-forwarded to `b843938f824673d15bdc9f62c1de39e169cf6510` without changing V4. Under isolated V5 Python venv, 60/60 offline tests passed. A ten-second configured `ws_capacity_probe` using the 12 previously verified liquid markets produced: `result=HOLD`, reason `PUBLIC_FRAME_CAP`, `market.frames=2297` (1,996 aggregate trade messages and 301 unclosed kline updates), `public.frames=50000` within **12.78 elapsed seconds** (including startup), zero rejected frames on either channel, both connected, `peak_process_rss_mib_approx=36.56`, `latest_quotes_retained=12`, `latest_trades_retained=12`, `total_candles_retained=0`, `trade_gap_symbols=[]`, `cohort_verified=false`, `research_ready=false`, `order_authority=NONE`, `database_written=false` and `persistent_service_started=false`. Zero closed candles are expected during a short test not spanning a five-minute boundary. **Important: limit hit is NOT a clean PASS** despite functioning sockets; there was no evidence of long-term quote fidelity or uninterrupted source health. 50,000 frames/12.78 seconds is roughly 3,900 public messages per wall-clock second in this test, not a forecast for 50 markets.

**Engineering decision (safety-first):** Do not raise the frame cap or classify all 50 markets ready. Use Binance's documented USD-M **public partial book depth** stream `<symbol>@depth5@500ms` as a bounded update-rate **sampled bid/ask** alternative for observation research context. Docs: `https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/ws-streams/public#partial-book-depth-streams`, supported levels `5`, interval `500ms`, dedicated WSS public route. The alternative top-five book snapshots are NOT tick-perfect best-quote event history, execution price, filled liquidity or historical book reconstruction, and Binance may omit RPI orders. Missing/stale snapshots block quote-dependent decisions. Preserve the original real-time `bookTicker` option for any later narrowly-scoped execution quote need after separate capacity tests; never silently intermix different quote streams' update IDs or certify gaps as repaired.

**Source changes:** `nbot/v5/ws_contract.py` supports an explicit, mutually exclusive `quote_mode` of `bookTicker` (old behavior) or `depth5@500ms`; derives the proper combined `/public/stream?streams=...` URL. Strictly validates partial depth stream symbol/event type, USD-M `st=1` if supplied, event times, update-ID range, 1–5 monotonic positive bid/ask levels, uncrossed best price and nonfinite refusal; produces latest sampled best bid/ask and quantity under `quote_source=PARTIAL_DEPTH_500MS`. `FeedStatus` treats snapshots as sampled quotes. `nbot/v5/stream_buffer.py` rejects receipt of the wrong quote stream mode and still retains only one sampled quote per symbol, not all frames. `nbot/v5/ws_capacity_probe.py` CLI default is the **bounded 500ms depth feed**, while explicit `--quote-mode bookTicker` remains available; still uses read-only WSS/REST-free sample run, no daemon, no database. Quote update IDs for sampled depth snapshots do not establish lossless full-book continuity.

**Validation:** GitHub Actions `38411121910`, `https://github.com/samqju/Nbot/actions/runs/38411121910`, exact tested commit `d43481989b47930e2fb43453be2780bc993a8ecc`, Python 3.12 unit CI SUCCESS with **65 of 65 tests** PASS. Five new synthetic tests cover lower-frequency public URL, valid sampled best bid/ask, crossed/malformed/CM market-mismatch refusal, in-memory sample coalescing, rejection of cross-mode messages and stale update IDs. **No real Binance 500ms depth stream has been observed yet by this assistant; the next test is explicitly required.** No legacy services started.

**Next user-controlled gate:** On the Observation VPS, verify clean `/home/ubuntu/nbot_v5_sandbox` branch and inactive seven V4 services, fast-forward only the sandbox to pinned GitHub roadmap commit, rerun 65 V5 tests and perform a single 10-second public+market WSS capacity check on the same 12 user-observed markets using `--quote-mode 'depth5@500ms'`. Compare public frame count to prior 50,000 cap, verify both channels and zero parser refusals, CPU/memory footprint, HOLD reasons and `research_ready=false`. No top-level shell `set -e` or `exit` that closes PuTTY. If Binance live payload differs from the strict fixture, HOLD and investigate instead of relaxing checks without evidence. Do not deploy persistent ingestion, create databases, train models or trade until feed continuity/health and restart-reconciliation phases pass.

**Change record — v2.1 / 2026-10-13:** Confirmed live WSS 12-coin public-quote throughput overload despite low memory; built rate-reduced order-book quote alternative and 65/65 offline tests, pending live validation.


---

## 37. V2.2 Owner-authorized automatic VPS access and first 50-market live WSS capacity — PASS, 2026-10-13

**Updated permission/workflow supersedes earlier PuTTY-only approach for narrowly scoped safe work:** The owner explicitly authorized Desktop Commander on connected Windows laptop `Sameer-Laptop` to invoke existing PuTTY saved sessions via `C:\\Program Files\\PuTTY\\plink.exe` with `-batch -load Observation-VPS -l ubuntu` or `-batch -load Execution-VPS -l ubuntu`. Read-only SSH identity checks completed successfully via the connected laptop: Observation returned `ubuntu/base` (uptime ~10 days, load 0); Execution returned `ubuntu/nbot-execution` (~7 days uptime). No private keys/credentials were read or logged. Permission is limited to safe, reversible V5 isolated actions and does NOT authorize production service changes, real Binance orders, credentials, or edits to original V4 research state. When remote operations were previously restricted to user-run PuTTY, the new instruction supersedes that working arrangement, but not the core F0 safety gates.

**Verified preflight:** Read-only Observation VPS sandbox `/home/ubuntu/nbot_v5_sandbox` was on clean `v5-clean-restart-20261013`, HEAD `0a6b407ecc83e482612fbc4f54d5a1c1dcd2568a`, dependency `websockets==17.2`, 954 MiB total RAM, 574 MiB available, 2,047 MiB swap, 90 GiB free disk; all seven named legacy V4 Observation units were `inactive` and no NBOT application process reported. Execution VPS had 952 MiB RAM, 685 MiB available and ~40 GiB free disk. **Important unresolved operational condition on Execution VPS:** Two legacy services were already `active running`: `nbot-control-tunnel-live-paper.service` and `nbot-execution-live-paper.service`. Assistant did not change, restart or stop them. Do not treat Execution VPS as empty, paused or ready for V5 dual-book deployment without a future owner-approved transition/safety review. V5 did not connect to or instruct either worker.

**Engineering implemented:** `nbot/v5/ws_capacity_probe.py` now supports a mutually exclusive `--top 50` option for current Binance USD-M public `/time` + `/exchangeInfo` + `/ticker/24hr` exchange-reported USDⓈ-M USDT-quoted/margined `TRADING PERPETUAL` universe. Existing verified selection function, finite volume checks, freshness/skew checks, max-50 guard, deterministic ranking and SHA256 snapshot provenance apply. The resulting rank snapshot is explicitly `historical_eligibility_asserted=false`; no lookback fraud, no private or order endpoints. The existing dedicated market/public WSS streams run with `depth5@500ms`; it is not tick-perfect execution pricing. Added `tests/test_v5_ws_selection.py` with four isolated tests for top 50 deterministic selection, invalid-count/no-network refusal, stale/missing market selection and 50-state bounded read-only WSS probe. Updated `.github/workflows/v5-isolated-observation.yml` for the new tests. No V4 files were edited, deleted or imported into service infrastructure. Development commit **`047f75fdec184c25fc53c47262d56492aefd44d9`**; GitHub Actions run `38412483599`, `https://github.com/samqju/Nbot/actions/runs/38412483599`, completed SUCCESS with **69/69 tests PASS**.

**Assistant-executed actual Observation VPS validation:** Through authorized Desktop Commander + PuTTY Plink, verified clean V5 sandbox and expected branch, fast-forwarded **only** sandbox to pinned development commit `047f75f...`, ran all 69 tests using `/home/ubuntu/nbot_v5_venv/bin/python` (69 PASS in 1.573 seconds), then manually executed a **one-shot** `python -m nbot.v5.ws_capacity_probe --top 50 --seconds 10 --quote-mode depth5@500ms`, additionally capped at 45 seconds wall and 512 MiB virtual memory. Process exited successfully (0), no systemd service start and no databases written.

**Exact live 50-market evidence:** Probe returned `result=PASS`, `reasons=[]`, `eligibility_count=50`, `total_symbols_including_btc=50`, `quote_mode=depth5@500ms`, `market.connected=true`, `market.frames=4763` (3,927 aggregate trades + 836 *unclosed* kline updates), `public.connected=true`, `public.frames=960`, no rejected frames, neither route hit the 50,000-frame cap, `latest_quotes_retained=50`, `latest_trades_retained=50`, `total_candles_retained=0`, `trade_gap_symbols=[]`, `peak_process_rss_mib_approx=36.78`, `total_elapsed_seconds=12.85` including connection setup/closing, `cohort_verified=false`, `research_ready=false`, `database_written=false`, `persistent_service_started=false`, and `order_authority=NONE`. Current top-50 selection included BTCUSDT and is identified by SHA256 universe digest `11a835cb0d91be038174a576a0f441b324b4ebca34b93ead99ecb948c86ec66b`; snapshot server time `1791901295710` ms. The complete 50-coin snapshot is emitted in terminal evidence and deliberately is not retrospectively applied to prior market events. No completed final 5-minute candle happened in the 10-second test, so there is no evidence of actual end-to-end closed-event persistence or maturity.

**Milestone acceptance:** 50 current eligible WSS public/market streams, separate routes, bounded latest quote state, short duration and memory, zero invalid frames, explicit future data quality gates, and 69/69 sandbox/CI tests = **PASS for short-duration 50-market WSS transport and memory capacity**. Does **NOT** pass F0 live data/replay reliability, 24-hour continuity, completed 5-minute candle identity, REST recovery after connection loss, durable observations, 2,000 mature labels, initial Champion training, independent paper portfolios, or real trades. Production-ready gate remains **HOLD**. No old Observation units started; Execution's existing two live-paper services remain operationally out-of-scope and require transition review.

**Next unfinished milestone:** Build/test a separate durable V5 event and candle ledger with monotonic five-minute event IDs, WSS *final* kline close-only capture, 96-bar as-of REST initial seed, explicit missing/stale BTC and per-symbol source status, bounded recovery of missing historical candles, immutable provenance, checksum/transaction safety, restart cursor reconciliation and a fail-closed unresolved trade/quote health gate. Test with synthetic gaps, reconnects and crash/restart before a short owner-authorized VPS no-order endurance test spanning actual 5m interval boundaries. Do not enable a production daemon, infer historical liquidity from current volume, or start paper/live execution as part of that milestone.

**Change record — v2.2 / 2026-10-13:** Automated authorized VPS identity/read-only checks, isolated 50-symbol selection code and 69 CI/local tests, live 50-market WSS capacity PASS, legacy Execution live-paper processes flagged without alteration; milestone boundaries and next G1 feed-continuity phase recorded.


---

## 38. V2.3 G1c isolated durable closed-5m candle evidence ledger — foundation PASS, 2026-10-13

**Owner authorization:** Owner explicitly authorized autonomous GitHub and two-VPS engineering, isolated deployments, read-only inspections, and safe/reversible tests, with **one milestone per approval** and a completion report before advancing to the next. The present milestone stops after validated ledger foundation and documentation; no continuously running V5 service or execution deployment is authorized by this checkpoint alone. The old Observation V4 units remain inactive and existing Execution V3 live-paper services are not altered.

**Implemented source (clean GitHub branch only):** `nbot/v5/candle_ledger.py` adds a stand-alone **V5-only SQLite FULL-sync WAL** candle evidence ledger; `nbot/v5/candle_ledger_probe.py` adds a bounded, one-shot, credential-free live REST → temporary SQLite → close/reopen verification. Source accepts **only finalized** validated 5-minute WSS kline data (`k.x=true`, event aligned and actually past close time), validated REST 96-candle historical bootstrap and tightly scoped REST 96-candle gap reconciliation requiring overlapping, consistent past source evidence. Durable per-symbol monotonic candle cursor, immutable candle OHLCV/digest/source metadata, append-only evidence-event and gate-transition logs, idempotent replays, hold on missing intervals, durable conflict flags, checksum/SQLite integrity checks and atomic rollback on failed batch are covered. Gaps greater than the 96-bar recovery window HOLD for manual investigation. Source never repairs missing trade activity, stale quote spreads, model outcomes or fills. All state inspection returns `quote_health=UNVERIFIED`, `trade_health=UNVERIFIED`, `cohort_health=UNVERIFIED`, `research_ready=false`, `training_labels_matured=0`, `order_authority=NONE`. Old `/home/ubuntu/Nbot/` and legacy `v3/v4/live` database paths are explicitly rejected by the constructor. **No production event collector imports or schedules this module yet.**

**Changes:** New files `nbot/v5/candle_ledger.py`, `nbot/v5/candle_ledger_probe.py`, `tests/test_v5_candle_ledger.py` (13 tests), `tests/test_v5_candle_ledger_probe.py` (3 tests), plus update to `.github/workflows/v5-isolated-observation.yml`. There were **69** prior passing tests, now **85**. Last complete code+test commit `c197a94d03abdbecdb40fc09a109e1de8fbe71ac` on branch `v5-clean-restart-20261013`; GitHub main and V4 release history untouched.

**GitHub CI evidence:** GitHub Actions run `38414491821` at `https://github.com/samqju/Nbot/actions/runs/38414491821` completed SUCCESS on the exact code commit, Python 3.12 `Ran 85 tests ... OK`. Coverage includes cold SQLite startup, 96-bar source bootstrap, restart preservation, finalized parsed WSS candle append, duplicate IDs, atomic rollback under deliberately injected storage failure, gap HOLD persisted across reopen, strict REST overlap recovery, source conflict that requires human review, malformed/incomplete future candles refused, append-only SQL triggers and no training/order authority.

**Assistant-executed real Observation VPS validation:** Via authorized Windows Desktop Commander → PuTTY saved session `Observation-VPS`, confirmed `base`, clean isolated `/home/ubuntu/nbot_v5_sandbox` before changing code, and all seven V4 Observation units inactive. Fast-forwarded **only** that sandbox to exact commit `c197a94d03abdbecdb40fc09a109e1de8fbe71ac`. Under isolated `/home/ubuntu/nbot_v5_venv/bin/python`, all **85 unit tests passed in 2.456s**. Applied a **512 MiB virtual-memory limit** and **70s runtime timeout** to the manual, one-time `python -m nbot.v5.candle_ledger_probe --top 3`. Real Binance public `/time`, `/exchangeInfo`, `/ticker/24hr` and 96 validated closed-five-minute `/klines` per symbol delivered a current-snapshot selection of `BTCUSDT, ETHUSDT, SOLUSDT`. SQLite stored 96 candles for each, closed and reopened the connection, and verified all **288 closed candles**, each latest event open `1791901800000` ms, `research_ready=false`, `training_labels_created=0`; result `PASS`, `temporary_database_removed=true`, `live_final_wss_candle_confirmed=false`, `durable_production_ingestion_enabled=false`, `order_authority=NONE`, terminal process exit code **0**. No historical V4 DB reopened/recreated, no live or paper order, no production service start.

**Post-test read-only check:** Observation VPS remained `base` at deployed code commit `c197a94d...`, clean Git working tree, all seven legacy Observation services/timers/target `inactive`, and no new ledger DB in sandbox path. Execution VPS `nbot-execution` still reported two independently running V3 live-paper units `nbot-control-tunnel-live-paper.service` and `nbot-execution-live-paper.service` (both `active`); these pre-existing services were NOT modified or contacted by V5. Their controlled migration/shutdown remains a separate future, owner-visible safety gate before V5 execution.

**Classification: G1c standalone durable source ledger FOUNDATION PASS; LIVE INGESTION/RESEARCH READINESS HOLD.** This is validated persistence plus real REST bootstrap and **synthetic** WSS-final/restart test—not proof of capturing a genuinely WSS-final candle at the five-minute close, continuous stream health, any production collector persistence/auto-reconnect, lasting research samples, real WSS-versus-REST conflict resolution, BTC-wide source cohort freshness, or mature outcomes/training. Those must not be marked done. The ledger smoke's database intentionally existed temporarily and was removed; no unattended V5 stateful service is running.

**Next milestone (ONLY after owner approval):** G1d integrate the new ledger with a bounded, observation-only live WSS event loop across actual five-minute boundaries; perform real WSS final-flag capture and REST historical reconciliation including simulated disconnect/crash/restart; require explicit per-coin plus BTC heartbeat/quote/trade gates before any evidence may qualify as research. Include low RAM/swap budget, backpressure and source-generation safety. Continue using isolated V5 sandbox, no legacy V4 restart, no model training, no orders or Execution VPS modifications.

**Change record — v2.3 / 2026-10-13:** Implemented immutable V5 candle event ledger, 16 new tests, 85/85 CI+VPS pass, 3-symbol/288-bar real REST SQLite close/reopen proof, verified no application/service/trading changes outside isolated V5 sandbox; checkpoint concluded awaiting owner approval for next milestone.


---

## 39. V2.4 G1d real WSS finalized five-minute candle persistence — isolated PASS, 2026-10-13

**Owner approval and scope:** The user explicitly approved proceeding with **G1d** after G1c completion. Safe and reversible isolated code, GitHub actions and bounded VPS diagnostics were authorized. Continuous V5 production service start, model/trading activation, and changes to existing Execution VPS processes remain out of scope. No orders, training labels or paper portfolios were created.

**Source implemented:** `nbot/v5/observation_continuity.py` connects the existing bounded public `depth5@500ms` quote stream and `aggTrade`/five-minute candle market feed to the separate durable `CandleEvidenceLedger`. Only **WSS `k.x=true` finalized candles** are appended to SQLite after validation; individual quote updates coalesce in memory and trade updates are not fabricated by REST. Per-symbol AND BTC context feed-health checks include missing/disconnected/stale quotes, missing/disconnected/stale trades, sticky aggregate-trade-ID gaps, complete candle events, 96-bar ring windows and unapproved post-reconnect market cohort. ALL remain explicitly insufficient for research/trading authorization until F0/G1 certification; no trading/research promotion hooks exist. `CandleEvidenceLedger.synchronize_asof_rest` compares a closed 96-bar REST window against immutable stored overlap on process restart, atomically recovers only verifiable missing candle intervals after logging a `CANDLE_GAP` HOLD, refuses stale/nonoverlapping windows and persists `SOURCE_CONFLICT` on inconsistent REST/WSS history. Quote/trade gaps remain unrepaired. Added `nbot/v5/live_final_probe.py` as a bounded one-shot live public WSS+REST diagnostic which uses a temporary SQLite ledger, checks actual final events, closes/reopens the DB, and automatically removes it; bounded duration/frames and test-only quote mode, no credentials, execution orders, automatic services or training.

**Files:** `nbot/v5/candle_ledger.py` modified (as-of recovery), `nbot/v5/observation_continuity.py` and `nbot/v5/live_final_probe.py` added, `tests/test_v5_observation_continuity.py` added (9 new unit tests), and `.github/workflows/v5-isolated-observation.yml` updated. Development code HEAD: **`174641036332c02ec50cf5a4a4945301479db575`** on `v5-clean-restart-20261013`. CI run `38416444348` (`https://github.com/samqju/Nbot/actions/runs/38416444348`) SUCCESS; earlier run `38416235341` also SUCCESS before final heartbeat/fault handling adjustment. **94/94 unit tests passed**; tests include validated WSS-final replay, two-symbol durable reopen, missing BTC quote/trade hold, nonfinal/future kline refusal, simulated market/public disconnect and REST as-of restart recovery without quote/trade certification, sticky source conflicts, missing long-history overlap, simulated atomic failure, missing WSS candle gap and strict bounded probe arguments.

**Assistant-executed real Observation VPS proof:** Using the authorized Desktop Commander Windows laptop and saved PuTTY `Observation-VPS` session, verified `base`, clean isolated branch, correct unchanged V4 stop-only units; fast-forwarded ONLY `/home/ubuntu/nbot_v5_sandbox` to exact development HEAD, reran all **94 tests (PASS in 3.189s)** in `/home/ubuntu/nbot_v5_venv`. Bounded real diagnostic `timeout 390s` and `ulimit -v 524288` ran `python -u -m nbot.v5.live_final_probe --top 2 --seconds 335`, completed with process **exit 0 in 106.46 seconds**. Initial Binance REST 96 completed bars each for `BTCUSDT` and `ETHUSDT` ended at candle open `1791902400000` ms (14:40 UTC); live Binance market WebSocket produced real `k.x=true` final frames for BOTH symbols with next open `1791902700000` ms (14:45 UTC, finalized at 14:50 UTC), received around `1791903000219` and `1791903000708` ms. **Two authentic WSS final candles were appended atomically**, then SQLite was closed and reopened with **97 immutable closed candles per symbol**, no open candle-source gates, `final_candles_confirmed_for_every_coin=true` and `result=PASS`. During this limited window, 3,224 trade updates and 362 sampled quote updates were parsed, 434 nonfinal kline updates ignored, market frames 3,660, public frames 362; max RSS approximately **38.63 MiB**. The test-only SQLite database was deleted after reopening verification (`temporary_database_removed=true`). No production collector remained running, and no production database was written.

**Critical fail-closed proof:** The resulting report correctly had `cohort_verified=false`, `research_ready=false`, `training_labels_created=0`, `paper_trades=0`, `order_authority=NONE`, and market/quote/trade holds after sockets were intentionally closed. No premature research readiness or trade permission was created by merely storing accurate finalized candles. A real WSS→REST *same-final-candle* reconciliation was NOT run in the live probe; the overlap/restart path was validated by synthetic tests. Nor is 24-hour WSS survival/reconnect or sustained data completeness yet proven. Do not classify full production ingestion / model-learning maturity as PASS.

**Final read-only state:** Observation VPS `base` at sandbox code `1746410...`, Git worktree clean, seven previously named V4 Observation units all `inactive`, no `live_final_probe` process and no test ledger left in sandbox. Execution VPS `nbot-execution` still has exactly the two previously identified legacy LIVE_PAPER services active: `nbot-control-tunnel-live-paper.service` and `nbot-execution-live-paper.service`; untouched throughout. GitHub `main`, the old V4/V3 archival backup on F: and operational DB paths were never edited.

**Milestone assessment: G1d bounded live WSS final→SQLite persistence / restart-recovery foundation PASS. Production/live observation readiness HOLD.** The milestone proves a genuine five-minute close persisted and recovered, with synthetic disconnection/crash-rest verification. It does NOT establish full 50-market five-minute close completeness, 24h uptime, actual WSS disconnect under load, no-loss trade-feed recovery, source timestamp drift/funding/quote safety, or 2,000 matured learning outcomes. G1d is hereby complete only for its isolated proof gates, and no next milestone will begin until the user approves.

**Proposed next milestone, G1e (approval required):** Implement/validate complete **50-market final-close coverage** and WSS-vs-REST finalized-candle cross-source consistency around multiple real five-minute boundaries; add bounded reconnect/backoff with lost-event evidence, source-generation and process-restart detection, health/quarantine counters, and a strictly isolated diagnostic endurance/soak run. No services, model training or execution trading until the owner separately approves and F0 gates pass.

**Change record — v2.4 / 2026-10-13:** Real two-symbol WSS-final 5m capture and SQLite reopen PASS; 94/94 GitHub+VPS tests, 97 candles/symbol checked; fail-closed BTC/source gates retained, legacy systems untouched, next G1e gated by owner approval.


---

## 40. V2.5 G1e 50-coin live WSS close / REST equality / source recovery — HOLD (owner-approved), 2026-10-13

**Owner approval and scope:** Owner explicitly approved G1e after G1d completion. All subsequent work limited to GitHub clean V5 branch and isolated Observation VPS sandbox, bounded public-only WSS/REST probes, transient SQLite test data and safe tests. No production collector, real/paper order authority, training, model promotion, Execution VPS modification, or V3/V4 restart. The user requested a report after each milestone and approval before next; this record closes the approved diagnostic checkpoint as **HOLD pending targeted remediation**, not a completed production-readiness pass.

**Code and test changes:** `nbot/v5/live_cohort_probe.py` (new) explicitly selects today's 50 eligible USDT-margined/trading perpetual markets, including mandatory BTC context, does strict 96 fully closed 5m REST bootstrap per symbol, listens on existing separate public `depth5@500ms` and market `aggTrade` + `kline_5m` WSS sockets, and requires real `k.x=true` final close for every symbol. It then fetches another exact 96-bar REST window per symbol ending at the WSS final event, compares immutable OHLCV and provenance, closes and reopens the SQLite ledger, records source mismatches and gate incidents, and deletes temporary databases. The result is PASS only if **every** symbol has final WSS + matching as-of REST + durable 97th close + quote and trade evidence within that run, with no faults. Public network only; bounded frames/time/memory, no keys/orders or service starts. The later diagnostic addition reports the exact conflicting event open, first source and differing OHLCV fields without weakening source matching.

`nbot/v5/reconnect_policy.py` defines the conservative public/market socket generation and 2/5/12 second capped retry contract; socket interruptions, trade/candle gaps and source cohort risk never automatically certify research. `nbot/v5/source_epochs.py` adds an immutable source generation audit in the same isolated V5 SQLite DB, with monotonic per-route generations and explicit `UNCLEAN_RESTART` evidence after an interrupted previous run. `nbot/v5/observation_continuity.py` now persists source connect/disconnect transitions and retains bounded evidence of coins that emitted sampled public quotes and aggregated trades during the probe while ensuring these do **not** become continuous quote/trade freshness guarantees. Updated `tests/test_v5_g1e_cohort.py` and new `tests/test_v5_source_epochs.py`, plus CI workflow. The tests explicitly simulate a 50-of-50 successful as-of match, loss of one finalized candle, one strict source mismatch, actual ADA-style difference in both `close` and `volume` (using a synthetic test symbol), limits/retries, sticky quote/trade gaps, immutable source generations and unclean restart. 94 prior tests expanded to **107/107 passing**, with a fixed erroneous test-fixture symbol and no reduction of validation criteria.

**Last completely validated code/test commit:** `6d10ee766cebc2f72dea9844b4053ce7ecf831a8` on `v5-clean-restart-20261013`; GitHub Actions run `38421635482` (`https://github.com/samqju/Nbot/actions/runs/38421635482`) SUCCESS, `Ran 107 tests ... OK`. After the two real live probes the latest isolated sandbox code was fast-forwarded safely and all **107 tests passed on Observation VPS in 14.307s**, exiting 0. The original GitHub main, original `/home/ubuntu/Nbot` and F: archives are untouched.

**Actual live probe 1 (VPS, strict entire-cohort HOLD):** `--top 50 --seconds 338`; target finalized event `1791904200000` ms UTC (2026-10-13 15:10 candle open, final near 15:15). All 50 current eligible symbols had verified initial 96 closed REST candles, genuine WSS final candles, at least one sampled quote and trade observation, and **97 candles verified after SQLite reopen**. WSS market frames **103,067**, public frames **21,693**, verified trade events **88,502**, WSS finals **50**, memory peak **37.44 MiB**, temporary DB removed, no order/training/service. However REST cross-source exact-match only **49/50**; `ARBUSDT_V5_LEDGER_ASOF_SOURCE_MISMATCH` triggered persistent-in-session `SOURCE_CONFLICT` and `ARBUSDT_OPEN_LEDGER_GATES`. The original probe did not yet record the exact changed OHLCV fields; **do not assert the ARB mismatch field/type**. Exit code 1, `result=HOLD`, `research_ready=false`.

**Actual live probe 2 (VPS, strict entire-cohort HOLD, enhanced mismatch diagnostics):** `--top 50 --seconds 338`; target finalized event `1791904500000` ms UTC (15:15 candle open, final near 15:20). Again all **50/50 actual WSS final candles**, current quote/trade evidence per asset, 96 REST history per asset, and **97 persisted SQLite candles per asset after reopen**, with memory peak **37.36 MiB**. Market frames **39,392**, public frames **9,043**, accepted aggregate trades **32,873**, sampled quotes **9,043**, WSS finals **50**, both connections completed their bounded diagnostics. REST independently matched **49/50** and disagreed on **ADAUSDT**, specifically its current finalized event `1791904500000` first recorded from `WSS_FINAL`, differing `close` **and** `volume` fields. `ADAUSDT_V5_LEDGER_ASOF_SOURCE_MISMATCH` and `ADAUSDT_OPEN_LEDGER_GATES` were recorded. Strict cohort `HOLD`; exit code 1; `research_ready=false`, no labels/trades/orders/service, transient DB removed. No causal claim has been proven: this could involve exchange final-candle revision, source timing, or another underlying discrepancy; diagnostics establish difference, **not why**. Neither a time-delay nor another external recheck was performed to prove if/when REST values stabilize. A different symbol failed in each run, so do not dismiss mismatch as one chronically bad coin.

**Fault containment and resource proof:** Across both runs, all 50 incoming WSS finals were indeed received and persisted; no system capacity failures, lost symbol selection, quote-message frame budget cap, or memory overrun were observed. A full market cohort MUST NOT pass solely on WSS or REST in the face of a mismatch; the prototype appropriately applies per-source `SOURCE_CONFLICT` quarantine and returns whole-probe HOLD. The two `SOCKET_CLOSED` entries in source policy are caused by intentional teardown of the short-lived test, not evidence of unexpected live transport outages; **actual reconnect during a live socket failure was NOT proven**, only synthetic tests were. One failed symbol must not silently contaminate others' labels; a future mature policy needs per-symbol quarantine and explicit BTC-wide gating rather than pretending the entire world has valid/unavailable evidence.

**Final VPS state:** Observation server `base` on clean sandbox commit `6d10ee7...`; seven named legacy Observation units `inactive`; no live-cohort probe running, no temporary `g1e_temp.db` left; ~578 MiB RAM available and legacy Observation research databases remain absent. Execution VPS `nbot-execution` reported both existing legacy live-paper units `active` and unchanged. The assistant never modified their code, running workers, credentials or trading settings.

**Milestone decision:** G1e **ENGINEERING and SYNTHETIC TESTS PASS**, real **50/50 WSS closing-candle transport and source persistence PASS**, but complete **50/50 WSS-vs-REST OHLCV equality FAILS in both independent live windows** (49/50 each), therefore **G1e production/data-quality acceptance HOLD**, not PASS. No model-training evidence from this batch is authorized. This is not proof that WSS or REST is always correct, nor a mandate to weaken exact source integrity.

**Proposed owner-approved remediation before advancing beyond G1e:** Investigate last-bar stability after WSS `x=true` with bounded, delayed, repeat REST snapshots of the same explicit historical candle; record exact WSS and successive REST digests/timestamps for affected markets without rewriting original immutable source records. Establish a separately versioned **quarantine and finality-maturity policy**: skip/UNSCORABLE only the affected coin and both directions until independently proven sound, keep the remaining verified coins' research opportunity events as separate append-only records, require BTC context and quality threshold, and prohibit trading/training on disputed bar. Test at least two live subsequent close windows and simulated upstream bar correction plus restart; do not automatically resolve `SOURCE_CONFLICT` or infer absent aggTrades from REST. Recheck rate budgets and quote spread freshness. Require another owner approval before starting this remediation submilestone; do not start G1f/training/execution based on G1e HOLD.

**Change record — v2.5 / 2026-10-13:** G1e approved implementation and two real 50-coin trials; 107/107 CI+VPS tests PASS, all 100 real WSS final candle observations captured across two windows, 2 distinct upstream source mismatches blocked correctly, transient databases removed, source generation/reconnect protections tested synthetically, unresolved G1e OHLCV equality HOLD and targeted remediation proposal documented.


---

## 41. V2.6 G1e owner-approved finality mismatch remediation — isolated PASS; production readiness HOLD, 2026-10-13

**Owner authorization and scope:** The owner explicitly approved targeted G1e remediation after the v2.5 two-window ARBUSDT/ADAUSDT REST/WSS mismatch HOLD. Work remained strictly on GitHub clean branch `v5-clean-restart-20261013` and manually invoked, bounded Observation VPS sandbox diagnostic; GitHub main, V3/V4 operational data, Execution VPS, historical F: backup, credentials and systemd units were not modified. The remediation is a proof of safe data handling; it does NOT grant training, trading, long-running service or production research authorization.

**Implemented policy:** New `nbot/v5/finality_quarantine.py`, version `V5_FINALITY_PER_SYMBOL_QUARANTINE_V1`, records the original closed WSS 5m candle OHLCV, receipt time and SHA-256 and three separately observed, time-ordered REST `1`-bar snapshots of that exact 5m closed event, called `FIRST_REST`, `DELAYED_REST` and `CONFIRM_REST`. The one-candle REST endpoint is explicitly bounded to `startTime=event_open` / `endTime=event_open+5m-1`, and all candle times and finite positive OHLCV are checked. The source fingerprints, changed OHLCV fields and REST observation timestamps go into immutable SQLite tables protected by UPDATE/DELETE triggers; a source cannot change between REST stages. Any WSS-versus-REST mismatch, revised REST data or unavailable REST response is a **sticky per-symbol per-event quarantine** and may not silently clear on a later identical quote or restart. No source overwrites. Verified symbols receive one immutable `VERIFIED_OBSERVE_ONLY` LONG and SHORT directional evidence-state record; a disputed or missing symbol receives two `UNSCORABLE` states, never two training labels or trade candidates. A missing/disputed BTCUSDT context makes **ALL** symbols' directional evidence unscorable. A minimum 10 valid symbols and 80% original eligible-universe coverage is required for `evidence_cohort_eligible_for_future_review`; this remains a conservative engineering threshold, not proven profitability or final market-quality authority. Every policy status expressly has `research_ready=false`, `training_labels_created=0`, and `order_authority=NONE`.

**Bounded manual live diagnostic:** New `nbot/v5/live_finality_remediation_probe.py` subscribes to **market WSS only** for currently selected top 50 Binance USD-M USDT-margined perpetual markets (plus BTC context), holds at most one real finalized WSS kline per symbol per event, and makes three separate REST rounds through six bounded concurrent public GET requests per stage with an 8-second inter-stage delay. It can sample one or two actual five-minute close windows. A temporary SQLite database persists live WSS source fingerprints, 3 REST comparisons and both-direction evidence statuses; it is closed/reopened and integrity checked, then deleted at end. On mismatch the report quarantines the affected coin and now also emits its stage-by-stage WSS/REST SHA-256 fingerprints and REST observation timestamps for forensic review. This is intentionally **NOT** a continuously connected trade/quote full-health validation: no public depth book subscription, BTC-wide trade-source certification, full F0, matured outcome labels, paper execution, or real Binance order API. The script and database never run as systemd.

**Synthetic safety test evidence:** Added `tests/test_v5_finality_quarantine.py` (9 unit tests) and `tests/test_v5_finality_remediation_probe.py` (4 unit tests), updated isolated GitHub Actions test workflow. Full suite increased from 107 to **120 tests**. Includes 50-coin cohort with 49 valid + 1 discrepancy, immutable directional preservation (98 verified-observe-only/2 unscorable), immediate REST mismatch followed by convergence at delayed stages still quarantined, REST later revisions, BTC mismatch blocking 100/100 directional states, incomplete stage refusing all evidence, duplicate/out-of-order/future source refusal, tamper-proof SQLite/reopen, two consecutive synthetic 50-market windows, missing authorization constraints, and exact conflicting hash/timestamp exports. Last fully CI-tested V5 **code commit `626a9c6ce93cd5a95f9e30dafa365cdbe859d38f`**, run `38424680492`, `https://github.com/samqju/Nbot/actions/runs/38424680492`, **SUCCESS, Ran 120 tests OK**. The two cosmetic-forensics changes after the actual live run added diagnostic SHA/timestamp export, and are independently CI/VPS tested, not falsely claimed to have been present during the original live sampling.

**Actual owner-authorized live Validation: two consecutive full 50-symbol 5-minute closes:** Observation VPS `base` sandbox had the tested earlier commit `a2dba9765a250a9ca8ebc7656646ddfcc2f41459`, safely advanced from `6d10ee7...`. Before the live test, all seven existing V4 Observation units verified inactive; 120 V5 tests passed on VPS. A manually invoked `timeout 850s` / 512-MiB virtual-memory bounded `python -u -m nbot.v5.live_finality_remediation_probe --top 50 --windows 2 --seconds 338` completed **EXIT 0**, after ~411.30s. The two exact closed WSS event opens were `1791905700000` ms and `1791906000000` ms UTC (2026-10-13 15:35 and 15:40 opens respectively, finalized on successive 15:40/15:45 UTC boundaries). EACH window received all 50 authentic WSS-final `k.x=true` candles, and EACH independent REST round matched **50/50**: `FIRST_REST`, `DELAYED_REST`, `CONFIRM_REST`; **300 of 300 REST/WSS comparisons PASS** across 100 actual finalized candles. Both windows had BTCUSDT context verified and `50/50` per-symbol source-valid observation states; no coin quarantined in these two later windows. Market WSS frames `8165` then `113175`, aggTrade events observed `6766` then `97661` (these trade counts are transport events, NOT full trade health certification). Peak process RSS `79.51 MiB`, within bounded resources. After closing/reopening transient SQLite, `wss_proofs=100`, `rest_checks=300`, `directional_observations=200` immutable source-valid/observe-only evidence states; SQLite integrity PASS, `temporary_db_removed=true`. Explicit `research_ready=false`, `training_labels_created=0`, `order_authority=NONE`, and `persistent_service_started=false` throughout. This live diagnostic used market WSS and public REST; it did NOT collect public-depth quote snapshots simultaneously.

**Final assistant-run isolated code validation:** The sandbox was then fast-forwarded to commit `626a9c6...`, full **120 VPS tests PASS in 18.457s**, exit 0. GitHub branch code and tests match, with no production services changed. All finality data produced by the one-shot probe was intentionally transient, so no 200 real research candidate features or profit labels remain in a production training database. The real status is proof of robust evidence handling, not ongoing autonomous market data collection.

**What the result does NOT prove:** Earlier actual mismatches remain evidence: `ARBUSDT` in 15:10 open and `ADAUSDT` in 15:15 open (the latter close and volume difference). The next two genuine windows were clean, but this cannot establish why the earlier mismatches happened, whether Binance revised the candle after WSS completion, nor absence of rare inconsistencies. In synthetic tests a REST candle revised during delayed checks stays quarantined, but **no real later revision was observed during the two clean windows**. A real recurring discrepancy with detailed WSS/REST hash timeline was not caught in the live run; the new forensic detail output path is synthetically validated. The 10/80% cohort threshold is provisional and does not remove coin eligibility/listing/spread/market-health needs. The temporary-database test does not prove continuous 24h source continuity, crash recovery under live load, research outcome maturity, or independent paper portfolio readiness.

**Milestone disposition:** Owner-approved **targeted G1e remediation PASS** for correct immutable staged finality audit, sticky per-symbol quarantine, BTC-wide hold, isolation of legitimate other coin observations and two verified live 50-coin windows under bounded resource conditions. **Original broader G1e 24-hour live-feed/F0 & production research readiness stays HOLD.** No automatically placed trades, no accepted matured training labels, no champion model, no live execution. Do not auto-advance to G1f or start an always-on V5 service based only on this checkpoint.

**Next owner-approved milestone recommendation:** G1f design and implement safe long-running V5 Observation-only collector with durable as-of symbol cohort snapshots, per-5m append-only research candidate events, explicit quote/trade/candle source-health gates and crash/reconnect bounded REST historical recovery, uptime/memory/CPU metrics and a controlled service transition only after safety review. No training until 2,000 newly mature real after-cost labels across diverse regimes are proven; Execution VPS legacy live-paper services require a separately approved migration transition. Await user approval before starting G1f.

**Change record — v2.6 / 2026-10-13:** Targeted owner-approved G1e finality remediation implemented and 120/120 GitHub+VPS tests passed; two real 50-coin WSS close windows with 300/300 REST as-of comparisons passed, 200 observe-only directional evidence states, 0 trading/training, original two mismatches retained as unexplained; G1e remediation PASS, production readiness HOLD.


---

## 42. V2.7 G1f owner-approved persistent observation-only collector — current-boot PASS, reboot/readiness HOLD (2026-10-13)

**Owner authorization/scope:** The owner explicitly approved G1f after targeted G1e remediation PASS. The assistant used authorized GitHub and Windows Desktop Commander / PuTTY saved sessions to inspect both VPSs; edited only the isolated `v5-clean-restart-20261013` GitHub branch, new `/home/ubuntu/nbot_v5_data` V5-only evidence files, and a new `nbot-v5-observation-only.service` on Observation VPS. Original `/home/ubuntu/Nbot`, old V3/V4 backups, Binance keys, Execution VPS services and GitHub `main` were not modified. No model, training label, paper execution or Binance order endpoint was enabled.

**Implemented:** `nbot/v5/g1f_journal.py` persists an immutable, point-in-time top-50 USDT perpetual cohort digest (never silently retrospectively relabeled), one five-minute event manifest and all LONG+SHORT candidate observation slots as checksum-backed append-only SQLite records. `nbot/v5/g1f_engine.py` requires a genuine finalized WSS candle, three exact independent REST checks, BTC market context, sampled quote freshness and spread, aggregate-trade freshness and sticky missing-trade-ID flags; unavailable or contradicted evidence produces visible UNSCORABLE records instead of fake candidates. Pattern vectors use only the existing independently tested, closed-candle, 24-pattern V5 adapter. The distinction is binding: **OBSERVED candidate is NOT a matured research outcome, trade recommendation, trained model, or trade authority**; all records explicitly `research_ready=false`, `training_labels_created=0`, `order_authority=NONE`.

`nbot/v5/g1f_runner.py` implements a continuous, independent public market WSS and public depth-500ms quote socket with 50-coin cap, 96 closed candles/coin, REST bootstrap/restart overlap verification, bounded REST concurrence, 3-attempt 2/5/12-second reconnect policy, per-route 250,000 frame budget per five minutes, 192 MiB internal peak RSS hold, 256 MiB SQLite+WAL+SHM hold, explicit signal-based stop, 15-second resource/transport heartbeat, and fail-closed exits. WSS interruptions cannot manufacture aggregate trades/quotes or certify source continuity. The process stores state in the **new** `/home/ubuntu/nbot_v5_data/g1f_observe.sqlite` with SQLite synchronous FULL/WAL; no raw quote history accumulates. A restart with up to 96 missing five-minute intervals appends UNSCORABLE historical *missing-event markers*, never hypothetical trades; an interrupted WSS-final/REST audit is also preserved as an UNSCORABLE event, and greater gaps HOLD for review. `nbot/v5/observation_continuity.py` now caps WSS final-candle cursors to three per coin, eliminating a long-lived in-memory list-growth risk. New `nbot/v5/g1f_preflight.py` refuses startup on wrong host, wrong branch, wrong DB path or any of the seven legacy Observation services/timers/target being active; it never starts or stops legacy units.

**Controlled service:** New repository file `deploy/v5/nbot-v5-observation-only.service` and `deploy/v5/G1F_OPERATOR_RUNBOOK.md`; systemd service runs as non-root `ubuntu`, under `ProtectSystem=strict`, writable only to the new V5 evidence directory, `NoNewPrivileges`, `MemoryMax=200M`, `CPUQuota=75%`, `Restart=no`, and read-only `ExecCondition` V4-conflict preflight. The installed unit and repository source were SHA256-equivalent: final `4a556def122616c0a1971657b652f2936fa6d134d2e543814b82645e728bbb79`. Unit activation on Observation VPS returned `active`, `User=ubuntu`, `MainPID=634479`, `MemoryMax=209715200`, `NRestarts=0`. The service remains actively collecting, but **UnitFileState=disabled**, deliberately not enabled for boot. The read-only startup preflight ran independently and returned `G1F_PREFLIGHT_PASS OBSERVATION_ONLY`. Existing Execution VPS `nbot-control-tunnel-live-paper.service` and `nbot-execution-live-paper.service` remained `active` and untouched.

**Automated evidence:** GitHub Actions on exact code/test commit `6c08d689029774b9ecdff45ad43938e67ac0b59a` run `38431130019`, `https://github.com/samqju/Nbot/actions/runs/38431130019`, passed **149/149 Python 3.12 unit tests**. Full matching **149/149 tests passed on Observation VPS** in 27.077s, code HEAD `6c08d68...`, clean Git tree. New tests cover immutable frozen cohort and two-sided journal, failed/missing quote, BTC-wide abstention, staged finality quarantines, restart/offline five-minute markers and unfinalized WSS crash, 96-event missing window cutoff, resource guards, REST-only explicit 96 history, new service privilege/memory restrictions, and refusal to run alongside ANY active legacy unit.

**Genuine production-host observed evidence:** First bounded 60-second 50-coin test exited 0: both WSS connections active, `market_frames=14967`, `public_frames=4959`, no reconnect, RSS `51.95 MiB`, `db_mib=5.86`, zero five-minute event (a short run not spanning a close). A subsequent bounded 390-second run also exited 0, explicitly crossed a real five-minute final-close boundary, persisted BTC-inclusive 50/50 WSS+three-stage REST-finality checked symbol events and **100 durable LONG+SHORT OBSERVED candidate rows** for event open `1791908100000` ms UTC (2026-10-13 16:15 UTC open), zero quarantine, `market_frames=139594`, `public_frames=36180`, no reconnect/gap, peak RSS `53.02 MiB`, DB ~`5.93 MiB`. Terminal proof `research_ready=false`, `training_labels_created=0`, `order_authority=NONE`. Direct read-only SQLite query after clean closure showed the correct single event, 100 OBSERVED rows, **50 WSS proofs and 150 REST stage checks**, `integrity_check=ok`.

The standalone new service then started using the **same** persistent DB, recognized one five-minute interval missed while the controlled test had stopped, and inserted **100 UNSCORABLE LONG+SHORT missing-event records** rather than replaying unseen data. Later while running it captured another real event: final read-only SQLite verification reported **three event manifests total**, **200 OBSERVED plus 100 UNSCORABLE candidate rows**, `PRAGMA quick_check=ok`. Final `journalctl` reported `market_frames=128556`, `public_frames=36785`, `committed_events=1` in service lifetime plus `restart_missing_events=1`, zero reconnects, zero reported aggTrade gaps, BTC/public routes connected, ~`52.65 MiB` peak service-process RSS, unit cgroup memory ~`46.4 MiB`, active PID 634479, no automatic restarts. **These are observation-only evidence slots, not 300 settled trade/outcome labels.**

**Critical boot safety discovery — unresolved:** The legacy V4 Observation units are currently **inactive** but several still show `systemctl is-enabled=enabled`: `nbot-observation-live.service`, `nbot-v4-research.service`, `nbot-v4-paper-contest.service`, `nbot-v4-training.timer`, and `nbot-observer.target`. The paper-control and research-epoch timer are disabled. Their enabled states mean V4 may reactivate on a future host reboot, contrary to the previously desired no-V4-auto-restart safety intent. The assistant explicitly did **not** change or disable any V4 unit as this would alter legacy service configuration without a fresh, owner-visible migration gate. To avoid co-start, the new V5 unit remains **DISABLED for boot** despite being active under the current running host. The new V5 `ExecCondition` will also refuse activation if a legacy Observer becomes active. This is a hard **boot-autostart HOLD**; do not claim unattended reboot survival until the V4 boot configuration is reviewed and owner-approved.

**Disposition:** G1f code, synthetic validation, bounded actual 50-coin sustained observation and checked current-boot systemd **PASS**. Automatic multi-boot persistence, clean V4 boot-state transition, 24-hour uninterrupted continuity, real reconnect after a prolonged WSS outage, verified after-cost matured outcomes/2,000 labels, model training, paper execution and all live order permissions remain **HOLD**. The assistant stopped engineering at this milestone checkpoint; the isolated V5 collector itself continues running as explicitly approved for persistent observation on this boot.

**Next approval request:** Owner to authorize a dedicated G1g **boot coexistence safety** phase: read-only inventory of ALL V4-enabled units and dependencies, owner-reviewed disabling/masking of approved retired V4 units only (never deleting V4 evidence), then controlled enablement of new V5 service across reboot, with a separate extended 24-hour+ observation soak and fault-recovery/audit monitoring. Do not activate model-training or Execution VPS as part of G1g.

**Change record — v2.7 / 2026-10-13:** Owner-approved G1f persistent observation-only engineering verified with 149/149 GitHub+VPS tests, real 50-coin observation and 300 total durable LONG/SHORT records (200 observed/100 unscorable), active secured V5-only systemd service under a 200 MiB limit; boot-on-reboot intentionally blocked pending legacy V4 enabled-unit remediation.


---

## 43. V2.8 G1g V4/V5 boot transition and 24-hour monitoring — BOOT PASS, SOAK PENDING (2026-10-13)

**Authority update:** Owner approved G1g and pre-authorized ordinary, reversible subsequent roadmap milestones without requiring repeated approvals; continue reporting completed milestone evidence. Real-money trading authority and potentially irreversible/high-impact changes still require separate owner approval. Existing no-order, training-readiness and two-VPS separation constraints remain binding.

**Reboot conflict verified:** On Observation VPS hostname base (initial boot ID bb78953b-e8e0-4e0b-8703-a18a6bd49a42), legacy units were inactive but five boot entries were enabled: nbot-observer.target, nbot-observation-live.service, nbot-v4-research.service, nbot-v4-paper-contest.service, and nbot-v4-training.timer. Old target wanted the legacy observer and research-epoch timer. The independently verified Execution VPS retained its two existing live-paper services active; no changes were made there.

**Reversible migration:** A private 916-line systemd unit inventory was saved to /home/ubuntu/nbot_v5_data/G1G_BOOT_UNITS_PRECHANGE_20261013.txt. Exactly those five retired V4 boot entries were disabled (not removed/masked); each returned disabled. Original V4 unit definitions, drop-ins, code, databases, forensic F: backups and GitHub main were preserved. Only nbot-v5-observation-only.service was enabled for multi-user boot. The multi-user.target dependency check showed V5 and host swap, no legacy NBOT observer; timers.target showed no old NBOT timer. The running V5 service had Restart=no and 200 MiB memory limit.

**Pre-reboot data safety:** The live isolated V5 SQLite observation ledger passed PRAGMA quick_check=ok. An independent online SQLite backup was saved at /home/ubuntu/nbot_v5_data/g1g_pre_reboot_snapshot.sqlite (about 3.6 MiB) and also verified quick_check=ok.

**Actual reboot and recovery:** Only Observation VPS was rebooted using sudo systemctl reboot, without touching Execution VPS. The first SSH retry timed out during restart; a later successful connection confirmed a different system boot ID, 9bc008f6-eaa2-4ced-8a9d-c3f54f3b5a6e. V5 automatically started, with ActiveState=active, UnitFileState=enabled, MainPID=1082, NRestarts=0 and about 52–59 MiB actual memory against 200 MiB bound. All SEVEN checked legacy V4 observation services/timers/target stayed inactive, with all five retired boot entries disabled. V5 boot journal showed G1F_PREFLIGHT_PASS OBSERVATION_ONLY; public market and quote WebSocket feeds reconnected with actual nonzero accepted frames, zero initial reported trade ID gaps and zero reconnect attempts during checked window. Both original V5 SQLite ledger and its pre-reboot snapshot again passed quick_check=ok.

**Independent monitoring implementation:** Added nbot/v5/g1g_health.py, a READ-ONLY, fail-closed health check of seven legacy runtime states, the five retired boot states, V5 startup/activation status and memory bounds, read-only SQLite integrity check, frozen coin cohort denominator, event freshness threshold of 20 minutes, and observed versus unscorable directional records. It always reports research_ready=false, training_labels_created=0, order_authority=NONE; it cannot modify a service, access trading credentials or submit orders. Initial mocked systemctl test fixture bug was fixed without weakening the check.

**Hourly unattended audit:** Added deploy/v5/nbot-v5-g1g-health.service, a read-only non-root oneshot, with ProtectSystem=strict, ProtectHome=read-only, Restart=no, MemoryMax=64M and CPUQuota=25%, and deploy/v5/nbot-v5-g1g-health.timer, a monotonic one-hour timer with OnBootSec=8min and Persistent=true. Both installed systemd units were SHA256-identical to GitHub files and passed systemd-analyze verify. Manual service activation yielded Result=success and ExecMainStatus=0. Timer is enabled and active with a verified next monotonic trigger. An actual scheduled hourly read-only run logged another PASS via journald (8 manifests, 700 OBSERVED + 100 UNSCORABLE directional records, database integrity OK, V4 inactive/disabled, V5 active/enabled, zero health blockers). It produces passive health evidence; it does not restart V5 or contact Execution VPS.

**Engineering verification:** GitHub CI code/test commit 5044dd15927e1c2cda9d6431b1b98ea46ea26e8f, Actions run 38434353024, https://github.com/samqju/Nbot/actions/runs/38434353024, SUCCESS with 156/156 Python 3.12 safety tests. Actual Observation VPS ran the same 156 tests successfully in 27.490s. This includes new tests/test_v5_g1g_health.py and tests/test_v5_g1g_service.py, covering every legacy boot/runtime conflict, missing/stale/incorrectly sized event ledger, unsafe DB symlink/memory, limits and no trading authority. The isolated sandbox was fast-forwarded to that verified commit and remained clean while the original V5 observation-only systemd process continued running. Independent read-only postboot G1g health audit was PASS with 8 event manifests, 700 observed + 100 unscorable records and no safety blockers.

**Extended soak:** A one-time automated 24-hour follow-up was scheduled for 2026-10-14 16:58:42 UTC (2026-10-14 22:28:42 India time), to inspect hourly audit journals, five-minute durable event continuity, observed/held windows, systemd boot/restarts, memory, fault evidence and database integrity. If connected inspection infrastructure is unavailable, the result must be UNVERIFIED rather than fabricated. The local hourly timer generates its own evidence while the laptop is offline.

**Disposition:** G1g **reversible legacy boot isolation, real reboot, automatic V5-only startup, SQLite restart integrity and hourly monitor deployment PASS**. The full 24-hour+ uninterrupted market-feed/reconnect soak is STILL RUNNING / HOLD; it must NOT be recorded as a completed PASS before independent next-day evidence. Research readiness, 2,000 valid matured outcome labels, Champion training, dual paper portfolio execution, model promotion and real money remain NOT AUTHORIZED. No real/paper exchange orders were created.

**Roadmap continuation:** Ordinary future V5 engineering is pre-authorized without asking at each milestone. Continue G2 full eligible-population and BTC-regime scientific candidate design while the independent 24-hour reliability gate accumulates evidence; require remediation if the soak reveals a data/source failure. No Execution VPS migration or real-money trading authorization is implied.

**Change record — v2.8 / 2026-10-13:** Owner-granted standard milestone autonomy; five V4 retired boot symlinks disabled reversibly, V5 enabled, actual reboot proven and all V4 remain inactive, SQLite snapshot/integrity verified, 156/156 CI/VPS tests, hourly read-only audit installed and verified, automated next-day 24h review scheduled.


---

## 44. V2.8.1 — Owner-authorized retirement of Execution VPS legacy V3 live-paper workers (2026-10-13)

**Owner instruction:** Owner explicitly questioned why the two unnecessary old Execution VPS services were still running and requested stopping them; current Observation-only V5 does not use old Execution V3 paper workers. This was treated as an independently authorized, reversible service shutdown; **no permission to send paper or real-money orders or delete legacy code/data** was inferred.

**Before change, verified directly on `nbot-execution`:** `nbot-execution-live-paper.service` described itself as `NBOT V3 LIVE_PAPER Execution Worker`; `nbot-control-tunnel-live-paper.service` as `NBOT V3 Execution -> Observation LIVE_PAPER Control Tunnel`. Both had `ActiveState=active`, `UnitFileState=enabled`, `Restart=always` and `WantedBy=multi-user.target`; execution worker wanted the control tunnel. A third `nbot-control-tunnel-testnet.service` was already disabled. These service identities were read from live `systemctl show/list-unit-files` output without exposing secret environment variables.

**Action:** Saved a minimal service-state audit (0600 permissions) at `/home/ubuntu/NBOT_V3_EXECUTION_SHUTDOWN_AUDIT_20261013.txt`, then executed `sudo systemctl disable --now nbot-execution-live-paper.service nbot-control-tunnel-live-paper.service` on **Execution VPS only**. Systemd confirmed removal of their two `multi-user.target.wants` symlinks and both services `ActiveState=inactive`, `SubState=dead`, `UnitFileState=disabled`, `MainPID=0`, `Result=success`. A second independent read-only verification confirmed there were **zero running NBOT systemd services** on Execution VPS; all three known NBOT execution unit files (the two old live-paper plus existing testnet tunnel) show disabled. No unit files were deleted, masked, edited or migrated, no old V3/V4 code/databases/logs were removed and no real-money order flow was enabled.

**Independent Observation VPS check:** Immediately following Execution VPS shutdown, the Observation host `base` still reported `nbot-v5-observation-only.service` **active, enabled, MainPID present, NRestarts=0**, and `nbot-v5-g1g-health.timer` **active, enabled**. Thus stopping the legacy execution/control tunnel had not interrupted the V5 collector or hourly G1g audit in this observed check.

**Safety and roadmap status:** This removes legacy Execution VPS idle workload and reboot/autorestart behavior before any V5 Champion/Challenger deployment. It does **not** indicate that a V5 Execution agent, paper books, model, or live-trade infrastructure is already running. Prior G1g 24-hour soak remains pending, and G2 learning/scientific-observation milestones remain incomplete. Future Execution VPS reuse must involve independent owner-reviewed V5 Champion and Challenger isolated portfolio engineering and simulation validation; no implicit restart of legacy V3 workers.

**Change record — v2.8.1 / 2026-10-13:** Reversibly stopped and disabled both owner-identified unused V3 execution live-paper workers, verified Execution VPS NBOT idle, confirmed V5 Observation VPS unaffected, preserved all existing source/data/logs and legacy audit evidence.


---

## 45. V2.8.2 — Owner-shortened G1G 12-hour checkpoint and isolated G2 population audit (2026-10-14)

**Owner explicitly replaced G1g 24-hour soak with a 12-hour reliability checkpoint at 10:30 AM IST, 2026-10-14.** An actual direct read-only check at 10:30:52 IST verified Observation host base uptime 12h14m, unchanged post-G1g reboot ID 9bc008f6-eaa2-4ced-8a9d-c3f54f3b5a6e, nbot-v5-observation-only.service active/enabled with MainPID=1082 and NRestarts=0; current resident systemd memory 101,195,776 bytes, observed peak 111,292,416 bytes versus hard 209,715,200-byte cap. Seven checked retired V4 units stayed inactive, five retired boot states disabled, hourly health timer active/enabled and recently fired. G1g read-only report PASS: SQLite quick_check=ok, 152 committed event manifests, 15,090 OBSERVED + 110 UNSCORABLE directional records. Journal heartbeat confirmed market and public feed routes connected, reconnect_attempts=0, trade_gaps=0, research_ready=false and order_authority=NONE. All checks are operational; real disconnection recovery, profitable strategy and 24h soak were NOT proven.

**Parallel safe scientific G2 development:** Created independent branch feature/v5-observation-g2-20261014 (never merged into live branch or Execution). Added read-only nbot/v5/g2_population_audit.py and tests/test_v5_g2_population_audit.py to verify frozen source cohort, exactly 50 symbols x LONG/SHORT per completed five-minute event, complete 24 pattern states, identity/hash/source clocks, matching manifest/event counts, explicit HONEST unavailable reasons, no replayed/dangling events, and absence of any recommendation, label, training or order authority. Standalone Observation VPS clone/worktree at /home/ubuntu/nbot_v5_g2_audit_dev tested and queried original live SQLite with mode=ro; running Observation service was not restarted or changed. GitHub Actions on Observation G2 isolated commit 80277c2826b56a928d10e65d84794fb11d80b640 passed 166/166 tests, run https://github.com/samqju/Nbot/actions/runs/38515064045 . Observation VPS G2 tests passed 10/10.

**Actual G2 live outcome:** Independent G2 auditor PASS with zero violations, 154 contiguous committed five-minute event manifests, 50 frozen symbols and complete 15,400 expected/present two-sided candidate slots (15,290 OBSERVED, 110 UNSCORABLE). Exactly six manifests had HOLD status: one earlier explicitly recorded process-offline interval accounting for 100 directional records, and other intervals holding ten records due to stale trade data; counts across reason codes are overlapping, not independent observations. Initial cohort REST/bootstrap clock preceded first committed observation by TWO five-minute setup intervals; explicitly reported and excluded, not silently counted as observed. No gaps among committed events, no invented terminal trade labels or executable orders.

**Execution dependency and safety:** Separate Execution E1–E5 offline synthetic 72/72 PASS is unchanged. E6A offline security/interface development MAY resume now, but E6B authenticated operational Observation-to-Execution integration remains HOLD pending a real scientifically validated first Champion plus compatible signed versioned recommendation producer, independent market quality/risk checks and paper authorization. No such model or producer exists; 15,290 candidate observations are **NOT** 15,290 matured after-cost training outcomes. Scientific G2 outcome labeling and future model creation remain separate not-yet-complete roadmap gates. Live Binance order authority remains NONE. A direct 12h check does NOT waive subsequent model/profit/safety gates.

**Change record — v2.8.2 / 2026-10-14:** 12h G1g operational PASS (not 24h) and G2 population-only integrity audit PASS, further scientific labels/model/integration HOLD. Detailed handoff in docs/NBOT_V5_G1G_12H_AND_G2_AUDIT_2026-10-14.md on isolated Observation G2 branch.


---

## 46. V2.8.3 — G1 forensic preservation verification and G2 provenance acceptance HOLD (2026-10-14)

**Owner instruction:** Complete G1 then G2 in the original roadmap order without shortcuts. No default permission for real money, irreversible old-data deletion or unverified paper/live trading was inferred.

**G1 independent historical preservation evidence:** User's F: drive contains 2026-10-13 snapshot `NBOT_V4_R2_EVIDENCE_BACKUPS/20261013T115137Z-288e9b1a`, original per-database manifest and separate `_ISOLATED_RESTORE` subtree. Actual read-only SHA256 recalculation confirmed all TEN original archived files AND all TEN respective restored copies byte-match their manifest SHA256 values. The manifest certifies nine independent SQLite sources passed SQLITE_INTEGRITY_OK at original snapshot time and one intentionally zero-byte original was preserved. Backup status VERIFIED_PER_DATABASE / STOPPED_SERVICES_PER_DATABASE; explicitly `cross_database_atomicity=NOT_PROVEN`. No new SQLite PRAGMA integrity_check was run on the laptop restore copies; do not claim new physical cross-database transaction consistency. Original F0 service-resumption restrictions survive. Combined with G1g verified 12h14m Observation V5-only live uptime, 0 restarts, bounded memory, frozen five-minute journal and independent health audit PASS, and a fresh isolated V4 restart/V5 source epoch/Observation continuity test subset **39/39 PASS**, the **minimum G1 V5 Observation evidence safety platform is verified with disclosed limitations**. A real live WSS disconnect/reconnect was not witnessed in this window, and no full 24h soak was run (owner explicitly requested 12h instead). The holistic F0 cross-DB atomicity question is not silently closed.

**G2 additional source-integrity implementation (ISOLATED ONLY):** Branch `feature/v5-observation-g2-20261014` and standalone working tree `/home/ubuntu/nbot_v5_g2_audit_dev` now have a full-denominator audit with per-coin attrition and 24 pattern counts, bounded deterministic feature/source replay from 96 real recorded closed candles per selected coin with independent original source-receipt-time and SHA256 checks, and a new **offline-only** immutable raw market-universe/quote/time provenance witness. The latter is a prospective schema, NOT wired into the running observer and NOT a historical proof of the original top-50 ranking or executable bid-ask prices. All V5 live collector and Execution service files/processes remain untouched.

**G2 real pass/hold breakdown:** Read-only audit of live G1f SQLite returned candidate-data integrity `PASS`, zero violations, 159 consecutive five-minute manifests, exactly 15,900 candidate LONG+SHORT slots for 50 fixed coins (15,790 OBSERVED, 110 UNSCORABLE), six HOLD events, zero unexplained gaps between committed event manifests, and two transparently excluded initial setup/bootstrap slots. Bounded deterministic causal replay at twelve separate complete event times verified all **1,200/1,200** originally recorded 50-coin two-sided pattern/source records without looking ahead. Independent G2 unit tests **27/27 PASS** on Observation VPS; separate V4/V5 restart subset 39/39 PASS; GitHub CI **183/183 isolated V5 observation tests PASS** on commit `1a7bca9b2b9466d6dc6feb05b443c6a29f292084`, run https://github.com/samqju/Nbot/actions/runs/38517208457 . These are observation candidates, NOT matured future P&L/fees outcomes.

**Why G2 cannot yet be marked complete:** Current live G1f records DO NOT retain original point-in-time full Binance exchangeInfo+ticker/rank inputs/excluded symbols and DO NOT retain per-event quote/trade receipt snapshots and feed/source generation proofs. Complete at-event selector-eligibility and quotation as-of replay is therefore `UNVERIFIABLE` for historical G1f data. G2 witness code and synthetic tests have passed but future actual capture is required through a separately validated, bounded prospective collector, then an independent full audit. Old immutable data must not be rewritten or backfilled with today's rankings/prices. Do not infer any all-Binance population, executable bid/ask trade or outcome labels from top-50 observations.

**Exact stage disposition:** G1 minimum V5 observation evidence platform **PASS within explicitly limited 12-hour/frozen-cohort scope**; historical cross-database atomicity and actual WSS disconnect recovery NOT VERIFIED. G2 two-sided denominator and sampled deterministic pattern-source replay **PASS**, while full original G2 complete eligible-market and quote-source provenance **HOLD**. Continue G2 only: integrate/version the prospective as-of witness and independently validate it offline before any carefully scoped operational change, collect genuine future source proof, then independently check accepted-event coverage, hold/attrition and determinism. **Do not advance to G3/G4/G5/G6 or connect E6B** merely due to an integrity test PASS. No source branch merge or running system deployment has taken place.

**Change record — v2.8.3 / 2026-10-14:** Confirmed 10/10 V4 snapshot+restore SHA, genuine 12-hour V5 operational health and 39/39 targeted recovery regressions; built validated G2 population/causal replay and offline-only prospective source witness with 183/183 CI; preserved original G2 provenance HOLD and no-order authority. Isolated branch details: `docs/NBOT_V5_G1_G2_SOURCE_PROVENANCE_CHECKPOINT_2026-10-14.md`.


---

## 47. V2.8.4 — G2 original-snapshot and genuine two-window forward-source evidence accepted (2026-10-14)

**Owner authorization:** Progress exactly in original roadmap order and close G2 ONLY upon independent original source/ranking/quote and two-sided coverage evidence. G1 minimum Observation safety integrity previously passed in 12-hour owner-chosen scope. G2 remains a scientific candidate-data population and as-of source integrity gate, not a training, paper-trading or operational execution deployment gate.

**Independent new G2 feature implementation:** Isolated branch feature/v5-observation-g2-20261014 includes opt-in G1f runner+event source hook, immutable original exchangeInfo/24h turnover source cohort witness, immutable per-event 50-coin sampled bid/ask WSS receipts and trade/quote source-generation clocks before REST finality, a separate independent fail-closed original-cohort/every-event source verifier, complete LONG/SHORT population/attrition counters and 96-closed-bar causal candidate pattern replay. All operations paper- and real-order forbidden, no label generation, with source-grade explicitly LOCAL_WSS_REST_NOT_EXCHANGE_SIGNED and paper_fill_grade=UNVERIFIED. Code and tests remained in a separate G2 worktree; old running V5 service files were NOT updated.

**Real proof procedure and exact population:** Started one bounded, independently connected public-Binance observation-only G2 probe using a fresh private V5 G2 SQLite DB, leaving original live G1f service running. The preserved original snapshot contained 927 reported exchangeInfo rows and precisely 525 positive-24h-turnover, rankable, USDT-quoted USDT-margined TRADING perpetual markets. Versioned policy selected the original top 50 (BTC included), while the other **475 were visibly EXCLUDED and never claimed as evaluated**. Exact cohort digest 82176070c5454a174701d4e5b9e49396f070945db62cfd7372a9aac0ff9f7a82; original snapshot SHA256 8bf5dab15452f2f49770e56f71f2b1fa6fc1b27ace92aadde576707cc472797d.

**Two independent real five-minute windows:** Binance 2026-10-14 05:45 UTC and 05:50 UTC event-open candles. Each source audit observed 50/50 genuine WSS finality, 3 consecutive REST comparisons and valid BTC context, zero quarantined, zero per-coin health holds, zero reconnection attempts and zero trade gaps reported, **100/100 OBSERVED LONG+SHORT records per window** and 0 UNSCORABLE. The independent read-only source acceptance checker verified **2/2 fully source-qualified complete event manifests**, **200/200 original frozen candidate records**, **100/100 originally archived as-of local quote/trade/epoch witness rows**, correct original top50 ranking versus 475 excluded rankable assets, matching SHA/time/authority, no missing slot and **violations=[]**. Independent causal 96-historical-bar detector replay reproduced **200/200 candidate source/pattern records** with no future bars; quotes truthfully reported archived in this new DB. This is a bounded ORIGINAL research cohort observation proof, not a backfilled test of legacy G1f observations or 525-market selection intelligence.

**Closeout, preservation and safety:** Deliberately stopped the temporary G2 probe using SIGINT after both windows. Runner returned OBSERVATION_ONLY_RUN_COMPLETED, reason null, both WSS routes cleanly disconnected, peak RSS 61.33 MiB, bounded DB ~7.65 MiB with WAL; final immutable evidence /home/ubuntu/nbot_v5_g2_proof_20261014/g2_witnessed.sqlite has strict SQLite integrity_check=ok and post-close standalone SHA256 acc7dcb1e7de9c8a7f65041dffa1ca38a267d8bfa4c252d84e8500562995664f; private directory 0700, file 0600; preserve forever as frozen G2 evidence. The original old V5 collector stayed active/enabled PID1082 with zero unexpected restarts; legacy V4 remained inactive/disabled, original hourly health PASS, no Execution changes. GitHub Actions isolated V5 Observation source/test SHA 9b890098e1050a84de30d788ff32fbf6866b7b49 PASS **206/206** tests, https://github.com/samqju/Nbot/actions/runs/38519602049 . Separate VPS G2 replay+source acceptance tests 30/30 PASS, live fully sourced DB source audit PASS and direct causal replay PASS.

**Exact G2 exit and limits:** G2 **SCIENTIFIC FROZEN TOP-50 FULL-DENOMINATOR + PROSPECTIVE SOURCE EVIDENCE PASS** for the two expressly accepted live windows. The original V5-02 §10 exit permits restricting historical/market claims where archival information is incomplete; strict historical G1f records and rankable 475 unselected markets remain out of acceptance scope. DO NOT infer the old 16,000+ historical candidate rows have full original quote/ranking proof; their source grade stays unverified. No mature economic research outcomes, signed exchange-executable bid/ask, validated funding, P&L/edge, trained Champion/Challenger, two-paper-book activation or live-money authority. `research_ready=false`, `training_labels_created=0`, `order_authority=NONE` remain binding.

**Operational next-step separation:** The original long-running G1f collector has **NOT** been upgraded or connected to the newly passing G2 witness capture. Continuous future source-qualified observations require a separately validated, restorable collector cutover with matching hourly health monitor and retained old database (no attempt to forge/backfill past evidence). This is a future operational acceptance prerequisite to using prospective ongoing data for G4 outcome research, not evidence that G2 original scientific source gate failed. Follow original order: **G3 BTC/coin regime causal features OFFLINE NEXT**; defer G4/G5 learning and G6 models until required prospective data/label gates.

**Detailed evidence:** docs/NBOT_V5_G2_PROSPECTIVE_SOURCE_ACCEPTANCE_2026-10-14.md on independent feature/v5-observation-g2-20261014 branch.

**Change record — v2.8.4 / 2026-10-14:** 2/2 witnessed genuine market events, immutable cohort-selection census of 525 rankable / 50 included / 475 excluded, 200/200 source-pattern candidates, 100/100 per-coin quote witnesses, preserved SHA-verified source DB, 206/206 CI; accepted bounded G2 scientific proof, explicit production-rollout HOLD and no-order authority.


---

## 48. V2.8.5 — G3 BTC/coin regime frozen-clock feature PASS, with actual source-qualified replay and branch controls (2026-10-14)

**Owner instruction:** Develop V5-03/G3 in the original approved order; full authorization for safe Github/VPS/laptop engineering, while strictly keeping Observation, Execution and prior V5 prototype branches separate. No inference of live Binance financial-order authority.

**Verified strict source and branch ancestry, no accidental merges:** From actual Observation VPS git history, `feature/v5-observation-g3-20261014` descended **directly** from the verified `feature/v5-observation-g2-20261014` snapshot `af6d5a458eeca047c43d0360ce6a8fd3f76ec799` (exact merge-base same SHA), with `0 behind / 11 ahead` at the initial acceptance HEAD `d818bc173c04c4279a7f6a3dff52faff35209c99`. G3 development is a detached *separate* VPS worktree `/home/ubuntu/nbot_v5_g3_audit_dev`. The V5 clean-restart branch is still the authoritative roadmap and unchanged active G1f collector source; G2, G3 and Execution branches were not merged into it. `feature/v5-execution-foundation-20261014` is an entirely unrelated execution development workstream; `feature/v5-live-evidence-recovery` is a historical prototype excluded from the clean development path.

**V5-03 actual implementation:** The G3 feature contract `NBOT_V5_G3_BTC_COIN_CONTEXT_V1` emits a deterministic SHA256-identified, frozen-clock, observation-only BTC regime and 50-member coin-structure feature for an independently accepted G2 source event. Inputs are original, SHA256-proven 96 consecutive *closed* 5m candles per selected coin and originally captured local public-WSS quote/trade/source-epoch witnesses whose sampled-at clocks were recorded before finality audits. Exactly known `valid_from_ms` is original event commit; no using post-cutoff bars or fabricated zero returns. BTC regimes: SHOCK_UP/DOWN, TREND_UP/DOWN, RANGE, TRANSITION, UNKNOWN. Coin structures: BREAKOUT_UP/DOWN, TREND_UP/DOWN, COMPRESSION, RANGE, TRANSITION, UNKNOWN; confirmed swings require TWO successor bars that were already closed by that decision. Breadth is computed only across source-qualified **49 non-BTC altcoins**, minimum 80% qualified coverage, not double-counting BTC; directional coin-BTC relative momentum can classify LONG/SHORT independently when BTC is valid. Unavailable/stale BTC yields UNKNOWN and UNAVAILABLE for every BTC-conditioned result, never a false neutral/zero. Frozen confidence scores are **heuristics, NOT calibrated profit probabilities**. No G3 outcome labels, recommendations, paper orders or real orders.

**Acceptance in original roadmap order:** Original §10 V5-03 exit required (i) causal reproducibility at frozen clocks, (ii) explicit BTC stale/absent withheld state, (iii) source-path feature availability tests and (iv) deterministic regime classifications. All conditions tested: G3 **27/27 unit and frozen-source replay tests PASS on Observation VPS**; isolated full V5 Observation GitHub Actions **233/233 PASS** at code commit `516745b866d83fb1768b766a1e0572f5e4ffc5f4`, run https://github.com/samqju/Nbot/actions/runs/38521549149 . Tests include realistic upstream/downstream BTC shock and trend fixtures, BTC-relative positive/negative cases, future-data/swing-hindsight holds, low-breadth and stale/unsigned local quote limitations, deliberately altered SHA/witness and source clocks.

**Actual independently qualified live source replay:** Read-only G3 replayer required previous strict G2 source acceptance PASS and reread the unchanged preserved `/home/ubuntu/nbot_v5_g2_proof_20261014/g2_witnessed.sqlite`, SHA256 `acc7dcb1e7de9c8a7f65041dffa1ca38a267d8bfa4c252d84e8500562995664f` (identical to original G2 final checksum). The two original 2026-10-14 05:45 / 05:50 UTC real event windows produced **100/100 source-qualified coin-event context classifications**, no UNKNOWN, deterministic SHA identical across repeated pure calculations, no unverified time/receipt/window violations. BTC regime = TRANSITION in both events with heuristic score .4; altcoin-only breadth `-0.7959183673` and `-0.9183673469`. Source-qualified coin-event structures summed `BREAKOUT_DOWN=33`, `COMPRESSION=24`, `TREND_DOWN=30`, `TRANSITION=13`; separate hypothetical directional BTC-relative MATCH tags LONG=5/4, SHORT=40/43 (nontrades, unscored, potentially overlapping). **These are 100 coin-context records, NOT 100 returns or independent research trade outcomes.** No observable real BTC shock occurred in these two windows; shocked states were validated only synthetically, not via fabricated historical market claims.

**Operational independence reconfirmed:** Existing original Observation VPS `nbot-v5-observation-only.service` remained active/enabled original PID 1082, unexpected restarts zero, memory ~106MB against 200MiB limit. Original G1g real-time audit PASS; 169 original five-minute historical manifests, 16,790 OBSERVED + 110 UNSCORABLE legacy directional candidate records, SQLite quick_check=ok and all seven V4 services inactive. G3 tests made no writes to this running DB or frozen G2 proof. Execution VPS left idle; no model, virtual-trade outcome, Champion/Challenger or order authority created.

**Exact gate claim and handoff:** `G3_EXIT=PASS` **for the original frozen causal BTC/coin feature engineering and bounded source-qualified proof**, but this is **not deployment of a G3 production feature stream, not proof of statistical financial edge and not permission to advance any trading authority**. G2 source-grade *continuous production* rollout remains a separate outstanding operational prerequisite: the active original G1f collector is still the earlier non-witnessed G1f version; do not use its historical rows as if G2 original source receipts existed, and do not silently migrate its old DB. Before genuine G4 economically matured labels can be scored, require a separately tested reversible prospective G2 witness/G3 feature collection plan, complete at-event original quote/trade proof for each newly accepted event, and a G4 versioned exit/cost/censoring plan. Any unverified or missing source should produce abstain/HOLD, not guessed profits.

**Source documents:** `docs/NBOT_V5_G3_BTC_REGIME_COIN_STRUCTURE_CONTRACT_2026-10-14.md` and `docs/NBOT_V5_G3_ACCEPTANCE_2026-10-14.md` in `feature/v5-observation-g3-20261014`. The original clean branch contains this authoritative *summary* only; it intentionally does NOT merge G3 code or Execution code.

**Change record — v2.8.5 / 2026-10-14:** Isolated, directly descended G3 BTC regime/coin-structure source-clock design and acceptance PASS; 27/27 G3, 233/233 CI, immutable original G2 proof unchanged; preserved branch/isolation discipline and future continuous-source/economic-label HOLD.


---

## 49. V2.8.6 — Real integrated G1/G2/G3 Observation VPS deployment, end-to-end source/feature PASS, 24h soak PENDING (2026-10-14)

**OWNER CONTEXT AND EXACT LIMIT:** Owner requested real integrated deployment because earlier G1/G2/G3 tests were isolated and had not made original G1f observation service G2-source-witnessed or G3-aware. The original live collector was V5 G1f, **not V4**; V4 legacy units had already been disabled. User approved repository, Observation VPS and laptop changes. No live Binance orders, paper services, trading API credentials, model training or G6/E6B decisions were authorized or activated by this deployment.

**Git branch/side-effect separation:** New `feature/v5-observation-integrated-20261014` forked from the verified `feature/v5-observation-g3-20261014`, with Git-confirmed exact merge-base `fdca6980d1c778e2da8466b51631b31287740ff4` and `0 behind / 12 ahead` at the immutable pinned integrated release `1e7c090d05dc118b290c764d58c2944f56ad4b3b`. The GitHub CI run for that precise release https://github.com/samqju/Nbot/actions/runs/38523923669 passed **247/247** Python 3.12 tests. New detached VPS code dir `/home/ubuntu/nbot_v5_integrated_20261014` and NEW private G1/G2/G3 DB `/home/ubuntu/nbot_v5_integrated_data/g1g2g3.sqlite`. No code was merged into the original `v5-clean-restart-20261013` Observation collector or Execution branch. This roadmap file is the **only** artifact updated in the clean-restart branch.

**Preservation and reversible deploy:** Before operating on services, performed a genuine SQLite online backup of old running V5 G1f `g1f_observe.sqlite` to separate `g1f_pre_integrated_20261014.sqlite`, verified SQLite integrity `ok`, length **51,490,816 bytes** and SHA256 `c3a3d8f6aac1ff254f8ee3daaff3ce06e72f299cfac01c5ec305cca87ba0d03d`. Previous G1g pre-reboot snapshot and F: V4 forensic originals/isolated restore copies remain retained. New source unit `nbot-v5-g1g2g3-observation.service` and new timer `nbot-v5-integrated-health.timer` were installed/enabled without overwriting old unit files, with production Git SHA preflight, 200MiB memory cap, CPU/privilege/filesystem restrictions, bounded service restarts, frozen-cohort resume, immutable source/event/feature ledgers and an independent hourly read-only source/context auditor. No execution authority.

**Unexpected but bounded maintenance incident:** During rollout, Ubuntu `apt-daily-upgrade.service` coincided with explicit stop/start of both the older V5 service and the new integrated service around **06:45–06:47 UTC**; **the host did not reboot** (same boot ID `9bc008f6-eaa2-4ced-8a9d-c3f54f3b5a6e`). Old G1f service could not restart against a changed new 24-hour market rank, intentionally failing `G1F_COHORT_ROTATION_REQUIRES_REVIEW`, and was subsequently safely disabled along with its now obsolete hourly timer. Its original data and backup were not modified or removed. The new integrated service restarted, **reused original frozen witnessed top50 selection**, successfully reconnected public market and trade WSS feeds, and maintained a fixed Git SHA and immutable DB. After preserving logs, the old failed-unit flag was reset and the older unit is inactive/disabled. The new live service stable `ActiveEnterTimestamp` is **2026-10-14 06:46:04 UTC (=12:16:04 IST)**; do not count earlier partial service runtime toward a full 24-hour soak.

**Actual SOURCE-PROVENANCE G2 and causal G3 production EVIDENCE, not hypothetical tests:** New always-on systemd service persisted genuine 2026-10-14 **06:45 and 06:50 UTC** five-minute event opens, 50 frozen real Binance public Futures markets each (BTC included), full REST/WSS finality and immutable original quote/trade/source receipt proof. Independently reevaluated the original exchangeInfo/ticker snapshot: 927 reported rows, **525 eligible/rankable positive-turnover USDT perpetual markets, top 50 selected and 475 explicitly excluded from evaluation**. Cohort snapshot SHA `fd05727503afb8c146e603995302a05b9496188fac715b88f851c0994d49dfb3`. Read-only **G2_source_acceptance=PASS**, violations=[], 2 fully verified events, exactly **200/200** original LONG/SHORT candidate records and **100/100** event-time per-coin quote/trade/epoch witnesses, zero unscorable/quarantined/held intervals and zero silent missing five-minute slots.

**G3 production persisted, not merely replayed:** Original live process saved **2/2 immutable G3 context rows** with full 50-coin features, original approved BTC/altcoin as-of clocks and SHA. Independent read-only G3_frozen_replay=PASS: all **100 coin-event contexts** available and reproducible, two genuine BTC `RANGE` classifications (other shock/trend cases remain synthetically tested), BTC-excluded altcoin breadth `-0.4897959184` and `+0.4693877551`. Real systemd `nbot-v5-integrated-health.service` manually invoked as its protected oneshot and returned **Result=success, ExecMainStatus=0, audit=PASS, violations=[]**, 2 event manifests, 200 candidates, 100 witness rows, 2 G3 contexts; `NRestarts=0` post-maintenance, current ~67MiB memory versus 200MiB cap. Old G1f service and timer inactive/disabled; new integrated service and health timer active/enabled. V4 old boot enablers still disabled, Execution untouched, `order_authority=NONE`, `training_labels_created=0`, `research_ready=false`.

**HONEST GATE STATUS on 14 October:** (1) G1 historical forensic preservation and fail-closed tests previously passed with an explicitly **unproven cross-database atomicity limitation**. (2) G1 **new integrated 24-hour unattended soak is PENDING REAL ELAPSED TIME, NOT COMPLETE**. Earliest full 24h after stable start is **2026-10-15 06:46:04 UTC (12:16:04 IST)**, subject to no additional unexpected service restart, missing feeds, source gaps or resource failures. (3) **G2 in actual persistent service PASSED two consecutive original-source-qualified fully enumerated candidate windows.** (4) **G3 in actual persistent service PASSED two consecutive originally sourced persisted/regenerable BTC/coin contexts.** Those bounded live operational PASSes prove connected stage correctness, **not** 24h resiliency, future regime coverage, economic profit, virtual research labels, model training, 100-trade Champion contests or real exchange orders. Keep G4 economic-source and maturity planning after full upstream integrity verification; do not skip future gates.

**Unattended daytime review scheduled:** Thursday **15 October 2026 around 12:45 PM IST**, a 24h+ automatic review of the new actual service, journal, hourly health, G2 source witnesses and G3 time-locked contexts; remote SSH/ChatGPT inspection relies on laptop connection, while the server timer runs independently. If offline/unverified, the answer must report HOLD/UNVERIFIED, never pretend the gate passed. New live service is expected to run independently while laptop/ChatGPT are closed. Full deployment audit: `docs/NBOT_V5_G1_G3_INTEGRATED_PRODUCTION_DEPLOYMENT_2026-10-14.md` in the authoritative roadmap branch, with additional source/feature evidence from V5 G2 and G3 separate verified branches.

**Change record — v2.8.6 / 2026-10-14:** New pinned restorable integrated Observation service live, original older V5 safely retired after a detected Ubuntu package-upgrade restart incompatibility, 247/247 CI + 2/2 genuinely witnessed production G2/G3 windows and protected health timer PASS, **full fresh 24h G1 soak still pending**. No financial order authority.


---

## 50. V2.8.7 — Owner-directed simplification, 12h/24h soak distinction, no-loss handoff and nonblocking offline work (2026-10-14)

**Owner decision and non-negotiable intent.** The owner wants to stop accumulating confusing Observation VPS root directories, converge after acceptance on a clear single canonical `Nbot` Git codebase with `main` as the authoritative trunk, protect every cent of existing market evidence, preserve the full milestone-order engineering method across new chats, and avoid idle waiting when safe coding can proceed. This amendment is a DOCUMENTATION/GOVERNANCE change only to the roadmap branch `v5-clean-restart-20261013`, NOT a runtime, branch-merge, database, service, order-permission or retention mutation.

### 50.1 Observed current state (not inferred future progress)

At ~2026-10-14 07:17 UTC, connected Sameer-Laptop -> saved PuTTY `Observation-VPS` -> VPS `base`, verified:

- The actually running service is `nbot-v5-g1g2g3-observation.service`, active and enabled, and independent `nbot-v5-integrated-health.timer` active/enabled; old `nbot-v5-observation-only.service` inactive/disabled.
- Pinned integrated release is `/home/ubuntu/nbot_v5_integrated_20261014` on `feature/v5-observation-integrated-20261014`; clean Git HEAD and approved_code_sha both `1e7c090d05dc118b290c764d58c2944f56ad4b3b`; 247/247 historical CI PASS on release SHA.
- Integrated DB `/home/ubuntu/nbot_v5_integrated_data/g1g2g3.sqlite` still ACTIVE. Stable service start `2026-10-14 06:46:04 UTC`, MainPID 11327, `NRestarts=0`, ~67 MiB RSS vs 200 MiB limit. Recent live WSS heartbeats showed both public streams connected, no reported trade gaps or reconnect attempts.
- Protected health systemd oneshot manually rerun and PASS (`ExecMainStatus=0`, `violations=[]`): **6 accepted consecutive five-minute events, 600 full LONG+SHORT candidate records, 300 original G2 per-coin quote/trade source witness rows, 6 G3 contexts, 50 selected markets, 0 holds**, `research_ready=false`, `training_labels_created=0`, `recommendation_authority=NONE`, `order_authority=NONE`. Historical independent original G2/G3 proof database and branches remain distinct and intact. These records are NOT research-matured financial outcomes.
- `/home/ubuntu/Nbot` exists on Git `main` (262 MiB), but it is NOT the code currently executing the integrated service. Source branch `v5-clean-restart-20261013` is authoritative for the original roadmap/G1f; integrated/G2/G3 features were isolated in their own ancestry; independent `feature/v5-execution-foundation-20261014` not merged. No evidence supports blindly replacing the running code with `main` today.

### 50.2 The 12-hour pass was not canceled; the 24-hour gate is for a different release

- Previously accepted 12-hour G1g/G1f soak established a bounded operational checkpoint for the **old G1-only V5 observer**, with documented old-source and historical cross-DB integrity limits. That evidence remains valid for its stated scope and does NOT restart when new G2/G3 code is deployed.
- On October 14 a new **integrated G1+G2+G3** systemd collector and provenance/context database were first made permanent. During package maintenance there was a stop/start; its post-maintenance stable ActiveEnterTimestamp is **06:46:04 UTC / 12:16:04 PM IST, October 14**. A distinct original 24-hour *integrated-production reliability gate* starts there because the system, source-witness and persistence paths changed. The earliest 24 hours are **06:46:04 UTC Oct 15 / 12:16:04 PM IST Oct 15**, subject to proper continuity proofs, independent G2/G3 replay and resource/audit health. Formal review was scheduled for ~12:45 PM IST Oct 15; offline laptop results must be `UNVERIFIED/HOLD` if not reachable.
- **Never impose a second redundant 24-hour clock merely because a new chat starts, a research branch advances, or a read-only audit runs.** Reset/re-evaluate the relevant gate only upon an actual restart, code/runtime/source boundary change, or an acceptance-breaking fault; document the new start and causal reason. Count `journalctl` systemd service transitions, not just NRestarts.
- **Do not block all work during the soak.** Safely proceed with G4 scientific specification, failure-mode fixtures, research-grade economic cost/funding/slippage/quote evidence requirements, counterfactual horizons and missing/censored outcome design, mock/offline tests, historic branch ancestry audit and proposed directory simplification. Do not touch the running pinned collector's code, DB, unit, timer or host settings merely to keep busy. Do NOT activate continuous G4 label ingestion, mutate current evidence, enable research-ready, train Champion, start Execution or submit orders until full G1/G2/G3 operational acceptance and an independently frozen G4 contract. Original G4+ milestone acceptance order remains binding.

### 50.3 Directory inventory (actual Observation VPS; October 14)

| Existing `/home/ubuntu` path | Actual role | Planned safe disposition |
|---|---|---|
| `Nbot` | Git checkout `main`; historical larger working tree | Future sole canonical editable code repository, **after reviewed history integration**, never an in-place runtime replacement mid-soak |
| `nbot_v5_integrated_20261014` | Active immutable pinned G1/G2/G3 code worktree | Keep untouched until explicit reviewed immutable-release transition; then archive/remove worktree after verified cutover |
| `nbot_v5_integrated_data` | Active SQLite + pin | Retain and back up; later relocate through tested migration outside Git, never empty during soak |
| `nbot_v5_sandbox` | Retired G1f observer worktree | Archive/remove after proof checks, not currently an automatic rollback |
| `nbot_v5_data` | Legacy G1f SQLite + tested online backup | Archive with hashes/restore proof; do not convert historical rows to G2-qualified evidence |
| `nbot_v5_g2_audit_dev` | Independent G2 Git worktree | Remove using verified Git worktree cleanup only once ancestry merged and proofs retained |
| `nbot_v5_g2_proof_20261014` | Original immutable bounded source-witness proof database | Preserve, checksum and archive, do not mutate |
| `nbot_v5_g3_audit_dev` | Independent G3 Git worktree | Remove after reviewed integration/proof retention |
| `nbot_v5_venv` | Runtime Python environment | Consolidate only via reproducible pinned dependencies and verified new runtime |
| `nbot-backups` | Host backup copies | Retain until restore/off-host copy and retention approval |
| `nbot_f0_snapshot_staging` | Historical F0 forensic/recovery snapshots | Keep immutable, audited, off-host retained before owner-reviewed cleanup |
| `nbot-release-records` | Deployment and rollback records | Keep as small canonical audit ledger |

**Desired future simplicity:** one canonical editable `/home/ubuntu/Nbot` Git checkout on `main`, short-lived feature branches merged by PR/verified commits, one independent immutable *production release path* (e.g. `/srv/nbot/current` pointing to `/srv/nbot/releases/<SHA>`), one private persistent dataset root (e.g. `/var/lib/nbot` with observation and later paper subdirectories), and one managed backup/archive root (e.g. `/srv/nbot/archive`). The stable release may be a separate directory from `Nbot` for safety; 'only Nbot' must NOT mean putting mutable SQLite, API keys or a running code checkout in a Git source tree. These example destination paths are a PLAN, not actual deployed paths.

**Safe consolidation acceptance and order:** (1) freeze full directory, service, timer, path, Git worktree/ref/merge-base and SHA inventory and offline restore plan; (2) prove complete V5 code ancestry with no Execution/V4 prototype contamination; (3) use PR/review/CI to bring accepted integrated V5 into `main` on a stable baseline without force updates, keep pinned running release untouched; (4) after the 24h operating gate and appropriate owner-acknowledged production cutover, create and verify versioned immutable release and service rollback; (5) back up/verify SQLite online plus WAL, restore offline and cross-check source-event SHA/continuity, then deliberately migrate state with one service cutover and observation; (6) only after strong backups/off-host retention, signed manifest and owner approval, retire obsolete extra worktrees/files in small reversible batches. NEVER delete just to make a directory listing look clean. Prior G1f failed an automatic restart from cohort rotation; it is not a proved failover.

### 50.4 SQLite reset policy and economic-evidence separation

**No blanket SQLite deletion.** Market-event DBs contain source clocks, original quote/rank witnesses, event history, BTC context and future learning provenance; old F0/G1/G2/G3 datasets are scientific and recovery assets. Keep observation event streams and frozen selected/unselected denominator records intact, with ID/version lineage. When separately authorizing a FINAL production/paper experiment launch, a fresh versioned *trading or portfolio ledger* with zero starting paper/live positions may be correct, alongside preserved read-only prior evidence and recorded cutover clocks; create a new DB only after backup, integrity, replay/restore proofs and an explicit release-boundary definition. Research counterfactual outcomes, forward paper fills and eventual real exchange fills must never be interchanged. There is no justification for zeroing the observation data just because G10 is complete.

### 50.5 Standing architecture, gates and branch governance

- Preserve two VPS separation: Observation/Learning collects top50 BTC/alt/24-pattern evidence, original quote/trade timestamps and then versioned mature virtual outcomes/offline ML. Execution runs independent gated Champion and Challenger **paper** books; much later any Champion real-order book requires separate independent authorization and safety. Candidate slots and coin contexts are NOT economic trade outcomes.
- G4 economic source/label protocol -> G5 baseline/scientific viability -> G6 calibrated challengers -> G7 guarded paper decisions -> G8 shadow/paper forward observation -> G9 reviewed outcomes/promotion -> G10 improvements, strictly original documented order; 2,000 **qualified matured observations** is proposed learning threshold, not 2,000 raw slots; compare Champion/Challenger at fair paired 100-trade windows with after-cost no-trade/0R control and risk checks. Missing/noisy data => HOLD/ABSTAIN.
- Keep `feature/v5-observation-g2-20261014`, `feature/v5-observation-g3-20261014`, `feature/v5-observation-integrated-20261014` distinct until audited, then converge via reviewed integration into `main`. Keep `feature/v5-execution-foundation-20261014` independent. Old `feature/v5-live-evidence-recovery` is historical, not trusted new V5 source. `v5-clean-restart-20261013` remains the governance branch until controlled integration is done; do not conflate with release Git HEAD.
- Existing owner standing permissions permit safe inspection, testing, repository/documentation edits and isolated development; seek permission for irreversible deletion, production-impacting cutovers, material monetary risk and any real-order enablement. Preserve active collector until its independent acceptance gate is earned. No fabricated fills, win rates, label maturity or deterministic 'probabilities' from heuristic G3 confidences.

### 50.6 Durable chat transition references

Detailed reviewed release history: `docs/NBOT_V5_G1_G3_INTEGRATED_PRODUCTION_DEPLOYMENT_2026-10-14.md` (same roadmap branch). Fully standalone and latest user-intent handoff: **`docs/NBOT_V5_NEXT_CHAT_CONTINUITY_AND_CONSOLIDATION_2026-10-14.md`**. Both must be read with THIS roadmap by the new chat, then fresh read-only Observation VPS state verified; never assume a scheduled task or timestamp remains correct after a future incident. The scheduled 24h check is active on Oct 15 ~12:45 IST, subject to available remote access.

**Change record — v2.8.7 / 2026-10-14:** Observed 6-event integrated health PASS and verified clean pinned release, clarified G1 old 12h versus new 24h gate and prohibited arbitrary repeat soaks, authorized concurrent *offline* G4 specification/tests during soak without premature operational acceptance, recorded complete workspace/data/backup roles, formalized later reviewed Git `main` consolidation and archive-only SQLite policy, and created a comprehensive new-chat GitHub handoff. **No running services, source refs or databases changed by this amendment.**


## 51. V2.8.8 — Independent post-handoff verification, reversible consolidation audit, G4 offline-only mocked acceptance (2026-10-14)

**Source of exact evidence, checksums, Git ancestry and proposed rollback:** `docs/NBOT_V5_POST_HANDOFF_AUDIT_CONSOLIDATION_G4_2026-10-14.md` on THIS governance branch. This section is supplemental to and does not supersede §§10,17–25,45–50 or the pending 24h integrated G1 gate.

1. **Verified live at 2026-10-14 07:32:18 UTC:** connected to real `ubuntu@base` via Sameer-Laptop saved PuTTY session; active `nbot-v5-g1g2g3-observation.service` PID 11327, clean detached production SHA `1e7c090d05dc118b290c764d58c2944f56ad4b3b` matching approved pin; `ActiveEnterTimestamp=2026-10-14 06:46:04 UTC`, `NRestarts=0`, 71,102,464 bytes memory of 200 MiB max. Direct read-only independent integrated health **PASS with zero violations**: 9 accepted 5m events, 900 full LONG/SHORT candidate rows, 450 original G2 witness rows, 9 G3 contexts, 50 frozen markets, no explicit holds, zero research labels and zero order/recommendation authority. Production SQLite read-only `PRAGMA quick_check` = ok. Old G1f frozen backup SHA256 independently still matches `c3a3d8f6aac1ff254f8ee3daaff3ce06e72f299cfac01c5ec305cca87ba0d03d`. Earlier 6-event handoff remains a true EARLIER snapshot; neither number implies any matured virtual trade.
2. **Gates:** original prior 12h G1f evidence PASS within scope; newer integrated G1 24h **PENDING until Oct 15 06:46:04 UTC / 12:16:04 IST earliest**, with independent ~12:45 IST review and no ungrounded pass/reset. G2/G3 initial source/technical PASS within bounded live evidence, no after-cost performance claim. G4 operational research labels NOT STARTED/NOT ACCEPTED. G5–G10 locked in original order.
3. **Git auditable constraints:** current remote GitHub `main` `d497e961e2891c43669d64f2a16d210011d703a4`, whereas VPS `/home/ubuntu/Nbot` local main is stale `b1a3c4a8d2a82c994669df7adb0d345e0415ffbf`. `main...integrated` diverges by 186/45 commits (merge base `b1a3c4a...`); `governance...integrated` diverges, with 8 governance-only and 58 integrated-only commits at audit cutoff. G2→G3→integrated production is linear (12 + 12 commits). The active pinned production checkout, G2 and G3 audit checkouts are linked worktrees whose git-common-dir is `/home/ubuntu/nbot_v5_sandbox/.git`; **deleting retired G1f sandbox before a release-metadata migration may break production.** No Git merges, code or systemd cutovers executed.
4. **Consolidation plan, not cutover:** classify 12 folders including F0/G1f/G2 original proof and all backup archives; independently verify Git refs/merge-bases and code/DB manifests, reconcile `main` via reviewed CI-backed non-force integration excluding V4 prototype and isolated Execution work, then only after operational gate and approval deploy self-contained immutable release under a versioned `/srv/nbot/releases/<sha>`, one mutable source `/home/ubuntu/Nbot`, private `/var/lib/nbot` data, and managed `/srv/nbot/archive`. Backup live SQLite ONLINE with WAL-aware API and independently verify offline restore/source continuity before ANY service/data migration. All existing files retained; deletions owner-gated. Existing disk is only 7% used.
5. **G4 safe offline step DONE, NOT G4 scientific PASS:** new temporary `feature/v5-g4-offline-contract-20261014` descends directly from the pinned integrated SHA; frozen 24-pattern/price/quote/funding/label specification, pure source/time `PENDING/HOLD/REPLAY_READY` preflight and 21 mock tests (no outcome calculation, service, DB, network, trade authority). Official GitHub Actions `268/268 PASS` https://github.com/samqju/Nbot/actions/runs/38529672257; **draft, unmerged** https://github.com/samqju/Nbot/pull/39. No new VPS directory created; no operative G4 labeling permitted before evidence gates.
6. **Next in order:** allow integrated collector and existing timer to continue; at >=24h independently verify service/journal/DB/source/G3 across entire window; write exact GO/HOLD. Finish G4 original price-path and executable source/cost methodology only after prerequisites, then G5 scientific no-trade/after-cost baseline, qualified ~2,000 matured observations if justified, G6 model gate, G7–G10 guarded downstream sequence. `main` consolidation and immutable release are distinct, reviewable actions, not silent overwrites of the live runner.

**Change record v2.8.8:** durable GitHub post-handoff audit, revised checkpoint, off-path G4 pure mocked tests and 268-test CI, and explicit dependency of production worktrees on retired G1f Git metadata. The live integrated collector and historical evidence remain unchanged.


## 52. V2.8.9 — G4 owner-authorized continuation: offline original-source binding and archive-integrity tests (2026-10-14)

The owner authorized full G4 engineering on 2026-10-14. This is permission to progress the milestone in original order, **not scientific evidence that existing source/quote/exit grades support real G4 economic labels, nor a waiver of the distinct integrated G1 24-hour operational gate.**

**Unmerged G4 engineering evidence:** reviewed G4 branch `feature/v5-g4-offline-contract-20261014`, base pinned integrated production SHA `1e7c090d05dc118b290c764d58c2944f56ad4b3b`, draft PR https://github.com/samqju/Nbot/pull/39; new `nbot/v5/g4_source_binding.py` and synthetic `tests/test_v5_g4_source_binding.py`, new `tests/test_v5_g4_archive_import.py` exercising original archive importer and trade-ID/time/byte integrity. Official GitHub Actions https://github.com/samqju/Nbot/actions/runs/38535274905: **367/367 tests PASS**. These are synthetic/contract tests only; none uses live G4 virtual outcomes, enables a model, or routes an Execution order. Latest G4 spec explanation in `docs/NBOT_V5_G4_OFFLINE_CONTRACT_2026-10-14.md`, §9 on that same G4 branch.

**Actual separately checked collector during this engineering:** observation VPS `base`, 2026-10-14 08:22:11 UTC, independent read-only `g3_prod_health` reported PASS with 19 five-minute accepted events, 1,900 two-sided candidate records, 950 original G2 source witness rows, 19 G3 contexts, zero explicit holds/restarts/violations, no labels/trade authority. Same MainPID `11327`, unchanged original post-maintenance ActiveEnterTimestamp 06:46:04 UTC Oct 14. This fresh checkpoint is evidence at the inspection time only; first integrated 24h ends no earlier than 2026-10-15 06:46:04 UTC, followed by actual independent continuity/replay review.

**Critical genuine-economics limitation discovered from G1/G2/G3 source schemas:** the production database preserves closed candles, original per-event quote/trade receipts and G3 market context. It does **not** preserve a continuous original after-decision aggTrade path or executable bid/ask quote at arbitrary intrahorizon stop/target exits. Therefore 19 events × 100 directional candidates = 1,900 *candidate observations*, not even one proven matured economic outcome. A frozen prospective G4 research policy, independently authenticated original price path, exit-time quote and fee/slippage/funding source coverage, realistic net-R uncertainty, idempotent after-cost outcome/censoring proof and verified restoration in a separate immutable offline G4 dataset are still required. Historical price replay `PATH_ONLY` cannot masquerade as quote-constrained SCORED grade. Original Binance ZIP bytes checked against caller-supplied `.CHECKSUM` alone lack independently authenticated acquisition/custody; do not set `original_archive_verified=True` from that relation alone. Research training gate remains **LOCKED**.

**Stage truth:** G1 historical 12h PASS within original scope; G1 *new integrated* 24h **PENDING**; G2/G3 initial original-source operational/technical PASS within bounded evidence; G4 **OFFLINE ENGINEERING PASS / OPERATIONAL SCIENTIFIC HOLD**, no actual matured verified after-cost labels; G5+ not started. Next: complete independent Oct 15 G1 review, then approve isolated prospective G4 original path/quote-cost capture (without replacing live DB), bind authentic sources to predeclared policies, independently replay and audit risk/cost/attrition/zero-trade, and only issue G4 GO when all acceptance criteria are genuinely met. No production source checkout, systemd, SQLite, backed-up F0/G1f/G2 proof, Execution VPS, or historical Git branches changed by this offline work.

**Change record v2.8.9:** Extend documentation of G4 source binding and archive integrity tests, verified 367-test CI, operational evidence incompleteness and specific next gate, preserving the accepted integrated release and original G0–G10 order.


**Second independent actual production verification, Oct 14 at 08:32:15 UTC:** read-only CLI `nbot.v5.g2_source_acceptance --min-events 2` on original production DB returned **PASS** on all **21** contiguous/source-verified events, 2,100 candidate rows, 1,050 original G2 quote/trade witnesses, **zero missing five-minute slots/source holds/violations**. Original ranked cohort witness still SHA `fd05727503afb8c146e603995302a05b9496188fac715b88f851c0994d49dfb3`, 50 selected out of 525 rankable eligible, 475 explicitly excluded. Separate read-only `nbot.v5.g3_frozen_replay --events 2` returned **PASS** on two latest original events, each 50 available coin contexts, exact deterministic G3 feature digests, zero UNKNOWN, BTC labeled TRANSITION in these two events (not a profit prediction). Direct `g3_prod_health` then returned **PASS**, 21 G3 context rows, 0 restarts, 0 labels, no order/recommendation authority. These bounded independent replays strengthen *initial G2/G3 source and structure evidence* but do NOT close integrated G1 24h or operational G4.


## 53. V2.8.10 — Owner-authorized real Binance market-source pilot, original continuity HOLD and modern WSS contract (2026-10-14)

**Durable source report:** `docs/NBOT_V5_G4_REAL_BINANCE_SOURCE_ACQUISITION_PILOT_2026-10-14.md` on the isolated G4 branch `feature/v5-g4-offline-contract-20261014`. This supplements §§10,17–25,45–52 and does not override the integrated G1 24-hour or G4 scientific GO/HOLD gates.

**Genuine pilot safely completed off-production:** On real Observation VPS `base`, using public TLS-verified HTTP GET only, original Binance USD-M QNTUSDT daily aggTrades ZIP for 2026-10-12 and its original `.CHECKSUM` were captured into the EXISTING private `/home/ubuntu/nbot-backups/g4-source-pilot-20261014/` backup hierarchy. TLS certificate validation succeeded, server headers and raw bytes retained, `sha256sum -c` returned OK. ZIP SHA256 `a6b241b6bf911d9d58776ccd51850c5cd56b9acf0183ac51a2e3ae2ece442f7c`; checksum SHA256 `5e4862c46770e0e132b2b07378a3612f023af8776f1c8ddd55c3980fdf6f863d`. Python stdlib ZIP CRC PASS; full archive parsed **278,165** actual market aggregate-trade data rows (16,655,778 uncompressed CSV bytes); aggTrade IDs strictly continuous from 99,853,796 to 100,131,960; original timestamps 2026-10-12 00:00:00.158–23:59:55.855 UTC. The original underlying trade-ID sequence has **158 single-ID holes** (158 missing individual IDs), despite continuous agg IDs. Per-source gaps are preserved explicitly: reason `HOLD_UNDERLYING_TRADE_ID_GAPS`; no network packet-loss cause inferred without further corroboration (Binance public aggregate trades exclude specified non-market executions). No history was deleted or fabricated, and no historical labels were created. Original ZIP full-capture SHA/byte evidence stays archived as research/forensic grade, not executed-price proof. Original archive importer quality fix preserves all rows, records each hole in its source manifest and keeps downstream strict path replay fail-closed. Validation-manifest file SHA256 `4fbb55f11f529aab5b542317b48ef74b63bd52732f548390b90e52ea246f792c`.

**Additional original public point samples captured at 08:49:32–34 UTC:** Binance USD-M current QNTUSDT bookTicker SHA `801be27857243df99aadd51217ccb838a21f015095a6127eeeb73654c8635d77`, Binance original fundingRate history (five samples) SHA `a4b442763dc5b479aaf908df8f64bde4232118a8a6cd89385ba795bf04e183ee`, and ten recent aggTrades SHA `3ce5c3f99a2828965d8178227ab161c23d469d771f82e38bb95117cb79104404`. All have separately retained raw bodies, HTTP headers and receipt clock files in the same already-managed private backup root; **none** is a prior decision-time/executable exit price, user account fee statement, order or genuine paper/live fill. This confirms actual public source access, not full cross-event quote/funding coverage.

**Additional G4 offline source engineering:** `g4_https_capture.py` constructs only bounded, allowlisted real HTTPS public read endpoints (archive, check, book ticker, funding and aggTrades), SHA+UTC receipts, exact response URL/host checks, 429/timeout/future-clock/oversize fail-closed, and no keys/order authority. `g4_forward_stream_contract.py` freezes the 2026 Binance USD-M routing split: high-frequency `<symbol>@bookTicker` on `wss://fstream.binance.com/public`, regular `<symbol>@aggTrade` on `wss://fstream.binance.com/market`; its quote, original trade-ID, epoch, receipt clock, symbol, source st=1 and no-fill constraints are synthetic-tested, **not deployed as a WSS acquisition service**. `g4_archive_import.py` now checks complete UTC day and valid original Decimal prices/qty while reporting true underlying gap quality; `tools/v5_g4_archive_diagnose.py` is an offline bounded forensic tool. These are appended to existing G4 pattern/price/cost/immutable ledger components and can be reviewed in still-draft unmerged PR #39.

**Independent CI:** https://github.com/samqju/Nbot/actions/runs/38538667595 **413/413 tests PASS**, including 20 HTTPS acquisition receipt and 22 modern forward WSS stream-contract mocks beyond earlier 367; original archive real-pilot evidence is separately documented and not counted as 413 empirical outcomes. Early red fixture CI runs were diagnosed and corrected before the green suite.

**Current scientific stage:** G1 old 12h PASS, **new integrated G1 24h PENDING** to earliest Oct 15 06:46:04 UTC; G2/G3 initial/source-replay PASS with bounded actual record coverage; G4 market-source acquisition **REAL PILOT PASS within its bytes**, **full 50-market continuous prospective source/exit quote/economic research source grade HOLD**, no research labeler deployed, 0 genuinely verified matured after-cost research outcomes, 0 Execution paper fills, no training, model or real trading permission. The source test pilot created **no** active daemon, G1 source changes, SQLite writes, released worktree, service restart, or new permanent production directory. At last observation 2026-10-14 08:50:55 UTC, integrated PID `11327`, NRestarts=0, original ActiveEnterTimestamp unchanged.

**Next mandatory dependencies (cannot be truthfully completed on Oct 14):** independently accept entire new integrated G1 24-hour soak on Oct 15; predeclare versioned forward research policy before future candidate/exit observations; review CPU/network/disk per 50-market independent public/market WSS feeds and source-epoch/gap WAL-aware evidence ledger, then install **only as an independently approved, resource-bounded isolated collector after gate**, preserving G1/G2/G3 service. Gather genuinely continuous future trade/quote/funding/fee witnesses and test restore/rollover, after-cost original replay, censorship, complete denom and independent data quality. Only then reviewed G4 scientific GO/HOLD, and only after that G5–G10 in original order. A real pilot snapshot or 413 mocked tests alone is not a matured virtual trade.

**Change record v2.8.10:** protected source capture, empirically discovered 158 holes and explicit science hold, 413-test CI, modern 2026 WSS architecture, no-loss backups and original stage continuity. No production-impacting cutover or financial authority.
