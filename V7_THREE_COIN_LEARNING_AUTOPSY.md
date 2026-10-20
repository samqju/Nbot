# NBOT V7 — Three-Coin Learning Autopsy (LEARN-3C)

**Date:** 2026-10-20 (IST)  
**Status:** **AUDIT COMPLETED; LEARNING GATE FAIL/HOLD**. Existing source-verified research artifacts analyzed; no retraining, no trade policy change, no new dataset download, no paper/live orders.  
**Branch:** `V7`  
**Scope:** BTCUSDT, ETHUSDT, SOLUSDT only. Initial nine-month January–September 2026 experiment; frozen model examination **July–September 2026**.  
**Caution:** Previously inspected calendar dates, archive-observed **unverified historic contract lifecycle**, 5m OHLC stop-first **proxy** labels, not native fills. The analysis is a debugging autopsy and cannot constitute independent profit evidence.

## 1. Frozen primary evidence, provenance and reproduction

- Read-only source: `/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/labeled.sqlite` (344 MiB, `build_complete=true`, no modification).
- Corrected historic replay (Step 6): `/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/experiment-boundary-fixed/`, `summary.json` SHA256 `7e6097bac1e3565863e6d1f5d017c8df722e808738ae03323a13ae1b5734dae0`. Original historical run also preserved and NOT silently substituted.
- Deterministic audit source: [scripts/v7_three_coin_learning_audit.py](scripts/v7_three_coin_learning_audit.py). The script opens SQLite read-only, validates every archived experiment output against the run manifest, verifies SHA-chain integrity of every decision event, joins every selected trade to its original outcome and future-only context, and reconciles summed net PnL to the frozen summary. **No joblib models are deserialized, fitted, or traded.**
- Audited result: `/opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/learning-autopsy-v2.json`, SHA256 `f2ce95529bdfe6728c6e60cc655156111a6cb2b9aeb1b3ff9a7fbc8a641212bc`. The earlier experimental `v1` audit also remains saved; **v2 adds full run-hash verification and label maturity checks**.
- Reproduction: `python scripts/v7_three_coin_learning_audit.py --db /opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/labeled.sqlite --run /opt/nbot-v7-20261020/runs/pilot-btc-eth-sol-2026/experiment-boundary-fixed --output /path/to/NEW-learning-autopsy.json`. Output file must not already exist.
- Actual Linux test suite: **39/39 V7 tests PASS** at source commit `488abf927e08347bdc84c9cca388f8f99971f2e0`. Test transcript `/opt/nbot-v7-20261020/runs/learning-autopsy-v2-tests.txt`, SHA256 `cba7a8491cb42d5513b488c70f96d73df974a47e8441da68024a90fb973dd3f7`. New [tests_v7/test_learning_autopsy.py](tests_v7/test_learning_autopsy.py) tests chain-tamper detection, predicted-return bands and BTC as-of classification. The 530 historical execution regression tests from Step 5 were NOT rerun during this autopsy.

## 2. Result: every brain forecast positive net, while selected trades lost

Predictions are **per selected trade's positive net-regression estimate**; actual is the same trade's paper-proxy **after-cost** realized result. 1 basis point (bp) = 0.01% traded notional. Each trade uses $1,000 notional, separate $10,000 research sleeve per brain.

| Brain | Fit period | Closed trades | Forecast average (bp) | Actual average (bp) | Selected-trade optimism gap (bp) | Net PnL (USDT) |
|---|---|---:|---:|---:|---:|---:|
| **A** | Jan–Mar | 233 | **+16.6632** | **−14.6218** | **+31.2850** | **−340.6883** |
| **B1** | Jan–Jun, same architecture | 377 | **+15.1143** | **−17.5067** | **+32.6210** | **−660.0041** |
| **B adaptive** | Jan–Jun with regime experts | 630 | **+13.1746** | **−15.1373** | **+28.3119** | **−953.6469** |
| **NO TRADE** | No model | 0 | n/a | 0 | n/a | 0 |

All 1,240 **selected** July–September trades have a positive predicted expected return by the hard-coded choice rule. The average selected-trade optimism exceeds 28bp in every model. This is a **selected-trade calibration error**, not yet proof that the model's predictions are biased on every candidate or that any particular replacement would be profitable.

Win fractions: A **33.91%**, B1 **34.48%**, adaptive B **36.35%**. The adaptive model won slightly more often while still losing substantially more in total; win fraction alone is not economic learning.

At +25bp *additional roundtrip* cost stress beyond the base 5m-proxy policy: A **−923.1883 USDT**, B1 **−1,602.5041 USDT**, B adaptive **−2,528.6469 USDT**. All fail stress. These are stress scenarios, not verified actual historic fills.

**Source code reason:** `nbot_v7/decision.py::choose` treats **predicted_net>0** as sufficient for entry eligibility, then selects the greatest **LightGBM rank score** among positives. The latter is a *relative preference*, not an absolute economically calibrated expected payoff. **No calibrated prediction uncertainty, per-execution spread/queue/market-depth confidence, or explicit positive safety margin vs NO TRADE is required.** Fixing this requires prospective validated calibration, not changing a zero threshold after seeing holdout losses.

## 3. Why adaptive B traded more

At the **same 18,131 potential decision timestamps** in July–September, from the immutable decision event logs:

| Decision | A | B1 | B adaptive |
|---|---:|---:|---:|
| Entered one trade | 233 | 377 | **630** |
| Brain abstained with candidates | 15,981 | 14,782 | **12,607** |
| Slot occupied (other trade still open) | 1,911 | 2,966 | **4,888** |
| Boundary entry declined | 6 | 6 | 6 |

The important causal control: B1 and B's frozen model manifests have **identical SHA256 of the base trade-head and watch-head joblib artifacts**. B differs by adding the `down`, `range`, and `up` **context expert heads**. Therefore their increase in selected trades is attributable to the **expert-routing choice policy in the saved experimental setup**, not a different underlying watch/head fit or new months of input history. This is evidence of **more frequent action**, NOT evidence that specialized experts learned safer entry judgments.

**Extra trades at A's abstentions:** Of adaptive B's 630 July–September trades, **522** (82.86%) happened when A's decision at that exact 5m timestamp was **BRAIN_ABSTAIN**. These 522 selected trades lost **−657.4179 USDT**, equivalent to ~69% of B's total −953.6469 USDT loss. B also traded 78 times when A was already occupying its separate wallet slot (−218.7878 USDT) and 30 times when A made a simultaneous trade (−77.4412 USDT). These groups reconcile exactly to B's total loss. **Matching A's decision timestamp does not make B's trade substitutable in A's separately occupied one-slot wallet.**

For B1: 270 trades at A abstentions lost **−453.8889 USDT**; 54 at A occupied-slot instants lost −183.2224; 53 simultaneous A-selected lost −22.8928 USDT.

**Interpretation:** The biggest marginal damage is not that adaptive B picked a better ranked coin too rarely. Its learned scoring/routing substantially **loosened the effective abstention policy**, granting entry to many more after-cost losing candidates.

## 4. Market, coin, direction and strategy diagnostics — descriptive only

Adaptive B, July–September 2026, selected-trade realized after-cost net PnL:

| Group | Trades | Net USDT | Comment |
|---|---:|---:|---|
| SOLUSDT | 288 | **−534.5729** | Largest coin-level loss |
| ETHUSDT | 211 | **−237.1126** | Negative |
| BTCUSDT | 131 | **−181.9613** | Negative |
| SHORT | 349 | **−725.6696** | Largest direction-level loss |
| LONG | 281 | **−227.9773** | Also negative |
| As-of BTC 1h DOWN | 79 | **−197.9233** | Entry-time BTC bucket from `btc_r12` |
| As-of BTC 1h FLAT | 446 | **−589.1963** | Most traded BTC context |
| As-of BTC 1h UP | 105 | **−166.5273** | Still negative |
| Brain context `range` | 395 | **−678.5398** | Main regime loss |
| Brain context `down` | 86 | **−137.8608** | Negative |
| Brain context `up` | 149 | **−137.2463** | Negative |

Different groupings **overlap**: do NOT sum direction, regime and coin figures. BTC entry buckets shown here are audit-only thresholds on a known-at-decision 1h BTC feature: returns above +0.5%, below −0.5%, or between; not separate profitable regime models.

Notable losing selected proposal families (again **descriptive**, not validation of a new family blacklist): `V6_stochastic_reversal` 112 trades **−154.6925 USDT**, `structure_generic` 76 **−139.9144**, `breakout_12` 70 **−118.4371**, `V6_atr_breakout` 70 **−116.9162**, `momentum_12` 28 **−98.5756**. Some families with very few selected trades were positive; this is not proof of a stable profitable strategy. Do NOT disable families based only on this already-inspected July–September window.

MFE/MAE from **5-minute candle OHLC bounds** on adaptive B selections: average `mfe_pct=+0.004877` and `mae_pct=−0.005136`. These are retrospective intrabar/path bounds and **do not** supply execution-order certainty.

## 5. Label health and true limits

- Source SQLite: **249,693** candidate rows, **249,685** matured conditional outcomes, **8** future outcomes unresolved; missing outcomes remain candidates, not automatically treated as zero or dropped at decision time.
- **0** labels becoming available at/before their decision time (time check), and **0** matured outcomes without their future-only `outcome_context` rows. The as-of model scoring API explicitly whitelists features; post-entry BTC behavior remains an outcome diagnostic, not an input.
- Outcome quality: **249,674** `COARSE_5M_OHLC_PATH_PROXY`, **11** `AMBIGUOUS_5M_STOP_FIRST`. The pilot is entirely an approximate 5m-based *trade pathway*, not native Binance tick/orderbook execution; ambiguous both-touch paths are conservatively tagged.
- Funding context for all **630** adaptive B selected outcomes: `MONTHLY_RATE_ARCHIVE_PROXY`, **not** verified payable mark-notional funding or exchange fills. Source universe grade for all 3 symbols is `ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE`.
- **Caution:** Zero observed early-label timestamps and whitelisted features are useful tests; they do not prove all potential timestamp/data-mining leakage is absent. Missing mark/funding native semantics could still change economic outcomes.

## 6. Critical hidden limitation: only ~11% of available six-month labels were used to fit

From source `nbot_v7/brain.py::rows_before`, the training code thins full same-timestamp groups to a default `max_groups=4,000` and `max_rows=175,000`. For this 3-coin sample the practical time-group sampling yields:

| Brain | Matured opportunity rows eligible before fit cutoff | Rows actually fitted | Fitted fraction | Ranking comparison groups |
|---|---:|---:|---:|---:|
| A | **90,235** | **18,142** | **20.105%** | 2,719 |
| B1 and adaptive B | **171,482** | **18,903** | **11.023%** | 2,921 |

Thus the available matured sample nearly doubled, but the number of fitted examples increased by only **761** (+4.2%), and grouped rank-training events by only **202**. We should quantify time/regime/coin coverage effects and train-size sensitivity **using development folds only**. This is a concrete potential learning bottleneck, not proof that including every correlated candidate row would improve economic performance.

## 7. What NO TRADE evidence actually says

The candidate ranking pipeline checks each candidate's **predicted** net value against 0 then ranks eligible positives. This is *not* a separately calibrated NO TRADE reward/state model. On the exact same 18,131 decision timestamps, A abstained **15,981** times, while B adaptive abstained **12,607**. The additional B decisions were mostly loss-making, including the 522 selected when A abstained.

Audit-only hindsight probe on evenly thinned abstention timestamps (roughly 294–296 timestamps per model, across **all** 3 symbols and independent conditional candidates) finds that positive labels can exist at some times even when the brain abstains. This is **not executable missed PnL**: it ignores predictive feasibility, candidate watch selection and which wallet slot is already committed. The hindsight maximum is an unattainable oracle; do NOT use it as reward or a pass/fail learning criterion.

**Desired behavior:** Keep comparing to a zero-exposure state, but add development-only validated expected-net reliability, cost stress and uncertainty-aware abstention. Realization-aware cutoff tuning on July–September would overfit and is prohibited as promotion proof.

## 8. Preliminary root-cause rankings — hypotheses vs established facts

**Established by logs/source:**
1. **Poor conditional net-return calibration at entries:** every selected brain's forecast averaged above +13bp, while net realized was below −14bp.
2. **Context experts increased exposure without better economics:** B and B1 share identical trade/watch heads, and B made 630 vs B1 377 trades.
3. **Extra B trades at A abstentions were costly:** 522 B trades when A abstained accounted for −657.4179 USDT.
4. **Training sample is heavily time-thinned:** 11.0% of available matured six-month opportunities made the trade fit.
5. **Current policy has no robust margin vs NO TRADE:** `predicted_net>0` qualifies a candidate for a highest-rank selection.

**NOT YET established:** Which specific model feature, spread/cost mismatch, per-symbol drift, algorithmic overfitting or reward policy is the unique cause of miscalibration; whether fully supported regressor calibration or more training labels will improve genuinely unseen decisions; whether RL or alternative supervised rankers outperform the current V4 foundation.

## 9. Recommended next small experiment — not yet authorized as successful

**Stage A (NO changed wallet rules):** Extend *read-only* diagnostic scoring on the development-only **April–June A examination** and full as-of candidate vs after-cost label comparisons, not just selected trades, to measure predictive calibration by score decile, BTC regime, family, source quality and confidence. Reconstruct potential abstention candidates without crediting oracle profits.

**Stage B (preregistered challenger choices, develop only):**
- Same exact candidate universe and frozen 60m proxy exit/cost policy; verify **model selection objective** does not unintentionally use uncalibrated relative LambdaRank as proof of positive absolute expected net.
- Compare the current `predicted_net>0` rule against a **development-calibrated net+uncertainty/cost margin** and a **NO TRADE** reward/utility head; measure coverage-vs-return, one-slot wallet outcomes and net prediction calibration.
- Perform a sensitivity/ablation of `max_groups` group-thinning with purged chronological training folds, and compare **base B1 vs regime-router B** head choice at matched decision timestamps. Hold model and risk boundary constant for the initial diagnosis.
- Do not selectively disable `SHORT`, SOLUSDT, or a losing strategy family based solely on previously inspected July–September hindsight. Any future candidate requires frozen research protocol and *subsequent* unseen period.
- Keep the frozen A (and NO TRADE), B1 and B artifacts and all prior negative reports unchanged. Only consider model challenger promotion after **new unseen source-qualified prospective** results and owner review. More completed trades or better training rank score do not pass.

**Gating verdict: `LEARN-3C = HOLD / NOT PASSED`. Full-market expansion remains blocked. No trading permission.** The autopsy provides a causal diagnostic agenda; it is **not** evidence that the proposed remedies will work.
