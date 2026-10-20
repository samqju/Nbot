# NBOT V7 — Full Nine-Month Daily-Retrained FreqAI + Uncertainty-Filter Research

**Completed October 20, 2026 (IST)** on isolated 8GB Observation VPS.  
**User:** “if you have Daily retraining + uncertainty filter model saved then start with it and run the research 9 months and see the outcome.”  
**Scope:** Simulated BTCUSDT, ETHUSDT, SOLUSDT perpetuals only, **January 1–September 30, 2026** as all nine trading months.  
**Current verdict:** **PROMISING EXPLORATORY FILTERED RESULT, BUT LEARN-3C = HOLD**. No paper/live orders, no broadened market, no model promotion.

## 1. Why earlier saved July models could not trade in January

Previously saved 92 daily models were already trained using 2026 history from Jan–Jun before the July 2026 start. Using those fitted models to make decisions in January–June would leak future information. Instead, the same fixed FreqAI LightGBM after-cost model specification and uncertainty filter were **retrained fresh** on genuine preceding history at every 00:00 UTC day of the full January–September period. This is a new, independent source-hashed study, NOT a retroactive relabeling of the old July–September results.

To provide January 1, 2026 with a full 180-day training window, Binance's **July–December 2025** BTC/ETH/SOL **5-minute klines and monthly funding** were downloaded and verified. **36** new 2025 archive ZIPs + **54** reverified and symlinked original 2026 ZIPs, **90/90 SHA256 matched Binance published .CHECKSUM files**. The original archives, previous V7 runs and negative audits remain unchanged. New 2025 archive bytes 7,289,911. New isolated research root: `/opt/nbot-v7-20261020/runs/freqai-nine-month-180d-2026/`.

Complete 15-month source-gated 3-coin dataset has **131,616 eligible 5-minute bars PER coin, zero missing eligible bars**, complete archived monthly funding file presence for all three, and **436,609 conditional opportunity labels** from the 20 existing V7 strategy families. Its grade is still **ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE**: archive integrity does **NOT** prove historical contract tradability, real order-book liquidity, native stop fills or settlement chronology.

## 2. Exact fixed policy compared

**Real upstream FreqAI 2026.9 `LightGBMRegressor.fit()` API**, called by custom V7 offline after-cost adapter, NOT full native FreqAI start_backtesting schedule, no continual weight warm-start and NOT an AI updating its brain only after each actually executed trade. It learns from **all matured historical candidate outcomes**, much larger than the selected trades.

Every daily model: fresh 180-calendar-day historical source lookback preceding a 00:00 UTC decision date, **last 14 days held out for prior-only empirical absolute-error calibration**, earlier ~166 days used to train. Features available no later than the observed 5m candle close; labels available before each train/calibration cutoff; fixed regression hyperparameters from prior daily study, strategy family/side/coin inputs, consistent 2% stop/3% take/60-minute max paper exit and fee/slippage/funding proxy.

**Precommitted comparison:** 273 daily models vs nine monthly models (EXACT same model weights as daily on each month first) vs single frozen January 1 model (EXACT same weights as first daily model throughout nine months). For each: RAW predicted net > 0; UNCERTAINTY predicted after-cost net minus prior calibration q75 absolute error > 0; STRESS adds +25bp **prediction entry** hurdle. **Separately** apply additional realized execution-cost stress of 25bp **per completed roundtrip trade**. All accounts start with **10,000 USDT** and one **1,000 USDT** position slot, one continuous January–September wallet with no resets. Flat NO TRADE holds 0 USDT.

Source, model and period selection were committed [before reading economic results](V7_FREQAI_9MONTH_DAILY_180D_PROTOCOL_2026-10-20.md). Previous 2026 calendars had been studied in V6/V7, so this is **NOT pristine unseen investment evidence** despite chronological model cutoffs.

## 3. Audited NINE-month after-cost results

| Research model / entry policy | Nine-month selected trades | Net simulated USDT after base costs | Net with EXTRA +25bp realized per trade |
|---|---:|---:|---:|
| FROZEN JANUARY RAW | 606 | **−437.3586** | −1,952.3586 |
| MONTHLY RAW | 511 | **−814.3143** | −2,091.8143 |
| DAILY RAW | 447 | **−790.1252** | −1,907.6252 |
| FROZEN JANUARY UNCERTAINTY | 86 | **−15.8240** | −230.8240 |
| MONTHLY UNCERTAINTY | 30 | **+30.6803** | −44.3197 |
| **DAILY UNCERTAINTY** | **24** | **+195.4435** | **+135.4435** |
| FROZEN JANUARY STRESS entry hurdle | 50 | −2.6974 | −127.6974 |
| MONTHLY STRESS entry hurdle | 17 | +66.2339 | +23.7339 |
| DAILY STRESS entry hurdle | 11 | **+130.9874** | **+103.4874** |
| **NO TRADE** | 0 | 0 | 0 |

**NINE-month daily UNCERTAINTY result:** $10k reference wallet, **24 closed trades, 18 aftercost winning trades, 75% win rate on this tiny selected sample, net +195.4435 USDT (+1.9544% sleeve)**; extra 25bp × 24 trades = 60 USDT of extra costs, yielding **+135.4435 USDT (+1.3544% sleeve)**. Selected 24 trades spanned coins: **BTC 4, ETH 10, SOL 10**. Source-audit verified exactly **53,881 decision events** for each account. Relative to MONTHLY UNCERTAINTY +30.6803, the nine-month daily filter gained **+164.7632 USDT**; relative to FROZEN UNCERTAINTY −15.8240, **+211.2675**.

Critically **DAILY RAW was −790.1252 USDT on 447 trades** even though its selected mean predicted net was **+13.269bp** while selected realized net was **−17.6762bp**. The raw selected-forecast optimism remains approximately **30.945bp**. This directly demonstrates that **daily retraining alone is not sufficient**. The uncertainty filter's selected 24 trades had average forecast +21.3645bp and average realized +81.4348bp, but only 24 observations; selected outcome calibration still needs new independent testing.

The two stricter uncertainty +25bp prediction-entry-hurdle research models had a positive base/proxy PnL for daily and monthly too, but these were predefined exploratory variants. Do not retrospectively optimize the filter on the inspected nine months or call the best cell a fully validated strategy.

## 4. Daily uncertainty trade results BY EXIT MONTH

| 2026 month | Closed trades | Simulated base net USDT |
|---|---:|---:|
| January | 3 | +25.3884 |
| February | 2 | +35.6994 |
| March | 5 | +57.7127 |
| April | 1 | −21.0880 |
| May | 1 | +3.5309 |
| June | 2 | +44.5852 |
| July | 1 | −1.1155 |
| August | 6 | +30.5807 |
| September | 3 | +20.1497 |
| **Total** | **24** | **+195.4435** |

Seven months positive and two negative under base costs; with 25bp added per executed trade, still seven months positive, two negative. This is more encouraging temporal coverage than the earlier three-month **11-trade** sample, but each month holds only 1–6 selected trades. Even 75% observed wins can be chance/label-proxy sensitive.

## 5. Independent causal and statistical evidence

Complete historical replay status `FULL_9MO_FINISHED`; separate evaluator [research/freqai_v7_full_nine_month_audit.py](research/freqai_v7_full_nine_month_audit.py) **EXIT 0** with `COMPLETE_273_SAVED_REAL_FREQAI_MODEL_RESULTS_VERIFIED`. The auditor:

- Reverified original 15-month dataset SHA, **all 273 actual saved FreqAI model joblib SHA**, all full daily/monthly/frozen source forecast stream digests and the correct **model hash per decision timestamp**.
- Checked each model was available before its scored day; no train target label at/after the previous fit cutoff, no calibration label at/after the daily decision cutoff. Monthly was bound to each first-day saved model and frozen to identical Jan 1.
- Verified all **nine complete one-slot** historical portfolios, JSONL decision hash chains, each selected trade/PnL against the saved wallet summaries, every roundtrip extra 25bp cost, source SHA receipts and monthly trade counts. Nine months of simulated portfolio time was retained across month changes.
- Used **2,000 reproducible paired 7-calendar-day moving-block resamples** of daily PnL to assess uplift, instead of treating every correlated five-minute proposal as an independent sample.

**Comparative daily uncertainty uplift:**
- Daily UNCERTAINTY minus monthly UNCERTAINTY **+164.7632 USDT**, exploratory 95% bootstrap range **[+8.4348, +342.8515]**, fraction positive in these resamples **0.9835**.
- Daily UNCERTAINTY minus January-frozen UNCERTAINTY **+211.2675**, range **[+26.7242, +397.5361]**, fraction positive **0.9885**.

The intervals **exclude zero in this one historical replay**, but do **not** convert the experiment into a pristine holdout: all of 2026 was inspected in older V6/V7 work and uncertainty policy was chosen based on earlier research. Also blocked-day bootstraps on virtual 5m fills are **not** evidence of real exchange execution or independent real-market generalization. Do not conflate indicative resampling sensitivity with a forward-performance confidence interval.

## 6. Reproducibility paths and frozen SHA receipts

- Upstream pinned actual FreqAI 2026.9 runtime lives separately in `/opt/nbot-v7-20261020/freqai-standalone-20261020/venv/` (no daemon/order service).
- [2025 archive source prep + dataset builder](research/freqai_v7_ninemonth_sources.py), source receipts SHA256 `25534cdd0adaed2c58b7e2384cfd433921ae06f26e9cda4ce791e59003c18faa` and historical 3-coin registry SHA256 `43f091ac296ea04597cbba924b94928466c5fb52f56f2822f55e69d77933460d`.
- New immutable 15-month label SQLite SHA256 `26ffb66806142c6c959c6f5a2a9f72bbab73ee16d83489d4841913646076db14`; build complete `source_authority=OFFLINE_5M_PROXY_NOT_NATIVE_FILLS`, 436,609 candidate labels, 4,110 universe review records, 3/3 funding month coverage, 0 missing price bars for 3 source symbols.
- [Full Jan–Sep 273-model training and 9-wallet one-slot evaluator](research/freqai_v7_full_nine_month_daily.py): source and output isolated at `/opt/nbot-v7-20261020/runs/freqai-nine-month-180d-2026/ninemonth-daily-2026-v1/`. SHA256 of final `summary.json`: **`6a3c6a9716763316877fa5d6fdcd7a20acff2fcdd76b9a3ba2e2b640a9ff20bc`**.
- [Independent model, source, decision and PnL audit](research/freqai_v7_full_nine_month_audit.py): result JSON `/opt/nbot-v7-20261020/runs/freqai-nine-month-180d-2026/ninemonth-audit-v1.json`, SHA256 **`cd18a6a776a85a83b23c9c4b84e66b0b8fdf2ae0da2c4ebb913cf1d0935b466e`**.
- [Causal scope unit tests](research/test_freqai_full_ninemonth.py) **5/5 PASS** using isolated real FreqAI environment; existing 48 V7 and 530 audited legacy execution safety regressions also PASS on isolated VPS after source prep, not altered by the research runner.
- All original NBOT V3–V6 and V7 code, models and historical reports have been preserved. **No VPS destructive reset, no private trading credentials, no paper/live order and no broader coin download**.

## 7. What we actually learned and next gate

The hypothesis “daily training is better” needs qualification. Nine-month raw daily **lost $790**, monthly raw **lost $814**, and frozen raw **lost $437**. **Only when combined with strong abstention did daily produce positive historical proxy results** (+$195, or +$135 after +25bp cost). Model overconfidence remains stark on the raw selected population. The best indication is not an automatically self-learning system, but **a retrained model with a conservative NO TRADE gate**.

**LEARN-3C remains HOLD** because 24 trades are few, the nine-month historical period is not truly unseen, native Freqtrade stop/funding/precision/slippage/source-tradability parity was not established, and the daily q75 uncertainty is based on ALL candidate errors rather than reliable selected-top-trade calibration. The correct next validation is to **freeze the exact daily uncertainty policy and compare its behavior on genuinely untouched later dates (post-September 2026)**, with native exchange execution cost modeling and sufficient independent trade outcomes. Do **not** promote the selected positive account into paper/live or expand beyond three coins on this evidence.
