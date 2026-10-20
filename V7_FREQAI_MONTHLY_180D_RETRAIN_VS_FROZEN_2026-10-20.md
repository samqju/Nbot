# NBOT V7 — Real FreqAI Fitting Every Month with Rolling 180-Day History

**Owner request (2026-10-20):** Train the actual FreqAI LightGBM model on BTC/ETH/SOL historic after-cost strategy results with the most recent 180 days of history, refit after the close of each month, compare learning against frozen and expanding-history controls, and, **only if justified**, investigate daily retraining. Owner mentioned Brain F/G, but available fully studied data Jan–Sep gives only **July, August and September** 180-day-lookback examination windows. Do not fabricate F/G results or imply more unseen months.

**STATUS: MONTHLY RESEARCH AND FULL AUDIT COMPLETE. LEARN-3C = HOLD.** Daily research subsequent to this primary record is separately logged; no new broader-market coins, no paper/live orders or model promotion.

## 1. Hypothesis, corrected explanation, and accurate FreqAI capability

FreqAI is **supervised forecasting software**. It learns from paired historical feature/label examples, **not automatically from one trade's wallet PnL after that trade closes**. The existing V7 source provides **many thousands of post-horizon trade outcomes per month** across all eligible opportunities, independent of which trades its one-slot simulator would have selected; that is a crucial advantage but also means it is *not* online learning solely from the realized history of 1, 10, or 100 executable trades.

FreqAI's default \`continual_learning\` is **false**; enabling it carries Freqtrade's own warning of naïve inherited-weight overfitting. We keep it **OFF**. At each month boundary we train a **FRESH** upstream FreqAI 2026.9 \`LightGBMRegressor.fit()\` model using only matured labels known by that cutoff. This is a custom research orchestration with a real FreqAI model API, **not** official FreqAI per-pair \`start_backtesting\` scheduling or live per-trade updates.

We preserve the original /opt/V7 source, all previous V3–V6 services, exchange credentials, already-run v1/v2/v3 FreqAI research, source ZIPs and SQLite. The request to “reset VPS environment” is interpreted as a **new isolated research run/output path**, not deleting or rebooting the VPS, clearing prior negative evidence or resetting wallet/live services.

## 2. Fixed experimental rules before interpreting outcomes

- **3 coins:** BTCUSDT, ETHUSDT, SOLUSDT; all 20 existing V7 candidate families and eligible LONG/SHORT directions.
- **Clock:** Three forecasts fitted at **July 1, August 1, September 1, 2026, 00:00 UTC**.
- **Rolling lookback:** Exactly **180 calendar days of historical feature/label eligibility before each month begins**, with the **last 14 days reserved as strictly prior-only calibration**. So the model fit uses about **166 days** per month, NOT the full 180 for gradient updates. Prior labels require \`label_available_ms\` strictly less than both fit or calibration cutoff.
- **Expanding-history control:** Starts January 1, 2026 and fits everything before the 14-day calibration reserve. A model in August/September receives earlier 2026 labels rather than sliding the start forward.
- **Frozen control:** The exact July 1 **rolling model** is used through September 30. The rolling and frozen July trade results match precisely. Thus the treatment difference is genuinely later monthly updates, not changed July weights.
- **Aftercost score:** Common real upstream FreqAI LightGBM regression estimated net return in fractional notional units; V7 chooses a global highest positive candidate across all 3 symbols/families or legitimate **NO TRADE**. Uncertainty mode subtracts one global 75th-percentile absolute calibration error (not yet correct selection-specific coverage). STRESS entry policy adds an extra 25bp confidence hurdle.
- **Capital:** Identical **$10,000** separate starting research accounts, **one $1,000-notional position at once**, 2% stop, 3% take, maximum 60 minutes; unchanged research fee/slippage/funding proxy and stop-first 5m simulation. **One continuous July–September portfolio for each policy**, no monthly wallet/capital restart.
- **Economic stress:** In addition to base simulated trading fees/slippage, deduct an EXTRA 25 basis points **per executed round-trip trade** from the realized portfolio PnL.
- **Cohort safety:** All 180d refits use only past matured outcomes, never July future labels when deciding July trades, and no future BTC path/MFE/MAE as predictor features.
- **No performance-based tuning:** Prior seven V7 FreqAI brain trials did inspect the calendar. These are exploratory hypothesis tests on **previously inspected dates**, NOT pristine out-of-sample or future profitability proof.

## 3. Training evidence actually fitted on VPS

| New model and as-of cutoff | Number of fitted matured opportunity examples | Last 14d calibration examples | Historical q75 absolute net forecast error |
|---|---:|---:|---:|
| Rolling July 1 (July Brain B) | 157,260 | 13,672 | 67.00 bp |
| Rolling August 1 (August Brain C) | 157,086 | 11,137 | 39.70 bp |
| Rolling September 1 (September Brain D) | 144,275 | 13,495 | 69.53 bp |
| Expanding July 1 | 157,783 | 13,672 | 66.45 bp |
| Expanding August 1 | 185,943 | 11,137 | 39.77 bp |
| Expanding September 1 | 209,950 | 13,495 | 71.48 bp |

All six models freshly fitted with actual installed FreqAI LightGBMRegressor.fit, rather than reusing prior weights. The number of examples is **not** the number of actual executed exchange trades.

## 4. Primary paired continuous July–September historical portfolio results

| Policy | Closed trades | Net USDT after base modeled costs | Net with +25bp extra roundtrip stress |
|---|---:|---:|---:|
| **Frozen July RAW** | 67 | **−45.7850** | −213.2850 |
| **Monthly rolling 180d RAW** | 60 | **+12.0790** | −137.9210 |
| **Monthly expanding history RAW** | 56 | **−41.0976** | −181.0976 |
| Frozen July UNCERTAINTY | 5 | −14.2966 | −26.7966 |
| Monthly rolling UNCERTAINTY | 6 | **−58.4743** | −73.4743 |
| Monthly expanding UNCERTAINTY | 5 | −27.4340 | −39.9340 |
| Frozen July STRESS entry | 1 | −3.7156 | −6.2156 |
| Monthly rolling STRESS entry | 2 | −12.5674 | −17.5674 |
| Monthly expanding STRESS entry | 1 | −3.7156 | −6.2156 |
| **NO TRADE** | 0 | **0** | **0** |

**Important observations:**

1. Rolling monthly fresh-refits outperform the **identical July-frozen model by +57.8640 USDT** and switch a −$45.79 loss to a +$12.08 nominal win under base simulator costs, using fewer trades.
2. Rolling raw model's July was **18 trades/−22.0781 USDT**, August **31/+24.4373**, September **11/+9.7199** (calendar month of close). Frozen identical July then August **27/−8.8170**, September **22/−14.8899**.
3. Expanding monthly model barely beats frozen under raw economics (**+4.6874 USDT**), despite training rows growing to ~210k. More cumulative data ≠ inherently better trade decisions.
4. **Uncertainty filter got WORSE with monthly updates:** rolling −58.47 vs frozen −14.30; and all uncertainty stress cases negative. Thus “retrain more often always helps” is falsified in these examined configurations.
5. The most favorable monthly raw nominal outcome **fails extra-cost stress badly: −$137.92**. NO TRADE is better under stress. The nominal +$12.08 is not robust.
6. Dates are previously inspected and cannot produce clean promotion proof. Differences could stem from market regime variations, noisy model retrains and thin net edge, and not a dependable generalization.
7. The model is continuously refitted from thousands of matured hypothetical trade outcome labels; **not reward-learning from each one actually executed trade**. Frequent retraining can overfit, forget durable patterns or amplify outcome-proxy defects.

## 5. Independent causal and statistical cross-check

- Reproducible [monthly model trial source](research/freqai_v7_monthly_180d.py), GitHub commit \`ccdf6e5095cf8055d27ffcdc1916a769d2390fc0\`.
- [Monthly artifact and daily-block auditor](research/freqai_v7_monthly_audit.py), commit \`bcca987d845b0c6930b9b8b150ba66cce02f65a6\`, reads all stored model SHA, 3× strategy forecast streams, all 9 immutable V7 decision hash chains/trade ledgers; reconciles exact model training cutoffs and per month/wallet PnL.
- **VPS run EXIT 0**; monthly auditor **EXIT 0**, status \`SOURCE_HASHED_READ_ONLY_COMPLETE\`.
- Audit paired dependence-aware **7-calendar-day moving-block bootstrap**, 2,000 deterministic resamples, using day-of-exit one-slot PnL differences:
  - Rolling RAW minus same July-frozen RAW: **+$57.8641 USDT**, exploratory 95% percentile range **[−58.5482, +164.6330] USDT**. Interval crosses zero—no robust statistical proof.
  - Expanding RAW minus same July-frozen RAW: **+$4.6875**, exploratory 95% range **[−68.1278, +120.7068]**; also crosses zero.
- These bootstraps quantify the uncertainty conditional on the **already-inspected proxy simulation**, not true future profitability.
- Run manifest \`/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/freqai-monthly-180d-v1/summary.json\`, SHA256 **\`3d77a7a218dd1eb0ac3af40946d9810174667b81e9542b8cbbce7e9d5f01f4e4\`**. Auditor summary separate path \`/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/freqai-monthly-180d-v1-audit.json\`.
- Cohort remains original three-coin V7 SQLite; check source hash recorded in stored summary. All results/manifest outputs are **local to isolated VPS research directory**, not embedded binary models in GitHub.

## 6. Next experiment and gate

Because rolling monthly raw PnL improved over frozen, owner authorized **conditional evaluation of daily training** as NEXT experimental research. A [checkpointed daily 180-day FreqAI model runner](research/freqai_v7_daily_180d.py) is introduced for a one-time comparison of **92** 00:00 UTC freshly-fitted models, with the identical label, 180d lookback, 14d calibration reserve and continuous one-slot Jul–Sep capital account. Monthly remains an unpromoted and unoptimized baseline; do not optimize daily solely to win observed 2026 outcomes.

**PASS/FAIL interpretation:** Monthly gives a *promising nominal difference*, not a reliable profitable learning result. Before any paper/live rollout or scaling to more coins require selected-trade prediction calibration, sensitivity to native Freqtrade fills/mark/funding, positive results under materially worse trading costs, and genuinely fresh post-Sep data plus owner review. **LEARN-3C remains HOLD.**
