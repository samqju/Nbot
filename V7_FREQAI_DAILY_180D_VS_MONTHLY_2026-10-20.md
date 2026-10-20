# NBOT V7 — 180-Day Monthly vs Daily FreqAI Retraining on BTC, ETH, SOL

**Executed:** 2026-10-20 IST, isolated authorized 8GB-Observation VPS.  
**Authority:** Owner approved monthly historical retraining and conditional daily follow-up.  
**VERDICT: RESEARCH EXECUTED; LEARN-3C STILL HOLD.** Daily with uncertainty passed one extra-cost stress scenario but had only 11 trades on previously inspected dates. No clean holdout, no native-order parity, no reliable portfolio uplift.

## Exactly what we trained

Actual upstream FreqAI 2026.9 LightGBMRegressor.fit was invoked from a custom offline V7 adapter on the three-coin matured **after-cost** trade outcome labels, across all 20 V7 opportunity families and available LONG/SHORT setups. It did NOT use the standard FreqAI future-close target, the full native FreqAI start_backtesting scheduler, real after-execution feedback, or the experimental continual_learning warm-start feature.

- Monthly 180-day rolling lookback: fresh July 1, August 1 and September 1 models; last 14 days of each lookback reserved for past-only error calibration; ~166 days used to fit. Three separate monthly expanding-history models add a control.
- Frozen control: uses **exactly the same July rolling model** throughout July–September 2026.
- Daily 180-day rolling lookback: **92/92** freshly fitted models, one at each 00:00 UTC day July 1–September 30; each uses only pre-cutoff matured labels and has its own verified model and prediction artifacts.
- Portfolios: identical V7 three-coin single $1,000-notional position / separate $10,000 sleeves; same 2% stop, 3% take, 60-minute exit, 5m OHLC stop-first after-fee/slippage/funding **proxy**, all 20 families. One continuous Jul–Sep account per policy; **never reset capital each month**.
- Policies: RAW means estimated after-cost net >0; UNCERTAINTY requires expected net greater than model's prior 14-day q75 absolute prediction error; STRESS entry is uncertainty plus another 25bp required predicted net. Economic stress separately deducts another 25bp per actually selected roundtrip trade from reported returns.

## Complete July–September 2026 results (USDT)

| Research policy | Trades | After base modeled cost PnL | With EXTRA 25bp per-trade actual-cost stress |
|---|---:|---:|---:|
| Frozen July RAW | 67 | **−45.7850** | −213.2850 |
| Monthly ROLLING RAW | 60 | **+12.0790** | −137.9210 |
| Monthly EXPANDING RAW | 56 | **−41.0976** | −181.0976 |
| Monthly ROLLING UNCERTAINTY | 6 | −58.4743 | −73.4743 |
| Daily RAW | 60 | **+1.6589** | −148.3411 |
| **DAILY UNCERTAINTY** | **11** | **+67.2705** | **+39.7705** |
| Daily STRESS entry hurdle | 2 | −11.6988 | −16.6988 |
| NO TRADE | 0 | **0** | **0** |

**Monthly RAW improved +57.8640 USDT against the identical July frozen model**, but the base-model gain disappeared under more realistic additional costs. Daily RAW did **not** beat monthly RAW: daily +1.6589 vs monthly +12.0790, a difference of −10.4201 USDT. Therefore “more frequent retraining always improves trading choices” is **not** supported.

Daily UNCERTAINTY made 11 selected trades with +67.2705 nominal and +39.7705 USDT after **an additional 25bp per-trade**. This is a hypothesis worth investigating, **not stable-profit evidence**. Its July: 1 trade/−1.1155; August: 8 trades/+60.0214; September: 2 trades/+8.3646. Most of its gains are concentrated in eight August trades. STRESS as an **entry hurdle** lost money; that is distinct from merely subtracting more real trade costs.

## Statistical and causal reality

Both source-hash audits returned success, including model SHA256, model-label cutoff maturity, full decision hash chains, trade PnL sum, capital-slot completeness and per-month accounting. Dependent-sample sensitivity via paired seven-day moving block bootstrap, 2,000 repeats on July–September:

- Monthly rolling RAW minus frozen July RAW: **+$57.8641**, exploratory 95% range **[−58.5482, +164.6330] USDT**.
- Daily RAW minus monthly rolling RAW: **−$10.4202**, range **[−210.0145, +183.0906]**.
- Daily UNCERTAINTY minus monthly rolling UNCERTAINTY: **+$125.7448**, range **[−0.4236, +353.4969]**.
- Daily UNCERTAINTY minus frozen July UNCERTAINTY: **+$81.5670**, range **[−15.5611, +254.7113]**.

**Every compared uplift range crosses zero.** There is no statistically convincing frequency benefit. These dates were already heavily inspected in earlier V6/V7 work. Even a more favorable percentile range would not make them pristine out-of-sample evidence.

Critically, FreqAI's supervised models have **roughly 144,000–159,000 historical candidate outcomes already available at each daily fitting date**. They are NOT being trained from nothing on the first executed trade, nor do they acquire a special reward after each trade. Retraining after every one of 11 or 60 selected trades would be a different online learning algorithm and could encourage overfitting to noisy partial fills and selection bias.

## Source, artifact hashes, and execution proof

- [Monthly training/replay](research/freqai_v7_monthly_180d.py), commit ccdf6e5095cf8055d27ffcdc1916a769d2390fc0.
- [Monthly verification and paired day blocks](research/freqai_v7_monthly_audit.py), commit bcca987d845b0c6930b9b8b150ba66cce02f65a6.
- [Daily 92-fit model/replay](research/freqai_v7_daily_180d.py), commit 0efd6790c91e65dc3df17cd1408acc3dac244483.
- [Daily artifact and paired benchmark audit](research/freqai_v7_daily_audit.py), commit 208eb973ffc99536c1c45c02cd09fe9e91854abe.
- [Causal schedule tests](research/test_freqai_retrain_schedules.py), commit 5975d4c4f4dd6aa30527248076c1d3593305081e; **5/5 PASS** on isolated actual FreqAI environment.
- Monthly output: /opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/freqai-monthly-180d-v1/summary.json, SHA256 **3d77a7a218dd1eb0ac3af40946d9810174667b81e9542b8cbbce7e9d5f01f4e4**.
- Monthly audited output: /opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/freqai-monthly-180d-v1-audit.json, SHA256 **2e8010367eab096590a42c0aa6d08732bc309279cee4ddf389423d50d77429f3**.
- Daily 92 model run summary SHA256 **ce79f0f44f6389a3054bc11907212d1b838249aaa8e0907938926c4fdb73ebc1** (same root, freqai-daily-180d-v1/summary.json).
- Daily independent audit SHA256 **ae37d14748dfbc0aafd451c0b1701a3af12224f54883b8f9e01bcd0a95b96aed**, saved as freqai-daily-180d-v1-audit.json; result **PASSED_READ_ONLY_92_MODEL_FUTURE_BOUNDARY_AUDIT**. First audit attempt used wrong V7 venv and lacked freqtrade; retried under isolated FreqAI venv with **EXIT 0**, models/results unchanged.
- No Binance API credentials, no actual exchange orders, no existing model overwritten. “Reset VPS” meant starting **new isolated research directories**, not destructive deletion of source data, negative history or rebooting original V3–V6 bots. During the experiment the VPS root had ~91GiB free and ~6.7GiB RAM available.

## Next gate

**LEARN-3C = HOLD.** Do not promote monthly or daily models, start even paper exchange orders, expand coins, or jump to after-every-trade retraining. Priority is **previously untouched post-September data and native Freqtrade fill/mark/funding fidelity**, selection-conditioned confidence estimation, cost sensitivity, and enough independent trade observations for robust decision quality. Only then decide whether monthly/daily cadence justifies additional complexity.
