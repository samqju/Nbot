# NBOT V6 original full-feature FreqAI fixed-model as-of audit — October 17, 2026

**Actual V6-only VPS execution; research result, NOT model release.** Owner-authorized `8GB-Observation` VPS on branch `prototype/v6-freqtrade-freqai-20261016`, original Freqtrade **2026.9** installed Docker image. Historical **October 8, 2026 UTC** source candles were previously inspected market data; **reserved May–August outcomes were not examined**. No API keys, real/paper orders, background service, trading deployment, default branch, V5, or PR merge.

## Result: original AI feature/decision fixed-model causal consistency passed for 250 as-of decisions

A reproducible [original configuration fixed-model probe](../../scripts/m2r_original_72feature_asof_probe.py) invokes Freqtrade's native **`FreqaiDataKitchen.use_strategy_to_populate_indicators()`**, original `NbotV6.feature_engineering_expand_all/basic/standard()` for **5-minute + 1-hour timeframes, 14/28-period indicators, previous shifted candle, and correlated BTC**, then native `remove_special_chars_from_feature_names()`, the original **12-future-5m-candle `&-forward_return` target**, native `LightGBMRegressor.train()` and `predict()` (including trained DI/`do_predict` pipeline), and `NbotV6.populate_indicators()/populate_entry_trend()/populate_exit_trend()` for the resulting original strategy entry/exit columns.

**Important methodological limit:** Older October FreqAI backtest runs configured `save_backtest_models=false`; the exact prior saved model binaries were **unavailable**. Instead, this experiment **fresh-fitted** a separate original-config LightGBM model for **each of 25 pairs exactly once** at the original **Oct 8 00:00 UTC training cutoff**, froze the in-memory fitted model/pipelines for the entire comparison, and SHA-256 fingerprinted the native LightGBM booster before and after. `NbotV6.populate_indicators()` was supplied an injected frozen prediction instead of actually invoking native `freqai.start()` again; this tests **original strategy signal formulas under identical fixed predictions**, **not** the complete production backtesting engine. Fits used original native chronological 80/20 train/validation split **without embargo**. The separate research-only 45-row purge from previous audit was **not** silently introduced into this original benchmark.

- Model dimensions: **BTC = 36 features** (it is the correlation reference, so its BTC features are not duplicated); **24 other markets = 72 features each** (market + BTC correlation, both 5m and 1h).
- Historical dataset: original fixed 25 markets, two futures candle timeframes, Oct 8 2026 decision day; 30-day training ending **Oct 7 at 23:55 UTC**. Each original forward-return fit has **8,640 train-period 5m rows** with last **12 future-target labels missing**, leaving **8,628 eligible labeled rows**; logged FreqAI LightGBM training used about **6,902** after the configured 80/20 split.
- Test points: **10 per pair**, at 00:05, 03:00, 03:35, 09:00, 09:25, 15:00, 15:55, 21:00, 21:40, 23:55 UTC, including deliberately difficult 1h/5m joint-close boundaries.
- Full-history feature extraction was compared to independently reconstructed **as-of feature extraction** with strict source prefixes. The 5m candle with index `HH:55` is a decision at **its close, HH+1:00**, not at its opening timestamp. A 1h candle opening at `HH:00` also becomes complete at `HH+1:00`; this is the exact availability rule used in final test. This matches Freqtrade 2026.9 `merge_informative_pair()` which advances 1h informative timestamps by **60m−5m = 55m** when joining to 5m candle rows.

| One-shot test | Pairs/fits | Comparisons | Causal feature mismatches | Forecast mismatches | DI / `do_predict` mismatches | Entry/exit mismatches | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| Four selected UTC hour-boundary decisions | 25 | 100 | **0** | **0** | **0** | **0** | **PASS** |
| Ten decisions, **incorrect** audit rule (1h completeness tested vs 5m **open**) | 25 | 250 | **50** | **50** | **50** | **10** | **FAIL — harness defect** |
| Ten decisions, corrected 1h completeness tested vs 5m **close** | **25** | **250** | **0** | **0** | **0** | **0** | **PASS** |

For all runs, the same fitted model's booster hash remained stable across full vs prefix predictions (**0 model hash changes**); source indicator feature counts were correct, and the corrected 250-check Docker exited **0**. The deliberately failed broader harness exited **2**; full original output was **preserved rather than discarded** for traceability.

### Why the intermediate 50 failures mattered, and why they were NOT proven lookahead

The first expanded harness incorrectly excluded the current 1h candle if `hour_open + 1h > five_minute_row_open`. At **15:55** and **23:55**, the **five-minute row itself only becomes observable at 16:00 or 00:00 next day**, which is exactly when the relevant 1h candle becomes complete. Freqtrade's native indicator merge deliberately allows that jointly closed 1h candle on the `HH:55` 5m row. The flawed strict-open test therefore compared a past 1h feature value against the legitimately newer closed 1h feature value, creating **50 feature, 50 prediction, 50 DI/validity, and 10 downstream entry/exit discrepancies across 250 checks**. All those discrepancies disappeared **without changing the trading strategy, the trained models, the historical data or indicator calculations**, merely by aligning source candle **availability to candle close**, as Freqtrade does.

This result **does not waive the earlier official full-engine `has_bias=Yes`**: Freqtrade's official `lookahead-analysis` automatically erases/refits FreqAI model artifacts for shortened single-pair probes and still reports changes to `do_predict` and entry columns. The newly proven frozen-model/path-as-of invariance explains *one test-harness confounder* and rules out sampled future-candle dependence in this controlled research experiment; it does not resolve all native backtest-model lifecycle paths, every candle, internal 80/20 embargo, real fills/funding, or profitability. Official diagnostic and M2 release are **STILL NO-GO**.

### Reproducibility and raw evidence

Original 25-model audit runs happened on the **isolated V6 research VPS** only with Docker **`--rm --network none --memory=6g --cpus=2`**, no persistent container. Source-controlled auditor: [`scripts/m2r_original_72feature_asof_probe.py`](../../scripts/m2r_original_72feature_asof_probe.py). Full per-pair/per-timestamp features/predictions/prediction gates/entry+exit decisions and LightGBM model hashes are stored outside Git checkout:

- `/root/nbot-v6-m1-20261016/original-feature-audit/probe-original25.json`: initial 100 decision pass; SHA-256 **`b6536bb189ec72e1e34a0243058fdd2274dc902daab2b9fe592b2a72e7a9e231`**.
- `/root/nbot-v6-m1-20261016/original-feature-audit/probe-original25-10points.json`: **intentional retained failed earlier overly strict 1h prefix rule**, 50 feature/prediction mismatches and 10 changed decisions; SHA-256 **`6b394b22a027fcfe656ebe010c1addac8f6a2d90b5a99fde742eaa2543aceb04`**.
- `/root/nbot-v6-m1-20261016/original-feature-audit/probe-original25-10points-candleclose.json`: **final corrected pass 25 × 10 = 250**, all mismatch counts 0; SHA-256 **`55f5b1e1853aa59f48f6bb6ed812b40fc313e8e1c645035c8d8684f5d66b9c78`**.
- Corresponding logs `all25.log`, `all25-10points.log`, `all25-10points-candleclose.log` in the same directory; complete source-controlled compact factual JSON [here](2026-10-17-original-72feature-fixed-model-summary.json).

Reproduction on existing authorized V6 VPS (one-shot offline only):

```bash
cd /root/nbot-v6-m1-20261016/source
docker run --rm --network none --memory=6g --cpus=2 \
  -v "$PWD:/research:ro" \
  -v /root/nbot-v6-m1-20261016/original-feature-audit:/results \
  --entrypoint python freqtradeorg/freqtrade:stable_freqai \
  /research/scripts/m2r_original_72feature_asof_probe.py \
  --limit-pairs 25 \
  --data /research/user_data/data/binance/futures \
  --config /research/user_data/config.json \
  --output /results/probe-original25-10points-candleclose-reproduction.json
```

**What next:** if expanding, investigate a **genuinely frozen original full-engine saved-model reuse** without the diagnostic's model deletion/refitting, integrate internally purged validation in a separately isolated research identifier, and validate actual execution/funding quality before considering pre-registered May–August 30/60/90/180-day performance comparisons. This test did **not** use the January staged archive or generate any new AI profitability results.

**Release:** **M2 NO-GO**, M3 not started, M4 virtual paper not commissioned (future maximum up to 20), M5A approx-eight-hour dynamic up-to-25 market selector unbuilt, M7 live locked, PR #50 draft/unmerged; V5/default untouched.
