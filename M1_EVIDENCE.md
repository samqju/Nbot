# NBOT V6 — M1 real historical training and backtesting results

**Date:** October 16, 2026 (UTC)  
**Status:** **M1 TECHNICAL GATE PASSED** — actual Binance USDT-M futures history downloaded, all 25 candidate datasets checked, 25 LightGBM models fitted on the intended 30-day FreqAI training window, and a genuine 7-day official Freqtrade futures backtest completed.  
**Trading quality:** **NEGATIVE IN THIS TEST; NOT PROFITABLE/NOT VALIDATED.** M2/M3 must evaluate after-cost performance across more periods.  
**Safety:** Public market data only. No Binance trading credentials, Telegram setup, live orders, persistent paper daemon or changes to V5.

## Test machine and exact reproducibility

- New separately authorized **8GB-Observation** VPS: **2 vCPU, 7.8 GiB reported RAM, 96 GB total disk (approximately 92 GB free after tests)**, Ubuntu, root SSH login using a local PuTTY key, Docker Engine **29.9.1**, Docker Compose **v5.6.0**.
- Public Binance Spot and USD-M futures exchangeInfo API checks: **HTTP 200** on both from this VPS. GitHub's US-hosted runner was previously refused with HTTP 451; no access restrictions were bypassed.
- Official image **Freqtrade 2026.9 + FreqAI/LightGBM**, Docker image digest **freqtradeorg/freqtrade@sha256:e0ca51420b80357edcbec3970fd8a33ebebeacd53b914aed2735a9c14fe94535**.
- Code branch: **prototype/v6-freqtrade-freqai-20261016**. The full 25-coin backtest ran at commit **eeafff5e7ac1e70276db04e0eef2506c875f6594**, with test-only **user_data/config.m1-all25.json** selecting independent model identifier **nbot-v6-m1-all25-20261016**. Candle audit script was subsequently committed at **dd7fbacaeadd66ce6c5ad4e86d7fbffae41b6b0a**.
- All operations stayed inside **/root/nbot-v6-m1-20261016/source**. The official FreqAI image ran via **short-lived Docker containers**, capped at **2 CPUs and 6 GiB** of container memory. This is a CAP, not measured peak RAM; do not infer actual memory requirements from it.
- Actual logs and Freqtrade trade result ZIPs are retained on the user's VPS under **/root/nbot-v6-m1-20261016/** and **source/user_data/backtest_results/**. Raw data/models/trade artifacts are intentionally gitignored; preserve a private backup if needed.

## Real Binance historical data — all 25 candidates

Official command: **Freqtrade download-data**, Binance **USDT-M futures**, all 25 configured pairs, **5m and 1h**, **60 days** requested; Freqtrade also downloaded hourly mark and funding events.

- Result: **25/25 downloaded successfully**, with **100 exchange-data files** (5m futures, 1h futures, 1h mark and 1h funding series for each pair).
- Archive dates verified by our audit: approximately **2026-08-17 through 2026-10-16**.
- [Machine-readable independent candle audit](evidence/m1/2026-10-16-8gb-vps-full25-candle-audit.json): **25/25 pairs passed**, with no duplicate, backward or irregular dates in the 5m futures, 1h futures and 1h mark files, valid sampled OHLCV field constraints, and train/backtest interval coverage. The funding series have valid dates and coverage; they are **sparse exchange funding events (not continuous hourly candles)** and were not incorrectly required to have hourly intervals.
- The earlier metadata/sample-only [25-pair public Binance market preflight](evidence/m1/2026-10-16-binance-public-preflight.json) also passed.
- Example BTC coverage: 5m futures **17,494 candles**, 1h futures **1,457**, 1h mark **1,457**, funding **183** events, with zero audited missing intervals for continuous-price files. All 25 pairs are represented in the JSON report.

**Limitation:** This audits local candle continuity, basic OHLCV coherence and chronological coverage. It does **not** prove there are no exchange-side anomalous prices, economic selection bias, misreported funding or data leakage elsewhere. Those require M2/M3 checks.

## A. Two-pair full-configuration smoke, BTC + ETH

- **FreqAI training:** two genuine LightGBM fits, 30-day historical window **2026-09-01 to 2026-10-01**; BTC trained with **36 features**, ETH with **72 features**, approximately **6,902 model training points** each. Historical predictions were generated and used by the backtester.
- **Backtest:** **2026-10-01 through 2026-10-08** (seven complete days), configured **100,000 USDT simulated wallet**, **1,000-USDT stake**, **one maximum global open position**, 1x leverage.
- **Outcome:** **4 closed trades**, **1 win / 3 losses**, **25% win rate**, **-1.720 USDT** simulated P&L, **10.637 USDT** reported maximum drawdown.
- Official process **exit status 0**, no errors. The first two-pair test used the base identifier in an independent research folder; it never started `trade` mode.

## B. All-25-pair normal-configuration backtest (main M1 acceptance evidence)

- Historical training **2026-09-01 to 2026-10-01**, target **30 rolling days**, with native V6 **5m/1h features, shifted candles, BTC correlation, FreqAI LightGBMRegressor and the 150-tree default model training parameters**.
- Actual logs recorded **25 individual model-training completions**, no `ERROR` log entries, and Freqtrade backtesting **exit status 0**.
- Historical evaluation: **2026-10-01 00:00 UTC through 2026-10-08 00:00 UTC**, all **25 candidate futures pairs**, one global simultaneous simulated position. Independent model identifier **nbot-v6-m1-all25-20261016**.

| Freqtrade reported metric | Actual value |
|---|---:|
| Closed simulated trades | **34** |
| Wins / losses | **9 / 25** |
| Win rate | **26.5%** |
| Total simulated P&L | **-135.640 USDT** |
| Account return on 100,000-USDT dry wallet | **-0.14%** |
| Mean P&L per trade | **-0.40%** |
| Long / short trades | **25 / 9** |
| Long / short simulated P&L | **-63.728 / -71.912 USDT** |
| Profit factor | **0.49** |
| Maximum reported drawdown | **165.156 USDT (0.17%)** |
| Entry signals rejected by Freqtrade | **68** |
| Entry / exit timeouts | **0 / 0** |

- Freqtrade logged a **0.0500% exchange fee** assumption (worst rate from its exchange tier lookup) for the initial two-pair run. Do not infer that these results fully include realistic, independently validated spread, market impact, slippage and funding costs. That is the purpose of M2.
- Model/DataSieve prediction filtering was observed (some out-of-distribution predictions rejected), both **LONG and SHORT** trades occurred, and the configured **one-global-position** constraint was in force.
- LightGBM emitted an **upstream deprecation warning** about `eval_set`, but there were **no runtime ERROR lines**, and no process failure.
- When checks finished, **docker ps returned no running containers**. Neither paper trading nor live trading was started. No auth secrets were supplied.

## M1 acceptance checklist

| Technical gate | Status |
|---|---|
| Correct V6 strategy and dry-run configuration load under official framework | **PASS** |
| Public Binance futures connectivity and exchange-eligible 25-pair metadata | **PASS** |
| Download sufficient 5m/1h futures + mark/funding history | **PASS — 25/25** |
| Run separate trained LightGBM models on real 30-day history | **PASS — 25/25** |
| Obtain model forecasts and run genuine held-out 7-day historical replay | **PASS** |
| Confirm trade/abstention, LONG/SHORT and one-open-position behavior | **PASS for basic mechanics** |
| Detect obvious missing date intervals/invalid OHLCV for downloaded data | **PASS — local dataset audit** |
| Exit successfully with no live order side effects | **PASS** |
| Demonstrate positive, after-cost, stable strategy economics | **NOT an M1 claim; M2/M3 NOT STARTED** |
| Validate 20-slot simultaneous research forward paper on VPS | **NOT M1; M4 NOT STARTED** |
| Owner-governed Binance live money | **M7 LOCKED** |

**M1 is technically complete but the model is not acceptable for deployment on profitability grounds.** Passing M1 only establishes that the infrastructure, FreqAI model, market data and replay engine work together. **Do not authorize M4/M7, migrate V5, add credentials or start a continuous bot based solely on this backtest.**

## Reproduction (future isolated research server)

Commands run against the isolated checkout from the repo root (replace host paths as required):

```bash
docker pull freqtradeorg/freqtrade:stable_freqai
docker run --rm --memory=6g --cpus=2 -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai download-data --config /freqtrade/user_data/config.json --trading-mode futures --timeframes 5m 1h --days 60
docker run --rm --memory=6g --cpus=2 -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable_freqai backtesting --config /freqtrade/user_data/config.json --config /freqtrade/user_data/config.m1-all25.json --strategy NbotV6 --freqaimodel LightGBMRegressor --timerange 20261001-20261008 --export trades
docker run --rm --memory=6g --cpus=2 --entrypoint python -v "$PWD:/freqtrade/work" freqtradeorg/freqtrade:stable_freqai /freqtrade/work/scripts/m1_audit_history.py
```

**Note:** The commands use the mutable `stable_freqai` tag for portability; for a strictly reproducible rerun pin the tested digest above, protect model/data artifacts and use the exact historical dates. Docker's ftuser needs write permission to the mounted `user_data`. See [VPS_SETUP.md](VPS_SETUP.md).

## Earlier obstacles and retained historical research

- [Initial GitHub M1 Docker attempt](https://github.com/samqju/Nbot/actions/runs/38927033699): wrong temporary UID made Freqtrade executable unreadable, corrected. [Second GitHub attempt](https://github.com/samqju/Nbot/actions/runs/38927259804): Binance API refused US runner with **HTTP 451**. These are superseded as blockers by the successful owner-authorized VPS test above.
- [1GB Observation VPS memory-limited trial](evidence/m1/2026-10-16-observation-vps-1gb-freqai-trial.md): completed a **3-day/5m-only** tiny BTC fit/one-day zero-trade backtest under **440 MB process cap**, but full 30-day model was OOM-killed inside that cap. **8GB is not a theoretical minimum**; it was merely the specification of the new available research VPS.
- All V6 source and model artifact IDs are separate from V5; maintain this isolation.
