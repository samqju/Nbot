# M2R — Frozen FreqAI predictions, internal embargo and real funding/mark data (October 17, 2026)

**Owner-authorized V6-only VPS historical research. Not a release test, not an exchange-order test.** Draft PR #50 and research branch `prototype/v6-freqtrade-freqai-20261016` only, installed Freqtrade 2026.9 Docker. No network in the actual model tests; no persistent bot, credentials, paper orders or live trades. **M2 is still NO-GO.**

## 1. Frozen same-model as-of prefix experiment — PASS in its limited scope

Created [`scripts/m2r_frozen_native_prefix_probe.py`](../../scripts/m2r_frozen_native_prefix_probe.py) and executed it twice in short-lived, network-disabled official-image Docker containers with `--memory=5g --cpus=2`. The script trains a **separate after-cost LightGBM model for each of the original 25 pairs** using the existing 30-day 5m historical prefix ending **October 8 00:00 UTC**, V6 `training_labels()` and four native `%-` decision features: setup ID, EMA trend, recent volatility, relative volume. Training uses native FreqAI 2026.9 `LightGBMRegressor.train()`, DataKitchen `make_train_test_datasets()`, native feature and label preprocessing/prediction and the original 80/20 chronological split. Reuses the *same in-memory fitted model, native feature pipeline and LightGBM model hash*, to predict identical Oct 8 03:00, 09:00, 15:00 and 21:00 UTC decisions from (a) all data through end of day and (b) only the prefix available at decision time. It does **not** retrain between these comparisons, and excludes future `&-` labels from model inputs.

| Recorded measure | Native baseline split | Explicit experimental internal embargo |
|---|---:|---:|
| Distinct pair fits | **25** | **25** |
| Frozen-model decision-time comparisons | **100** | **100** |
| Causal `%-` feature mismatches | **0** | **0** |
| Frozen model numeric prediction mismatches | **0** | **0** |
| Native `do_predict` / DI mismatches | **0** | **0** |
| LightGBM fitted model SHA-256 changed while reusing model | **0** | **0** |
| Internal training samples omitted under 12-bar embargo | *Not embargoed (frozen current benchmark)* | **45** across 25 fits |
| Remaining conservatively computed embargo-boundary violations | *Not tested as purged* | **0** |
| One-shot Docker process exit | **0 (PASS)** | **0 (PASS)** |

**Native experimental purge method:** An explicit opt-in `--purge-internal` on the same script wraps DataKitchen's chronological 80/20 split **BEFORE fitting/preprocessing** and conservatively excludes any train row whose decision time **plus 12×5 minutes** is at or beyond the first validation timestamp. This removes **45 train observations** in the actual 25 pair fits with zero detected residual crossing, while maintaining unchanged native `LightGBMRegressor` pipeline behavior and prefix invariance. It is a *prototype methodology*, not yet an integrated/published candidate `--freqaimodel` and **has NOT been applied to the frozen original backtests**.

**Scope limits (critical):** These were four-feature combined after-cost research models. The frozen original price-only AI has **72 feature columns** in its native FreqAI multi-timeframe/cross-pair experiments, and separate breakout/pullback research modes may have different prediction behavior. This does **not** clear the original official `has_bias=Yes`, prove all-25 full-strategy as-of invariance, demonstrate executable trades, or compare any May–August returns.

Raw complete JSON results remain on the authorized V6 VPS, **outside the Git checkout and original active data**:

- Unpurged `/root/nbot-v6-m1-20261016/january-2026-public-history-stage/frozen-native-prefix-20261017.json`, SHA-256 `47e55a61ac344ae34dc90da7057c1211948ca9031cfd1ea1c64c82ed66fa4670`.
- Purged `/root/nbot-v6-m1-20261016/january-2026-public-history-stage/frozen-native-prefix-purged-20261017.json`, SHA-256 `535b850842af4f02151b926cd5c621d0419c6af7259d67a1171a7c72ccb7e6a6`.
- Model execution logs `/root/nbot-v6-m1-20261016/lookahead-boundary-20261017/frozen-native-prefix-20261017.log` and `frozen-native-prefix-purged-20261017.log`.

Reproduction (must be on existing authorized V6 VPS; never launch a service):

```bash
cd /root/nbot-v6-m1-20261016/source
docker run --rm --network none --memory=5g --cpus=2 \
 -v "$PWD:/research:ro" \
 -v /root/nbot-v6-m1-20261016/january-2026-public-history-stage:/stage \
 --entrypoint python freqtradeorg/freqtrade:stable_freqai \
 /research/scripts/m2r_frozen_native_prefix_probe.py \
 --data /research/user_data/data/binance/futures --config /research/user_data/config.json \
 --output /stage/frozen-native-prefix-20261017.json
# Separate experimental variant; distinct results/model version:
# Repeat with --purge-internal and --output /stage/frozen-native-prefix-purged-20261017.json
```

## 2. Native historical funding, mark/futures and price gaps — DATA OBSERVED, execution quality still NO-GO

New read-only [`scripts/m2r_execution_funding_quality_audit.py`](../../scripts/m2r_execution_funding_quality_audit.py) ran in offline official-image Docker on **already examined** Sept 1–Oct 15 UTC (excluded May–August reserved trading-outcome blocks), with all the original fixed 25 pairs. It checks historical **exchange funding-event rates, hourly mark/futures basis and close-to-next-open price changes**. It does *not* reconstruct actual bid/ask, depth, impact, stop fills, or true funding expense per portfolio trade.

| Measure (previously examined September–October history) | Observed |
|---|---:|
| Markets | **25** |
| Funding events | **3,375** |
| Events with abs(rate) greater than **1 bp** | **208** (6.16%) |
| Absolute funding rate median | **0.7523 bp per event** |
| Absolute funding rate p95 | **1.17109 bp per event** |
| Absolute funding rate p99 | **3.29081 bp per event** |
| Largest absolute event | **18.5769 bp** |
| Matched hourly mark vs futures prices | **27,000** |
| Absolute mark/futures basis p95 | **4.9980 bp** |
| Next 5m open vs previous 5m close absolute gap p95 | **2.4193 bp** |

**Interpretation:** The hypothetical outcome target subtracts a constant roundtrip **10 bp fee + 10 bp slippage + 1 bp funding = 21 bp**, but this isn't the actual exchange cost of each trade. Funding may be earned or paid depending on long/short and settlement crossing, and not every 60-minute trade crosses one. Rate outliers can exceed the flat 1-bp reserve, and mark-vs-futures basis / next-candle gaps are **not a substitute for historical bid/ask spread or stop-market fill price**. The official after-cost Oct AI PnL previously flipped negative under +25bp roundtrip sensitivity; see [prior after-cost evidence](2026-10-17-aftercost-model-learning-results.md). Existing September two boundary funding differences still not closed. **Cost and fill quality gate remains FAILED/UNRESOLVED**, and zero price/model improvement is claimed from this data audit.

The complete audit JSON is on the authorized V6 VPS:
`/root/nbot-v6-m1-20261016/january-2026-public-history-stage/m2r-execution-funding-sept-oct-20261017.json`, SHA256 `4b4b627d02e6b7221c25b8209d3ac915ac4134c9c00b49bfd2d0e99e58720417`.

## 3. Release/trading gates and next work

- [x] Existing V6 25-pair January-onward **data archive** 100/100 audited in [previous evidence](2026-10-17-vps-resumed-cutoff-lookahead-history.md); no original source history replaced.
- [x] **25 native four-feature after-cost LightGBM fixed-model prefix runs** and explicit optional internal 12-bar embargo **executed**, 100 comparisons each, all invariant. Zero internal cutoff violations **in that experimental variant**.
- [x] September–October 25-pair funding/mark/candle-gap facts audited; confirmed **no observed real bid/ask/fill evidence** and constant one-bp funding target is an approximation.
- [ ] Integrate/test internal embargo in a separately isolated **full native FreqAI 72-feature training route**, add breakout/pullback separate per-family tests, verify cross-pair/1h feature as-of alignments on **all 25** and explain official `has_bias=Yes` prediction/entry differences with **identical cached models**. The official checker retrains shortened contexts, so its output alone cannot decide whether the strategy leaks future data.
- [ ] Reconcile real Freqtrade funding settlement/mark-hour boundaries, fee/stop execution and sensitivity. No observed orderbook fills on raw candles.
- [ ] Only after the integrity/economic gates are defensible, run pre-registered May–August 30/60/90/(eligible)180-day actual controlled backtests; preserve original price AI, frozen non-ML, matched exits and **NO TRADE**.

**M2 NO-GO. M3 not started; M4 up to 20 future virtual positions not started; M5A approx eight-hour up-to-25 universe selection unbuilt; M7 real money locked. Draft PR #50 remains unmerged; V5/main untouched.**
