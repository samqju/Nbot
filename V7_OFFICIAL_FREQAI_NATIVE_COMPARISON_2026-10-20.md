# NBOT V7 — Actual Official Freqtrade/FreqAI Native Three-Coin Benchmark

**Date:** 2026-10-20 IST  
**Owner question:** Why not install the real Freqtrade + FreqAI and see whether its OWN predictive AI learns better decisions? Aren't bots using this technology successfully?  
**Status:** **ACTUALLY INSTALLED + TRAINED + NATIVE HISTORICAL BACKTESTED**. The vendor's unmodified example strategy was used with configurable research-only capital/timeframe/costs. **Negative after-fee native economic result; no evidence that retraining produced profitable learning.**  
**Scope:** Only BTC/ETH/SOL Binance USDT-M perpetual futures, one position, historical Jan–Sep 2026. **NO paper/dry-run service, no private credentials, no live orders.**  
**Separation:** Isolated `/opt/nbot-v7-20261020/freqai-standalone-20261020/`; current NBOT V7 production/runtime core and previous artifacts untouched.

## 1. What was installed and how we know it really is FreqAI

- Cloned upstream **Freqtrade stable tag 2026.9**, source commit **`1f394eaebc2f46a83d26971388628707802f8602`** into separate repo/venv.
- The VPS initially lacked `python3.12-venv`, installed this OS prerequisite; no service restart was required. Created independent Python 3.12 virtual environment; installed Freqtrade editable source plus its official `requirements-freqai.txt` (LightGBM, scikit-learn, datasieve, etc.). CLI version reports **Freqtrade 2026.9**.
- Used upstream **`freqtrade/templates/FreqaiExampleStrategy.py`** and upstream **`freqtrade/freqai/prediction_models/LightGBMRegressor.py`**, **not** V7's imitation or V6 signals. Official docs explicitly say the example is a **DEMONSTRATION, NOT a production profitable strategy**.
- Bound config file **[research/freqai_official_three_coin_config_2026.json](research/freqai_official_three_coin_config_2026.json)**: Binance futures isolated, dry-run true (command still `backtesting`), zero API credentials, BTC/ETH/SOL static pairs, `5m`, `max_open_trades=1`, stake **1,000 USDT**, wallet **10,000 USDT**, fee **0.0005 each side** (10bp total roundtrip modeled), `train_period_days=90`, `backtest_period_days=30` (rolling monthly retrain), 12-candle future-return label, 44 engineered features used, LightGBM 120 estimators, n_jobs=1, 1-CPU thread environment. We did NOT inject trading outcomes into predictions after their entry.
- Protected VPS filesystem: 96GiB total, approximately 92GiB still free after research packages/data (check Oct 20). No Docker required, no new order service deployed and no V7 runtime model promotion.

## 2. Actual Binance USDT-M historical market data

Official Freqtrade `download-data` from public Binance exchange API:
```sh
<isolated-venv>/bin/freqtrade download-data \
  --userdir <isolated-user-data> --exchange binance \
  --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT \
  --timeframes 5m --trading-mode futures \
  --timerange 20260101-20261001 \
  --datadir <isolated-official-data> --no-parallel-download
```

`freqtrade list-data --show-timerange --trading-mode futures` reports **9 native series** (3 pairs × 5m futures + 1h mark + 1h historical funding-rate):
- BTC/ETH/SOL **each have 78,624** futures 5m candles dated exactly **2026-01-01 00:00 UTC to 2026-09-30 23:55 UTC**.
- Each has **876** funding rate events from Jan 1 through Oct 19 (read-back archive includes some newer records; only backtest-period data used by engine), and **6,982** 1h mark candles from Jan 1 through Oct 18.
- These are **public exchange API records** with local downloads, not independently Binance-CHECKSUM-verified like the original V7 research ZIPs; native historical symbol-lifecycle/suspension validation and order-level fills are still unverified.
- **Model training dates** logged by FreqAI: e.g., Apr1 model trained on Jan1–Mar31 on approximately **20,694** samples for each pair, 44 features. More model windows trained as the rolling time window shifted, with saved model and native FreqAI prediction feather files.

## 3. Primary continuous April–September result — FreqAI OWN trained models

Command (not a trade daemon):
```sh
<isolated-venv>/bin/freqtrade backtesting \
  --userdir <isolated-user-data> \
  --config <isolated-user-data>/config-offline-only.json \
  --strategy FreqaiExampleStrategy \
  --strategy-path <upstream-freqtrade>/freqtrade/templates \
  --freqaimodel LightGBMRegressor \
  --datadir <isolated-official-data> \
  --timerange 20260401-20261001 \
  --export trades --cache none --breakdown month
```

**Exited successfully.** FreqAI monthly retraining windows were actually run (some model artifacts may be reused from initial April smoke; see native log). Native Freqtrade backtest with one open trade, commission and historical mark/funding semantics returned:

| Time period in one CONTINUOUS Apr–Sep run | Trades | Net USDT |
|---|---:|---:|
| April–May | 0 | 0 |
| June | **92** | **−217.543** |
| July | 0 | 0 |
| August | 1 | **−2.165** |
| September | 6 | **−18.292** |
| **Total Apr–Sep** | **99** | **−238.000** |

- Starting 10,000 USDT, ending **9,762 USDT** (**−2.38%**); **44 wins / 55 losses (44.4% wins)**; native reported worst max drawdown **247.563 USDT (2.48%)**; **profit factor 0.60**.
- June dominated the losses; the subsequent relative reduction in entries **could** reflect retraining, new regimes, threshold, model bias or market scarcity. Since even later trades were negative, **this is not demonstrated learning to choose positive-after-cost trades**.
- NO TRADE (0 USDT) beats the total after-cost result on this specific research window.
- Native modeling includes commission and Freqtrade's historical funding/mark accounting, **not actual Binance fills, spread/queue/slippage or historically exact delisted-contract filters**; avoid treating −2.38% as a realizable wallet PnL claim.

**Primary native artifact** (unchanged):
`/opt/nbot-v7-20261020/freqai-standalone-20261020/user_data/backtest_results/backtest-result-2026-10-20_07-46-57.zip`
SHA256 **`969a4521cf5ba8371ed798825533b3d4ed7bfb0362de08bd060025d999568a12`**. Continuous native text report `freqai-apr-sep-native.log`, SHA256 **`5c06653d6b70b9b92bc913606ed0a2d075d888b669ce3de766687ecebcdabf37`**.

## 4. Separate period cross-checks — DO NOT ADD OR DIRECTLY COMPARE WITHOUT ALIGNING RETRAINS

The same config and official example strategy were run from **separate wallet starts**:

| Separate backtest command | Trades | PnL USDT | Report SHA |
|---|---:|---:|---|
| Apr 1–May 1 | 0 | 0 | `4f50a276ccebf142d712894efde8fc92957115ed21dbb39c7bbbc06f6238a4b7` |
| Apr 1–Jul 1 | 92 | **−217.543** | `cd7382160b2527821b47b40972f042692e7e08a2252d0cadf7d5bc2eab7dfeca` |
| Jul 1–Oct 1 | **2** | **−1.599** | `0bffd8a678a94237a4d68685086bce85aed72fc80a6816c1e709bbdc0b1b3b08` |

The independent Jul–Sep run's **2 trades/−1.599 USDT is NOT the same as the continuous Apr–Sep run's 7 Jul–Sep trades/−20.457 USDT**. FreqAI partitions rolling training windows based on the backtest start and can reuse cached model prediction windows. This change of experiment anchoring makes a naïve A vs B or subperiod comparison **invalid** unless training/inference models are timestamp-matched or run continuously with the same wallet. Report this discrepancy explicitly; it must be investigated before inference about learning.

The native single-month April smoke trained BTC/ETH/SOL models on Jan–Mar, FreqAI prediction files were stored, yet 0 trades passed the official sample strategy's +1% / −1% forecast entry threshold. This is not evidence FreqAI training failed.

## 5. Comparison to NBOT V7 three-coin brain — only methodological, NOT matched economics

- V7 core 5m-proxy experiment, separate wallets July–Sep: A 233 trades/−340.6883 USDT, B1 377/−660.0041, adaptive B 630/−953.6469. Prior V7 audit found mean forecasts of positive net vs actual negative net on selected trades.
- Official FreqAI benchmark uses a DIFFERENT target (`&-s_close` price forecast), entry gates, native strategy's **−5% stoploss and +10% ROI rule transitioning at 240min**, exit signal, mark/funding engine, and lower/fixed commission with no comparable modeled slip. **Do not claim FreqAI is a matched superior or inferior portfolio model** based on the raw $ amounts/trade counts.
- The test answers the owner's deployment question: real stable FreqAI can run on this exact authorized 8GB VPS, train from Jan–Mar, periodically retrain and produce historical decisions. **It did not produce positive after-cost PnL from its official example on BTC/ETH/SOL here.**
- Consistent with historical **V6 actual FreqAI** prior work: V6 25-pair native supervised/RL pipelines and 8 research families were not profitable under audited costs; V6 12/12 global native tasks made 0 selected trades. FreqAI integration was not totally new, but this isolated upstream-pure 3-coin baseline removes the complexity of V6's custom selectors.

## 6. Known constraints and next scientifically sound experiment

1. Retain frozen upstream baseline; **do not** tune official FreqAI model thresholds using observed Apr–Sep profit and call improvement.
2. Resolve FreqAI backtest-window anchoring/caching differences with matched timestamp/model cutoffs and trade-account comparability. The continuous Apr–Sep series is the best *single* longitudinal comparison currently saved.
3. Evaluate FreqAI **actual future-return prediction calibration**, direction accuracy and trade/no-trade discrimination over all eligible model predictions (not just selected trades); compare against a simple always-flat baseline and cheap momentum controls, stratifying by market regime and funding costs.
4. A second V7-specific experiment MAY implement a frozen after-cost target and risk-adjusted abstention in **FreqAI itself**, keeping one real slot and unchanged costs/labels. Test on chronological development-only folds first. No production-safe edge until genuinely new untouched BTC/ETH/SOL forward data exists.
5. No Full Binance expansion, no model promotion or paper/live operation remains authorized; `LEARN-3C HOLD` persists.

**Upstream docs:** https://docs.freqtrade.io/en/stable/freqai/ , https://docs.freqtrade.io/en/stable/freqai-running/ , https://docs.freqtrade.io/en/stable/backtesting/ , https://docs.freqtrade.io/en/stable/freqai-reinforcement-learning/ . Official docs warn the example strategy is showcase-only and RL training rewards can exploit simplified simulation. Successful deployment of tooling does not certify investment profitability.

## 7. GitHub/VPS source authority and reproduction

- Config on `V7`: [research/freqai_official_three_coin_config_2026.json](research/freqai_official_three_coin_config_2026.json), commits `cc004764a0b6fd0c9a99ad10cb7260614f6f9562` and `e1a4b2a44c3ad530d6cf0e4c505819e5c868d69e`.
- VPS effective config SHA256 `d35f43f9f27efe5753ec2af809de5d6dad2e9ee08b0e3b0fb3e30c802057d595`.
- Native log separate Apr–Jun SHA256 `a19dbbb01cb3c6783486ac34d343370b87f4cebfe41df1a33f2e6f47f2b7f7c6`.
- Native log separate Jul–Sep SHA256 `d2c9353338b07360674fe370bd91d03a05d444189c191df88d77d6e65da21ed5`.
- Isolated upstream repository and venv are **NOT** pushed into NBOT source or used by V7 default runtime. The user can re-run the above pinned commands on the VPS. Original `V7_CHAT_HANDOVER.md` and `V7_ROADMAP.md` shall record this observation without changing the frozen source roadmap or claiming profitability.
