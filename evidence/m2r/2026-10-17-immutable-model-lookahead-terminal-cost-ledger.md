# October 17, 2026 — FOCUSED immutable-native-model lookahead root cause + 24-trade execution/funding reconciliation

**Owner-requested focused investigation, actual V6 VPS execution.** Owner-authorized Windows PuTTY session `8GB-Observation` -> V6-only isolated VPS `/root/nbot-v6-m1-20261016/source` on `prototype/v6-freqtrade-freqai-20261016`; draft/unmerged [PR #50](https://github.com/samqju/Nbot/pull/50). Used original **25 saved** native FreqAI 2026.9 LightGBM research model bundles, *not refitted*. Copied them **once** into a separate ~195 MiB scratch folder under `/root/nbot-v6-m1-20261016/immutable-lookahead-20261017/models` and did not touch original saved model binaries, active bot/runtime, main or V5. No API credentials, paper/live service or orders. Public `Binance.exchangeInfo` metadata was required by the native backtest engine, so this one-shot diagnostic used a bounded Docker network interface only for public market setup with `dry_run:true` and empty keys. Trading-cost ledger was isolated **network-none**.

## 1. Real stock 2026.9 lookahead replays with genuinely fixed models

**Verified upstream source cause of suspected confounding:** Freqtrade 2026.9's `freqtrade/optimize/analysis/lookahead.py:97–107` explicitly `shutil.rmtree(user_data_dir/models/freqai.identifier)` before preparing each shortened replay. This normally **deletes FreqAI model artifacts**, making a refit possible and comparisons nonidentical. In research-only [native immutable lookahead wrapper](../../scripts/m2r_native_immutable_lookahead.py), suppressed **only this exact delete path in an isolated copied model identifier** and guarded against any other folder deletion or LightGBM native retraining. **Seven attempted deletions blocked**, **25/25 model SHA-256 fingerprints identical before/after**, **zero training method invocations**. Existing audit-only [`NbotV6M2Audit`](../../user_data/strategies/NbotV6M2Audit.py) was used because official lookahead forces `max_open_trades=-1`; unmodified normal `NbotV6` correctly refuses the diagnostic's unlimited positions. Original strategy risk guard unchanged.

**Important finding:** Even with all native fitted binaries and pipeline artifacts unchanged, the official native Freqtrade 2026.9 lookahead analysis **STILL outputs `has_bias=Yes`** for the *original price-target* model, in **3 selected historical trades** on Oct 8 2026, with **0 falsely flagged trade entry events and 0 falsely flagged trade exit events**. Indicator list: `&-forward_return`, `&-forward_return_mean`, `&-forward_return_std`, `do_predict`, `DI_values`, `exit_short`. This definitively shows **model retraining is NOT the sole cause of the warning**; the original stock warning must **not** be stated as cleared.

### Row-by-row causal isolation (key advance)

The native Freqtrade `LookaheadAnalysis.analyze_indicators()` compares all indicator rows, including a **one-candle-ahead terminal data row** following each actual event being tested. The extended [trace](../../scripts/m2r_native_immutable_lookahead.py) instrumented that stock checker and captured **3 trades × 2 entry/exit replays = 6 comparisons**. For **all 6**, the actual trade decision time was **exactly five minutes BEFORE** the replay's final candle. Comparing **every dataframe column** from start of replay **through AND including the actual trade-decision time** produced **ZERO changed rows and ZERO changed columns**. Every native flagged indicator difference was confined to **a single *later* replay terminal 5m candle**, and only that row. Specifically, the shortened run had a missing native FreqAI prediction there, zero-filled along with target forecast stats/`do_predict`/DI. FreqAI's upstream `FreqaiDataKitchen.fill_predictions()` at `data_kitchen.py:465–476` fills missing merged prediction values with `0`. In **3 of 6 replays** this post-decision zero also changed `exit_short`, which is why a downstream strategy column was flagged—even though no actual entry/exit trade event differed at its checked timestamp.

The **controlled 1×5m endpoint padding diagnostic** (diagnostic **only**; not a trading strategy modification or independent causal proof) simply **moved the single missing prediction to the newly created last row**. The native stock checker still flagged `has_bias=Yes` on the new terminal row, reinforcing terminal-row behavior as the specific mechanism. We did **NOT** hide columns, suppress warnings, or change original target/strategy thresholds.

A separate fail-closed [decision-time verifier](../../scripts/m2r_verify_native_decision_boundary.py) read the actual stock CSV plus detailed full-column trace and exited **0**, asserting **six of six** complete-indicator comparisons equal through actual trade decision and all other differences were exclusively post-decision terminal. **The stock Freqtrade `has_bias=Yes` remains true.** Later attempted expansion to **8 trade signals** stopped with a *new experimental tracing-wrapper DataFrame schema-alignment error* after 4 comparisons; the partial output is **not** claimed as an eight-trade pass. The scope is **3 trades and 6 complete comparisons**, plus prior separate 250 frozen-feature as-of and 7,200 saved-model native prediction equalities. Other future cases, native subtlety and live execution are not universally certified.

**Raw, reproducible V6-only files (no binary models in GitHub):**
- `/root/nbot-v6-m1-20261016/immutable-lookahead-20261017/frozen-lookahead-full-columns.json` SHA256 `6eb580d49894e96ca7e9248c9bf63b2914a6ca230630c2f21b638b2c99280881` — six complete native input-data comparisons, all <= decision time equal, post-decision terminal mismatches only.
- `.../frozen-lookahead-decision-only-assertion.json` SHA256 `e2f8f9e0adce6fa22e2ab005d68b2506c00ffcf0d7e8394b24cea1e60a61eac8` — independent strict assertion, exit 0.
- `.../frozen-lookahead-padding1.json` SHA256 `65d4274103b25b86d7a369d955793479397d8383edc84cdccb452827ec255364` — artificial one-candle terminal shift probe, still stock `has_bias=Yes`.
- `frozen-lookahead-full-columns.csv`, matching `.log`, and aborted eight-signal `frozen-lookahead-8signals.log` retained for failures/method boundaries.

## 2. Step 3: audit actual historical engine trades against public funding events and fee formula

Added strictly offline [24-trade native Freqtrade cost/funding ledger](../../scripts/m2r_native_trade_funding_ledger.py) and ran on the **previously viewed Oct 8–9 2026 two-day 25-market one-global-$1000-position** funding-aware native Freqtrade backtest ZIP, NOT overlapping hypothetical setup labels. Full source: existing [three-way actual-engine cost stress](2026-10-17-native-three-way-matched-cost-stress.md) plus public historical Binance 1h *actual event funding rates*, last completed 1h mark price proxies and actual simulated Freqtrade trade timestamps/directions/size/fees.

| Metric | Actual research verification |
|---|---:|
| Native backtest simulated trades | **24**, across **10 traded markets** |
| Backtest total simulated PnL | **+39.085015 USDT** |
| Actual engine trade fee arithmetic at 0.05% each side (simulated fills) | **23.981704 USDT** |
| Engine-reported net funding *income* field | **+0.09019117 USDT** |
| Public signed event funding *estimated paid* using completed hourly mark | **−0.09020991 USDT** |
| Absolute difference engine income vs negative public funding-paid proxy (all event trades) | **0.00001874 USDT** |
| Historical funding events across these 24 simulated positions | **3** |
| Potentially ambiguous exit coincident with funding settlement | **1** |
| Simulated time-horizon exits / stop-loss exits | **21 / 3** |
| Simulated entry price equals public 5m candle `open` | **24/24** |

**Interpretation:** Historical **funding event timing, rates and Freqtrade funding arithmetic reconcile very closely**, and 0.05%-per-side arithmetic on the saved 24 simulated trades is reproducible. This confirms a material improvement to **historical cost accounting for the observed portfolio**, not actual exchange funding receipts. An ambiguous exact exit-at-funding boundary remains. All 24 fills equal 5m candle opens **because they are backtest simulated fills; the actual bid/ask spread/order-book liquidity and real market orders were never observed**. Three engine stop-loss results similarly **do not** demonstrate executable stop prices. Existing +20bps extra roundtrip what-if cost would turn small two-day funded challenger result **negative (−8.885390 USDT)**; breakeven extra slippage **16.2955bps**, so no robust economic safety margin.

Full per-trade ledger stored ONLY on authorized VPS at `/root/nbot-v6-m1-20261016/native-purged-validation-20261017/native-24trades-funding-ledger.json`, SHA256 `d103cf437e09930bff0add675b0e1100b9466ed9e56b5393a57db208cf07411b`; Docker `--network none` exit 0. No trading service, no exchange credentials.

**Step 3 does NOT qualify as fully externally certified:** real historical quoted bid/ask, actual entered/exited depth, high-volatility stop-market fills and exact exchange funding settlement invoices/mark are **not present in the available OHLCV, mark close and event-rate files**. Cannot truthfully derive these from the candles, and should not declare a validated executable cost floor. With existing aftercost-vs-extra-slippage collapse, **M2 still NO-GO**. A follow-on truly controlled execution trial / real executable venue quotes and appropriate independent holdouts would require separately approved scope before any trading.

## Decision and owner safety

- **Step 1:** existing original price native FreqAI saved-model replay matched 25/25 models and 7200/7200 forecasts; THIS focused native trace isolates a *particular post-decision terminal missing-prediction artifact* in 3 trades and six entire-df comparison paths. **Official `has_bias=Yes` still present; not a universal `has_bias=No`.**
- **Step 2:** native research-only chronological 12×5m/1h internal validation embargo passes, 300 dense training records purged; original/live no changes.
- **Step 3:** full available-data backtest fee-event funding reconciliation performed and mismatch tiny, **but observed real fills/spread/stops/actual settlement not available => external cost gate remains NO-GO**.
- No original trading models erased, no persistent jobs/containers, no M3/M4/M5A live/paper activation, M7 live locked; V5 and default branch untouched. Previously viewed historical Oct data is NOT reserved unseen evaluation; no Jan-enabled May–Aug performance tested. Draft PR #50 unmerged.

**Next science:** keep validation on untouched chronology for independent model and fee sensitivity; investigate upstream lookahead terminal-row handling (test/instrument solution, do not hide signal differences); obtain defensible order-book/fill evidence before treating after-cost PnL as executable or releasing M2.
