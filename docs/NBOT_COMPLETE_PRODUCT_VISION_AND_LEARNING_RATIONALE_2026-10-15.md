# NBOT — Complete Product Vision, Learning Philosophy, and Reason for Every Major Component

**Vision document, version 1.8 — 15 October 2026**

**Purpose:** Explain what NBOT is supposed to become, why it was conceived, what V4 taught us, why V5 includes virtual research trades, Champion/Challenger learning and paper trading, and how all of that serves a **single-position autonomous trading bot** rather than a needlessly complicated research institution.

**Nature of this document:** Product vision, design rationale and proposed simplifications. **Not a trading authorization, a model approval, a replacement for the authoritative roadmap, or a statement that engineering is complete.** The implementation and safety gates are governed by the authoritative roadmap, especially its sections 1–16 and owner-selected lifecycle amendments in sections 17–26. Where this vision recommends simplification that differs from the roadmap, the difference is identified as a decision requiring approval.

---

## 1. NBOT in one sentence

**NBOT is an automated, evidence-driven Binance USDT-M trading system that watches a broad market, learns which opportunities have a credible positive expected return after costs, decides whether to take a trade or abstain, and—if separately authorized for real execution—manages at most ONE actual open position at a time.**

The system should become better at **selecting** a trade, not better at generating large numbers of trades.

The user should not need to sit in front of charts looking for entries, repeatedly tune dozens of rules after each loss, or manually decide which model deserves to replace the current one. NBOT should do the monitoring, evidence collection, bookkeeping, analysis, training and presentation of proposed improvements automatically. Model promotion and real-money authority must remain subject to separately defined safeguards and approval.

The ideal output on most five-minute market events can be: **NO TRADE**.

### The fundamental distinction

- **Many markets observed:** approximately 50 liquid USDT-M perpetual pairs, with BTC context.
- **Many opportunities considered:** a possible LONG and SHORT for each observed coin, including no-pattern observations.
- **Many hypothetical outcomes researched:** only where a virtual-trade experiment is eligible, prospectively defined and later independently verifiable.
- **Few actual trades selected:** sometimes none.
- **Actual open positions:** no more than **one globally**, under the user's clarified operating goal.
- **Many models researched:** potentially, but only one designated incumbent Champion may control an approved real decision policy at a time.
- **No automatic live trading permission:** source engineering and research are not permission to send an exchange order.

That is the product. Everything else must justify its cost by making that product safer, more selective, more reliable or more capable of learning.

---

## 2. Why the project was created: the problem with naive automated trading

A traditional rule-based bot follows instructions such as "buy when several bullish indicators agree." It may run perfectly as software while losing money as a trader.

A technical pattern is a **description of market conditions**, not proof of future profit.

An entry can lose because:

1. The direction was wrong.
2. The direction was reasonable but the entry came too late.
3. BTC or the broad market regime had changed.
4. The stop was too tight for the coin's normal noise.
5. The target or holding period did not fit that situation.
6. Fees, spread, slippage or funding consumed the gross advantage.
7. The trade was too correlated with an existing exposure.
8. The quoted information was stale or incomplete.
9. The apparent historical advantage was sampling luck or data leakage.
10. The market simply offered no attractive opportunity.

A profitable decision must therefore combine **market context, a viable entry/exit plan, evidence of conditional advantage, risk and real costs**. A ranking score alone is insufficient.

The goal is not to guarantee profitability. The goal is to build a system that can ask and test, without self-deception: **"Is this trade better than doing nothing?"**

---

## 3. What V4 taught us, and why a V5 redesign was necessary

The authoritative V5 roadmap documents several important V4 observations and code findings.

### 3.1 V4 often prioritized patterns rather than demonstrated economic advantage

The V4 scanner ordered research opportunities roughly by whether recognized setup tags existed, how many tags matched, universe rank and a deterministic tie-breaker. Later relative machine-learning ranks could order candidates without indicating positive expected after-cost return.

This created a dangerous confusion:

> "Best-ranked candidate" does not mean "candidate with positive expected profit."

If all available candidates are unattractive, the highest-ranked one is still unattractive. **NBOT must be able to reject the entire list.**

### 3.2 More matching patterns did not establish more profit

The roadmap's historical V4 analysis found no monotonic rise in after-cost return as pattern-match counts increased. Some groups with slightly positive gross results remained negative after costs.

The source-analysis lesson is **not** that every indicator is useless. It is that a named indicator or a high count of matching indicators does not by itself constitute an edge.

The original 24 V4 detectors should be preserved as **hypotheses and features**. They may be useful only in particular BTC/coin regimes, directions, volatility states, liquidity conditions or risk geometries.

### 3.3 V4 lost money in the analyzed samples

One earlier V4 sample comprised 8,878 scored decisions, with average gross approximately -0.06043R, modeled round-trip costs approximately +0.39077R and average net approximately -0.45120R. A later, **different** observation cutoff recorded 9,177 usable scored decisions and additional unresolved cases. These populations must not be combined or treated as one backtest.

These are historical sample findings, not proof that every future strategy must lose or proof of a single root cause. They support a stronger entry-selection, source-integrity and after-cost research design.

### 3.4 The data itself was sometimes incomplete

Some V4 outcomes were unresolved owing to gaps or process restarts. An outcome whose trade path is unknowable cannot honestly be relabeled a win or a loss.

The learning system must distinguish **what happened**, **what we can verify** and **what is not known**.

### 3.5 V4 model validation had weaknesses

Historical generations experienced training/validation overlap or other weaknesses, and the evaluated model generations did not establish an improved economic decision policy.

V5 must use chronological, embargoed, independent evaluations and must preserve the incumbent model unless a Challenger convincingly improves the decision.

### The V4-to-V5 change

**V4 emphasis:** Find patterns, rank available opportunities, fill research capacity, evaluate resulting activity.

**V5 emphasis:** Understand market state, consider all eligible opportunities, measure complete after-cost outcomes, learn conditional advantage and uncertainty, **select only when a credible advantage exists**.

V5 is not merely V4 with additional machine learning. It changes **the question being asked**.

---

## 4. What "automatic learning" should really mean

Automatic learning is not "change the strategy after the last losing trade."

It is a continuous, disciplined loop:

1. Observe markets reliably.
2. Record what was known **before** each decision.
3. Enumerate opportunities, including those not chosen.
4. Freeze objective hypothetical entry/exit rules where eligible.
5. Allow enough future market time to observe each outcome.
6. Verify the outcome and its costs.
7. Gather enough independent evidence across market conditions.
8. Train and evaluate candidate models on appropriately separated data.
9. Compare a candidate model to the currently accepted Champion and to **no trade**.
10. Recommend retaining, rejecting, suspending or promoting a model based on predeclared rules.
11. Apply any required approval before allowing a new model to influence real decisions.
12. Repeat without retroactively rewriting past decisions.

**Automated learning** can mean automatic data collection, maturation, analysis, training, evaluation and recommendation. It **does not have to mean unsupervised self-promotion of a model that controls money**.

An especially important ability is learning **not to trade** in regimes that provide no demonstrated advantage.

---

## 5. Why NBOT needs to observe the market

**NBOT must understand the market before deciding whether to trade.** Watching the market is how it learns what different conditions look like, which opportunities may be promising, and when it is better to stay out.

### The main reasons

1. **Understand different market conditions.** Recognize whether the market is trending up, trending down, moving sideways, becoming volatile, staying calm, or changing from one condition to another. The same setup may behave differently in each environment.

2. **Understand how BTC influences the overall market.** Observe when altcoins follow BTC, react more strongly than BTC, move against BTC, or behave independently. Learn how a sudden BTC move changes other coins' risk and opportunities. Do not assume BTC controls every coin all the time.

3. **Recognize and learn market structures.** Identify structures such as **double bottoms, double tops, cup-and-handle formations, range breakouts, breakout-and-retests, failed breakouts, support/resistance, trends and reversals**. Observe how they form, when they fail, and what happens afterward. These are structures to **study**, not automatic buy/sell orders; not every example is necessarily implemented in the original 24 V4 detectors.

4. **Find and compare opportunities across coins.** An attractive setup on one coin may be weaker than another, or all available opportunities may be poor. Watching approximately 50 liquid coins gives NBOT a choice, **even though it should manage only one actual position at a time**.

5. **Learn what really works in which conditions.** Record what the bot could see at the time, then study the later outcome of eligible opportunities—including ones it did not trade. This helps distinguish a visually convincing pattern from a setup with a credible advantage **after fees and other trading costs**.

6. **Understand risk and trading costs.** Watch volatility, liquidity, spread, price movement and relevant funding conditions. A good-looking pattern may still be too risky, too expensive or unsuitable for the intended stop-loss and target.

7. **Know when NOT to trade.** Recognize unclear structures, sudden market changes, poor liquidity, conflicting signals or missing/stale data. Market observation must help NBOT say **NO TRADE**, not push it to find an entry at every five-minute event.

### What does this look like in practice?

Suppose NBOT sees a possible **double bottom** on one coin and a **range breakout** on another. It also observes that BTC has just started falling sharply. Instead of buying because a pattern appeared, NBOT studies the BTC impact, the coin's price structure, available liquidity, likely costs and what its verified past research says about similar conditions. It may choose one opportunity—or **neither**.

**Important distinction:** Observing a structure means **"this may be worth studying."** It does **not** mean **"place a trade."** A trading decision comes later, after economic evidence, model confidence and risk checks.

### Why observe 50 coins and both directions?

The current G1 research design observes **50 USDT-M symbols, including BTC**, with up to **100 LONG/SHORT directional candidate records** per completed five-minute event. These records describe what was observable; they are **not** 100 opened positions or 100 completed virtual trades.

Both LONG and SHORT perspectives help NBOT compare different possible outcomes, but opposite-direction candidates from the same event can be dependent and must not be counted as independent successes.

**Bottom line: NBOT observes the market to understand it, recognize opportunities, learn from outcomes, manage risk and know when to stay out—not simply to generate trades.**

---

## 6. After observation: MARKET EXPLORATION — what should NBOT do with what it sees?

**Observation tells NBOT what is happening. Exploration asks what those observations might mean and what could be worth testing. Research then determines whether those possibilities actually have a positive economic advantage.**

This is the owner's intended next step, expressed in practical terms:

> Watch the market, select approximately 50 suitable coins, study the market and BTC environment, inspect each coin's price structure through our 24 existing pattern detectors, and explore whether a LONG opportunity, a SHORT opportunity or **NO TRADE** might make sense. Learn how the same setup behaves differently under different conditions.

It is useful to call this **Market Exploration** rather than immediately calling every observation "research." Exploration generates and organizes questions. Rigorous research answers them using later, verified outcomes. Both belong in NBOT's learning process.

### Step 1 — Choose the market universe

Select roughly **50 eligible, reasonably liquid USDT-M perpetual coins**, using information already available at the selection time: contract eligibility, liquidity/volume, freshness, market quality and the existing frozen selection rules. The present G1 implementation includes BTC among the 50.

This is a **market watchlist**, not 50 trade recommendations. Keep the chosen universe and its selection time recorded so NBOT does not quietly replace yesterday's watchlist with today's winners.

### Step 2 — Understand the overall environment

Before examining any coin on its own, ask:

- Is BTC trending up, trending down, ranging or experiencing a sharp move?
- Is the wider market generally following BTC, diverging from it or moving unevenly?
- Is volatility calm, increasing, extreme or transitioning?
- Are many coins participating in the same move, or only a few?
- Is the information sufficiently complete and current to draw any conclusion?

BTC should be understood as **market context**, not as a permanent command to go LONG or SHORT.

### Step 3 — Understand each coin's individual behavior

For each of the 50 coins, look at:

- **Direction:** trending upward, downward or sideways.
- **Price structure:** support/resistance, higher highs/lows, lower highs/lows, ranges and confirmed reversals.
- **Recognizable formations:** double tops/bottoms, cup-and-handle shapes, range breakouts, retests, failed breakouts, pullbacks and consolidation.
- **Strength compared with BTC and other coins:** following, lagging, leading or diverging.
- **Volatility and liquidity:** whether the movement is orderly or erratic, and whether trading costs might be excessive.
- **Timeframes and maturity:** whether a structure is confirmed on information already available or is only beginning to form.

A chart can look like a double bottom before the pattern has actually been confirmed. NBOT must distinguish **forming / confirmed / failed / uncertain** structures without using future prices to rewrite the past.

**Scope note:** Double bottoms, cup-and-handle shapes and other familiar chart structures are useful examples for exploration. They are **not all guaranteed to be implemented by the original 24 V4 detectors**. Additional detectors should be explicitly specified and tested rather than claiming that an existing rule recognizes something it does not.

### Step 4 — Apply the 24 original setup detectors

Use the existing 24 V4 pattern hypotheses as tools for describing the coin's situation, including:

- Momentum and trend continuation.
- Pullbacks within established trends.
- Breakouts and breakout retests.
- Reversals and failed breakouts.
- Range and mean-reversion behavior.
- Relative strength versus peers and BTC.
- Confirmed structure continuation.

Each detector answers **"Is this type of setup present?"**, not **"Is this trade profitable?"**

A coin can match several patterns or no pattern. Multiple matching patterns do not automatically increase expected profit. The pattern names are observations about the **same price movement**, not separate independent victories.

### Step 5 — Explore LONG, SHORT and NO TRADE

For each coin, explore **both directions** as possibilities, not obligations:

| Possibility | What NBOT asks during exploration |
| --- | --- |
| **LONG** | Is there a plausible upward setup, given BTC conditions, the coin's structure, volatility, likely entry, stop and costs? |
| **SHORT** | Is there a plausible downward setup, given the same evidence? |
| **NO TRADE** | Are conditions unclear, contradictory, too risky, too costly, source-unverified or simply unpromising? |

**At this exploration stage, a "promising LONG" or "promising SHORT" means a hypothesis worth examining—not a proven positive-outcome trade signal.** Whether a directional hypothesis has credible **positive expected net return** is established later, using independently qualified historical/forward outcomes and uncertainty.

Keep NO TRADE available for **each coin** and for the **entire market event**. Both directional hypotheses can be considered in the research ledger even if neither qualifies for a real or paper entry.

### Step 6 — Record the combinations so NBOT can learn

The useful learning question is not merely "Did a breakout work?" It is:

> "When BTC was in condition X, a coin had price structure Y, detector Z appeared on the LONG or SHORT side, and costs/risk looked like W, **what happened afterward?**"

For every eligible decision-time observation, retain the relevant facts **as they were known at that time**, such as:

- The event time, coin and direction being considered.
- BTC state, broad-market behavior and each coin's relationship to BTC.
- The coin's trend, range, volatility, structure and degree of confirmation.
- Applicable pattern detectors, including when none matched.
- Quality/freshness of market sources, spreads, liquidity and the prospectively defined risk/cost assumptions.
- The reason a possibility was observed, held, rejected or considered for a virtual research experiment.

This preserves the complete **choice set**, including opportunities the current Champion did not select. It also allows NBOT to explore combinations it might otherwise overlook.

Do **not** silently start 24 virtual positions per coin because 24 detectors exist. The current system records up to **100 distinct coin-direction candidate observations per completed five-minute event** across 50 symbols. Tags can overlap; only separately eligible, frozen and fully evidenced virtual experiments may later become scored outcomes.

### Example: the same pattern can mean different things

Imagine three illustrative situations:

| Market and BTC condition | Coin structure | What exploration should ask |
| --- | --- | --- |
| BTC calm or gradually rising | Potential double bottom | Could a LONG become attractive after confirmation, reasonable costs and proper research support? |
| BTC falling sharply | The same-looking double bottom | Is this a weak or dangerous countertrend bounce that should be avoided? |
| BTC moving sideways | Range breakout that quickly fails | Might a SHORT or **NO TRADE** be more sensible than chasing the breakout? |

These are **questions**, not conclusions. There is no universal rule that these formations will succeed or fail in these situations. Their economic value must be tested.

### Step 7 — Hand promising and rejected possibilities to the RESEARCH stage

**Exploration output:** a timestamped, source-backed description of the available opportunities, market context, matched structures and possible LONG/SHORT/NO TRADE choices. It generates **hypotheses**, not orders.

**Research output (the next stage):** for eligible hypotheses, freeze an entry, stop, target, horizon and economic assumptions **before** observing future prices. Follow the actual later source path, verify entry/exit quotes and costs, mark missing evidence honestly, and calculate qualified hypothetical **net** results. Study how those outcomes vary by BTC regime, coin structure, detector, direction, liquidity and risk.

**Learning output:** estimate whether any particular type of opportunity has a credible advantage over **NO TRADE** after costs, while accounting for dependence, uncertainty and evidence quality.

**Trading decision output:** only a properly validated and approved Champion, together with an independent risk guardian, can propose/authorize a paper action or, under a separate future live authorization, an actual trade. The owner's operating goal remains **at most one actual open position globally**.

### The simple distinction we should preserve

- **Observation:** "What is happening?"
- **Exploration:** "What patterns, behaviors and possible opportunities do we see, and what should we investigate?"
- **Research:** "When we tested those possibilities against properly verified later outcomes, what really happened after costs?"
- **Learning:** "Which combinations have repeatable, sufficiently credible positive expected net results?"
- **Selection:** "Of the qualified opportunities available now, is one worth taking—or is NO TRADE better?"

**Bottom line:** NBOT should become a patient **market explorer and learner first**, and a very selective **single-position trading bot second**. Recognizing an opportunity must never be confused with proving that entering it will make money.

---

## 7. Why BTC and market regime matter

Altcoin behavior often depends on the broader market. BTC can influence liquidity, volatility and directional risk, but its role is not a universal buy/sell rule.

NBOT should distinguish conditions such as:

- BTC trending strongly upward or downward.
- BTC trading sideways.
- BTC suddenly experiencing a volatility shock.
- Broad market breadth improving or deteriorating.
- Individual coins outperforming or lagging BTC.
- A coin trending, ranging, compressing or attempting a reversal.

A bullish coin pullback could have different outcomes when BTC is stable versus when BTC is in a severe downward shock.

Learning should estimate the **conditional** advantage of a pattern and direction **within a market environment**, using only data available at the original decision time.

An unknown or stale BTC state must remain **UNKNOWN**; it cannot silently become a neutral input merely to permit a trade.

The goal is not to predict BTC perfectly. It is to avoid taking a coin trade as though the rest of the market did not exist.

---

## 8. WHY VIRTUAL TRADES ARE ESSENTIAL

This is one of the most important choices in NBOT.

A virtual research trade is a **predeclared, hypothetical position**. It is used to learn what a valid opportunity would have produced under a specific entry, stop, target, maximum holding period and cost model.

It is **not** a real exchange order. It consumes no real capital and creates no actual position.

### 8.1 The selected-trade problem

Imagine NBOT considers 100 directional candidates at 10:00 AM but chooses only one, or chooses none.

If it learns only from trades it actually selected, it knows little about the 99 alternatives. That creates **selection bias**:

- It cannot tell whether its chosen trade was the best available.
- It cannot discover that a previously ignored pattern works in some regime.
- It cannot evaluate why no-trade was better on a dangerous market event.
- It cannot fairly compare a new selector against the old selector.
- It collects learning examples slowly when one actual position may remain open for hours.

Virtual research supplies counterfactual evidence: **"What would this prospectively defined opportunity have done, under the same source and cost rules?"**

That is the foundation for improving a **single-position** decision maker.

### 8.2 How a legitimate virtual trade works

1. At the decision time, freeze the coin, side, BTC/coin features, applicable pattern tags, source IDs, entry convention, stop, target, maximum hold and cost policy.
2. Do **not** change those conditions later because the future path looks unfavorable.
3. Observe the **subsequent** original market path. Determine whether the stop, target or horizon is reached first.
4. Verify relevant entry and exit bid/ask evidence. AggTrade crossing a price does **not** establish an exchange fill.
5. Apply defensible, timestamp-appropriate fees, spread/slippage and funding assumptions according to the declared evidence contract.
6. Calculate a hypothetical **net** result in initial-risk units, or mark the case PENDING, HOLD, UNRESOLVED or CENSORED when the required facts are unavailable.
7. Retain the full evidence lineage so the result can be independently checked.

The required quality is **honest counterfactual research**, not a claim that the bot could have received an identical real fill.

### 8.3 Why we need virtual trades even after live trading begins

A real single-position bot will leave many opportunities untraded because its one available position is occupied or because the Champion abstains.

Those unchosen opportunities still contain potentially useful learning information. Proper virtual experiments let the research engine continue learning while actual execution remains narrow.

Virtual outcomes must be measured consistently against hypothetical time, costs, correlation and occupancy. We must not pretend the bot could have executed **all** simultaneous alternatives with one position.

### 8.4 Why 100 candidate records are NOT 100 completed virtual trades

A candidate record states that an opportunity was **observed and described**. A virtual outcome counts toward scientific learning only when the entry plan was eligible and its future path and costs were sufficiently evidenced and matured.

One candidate can remain an observation, be rejected, never mature or lack verifiable source coverage.

Virtual outcomes from the same BTC shock, same five-minute boundary or overlapping horizons are statistically dependent. **2,000 rows are not automatically 2,000 independent market experiments.**

### 8.5 What virtual trades must NEVER do

They must never:

- Send real or operational paper orders.
- Use future features to make past entry decisions.
- Assume missing fees/funding/slippage are zero.
- Turn gaps or process restarts into fabricated wins or losses.
- Claim precise actual execution from trade-print prices alone.
- Create false scientific qualification by multiplying one outcome across many pattern tags.
- Become retroactively modified to favor a preferred model.

**Virtual trades are NBOT's laboratory, not NBOT's brokerage account.**

---

## 8A. RESEARCH — what NBOT does after Exploration has identified possibilities

**Observation sees the market. Exploration describes potential opportunities. Research tests those possibilities using actual subsequent market evidence, without spending real money.**

The owner's proposed design is best implemented as **one shared Research function**, not a separate Research system for each trading portfolio.

### What Research receives

Observation and Exploration hand Research a time-stamped, source-backed record containing:

- **Which market event and coin?** The decision clock, eligible universe and the LONG or SHORT hypothesis.
- **What was the broad market doing?** BTC direction, strength, volatility and shocks; overall market breadth and transition state.
- **What was this coin doing?** Trend/range state, confirmed or forming price structure, strength relative to BTC, volatility and liquidity.
- **Which patterns were visible?** Any of the 24 original V4 detector tags, including a valid **no-pattern** observation; overlapping pattern names are not independent trades.
- **How trustworthy are these facts?** Data timing, source witnesses, gaps, quote freshness and what was or was not knowable at that moment.
- **Was a trade plan eligible?** A prospectively frozen entry convention, stop-loss, target, maximum holding time and risk/cost assumptions where a virtual experiment is justified.

A complete **observation/candidate record** need not become a virtual trade: the experiment still requires prospective eligibility, a coherent entry/exit plan and enough verifiable forward data.

### What Research does

1. Records every observed eligible alternative, including unchosen, rejected and **NO TRADE** possibilities, so the learner can see the choice NBOT actually faced.
2. Starts **virtual research trades** only for eligible, **predefined** LONG or SHORT experiments. A virtual trade is a laboratory hypothesis, not an order or a real position.
3. Follows later market prices without allowing future information to change the entry-time hypothesis.
4. Determines whether stop, target or time limit was reached first using original and continuous-enough source evidence.
5. Validates appropriate entry/exit quote evidence and economic assumptions; accounts for transaction fees, spread/slippage and applicable funding without double counting costs or inventing exchange fills.
6. Produces an evidence-backed **after-cost hypothetical result**, or honestly records **PENDING / UNRESOLVED / CENSORED / HOLD** when the needed facts are not available.
7. Links the result back to **the exact market, BTC state, coin structure, detector tags and direction** observed at the start.
8. Supplies the mature, scientifically eligible results to Learning under explicit provenance and sample-independence rules.

Research should also examine **missed opportunities**, including trades the Champion rejected, because learning only from chosen trades would perpetuate the previous selector's blind spots. It cannot claim that a one-position bot could have simultaneously executed all virtual alternatives.

### Where do paper and future live trading fit?

Research has **multiple sources of feedback** but does **not** need multiple independent research engines:

| Evidence channel | What it teaches Research | What it does NOT prove |
| --- | --- | --- |
| **Virtual research trades** | Which prospective coin/structure/direction/BTC-condition combinations appear to have positive or negative after-cost hypothetical outcomes, and which were missed | That Binance would have filled all these hypothetical trades at those prices |
| **Champion Paper** | How the approved selector behaves with forward timing, a realistic one-position paper budget, entry/exit simulation and risk vetoes | Actual exchange fills or actual earned profit |
| **Challenger Paper** | Whether a frozen new model makes better decisions than the Champion over the **same** future market period | That a superior paper model is automatically fit for real money |
| **Future Champion Live** | Real execution evidence: order acceptance/rejections, actual entry/exit fills, fees, funding, latency, slippage, operational issues and risk | That an untraded alternative would have achieved an identical real fill |

All channels may provide useful learning feedback, **but keep their records, uncertainty and evidence grades separate**. A live trade and its corresponding virtual-paper mirror must not be counted as two independent market opportunities. Real results are a selected sample, so they cannot replace the broad virtual research denominator.

The authoritative roadmap begins with **a qualified Champion paper stage**, and later permits independent Champion and Challenger paper portfolios for fair competition. A future separately authorized live phase may include Champion Live, Champion Paper Mirror and Challenger Paper. **These are separate testing/accounting environments, not separate Research departments and not three real open positions.**

### The responsibility boundary — a deliberate architectural decision

**Research may discover, test, measure and recommend. It must NOT place real orders, control real open positions, change the active Champion without approval, or grant itself paper/live authority.**

- **Research:** establishes verifiable results and creates learning datasets.
- **Learning/training:** estimates conditional after-cost advantage and produces independently testable model versions.
- **Approved Champion decision policy:** generates current LONG/SHORT/NO TRADE recommendations from live, valid features; the Challenger can produce separate experimental recommendations.
- **Independent Execution guardian:** validates model identity, proposal freshness, market source, position occupancy, stop/risk/cost gates and authorization; can veto any action.
- **Owner-approved release controls:** govern model promotion, initial paper release and any future real-money permission. The user's final real-trading objective is **at most one actual open position globally**.

This is how NBOT can become autonomous **at gathering evidence, learning and making proposals**, without letting a newly discovered pattern immediately take control of real money.

---

## 8B. LEARNING — how NBOT discovers what works, when and why

**The owner's central learning goal is:**

> "From the verified results of past virtual trades, learn whether a particular coin price structure and direction performs well under a particular type of market condition and BTC condition. Use that experience to recognize similar future situations—and avoid trades that have not shown a reliable advantage."

That is the right goal. One critical refinement is that **past success is evidence, not an eternal guarantee**. NBOT should learn *estimated, conditional, after-cost advantage and uncertainty*, and keep testing whether those relationships remain useful in new market periods.

### 1. Learn combinations, not isolated patterns

A double bottom, breakout or trend continuation does not have one universal success rate. Its outcome may depend on many interacting conditions:

| Question | What Learning should consider |
| --- | --- |
| **What market conditions?** | Overall uptrend/downtrend, range, broad participation, volatility regime, sudden transition or shock |
| **What is BTC doing?** | BTC trend, short-term acceleration, sudden fall/rise, regime and whether the coin tends to follow or diverge from BTC |
| **What is the coin doing?** | Trend versus range, its own volatility, relative strength, support/resistance, price-structure maturity and confirmation |
| **What was detected?** | One or more of the original 24 pattern hypotheses, or a no-pattern observation, with direction-specific features |
| **Which direction?** | LONG, SHORT or **NO TRADE**; conditions favorable for one direction can be unfavorable for the other |
| **What was the proposed trade plan?** | Entry time, stop distance, profit target, exit/timeout, initial R, liquidity, spread and funding environment |
| **How did it end?** | Matured verified after-cost net R, downside, missed/expired opportunities and valid outcome status |
| **How reliable is the finding?** | Genuine independent samples, diversity of market periods, uncertainty, missingness and stability when conditions change |

The learning target is not merely **"price rose after a pattern."** It is whether an eligible, prospectively declared and executable-looking trade policy would have had a **credible positive expected net return compared with not trading** under those *decision-time conditions*.

### 2. Example — the same double bottom in three different environments

The following is an **illustrative question**, not an established profitable result:

- **Case A:** A double bottom forms on a relatively strong coin, BTC is stable or gradually strengthening, spreads are small and the stop/target geometry is reasonable. Research may eventually find that this combination deserves a **LONG** hypothesis.
- **Case B:** The same-looking double bottom forms while BTC is plunging and the coin is weak relative to BTC. It may fail more often or create excessive downside, suggesting **NO TRADE**.
- **Case C:** A purported double bottom appears inside an unresolved range with unreliable quotes, little liquidity or excessive costs. NBOT should **ABSTAIN**, even if the visual pattern looks attractive.

Only verified future-outcome evidence can tell NBOT whether these descriptions actually separate better trades from worse ones. **Do not hardcode the illustrative conclusions as trading rules.** A structure that *looks* like a double bottom must also meet an explicit, versioned detector/confirmation definition before Learning can count it as such.

### 3. What Learning needs from each virtual trade

A useful learning example joins **the original decision-time context** to **the later verified outcome**:

- Market event and time, coin, side and unique hypothesis identity.
- BTC regime and overall market/breadth state **as known then**.
- Coin structure and structural confirmation, including detector version and matched tags.
- Relative strength/correlation, volatility, liquidity, quote freshness, and cost/risk geometry.
- The entry/stop/target/timeout policy frozen **before** the outcome.
- The future original price-path and source evidence, appropriate quote/cost/funding proofs, maturation time, and result **net of costs**.
- Outcome quality status, evidence grade, event/regime dependence group, experiment version and code/model provenance.

Learning must not use a future candle, later BTC movement, revised structure label, finalized funding figure or matured trade result as an **input to an earlier trading decision**. Those later facts may be outcome evidence only. Hold unresolved or insufficient-evidence cases outside qualified training labels, while keeping them visible for honest denominator and missingness analysis.

The same coin movement may satisfy multiple detectors. **Count one uniquely defined virtual experiment once**, not once per detector tag. Simultaneous coins and LONG/SHORT alternatives can share a BTC-driven shock and must not be treated as independent proof.

### 4. What Learning is actually trying to discover

Over enough independently qualified outcomes, the system should estimate things like:

- Under **which** BTC and market conditions is a breakout LONG worth considering?
- When is the identical breakout too risky, too costly, or more likely to fail?
- Do some structures produce more favorable SHORT than LONG results in particular conditions?
- Is a coin's strength or weakness relative to BTC informative?
- Does the same structure work differently in a range, trend or sudden regime shift?
- Are expected returns still attractive **after** fees, spread, slip and funding?
- How likely is a large loss or unacceptable drawdown, not just a winning trade?
- Are apparent successes confined to one coin, one week or one correlated BTC move?
- Is the model confident **enough to trade**, or should it answer NO TRADE?

A learned relationship is useful only if it improves decisions **on later unseen market periods**. If it cannot do so reliably, it stays a research hypothesis.

### 5. Learn without fooling ourselves

The most important safeguards are not additional indicators. They are tests of whether the evidence deserves trust:

1. **Authentic and mature:** only the correctly verified evidence grade enters the qualified dataset. Synthetic laboratory trades validate engineering but never count toward genuine research thresholds.
2. **No future knowledge:** features must be available at the exact event; outcomes must mature before entering any model's training cutoff.
3. **No false independence:** overlapping positions, same-event alternatives, opposite sides and shared BTC shocks are dependence groups, not thousands of independent successes.
4. **Diverse market experience:** include sufficient independent events, coin/side variation, time span and distinct regimes. If all examples come from one BTC rally, uncertainty remains high.
5. **Time-separated testing:** train on earlier data, use proper purging/embargo for overlapping horizons and evaluate on later untouched periods. Randomly splitting highly overlapping rows is misleading.
6. **Conservative uncertainty:** judge whether a positive result is stable and convincingly above costs and the **NO TRADE** benchmark, not merely a positive in-sample average.
7. **Multiple-attempt protection:** exploring many detectors, risk/target combinations and model versions creates false discoveries by chance. Track what was tried and preserve untouched evaluation evidence.
8. **Observe changing conditions:** detect when a once-promising relationship weakens. Unknown regimes, bad sources or deteriorating evidence mean **HOLD / NO TRADE**, not forced retraining or action.

The initial **2,000 genuinely matured virtual-outcome checkpoint** defined in the roadmap is a *minimum opportunity to evaluate learning*, **not proof that a strategy works**. If independence, diversity or the after-cost tests fail, keep collecting evidence and do not qualify a Champion.

### 6. Translate learning into a usable decision

For each eligible opportunity, a scientifically qualified model should be able to provide a decision-oriented estimate, for example:

- **Coin and side:** the LONG or SHORT hypothesis under consideration.
- **Conditions:** which BTC/market/coin structure features informed the evaluation.
- **Expected after-cost result:** estimated net R or an appropriately calibrated outcome distribution.
- **Uncertainty:** a conservative confidence estimate or lower bound, plus out-of-distribution flags where applicable.
- **Risk and cost feasibility:** spread, slippage/funding assumptions, stop distance, downside and available position budget.
- **Decision:** **QUALIFIED FOR FURTHER EXECUTION CHECK**, **INSUFFICIENT EVIDENCE**, **UNFAVORABLE**, or **NO TRADE**, together with the reason and frozen model version.

A model that ranks Candidate A ahead of B has **not** necessarily established that either candidate is economically attractive. Learning must allow all candidates to fail the threshold, leaving **NO TRADE** as the right action.

The final decision engine should consider only the **currently approved frozen Champion**, and the independent Execution guardian can still veto it. A model cannot take a second actual position merely because it has found a high-confidence opportunity.

### 7. How Learning gets better over time — Champion and Challenger

**Learn continually; change production behavior cautiously.**

- Initially, Research supplies enough genuine, independently qualified, matured outcomes to attempt rigorous model evaluation.
- If a model passes predeclared economic, uncertainty, causal and review tests, it may become the first **paper-only Champion**. If not, NBOT stays NO_MODEL / NO_TRADE.
- Research keeps receiving new valid outcomes while that Champion remains unchanged.
- After the roadmap's **next additional 2,000 newly matured qualifying outcomes** and the required independence/diversity gates, Learning may propose a **Challenger** trained on an approved earlier data window and checked against separate later evidence.
- The Challenger does **not** replace the Champion because it is newer, has a higher historical win rate or wins a brief streak.
- A qualified Challenger is evaluated prospectively over the same market period as the frozen Champion in **separate, comparable paper books**. Fair paper competition measures true position occupancy, costs, drawdown, abstention and forward net results.
- When the contest produces strong enough evidence under predetermined standards, the system may **recommend** retain, reject, suspend or replace. **Approval is independent; there is no self-promotion into paper or live authority.**
- If the market changes or both policies lose to doing nothing, retain safety and **NO TRADE** rather than forcing a winner.

The roadmap's proposed **100 settled paper-trades-per-model checkpoint** is also subject to a common time period, predeclared maximum window and independent-event coverage. A highly selective model must not be forced to generate 100 trades. Inconclusive results remain inconclusive.

### 8. Paper and actual outcomes also improve Learning—but not as interchangeable labels

Virtual trade outcomes provide broad **counterfactual opportunity learning**.

Paper outcomes help show whether a selected policy can operate in real time, with simulated fill/cost assumptions, risk vetoes, one-position occupancy and restart behavior.

Separately authorized future real outcomes show **what Binance actually filled**, paid/charged and rejected. They may reveal that the virtual/paper cost models are too optimistic.

Learning should use these as **separate labeled evidence channels**. The system should not pool hypothetical, paper and live outcomes as if they were the same kind of trade, nor count a virtual reflection of a real trade as an independent win. Actual trading is only a selected subset of possible opportunities, so real-only results cannot replace the unchosen-opportunity research dataset.

Research and Learning can investigate and propose corrections to assumptions or new Challengers. **They may not directly order, cancel, leverage, liquidate or promote a real model.** Only a separately authorized execution system and policy can manage an actual position.

### 9. What Learning should produce—not just a newly trained model

The output of Learning should be understandable and auditable:

1. A **condition-versus-outcome evidence map**: where there is positive, negative, uncertain or insufficient after-cost evidence by regime, structure, side and cost/risk conditions.
2. A **sample-quality report**: counts of eligible, matured, independently effective, unresolved, censored and withheld cases, with source grades.
3. A **baseline comparison**: no-trade, simple conditions and the existing model, evaluated on comparable opportunity periods where defensible.
4. A **frozen model candidate** with its features, training cutoff, validation results, version, assumptions and checksum.
5. A **plain-language recommendation**: retain Champion, evaluate Challenger further, reject, suspend, or stay NO_MODEL / NO TRADE.
6. A **reason for abstention** when a tempting setup lacks reliable evidence.

NBOT need not discover a magical "best strategy" for every market regime. Success means recognizing where it has enough evidence to act **and where it does not**.

### The Learning vision in one paragraph

**NBOT should learn from genuine, prospectively recorded virtual trades which kinds of coin structures, directions and detector combinations have shown a credible positive return after costs under which BTC and overall-market conditions. It should also learn when these setups fail, when costs are too high and when its evidence is too weak to trade. The learning system should improve selection through independently tested Challenger models while keeping the approved Champion stable, the single actual-position rule intact and all live order authority outside Research and Learning.**

---


## 8C. TRAINING — Product Stage 5: turn what NBOT has learned into a candidate trading model

**The owner's intended step:** After Learning has accumulated credible evidence about which coin structures, directions and patterns behave well under which market/BTC conditions, **Training creates a versioned trading model that can evaluate future opportunities.**

This is the difference between **knowing from research that a type of situation may have an advantage** and **having an explicit decision rule capable of applying that knowledge today**.

### Our seven plain-language product stages

| Product stage | The question it answers | Main output |
| --- | --- | --- |
| **1. Observation** | What is happening across BTC and the watched market? | Reliable time-stamped market-state evidence |
| **2. Exploration** | What coin structures and LONG/SHORT/NO TRADE possibilities are visible? | Complete eligible candidate descriptions and pattern labels |
| **3. Research** | What happened afterward to prospectively defined virtual possibilities, after costs? | Source-verified hypothetical outcomes, or honest missing/pending states |
| **4. Learning** | Which combinations have credible, repeatable positive after-cost advantage and when should we abstain? | Conditional evidence, uncertainty, acceptable/no-edge findings |
| **5. Training** | Can that experience be encoded into a reproducible candidate trading strategy/model? | Frozen model candidate and validation report |
| **6. Evaluator / Promoter–Retainer** | Is a tested Challenger actually better than the current Champion? | Retain/reject/replace/suspend recommendation and approval record |
| **7. Trading Decisions & Position Management** | On the latest valid market event, should the approved model recommend LONG, SHORT or NO TRADE—and may the independent guardian act? | Authenticated proposals, vetoes and separately accounted paper/future live actions |

**Naming distinction:** These seven stages express the **product's understandable learning-and-trading lifecycle**. They are **not** a unilateral renaming or override of the existing engineering/source-governance gates called G1–G7, or the later roadmap's G8–G10 milestones. Existing controls and evidence requirements remain binding unless explicitly revised and approved.

### What Training receives

Training uses mature, approved research evidence and the conditional findings from Learning, including:

- **Features:** BTC and broad-market condition, a coin's time-of-decision structure, relative strength, volatility, liquidity and available pattern-detector labels.
- **Sides and possibilities:** LONG, SHORT and the option to abstain. No-pattern observations may be informative; they cannot become forced trade signals.
- **Economic targets:** verified after-cost hypothetical results, downside outcomes and uncertainty under frozen entry/exit/risk policies.
- **Source/evidence quality:** time stamps, quote and original-price-path provenance, fee/slippage/funding assumptions, and incomplete-outcome exclusions.
- **Dependence information:** overlapping market events, correlated coins, opposite directions and shared BTC shocks, so one market incident does not masquerade as many independent lessons.
- **Experiment rules:** permissible training windows, model families, evaluation metrics, selected features, cost-to-risk limits, no-trade hurdle and approved scientific protocol.

Training must not directly learn from invalid source gaps, uncompleted outcomes or self-created synthetic engineering fixtures as though they were genuine qualified market evidence.

### What a model must actually learn to do

Given an eligible **current** coin-direction opportunity with its current BTC/coin conditions, a model should estimate whether taking it would offer a **credible expected net outcome after costs**, and how uncertain that estimate is.

It can learn relationships such as:

- A confirmed breakout LONG may be more or less favorable in a BTC uptrend than in a BTC volatility shock.
- Some mean-reversion attempts may work only when a coin is ranging, rather than already trending aggressively.
- A structurally plausible SHORT may not be worth taking because spread, funding or downside risk overwhelms its apparent advantage.
- There may be **no sufficiently supported opportunity** across the entire eligible universe.

These are potential **learned findings**, not hard-coded or guaranteed profitable rules.

A good model should be able to report for each considered opportunity:

1. **The applicable context:** coin, side, BTC state, market state, coin structure, detector versions and current source quality.
2. **The economic estimate:** net expected R or properly calibrated return distribution under the declared exit/cost policy.
3. **Uncertainty and downside:** a conservative confidence/lower-bound or comparable robust safety statistic, out-of-regime warnings and drawdown sensitivity.
4. **Eligibility:** whether the data, quote, funding assumptions, risk geometry and cost-to-R constraints are acceptable.
5. **A recommendation:** a particular qualified LONG/SHORT opportunity, or **NO TRADE** with a reason.

A high model score is not automatically a high economic advantage. The estimated after-cost improvement over doing nothing must be meaningful and defensible.

### How a new model is produced safely

1. **Freeze a data cutoff.** No outcome that matured after the cutoff may leak into training.
2. **Check qualified evidence.** The roadmap's first checkpoint of **2,000 genuinely matured outcomes** is an eligibility threshold—not automatic proof of profitable trade selection. Apply independent event/time/regime coverage and sample quality.
3. **Choose a modest candidate model.** Prefer reproducible models and understandable economic/risk baselines over an unlimited search for complex architectures.
4. **Train on chronological data.** Preserve correlations and purge/embargo overlapping hypothetical trade horizons; no random split that lets future-linked evidence reappear as "new" validation.
5. **Test on later untouched periods.** Compare after-cost results against NO TRADE and fair simpler policies, including selection under **one-position** portfolio occupancy.
6. **Stress-test losses and uncertainty.** Recheck fees, slippage, different BTC/market regimes, stale inputs, gaps and abnormal conditions.
7. **Freeze the model artifact.** Record version, code SHA, training-data cutoff, features, parameters, risk/cost policy, validation reports and checksum.
8. **Submit it for independent qualification.** A trained file is a **candidate**, not a Champion and never an order authority.

If the model does not show a credible advantage, keep **NO_MODEL / NO TRADE**, continue observing and improve the research evidence rather than forcing deployment.

### The first model and later updates

The first independently qualified model may become the **initial paper-only Champion** under an explicit owner-approved release. A second model is **not necessary to begin that first Champion-only paper phase** according to the existing lifecycle roadmap; the documented G7 current-code two-model unlock inconsistency must be reconciled in reviewed engineering rather than bypassed.

After a further **2,000 newly matured independent qualifying outcomes**, Training may propose a **Challenger** using approved earlier data and a fixed cutoff. The new cohort is a checkpoint for proposing another candidate, not an excuse to retrain or promote after every recent loss.

**Training creates candidate policies; it must never place virtual-research fills, submit paper orders, execute real trades or promote its own output.**

---

## 8D. EVALUATOR / PROMOTER–RETAINER — Product Stage 6: decide whether the Challenger deserves to replace the Champion

**The owner's idea:** Keep the better strategy as the **temporary incumbent Champion** until stronger evidence shows that a genuinely better model should replace it.

This is sensible, with one safety refinement: **winning is not enough by itself**. A proposed new Champion must pass predeclared, fair after-cost/risk tests and **independent approval**. The stage's normal automatic output is a **recommendation** to retain, reject, suspend or promote—not an unrestricted model self-promotion.

### Why this stage exists

An incumbent model gives us a stable reference. Without it, each new retraining round changes the rules and makes it impossible to distinguish market luck from real improvement.

A Challenger may perform better on its own historical dataset simply because BTC was trending strongly then. The meaningful comparison is **both frozen policies on the same subsequent market period**.

The model comparison should be simple to operate, even if its scientific checks are rigorous.

### How a competition actually works

**A. Candidate qualification before a contest**

- The Challenger must already pass independent offline scientific, source and safety checks.
- Freeze **both** models, their training cutoffs, feature versions and entry/exit/cost assumptions.
- Define the comparison window, starting equity, risk limits, maximum duration, common events, outcome criteria and conditions for an inconclusive result **before** forward outcomes are observed.
- No model may retrain from data generated during its ongoing contest.

**B. One shared market feed, two independent paper books**

- A single approved **Decision/Execution paper subsystem** receives the same eligible real-time event opportunities for both models.
- The Observation-side inference process evaluates those same known-at-time features separately through **Champion** and **Challenger**, producing independent model-specific recommendations, including NO TRADE.
- The Execution-side guardian checks each authorized proposal and maintains two isolated **simulated** books: **Champion Paper** and **Challenger Paper**.
- Each book has its own equity, position budget, orders/fills, stops/exits, losses and accounting. In the proposed practical one-position design, **each paper book has at most one simulated position at a time**.
- Paper books may select different coins, the same coin, opposite sides or abstain. They do **not** create two actual exchange positions.
- They use the same forward clock, source-freshness standard and comparable costs/risk conventions so their results can be fairly compared.
- **One event loop and one paper engine can serve two logical books**; do not duplicate WebSocket collectors, archive data or heavyweight Research pipelines for each model.

**C. Compare the results honestly**

The authoritative roadmap proposes a checkpoint of **at least 100 verifiably settled paper trades per model where possible**, together with sufficient common evaluation time/events and independent BTC/market regimes.

The comparison also needs:

- **Net after-cost results**, not raw win rate or gross profit.
- **Risk and drawdown**, not merely which model earned the most by taking bigger bets.
- Comparable starting equity, risk per trade and capital occupancy.
- Trade frequency, selective abstention, missed opportunities, time in market and unresolved outcomes.
- Robust uncertainty, confidence of superiority and sensitivity to cost assumptions.
- A **common competition endpoint**, even when one model hits 100 trades first.
- Evidence that the differences are not dominated by one correlated BTC market shock.

**Never force a model to take trades merely to reach 100.** If a model is appropriately selective and reaches fewer trades before the frozen maximum duration, record **LOW ACTIVITY / INCONCLUSIVE**, not an automatic loss or unearned victory.

### The Promoter–Retainer decision

| Forward evidence | Decision |
| --- | --- |
| Qualified Challenger convincingly improves after-cost performance under comparable risk, confidence, source-quality and operational rules | **RECOMMEND PROMOTE**, subject to independent owner-approved routing change |
| Champion remains better | **RETAIN** Champion and archive/reject Challenger |
| Both lose money, neither clears NO TRADE, or results are too similar/uncertain | **HOLD / SUSPEND / CONTINUE RESEARCH**; do not promote the "less bad" policy automatically |
| Challenger wins only by larger risk, unfair time window or optimistic fill assumptions | **REJECT / HOLD** |
| Data gaps, timing mismatch, model changes mid-contest or irreconcilable accounting | **FAIL CLOSED**, preserve evidence and review |

**The Champion is temporary in the sense of being replaceable—not short-lived by force.** It may remain Champion through many rejected Challengers. A retired Champion remains available as a verified rollback reference when approved.

### Where the comparison runs—and why it should not stress a VPS

**Do not run a third continuous price collector, model trainer or raw-tick replay for the contest.**

- **Execution VPS:** A single lightweight forward-paper event engine and **two logical SQLite/accounting books** simulate model-specific fills and positions. It receives bounded, signed proposals, validates freshness and uses source evidence efficiently. Real-order code remains absent/locked without separate authorization.
- **Observation VPS:** Produces model recommendations on the already assembled five-minute events using two **frozen inference artifacts**, receives compact paper fills/position/equity reports, and performs small periodic performance comparisons. Only lightweight inference—not training or source replay—belongs on the critical event path.
- **Training:** Runs **offline or resource-limited**, asynchronously from the real-time event processing pipeline, only after a stable evidence snapshot. If testing shows its CPU/RAM load harms the 50-coin collector, move the **offline training job** to separately approved isolated compute, or schedule it more conservatively; do not interrupt or starve source custody, safety or position management.
- **Resource proof:** Measure actual resident memory, CPU peaks, disk growth, database lock contention, time-to-recommendation and quote freshness before commissioning. The small VPSs were previously measured near **1 GiB physical RAM**, so model sizes, buffers and training batches must be bounded. No claim of negligible load without tests.

The comparison is fundamentally **a pair of prospective decision logs and paper-account ledgers**, not a second complete market research platform.

### Important lifecycle dependency

Stage 6 cannot compare paper-trading models without **Stage 7 first producing paper results**.

Therefore, despite numbering, the system is a **feedback loop**:

**Training → candidate/Champion qualification → Stage 7 paper model decisions and simulated position results → Stage 6 fair comparison → reviewed promotion/retention → Stage 7 uses the approved updated Champion.**

The initial Champion can start its **owner-approved paper-only** evaluation once qualified, without waiting for an initial Challenger. Later Challenger competitions use two separate paper books. The documented conflict with the current G7 two-model unlock still requires an explicit reviewed resolution; this vision does not change executable permissions.

**Stage 6 decides which model deserves to become the reference; it does not decide an individual trade and does not send orders.**

---

## 8E. TRADING DECISIONS & POSITION MANAGEMENT — Product Stage 7: apply approved intelligence to today's market

**The owner's intended last stage:** NBOT combines current Observation and Exploration, the intelligence learned by Research and Learning, an approved model created by Training, and a model-selection outcome from the Promoter–Retainer to decide **whether to trade, on which coin, and LONG or SHORT—or NO TRADE**.

This should be the simplest possible operational decision loop, with an independently enforced safety boundary.

### What Stage 7 actually needs

Stage 7 **uses** the outputs of Stages 1–6, but **does not rerun them all on every event**.

1. **Fresh market evidence:** Obtain the latest complete five-minute event, 50-coin eligibility, BTC/overall regime, coin features, quotes and source quality from Observation/Exploration.
2. **A frozen approved model:** Load only the version and exact rules approved for the relevant paper or separately authorized future live channel.
3. **Evaluate current opportunities:** Use the model's trained relationships to assess eligible LONG and SHORT candidates in their **current** known-at-time conditions, including risk and modeled costs.
4. **Compare against NO TRADE:** Require a sufficiently credible conservative positive after-cost advantage. If none qualifies, issue an explicit NO TRADE decision.
5. **Pick no more than one proposed actual opportunity:** If multiple candidates qualify, select the highest eligible opportunity under the frozen policy; that does not mean it will be authorized.
6. **Send a limited recommendation:** Include model/strategy version, market event ID, coin, direction, proposed entry/stop/target/expiry, risk/cost assumptions, confidence, feature/source witness and idempotency identity.
7. **Apply independent guardian vetoes:** Execution verifies the proposal has not expired, that market conditions and available position state agree, that risk/cost/size/leverage limits pass, and that the model/mode is explicitly authorized.
8. **Act only in the authorized environment:** Paper simulation may record a hypothetical fill. A real exchange order is possible **only after a separate later real-money release**, and the global single-real-position rule must pass.
9. **Manage and reconcile the position:** Track stop/exit/timeout, fees and funding where relevant; on restart reconcile actual exchange state rather than assuming a position was flat or closed.
10. **Return results with their real evidence grade:** Paper and actual execution outcomes go back to Research/Learning and model comparison without being mistaken for new independent virtual hypotheses.

**NO TRADE is an actual decision**, not a failure or a requirement to choose the second-best alternative.

### Where virtual, paper and real trades should occur

**Do not put all three trade types into one mixed account or one authority boundary.** They answer different questions.

| Activity | Where it belongs | Purpose and authority |
| --- | --- | --- |
| **Virtual research trades** | **Stage 3 Research on Observation VPS** | Track frozen prospective LONG/SHORT experiments for learning, with verified hypothetical after-cost outcomes. **No actual order and no paper position authority.** May have many overlapping eligible virtual hypotheses because they do not consume real capital. |
| **Initial Champion Paper** | **Stage 7 paper engine on Execution VPS** | Prospectively rehearse the qualified approved Champion's decisions and simulate at most one open paper position in the Champion book. Explicit **paper-only** release required. |
| **Challenger Paper** | **Same Stage 7 paper engine; separate Challenger book** | Fairly compare frozen models using the same forward market period, independently simulated positions and accounting. Each book has its own one-paper-position constraint. A second paper book does **not** create another actual Binance position. |
| **Future Champion Paper Mirror** | **Same Execution paper subsystem, distinct book** | After separately approved live deployment, replay the **same Champion intent and timing** for paper versus actual execution-quality comparison. Not a surrogate actual fill. |
| **Future Champion Live** | **Separately authorized Execution VPS real-order subsystem** | Only approved Champion plus independent risk/position guardian. Enforce **one actual open Binance position globally**, including pending orders, partial fills and unresolved exchange state. Real orders remain prohibited until explicit separate authorization and safety acceptance. |

All modes can share **read-only, verified market-data references and model inference outputs**, but must keep **distinct position ledgers, fill assumptions, risk/accounting state, authority and failure isolation**.

No research virtual trade is a real fill; no paper fill is a live fill; no realized live trade is independent of its corresponding paper mirror.

### Why the decision engine should not be identical to the trading executor

**Approved model inference (the "brain")** remains on Observation VPS. It uses the current market event and approved Champion to **recommend** LONG, SHORT or NO TRADE. A frozen Challenger can independently recommend only for its authorized test book.

**The Execution guardian (the "hands and brakes")** remains on Execution VPS. It alone can permit the appropriate simulated action—and, after a future separately scoped real release, place/manipulate actual orders.

The guardian has an unconditional **VETO**, never a mandate to find a trade. It cannot invent alpha, silently substitute a different model, or bypass stale/unknown source information to stay active.

A new Challenger, even if it looked promising during yesterday's retraining, cannot control the actual position without the complete model review, fair comparison, approval and deployment controls.

### The ONE actual position invariant

If any actual position or pending/unknown real order exists across any coin/direction:

- No new real-entry recommendation may create a second exchange exposure.
- Stage 7 may still **observe, explore, maintain Research virtual outcomes and generate paper-contest results** because these do not create actual exchange positions.
- An uncertain/restarting position must be independently reconciled against actual exchange evidence before declaring the slot free.
- Existing approved real position management must follow its protected stop/exit/emergency policy even if Observation loses connectivity; **no fresh-entry trading** on stale proposals.

This is a single-position trader attached to a broad learner—not an enterprise multi-portfolio real trading system.

### What changes during Champion and Challenger competition?

Very little in the real-time infrastructure:

- Observation computes **two frozen model inferences** from the **same observed candidate event**: one Champion, one Challenger.
- Execution receives two separately authenticated **paper-only** recommendation streams and accounts for them in two logically separate paper books.
- Stage 6 reviews **small, immutable paper outcome summaries**, not duplicate market-data collectors or enormous per-candidate replays.
- The active Champion used for any separately approved real trade **does not change during the competition**.
- If the Challenger is credibly better, Stage 6 submits an approval recommendation; only the authorized owner-controlled release process can change active routing.
- If either model finds no edge, it may abstain. **NO TRADE** remains valid in either paper book.

### Keep the real-time workload minimal

On each valid five-minute decision event:

**Read known-at-time features → score approved models → choose qualifying proposal or NO TRADE → independently risk-check → account for authorized paper or future real position.**

This should not involve training a new model, rescanning full tick archives, duplicating 50-coin WebSocket connections or holding huge raw histories in RAM.

As a concrete operating principle, **research and training can run on delayed, bounded work queues, while source observation and actual position safety retain priority**. Measured latency and hardware load—not assumptions—must determine final process limits.

### Example: how the full loop fits together

Suppose Exploration detects a confirmed range breakout LONG in coin A, a possible reversal SHORT in coin B and several unattractive setups. Observation records the current BTC trend and volatile market conditions.

**Research** already contains verifiable virtual outcomes for similar combinations. **Learning** has estimated which conditions historically showed positive after-cost advantage, and **Training** has frozen a Champion plus a newer Challenger candidate.

At the current five-minute event, **Stage 7** asks the approved Champion to score all eligible coin/direction alternatives. The Champion may propose coin A LONG—or return NO TRADE because the cost/risk-adjusted confidence is too weak.

The **Execution guardian** may still reject coin A if spreads have widened, the quote is stale, or the single actual position is already occupied. Research continues to track eligible unselected virtual opportunities regardless.

During a qualified paper contest, the Challenger could instead recommend coin B SHORT. Each paper book simulates its own at-most-one position using the same forward source environment. **Stage 6** later decides whether the Challenger deserves a reviewed promotion based on full, comparable, settled after-cost paper evidence—not merely one winning trade.

The model can change through evidence and approval, **without the operational bot being rebuilt each time**.

### Product acceptance for Stage 7

The product is operationally ready for its *permitted mode* only when testing proves:

1. Every recommendation is tied to a frozen model, source witness, event time and valid mode approval.
2. Source gaps and stale information produce HOLD / NO TRADE, not guesses.
3. The model cannot command order authority or create additional positions itself.
4. Paper books have independent accounting and reconcile correctly after restart.
5. Future real-order controls reject second positions, duplicate/stale orders and uncertain exchange state.
6. Model comparisons cannot feed their own outcomes back into the frozen competitor mid-contest.
7. Restart, funding/cost mistakes, latency, duplicate messages and memory/disk pressure fail safely.
8. None of these tests changes the user's currently stopped/unreleased application services or grants live authority.

**The simplest useful architecture is ONE observation/research/learning pipeline, ONE active approved Champion policy, a controlled stream of Challenger candidates, ONE guarded paper/execution subsystem with separate logical comparison books, and at most ONE actual open position if real trading is ever independently authorized.**

---


## 8F. Practical operating design: original 50-only proposal (see newer provisional §8G)

**Status:** Earlier planning proposal retained for historical context. The newer §8G now proposes **100 observed → 20 deeply researched → up to 40 active virtual research trades → one actual position or NO TRADE**. The old per-event virtual-start limits in §8F have been superseded by §8G's **vacancy-based five-minute refill**. Neither policy is an operational approval.

**Prospective architecture proposal, 15 October 2026.** The owner has agreed to the seven product stages. This section makes the next design decisions concrete, before final engineering and operational failure rules are implemented. The parameter values below are **proposals to test and approve prospectively, not already validated thresholds or claims of completed code**.

The stages remain **Observation → Exploration → Research → Learning → Training → Promoter/Retainer → Trading Decisions**. Feedback and Continuous Improvement connects them; **it is not an eighth continuously running service**.

### A. Choose the 50-coin universe by tradability, not by recent price gains

**Decision: reserve 1 research slot for BTCUSDT, then select up to 49 suitable altcoin USDT-M perpetual markets.** BTC serves as a coin candidate and mandatory context. Watch fewer markets if fewer meet the criteria; never pad the list with poor-quality coins.

1. **Contract eligibility first:** Binance USDⓈ-M, USDT-quoted, USDT-margined, currently TRADING PERPETUAL contracts. Reject invalid, unsupported, suspended or delisting markets. Preserve the as-of-event contract snapshot.
2. **Liquidity and capacity second:** Sufficient reported 24-hour USDT quote turnover, reasonable executable bid/ask spread, and book depth relative to the **small future position size**. Order-book depth is not a guarantee of fill.
3. **Reliable history:** Enough verified finalized candles for the active feature lookback, independent BTC and per-coin source health, and a sufficiently established listing history. Stale, missing or conflicting information is an eligibility HOLD, not silently assumed healthy.
4. **Ranking:** Among those passing the gates, rank by available **24-hour USDT quote turnover**, breaking ties deterministically by symbol; take up to 49 non-BTC names. **Do not rank by yesterday's gains, by which patterns just won, or by future information.**
5. **Frozen cohort and version:** Record exact selected members, time, input sources, all rejected reasons, selection policy version and a cryptographic digest. No later market outcome may rewrite past universe membership.

**Initial engineering-test thresholds, to review before actual commissioning:**

| Screen | Proposed initial value | Caveat |
| --- | --- | --- |
| 24-hour quote turnover | At least **20 million USDT** | Unvalidated starting screen; benchmark against genuine market availability |
| Spread | Valid 30-minute median **≤15 basis points**, 95th percentile **≤40 basis points** | Missing snapshots cause HOLD; spread can widen suddenly |
| Executable-side depth | Test whether available displayed depth is **≥20× the prospective order notional** | Define depth-price band first and verify against actual order-size policy; no execution guarantee |
| Listing maturity | At least **30 days** where listing age is independently verifiable | Adjust only prospectively; preserve evidence of recently listed markets |
| Historical/stream data | All currently required feature history complete; valid final candles and trade/quote source health | Current simple 96-bar bootstrap is not proof of every desired longer lookback |

**Cohort lifecycle decision:** Start with a **frozen seven-day research epoch**, check each member's health daily, and quarantine any newly ineligible member without stealth replacement. Re-evaluate and sign a prospective new cohort at a reviewed weekly boundary. Stop admitting new four-hour virtual experiments in time to settle the previous epoch's obligations; never discard active original-path requirements merely to rotate the watchlist. Source and quota effects of this rollover must pass offline engineering tests first.

**Current code versus proposal:** The existing selection in nbot/v5/public_market.py prioritizes eligible USDT perpetual symbols using 24-hour quoteVolume; G1 maintains one frozen cohort per database. The spread/depth/listing screens, explicit reserved BTC slot and safe seven-day cohort rotation described here **still require implementation and tests**. Never silently rewrite the existing frozen G1 cohort.

### B. Classify ALL opportunities, but open only eligible virtual experiments

**Observation outputs:** One timestamped event per completed five-minute boundary, the chosen cohort digest, source integrity and quality, BTC market state, cross-market breadth, each coin's trend/range/volatility/structure and coin-BTC relationship. Relevant statuses are **OBSERVED / SOURCE_HOLD / UNSCORABLE**, with specific missing-data reasons. BTC states may include trend up/down, range, shock up/down, transition or UNKNOWN under a versioned classifier.

**Exploration outputs:** For **each of 50 coins × both directions**, up to **100 coin-side candidate records per five-minute event**, including:

- Explicit LONG and SHORT possibilities, with NO TRADE/rejected reasons and no inferred economic advantage.
- The states of **all 24 original pattern detectors**, for example MATCH / NO_MATCH / UNAVAILABLE, plus the exact detector version.
- Coin price structure, optional causally defined **FORMING / CONFIRMED / FAILED / UNCERTAIN** states, BTC/market conditions and time-of-decision features.
- Eligibility, source and quote witnesses, risk/spread/liquidity descriptors, all known-at clocks, event ID, unique candidate ID and source/hash references.
- A candidate with five matching pattern tags is **one coin-direction observation**, not five independent winning strategies.

**Research outputs:** Only predeclared, eligible hypotheses become virtual trade experiments. Each has a frozen entry convention, stop, target, horizon, initial R, economic assumptions, BTC/coin/detector labels and source identity **before** future prices arrive. Later results are **PENDING, SCORED, PATH_ONLY, CENSORED, UNRESOLVED or HOLD** under the applicable frozen ledger policy. A source-only stop/target path is not an independently qualified after-cost label. A verified hypothetical quote-constrained net return is not an actual Binance fill.

**Research workload choice:** Avoid automatically starting all 100 possible direction experiments every five minutes or a separate virtual trade for every detector. Start offline design/testing with **at most 10 new virtual intents per five-minute event**, chosen by a predeclared deterministic **stratified policy** from the complete 100-candidate population. Ensure coverage of LONG/SHORT, multiple coins, BTC/coin regimes, different detector families, no-pattern controls and rejected as well as favored opportunities; record inclusion probabilities and unselected candidates. Allow fewer or zero when ineligible. This is a **provisional scientific and resource budget, NOT a daily trade quota**. Test sample bias, regime coverage and throughput before final approval or changing the cap.

With a frozen **four-hour maximum horizon**, 10 starts per five-minute boundary yields up to approximately **480 overlapping active virtual intentions**, allowing for early exits. These are hypothetical studies, **not 480 simultaneous real or paper positions and not 480 independent research samples**.

**Learning labels:** Qualified virtual results must join their *original decision-time* BTC conditions, broad-market regime, coin structure, direction and detector states to the **later** source-verified net outcome. Separate experiment grade, source quality and temporal/dependence groups. Never use future features to make yesterday's decision or double-count overlapping pattern tags. The roadmap's 2,000-outcome checkpoint remains a minimum evaluation gate, not automatic proof of advantage.

**Paper and future live labels:** Keep **different evidence-grade ledgers** for model proposals, NO TRADE, risk rejects, paper simulated open/close and unresolved states, and separately authorized future exchange-confirmed requested/acknowledged/partial/filled/closed/reconcile states. Every simulated book may hold at most one simulated position under the proposed competition rule, while actual authorized execution would enforce **one real open position globally**. Do not treat parallel paper books as parallel real positions.

### C. Store data in three layers, without per-frame SQLite writes

**Decision: maintain compact RAM state, durable event/decision ledgers and independently auditable compressed original source segments.**

| Data | Where it belongs | Reason |
| --- | --- | --- |
| Most recent valid quote, last trade cursor, feed health, recent candle ring | **Bounded RAM** | Low latency; thousands of updates replace one latest-state slot |
| Finalized five-minute candles and independent source confirmations | **Durable immutable candle/event database** | Replayable market and pattern context |
| Every complete event's 100 candidate/detector states | **One compact transactional research batch** | Preserve the full choice set without per-frame writes |
| Frozen virtual plans, progression/terminal status, scientific approvals | **Separate small durable research ledger** | Idempotent restart and transparent outcomes |
| Original trade sequence needed to prove first stop/target across a virtual horizon | **Lossless compressed/hash-verified source files or an independently verified equivalent** | Five-minute candle OHLC cannot prove which barrier was hit first |
| Entry/exit bid/ask and mark/funding/cost witnesses | **Timestamped durable receipts linked to original source and cost policy** | Needed for independently qualified after-cost outcomes |
| Finalized Champion/Challenger paper actions, fills and accounts | **Two independent small event-sourced paper ledgers** | Fair comparison and restart reconciliation |
| Unclosed candle updates, redundant display state, ephemeral health counters | **RAM unless required by a declared evidence contract**; persist epoch/gap incidents | Avoid useless permanent writes |

**Important qualification:** Current V5 G4 **does persist every received raw frame on its subscribed aggTrade, bookTicker and mark/funding routes**—but into **batched, gzip-compressed, hash-chained files**, **not one row per frame in SQLite**. It does **not** eliminate disk use; a finite cap still exists. Changing raw quote/price-source retention needs an independently reviewed proof of which evidence is sufficient. We must not sample or discard necessary first-touch trade events while pretending the path remains complete.

**Microbatch design:** Reuse the existing segmented source recorder's approximate **five-second flush interval, 2 MiB pending-byte ceiling and 2,048 pending-frame budget** as initial engineering settings, with bounded memory, file syncing, immutable manifests and verified segment hashes. The tail awaiting flush is explicitly **not crash-durable**. A separate RAM ring holds the latest 96 completed five-minute candles per coin; validated finished candles also go to the immutable ledger. Active virtual hypotheses should be advanced by **one shared per-symbol trade-stream pass**, with indexed replay or checkpointing for auditors—not a giant SQLite table and not one full-archive rescan per hypothesis.

**Storage must be honestly budgeted.** If complete 50-market aggTrade and quote evidence exceeds a small VPS's disk, we must either add approved, independently verified off-host custody, limit/scientifically declare which hypotheses receive high-grade source collection, or hold admission when resources are exhausted. We may not discard original evidence merely to make a green result. Report actual frames/second, bytes/second, compression ratio, per-day growth, CPU, RAM and recovery throughput in offline synthetic stress tests and later owner-authorized prospective measurements. No fixed GB/day estimate is supported yet.

### D. What happens after a disconnection, crash or restart?

**Do not treat RAM as a backup.** If a process dies before the next verified disk checkpoint, the tail can be lost. Neither a saved latest price nor a candle replay automatically reconstructs the missing trade sequence or bid/ask history.

**Recovery protocol:**

1. **Begin locked/HOLD**, with no new scientific labels or unauthorized paper/live entries.
2. Verify the original SQLite ledger, source-chain hashes, immutable manifests, finished segments and last committed event/intent IDs. Reject damaged or temporary segments; do not "repair" evidence by inventing records.
3. Explicitly record a **new source epoch and ABRUPT_RESTART_HOLD / SOURCE_GAP** from the last durably known-good receipt to newly verified source continuity. The true interruption start may be unknown.
4. Recover **closed five-minute candles only** from appropriate public REST sources using strict as-of windows and independent overlap checks. Never claim REST candles repair missing quote updates or original aggregated-trade chronology. If separately recovered aggregate-trade history is available, require full ID/time/source verification and record its **distinct recovery grade**; do not assume guaranteed availability.
5. Restore bounded RAM features from verified candles and fresh live quotes/trades. Wait until BTC and each relevant coin have healthy feed/source epochs before accepting new original-grade virtual observations.
6. Resume previous **durable virtual intents** idempotently only where the *entire* intervening source chronology has been independently proven. If missing data could have hidden a stop, target or quote change, classify affected outcomes **UNRESOLVED/CENSORED/HOLD** rather than a winning or losing qualified sample.
7. Reconcile paper book balances and simulated open positions from the separate append-only ledgers, and independently verify approval before enabling any new paper action.
8. For **future** separately approved real trading, reconcile exchange-side pending orders/partial fills and the actual open position before treating the single real-position slot as free. The guardian preserves the defined emergency management path for an already open authorized real position even if new-entry research is locked.

**A five-second gap might matter more than four hours of correct candles if stop and target could both be crossed during the missing interval.** NBOT must prefer an unresolved result over a fabricated one.

### E. Continuous storage: sealed segments and independently verified archival

The existing compressed source cap is bounded (up to **8 GiB** in the current G4 collector); it is **not** a proven indefinite 50-coin retention solution.

**Proposed custody lifecycle:**

1. Bounded writer seals compressed, independently hash-checkable segments; maintain immutable source epochs, min/max times, per-symbol indexing and checkpoint receipts.
2. Keep every segment necessary for an **unmatured** virtual experiment accessible, plus the required independent review/retention interval.
3. Export **sealed** source segments to a separately approved durable off-host archive; independently verify content hashes and chain manifests; periodically test replay/restore from the replica.
4. Only after confirmed independent custody, policy-compliant retention and absence of active research dependencies may local source be relocated/pruned by an explicitly authorized process. **Never delete the only verifiable original or break its chain of custody.**
5. If disk headroom, archive replication or write latency fails, **stop admitting new high-grade virtual experiments and label affected source HOLD**. Do not silently reduce original-market evidence grade or substitute candle-only net results.

The owner has **not** selected an archive provider, storage budget or deletion approval policy. Those require separate review. Until then, finite G4 capacity is an engineering HOLD, not permission to run indefinitely.

### F. Allocate jobs to two VPSs without seven heavy services

**Observation VPS:** one validated market intake for 50 coins; one bounded candle/candidate ledger; one compressed original research-source writer; a shared per-symbol virtual-experiment updater and durable maturity queue; periodic bounded economic review, Learning and Training on *off-critical-path* immutable snapshots; lightweight inference of frozen approved Champion/Challenger models on each valid five-minute event; compact signed recommendations and feedback processing.

**Execution VPS:** one independent proposal/risk/position guardian and one paper engine holding **two logical, isolated books** only when separately approved for competition. Paper books use the same verified market timeline but have independent cash, risk, positions, accounting and model identity. Do not train models, re-run G4 virtual research, or create a second 50-market archive on Execution merely for comparison. Any future real order capability remains separately locked and governed.

**Stage 6 comparison:** receive **small immutable settled paper/equity/rejection summaries** on Observation, compare frozen models using shared-clock/risk/after-cost evidence, and recommend retention/replacement. Heavy training and replay must never run in the collector/position-safety deadline. If offline training is too expensive for the approximately **1 GiB RAM** VPS, constrain/schedule it or move **only that offline job** to separately authorized isolated compute—without adding a continuously running trading VPS.

**Resource admission control:** give source intake and any authorized existing-position management priority; bound source queues, active virtual intents, write frequency, dataset size, training memory and time-to-recommendation; use backpressure or scientific HOLD if limits cannot be met. Quantify resource sufficiency with offline load/crash tests instead of guessing.

### G. Failure responses to formalize before service commissioning

| Failure/condition | Required minimum response |
| --- | --- |
| BTC/coin quote or trade source stale, disconnected or corrupted | NO TRADE / SOURCE_HOLD; quarantine affected events/intents |
| Candle or source ID gap; restart before last RAM tail was synced | New source epoch + documented unknown interval; original trade path cannot be inferred |
| Structure not confirmed or one of 24 detectors has missing prerequisites | FORMING or UNAVAILABLE; never fabricate a MATCH |
| Expected after-cost economic advantage is absent or uncertain | NO TRADE, even when several patterns match |
| Stop-vs-target order cannot be proven from source | UNRESOLVED/HOLD, not SCORED; no invented net-R label |
| Entry/exit quote, fee, slippage or settled funding evidence insufficient | HOLD economic qualification; never default unknown cost to zero |
| Archive full, replication failure, unsafe disk/RAM pressure | Stop new virtual admission, preserve existing immutable source, signal storage HOLD |
| Too few independent genuine virtual outcomes, poor regime coverage or weak validation | NO_MODEL/NO TRADE or keep frozen Champion; no scientific promotion |
| Challenger loses, both paper books lose, or competition is inconclusive | RETAIN / REJECT / HOLD; never promote the "less bad" strategy automatically |
| Wrong model, stale signed recommendation, duplicate proposal or lost paper approval | Reject and record; no execution |
| Paper account/position mismatch after restart | Reconcile before allowing new paper entries |
| Any unknown real order/open position or proposed second actual entry | Independent Execution VETO; at most one real position globally |
| Observation unavailable while an approved real position is open | No new entries; independently defined conservative real-position safety/reconciliation |
| Training or archive job threatens feed latency | Slow/stop noncritical jobs, never starve source intake/position guardian |

These are **minimum design principles**, not claims that every failure path has been fully implemented, passed endurance tests or received an owner-issued release.

### H. Tests required before these proposals become operational rules

1. A frozen 49-plus-BTC selection fixture proves all screens, no padding, explicit rejected reasons, event-time membership and safe weekly epoch closure/rotation.
2. An exact **100 coin-side observation denominator** on a complete 50-coin event proves all 24 detector states with causal known-at clocks, including UNSCORABLE records.
3. A reproducible, diversity-aware virtual-intent sample with a bounded active set proves fair selection among all eligible opportunities and correct inclusion probabilities.
4. A single synthetic-only **full observation → exploration → original-format virtual price path → independently verified after-cost research → Learning → Training → paper decision and model comparison** runs without manual insertion of prequalified data. Synthetic grade never becomes genuine scientific authority.
5. Crash immediately before and after source flush; missing quotes/ID continuity; segment corruption; disk-full and restart all fail closed, preserving the last authentic segment/event and correct UNKNOWN/HOLD states.
6. Stress a representative continuous 50-coin source load with many overlapping virtual hypotheses; report **peak RAM, CPU, disk writes, source growth, processing backlog, restart time and independent source audit**.
7. Archive sealed segments off-host with independently verified restore and no active virtual-path source loss, or report storage capacity as HOLD.
8. Verify first-Champion-only paper release and later dual-paper contest under independently approved rules, separate paper cash/positions, abstentions and one position per book; **no real money authority or service startup** during offline engineering.

**Implementation boundary:** The source already includes simple 24-hour-volume initial selection, frozen cohorts, a complete two-sided candidate journal, bounded latest-state RAM rings, verified final-candle persistence, compressed G4 source segments and fail-closed restart markers. The **full new 50-market quality screens, weekly cohort rotation, predeclared sampling process, off-host rotation and automatic qualified after-cost G4→Learning handoff remain proposed/unimplemented or unaccepted** under the latest engineering evidence. Do not report this vision section as engineering completion.

**Guiding rule: observe broadly, label all possibilities honestly, research an explicitly selected subset with adequate original evidence, learn only from genuine qualified outcomes, compare models on fair forward results, and permit no more than one separately authorized real position.**

---

## 8G. Preferred simplified architecture: 100 observed → 20 researched → one actual position

**Prospective product decision, 15 October 2026.** The owner proposes reducing broad Observation from 200 to **100** coins, and deeper Research from 50 to **20** coins, so the existing small VPSs need fewer feeds, less original source storage and less simultaneous state. **This 100 → 20 → 1 design supersedes the earlier 200 → 50 discussion in this section.** It is a preferred architecture for offline engineering tests, NOT an implemented change, engineering signoff or authorization to start services.

### A. Choose 100 broad observation coins

Select up to **100 unique, eligible Binance USD-M USDT-margined and USDT-quoted TRADING PERPETUAL markets**, with BTCUSDT mandatory for market context.

Use a provisional, deduplicated mix of **50 high-24h-USDT-turnover coins, 25 top percentage gainers and 25 top percentage losers** (as known at selection time). A coin may belong to multiple groups; preserve its category tags but never count it twice. Apply common liquidity, spread, adequate history, source-quality and exchange-status screens **before** considering it. Fill missing positions with other already-qualified liquid markets under a documented deterministic ranking, or observe fewer than 100 if the market cannot support 100 valid names.

Top gainer means **interesting momentum**, not BUY. Top loser means **interesting weakness or reversal**, not SHORT. Do not use subsequent price movement to rewrite prior list membership.

Keep this tier **lightweight**: validated completed five-minute candles, bounded recent history, BTC and overall-market context, and compact health/selection snapshots. Do not subscribe to or permanently archive every aggTrade, book and quote message for all 100 symbols. Use rate-limited, source-verified broad candle intake and record point-in-time universe changes. The current G1 implementation is **hard-capped at 50**; a separate 100-lightweight intake and safe cohort controls must be engineered and tested, not obtained by increasing a constant blindly.

### B. Explore all 100; select 20 for deep research

For every complete five-minute broad observation event, Exploration describes all 100 coins and **both directions**, up to **200 coin-side observations**. Each observation records: valid source and decision time, BTC regime and sudden moves, overall market breadth/volatility, coin trend/structure/relative BTC strength, verified liquidity and source quality, the states of all **24 original V4 pattern detectors**, plausible LONG/SHORT and explicit NO TRADE or HOLD reasons.

The **Research admission policy** selects up to **20 deep-monitored symbols, including BTCUSDT**, so there are exactly **40 possible coin-direction observations** when all 20 are valid. Selection should be determined by:

1. **Reliable original source and tradability**: safe contract, liquid book, acceptable spread, adequate finished candles and fresh quote/trade/cost evidence.
2. **Interesting causal structures and varied regimes**, not maximum detector-match count or biggest percentage increase.
3. **Previously matured qualified economic evidence**, only if available before the shortlist event and scientifically defensible.
4. **Research coverage and diversity**: BTC/coin market regimes, both directions, momentum/reversals/ranges, and some no-pattern or less-studied control opportunities. Avoid 20 strongly correlated coin directions masquerading as 20 independent findings.
5. **A fixed cohort/admission clock and selection audit**: record why coins were included or excluded, source timing, policy version, identities and prospective inclusion probabilities for sampled controls. A new research member needs its own verifiable source warm-up; do not backfill original quote continuity.

The 20 are **the high-integrity research source budget**, not 20 recommended live positions. An eligible new market must not become paper/real trade-ready until independently verified current quotes, costs and risk controls exist.

### C. A rolling pool of at most 40 active virtual research trades — refill vacancies at each five-minute candle close

**Owner's clarified rule (supersedes the old eight-new-per-event proposal):** Research may maintain **no more than 40 simultaneously ACTIVE virtual trades** across the selected 20 deep-research coins. These are hypothetical scientific experiments, **not 40 orders or 40 actual exchange positions**. The number of **new** virtual trades at a review is governed by **available capacity and genuine research eligibility**, not a fixed artificial quota of eight or any obligation to fill all 40 places.

Each coin and both directions are continually explored. A 20-coin deep cohort offers **40 coin-direction possibilities at a five-minute event**. At most **one active virtual experiment per coin × direction** is the proposed simple initial rule; multiple pattern tags on that same hypothesis do not create separate trades. Opposite-direction virtual experiments may coexist solely for research, but they are correlated—not two independent pieces of evidence.

**What happens during the five-minute cycle:**

1. **Between candle closes**, a shared original price/trade-source stream continues monitoring every active virtual experiment according to its **already frozen** entry, stop, target and maximum holding duration. If a stop or target is hit at 10:03, the observed first-touch chronology must be recorded as occurring at 10:03—not assumed to have happened at 10:05 when the next candle closes. The experiment may stop consuming active-path capacity after its terminal first-touch or timeout is **durably and validly established**, while later quote/cost verification proceeds separately.
2. **At each fully closed five-minute candle**, independently verify/reconcile which of the previously active experiments have actually reached a stop, target, time limit or valid other policy-defined terminal state. A missing source path is **not** a verified profitable closure; quarantine it as PENDING/HOLD until the frozen rules permit a documented unresolved/censored terminal.
3. **Count the active research-book slots** after durable reconciliation: **vacancies = 40 − number of still-active virtual experiments**. Never free a slot merely because a database row is missing, a process restarted or a candle looked favorable.
4. **Explore the latest complete event** across the 100 broad observed coins, preserving all valid direction/structure/detector labels. Research evaluates the currently eligible LONG and SHORT alternatives within the **20 deeply monitored source-ready coins**.
5. **Select replacement virtual experiments** only where Research finds suitable, source-qualified, prospectively frozen candidates and permitted unoccupied coin-side slots. Rank/admit under a versioned, diversity-aware policy that includes controls and does not select solely by the 24-detector match count or presumed profit.
6. **Admit up to the number of free slots**; if only three suitable new experiments exist for seven vacancies, start **three**, and leave **four** unused. A full 40-active book starts zero. A book with 40 empty slots can admit up to 40 *only if* 40 distinct coin-side hypotheses genuinely satisfy the frozen eligibility, source and capacity policy.
7. **Commit the resulting decisions and new intents idempotently**, preserving all rejected/unselected possibilities, admission reason codes, source/version hashes and the post-event active count. New virtual experiments must use current decision-time quotes/rules and cannot be assigned fictitious entries at earlier candle times.

**Illustrative review example:**

| Five-minute review at 10:05 | Count |
| --- | ---: |
| Previously active virtual experiments | 40 |
| Verified experiments closed/expired since prior review | 7 |
| Active experiments after reconciliation | 33 |
| Free research slots | 7 |
| Genuinely qualified new coin-side opportunities | 5 |
| New virtual experiments admitted | 5 |
| **Active after review** | **38** |
| Remaining unused slots | 2 |

**The number 40 is a concurrency ceiling, not a target, not 40 starts per five minutes, and not 40 realized after-cost labels per event.** It is perfectly acceptable to have zero, twelve, thirty-eight or forty active virtual experiments. Completed experiment economic results may still be awaiting independent fee/quote/funding verification after the price-path slot becomes free; keep those records pending in the durable research ledger, not in the active-trade book.

**Recovery caveat:** On disconnect, corrupt trade chronology or unsynced-RAM crash, do not claim a previously active experiment closed successfully. Preserve its status, source gap and frozen horizon; resolve, censor or hold it according to a validated causal recovery/terminal policy before reuse of its active slot. Losing proof may reduce the count of *scientifically usable* outcomes even if the resource slot is eventually freed safely.

**Implementation and workload test:** The trial must measure per-symbol shared first-touch processing, 40-active state, five-minute reconciliation, immediate terminal detection between candle closes, idempotent replacement, simultaneous closings, no eligible replacements, BTC/coin source gaps and missing economic witnesses. **Delete the former arbitrary eight-new-per-event admission gate** from the preferred product policy. Operational performance limits may still require bounded batch processing and safe backpressure, but any such technical limit must be derived from offline measurement and must never cause a false virtual result.

### D. Use the same canonical market evidence for Research and Trading Decisions

Do **not** create separate Observer/Explorer systems for virtual, Champion paper, Challenger paper and possible future real decisions.

- One **100-coin Observation/Exploration snapshot** supplies BTC, market and individual-coin conditions to the shared learning architecture.
- Only the **20 deeply monitored, independently trade-ready** symbols can initially generate actionable model proposals. Broad-candle-only coins may be interesting but cannot magically become executable without fresh bid/ask, order-book/size and source verification.
- The **approved frozen Champion** can recommend the single best sufficiently qualified LONG/SHORT from the current eligible pool or **NO TRADE**. The Challenger may make separate paper-only proposals in a qualified comparison.
- The **Execution guardian** independently validates current quotes, model version/approval, idempotency, actual position occupancy and risk/size/cost. Paper Champion/Challenger books have at most one independently simulated open position each under the proposed policy. Future separately approved actual trading has **at most ONE global real position**.

Research and production selection have **different goals**: Research needs a scientifically balanced opportunity sample, whereas the Champion needs the most credible currently qualified economic opportunity. Never let shortlist generation become the same old V4 rule-count popularity ranking.

### E. RAM, permanent source storage and interrupted-feed recovery

**Reducing the number of coins does not justify discarding the evidence a virtual result depends on.** Use a bounded three-layer design:

| Layer | Stored data and recovery role |
| --- | --- |
| **Small RAM windows** | Most recent quotes, completed-candle rings, source/feed health and active virtual-path state; rebuild only from authentic durable or new source |
| **Immutable compact ledger** | Closed five-minute candles, 200 broad/40 deep directional labels, cohort decisions, virtual intents/results, processing cursors and paper books; **not one SQLite write per WebSocket frame** |
| **Compressed original source segments** | Relevant **complete** high-frequency aggregated trades, quote and mark/funding evidence for the 20 deep-source symbols, losslessly recorded in bounded RAM microbatches and checksum/hash-linked durable files |

One per-coin source stream should serve all the eligible active virtual hypotheses for that coin. Do not create 40 redundant WSS connections or replay the full original archive individually for each candidate. The current compressed G4 recorder already avoids individual frame-per-row SQLite inserts, but its finite disk cap still needs proper sealed archival, rollover and verified restore.

**Crash or interruption:**

1. Begin in LOCKED/HOLD; validate durable SQLite, source manifests and complete hash-chained segments. Detect any unsynced RAM tail and mark an explicit disconnected/restarted source epoch.
2. Restore **finished candles** from source-overlapping Binance historical candle data when valid. Preserve the distinction between recovered candles and missing original trade/quote evidence.
3. Where available, independently recover **complete original Binance USD-M aggregated trades** with validated sequence/clock/identity before allowing an original first-stop/target verdict.
4. Historical **one-second candles**, if actually supported by the specific Binance USD-M Futures endpoint and available for the time/symbol, can repair coarse price **context**; they cannot reveal whether target or stop was touched first **within** a one-second candle when both were crossed, and cannot reconstruct original executable bid/ask, actual fills or missing funding receipts.
5. A virtual intent dependent on an unverifiable interval becomes UNRESOLVED/CENSORED/HOLD, not a scientific win/loss or qualified after-cost outcome. Reconnect to fresh verified BTC and relevant coin quote/trade sources before new original-grade work.
6. Independently reconcile the two paper books and any later separately authorized actual order/position; an unknown real position makes the one-position slot **occupied until proven otherwise**.

Full original evidence needed for ongoing intents must remain verifiable. Stop new virtual admission if disk headroom or independent archival custody fails; never silently overwrite or prune the only source copy.

**External factual verification required:** Binance USD-M Futures common references may recognize a 1s interval while particular historical kline endpoints list different allowed intervals. Confirm actual exchange endpoint support, history depth and rate limits **before** promising automatic one-second recovery. Spot 1s candles are not a substitute for futures market prices.

### F. Split the workload without adding new heavy running services

| Work | VPS | Design |
| --- | --- | --- |
| Observe 100 markets and explore 200 coin-directions | **Observation** | Lightweight finalized candles, bounded feature history, event batches and no 100-symbol raw-tick archive |
| Deep 20 original-source markets, up to 40 active virtual experiments | **Observation** | Bounded source writer, shared per-symbol incremental trade-path updates, durable intent/economic labels |
| Learning/Training | **Observation, or separately approved offline compute if load testing requires** | Batch offline from immutable qualified snapshots, outside real-time collector deadlines |
| Approved Champion/Challenger inference | **Observation** | Lightweight fixed model evaluation of the same market event |
| Paper orders, stops and separate accounting | **Execution** | One guarded paper subsystem, two independent logical books when a comparison is authorized |
| Stage 6 model comparison | **Observation** | Small reviewed paper/equity/decision summaries, not a duplicate raw market collector |
| Future separately approved real execution | **Execution** | Independent risk veto, exchange reconciliation and at most one real position |

The main reduction is likely in **deep high-frequency trade/quote source I/O and archives** when going from 50 to 20, though high-volume BTC may dominate actual load. The RAM savings from fewer broad candle windows are real but may be modest; paper book RAM is mostly determined by the number of open simulated positions and accounting history, not 20 versus 50 watched symbols.

### G. Offline engineering acceptance before activating services

1. **100-market selection:** Valid exchange membership, deduplicated top-turnover/gainer/loser cohorts including BTC, exclusion reasons, timestamps, and causal full 200 coin-direction Exploration records. Invalid inputs produce explicit HOLD.
2. **20 deep-source admission:** Verify liquidity/cost/source prerequisites, BTC mandatory context, diverse regime controls, frozen shortlist and 40 directional possibilities without creating 24 separate trades for every detector.
3. **Virtual control:** Verify the rolling max-40 active book and one-per-coin-side constraint; detect actual stop/target first touch between candle closes; at each completed five-minute event reconcile genuinely ended experiments, calculate verified free slots and admit **only source-qualified replacements up to capacity**. Test simultaneous exits, 40 available eligible replacements, fewer eligible replacements than vacancies, all 40 occupied, restart gaps, idempotent records, NO TRADE and the complete candidate denominator; **no fixed eight-new-per-event quota**.
4. **Performance:** Offline synthetic 100 broad / 20 deep event-stream, many active virtual intents; measure maximum RSS, CPU, event latency, raw source disk growth, replay cost, archive sealing and restart.
5. **Recovery:** Crash before/after the compressed segment flush, corrupt source, missing aggregate trades and ambiguous 1s candles; no unverified original after-cost label after any source gap.
6. **Full integration:** One synthetic-grade Observation→Exploration→Research→Learning→Training→Champion/Challenger→Paper path, with genuine-original grade locked until independent source/economic acceptance.
7. **Paper / real safety:** Champion-first separately authorized paper stage, later two separate one-position paper books, model comparison, frozen releases and independent one-global-real-position refusal contract; no real exchange orders or service starts.
8. **Capacity:** Continuous storage rollover and independently verified off-host archive or a clear retention/quotas HOLD; no unapproved deletion or impossible perpetual recording promises.

**Current engineering status:** The presently tested NBOT V5 source was built around 50 monitored coins and 100 directional candidate records. A 100-market lightweight discovery engine, independently selected 20-coin original G4 source cohort and 40-active virtual admission constraints are **design choices awaiting engineering and offline tests**. The 2,000 genuine qualified outcome requirement remains a scientific review checkpoint, not 2,000 mandatory real trades or an automatic training approval.

**One-sentence objective: Observe 100, deeply research 20, learn honestly from up to 40 concurrent virtual hypotheses, choose only one qualified actual position—or NO TRADE.**

---

## 9. Why after-cost return matters more than signal accuracy

The model is not built merely to predict whether a price rises.

A trade can be directionally correct and economically poor. A narrow profit target may be eaten by fees and spread. A tight stop can make relatively small costs very large compared with the amount initially risked.

We therefore express outcomes in **R**, the frozen initial price-risk distance, and separate:

- **Gross R:** hypothetical price-path profit/loss before trading costs.
- **Cost in R:** estimated or verified entry/exit fees, spread, slippage and applicable funding under the evidence contract.
- **Net R:** gross R after the nonduplicated relevant costs.

For an illustrative LONG trade, suppose an entry of 100, a stop of 98 and a target of 104. Initial risk is 2 price units, and the target is 2R gross. If **all properly attributed** trading costs total 0.30 price units, the hypothetical target outcome is about 1.85R net. If the costs are unknown, NBOT cannot honestly assert 1.85R.

This example is illustrative, **not** a market assumption, prediction or verified Binance fill. Costs must not be counted twice if a bid/ask entry/exit convention already incorporates spread.

The model should evaluate an adequately conservative expectation of **net** R, including uncertainty. A historical average that is barely above zero is not automatically enough.

---

## 10. Why NO TRADE is a first-class decision

A bot that is forced to trade will sometimes choose the **least bad** opportunity and call it the best.

NBOT needs a genuinely available alternative: **0R from not entering a position**, apart from any specified idle-capital economics.

NO TRADE may be correct when:

- All candidate expected returns are nonpositive or insufficiently certain.
- Spread, slippage, funding or liquidity makes the entry unattractive.
- BTC conditions are unstable or unknown.
- Source witnesses are stale, gapped or untrustworthy.
- The current Champion has no reliable experience in this regime.
- The single actual-position slot is already occupied.
- Drawdown, exposure, leverage, available margin or other risk limits say stop.

An abstention should be recorded with its reason. The bot can later research whether the rejected opportunities really were poor, but it must not retrospectively invent a trade.

**Success can mean a day of zero trades if conditions were unfavorable.** A quota, daily trade count or requirement to stay in the market is not the objective.

---

## 11. Why NBOT needs training data, and why the first checkpoint is 2,000 outcomes

Machine learning needs historical relationships between decision-time conditions and later outcomes.

For NBOT these relationships should include, at minimum, the BTC/coin regime, side, pattern tags, risk geometry, relevant liquidity/cost evidence and matured **net** return.

The roadmap proposes **2,000 fully matured, source-verifiable virtual economic outcomes** as an initial checkpoint for considering scientific evaluation and model training.

**Why 2,000?** It establishes a meaningful minimum population and discourages promoting a model on a handful of coincidental wins. It is a **proposed process threshold**, not a theorem of statistical sufficiency.

A checkpoint does not pass unless source authenticity, age, diversity, independence, time span, side coverage, risk and predeclared scientific tests also pass.

A first model can fail after 2,000 outcomes. If that happens, NBOT should keep **NO MODEL / NO TRADE** and gather more evidence.

A great many coincident outcomes from one volatile BTC event are not equivalent to thousands of independent market conditions.

---

## 12. What is a Champion model?

A **Champion** is the current **approved incumbent decision model**, not necessarily a profitable strategy and not necessarily a live-money-authorized model.

It exists to give NBOT:

1. A stable, reproducible policy to benchmark.
2. A fixed reference against which new learning can be judged.
3. Consistent behavior during forward testing.
4. A rollback point when experiments disappoint.
5. Protection from changing trading logic after every loss.

To qualify as the first Champion, a candidate model must pass the appropriate independent scientific validation, cost/risk criteria and paper-only release checks. The first 2,000 outcomes merely permit consideration; they do not install a Champion.

Until a credible Champion exists, **NO_MODEL / NO_TRADE** remains legitimate.

A Champion's model version, features, policy, training cutoff and approval must be frozen for the evaluation period. It must not secretly retrain while being judged.

---

## 13. Why train Challengers instead of changing the Champion directly?

Markets change, new source evidence arrives and yesterday's model may become less accurate. NBOT should keep learning.

But directly retraining and replacing the live incumbent creates serious problems:

- There is no stable benchmark to tell whether the update improved anything.
- Recent winning or losing streaks can trigger overfitting.
- A new feature or model defect could immediately affect money.
- Training on outcomes from an unfinished test contaminates the comparison.
- Reverting a bad model becomes difficult without frozen versions.

A **Challenger** is therefore a new, separately versioned candidate model, trained and tested **without disturbing** the current Champion.

The lifecycle is:

1. Freeze and retain the existing Champion.
2. Continue generating legitimate new virtual economic outcomes.
3. After the proposed **next 2,000 newly matured qualifying outcomes**, consider training another Challenger.
4. The Challenger may use other allowed **earlier matured data** under a frozen cutoff; the new 2,000 are not necessarily its only training records.
5. Apply causal, purged and embargoed validation on data not improperly reused.
6. Reject unconvincing Challengers.
7. Evaluate qualified Challengers beside the Champion in controlled forward simulation/paper.
8. Recommend promotion only with credible after-cost/risk superiority and governance approval.

Most Challengers may not deserve promotion. **Rejecting a bad update is a successful feature**, not a failed learning cycle.

---

## 14. Why Champion versus Challenger competition is necessary

Separate historical validation is useful, but market periods differ. A Challenger that makes money in a favorable month cannot be declared better than a Champion measured in a different, unfavorable month.

The fairer question is:

> "On the SAME future market events, under comparable costs, capital, risk and time exposure, would the Challenger have made better decisions than the Champion?"

The authoritative roadmap therefore proposes **two separate paper books sharing one market timeline**:

- **Champion Paper book:** driven only by the frozen Champion.
- **Challenger Paper book:** driven only by the frozen Challenger.

These are **independent simulated ledgers**, not two real-money positions. They can choose different coins/directions or one can abstain while the other trades. Each book must apply its own consistent position limits and use a comparable execution/cost standard.

This competition distinguishes **model quality** from changes in the market.

### What must be compared?

Do not compare only total gross profit or win rate. Compare:

- Total **net** returns after costs.
- Risk-normalized returns and equity curves.
- Maximum drawdown and volatility of outcomes.
- Capital usage, time in market and number of eligible opportunities.
- How often the model abstains, including correct abstentions.
- Exposure concentration and correlated BTC risk.
- Fee, spread, slippage and funding sensitivity.
- Operational rejects, missing-data cases and fair source coverage.
- Confidence intervals and effective **independent** sample counts.
- Whether performance is better than simply not trading.

The roadmap proposes a checkpoint of **at least 100 settled paper trades per model when possible**, plus minimum common-time/event/regime exposure and a predeclared maximum competition horizon.

**100 is not an excuse to force trades.** If a selective model cannot reach that count within the allowed forward evaluation window, report **low activity or inconclusive evidence**.

If both models lose after costs, the less-negative model is not automatically a good Champion.

### Who decides the winner?

The research engine can calculate the comparison and recommend retain/reject/replace/suspend. The model must not promote itself. The authoritative roadmap requires separately authenticated owner approval for paper model replacement and entirely separate approval for any future real-money authority.

---

## 15. Why paper trading exists even after virtual research works

**Virtual research asks:** "Was this hypothetical candidate's declared entry/exit path economically attractive under verifiable future market evidence?"

**Paper trading asks:** "Can the *entire decision and position-management system* act consistently on real-time, prospective recommendations, under a realistic execution simulation?"

Paper tests things that a table of matured virtual labels cannot fully establish:

1. Did the model issue its recommendation **before** the move?
2. Did the Execution VPS receive it in time?
3. Was the quote still fresh?
4. Did the independent risk guardian accept or reject the proposed position?
5. Did the simulated fill assumptions reflect bid/ask, spread, slip and fees?
6. Were stop, target, timeout and funding applied correctly?
7. Did the position occupy the single-position budget?
8. What opportunities were unavailable while a position remained open?
9. Did the balance, exposure, equity and drawdown ledger reconcile?
10. What happened during loss of connectivity, duplicate messages or restarts?
11. Did the paper Champion actually perform well outside the training sample?

Paper trading is a **forward operational rehearsal**. It has no private-order authority and produces **simulated** fills, not money.

It can expose errors in handoffs, latency, occupancy, risk controls and model behavior before any separately authorized real trading.

Paper success is necessary evidence for considering a later live decision; it is not a guarantee of actual exchange execution or profitability.

---

## 16. The one-position rule: what it means and what it does NOT mean

The owner's clarified practical operating objective is:

**At most ONE actual Binance position may be open at any time across all watched markets, both sides and all active model versions.**

This should become a single, global Execution-side invariant if/when real execution is separately designed and authorized. Pending entries, partial fills, protective-order status and unknown/reconciling exchange state must be considered: the bot cannot open another real position just because its local database temporarily says "flat."

### What the one-position rule DOES mean

- No second real LONG or SHORT while an actual position is open or unresolved.
- No new real position until closing, exchange reconciliation and release of the global position budget are verified.
- One risk-controlled position manager rather than many independent real trading agents.
- Every model's recommendation is advisory until the single independent Execution guardian authorizes it.
- The bot may abstain for hours or days.

### What it does NOT mean

- Only watching one coin.
- Only considering one hypothetical candidate.
- Only learning from actually placed trades.
- Ignoring good opportunities because they were not selected.
- Deleting one of two **paper** comparison books.
- Training only one model forever.

**A virtual trade or paper-only simulated position is not an actual Binance position.**

### Important design/governance distinction

The existing authoritative roadmap calls for a **first qualified Champion paper stage**, and then **two independently accounted paper books** for Champion/Challenger comparison. The owner's newly emphasized one-position constraint specifically addresses **actual** trading.

There is an existing engineering mismatch: current G7 paper unlock requires **two qualified models from the outset**, whereas the roadmap permits a first Champion-only paper phase. That mismatch requires a reviewed engineering change.

If the owner also wants **only one paper position globally across all paper comparison books**, that is a **separate proposed simplification**, not an authorized reinterpretation of the existing competition rules. It would affect fairness and must be adopted explicitly.

---

## 17. Why separate Observation ("brain") and Execution ("guardian") across two VPSs?

One physical VPS watches markets, builds evidence, computes features, matures virtual research outcomes, trains candidates and proposes model decisions.

The other verifies that a recommended paper or future real action is **permitted, fresh, consistent and safe**, then independently records the resulting position accounting.

This separation prevents a bug in a self-training model from directly granting itself exchange-order authority.

### Observation VPS

- Watches approximately 50 markets plus mandatory BTC context.
- Maintains source and five-minute event quality.
- Enumerates all eligible coin/side opportunities.
- Computes the 24 pattern tags and BTC/coin state.
- Maintains prospective virtual research and qualified economic evidence.
- Trains and evaluates model candidates using mature outcomes.
- Sends only versioned, explicitly authorized proposals.
- Has **no Binance private-order keys or real-money order authority**.

### Execution VPS

- Independently checks model/version/approval and source freshness.
- Applies the global one-actual-position rule if real execution is ever authorized.
- Applies stop, cost, leverage, available-margin and drawdown vetoes.
- Manages paper-account entries/exits and isolated accounting.
- Reconciles unsettled positions conservatively after restart.
- Does not invent research outcomes, train the winning model or override a scientific HOLD.
- May obtain any actual exchange authority **only in a separate future approval project**.

The benefit is **separation of responsibilities**; it does not require seven unrelated daemon processes. Logical G1–G7 stages can run within a small number of carefully coordinated services.

---

## 18. The logical purpose of G1 through G7

| Gate | In plain language | Why it is required |
| --- | --- | --- |
| **G1 — Observe** | Know which markets, prices and candles were available at each decision time. | Cannot learn from events the bot never reliably observed. |
| **G2 — Trust** | Confirm data identity, chronology, quality and gaps. | Bad input would create falsely convincing research. |
| **G3 — Understand** | Describe BTC, broad market and individual coin conditions. | Patterns have context-dependent meaning. |
| **G4 — Measure** | Freeze and mature eligible virtual opportunities into verifiable after-cost outcomes. | Learning needs outcomes from selected **and unselected** candidates. |
| **G5 — Judge** | Test whether a policy offers statistically credible positive after-cost advantage versus no trade. | Good-looking ranks can still lose money. |
| **G6 — Improve** | Train independent Challengers, prevent leakage and compare with frozen prior models. | A learning bot needs improvement without uncontrolled strategy drift. |
| **G7 — Rehearse** | Test approved candidate decision policies, risk vetoes and position accounting in paper. | A profitable-looking model may still fail operationally. |

The broader authoritative roadmap also covers forward comparisons (G8), approval/promotion (G9) and continuing controlled learning (G10). These are **lifecycle governance checkpoints**, not a reason to build unnecessary services.

---

## 19. A simple example of the intended day-to-day operation

Consider an **illustrative**, not real, five-minute market event.

**10:00 — Observe.** NBOT finishes its closed five-minute event for 50 eligible coins, records BTC conditions and describes up to 100 LONG/SHORT directions. No exchange order is sent.

**10:00 — Analyze.** Five candidates display recognizable technical patterns. Two have stale quotes. One has unattractive trading costs. Another has insufficient relevant historical support. One looks potentially attractive under the frozen current Champion, but the model uncertainty is still too wide.

**10:00 — Decide.** Result: **NO TRADE**. That is a valid outcome.

**10:00 onward — Research.** Eligible prospectively declared hypothetical experiments continue to be tracked using original-format market evidence. Selected and rejected opportunities remain in the research denominator.

**After their declared stop/target/horizon or complete maturation — Evaluate.** Some virtual outcomes are scored with verified cost evidence; others remain PENDING or HOLD because required quotes or funding are missing. Missing cases are never fabricated.

**After enough diverse qualified records — Learn.** The learner evaluates potential economic advantage by BTC/coin context, patterns, direction, risk and trading costs. It may find no reliable edge and retain NO_MODEL/NO_TRADE.

**Later — Champion.** An independently approved model becomes the frozen paper Champion, if the scientific and paper-release conditions are satisfied.

**After additional independent evidence — Challenger.** New training produces a proposed Challenger. It is tested separately; it does not displace the Champion merely because it is newer.

**Competition.** The two frozen policies are compared prospectively over the same market period in separate paper accounts. Differences in missed opportunities, position occupancy, risk, costs and abstention are measured.

**Promotion decision.** If superiority is convincing and independently reviewed, a paper model switch may be proposed. Otherwise retain or suspend. No automatic real-money order authority follows.

**If a future real trading phase is approved**, the Execution guardian permits at most one actual position globally, manages it until verified closure and may refuse even the Champion's preferred entry.

This is an autonomous process even if actual trade frequency is very low.

---

## 20. What NBOT should optimize—and what it should not

### Optimize

1. Verified long-run **after-cost** economic outcome, subject to robust downside limits.
2. Trade selectivity and correct abstention.
3. Stability across independent periods and market regimes.
4. Cost-to-risk feasibility before entry.
5. Capital usage and one-position occupancy.
6. Preservation of source truth and clear missingness.
7. Correct single-position risk controls and reconciled accounting.
8. Learning progress with minimal leakage, overfitting and unnecessary retraining.
9. Simple operational recovery and clear owner-visible decisions.

### Do NOT optimize blindly

- Maximum number of open positions.
- Maximum number of daily trades.
- Maximum number of matching patterns.
- Highest raw model rank without a positive-net gate.
- Highest gross return ignoring transaction costs.
- Best-looking historical chart after trying many tuned variants.
- Maximum paper trade count by weakening the no-trade rule.
- Automatic promotion of every newly trained model.
- Source storage volume as an end in itself.

**The point is to improve decision quality, not activity.**

---

## 21. Minimal necessary complexity versus avoidable complexity

The owner has raised a valid concern that NBOT may be getting more complicated than its purpose requires.

Some complexity protects against specific, documented V4 failures. Other complexity can be reduced.

### Essential, even for a one-position bot

- Independent source-clock and gap verification.
- Candidate records for the **full eligible observed set**.
- Prospective, immutable virtual experiment contracts.
- Honest net economic outcomes with explicit missing evidence.
- No-trade option and conservative expected-net gate.
- Chronological model training and untouched validation.
- A frozen Champion and separately evaluated Challengers.
- Independent paper simulation and bounded risk.
- A single global real-position guardian.
- Restart-safe idempotence, source retention and auditability.
- Human/authorized governance for model promotion and any future real orders.

### Candidates for simplification

- Logical G1–G7 stages need not mean seven independent daemon services.
- The 50-coin scanner should be simple, bounded and event-driven.
- Market data can be handled with compact validated snapshots, bounded queues and lossless compressed original evidence **where needed for reproducibility**.
- Incremental outcome state may avoid rebuilding huge per-tick SQLite tables.
- A small number of stable model families may be more useful than uncontrolled hyperparameter searches.
- Challenger evaluation can begin in research/shadow mode before more elaborate paper competition is operationally justified, subject to the existing roadmap's approvals.
- Paper execution can remain one service with separate logical ledgers.
- Research and training should be scheduled/bounded so the small VPSs retain feed and safety headroom.
- Dashboards, multi-portfolio live plans and elaborate reporting can be deferred until they solve a demonstrated operational need.

**Do not simplify by discarding evidence that is necessary to verify a claimed outcome.** Storage optimization must preserve either genuinely replayable original evidence or an explicitly narrower class of admissible scientific claims.

In particular, one actual position does **not** eliminate the need for broad virtual research; and compact summaries alone cannot prove a first stop/target touch if the intervening original path has been discarded.

### Suggested minimal product form

**Observation VPS:** one reliable market/source collector plus one bounded research-and-learning workflow.

**Execution VPS:** one independently guarded position-accounting/execution workflow.

Within these, keep G1–G7 as clear logical modules and contracts. Avoid turning each logical gate into a separate operational project unless isolation has a demonstrable safety or reliability benefit.

---

## 22. What happens when something goes wrong?

The system's trustworthy behavior must be simple.

| Problem | Correct response |
| --- | --- |
| Missing or stale quote, BTC feed or candles | Do not enter; record a source HOLD/abstention reason. |
| Aggregated-trade ID gap or lost original path | Do not fabricate stop/target order or qualified virtual PnL. |
| Missing entry/exit fee, quote or funding evidence | Do not promote the virtual result into independently qualified net data. |
| Hypothetical position not yet mature | Keep PENDING; do not train on it. |
| Insufficient diverse independent samples | Do not train/promote as if 2,000 rows proved an edge. |
| No credible expected positive after-cost advantage | NO TRADE; preserve reason. |
| Challenger performs worse or is uncertain | Retain Champion, reject Challenger or HOLD. |
| Both paper models lose or competition is inconclusive | Do not promote the less-bad model automatically. |
| Observation VPS unavailable | Execution rejects stale new proposals; safely manage/hold any already open authorized position. |
| Execution VPS unavailable | Observation may record attempted recommendations, but cannot invent fills. |
| Restart with uncertain existing real order/position | Reconcile with exchange before allowing any further real entry. |
| Database/segment integrity failure | Isolate affected records, fail closed, retain evidence for inspection. |
| Unauthorized model, missing reviewer approval or stale release | No paper/live authority. |
| Owner emergency lock | Stop new entries and apply the defined safe open-position policy. |

The important feature is **predictable refusal**, not clever behavior under uncertainty.

---

## 23. What would count as NBOT succeeding?

The outcome must be measured at several distinct levels:

**Engineering success:** The entire source → candidate → virtual economic label → training → qualification → paper ledger chain functions automatically in realistic, isolated offline tests, survives expected failures, respects bounded resources and never manufactures missing evidence.

**Scientific learning success:** Real prospectively recorded, matured and independently verified data show a credible positive after-cost policy advantage relative to no trade, meaningful baselines and appropriate uncertainty/dependence checks. This result may legitimately be **NO EDGE**.

**Paper success:** Approved frozen decision models, actual one-position-style occupancy assumptions and paper execution guards behave correctly on forward events, with credible costs, reconciliation and acceptable risk. Challenger competition is fair, with no forced activity.

**Future live operational success:** Only after a separate real-money authorization, actual orders/fills/reconciliation and one-real-position safety function correctly under small, controlled risk limits. Actual profitability must then be assessed using genuine exchange evidence; paper profits are not actual profits.

A system that discovers **there is no reliable edge and refuses to trade** has succeeded at integrity and selectivity, even if it has not produced financial profit. A system that trades frequently despite negative expectation has failed the mission, even if its software never crashes.

---

## 24. Where we actually stood when this vision was written

At the latest documented NBOT acceptance checkpoint:

- The linked G1–G4 50-coin source-binding, gross-path and HOLD mechanisms are implemented and extensively tested offline.
- The G5/G6 scientific learning and G7 paper-book primitives passed isolated **synthetic** tests.
- The full V5 suite passed **743/743 offline tests on each VPS** on 15 October 2026.
- **The fully autonomous original G4 exit-cost/funding verification → independently approved economic outcome → G5/G6 learning/paper handoff was not yet complete.**
- G4 compressed source archival and multi-hypothesis long-run replay still required scaled rollover/resource engineering.
- The first-Champion paper stage and the current two-model-only G7 unlock required reconciliation.
- Both VPSs' NBOT application services remained stopped and disabled; scientific real-market qualification had not been established.

**This document is not engineering signoff.** Complete those missing connections and offline stress tests before any owner-authorized research commissioning. Genuine after-cost source evidence, initial and independent future 2,000-outcome checkpoints, paper acceptance and eventual real-money authority are separate later gates.

---

## 25. Decisions to preserve, and decisions still to make

### Established product direction

1. Automated, continually learning opportunity selection.
2. Market observation across approximately 50 liquid coins, BTC context and both directions.
3. Retain all 24 original V4 pattern hypotheses as candidate features.
4. Research both chosen and unchosen eligible opportunities.
5. Judge strategies by after-cost advantage, uncertainty and ability to abstain.
6. No arbitrary quota of trades.
7. Freeze an accepted Champion and evaluate independent Challengers.
8. Use paper forward execution to validate the decision system before any real-money proposal.
9. Keep a separate Observation brain and Execution risk guardian.
10. **At most one actual real-money position globally** as the owner's clarified operating goal.
11. No model self-promotion and no automatic live-trading authorization from the learning loop.

### Questions requiring explicit governance/engineering resolution

1. How to implement the roadmap's **first Champion-only paper phase** given the current G7 two-model unlock requirement.
2. Whether the owner wants **one global paper position** or independent virtual/paper books during fair Champion–Challenger contests. The latter is currently documented in the authoritative roadmap; the owner's explicit one-position statement concerned the ultimate actual trading bot.
3. The exact default one-position risk budget and treatment of pending entries, exchange UNKNOWN states and partial fills for any future real-order module.
4. The storage/evidence policy that balances small VPS costs against independently reproducible first-touch, quote and funding evidence.
5. The validated minimum independent events, time span, regimes, acceptable drawdown and model improvement required *in addition to* nominal 2,000-outcome and proposed 100-paper-trade checkpoints.
6. Whether any model-approval action may eventually be delegated to a tightly defined pre-authorized process; under the existing roadmap, **explicit owner approval remains the rule**.

These are decisions, **not** permission to silently change the authoritative roadmap.

---

## 26. Final guiding principle

> **Watch many opportunities. Understand their context. Learn from honest hypothetical outcomes. Require evidence of positive return after costs. Trade selectively—or not at all. Keep one real position under one risk guardian. Improve only when a Challenger truly proves it deserves the role.**

NBOT does not need to become a hedge fund or a complicated institutional research platform.

It needs to become a **small, robust, transparent and continuously learning decision-making bot** with enough research discipline to avoid repeating V4's selection mistakes.

Every database, service, model, portfolio and safeguard should be justified against that single mission.

---

## Source documents and traceability

This vision is derived from the existing repo's authoritative technical/design evidence and the owner's October 2026 single-position clarification; it does not supersede those sources:

1. **Authoritative product/engineering roadmap:** [NBOT V5 Market Intelligence, Strategy Alignment and Learning Roadmap](NBOT_V5_MARKET_INTELLIGENCE_ARCHITECTURE_AND_ROADMAP_2026-10-13.md), particularly §§1–9 for the original V4 lessons and research philosophy and §§17–26 for the two-VPS Champion/Challenger/paper competition lifecycle.
2. **V4 replay and selection source:** [V4 research scanner](../nbot/observation/v4_research.py), [V4 selection policy](../nbot/observation/v4_selection.py), and the original 24 pattern registry [candidate_setups.py](../nbot/observation/candidate_setups.py).
3. **Recent V5 engineering/controls review:** [V4 recovery engineering and release gates](NBOT_V5_V4_RECOVERY_ENGINEERING_AND_RELEASE_GATES_2026-10-14.md).
4. **Current measured engineering status:** [G1–G7 Offline Engineering Acceptance — 15 October 2026](NBOT_V5_G1_G7_OFFLINE_ENGINEERING_ACCEPTANCE_20261015.md), including exact tests and outstanding source-to-economics handoffs.

**Authority precedence:** Explicit current owner safety instructions; independently approved operational gate/backup constraints; authoritative roadmap for approved lifecycle; separately reviewed future amendments. This vision provides the **why** and a proposed simplicity boundary, but cannot itself unlock G7, start services or authorize exchange orders.
