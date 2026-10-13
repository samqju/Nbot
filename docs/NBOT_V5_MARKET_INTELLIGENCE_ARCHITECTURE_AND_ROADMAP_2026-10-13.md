# NBOT V5 — Market Intelligence, Strategy Alignment and Learning Roadmap

**Document version:** 1.0  
**Date:** 2026-10-13 (IST)  
**Owner:** NBOT project owner  
**Repository:** samqju/Nbot  
**Publication:** New document on GitHub main; a separate local copy in Downloads root  
**Forensic reference:** V4 source at commit b1a3c4a8d2a82c994669df7adb0d345e0415ffbf  
**Status:** **V5 ARCHITECTURE PROPOSED / DESIGN WORK AUTHORIZED; implementation, migration, services, trading and deployment NOT authorized by this document.**  
**Related governance:** Existing V4-R2 F0 roadmap controls evidence preservation and changes to running systems. This V5 document is the architecture-design successor, **not** an automatic amendment to F0 operations.

> **Project north star:** Understand BTC and broader market conditions; classify each coin's latest price action and market structure; detect applicable strategies; learn whether a given strategy and LONG/SHORT direction works under those conditions; evaluate after-cost return and uncertainty; **trade selectively or abstain**. Filling a trading quota is never an objective.

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

**No real orders in V5 roadmap phases.** A future execution proposal requires a new explicit approval scope, full security/operational review and independent evidence.

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
