# NBOT V7 — Strategy-Aware Whole-Market Universe and Label Contract (Design Refinement)

**Date:** 2026-10-20 IST  
**Status:** **Owner-originated architecture refinement, documented for review**. The user's stated design direction is captured here. This is a **versioned proposal**, not a silent overwrite of the frozen founding roadmap or acceptance of new numerical gates.  
**Scope:** Research design and documentation; no code, data downloads, VPS, paper/live trading or model training authorized by this file.  
**Context:** [Frozen roadmap](V7_ROADMAP.md), [G0 audit](V7_G0_LEGACY_AUDIT_2026-10-20.md), [numeric gate proposal](V7_NUMERIC_GATE_PROPOSAL.md), [handover](V7_CHAT_HANDOVER.md).

## 1. Owner's correction: quality of labels and entry ranking comes FIRST

1. **Candle data alone is not an intelligence dataset.** Do not accumulate endless unindexed 5m/1m OHLCV files without explicit as-of features, strategy/opportunity records, follow-up outcome labels, data-source proof, and a bounded retention plan.
2. **V3 replay and its outcome database need richer labels**, including trade-direction-adjusted MFE and MAE, times to excursions, BTC market/price status and regime, relative coin performance and trade/portfolio/cost context. Do not let future BTC state or MFE/MAE leak into entry-time model features.
3. **V4 LightGBM groupwise ranker is priority architecture**, adapted to evaluate strategy-specific opportunities across hundreds of point-in-time eligible Binance USDT-M perpetual contracts. It ranks expected *future net opportunity*, not simply 20 coins by current volume and volatility.
4. **V6 strategy families must feed the universal selector**, not sit downstream of a liquidity-only preselected watchlist. At a decision time, scan potentially ~150 coins (actual count variable), evaluate ~10 strategy families for each coin, and rank the most promising prospective trading setups; select up to 20 coins for detailed follow-up based on predicted after-cost opportunity quality.
5. **Selection quality has not been proven**. The entire challenge is demonstrating that the 20-of-N model beats safe, simple universe selectors and does not miss the actual best opportunities.

## 2. Correct causal order and data budget

### Research preparation (historical)

- Enumerate every historically eligible and traceable USDT-settled perpetual; records with unknown historical listing/tradability must be explicitly flagged or excluded from any certified historical test.
- Collect a **bounded, reproducible broad-market history** (minimum OHLCV/volume and metadata needed to compute features and independent proxy trade paths, plus verified funding/mark where available). Source raw data has value for replay and debugging, but bare files are not an acceptable research output.
- For **ALL qualifying historical strategy signals** in the broad market, compute a basic **conditional future outcome label** under a frozen policy, including adverse-first rules for OHLC ambiguity and explicit missing-cost/liquidity flags. This creates training signal beyond the 20 chosen markets; do not train the initial 20-of-N ranker using only its own past selected winners.
- For the 20 selected and an **explicit independently sampled out-of-universe control cohort**, compute **higher-resolution / more credible** path labels as data allows (1m, trade/mark/funding, measured spreads/depth when historically available). The out-of-universe sample records its draw method and inclusion probability, to diagnose selection bias.
- Split light coarse labels and precise verified labels into separate authority tiers. Never silently merge an imprecise historical proxy and verified fill/outcome into one claimed true label.
- Train ranker on **matured labels only**, with prediction time before outcomes and chronological embargo plus purging across overlapping horizons; no blind holdout leakage.
- Define broad-market data storage, compression/partitioning (e.g. Parquet), hash manifests, lossless source references, bounded retention, validation, and cache cleanup. **Do not discard irreplaceable raw data before reproducibility is guaranteed**. Don't duplicate market candles for each strategy.

### Real-time decision flow (prospective)

1. **Broad pass**: cheap point-in-time exchange eligibility, liquidity, volume/cost sanity, freshness and minimum data-quality gates; all eligible coins get lightweight as-of features. This pass is *not* a profitability ranking.
2. **All-market strategy overlay**: calculate **10–15 distinct strategies'** potential LONG, SHORT or NO SIGNAL on every sufficiently ready broad-market coin, using features that existed at t. There may be fewer or more than the illustrative 1,500 opportunities: never force one signal per coin/strategy.
3. **AI cross-sectional ranking** (highest priority): using the V4 `lambdarank` foundation plus V3/V5.1 causal/source controls, rank candidate signals by *calibrated expected after-cost utility and downside*; either no attractive candidate, or aggregate by coin into a market opportunity score.
4. **Top-20 universe selection**: choose up to 20 distinct coins by evidence-based estimated opportunity quality, subject to readiness, BTC/market context, diversification and sensible hysteresis/turnover. Selection review cadence is **provisionally every 8h**; no future information and no forced 20. Save excluded coins and scores.
5. **Detailed follow-up**: shadow simulate **every valid entry among these 20** (and sampled out-of-universe control signals) with reproducible paths and a frozen exit policy.
6. **Capital-allocated trade ranking**: at each executable decision moment (initially 5m completed candle), compare eligible simultaneous entry candidates and the **NO TRADE** alternative; select at most one position under actual wallet/margin/slot exposure.
7. **Continuing learning**: preserve rejected candidates and their matured conditional outcomes without pretending every overlapping virtual entry could have been opened in one wallet. Train separate challengers on known-before-fit evidence; promote only after new unseen matched economic evidence.

### Two distinct learned target definitions (avoid confusing them)

**Universe selector / 8h capacity decision:** Predict, using only data at universe review t, the *risk-adjusted net quality/availability of eligible trading opportunities over a predefined **future** watch horizon* for each coin, including the probability there will be no valid setup. This target MUST be computed later for historical training, never read at decision time. Selecting the top 20 does **not** imply opening 20 positions.

**Entry/portfolio ranker / 5m decision:** Given **currently valid entry signals** and present capital availability, estimate the expected net payoff, tail risk and time-at-capital under the exact frozen policy and costs; select one or NO TRADE. A coin can be in the top-20 universe without having a current valid entry.

A **shared base representation / LightGBM family** is plausible, but the labels, grouping and validation for these two decisions may differ. Do not assert a single model is automatically sufficient for both.

## 3. Storage and labeling contract

**Raw source layer (compressed/partitioned, audited):** symbol/timeframe/open-high-low-close-volume, exchange and contract metadata, mark/funding, collection or archive timestamp, data gaps, source URLs and SHA. Historical order-book claims require real archived snapshots; 5m candle turnover is NOT executable depth.

**Frozen `ASOF_FEATURE` row keyed by `decision_id` (safe prediction inputs):**
- Decision UTC, candle close known, symbol, side, strategy ID/version, current signal and feature hashes.
- Symbol price structure: relative move, returns across predeclared lookbacks, ATR, recent volatility, trend/slope, MACD/RSI (where causal), volume/turnover, funding snapshot, book quality/cost estimate, breakout/reversion structure and liquidity readiness.
- **BTC status known at entry**: BTC trend direction and strength, 5m/1h/4h price returns, volatility / ATR regime, BTC above or below prior as-of trend levels, cross-market breadth, coin-vs-BTC relative strength/beta/correlation using only lagged information.
- Current market regime and strategy-context agreement, portfolio slot status, versioned universe-selection rank/score and out-of-universe control membership/sampling probability.
- **Data-quality/provenance flags** for latency, stale or incomplete data, cost/funding source and source type. No future entry/exit prices or final label fields.

**Separate `MATURED_OUTCOME` row keyed to the same frozen decision (never available as a feature at entry):**
- Actual future simulated/real entry/exit UTC, side-aware gross and after-cost net USDT and % of notional, fees, actual/assumed funding, slippage, book-depth evidence confidence, loss/target/timeout/other exit reason.
- **MFE and MAE**: maximum favorable/adverse price excursion **from entry** for that side, report both price % and R (if risk distance defined), timestamp/time-to-MFE and MAE, first barrier-touch ordering, peak/trough and duration; mark candle-path ambiguity rather than invent precision.
- Holding time, gap and uncertain/censored/invalid cases, stop execution gap and actual executable crossing assumptions.
- **Market during the trade**: post-entry BTC path and realized regime change used for diagnostics/labels **only**, not to compute score at original t. Clearly distinguish "BTC at entry" (safe) from "BTC after entry" (future label).
- All simultaneously eligible candidates at t and their same-policy completed outcomes; per-time grouping, comparison cohort, best/worst counterfactual and regret (diagnostic), NO TRADE comparison.
- Source hash, market-data authority tier, model version/prediction hash, label policy ID, `outcome_available_at`; real executed PnL in an entirely distinct account ledger.

**Required governance:** 100% of qualifying candidate IDs traceable; no duplicate IDs or unknown time status; no future-outcome label in feature pipeline; old/source-mismatched/censored samples excluded from certified economics.

## 4. Scientific risks and tests

- **Selection bias:** Training only from the chosen 20 would tell the ranker little about the many potentially better choices it excluded. Baseline whole-market coarse labels and a genuinely sampled excluded control prevent false top-20 claims.
- **Forecasting vs hindsight:** Retrospective best-of-150 is an unachievable oracle diagnostic. Never feed realized future winners to the ranker at as-of time or compare it as if executable PnL.
- **Preselection economics:** Naively keep 20 with highest isolated return predictions may overconcentrate correlated coins or sacrifice cost/readiness, diversification and timing. Measure the net effect of universe restriction as well as 1-slot performance.
- **Alpha deficit:** V6's old eight families showed negative economic results. Overlaying them across 150 markets does **not** create edge; V7 must test each setup/strategy's conditional payoff and include an abstention option.
- **Label mismatch:** OHLC-derived stop first touch is only a proxy and can miss price paths, queue, book and funding. Full replay uses authoritative high-resolution events when possible and separate uncertainty tiers.
- **Review mismatch:** A slow 8h watchlist cannot always capture 5m transients; evaluate 8h hysteresis against more reactive schedules on development folds only.
- **Overfitting / small samples:** 150 pairs × 10 families is not automatically 1,500 independent examples. Correlated simultaneous signals must be grouped by decision time and resampled by time blocks.
- **Performance:** Broad strategy feature computation must be optimized/shared across families; no full heavy LightGBM retrain per contract every cycle on the ~2 vCPU/8 GiB VPS.
- **Evaluation:** Compare (1) as-of liquidity-only universe, (2) fixed 20/25 baselines, (3) strategy-only rule ranking, (4) learned strategy-aware top 20, (5) V6 where comparable, and (6) NO TRADE under identical historical costs and actual 1-slot constraints. Compare selected and excluded conditional opportunities separately.

## 5. Relation to current frozen numbers (do not silently change)

Founder-approved: complete eligible historic USD-M market discovery; three initial research months; 10–15 strategies; **20 candidate coin capacity**; shadow outcomes for valid signals; eventually one capital slot; 8h review as provisional; new unseen economic proof and paper/live owner gates.

**Open for explicit future numeric-gate approval:**
- Required number and coverage of **broad-market labeled signals and independent timestamps** before a 20-of-N ranker is considered trained. Existing [numeric proposal](V7_NUMERIC_GATE_PROPOSAL.md) suggests only 500 matured candidates / 100 multi-candidate events for *prototype readiness*; this is **not automatically enough for training a robust 150–300 universe ranking model**.
- Required outside-top20 control sampling size and strategy/market regime diversity.
- Whether to use 5m candle path labels throughout or to acquire 1m/tick for all eligible strategy-entry windows; storage/performance/quality study needed in G1.
- What each family's **prospective outcome label** and exit policy mean; must freeze before learning, not after viewing out-of-sample winners.
- Universe review cadence, risk of rapid rotation, minimum tenure and weighting of number vs expected quality of opportunities.
- Numeric expected-net calibration / tail-risk and macro-regime thresholds, prespecified statistical uplift evidence.

**Approval and stage:** This proposal is a substantive owner-originated design refinement but not yet a numerical threshold freeze or implementation authorization. If confirmed, create a versioned roadmap amendment reflecting the dual learning objectives before any expensive G1/G2 experiments.

## 6. First executable research task once approved

Within G1/G2, **first develop the source-attested `ASOF_FEATURE` / `MATURED_OUTCOME` schema and storage/readiness benchmark**, rather than downloading huge unlabeled raw datasets. Produce one multi-coin/multi-strategy toy + historical development-only sample with demonstrable causal timestamps, MFE/MAE/BTC features, historical archive source and compact storage. Validate temporal and order-path conventions, THEN scale to whole exchange. Strictly isolate future holdouts before evaluating models.

**No VPS or trading authorization arises from this design document.**
