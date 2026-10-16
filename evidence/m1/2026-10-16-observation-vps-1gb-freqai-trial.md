# NBOT V6 M1 — One-GB VPS native FreqAI bounded experiment

**Date:** 2026-10-16 UTC  
**Host:** owner-authorized *Observation-VPS*, Ubuntu 24.04 x86_64, 2 vCPU, **954 MiB total RAM**, **no swap**, no Docker.  
**Isolation:** `/home/ubuntu/nbot-v6-m1-20261016`; private Python virtualenv, isolated optional shared-library unpack and downloaded files in the V6 folder. No root/system installs, V5 service changes, Binance keys, Telegram secrets, live bot or real orders.  
**Resource limit:** `systemd-run --user --scope -p MemoryMax=440M -p CPUQuota=90%` for backtests; Python numerical libraries restricted to one CPU thread. This hard cap protects the host but does *not* replicate a larger VPS's available memory.

## What worked

1. **Native installation:** official PyPI `freqtrade==2026.9`, `lightgbm==4.7.0`, `datasieve==0.1.9`, `scikit-learn==1.9.1`, `xgboost==3.2.0` inside the private virtualenv. For LightGBM's OpenMP shared-library dependency, the Ubuntu `libgomp1` Debian package was **downloaded and unpacked privately** (not system-installed), and used solely with `LD_LIBRARY_PATH` for the test process. The package installer ran inside a 440 MB memory limit.
2. **Real Binance USD-M historical data:** Freqtrade's **native** `download-data` completed successfully on BTC/USDT:USDT with `--trading-mode futures --days 60 --timeframes 5m 1h`: **17,476 BTC 5m OHLCV records, 1,456 1h OHLCV records, 1,456 hourly mark-price records and 183 funding-rate records**. This was obtained from the actual Binance public exchange API with no account credentials.
3. **Small FreqAI LightGBM fit + completed backtest:** Config `user_data/config.m1-lowmem.json` is an explicit DIAGNOSTIC override: **BTC only, 3-day rolling window, 5m-only features, indicator period 7, zero shifted candles, 30 estimators, 1 backtest day**. Trained LightGBM on **681 valid examples with 5 features**, from September 28–30, 2026; FreqAI log recorded `Done training BTC/USDT:USDT (0.51 secs)`, generated prediction artifacts, and the official backtester completed **October 1–2, 2026, exit code 0**, 288 candles. **Zero trades, zero PnL.** This is a genuine end-to-end technical training/backtesting *micro-smoke*, NOT profitability or acceptance of the original full configuration.

## What did not work under 440 MB

- **Original V6 configuration:** BTC only, **30 days** training, 5m/1h features and original indicators. Native Freqtrade loaded real data, resolved the actual LightGBMRegressor, reached `Starting training BTC` / `Training on data from 2026-09-01 to 2026-09-30`, then the memory-limited scope exited **137 (killed)**. No model fit/backtest completion.
- **30-day leaner configuration:** `user_data/config.m1-30day-lean.json`, BTC only, 30 days training but 5m-only, 5-ish features and 30 estimators. It too reached the training phase and exited **137** under the same 440 MB process limit. This establishes that *even the lean 30-day run does not pass this particular conservative memory cap*. It does NOT prove that every 1-GB machine or optimized variant is categorically impossible.
- Both failures are inside explicitly memory-limited tests, with the Ubuntu host continuing to respond. The host had ~534 MiB available memory after tests and ~42 GiB free disk. No background Freqtrade trade process was left running.

## M1 conclusion

**M1 is PARTIALLY VERIFIED, NOT ACCEPTED.** The official Freqtrade pipeline and actual LightGBM fit have been proven with a deliberately reduced training window. The **unchanged 30-day V6 target, full 5m/1h features, 7-day walk-forward backtest, 25 pairs, funding/slippage analysis and actual trade validity are still not accepted**. There were zero trades in the micro-run; we cannot estimate profitability from it.

This refines the previous hardware recommendation: **8 GiB is a comfortable recommendation for multi-market research, NOT a universal minimum.** This user-authorized 1-GB VPS handled native package installation, Binance downloads and a 3-day FreqAI micro-backtest; it did **not** handle 30-day training under 440 MB. Next capacity tier should be tested carefully in an isolated **2–4 GiB** research environment with hard memory caps, adding pairs only after genuine single-pair 30-day results. A fully dynamic 25-pair active FreqAI VPS may need more; benchmark and measure instead of guessing.

**Do not enable real trading, Telegram or scheduled research while M1's original acceptance gate remains unmet.**
