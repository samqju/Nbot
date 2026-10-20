# V7 Nine-Month FreqAI Daily Retraining: Fixed Pre-Result Protocol

**Recorded 2026-10-20 during execution, BEFORE viewing nine-month portfolio results.**

The user requested research covering all nine months using the saved FreqAI 180-day daily-retraining setup and uncertainty filter. It is **not causally valid to apply already-trained July–September 2026 model weights to January–June 2026**. To make January–September 2026 a genuine simulated trading window, we added July–December 2025 prehistory for each fixed symbol.

## Historical sources and safety

- Symbols BTCUSDT, ETHUSDT, SOLUSDT only; no addition to whole Binance universe.
- Binance Vision public monthly BTC/ETH/SOL archives for **July–December 2025**: **36 ZIPs** (5m klines and funding rates), each checked against its original Binance publication SHA256.
- **54** preserved January–September 2026 ZIPs were **reverified** against Binance-published SHA256 and linked without rewriting original data.
- Total **90 archives**; 2025 new payload **7,289,911 bytes**. Exact download receipts: isolated VPS `/opt/nbot-v7-20261020/runs/freqai-nine-month-180d-2026/source_receipts.json`, SHA256 `25534cdd0adaed2c58b7e2384cfd433921ae06f26e9cda4ce791e59003c18faa`.
- The price/funding archived source proves file integrity, **NOT historical active-contract lifecycle, tradability, spread, mark fill, actual exchange partial fills or ordering**. Therefore contract grade remains `ARCHIVE_OBSERVED_UNVERIFIED_LIFECYCLE`.
- New source-hashed 15-month dataset July 2025–September 2026 (only January–September 2026 is the nine-month economic portfolio window): **436,609** candidate labels, three coins with complete monthly funding archive coverage, same V7 5m stop-first aftercost proxy label policy as before. Immutable separate DB `labeled_2025jul_to_2026sep.sqlite` SHA256 `26ffb66806142c6c959c6f5a2a9f72bbab73ee16d83489d4841913646076db14`. Original nine-month dataset and model outputs are not modified.

## Predefined model and portfolio policies (no result-based tuning)

- Real upstream installed FreqAI 2026.9 **LightGBMRegressor.fit** via pinned custom V7 research adapter; not full native FreqAI `start_backtesting` or inherited-weight `continual_learning`. Preexisting research hyperparameters fixed (LightGBM n_estimators 120, learning_rate 0.04, max_depth 5, num_leaves 15, min_child_samples 20, reg_lambda 2, deterministic seed 72026, n_jobs 1).
- A daily model is freshly fitted **at 00:00 UTC on each of 273 dates January 1 through September 30, 2026**. Each sees only matured labeled V7 opportunity data from 180 preceding calendar days. Last 14 days reserved strictly for pre-cutoff calibration; model fit gets the earlier ~166 days. Fixed target: outcome net after V7 2% stop, 3% take, 60-minute horizon, modeled fees/slippage/funding proxy, 20 V7 candidate families and eligible LONG/SHORT sides.
- Daily rolling vs **monthly (9 models)** vs **frozen January 1**; monthly reuses the **exact same saved daily first-of-month model weights** for its entire calendar month, frozen reuses the exact January 1 model for all nine months. All started on January 1, so no changing the starting fitted head between controls.
- Forecasts keyed and SHA verified by original candidate timestamp, symbol, family, side, source digest, model training label time. One global opportunity across all three coins at one common 5-minute decision time, or NO TRADE.
- Three **predefined** entry rules for each retrain cadence:
  1. `RAW`: enter if net-return estimate is positive.
  2. `UNCERTAINTY`: net estimate minus 75th percentile absolute error fitted on the preceding 14-day conditional candidates must exceed 0.
  3. `STRESS`: as uncertainty plus an **additional +25bp net prediction entry margin**.
- Nine independent accounts: one per retraining cadence × entry rule, all one continuous nine-month **$10,000 initial wallet / $1,000 stake / one-slot** V7 proxy; NO TRADE 0 exposure is separate baseline. Each also reports an extra **25bp of realized roundtrip cost per executed trade**. This extra post-execution cost is distinct from changing entry policy.
- No optimizer search, no replay-tuned coin/strategy blacklist, no new stop-loss, no trading permissions or source-unverified funding pass.

## Scientific interpretation gate

This 2026 period was inspected extensively in previous NBOT V6/V7 research. Even clean as-of labels and promising nominal profit **cannot establish pristine out-of-sample profitability or authorize deployment**. The research instead quantifies whether retaining the same daily uncertainly-gated idea across **nine separate market months** beats frozen and monthly controls, after modeled costs and additional execution stress.

If daily uncertainty cannot beat NO TRADE and monthly/frozen through varied months, label it not generalizable. If it appears better, require enough independent trades, seven-day-block chronological resampling on paired daily aftercost PnL, selected-candidate forecast calibration, native exchange fill/stop/funding parity, and genuinely new calendar data before model promotion. `LEARN-3C` remains HOLD until owner-reviewed evidence passes the full gate.

**Code:** [Source backfill](research/freqai_v7_ninemonth_sources.py) · [273 daily and 9 monthly backtest](research/freqai_v7_full_nine_month_daily.py) · [independent SHA and causal audit](research/freqai_v7_full_nine_month_audit.py).
