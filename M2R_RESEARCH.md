# NBOT V6 — after-cost learning and cautious strategy selection (M2R)

**Started:** October 17, 2026. **Status:** Research-code prototype, full 25-pair September FreqAI replay, separate breakout/pullback trained models and first predeclared October 8–15 comparison completed. **NOT** an accepted trading system. **M2 NO-GO still applies.**

The owner asked for three capabilities, implemented incrementally instead of throwing away FreqAI/LightGBM: (1) learn which complete trading setups work, including those rejected by the original bot, (2) train on results **after assumed trading costs and risks**, and (3) eventually select the best approved setup or **NO TRADE**. This is a *new research design*; the original strategy and its 25-pair September/October negative results remain frozen.

## October 17 broader-history question — research plan only, NOT EXECUTED

The owner proposed retaining Binance USDT-M market history from **2026-01-01 onward**, rather than limiting the research archive to the downloaded July/September/October coverage. **Recommendation: expand the raw research dataset** for more chronological/regime tests, but do **not** assume more bars guarantee a better LightGBM model. The actual [M2R config](user_data/config.m2r-trade-outcome.json) currently trains on a **rolling 30 days** and backtests **7 days** before refitting. Downloading January history does **not** automatically change the 30-day fitted window, and prediction from a saved model does not refit on all history every decision. This is a planning conclusion, **not a download, new fit, or new test result**.

**Proposed order (no start yet):** (1) first certify native FreqAI 12-future-5m-candle label cutoffs and root-cause official `has_bias=Yes`; (2) inventory/download public **5m/1h futures OHLCV, mark/funding** for the same frozen 25 markets from 2026-01-01 to the latest *complete UTC* history, respecting listing dates and gaps; record availability, hashes, chronology, VPS storage and training-resource costs; (3) **before inspecting any new results**, pre-register several calendar-block/market-regime walk-forward comparisons, untouched time-held-out periods and exact cost/NO TRADE baselines; (4) compare the *same frozen models/rules* under 30-day versus candidate 60/90/180-day rolling training windows, as resource constraints permit, using separate model identifiers and equal as-of dates. Keep data outside GitHub (publish compact reproducible manifests/results). A 180-day window cannot be fairly tested near January without earlier training history; never borrow future outcomes to supply missing warmup.

For every fitting cutoff, purge any label whose **12-candle maximum future outcome horizon** crosses that cutoff. Also ensure chronological train/validation partitions and account for correlation and overlapping labels when estimating statistical confidence. No M2 release acceptance, M3 commissioning, M4 paper, M5A selector or M7 release is implied.

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

## New actual full-model comparison — September and October 8–15

**The first answer to the owner's learning question is now measurable.** LightGBM didn't simply learn from a 32.3% aggregate statistic: the labels describe individual complete trades, and FreqAI trained separate 30-day models using causal price/setup features, then predicted net returns on later bars. The entry filter takes only model-ready setups with predicted after-cost net return above **0.4%**. A new [evidence report](evidence/m2r/2026-10-17-aftercost-model-learning-results.md) contains the exact source results, date cutoffs, fees, no-AI matched-exit comparisons, cost stresses and remaining concerns.

**September 1–30 (25 coins):** new after-cost combined AI **332 trades, −442.471 USDT**, original price-only AI **137, −444.980 USDT**, original no-AI **163, −242.894 USDT**, **NO TRADE 0**. **The new model still lost money that month.** The 29,033 hypothetical opportunity labels from September are overlapping training examples, NOT these 332 actual simulated trades.

**Predeclared later test October 8–15, same 25 coins, one slot and 0.05%-per-side engine fee:**

| Variant | Official trades | Simulated USDT |
|---|---:|---:|
| Original price-only AI | 45 | **+205.976** |
| New pullback-only after-cost AI | 68 | **+146.237** |
| New combined after-cost AI | 98 | **+113.046** |
| New breakout-only after-cost AI | 83 | **+62.552** |
| Original no-AI (different exits) | 52 | +24.135 |
| Matched breakout no-AI (same 60-min exit/2% stop/5% target) | 178 | **−34.227** |
| Matched pullback no-AI (same exits) | 177 | **−88.489** |
| Matched combined no-AI (same exits) | 189 | **−141.359** |
| NO TRADE | 0 | **0** |

The distinct breakout and pullback LightGBM models were actually trained using their own historical completed-trade labels. Three matched non-AI research variants isolate the value of **choosing** candidates from merely changing trade exits. **The new AI outperformed these matched no-AI variants in this 8-day test, but the original price-only AI still earned more simulated USDT.** No safe model promotion can follow one favorable eight-day block.

**Saved model predictions show selective learning:** Combined version had **7,732** raw hypothetical candidate opportunities (33.148% winners, average **−0.1430%** net under assumptions). It favored only **302** (45.364% winners, average **+0.0153%**). Breakout-only favored 235 of 4,295 (win rate **43.404%**, mean **+0.0608%**), pullback-only favored 154 of 3,437 (win rate **44.156%**, mean **+0.0602%**). These are NOT portfolio fills, and the estimated per-opportunity edge is modest.

**Execution-cost fragility:** Charging extra **10 basis points** of hypothetical roundtrip slippage beyond the engine base fee changes combined after-cost AI to **+15.112 USDT**, breakout-only to **−20.367**, pullback-only to **+78.293**, original price-only AI to **+161.003**, and original no-AI to **−27.521**. At extra 25bps, **ALL the new after-cost models become negative**, while original price-only AI still shows +93.542 for these eight days. These are assumed fixed-trade deductions, not observed spreads. [Full machine-readable cost evidence](evidence/m2r/2026-10-17-oct08-16-full-cost-sensitivity.json).

**Release decision remains NO-GO.** The official FreqAI `has_bias=Yes` warning, native train-boundary future-label purge and historic fill costs are not cleared. Auto-selection remains a separate **offline** router, not an active market algorithm; M5A and M4 are unchanged.

## October 17 code-level boundary finding and blocked January research — no new trading results

Read tagged upstream **Freqtrade/FreqAI 2026.9** implementation. In its historical backtest, `start_backtesting()` first restricts the training dataframe to `date < training stop`, then calls the V6 future-label target builder. The V6 12-candle label builder leaves the final 12 rows of this restricted dataframe **NaN**, which native FreqAI filters out. This supports **outer 30-day training-cutoff isolation by source**, unlike a dangerous full-history-label-then-slice ordering. However, the existing `test_size=0.2, shuffle=false` chronological INTERNAL train/evaluation split is not separately 12-bar embargo-purged. Do **not** equate internal evaluation scores with clean independent multi-week validation. This is a source-level finding, NOT a verified V6 VPS runtime pass or a `has_bias=Yes` explanation. [Full audit](evidence/m2r/2026-10-17-native-cutoff-source-audit.md) and [offline regression test](tests/test_m2r_native_cutoff_contract.py) recorded; new CI still needs checking.

The owner-authorized laptop is online but the saved PuTTY **`8GB-Observation`** host-key trust could not be verified by unattended SSH; the client failed closed and **no VPS commands/data download/retraining/backtesting ran**. Never bypass that trust check. The January 1 onward archive is therefore **PLANNED, NOT DOWNLOADED**. We froze a [calendar May–August 2026 multiwindow evaluation protocol](evidence/m2r/2026-10-17-january-history-multiwindow-preregistration.md) without reading new outcomes. It compares 30/60/90-day training on common month blocks and 180-day only where sufficient past warmup exists, original AI, no-ML matched controls, and NO TRADE, as-of/funding/extra-cost accounting. These are not test results. **M2 release remains NO-GO, M3 unstarted, M4 paper inactive, M5A unbuilt, M7 locked.**

## Newly verified October 17 VPS runtime, January history and blocked model validation (supersedes planning-only note)

Using `root` explicitly with the saved `8GB-Observation` PuTTY/PPK session fixed SSH access **without requesting or changing any secrets**. On the isolated V6 VPS: existing 25 pair archive confirmed July 15 onward with no 5m/1h gaps; Freqtrade 2026.9 tested historical as-of BTC complete-trade labels (Oct 8 training cutoff) with **1,145 combined / 617 breakout / 539 pullback** valid *hypothetical* labels and **12/12 last rows NaN** for every model. The native original AI's own historical fit logs also dropped exactly **12** missing target rows; this strongly supports safe *outer* rolling training-label boundaries on the installed image.

A clean separate **25-pair original AI official lookahead rerun** finished normally in 98.80s but again returned **`has_bias=Yes`**, with 8 signals and 0 explicitly changed trade entry/exit events; the same nine changing target, prediction and decision columns occurred. The official diagnostic's source deletes and re-fits its FreqAI model for shortened comparison runs, making model prediction differences a plausible test artifact, **not an independently demonstrated root cause**. Internal 80/20 future-label split still lacks explicit 12-candle embargo. **Do not certify integrity, model promotion or paper mode.**

**The owner's requested January history is now genuinely staged and data-audited.** Public Binance frozen-25 `20260101-20261017` downloaded and retained separately, **100/100** Feather files covering 5m futures, 1h futures/mark and 1h funding events; about 51 MiB. New source-controlled read-only audit checked 0 missing/gapped/duplicate/invalid candles and 0 July–October overlap differences. The original data and models were not overwritten. Full proof: [VPS report](evidence/m2r/2026-10-17-vps-resumed-cutoff-lookahead-history.md), [machine summary](evidence/m2r/2026-10-17-vps-history-runtime-summary.json), [repeatable auditor](scripts/m2r_history_stage_audit.py). **No January-informed LightGBM model, multi-window results or execution cost improvements yet.**

The next guarded offline step is all-25 **fixed-model, time-prefix forecast and label-boundary validation** with independent 12-bar internal embargo and realistic exchange execution/funding sensitivity; only after that, run the already-frozen May–August 30/60/90/eligible 180-day comparison with original AI, matched no-AI and **NO TRADE**. **M2 release NO-GO; M3/M4/M5A/M7 inactive.**

## Still required before real evaluation or activation

1. **M2 integrity issues:** The official FreqAI lookahead diagnostic still reported \`has_bias=Yes\` on some prediction/decision columns; precise old historical bid/ask and stop fills remain missing, and two small September funding boundary differences are unresolved. New code does not erase these.
2. **Training labels must be purged in the ACTUAL FreqAI model workflow**, not merely in an offline helper. Verify last-horizon exclusion at every 30-day rolling training cutoff; compare frozen as-of predictions across multiple periods/coins. If native internals don't ensure the boundary, add an explicit safe training mechanism.
3. **Compare a full after-cost Challenger with the frozen original AI, non-ML and NO TRADE** on independent chronology; measure trades, calibration, net P&L, drawdown, turnover, fees, slippage, funding, model drift and runtime. Prefer a never-before-inspected later period for final validation. Existing October BTC smoke does not qualify.
4. **Candidate-specific strategy switching is not trained or plugged into Freqtrade:** the offline router takes hypothetical/as-of candidate scores, but does not yet infer separate breakout vs pullback models or trade. It requires a defensible regime classification, a frozen qualified strategy library, candidate scores that were produced using no future candles and an explicit owner-reviewed promotion/rollback process.
5. **Original M5A selector is still UNBUILT:** every eight hours choose up to **25** suitable markets with fees/liquidity/model readiness, controlled rotation and protection of open positions. A fixed 25-coin audit is not this selector.
6. **Separate M4 virtual paper capacity remains up to 20 positions, NOT started.** Any actual live-money release stays **ONE position max** and locked behind independent owner approval. Do not touch V5 servers, main branch, real exchange credentials or orders.

**Decision: Code and BTC historical smoke exist; this is early M2R research only. M2 release NO-GO, M3 NOT STARTED, M4/M5A NOT COMMISSIONED, M7 LIVE LOCKED.**
