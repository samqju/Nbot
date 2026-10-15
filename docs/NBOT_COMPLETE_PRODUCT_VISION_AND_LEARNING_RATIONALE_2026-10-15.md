# NBOT — Complete Product Vision, Learning Philosophy, and Reason for Every Major Component

**Vision document, version 1.3 — 15 October 2026**

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
