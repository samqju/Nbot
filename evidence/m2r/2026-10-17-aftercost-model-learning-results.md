# M2R: What did after-cost LightGBM learn? Chronological September and October tests

**Date:** October 17, 2026. **Decision:** Scientific progress, **NO-GO for paper/live trading**. All results are simulated, from official Freqtrade 2026.9 + FreqAI LightGBM runs on the V6-only research VPS. Original V5 servers, original V6 AI/no-ML strategies and draft PR release status remain unchanged.

## Question

Out of many historical breakout and pullback opportunities, can LightGBM learn to filter for better results **after** assumed fees, slippage, time-limited trades and stops? And does it do better than an identical strategy with no AI filter, the previous price-prediction AI, and **NO TRADE**?

We froze the model threshold and rules **before** seeing October 8–15 trade results. See [predeclared experiment](2026-10-17-preregistered-setup-comparison.md).

The original September offline audit found **29,033 overlapping hypothetical opportunities** across all 25 coins; **32.332%** had positive outcomes after the assumed 0.21% roundtrip reserve. **That figure was a set of training labels, NOT an AI prediction score or a backtested 29,033-trade portfolio.** The model fits independently per coin to older 30-day examples and tests on later candles; as each week passes, the historical backtest retrains using newly available earlier data.

## Actual results: the full September month

| September 1–30 | Actual official *simulated* trade count | Net USDT at 0.05% fee per side | Win rate |
|---|---:|---:|---:|
| Original price-only FreqAI | 137 | **−444.980** | 31.39% |
| New after-cost combined FreqAI | 332 | **−442.471** | 39.76% |
| Original non-AI | 163 | **−242.894** | 25.77% |
| NO TRADE | 0 | **0** | N/A |

The new completed-trade target **did not improve profitability** in September despite a higher winning proportion. Its extra 195 trades increased turnover. [Official Freqtrade archive-based evidence](2026-10-17-september-official-aftercost-comparison.json). **It is a failed economic result, not a pass.**

## Later October 8–15 test — results frozen before inspection

All **25 original markets**, same starting virtual wallet (**100,000 USDT**), **1,000 USDT** stakes, **one** global position at once, **1× leverage**, and original Freqtrade historical **0.05% fee per side**. Previous-price and original no-AI versions retain their old exits; matched no-AI controls use exactly the **same 60-minute exit / 2% stop / 5% profit target** as the after-cost AI. **No strategy-switching router was activated.** The Oct 8–15 experiment is a new *chronologically later* period, but still only eight days and not a substitute for multiple independent periods.

| Official simulated strategy | Trades | Net USDT | Wins | Max drawdown USDT |
|---|---:|---:|---:|---:|
| **Original price-prediction FreqAI** | 45 | **+205.976** | 23 (51.1%) | 87.259 |
| After-cost FreqAI **pullback-only** | 68 | **+146.237** | 34 (50.0%) | 41.277 |
| After-cost FreqAI **combined** | 98 | **+113.046** | 51 (52.0%) | 77.036 |
| After-cost FreqAI **breakout-only** | 83 | **+62.552** | 36 (43.4%) | 72.076 |
| Original no-AI strategy with *different* exits | 52 | **+24.135** | 15 (28.8%) | 139.634 |
| Matched **breakout-only no-AI** / 60-min exit | 178 | **−34.227** | 76 (42.7%) | 189.605 |
| Matched **pullback-only no-AI** / 60-min exit | 177 | **−88.489** | 75 (42.4%) | 147.978 |
| Matched **combined no-AI** / 60-min exit | 189 | **−141.359** | 75 (39.7%) | 225.476 |
| **NO TRADE** | 0 | **0** | 0 | 0 |

[Full eight-strategy official backtest evidence](2026-10-17-oct08-16-eight-strategy-official-backtests.json).

**Interpretation:**

- Within the **same trade exit rules**, each after-cost AI family traded less often and did better than its matched **no-AI filter** comparator. The AI filter was useful *in this specific period*.
- **Pullback-only AI** had the lowest drawdown among the AI variants tested, but the **original price-prediction FreqAI made the most simulated USDT** (+205.976). Therefore **the new model has NOT earned promotion over the original**.
- The entire September month contradicts a simple assumption that the after-cost model must be profitable. A winning eight-day October window cannot erase a losing 30-day September result.

## Direct test: did the AI actually pick stronger hypothetical opportunities?

We analyzed the exact original **saved FreqAI predictions** from the October 8–15 backtest, joined to later *hypothetical* next-open/12-candle after-cost outcomes only **for scoring**, not for any decision or training at that timestamp. The hypothetical examples can overlap across coins and setups; actual engine portfolio PnL is in the table above.

| October 8–15 model | All raw setup opportunities (win rate, mean net) | Chosen by AI forecast (win rate, mean net) |
|---|---|---|
| **Combined** | 7,732 (33.148%, **−0.1430%**) | **302** (45.364%, **+0.0153%**) |
| **Breakout-only** | 4,295 (34.109%, **−0.1203%**) | **235** (43.404%, **+0.0608%**) |
| **Pullback-only** | 3,437 (31.946%, **−0.1714%**) | **154** (44.156%, **+0.0602%**) |

The model **accepted roughly 4–5%** of all eligible hypothetical opportunities. Its favored groups had higher win rates and slightly better mean outcomes under our labels. This is **real evidence of learned selection in these saved forecast outputs**, but **not proof of durable or executable trading profit**. One position may be active and not every selected signal becomes an order.

Per-coin [combined](2026-10-17-oct08-16-combined-prediction-selection.json), [breakout](2026-10-17-oct08-16-breakout-prediction-selection.json) and [pullback](2026-10-17-oct08-16-pullback-prediction-selection.json) evidence.

**How it used learning:** At each historical decision candle, FreqAI produced a numerical predicted **complete-trade net return**. The research strategy permitted entries only when the frozen setup was present, `do_predict == 1`, and predicted net was **greater than 0.4%**. Breakout/pullback models learned from their OWN corresponding completed-trade examples, including historical opportunities the original one-slot bot never opened. A model didn't literally ask itself after each simulated loss "what did I do wrong?" or modify its rules. It re-fitted LightGBM at the configured historical weekly intervals.

**Automatic model/strategy switching is NOT trained or activated.** The separate router remains an offline safety-tested chooser requiring approved candidate-specific as-of scores, fresh model, as-of regime, executable liquidity and risk/cost validation; none of those runtime credentials or permissions has been granted.

## The extra cost warning — strong enough to stop deployment

After the official engine's **0.05% per side fees and its own funding**, we hypothetically charged **additional** flat roundtrip execution penalties against the *same original trades*. These deductions use each trade's actual stake/1x leverage, but are **NOT historical observed bid/ask/spread, stop gaps or order impact**.

| October 8–15 | Official net PnL | Extra **10bps** per completed trade | Extra **25bps** per completed trade |
|---|---:|---:|---:|
| Original price-only AI | +205.976 | **+161.003** | **+93.542** |
| After-cost pullback AI | +146.237 | **+78.293** | **−23.625** |
| After-cost combined AI | +113.046 | **+15.112** | **−131.788** |
| After-cost breakout AI | +62.552 | **−20.367** | **−144.745** |
| Original no-AI | +24.135 | **−27.521** | **−105.005** |
| NO TRADE | 0 | **0** | **0** |

At **15bps additional roundtrip**, combined after-cost AI was already **−33.855 USDT**; at **25bps**, even pullback becomes negative. The original price-only AI was less sensitive *in this short window*, because it traded much less. [Per-trade-notional scenario calculations](2026-10-17-oct08-16-full-cost-sensitivity.json).

This is not a real fill-cost audit. The 0.21% approximate roundtrip reserve in the **training label** is not magically charged at execution; the engine uses its own historical fee/funding assumptions. Actual bid/ask data and stop slippage remain unverified.

## Remaining gates — no false green checkmarks

1. **Unresolved FreqAI lookahead**: Original official `lookahead-analysis` reported `has_bias=Yes` with some differing model/decision columns, despite previous BTC/ETH prefix invariance checks. Native FreqAI rolling training must be checked for future-complete-trade labels crossing each training cutoff. We did add a tested offline purged split, but have NOT proven its use inside native FreqAI fitting.
2. **No realistic execution validation**: Historical public top-of-book quotes and latency/order fill probability are unavailable for every old trade; fixed additional-cost scenarios can eliminate apparent advantage. Record prospective public depth/spreads without starting an order-placement service only with a separately approved research plan.
3. **Not enough independent chronology**: September already inspected and deeply negative; October 8–15 is only one later block. No tuned threshold/model promotion based on these small periods. Need multiple never-used time-held-out blocks and statistical uncertainty before approval.
4. **True adaptive strategy switching untested**: Candidate models have now been trained separately, but router is still an *offline* fail-closed helper. It is NOT connected to paper/live Freqtrade trading, and it must never switch based on hindsight outcomes.
5. **M5A** still needs an 8-hour universe evaluation, up to **25** eligible coins and safe rotation; **M4** still allows up to **20** simulated paper positions in future only if owner explicitly approves the milestone. These are separate from the research-only **one-position** experiment.
6. **M7 live** permanently locked until fresh explicit authorization. No V5 files, VPSes, models or services touched.

**Decision:** We have demonstrated how the AI can learn to filter trades and have documented both a failed September and a better October. **No strategy is proven reliably profitable after actual costs or cleared for paper/live trading. M2 remains NO-GO; M3 full multi-period acceptance not started.**
