# NBOT V6 — M1 actual evidence and execution blockers

**Date:** 2026-10-16 (UTC)
**Milestone:** M1 Official Freqtrade/FreqAI historical data, LightGBM training and backtesting
**Status:** **IN PROGRESS — PARTIALLY VERIFIED**. A reduced 3-day, BTC-only LightGBM training/backtest SUCCEEDED on the 1 GB VPS, but the full 30-day M1 configuration remains unverified and failed the conservative memory-cap test.
**Repo:** samqju/Nbot, branch prototype/v6-freqtrade-freqai-20261016
**NO LIVE TRADING / NO REAL ORDERS / NO BINANCE API KEYS**

## Real evidence collected

1. **Both saved PuTTY VPS reachable.** On the two Ubuntu VPSs, each has 2 vCPU, 954 MiB RAM and around 43 GiB free disk, no Docker installation. The Observation VPS has **no swap**. Since the initial inspection, a Python virtualenv with pip and native Freqtrade 2026.9 was installed **locally within the isolated V6 working folder only** (no system-wide installation). We made **no system package installs, no service changes and no modification of V5**, and cloned V6 only into the isolated home folder `/home/ubuntu/nbot-v6-m1-20261016/source`.
2. **Real Binance USD-M API reachable on Observation VPS.** Public `https://fapi.binance.com/fapi/v1/exchangeInfo` returned HTTP 200. The pure Python preflight tool, `scripts/m1_market_preflight.py`, executed on that host and checked all **25 configured USDT-M perpetual candidates** against real contract metadata and a limited 5m/1h historical data sample for each.
3. **Result:** **25 of 25 passed, zero failures**. Source report saved in `evidence/m1/2026-10-16-binance-public-preflight.json` with per-pair data, timestamps, recent candle gaps and 60-day existence probes. This is **not a complete 60-day data-quality audit** or proof of model readiness.
4. **Actual official Freqtrade/FreqAI Docker image loaded on GitHub runner**: Freqtrade **2026.9**, immutable image digest `freqtradeorg/freqtrade@sha256:e0ca51420b80357edcbec3970fd8a33ebebeacd53b914aed2735a9c14fe94535`. Its default strategy import checks pass. GitHub runner had 15 GiB RAM.
5. **First genuine M1 CI attempt:** [run 38927033699](https://github.com/samqju/Nbot/actions/runs/38927033699). It stopped **before an exchange request** because Docker was mistakenly started with GitHub runner UID, which lacked access to the image's executable in ftuser HOME. This container permission issue was corrected.
6. **Second genuine M1 CI attempt:** [run 38927259804](https://github.com/samqju/Nbot/actions/runs/38927259804). It passed preparation, pulled official image and called the official `freqtrade download-data` command, but Binance returned **HTTP 451** to GitHub's US-hosted runner from `https://api.binance.com/api/v3/exchangeInfo`. Therefore data could NOT be fetched, model training and backtesting steps did NOT start. Repeated GitHub-hosted retries from the same restricted region are disabled by default.
7. **Last offline CI:** [run 38928749522](https://github.com/samqju/Nbot/actions/runs/38928749522) passed 40/40 Python unit tests and official Freqtrade strategy discovery, with the blocked M1 job explicitly skipped. These tests are NOT a completed model fit/backtest.

## New evidence: actual 1-GB Observation VPS FreqAI trial

After the initial GH Actions Binance 451 and hardware preflight, the owner asked us to test the existing small VPS instead of assuming an 8-GB requirement. We therefore ran a **bounded private native Freqtrade 2026.9 experiment** using user-scoped `systemd-run` with **MemoryMax=440M**, CPUQuota=90%, 1 thread per numerical library, and an isolated Python environment under `/home/ubuntu/nbot-v6-m1-20261016`.

- **INSTALL PASSED:** Native Freqtrade 2026.9 + LightGBM 4.7, scikit-learn, DataSieve and XGBoost packages in the V6 virtualenv; OpenMP shared library extracted from an Ubuntu Debian package locally, with no system-wide installation. Freqtrade CLI reported version 2026.9.
- **DOWNLOAD PASSED:** Actual `freqtrade download-data` from public Binance futures for BTC/USDT:USDT fetched **17,476 BTC 5m futures candles, 1,456 BTC 1h futures candles, 1,456 hourly mark-price entries, 183 funding-rate records**. No API keys or money used.
- **TRUE SMALL FREQAI FIT + HISTORICAL BACKTEST PASSED:** Explicit diagnostic overlay `user_data/config.m1-lowmem.json`, BTC alone, **3 days of training**, 5m-only and fewer features, ~681 usable examples, **5 model features**, LightGBM 30 trees and 1-day backtest. FreqAI logged `Done training BTC/USDT:USDT (0.51 secs)`; real native Freqtrade 2026.9 backtesting completed **2026-10-01 to 2026-10-02** with exit code 0. **Zero entries, zero profit/loss**. This is an end-to-end technical demonstration only, not evidence for trading profitability or normal model scale.
- **ORIGINAL 30-DAY MODEL TRAINING FAILED AT MEMORY LIMIT:** Actual model process reached a September 1–30 BTC/USDT:USDT FreqAI training window, then exited **137 (killed)** inside the 440-MB scope. This test retained the original V6 5m/1h features.
- **LEAN 30-DAY MODEL ALSO FAILED AT MEMORY LIMIT:** `user_data/config.m1-30day-lean.json` uses just one coin, 5m features and a small 30-tree model, but keeps the **full 30-day** training window. It also reached model training and exited **137** under the same cap. This is a bounded test outcome, not a universal claim that 1 GiB machines can never train FreqAI.
- **VPS remained healthy:** After tests it had about **534 MiB available RAM** and 42 GiB free disk; no persistent Freqtrade service or real trading process was running.

Detailed dated methods and results: [evidence/m1/2026-10-16-observation-vps-1gb-freqai-trial.md](evidence/m1/2026-10-16-observation-vps-1gb-freqai-trial.md).

**Revised infrastructure conclusion:** **8 GiB RAM is a comfortable multi-market research recommendation, not a hard minimum for all FreqAI tests.** We proved an actual small historical training/backtest on 1 GiB. Under a protective 440-MB process limit we could not complete a 30-day model, so test **2–4 GiB** on isolated hardware next, with resource measurement, before sizing a 25-coin operation. M1 remains NOT ACCEPTED pending full-history feature compatibility, 30-day training, 7-day historical backtest, valid predictions, at least some strategy outcome assessment and reproducibility.

## What M1 has and has NOT established

| Requirement | Evidence | Status |
|---|---|---|
| Clean V6 strategy/config, no keys, official import | 40 offline tests + Freqtrade 2026.9 discovery | VERIFIED at import/test level |
| Verify 25 futures contracts and 5m/1h recent samples exist | Independent 25-of-25 real Binance REST preflight | VERIFIED for bounded samples only |
| Fully download/check 60 days BTC/ETH 5m/1h futures/mark/funding candles | Binance 451 from US GitHub host | **NOT DONE** |
| Train native FreqAI per-pair LightGBM on 30 rolling days | 3-day fit passed; 30-day model exited 137 at 440 MB | **NOT DONE for 30-day target** |
| Produce 7-day true out-of-sample backtest and model predictions | 1-day, 3-day-trained BTC technical backtest passed; zero trades | **NOT DONE for M1 target** |
| Verify fees, slippage, funding, lookahead safety, reproducible result | No official completed backtest | **NOT DONE** |
| Real-money execution | Not part of M1 | **LOCKED** |

**Gate M1 has NOT passed. No profitability assertion, no VPS trading service and no promotion to M2.**

## What is required to finish M1 safely

Use **one isolated 64-bit Linux development host**, preferably **8 GB RAM** (minimum candidate 4 GB RAM), at least 2 vCPU, Docker Engine and Compose, comfortable free disk, and normal permitted access to public Binance spot and USDT-M API URLs (both can be queried by Freqtrade/CCXT). Provision it in a location where exchange access is allowed. No Binance account API keys or Telegram credentials are required for historical backtesting.

A reproducible official M1 job remains inside `.github/workflows/ci.yml` gated by a deliberate `[RUN-M1]` marker in PR #50's title, to prevent further Binance 451 failures. It performs two-pair BTC+ETH market downloads with funding and mark data, history inspection, FreqAI LightGBM training and seven-day historical backtesting, retaining logs and result artifacts. On the suitably located development host, run those **same official Freqtrade commands** against the pinned image, and adjust only proven compatibility issues with logged results. Validate the full 25-pair universe and extend beyond the smoke set after the genuine two-pair integration passes.

Next acceptance evidence: complete 5m/1h data ranges, gap counts, successful LightGBM fit logs, number of models, actual FreqAI predictions/do_predict results, benchmark transactions/performance (which may be negative), training resource usage, and a safe rerun.

**Avoid uncontrolled resource-heavy runs on either 954-MiB VPS.** We successfully installed and tested a small native FreqAI experiment on Observation using a hard per-process cap; the original 30-day training remains unsuitable at this cap. Do not bypass geographic access restrictions or use real Binance credentials for M1.

Official supporting docs: https://www.freqtrade.io/en/stable/freqai-running/ and https://www.freqtrade.io/en/stable/data-download/ .
