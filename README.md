# NBOT V6 — Clean Freqtrade + FreqAI Bot

**Status:** Small research prototype; **not deployed**, **not backtested in production framework**, **not proven profitable**, **no real orders authorized**.

NBOT V6 is an isolated Freqtrade strategy powered by FreqAI's LightGBM regression model. We use Freqtrade for exchange data, trade execution, risk/accounting, historical backtesting and dry-run. We use FreqAI for features, retraining and prediction. NBOT's custom code only describes market features and trading decisions.

## Minimal source tree

~~~text
README.md
ROADMAP.md
docker-compose.yml
scripts/bootstrap_history.py
user_data/
    config.json
    config.paper-research.json
    strategies/NbotV6.py
tests/test_nbot_v6.py
.github/workflows/ci.yml
~~~

No V5/G1–G7 modules, execution services, source-data vaults, independent research databases or legacy CI are used. Legacy V5 main and history remain preserved and are not part of this checked-out V6 tree.

## Initial behavior

- Binance USDT-M isolated futures, **25 configured candidate markets**, five-minute candles with BTC-related 5m and 1h FreqAI features. The 25 symbols are an initial *candidate universe*, not a validated exchange/liquidity shortlist; confirm Binance availability, spread, data depth, and VPS cost in M1.
- EMA20/EMA50 direction plus previous 20-candle breakout and simple EMA pullback ideas; one LightGBM raw future-price-change model.
- Reject missing/outlier model predictions; only qualified directional signals can trade. NO TRADE is normal.
- Single-bot mode has at most **one** simultaneous dry-run position; the independent research mode permits up to **20** simulated positions at once, never 20 mandatory trades. Both use a **100,000 USDT simulated wallet**, **1,000 USDT stake per trade**, **1x leverage**, **2% initial stop** and **5% ROI target**. Both remain dry-run only, with API/Telegram disabled.
- The fixed 0.2% cost allowance is only a provisional estimate, NOT measured actual after-cost trade economics.

## Continuous Paper Research — optional (not yet deployed)

FreqAI normally trains from completed market candles and their future-return labels, **not from realized paper or live trade PnL**. This new mode uses Binance **mainnet public market data** and **Freqtrade's standard dry-run accounting** to log hypothetical entries/exits separately while a future one-position execution bot may be holding a real position. It is intended to continue independently; it **does not share a trading database or FreqAI model identifier** with single-bot mode.

- Independent config overlay: [user_data/config.paper-research.json](user_data/config.paper-research.json).
- Research default is **20 available simulated-position slots** (the hard cap). Slots are a ceiling, not a trade target. Freqtrade normally holds one trade per pair, so at most 20 different positions from the current 25-candidate universe can be held concurrently. Completed paper trades can accumulate over time.
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

## How 25-coin AI evaluation works

**Two distinct choices:** (1) which coins are eligible for model training, and (2) whether to open a trade on a particular coin. The V6 starter now includes a **fixed, versioned set of 25 Binance USDT-M candidate pairs**: BTC, ETH, SOL, BNB, XRP, ADA, LINK, DOGE, AVAX, DOT, LTC, BCH, NEAR, UNI, APT, ARB, OP, SUI, TRX, ETC, ATOM, FIL, INJ, XLM, HBAR. These are candidate markets only; verify actual contract support, minimum order sizes, historical coverage, liquidity and resource usage before M1 acceptance.

FreqAI evaluates each configured pair's own momentum, volatility, relative volume, BTC context, recent trend and projected return. **A configured pair is NOT automatically traded.** Signals require an actual strategy setup, a valid model prediction and a forward-return estimate exceeding the placeholder +/-0.6% threshold; otherwise V6 abstains.

**Important limitation:** This is **AI filtering of trades across 25 already-approved candidates**, not AI dynamically adding/removing coins from the universe. Official FreqAI documentation warns against changing membership with a dynamic VolumePairList because new pairs lack preloaded model-training history. See https://www.freqtrade.io/en/stable/freqai/. A periodic predeployment candidate-universe review may be added after M1–M3, with cached data, full retraining and no unreviewed pair churn.

**Another limitation:** Standard Freqtrade fills eligible entries under its normal pair iteration. A 1-position cap alone does not ensure the **highest-ranked predicted return across all 25 pairs** is chosen when signals arrive simultaneously. Explicit global scoring/selection remains a separate tested feature, not an existing capability. We should not build it before getting a real baseline.

## Will paper research and future execution share learning?

**Goal: yes; implemented today: no.** Today the single dry-run and 20-slot research modes have **independent FreqAI identifiers and databases**, both enabled to retrain their own LightGBM **per-pair models**. Paper performance results are *evaluation feedback*, not direct model training data; FreqAI primarily retrains from matured candle-return labels.

A future approved design may use one research **training leader** and a separate execution **model consumer**, loading the exact same *approved* model versions, features, BTC context and symbol universe, while retaining independent trade ledgers and risk limits. This avoids splitting knowledge and duplicated model training, but must first pass official-image compatibility, data/feature parity, model-version pinning, no-unsafe-auto-promotion, and model-stale fallback tests. FreqAI defaults to using its latest trained models, so paper retraining must NOT silently switch a future real-money bot to an unapproved model. We will implement shared-model consumption only after historical/forward validation, under roadmap M6/M7.

**No real Binance trades or automatic real-money promotion are authorized by this change.**

## Onboarding a new coin: history bootstrap (implemented helper)

**No 30-day waiting period.** FreqAI trains from **already-existing Binance market candles**, using a rolling 30-day training window (train_period_days=30). Retraining can be requested again after its configured 24-hour interval. A coin does **not** need 30 days of NBOT monitoring or any previous Freqtrade trade.

V6 now includes a small, opt-in preparation tool: [scripts/bootstrap_history.py](scripts/bootstrap_history.py). It asks Freqtrade to fetch **60 days of 5m and 1h historical data**, plus BTC context, for at most **10 candidates per review**; with no extra local database or custom download engine.

Start by printing the proposed commands (NO Docker run, NO market changes):

~~~bash
python scripts/bootstrap_history.py --pair NEAR --pair INJ
~~~

Only on an isolated, properly provisioned development host, explicitly request download and a report of the actual stored history ranges:

~~~bash
python scripts/bootstrap_history.py --pair NEAR --pair INJ --execute
~~~

Official Freqtrade handles public Binance history, downloaded candle files and standard futures mark/funding candles. The helper then invokes Freqtrade list-data with a timerange display and logs a local **DOWNLOADED_UNVERIFIED** record under ignored user_data/bootstrap_records/.

**This does not prove model readiness.** At activation time we must check the *actual* history ranges, missing candles, BTC coverage, trading age, liquidity/spread and funding, train the new per-coin LightGBM model, evaluate it and obtain valid predictions. It makes **no automatic updates** to the running 25-coin watchlist and **never** places real orders or starts paper trading. The full proposed eight-hour Universe Selector (M5A) is still a roadmap design requiring its own tests and safety gate.

See [M5A in ROADMAP.md](ROADMAP.md) for the current precise development status and remaining work.

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
