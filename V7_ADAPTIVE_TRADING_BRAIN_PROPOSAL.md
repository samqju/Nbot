# NBOT V7 — Adaptive, Replaceable Trading Brain (Owner-originated Design Refinement)

**Date:** 2026-10-20 IST  
**Status:** **Proposed architectural amendment for review**, not a silent revision of the existing frozen roadmap or authorization for G1–G8 execution.  
**Scope:** Concept, labeled-data contracts, offline evaluation and governed model lifecycle; no VPS access, coding, training, paper or real orders.  
**References:** [frozen roadmap](V7_ROADMAP.md), [strategy-aware market-ranking refinement](V7_STRATEGY_AWARE_UNIVERSE_REFINEMENT_PROPOSAL.md), [G0 audit](V7_G0_LEGACY_AUDIT_2026-10-20.md), [numeric-gate proposal](V7_NUMERIC_GATE_PROPOSAL.md).

## 1. Owner's correction

**Do not make the learned trade/no-trade decision fundamentally dependent on a fixed set of 10–15 strategies.** Trading styles go in and out of relevance when market structure changes. The central NBOT V7 decision maker should be an **auto-replaceable trading brain** that learns to choose a regime-appropriate behavior, can reject every candidate, and does not remain loyal to yesterday's successful setup.

**Clarification:** 'Auto-replaceable' means **governed model-version rotation and dynamic behavior/weighting using predeclared performance evidence**; not arbitrary self-modifying order code, unrestricted live retraining, backtest self-optimization, or promotion of unvalidated challengers to live execution.

## 2. Architecture — reusable proposal engines, adaptive brain, immutable safety boundary

### A. Market observation + feature/outcome memory

- Broad point-in-time observations from historically eligible Binance USDT-settled perpetual universe (not a fixed survivor sample).
- At decision time, label known features: BTC multi-timeframe state, coin/BTC relative behavior, liquidity/cost, volatility/trend/range/structure, market breadth, funding/mark context, time/regime, freshness and event/source identity.
- After observable expiry, append **MFE/MAE, sequence/times of adverse/favorable movement, realized exit/cost/funding, holding duration, reason, BTC path changes and comparison with contemporaneous candidates** under distinct future-only outcome fields.
- Record absent, stale, uncertain or unfunded fills as unresolved, not known negatives or positives.
- Store compressed raw data with source and hash lineage, not unlimited unlabeled/duplicated candle dumps.

### B. Diverse candidate proposal — strategies as advisors, not masters

- Reuse V6 eight families as frozen **negative/research controls**, plus genuinely distinct additional hypotheses (10–15 initial families).
- Add **strategy-independent candidate proposal** to prevent blind spots: feature-driven event/structure triggers, a broad family-neutral directional price-action grid, or an independently trained proposal head with an entry eligibility contract. Research proposal may be more permissive than live feasibility, but it cannot use future information.
- Every eligible market may produce long, short, multiple competing proposals, or none. Strategies generate *candidate hypotheses and useful explanatory features*, not a final mandatory entry list.
- Train on matured outcomes of **both selected and rejected candidates** across the wider market. Independently sample off-shortlist coins and strategy-independent hypotheses to measure blind spots; save inclusion probability and source quality.
- Candidate proposals themselves can be versioned/challenged, subject to robust validation. Otherwise the brain cannot learn setups the static proposal engines never reveal.

### C. Adaptive Trading Brain — central learned decision policy

The brain receives synchronized as-of candidates and cross-market context; evaluates current portfolio/capital state; produces calibrated estimates of:
1. Expected *net after-cost* value and downside/risk/holding time for each proposal, not only P(win).
2. Relative quality of available coins for the 20-pair capacity horizon.
3. Relative expected value of each currently valid entry vs NO TRADE at a one-slot decision.
4. Epistemic uncertainty, data-source/cost credibility, out-of-distribution warning, and sample support.
5. Confidence to abstain, reduce exposure or revert to conservative baseline when evidence is weak.

Two **distinct decision horizons** (may share features/models but need target-specific labels and validation):
- **Universe Brain**, e.g. an as-of 8h review: choose up to 20 coins likely to offer valuable *prospective* opportunities in the next declared watch horizon. Must not use later best-of-window to claim foresight.
- **Execution Brain**, e.g. a completed 5m entry event: rank *currently proposed eligible* long/short trades, decide one if expected benefit surpasses NO TRADE, else do nothing. Never pretend all shadow opportunities are simultaneously executable in one wallet.

### D. Flexible trading mindset: TWO adaptation speeds

**Fast (per decision, without retraining):** a frozen brain changes **weights/actions** based on known-at-decision market structure and uncertainty. For example, trend-continuation hypotheses may receive greater attention during strong trends; range/reversion hypotheses in quiet markets; breakout volatility expansion may be penalized after false breakouts. This routing must be **learned and validated**, not just arbitrary hard-coded RSI/regime rules. **Abstention is a genuine 'mindset'.** It can use a mixture-of-experts, context-conditioned ranking or a general model with family/context interactions. No need to swap model weights every candle.

**Slow (model artifact replacement):** monitor champion predictions against matured shadow/paper outcomes; detect degradation, regime drift and calibration errors; train a **challenger brain** from historical evidence that matured *before its fit cutoff*, freeze the challenger and evaluate it prospectively against the champion and simple baselines with matched candidates/costs/slot constraints. A challenger must have sustained after-cost economic uplift with uncertainty bounds, not just improved model NDCG, backtest wins, or more trades.

Use V4 existing grouped **LightGBM LambdaRank** and champion/challenger governance plus V5.1 provenance/science. Those are **implementation foundations, not validated adaptability or alpha**. A general net-return model and separate router/utility model may prove better than pure LambdaRank. Compare fairly, don't preselect winner by sophistication.

### E. Replaceability contract (fail closed)

- A Trading Brain is a signed/versioned, immutable **model artifact + feature schema + training cutoff + label/exit/cost policy + calibration + scope + risk envelope**. The safe executor, broker privileges, stop/kill-switches and portfolio money limits must **not** be self-rewritten by model replacement.
- Every candidate model has an identity, supported regimes, minimum support, known uncertainty/coverage and rollback parent.
- The champion remains active by default. Challenger is initially shadow-only; running an automatically evaluated challenger does not mean trading with it.
- Model **switch/routing** within a pre-approved ensemble can occur autonomously using frozen validated logic; model **promotion to paper** only according to approved prospective gates; **live-model promotion remains separately owner-approved** under current frozen roadmap unless explicitly changed in a future versioned safety decision.
- On insufficient sample, unresolved source quality, worsening calibration, holdout leakage, sustained negative after-cost results, model mismatch or missing executable fills -> return **NO TRADE / HOLD** or rollback to approved conservative baseline; never rotate into another untested brain merely to keep trading.
- Training a new model is NOT a reason to promote it; having an automatic replaceable architecture must not create automatic live order authority.

## 3. Why strategy-only entry gating is incomplete

If 10 strategies generate only 10 familiar shapes, the AI can rank only those shapes. This makes the training/execution opportunity space a fixed prison, even with perfect ranking.

V7 must allow **new prospecting heads/strategies/structure detectors** and a controlled **broad-market challenger candidate cohort** so the data can reveal successful new market behaviors. The generic proposer must still enforce basic ex-ante feasibility and be evaluated under a common, versioned, realistic stop/cost policy.

Avoid circular training: do not judge a new proposal by outcomes produced only from candidates the current champion already liked. Build independent, stratified exploratory **shadow-only** coverage and periodically label off-policy missed candidates with known sampling design. Do not spend real money purely to collect exploratory labels without explicit authorization.

## 4. Concrete decision examples (illustrative only)

| Observed market | Frozen static strategy tendency | Desired learned brain behavior |
|---|---|---|
| BTC strongly trending, broad strong directional breadth | Trend-following signal favored by fixed family | Evaluate whether trend-following setup retains positive net edge; reweight if confirmed, not automatically |
| BTC choppy/ranging, failed breaks across coins | Same breakout family still emits long signals | Lower breakout weight or abstain; evaluate reversal/range experts if their *current* evidence supports them |
| BTC violent discontinuity, correlated positions, uncertain fills | Momentum/volatility triggers numerous signals | Penalize fill/slippage/tail risk or NO TRADE despite high gross price moves |
| Formerly strong trend model deteriorates in forward shadow evidence | Previous model keeps trading | Freeze and test challenger with new labels, promote only if matched forward proof and permission gates pass |

These are examples of desired behavior, **not backtested/proven profitable policies**.

## 5. Model replacement approval tests — thresholds pending owner review

The full [numeric gates proposal](V7_NUMERIC_GATE_PROPOSAL.md) is still unapproved. For adaptive brain replacement add **specific tests before approval**:
- **Source/causality:** 0 detected future-input leaks; no current labels before maturity; model hash/fit cutoff/label schema match; missing data means HOLD.
- **Fair comparison:** champion vs challenger scored at **identical as-of timestamps** over the **same full candidate universe and feasibility rules**. One-slot portfolio simulation accounts for the fact that different trade choices produce different future occupancy and opportunity cost.
- **Predictive ranking:** report groupwise top-k uplift, calibration, abstention coverage, errors across regimes, excluded-cohort opportunity misses; these are *diagnostics*, not promotion proof.
- **Financial:** positive after-cost PnL and uplift vs strongest preregistered baseline; extra 25bp notional roundtrip stress; confidence bounds respecting shared market/time dependence; risk and max drawdown envelope.
- **Drift:** predeclare monitoring of realized net vs predicted net, ranking regret diagnostics, model calibration, candidate-source coverage, performance per market regime, no-trade rate. A drift alert can initiate challenger *research*, never force automatic live replacement.
- **Anti-churn:** minimum prospective samples and observation duration, minimum uplift, confidence, cooldown and rollback thresholds to be specified **before** observing promotion-window outcomes. Frequent switching can overfit noise.
- **Challenge truly adaptive vs fixed:** ablation A strategy-only static winner, B V4 standalone ranked family candidates, C context-conditioned adaptive brain, D champion/challenger replacements; all evaluated under identical data/cost/risk and one-slot wallet rules. Challenge the value of complexity itself.
- The previously proposed G5 >=90 unseen days / >=100 portfolio trades, 95% block-bootstrap uplift and G6/G7 forward trials are not automatically enough to prove every novel brain replacement across regimes. Treat insufficient evidence as NO-GO.

## 6. Development order / minimal scope

1. Amend and verify as-of feature + matured outcome schema: MFE/MAE, BTC context, costs, causality and market source labels.
2. Build a **broad-market candidate laboratory**, including strategy-independent shadow exploration and off-shortlist controls. Use development-only historical samples.
3. Port V4 LambdaRank as **one baseline brain**, not as a prematurely winning self-contained solution; benchmark against expected-net and contextual routing alternatives.
4. Prototype **two-level brain** (future up-to-20 watch universe; current one-slot entry/NO TRADE) and time-block matched evaluations.
5. Implement registry, challenger scoring, drift diagnostics, controlled promotion, fail-closed rollback and operating permission boundary.
6. Only after unseen positive economics and prospective paper gates consider any owner-approved real deployment.

**Decision state:** Owner's concern is recorded. Exact technical form (single context-conditioned model vs mixture of experts vs challenger population, dynamic promotion numeric thresholds, strategy-independent proposal method) remains for **scientific evaluation**, not solved by declaring that an adaptive brain will be profitable.

**No modifications to the existing frozen roadmap, execution authority, VPS, data, or code are implied by this design proposal.**
