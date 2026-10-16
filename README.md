# NBOT V6 — Clean Freqtrade + FreqAI Bot

**Status:** Small research prototype; **not deployed**, **not backtested in production framework**, **not proven profitable**, **no real orders authorized**.

NBOT V6 is an isolated Freqtrade strategy powered by FreqAI's LightGBM regression model. We use Freqtrade for exchange data, trade execution, risk/accounting, historical backtesting and dry-run. We use FreqAI for features, retraining and prediction. NBOT's custom code only describes market features and trading decisions.

## Minimal source tree

~~~text
README.md
ROADMAP.md
docker-compose.yml
user_data/
    config.json
    config.paper-research.json
    strategies/NbotV6.py
tests/test_nbot_v6.py
.github/workflows/ci.yml
~~~

No V5/G1–G7 modules, execution services, source-data vaults, independent research databases or legacy CI are used. Legacy V5 main and history remain preserved and are not part of this checked-out V6 tree.

## Initial behavior

- Binance USDT-M isolated futures, 8 markets initially, 5-minute candles with BTC-related 5m and 1h FreqAI features.
- EMA20/EMA50 direction plus previous 20-candle breakout and simple EMA pullback ideas; one LightGBM raw future-price-change model.
- Reject missing/outlier model predictions; only qualified directional signals can trade. NO TRADE is normal.
- Single-bot mode has at most one open trade; independent paper-research mode permits up to 10 simulated positions by default (hard cap 20), with the existing 8-pair universe currently limiting simultaneous positions to 8. Forced 1x leverage, illustrative 3% stop and 5% ROI, dry-run startup safety and disabled API/Telegram.
- The fixed 0.2% cost allowance is only a provisional estimate, NOT measured actual after-cost trade economics.

## Continuous Paper Research — optional (not yet deployed)

FreqAI normally trains from completed market candles and their future-return labels, **not from realized paper or live trade PnL**. This new mode uses Binance **mainnet public market data** and **Freqtrade's standard dry-run accounting** to log hypothetical entries/exits separately while a future one-position execution bot may be holding a real position. It is intended to continue independently; it **does not share a trading database or FreqAI model identifier** with single-bot mode.

- Independent config overlay: [user_data/config.paper-research.json](user_data/config.paper-research.json).
- Research default is **10 available simulated-position slots** and a maximum of 20 allowed by the startup guard. Slots are a ceiling, not a trade target. Freqtrade normally holds only one open trade per pair, so **8 monitored pairs mean at most 8 concurrent simulated positions**, regardless of a 10-slot setting. Completed paper trades can accumulate over time.
- Both modes still run in **dry-run only** and refuse Binance exchange credentials in the paper-research mode. This repository has no live-capable V6 runtime.
- The paper and single modes use two different FreqAI model identifiers and two separate Freqtrade trade databases; both are instances of standard Freqtrade, **not another custom execution engine**.
- To review trade quality, use ordinary Freqtrade recorded paper trades and performance tooling. Those paper PnL results are **evaluation feedback**, not automatically new supervised-learning labels. Adding genuine trade-outcome labels, if useful, needs independent chronological/selection-bias controls and is **not built here**.

To validate configuration/strategy on an isolated development machine:

~~~bash
docker compose --profile research config
docker compose --profile research run --rm paper-research list-strategies \
  --config /freqtrade/user_data/config.json \
  --config /freqtrade/user_data/config.paper-research.json
~~~

**Only after M1–M3 historical/economic gates and a VPS capacity preflight**, a human operator may explicitly start a monitored paper process:

~~~bash
docker compose --profile research run --rm paper-research
~~~

The research process is *opt-in*: no automatic service startup or persistent restart policy. The official image must be pinned to a tested digest before sustained deployment. Never start V6 paper research on an undersized or protected legacy VPS without a hardware/safety review.

**We should review 10–20 completed paper trades as an early debugging checkpoint, not as statistically sufficient evidence to authorize real trading.** The roadmap requires broader independent, forward, after-cost validation. Any real Binance order submission remains separately locked.

## Reproduce basic checks

On an isolated Docker development host, from repository root:

~~~bash
docker compose config
docker compose pull
docker compose run --rm freqtrade list-strategies --config /freqtrade/user_data/config.json
docker compose run --rm freqtrade download-data \
  --config /freqtrade/user_data/config.json --trading-mode futures \
  --timeframes 5m 1h --days 90
~~~

Then choose a fully downloaded backtest interval with at least 30 days of prior model training history and warm-up:

~~~bash
docker compose run --rm freqtrade backtesting \
  --config /freqtrade/user_data/config.json \
  --strategy NbotV6 --freqaimodel LightGBMRegressor \
  --timerange YYYYMMDD-YYYYMMDD
~~~

Do not assume this historical run will pass without adapting to an exact pinned Freqtrade version. These commands have **not** been executed on either existing VPS.

Offline unit tests need Python, pandas and numpy:

~~~bash
python -m unittest discover -s tests -v
python -m py_compile user_data/strategies/NbotV6.py
python -m json.tool user_data/config.json
~~~

CI additionally tests strategy discovery in the official FreqAI Docker image. **Strategy discovery does not establish actual model training, a passing backtest, forward paper performance, or profitability.**

**Do not start a persistent VPS bot or place any live orders before its roadmap gates are reviewed.**

See [ROADMAP.md](ROADMAP.md) for the step-by-step milestones, evidence requirements, V5 preservation and deliberate default-branch migration policy.

Official references: https://www.freqtrade.io/en/stable/freqai/ and https://www.freqtrade.io/en/stable/strategy-customization/.
