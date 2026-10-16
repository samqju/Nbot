# NBOT V6 — Freqtrade + FreqAI Starter

**Status: offline source prototype. Not deployed or economically validated.**

NBOT V6 is an **isolated** alternative to the V5 custom execution/research stack. The historical V1–V5 source, VPS services, databases, evidence, and approvals remain unchanged.

Freqtrade owns exchange connectivity, accounting, risk/stop orders, historical backtesting and dry-run execution. FreqAI provides the LightGBM model training and predictions. NBOT V6 is a single strategy file with straightforward market intelligence and signal gating.

## Scope and defaults

- Eight Binance USDT-M futures markets to begin with; longer-term target ~50 only after proving resource and strategy behavior.
- Five-minute trading timeframe; BTC features automatically included via FreqAI correlated-pair expansion on 5m and 1h.
- Model inputs: momentum, EMA-distance, volatility, relative volume and candle body.
- Signals: 20-bar breakout or EMA20 pullback in EMA20/EMA50 trend direction.
- One LightGBM model estimates raw 12-candle future price change. It **does not** estimate realized after-cost trade PnL. The 0.2% round-trip cost proxy and 0.4% minimum projected surplus are unvalidated placeholders.
- Predictions that FreqAI declares invalid, stale or out-of-distribution must not generate trades.
- One open position globally, isolated futures with forced 1x leverage, 3% baseline stop and 5% ROI threshold, disabled manual/API entries.
- Dry-run only. The strategy rejects any real-money startup; credentials are empty.
- FreqAI's automatic rolling model updates are **not** an independently approved Champion governance system.

## Quick start on a separate Docker development machine

Do not install this on either existing protected NBOT VPS without a separate capacity/safety review. From the v6 directory:

~~~bash
docker compose config
docker compose pull
docker compose run --rm freqtrade list-strategies --config /freqtrade/user_data/config.json
docker compose run --rm freqtrade download-data \
  --config /freqtrade/user_data/config.json \
  --trading-mode futures --timeframes 5m 1h --days 90
~~~

Then choose a timerange completely covered by the downloaded history and **run a backtest before trying dry-run**:

~~~bash
docker compose run --rm freqtrade backtesting \
  --config /freqtrade/user_data/config.json \
  --strategy NbotV6 --freqaimodel LightGBMRegressor \
  --timerange YYYYMMDD-YYYYMMDD
~~~

Only after upstream Freqtrade reports successful strategy loading and meaningful backtest results, the operator may explicitly start a monitored dry-run:

~~~bash
docker compose run --rm freqtrade trade \
  --config /freqtrade/user_data/config.json \
  --strategy NbotV6 --freqaimodel LightGBMRegressor
~~~

The Compose restart policy is "no". It does not automatically install services. The Docker tag stable_freqai moves over time; pin an exact tested digest before durable deployment.

## Offline source tests

Use Python with pandas and numpy (or the official FreqAI Docker image):

~~~bash
cd v6
python -m unittest discover -s tests -v
python -m py_compile user_data/strategies/NbotV6.py
python -m json.tool user_data/config.json > /dev/null
~~~

The 13 offline tests use a deliberately minimal test double for Freqtrade/FreqAI. They assert FreqAI entry-point invocation, causal indicators, training-label boundaries, long/short/no-trade decisions, absence of trades on missing predictions, one-position and dry-run restrictions. **They do not prove real Freqtrade compatibility or that model training, exchange connectivity or profitability works.**

## Deferred, not secretly implemented

1. Validate real Freqtrade strategy import, data download, runtime schema, historical backtests and future-data/recursive-analysis checks.
2. Evaluate out-of-sample, after-cost profitability with realistic fills, spread, funding and adverse conditions against both non-ML and no-trade baselines.
3. Default Freqtrade max-open-trades=1 does not guarantee selection of the single highest-scored signal across pairs; build cross-pair selection only if justified.
4. Port NBOT's historic 24 pattern detectors as optional features after unit testing; do not import V4 historical labels as automatically trusted training data.
5. Design a separately verified Champion/Challenger promotion mechanism if useful after the baseline works. Do not claim latest model = validated Champion.
6. No real orders, deployment or VPS service changes authorized in this prototype.

## Official references

- https://www.freqtrade.io/en/stable/strategy-customization/
- https://www.freqtrade.io/en/stable/freqai-feature-engineering/
- https://www.freqtrade.io/en/stable/freqai-configuration/
- https://www.freqtrade.io/en/stable/freqai/
