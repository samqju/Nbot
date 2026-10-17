# NBOT V6 — Pre-registered January-onward history / training-window research (2026-10-17)

**Status: FROZEN PROTOCOL; ZERO NEW MARKET-DATA DOWNLOADS, MODEL FITS OR BACKTEST RESULTS UNDER THIS PROTOCOL.** Created **before** opening outcomes in the planned evaluation blocks. This is research-only M2R planning; M2 remains NO-GO and M3 is not commissioned. No V5, paper daemon, order credentials or release authority.

## Inputs and quality gate (must pass before any scoring)

- **Archive starting point:** January 1, 2026 00:00:00 UTC to the latest fully closed available historical candle; original **25 fixed** Binance USDT-M perpetual pairs from `user_data/config.json`. Public futures 5m and 1h OHLCV plus hourly mark/funding events as needed by Freqtrade; use as-listed market history, never fabricate prelisting candles. Do not upload massive raw files to GitHub.
- On authorized **8GB-Observation** VPS, first verify trusted SSH host key, isolated V6 branch/git status, no persistent trading containers, actual total/disk/RAM budget and tagged FreqAI image. Inventory exact start/end UTC, expected/actual candles, timestamps, gap/duplicates, OHLCV sanity, funding event coverage and file hashes per pair/timeframe. Save compact audit JSON plus commands/logs to GitHub.
- **DO NOT EXECUTE test fitting until native FreqAI 12-future-bar outer cutoff is checked in the installed image, the official `has_bias=Yes` decision-column mismatch is explained or appropriately isolated, and possible label leakage is corrected.** Source-only review is not a substitute.
- Warm up all 1h indicators before each training period; never use future data to backfill prelisting or beginning-of-history windows. If a required coin/window is not data-ready, mark a coverage failure without silently replacing the coin based on future PnL.

## Frozen evaluation dates selected by calendar, not outcomes

All boundaries UTC, inclusive start and exclusive end, regardless of market performance. **Previously unscored under documented Freqtrade portfolio outcomes**, subject to an audit for any additional earlier inspection before calling them final blind tests:

| Block | Official portfolio outcome evaluation timerange | 30-day train | 60-day train | 90-day train | 180-day train |
|---|---|---|---|---|---|
| A | `20260501-20260601` (May) | PLANNED | PLANNED | PLANNED | NOT ELIGIBLE from January-only start |
| B | `20260601-20260701` (June) | PLANNED | PLANNED | PLANNED | NOT ELIGIBLE from January-only start |
| C | `20260701-20260801` (July) | PLANNED | PLANNED | PLANNED | NOT ELIGIBLE without full warmup proof |
| D | `20260801-20260901` (August) | PLANNED | PLANNED | PLANNED | PLANNED if 180-day training plus indicator warmup confirmed |

This choice intentionally **excludes September and Oct 1–15**, whose portfolio outcomes have already been examined. July/Aug historical candles have served as earlier September model-training inputs; do not misrepresent them as never seen by any model. If any study outcomes in A–D were already examined during development, disclose that, and treat them as replication rather than pristine blind acceptance.

Each rolling model fit follows the same historical as-of cutoff; keep `backtest_period_days=7`, all strategy/feature/LightGBM hyperparameters, one global position and 0.4% after-cost forecast entry filter (where applicable) frozen. Separate `freqai.identifier` and artifacts for 30/60/90/180; never reuse/relabel trained snapshots as if freshly fitted. Run any necessary purged internal model-validation experiment independently, clearly versioned, not as a silent change to the original benchmark.

## Frozen baselines and accounting

- Original frozen price-return FreqAI, original frozen simple no-ML, combined after-cost FreqAI, breakout-family after-cost FreqAI, pullback-family after-cost FreqAI, corresponding matched-exit no-ML controls and **NO TRADE**.
- Identical 25 markets (unless not historically eligible, reported as excluded), 100,000-USDT simulated Freqtrade wallet, **1,000 USDT per position**, **1×**, max **one simultaneous trade**, base engine 0.05% fee **each side**. Verify engine funding timestamps/sign, hour-boundary closure; note prior two September discrepancies separately.
- Keep **hypothetical 0.21% future-trade training-label reserve** distinct from official engine fee/funding trade results. Fixed-fill extra assumed **+10, +15 and +25 basis points ROUNDTRIP** beyond engine costs are sensitivity runs, not real spread fills. Report order type, stop gaps, missing spread evidence and fill-path limitations.
- Save per-block & aggregate simulated closed trades, win/loss, total PnL, net/trade after *explicit* cost, max drawdown, time at risk, hold time, pair/side/exits, rejected/unavailable model signals, estimated uncertainty with weeks as dependent units, and calibration (predicted net advantage versus later after-cost candidate outcomes). Separate overlapping hypothetical outcomes from actually executed Freqtrade portfolio trades. Regime analyses use *only as-of indicators* and report all resulting buckets, not hindsight-chosen winners.

## Comparison and NO-GO rules

1. Primary scientific question: does *longer training data* improve unseen, matched-date, matched-strategy predictions/economic outcomes compared with frozen 30-day training and NO TRADE? Estimate per-month and combined results; do not choose a winning lookback after inspecting one block and relabel it a clean final test.
2. Do not promote a model solely for wins in any one month, higher candidate win rate, better average of overlapping hypothetical opportunities or smaller mean error. Favor NO TRADE whenever estimated net expectancy is not demonstrably positive under uncertainty/realistic costs and M2 integrity cannot be certified.
3. A statistically attractive comparison cannot overcome `has_bias=Yes`, uncertain executable fills, internal label embargo limitations, model/model-version leakage or unresolved readiness. Release remains M2 NO-GO until separately evidenced; M3 formal gate, M4 paper up to 20 positions, M5A up-to-25 eight-hour selector and M7 real money remain LOCKED or NOT STARTED.

**Blocking operational observation on 2026-10-17:** authorized laptop available, but saved PuTTY session `8GB-Observation` requires unverified SSH host-key interaction, so no VPS access. Never auto-accept changed/unknown keys, bypass verification or switch to legacy machines. This document is a pre-registration, not results.
