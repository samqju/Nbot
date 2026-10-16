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
    strategies/NbotV6.py
tests/test_nbot_v6.py
.github/workflows/ci.yml
~~~

No V5/G1–G7 modules, execution services, source-data vaults, independent research databases or legacy CI are used. Legacy V5 main and history remain preserved and are not part of this checked-out V6 tree.

## Initial behavior

- Binance USDT-M isolated futures, 8 markets initially, 5-minute candles with BTC-related 5m and 1h FreqAI features.
- EMA20/EMA50 direction plus previous 20-candle breakout and simple EMA pullback ideas; one LightGBM raw future-price-change model.
- Reject missing/outlier model predictions; only qualified directional signals can trade. NO TRADE is normal.
- At most one open trade globally, 1x leverage, illustrative 3% stop and 5% ROI. Dry-run startup safety and disabled API/Telegram.
- The fixed 0.2% cost allowance is only a provisional estimate, NOT measured actual after-cost trade economics.

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
