# NBOT V6 — after-cost learning and cautious strategy selection (M2R)

**Started:** October 17, 2026. **Status:** Research-code prototype and single-coin FreqAI historical integration proof. **NOT** an accepted trading system. **M2 NO-GO still applies.**

The owner asked for three capabilities, implemented incrementally instead of throwing away FreqAI/LightGBM: (1) learn which complete trading setups work, including those rejected by the original bot, (2) train on results **after assumed trading costs and risks**, and (3) eventually select the best approved setup or **NO TRADE**. This is a *new research design*; the original strategy and its 25-pair September/October negative results remain frozen.

## What code exists

| Component | Status | What it does |
|---|---|---|
| [Causal setup and label library](user_data/strategies/nbot_trade_outcome.py) | **Implemented; unit-tested** | Four independent candidate types: breakout LONG/SHORT, EMA pullback LONG/SHORT. Decision at 5m completed-candle close, hypothetical entry at **next candle open**, evaluate up to **12 future bars**. |
| [After-cost hypothetical target](user_data/strategies/nbot_trade_outcome.py) | **Implemented; unit-tested** | Records one completed-trade outcome for *every* setup, whether or not Freqtrade executed it. Training label named \`&-trade_net_return\`; non-opportunities, missing future data and final 12 bars are **NaN, not fake 0% wins**. |
| [Historical-only FreqAI strategy](user_data/strategies/NbotV6TradeOutcomeResearch.py) | **Loaded and real BTC smoke-backed** | Separate LightGBM-regression Challenger with only past-price \`%-\` model features, after-cost target, \`do_predict\` checks, one-slot historical mode, 2% stop, 5% ROI target and 12-candle approx. time exit. **Paper/live attempts refused**. |
| [Separate model and safety config](user_data/config.m2r-trade-outcome.json) | **Implemented** | Unique FreqAI identifier, keyless, dry-run, one-slot, API/Telegram off, explicit historical-only switch. Cannot silently replace prior M1/M2 models. |
| [Offline, regime-aware strategy router](user_data/strategies/nbot_strategy_router.py) | **Implemented; unit-tested, not connected to trading** | Accepts hypothetical candidate scores, validates model freshness/liquidity/risk/stress, optionally filters to as-of rising/falling regime, selects max **one** fixed candidate or **NO TRADE**; sideways and unknown/unsafe input favor abstention. |
| [Purged chronological split tool](scripts/m2r_purged_split.py) | **Implemented; unit-tested** | For offline labels, removes any earlier candidate whose *outcome/exit* reaches the later test period. FreqAI's native model train/test handling still needs independent checks. |
| [All-setup audit](scripts/m2r_opportunity_audit.py) | **Real 25-pair offline research run** | Counts each hypothetical completed trade under the fixed conservative label assumptions. Does not sum overlapping candidates into portfolio profit. |
| [Offline research unit tests](tests/test_m2r_trade_learning.py) / [split tests](tests/test_m2r_purged_split.py) | **Implemented** | Next-open entry, fees/slippage, long/short, stop-first same-candle ambiguity, gap stops, missing future, no trade, as-of prefixes, model/paper/live locks, regime routing and future-label purging. |

## Exact cost and outcome assumptions

The **training example** has an entry at the next 5m candle OPEN, a 2% protective stop, a 5% profit target, or expiry after 12 five-minute candles (roughly one hour). If the same 5m candle reaches both stop and profit target, **the stop is assumed first**. An adverse next-candle open gap exits at that worse open, not a favorable theoretical stop fill.

Each completed hypothetical trade subtracts **0.05% simulated entry fee + 0.05% exit fee**, plus **0.05% assumed extra execution/slippage on each side** and **0.01% conservative funding buffer for the trade**, **0.21% total assumed round-trip reserve**. These are fixed **research assumptions**, not prices measured from the Binance order book. Slippage, actual Freqtrade limit execution, stop gaps, funding settlement and filled-size details can differ; do NOT call this an observed net outcome or proven after-cost real trade.

Every setup is tracked even if the one-slot original Freqtrade bot rejected it. When two setup types overlap on a candle, the opportunity audit retains **both**; the first FreqAI single-target Challenger uses deterministic **breakout-before-pullback** priority for the one label at a time. This is a necessary distinction: the offline router does **not yet receive separate trained model forecasts for every candidate type**.

### Real 25-pair September 2026 label audit

[Machine evidence](evidence/m2r/2026-10-17-september-all25-opportunity-labels.json) from the originally downloaded 25 Binance futures markets, September 1–30:

- **216,000** original pair/candle decisions.
- **29,033** distinct *hypothetical setup records*: **8,991 breakout LONG**, **6,346 breakout SHORT**, **7,124 pullback LONG**, **6,572 pullback SHORT**.
- **32.332%** of these labeled opportunities had a positive outcome after the assumed reserves; mean hypothetical net return per opportunity was **−0.246%**.
- **26,701** timed out after 12 bars, **2,064** hit the pessimistic stop, **268** reached the target.

**Do not sum these 29,033 outcomes as trading profit.** Most are simultaneous/overlapping or excluded by position limits. They are possible *training labels*, not actual independent trades or evidence of economic profitability. September has already been examined, so it is no longer a pristine unseen final test.

### Official engine smoke proof

Short-lived original official Freqtrade **2026.9** + LightGBMRegressor Docker research run with **BTC/USDT:USDT only** and timerange **2026-10-01 through 2026-10-08**, using existing preceding 30-day training candles and the separate after-cost model identifier:

- Engine **exit 0**, new after-cost target trained without framework errors, exact strategy discovery **OK**.
- After aligning the research strategy's timeout callback to the 12-bar target, **one** simulated closed BTC trade, **−1.104 USDT** under Freqtrade's 0.05%-each-side fee, held **1:00 hour**. **Not profitable; not a production result.**
- This is an *integration smoke*, not an M3 study, not a fair 25-pair comparison and not a challenger promotion.
- The original 25-pair September AI **−444.980 USDT**, non-ML **−242.894 USDT**, and **NO TRADE 0 USDT** remain the key M2 economic warning. Do not optimize this new approach to a previously explored October week and call it unseen.

Reproduce only in the authorized isolated V6 research VPS and only with PUBLIC history, no exchange keys:

~~~bash
docker run --rm --memory=6g --cpus=2 \
  -v "$PWD/user_data:/freqtrade/user_data" \
  freqtradeorg/freqtrade:stable_freqai backtesting \
  --config /freqtrade/user_data/config.json \
  --config /freqtrade/user_data/config.m2r-trade-outcome.json \
  --strategy NbotV6TradeOutcomeResearch \
  --freqaimodel LightGBMRegressor --pairs BTC/USDT:USDT \
  --timerange 20261001-20261008 --fee 0.0005 --cache none
~~~

## Still required before real evaluation or activation

1. **M2 integrity issues:** The official FreqAI lookahead diagnostic still reported \`has_bias=Yes\` on some prediction/decision columns; precise old historical bid/ask and stop fills remain missing, and two small September funding boundary differences are unresolved. New code does not erase these.
2. **Training labels must be purged in the ACTUAL FreqAI model workflow**, not merely in an offline helper. Verify last-horizon exclusion at every 30-day rolling training cutoff; compare frozen as-of predictions across multiple periods/coins. If native internals don't ensure the boundary, add an explicit safe training mechanism.
3. **Compare a full after-cost Challenger with the frozen original AI, non-ML and NO TRADE** on independent chronology; measure trades, calibration, net P&L, drawdown, turnover, fees, slippage, funding, model drift and runtime. Prefer a never-before-inspected later period for final validation. Existing October BTC smoke does not qualify.
4. **Candidate-specific strategy switching is not trained or plugged into Freqtrade:** the offline router takes hypothetical/as-of candidate scores, but does not yet infer separate breakout vs pullback models or trade. It requires a defensible regime classification, a frozen qualified strategy library, candidate scores that were produced using no future candles and an explicit owner-reviewed promotion/rollback process.
5. **Original M5A selector is still UNBUILT:** every eight hours choose up to **25** suitable markets with fees/liquidity/model readiness, controlled rotation and protection of open positions. A fixed 25-coin audit is not this selector.
6. **Separate M4 virtual paper capacity remains up to 20 positions, NOT started.** Any actual live-money release stays **ONE position max** and locked behind independent owner approval. Do not touch V5 servers, main branch, real exchange credentials or orders.

**Decision: Code and BTC historical smoke exist; this is early M2R research only. M2 release NO-GO, M3 NOT STARTED, M4/M5A NOT COMMISSIONED, M7 LIVE LOCKED.**
