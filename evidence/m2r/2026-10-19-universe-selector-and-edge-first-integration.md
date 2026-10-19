# Nbot V6 — Integrated Universe Selector (M5A) and Entry-Quality AI Research

**Updated 19 October 2026. Status: DESIGN / RESEARCH PLAN, not deployed or economically validated.** User confirmed both are necessary: the bot must dynamically decide **which coins are even worth studying** and then **which eligible coin × strategy × direction × exit opportunity** has positive after-cost expected return.

## What was missing in the completed research

The fully completed Stage1 (63), Stage2 (120), Stage3 global AI (12), no-60-minute exit (64) and −1%-stop (16) jobs **all reused a hard-coded original 25-contract universe**. The global model did compare eight families over those 25 at each simulated decision time, but **never evaluated whether the 25 were the best available tradable coins at that point**. Earlier descriptive analysis of 684 eight-hour review points within the fixed 25 and an archive of more historical symbol directories **did not produce an as-of market-wide selector or a native dynamically rotated trading backtest**. This must not be reported as M5A implemented.

## Two independent decisions, two cadences

```
ALL ELIGIBLE BINANCE USDT-M PERPETUAL MARKETS (N, varying with time)
                  |
     M5A: AS-OF 8-HOUR UNIVERSE SCREENER
       inexpensive public markets scan
       contract age and TRADING status
       1,000 USDT executable liquidity, spread, funding
       volume/volatility/market regimes, data readiness
       stability, incumbent retention, BTC and open-position pinning
                  |
           EXACTLY 25 READY COINS
             (0–10 changes/review)
                  |
     EVERY COMPLETED FIVE-MINUTE CANDLE:
     FOR EACH COIN × 8 STRATEGIES × ELIGIBLE LONG/SHORT
     × PREDECLARED EXIT POLICIES:
       - P(+1,+2,+3,+5% BEFORE stop), time-to-event, MAE/MFE
       - likely net realized payoff AFTER all fees/funding/costs
       - adverse and holding/capital occupation cost and confidence
                  |
     RANK RISK-ADJUSTED EXPECTED NET VALUE / OPPORTUNITY COST
            BEST ONE SLOT OR NO TRADE
```

Never confuse **universe approval** with a trade signal: a coin can be a good, highly liquid model-ready candidate yet have **zero attractive trades at the present candle**. Conversely, high observed price movement does not justify admitting a coin whose execution costs, training history, or spread are unsafe.

## Preserve the owner's already agreed M5A contract

1. **Scan the entire point-in-time Binance USDⓈ-M USDT-settled PERPETUAL set every 8 hours**, UTC 00:00, 08:00 and 16:00 *for future shadow proposals*. The eligible set is not the list that happens to trade today; historical eligibility must include contemporaneous listings and delistings, with no survivorship/lookahead. For historical evaluation, reconstruct snapshots as of each 8-hour cut or clearly label missing spread/contract metadata as unavailable; never substitute today's exchangeInfo/ticker for yesterday.
2. Keep **25 unique active candidate pairs**, replace **0–10** per review at most, and retain **at least 15 incumbents**. **No change is a valid best decision**. Maintain a meaningful improvement threshold/hysteresis and minimum tenure; account for model-bootstrap and transition costs. **BTC is pinned as market context** (and should remain among the selected 25 under existing agreed policy); also pin every coin with open orders/positions/protective exits. Defer updates if protected positions prevent 25-safe replacement.
3. **Split public discovery from active readiness:** anyone may be screened without an AI model, but no new coin becomes an active, tradeable signal unless 5m/1h/BTC/funding/mark history passes coverage and gap checks, price and spread are current, model features and mature labels are available, the coin-specific model successfully trains and validates causally, the prediction is fresh, and the 1,000 USDT order passes exchange constraints. Download **~60 days existing history** if available; do not demand 30 days of live runtime simply to get historical training bars.
4. **Lightweight two-pass ranking rather than ML training all N contracts every 8h:** filter broad public exchange data first, then inspect a bounded promising shortlist and the current 25 using historical candle regimes, actual orderbook information where available and candidate-specific model readiness. Final choice should factor not just volume but the modeled *future potential for quality executable signals*, calibrated on strictly earlier market periods and checked against a transparent liquidity-only selector.
5. **Never hot-edit the active FreqAI whitelist.** The framework preloads training candles for whitelisted pairs and explicitly warns against pairlists introducing unseen pairs while the bot runs. Write a versioned proposed list with as-of source timestamp, scores and rejection codes, prepare history/models separately, then apply only at a verified safe restart boundary when portfolio management remains protected. For now everything is **offline or shadow only**; no live/paper authorization, no automatic pair switch or rotation cron.
6. The original NO TRADE gate remains available irrespective of universe activity, and the owner's **one real position at a time** limit remains unchanged. Do not conflate 25 *candidate* pairs with up-to-20 separate future paper-research positions: M4 paper is OFF and not part of this experiment.

## Scientific research plan with explicit benchmark controls

- **Stage A — Historical universe reconstruction:** inventory exchange-supported contract metadata, first-listing dates, expired/suspended pairs, funding, 5m/1h candle completeness, historical liquidity. Where historic bid/ask snapshots do not exist, flag them explicitly; compare spread scenarios rather than guessing. Validate anti-survivorship, anti-future-data and 0–10 changes per 8h. Bootstrap data readiness and model delay. Must not select coins using information from *after* each historical review timestamp.
- **Stage B — Baseline universes:** construct (1) original fixed 25, (2) as-of liquidity-only 25, (3) M5A market-quality rotating 25. An opportunity-aware upgrade can be a separate **prespecified challenger** rather than declaring AI better just because the selector chose historically profitable symbols. Record 8h proposals and stable unchanged decisions. Score opportunity yield after costs, turnover, model readiness, delistings and missed opportunities.
- **Stage C — Fair exit-aware labels and forecasting:** at each completed 5m candle on every **historically eligible coin, including newly proposed coins and rejected strategy signals**, derive conservative first-touch outcomes under +1/+2/+3/+5% payoff targets, −1/−2% stops, specified trailing activations, funding, realistic fee and spread cost scenarios, and time capital is occupied. Labels can look forward, **inputs and universe membership cannot**. Purge overlapping future-label horizons from training/validation splits. Don't train LightGBM to predict +5%/−2%/60m and then evaluate different trading exits.
- **Stage D — Integrated 25×8×exit test:** for each selection policy, use the **same frozen downstream forecasting architecture, exit policies, dates, fee stress, 1× leverage, 1,000 USDT single-slot capital and native Freqtrade execution**, not retrospectively stitch together hypothetical best profitable trades. Score every qualified LONG/SHORT strategy as of the same closed candle; choose global positive expected net edge or NO TRADE. Include capital-occupation penalty and strict downside risk.
- **Stage E — Truly unseen evaluation:** stop using July–September 2026 as final validation because it has repeatedly influenced design. Prespecify candidate-scoring weights, 8-hour hysteresis, model inputs, cost units and all exit rules using earlier folds. Reserve a **fresh later market interval** with adequate data and no parameter revision after outcomes are seen. If historic metadata is insufficient, run an **offline shadow snapshot collector** over future 8h windows and test prospectively, with no orders. Compare equity, aftercost net/trade, maximum drawdown, trade count, calibration, missed positive opportunities, candidate turnover and model readiness against both baselines and NO TRADE.

## Practical go/no-go gates

- No incomplete snapshot; no survivorship; no missing future-required training history silently guessed.
- All 25 ready and unique; BTC pinned; no forced replacement; at most 10 rotates; open positions safe; safe fail-closed unchanged universe.
- All model estimates and strategy/exit values are based on closed-candle data only, and negative or ambiguous trades are included, not discarded.
- Prove a positive **net** 1-position result on unseen data against fixed-25, liquidity-only and NO TRADE; require sufficient actual trades and robust fees/funding/slippage sensitivity. A 40% realized +2/+3% outcome rate is a **diagnostic**, not the automatic business goal.
- No real/paper trading, no V5/main merge, no strategy/model promotion until owner approves the verified economic results.

**Important implementation note:** Freqtrade [FreqAI common pitfalls](https://www.freqtrade.io/en/stable/freqai/) warns against dynamic pairlists that add/remove markets inside a running instance; [Freqtrade backtesting](https://www.freqtrade.io/en/stable/backtesting/) warns that dynamic pairlists can draw on current market status rather than historic eligible pairs. Build the independent **as-of selector replay** and safe versioned transition first.

**Already available:** source bootstrap-history helper and original 25-coin global AI native adapter, plus archived historical market files. **Not built:** historical broad-exchange 8h M5A proposals, replay/benchmark, ready-coin scoring, safe model onboarding and shadow rotations, integrated dynamic-universe exit-aware model or untouched holdout result.

**Decision:** M5A is now a **first-class, upstream prerequisite of the next edge-first AI research**, not a postscript relegated after training only on 25 fixed pairs. Design amendment does not itself start new VPS training, downloads, pair activation, cron scheduling, or trading.
