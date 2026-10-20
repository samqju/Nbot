# V7 BTC/ETH/SOL: RAW Daily FreqAI, Fixed 2% vs Fixed 1% vs 1% Trailing Stop

**Executed and independently audited October 20, 2026** on isolated 8GB-Observation VPS; BTCUSDT, ETHUSDT, SOLUSDT only; 2026 Jan 1–Sep 30. **NOT a live-order study or a production-ready trailing-stop design.**

## Owner's question

“one more not only initial stop-loss but a trailing stoploss always present at 1% like at 0.5% SL at -0.5% and so on, just to check if price entries are bad or capturing profit is too loose. once done, clean the VPS of all unwanted stuff”

The static RAW daily learner originally fitted 273 daily FreqAI LightGBMRegressor models using **2%-stop** after-cost historical labels and continuously replayed one $1,000 position at a time from a $10,000 research sleeve. We **reuse the exact SAME 273 saved time-aligned predictions** for three matched execution policies. This isolates the stop mechanism and account-slot release without introducing model-retraining changes. The separate previously started **1%-stop model re-training** is an additional, independent question; do not call same-model execution replay a new 1%-trained or trailing-trained FreqAI brain.

## Exact trailing rule and epistemic limitation

The protective stop is **always initialized** at 1% adverse to entry (LONG -1%, SHORT +1%). The stop then follows favorable price movement by the *same 1 percentage point distance relative to original entry*:

- LONG: entry 100; highest observed previous *completed* 5-minute candle 100.50 ⇒ next bar stop 99.50 (−0.5% of entry); previous completed candle reaches 101 ⇒ stop 100 (break-even); reaches 101.5 ⇒ stop 100.5 (+0.5% locked).
- SHORT symmetric: entry 100; favorable prior bar low 99.5 ⇒ subsequent stop 100.5, and if prior low reaches 99 ⇒ stop 100.
- The stop can **tighten only**, never loosen. Fixed take profit **+3%** and maximum holding **60 minutes** remain unchanged. Existing V7 broker applies .05% fee each side, .01% slippage each side and a settled Binance funding-rate proxy. Gaps fill at worse opening price; if old stop and take are touched in one bar, stop wins.
- **Critical:** We have only public 5-minute OHLC bars, not ticks. It would be look-ahead to ratchet the stop from a bar's *high* and then assume it stopped out at that bar's low when high/low chronology is unknown. This research therefore ratchets ONLY after each completed 5-minute bar if no stop, target or horizon exit already triggered. It is **not** an actual continuously updated Binance trailing order; native intrabar trailing performance remains unverified.

## Nine-month CONTINUOUS one-position account: FINAL audited results

| Same 273 saved daily RAW FreqAI predictions | Number of trades | Net simulated PnL after base fees/slippage/funding | Net after ADDITIONAL +25 bp roundtrip cost | Max simulated drawdown |
|---|---:|---:|---:|---:|
| Fixed 2% protective stop | **447** | **−790.1252 USDT** | −1,907.6252 | 8.6395% |
| Fixed 1% protective stop | **496** | **−816.8753 USDT** | −2,056.8753 | 8.7199% |
| **1% trailing protective stop** | **574** | **−965.7466 USDT** | **−2,400.7466** | **10.7064%** |
| NO TRADE | 0 | 0 | 0 | 0 |

The trailing model **lost 148.8713 USDT more than the same fixed 1% model** and **175.6214 USDT more than fixed 2%**. Its extra trading activity increased the number of trades 78 vs fixed 1% and 127 vs fixed 2%. Trading 574 times incurred 1,435 USDT of extra stress cost at +2.50 USDT per $1,000 roundtrip beyond base modeled fees. The **10.7064% research drawdown exceeds V7's nominal 10% production envelope**; this offline research replay reports drawdown but does **not** enforce the runtime equity kill-switch. Do not interpret the drawdown as a deployable trading account.

### Why was trailing worse?

| Actual simulated exit type | Fixed 2% | Fixed 1% | Trailing 1% |
|---|---:|---:|---:|
| Protective stop | 43 | 168 | **391** |
| Profit target +3% | 20 | 25 | **18** |
| End of 60-minute horizon | 384 | 303 | **165** |
| Total | 447 | 496 | **574** |

The trailing system stopped out **391/574 ≈ 68.1%** of positions and achieved the 3% take-profit on only 18. Overall **195/574** trailing positions finished positive net after base modeled costs (34.0%). Every stop exit includes entries that could have recovered if left open; this count by itself is not a proof that any specific entry would win under another exit rule.

**Matched-trade attribution:** Across fixed 1%-stop vs trailing 1%, **462** exact opportunity identities were selected by both portfolios, **196** of those had identical profit and **266** were changed by exit logic. On matched opportunities trailing PnL was **69.3609 USDT worse**. Earlier slot availability then produced **112 trades only under trailing**, and **34 only under fixed 1%**. These selection changes account for additional total divergence; do not merely divide 2%-stop PnL by two.

**Month-by-month trailing PnL:** Jan −62.9397, Feb −425.0573, Mar −279.1284, Apr −82.0137, May −31.7965, Jun −168.3146, Jul −0.4525, Aug +90.1445, Sep −6.1883 USDT; **eight of nine months negative**. This does not support the hypothesis that merely capturing favorable price moves more tightly solves the RAW model's weak entry quality.

## Source and test integrity

- [Causal previous-completed-bar stop](research/v7_trailingstop1_broker.py), commit `c345259a613a3e808941b6a46308c0bb1da60e26`. [Three-way historical recomputation and portfolio runner](research/v7_stop1_daily_raw_counterfactual.py), original commit `ba2ef01661bc13881c55b10f7858f9c6668c42f7` with trailing extension `f5229fe9d9d4c7f9bcc633101d2ee1556d5839f3`.
- **Seven trailing-specific causal tests PASS** for LONG, SHORT, moving to breakeven, never loosening, correct initial stop, and stop-before-target ambiguity. Entire V7 suite **58/58 PASS**; audited legacy Linux execution safety suite **530/530 PASS**.
- 436,609 candidate outcome labels were recomputed on isolated archive/data copies, with **300/300** original static 2% stop broker parity samples checked before source policy change; original source dataset SHA256 `26ffb66806142c6c959c6f5a2a9f72bbab73ee16d83489d4841913646076db14`, trailing dataset `1dd10c49587fb364ce10c1f1d54ce9e3c54546cc4f4fc88f16f27c9718195372`.
- Same as-of daily FreqAI forecast stream SHA256 `29141151bcaca48ab474bb974b34a9b9f6fd1b857484290a0b926821dbe13935`. All accounts have **53,881 historical candidate decision timestamps** and one-slot PnL/realized extra-cost reconciliation. Stale 2% `watch` outcome labels and `outcome_context` were removed from the new counterfactual SQLite; the original market features and source hashes are unchanged. **Caveat:** MFE/MAE auxiliary metrics in the counterfactual `opportunity` table were inherited from the original source and should not be used for trailing-exit extrema analysis; only recalculated net/exit/reason/quality fields are certified by this study.
- Complete trade/decision receipts and 3-wallet summary: `/opt/nbot-v7-20261020/runs/freqai-nine-month-180d-2026/trailing1-raw-threeway-v1/summary.json`, SHA256 `e1c74d5fd1a5748f1a1f653f7cdfc7fa84b717b64d304010e9a032ac128d8a61`.
- Independent [three-way trade/exit hash audit](research/v7_trailing1_threeway_audit.py) EXIT 0, status `VERIFIED_STOPOUTCOMES_SOURCE_SHA_AND_3_MATCHED_WALLETS`; SHA256 of `runs/freqai-nine-month-180d-2026/trailing1-threeway-audit-v1.json` `e5eeaf893d8b3ad1908b6b46f83e7f627f700871053393d5a6318797a3814de1`.
- Original 2026 historical period has been repeatedly inspected; 5m OHLC is a coarse paper proxy, historical eligibility remains archive-observed unverified, and these are NOT native exchange executions. All FreqAI training, source files and original results retained untouched. No trading authorization or model promotion.

## Verdict

**The saved RAW daily FreqAI learner continues to make economically weak entries** when exited by either fixed or trailing risk rules. A 1% trailing stop tested under conservative candle causality did **not** rescue it. The better historical evidence remains **daily FreqAI + calibrated NO TRADE/uncertainty gate**, but that too is limited by small selected-trade count, inspected research periods and non-native exit fill fidelity. Before trusting an exchange-continuous trailing stop, evaluate tick/at-least-1m paths with trustworthy execution costs; do not infer intrabar chronology from 5m candles.

**LEARN-3C HOLD**, no automated champion promotion, no live/paper orders, no expansion to broader Binance universe. VPS cleanup is a separate explicitly requested action: remove only known disposable caches and temporary compiler artifacts, never protected source, models, audited evidence, archived input data or active processes.


## Additional fixed-1%-target model test — completed and independently audited

The prior owner-requested **273 daily FreqAI LightGBM model fits trained on fixed-1%-stop labels**, rather than the original 2%-stop labels, also finished across all Jan–Sep 2026 calendar days. Full [nine-month 1%-target model audit](research/freqai_v7_full_nine_month_audit.py) `--stop1` **PASSED** with the same as-of model cutoff, source SHA, original feature timeline and nine full portfolio ledgers. Its DAILY RAW result: **507 trades/−804.2296 USDT**, extra25bp execution stress **−2071.7296 USDT**; DAILY UNCERTAINTY 30 trades/**+21.3727** after base costs, but **−53.6273** extra-cost-stressed. Neither demonstrates a trustworthy new edge.

To recheck the exit-only effect with these better target-aligned saved predictions, [research/v7_stop1trained_trailing_eval.py](research/v7_stop1trained_trailing_eval.py) replayed the identical 273 freshly trained 1%-target model forecasts on the two distinct exit datasets. The independently [audited](research/v7_stop1trained_trailing_audit.py) continuous nine-month results were:

| Exactly same fixed-1%-target-trained daily RAW forecasts | Trades | Net after base proxy trading costs | Net after extra 25bp realized per roundtrip | Maximum simulated drawdown |
|---|---:|---:|---:|---:|
| Fixed 1% stop | **507** | **−804.2296 USDT** | −2071.7296 | 8.1624% |
| **1% previous-bar trailing stop** | **587** | **−1060.9423 USDT** | **−2528.4423** | **10.6396%** |

**Trailing harmed this retrained account by −256.7127 USDT**, too. Stop exits **166 vs 376**; time-limit exits **322 vs 196**; 3% targets **19 vs 15**. The trailing research account again crosses the runtime nominal 10% drawdown envelope, which the offline experiment does NOT automatically enforce.

**Provenance:** Fully trained 1%-target 273-head run `runs/freqai-nine-month-180d-2026/ninemonth-daily-stop1-trained-v1/summary.json` SHA256 `e60d6bb593945d4de1cdf0ba4f76d81821f04a3e1bd79ed92a4bb588928bc5b8`, model's forecast stream `43d12cde4ca17ff6caae70fc15ba5790c3a632f3e10956482d26ea5368fbc38b`. Fixed-1%-trained vs trailing comparison `runs/freqai-nine-month-180d-2026/stop1trained-fixed-vs-trailing1-v1/summary.json` SHA256 `2de6b1aa44dc290810e32dfe7c3d29d5231a2b55ec228419e477559d95b9006d`; read-only independent audit `runs/freqai-nine-month-180d-2026/stop1trained-trailing-audit-v1.json` SHA256 `353fcbdd2d276079352451c0432b6f9e963858dbf7025e1f6420db15dc2b1d0b`, status `SAVED_273_ONE_PERCENT_TRAINED_MODELS_FIXED_VS_TRAILING_EXIT_VERIFIED`.

**Scientific boundary:** This second comparison reuses models fitted on **FIXED 1% targets**; it does not train a separate 273-head model on trailing-specific targets. Both sets of saved model forecasts were frozen when the fixed-versus-trailing result was compared. This is an honest *execution-policy* experiment, not proof a trailing-specific learner couldn't perform differently.

### Deeper entry/exit attribution, independently audited

The [expanded exit ledger audit](research/v7_trailing1_threeway_audit.py), result `runs/freqai-nine-month-180d-2026/trailing1-threeway-audit-v2.json` SHA256 `710a321b463161c589dd41de964ebfdc088495d4cead623787056c5f83904d9b`, verifies original aftercost source labels, same FreqAI predictions, full decision hash chains and these trailing1 RAW **2%-target-model** exit economies:

- **391 STOP exits:** −1741.3972 USDT combined; **86** still had *positive net* because the trailing stop locked some profits. Average −4.4537 USDT per stop.
- **165 HORIZON exits:** +255.3064 combined; 91 positive net.
- **18 TARGET exits:** +520.3442 combined; all 18 positive net.
- The average selected expected aftercost net was **+12.9571bp**, while selected realized net was **−16.8249bp**, ~29.782bp overprediction. This is compatible with a weak raw model-selection edge; exact live generalization cannot be inferred.

### Authorized VPS cleanup — complete, non-destructive, source-hash-checked

After all studies and audits completed, cleared only:
- Existing **81 MiB** `/root/.cache/pip` wheel/download cache (installed FreqAI runtime left intact).
- Generated Python `__pycache__` folders within the isolated V7 `code` checkout; not the installed venv or other bot code.
- The single temporary diagnostic `/tmp/v7-q75-nine-month-2026.txt`.

VPS 96 GiB root filesystem use reduced from **8.7 GiB (~10%) to 8.6 GiB (~9%)**; **~88 GiB free**. All original 2025/2026 Binance checksum-verified archives, original 2%-stop models, 1%-stop daily models, trailing outcomes, model forecasts, all nine-month logs/reports, isolated FreqAI 2026.9 virtualenv and legacy deployments retained because they are research evidence or dependencies, **not disposable junk**. The four saved key report SHA256 receipts (old 2%-stop summary, fresh 1%-stop summary, updated trailing audit and retrained trailing audit) matched exactly **before and after cleanup**. V7 git checkout remains clean at cleanup. No real/paper orders or old bot service changes.

**Final verdict remains LEARN-3C HOLD.** Trailing stop cannot fix this RAW learner's poor entry quality in these matched 2026 historical 5m proxies. A genuinely exchange-continuous 1% trailing stop requires tick or at least 1-minute exit-path evidence, real fill/funding tests and an independent unseen evaluation period.
