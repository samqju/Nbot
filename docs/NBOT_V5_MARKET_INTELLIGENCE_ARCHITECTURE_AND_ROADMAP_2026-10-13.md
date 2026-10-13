# NBOT V5 — Market Intelligence, Strategy Alignment and Learning Roadmap

**Document version:** 1.6  
**Date:** 2026-10-13 (IST)  
**Owner:** NBOT project owner  
**Repository:** samqju/Nbot  
**Publication:** New document on GitHub main; a separate local copy in Downloads root  
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
