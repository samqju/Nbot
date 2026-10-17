# NBOT V6 — Clean Freqtrade + FreqAI Bot

**Status:** Research prototype; the **M1 technical integration test PASSED**: real Binance history, **25/25 trained 30-day LightGBM models**, and an official **seven-day historical backtest with 34 trades and -135.64 simulated USDT P&L**. **No positive trading edge is proven, no persistent paper bot is commissioned and no real orders are authorized.**

NBOT V6 is an isolated Freqtrade strategy powered by FreqAI's LightGBM regression model. We use Freqtrade for exchange data, trade execution, risk/accounting, historical backtesting and dry-run. We use FreqAI for features, retraining and prediction. NBOT's custom code only describes market features and trading decisions.

## New M2R research source — after-cost learning, no trading approval (October 17, 2026)

The owner approved **research-code development** for three capabilities: learn from *hypothetical completed trades*, estimate success **after fees/estimated slippage/funding**, and eventually route among *frozen* breakout/pullback strategies or **NO TRADE**. The complete staged and checked plan is in [ROADMAP.md](ROADMAP.md), with implementation details and limitations in [M2R_RESEARCH.md](M2R_RESEARCH.md).

- **Implemented, test only:** Four causal breakout/pullback LONG/SHORT candidate labels with next-open entry, conservative stop-first outcomes and a 0.21% **assumed** roundtrip cost reserve, including setups the old one-slot bot skipped. In September's 25-coin historical sample there were **29,033 overlapping hypothetical training opportunities**; only **32.332%** were positive *under these assumptions*. These are **not executed trades** or wallet profit.
- **Implemented, historical-only:** Independent [NbotV6TradeOutcomeResearch](user_data/strategies/NbotV6TradeOutcomeResearch.py) FreqAI LightGBM Challenger with a unique [locked model/config](user_data/config.m2r-trade-outcome.json); original V6 and no-ML strategies are unchanged. Real BTC-only Oct 1–8 Freqtrade smoke ran, **one virtual loss −1.104 USDT**, 60-minute holding time. Not a statistical/economic evaluation.
- **Implemented, offline only:** A deterministic [NO TRADE / regime-aware candidate selector](user_data/strategies/nbot_strategy_router.py) and [purged chronological label-split test utility](scripts/m2r_purged_split.py). There are **no approved candidate-specific forecasts driving an active router**, no model auto-promotion and no continuous paper bot.

**M2 quality gate still NO-GO:** The original official AI lookahead warning, historical real spread/stop-fill uncertainties and separate prospective fill measurement are unresolved. The actual FreqAI rolling-label split must also be independently inspected. **M3 not commissioned; M4's 20-simultaneous-virtual-trade mode and M5A's 8-hour 25-coin universe selector remain separate, unstarted operating milestones; M7 live money remains locked.** No V5 servers, model promotions or real exchange orders are touched.

## VPS installation and operating guide

**New to Linux or Freqtrade? Start with [VPS_SETUP.md](VPS_SETUP.md).** It has the complete step-by-step Ubuntu/PuTTY setup, short copy/paste commands, historical M1 training test, optional future paper research, logs, backup and troubleshooting instructions.

- **[DEPENDENCIES.md](DEPENDENCIES.md)** — exact hardware tiers, RAM/CPU/disk and networking requirements, Docker/FreqAI/Python dependencies, and tested vs estimated capacity.
- **[scripts/install_docker_ubuntu.sh](scripts/install_docker_ubuntu.sh)** — guarded official-Docker installer for a fresh Ubuntu VPS only. **Not** for the existing V5 servers.
- **[scripts/check_vps.sh](scripts/check_vps.sh)** — read-only RAM, disk, Docker/Compose and Binance API preflight.
- **[LIVE_SAFETY.md](LIVE_SAFETY.md)** — future owner/Telegram/Binance protections; real trading **still locked**.

**Status:** The full **25-coin M1 historical fit and replay has passed technically** on an isolated 8-GB VPS, but returned **losses**, not profitability. The VPS remains a research-only host; **M2/M3 economic and multi-period testing**, **M4 persistent forward-paper commissioning**, and **M7 any real-money trading** are not accepted. Do not start a continuous trading service until the appropriate release gate.

## Minimal source tree

~~~text
README.md
ROADMAP.md
docker-compose.yml
DEPENDENCIES.md
VPS_SETUP.md
scripts/check_vps.sh
scripts/install_docker_ubuntu.sh
scripts/bootstrap_history.py
scripts/owner_live_approval.py
LIVE_SAFETY.md
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

**Two distinct choices:** (1) which coins are eligible for model training, and (2) whether to open a trade on a particular coin. The V6 starter now includes a **fixed, versioned set of 25 Binance USDT-M candidate pairs**: BTC, ETH, SOL, BNB, XRP, ADA, LINK, DOGE, AVAX, DOT, LTC, BCH, NEAR, UNI, APT, ARB, OP, SUI, TRX, ETC, ATOM, FIL, INJ, XLM, HBAR. All 25 have passed real Binance contract and M1 historical-candle checks; **minimum order sizes, liquidity, spreads, execution capacity and trade economics** require additional M2/M3/M4 validation before continuous paper or real-money deployment.

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

## Future owner-only live execution (CODE STAGED, REAL TRADING LOCKED)

Live execution is *not enabled* by any committed config. We added a non-autostart, private-config-only Compose profile and a strategy owner gate that checks the owner's **single private Telegram ID**, an independent **owner-created VPS approval file** (valid up to 24 hours), one-position/1x/1,000-USDT risk caps and exchange-side stop-market settings before live entry. Telegram can report, pause and resume an already approved Freqtrade process, **but can never arm real-money access on its own**. A missing/expired/revoked approval rejects new entries without intentionally disabling the handling of existing exits.

There is no real Binance account secret, owner ID, Telegram token or approval file checked into Git, and no live process has started. FreqAI's approved-model release process and real exchange safety checks remain **M6/M7 tasks**, so this source hook must not be treated as operational approval. See [LIVE_SAFETY.md](LIVE_SAFETY.md) and [ROADMAP.md](ROADMAP.md).

## M1 status — October 16, 2026 (TECHNICAL INTEGRATION PASSED; NEGATIVE BACKTEST)

- **Exchange and history:** On the owner-authorized new **8 GB / 2-vCPU** VPS, official Freqtrade 2026.9 downloaded **60 days** of real Binance USDT-M futures history for **all 25 candidates**, including 5m, 1h, mark and funding records. Independent [candle coverage/continuity audit](evidence/m1/2026-10-16-8gb-vps-full25-candle-audit.json) passed **25/25**.
- **Training:** The original **30-day training window, 5m/1h feature set and LightGBM** model trained successfully for **25/25 coins**, with distinct M1 model ID in [user_data/config.m1-all25.json](user_data/config.m1-all25.json). The official process exited **0** with no ERROR lines.
- **Backtest:** Seven completed days, **October 1–8, 2026**, max one global virtual position, 100,000 simulated USDT wallet and 1,000 USDT stake: **34 trades, 9 wins/25 losses, 26.5% win rate, -135.640 USDT P&L, 165.156 USDT drawdown**. Profit factor **0.49**. The first BTC+ETH smoke returned -1.720 simulated USDT over 4 trades.
- **Interpretation:** **M1 technical gate passed; economic validity has NOT passed.** Freqtrade's estimated fees do not replace realistic, independently checked spread/slippage/funding assumptions, multiple market periods or a non-ML baseline. **M2** after-cost benchmark and **M3** multi-period validation come next.
- **Operations:** All tests used temporary Docker containers and public market data; **no real exchange credentials, live orders, Telegram, V5 modifications or persistent paper service**. Docker is installed on the new VPS, and no Freqtrade container was left running.

Detailed evidence, reproducible commands and prior low-memory context: **[M1_EVIDENCE.md](M1_EVIDENCE.md)**, [ROADMAP.md](ROADMAP.md) and [VPS_SETUP.md](VPS_SETUP.md). **Do not equate a successful backtest with permission to place real orders.**

## M2 status — October 17, 2026 (RESEARCH ASSESSMENT COMPLETED: **NO-GO**)

**NEW — Full September 1–30 study:** [Full-month results and method](evidence/m2/2026-10-17-september-full-month-analysis.md) using **25 pairs and 125 separate historical LightGBM model fits**, trained from August/earlier data with five 7-day steps. At 0.05% per-side fees, **AI lost 444.980 USDT (137 trades)**, **non-AI lost 242.894 USDT (163 trades)**, and **NO TRADE remained 0 USDT**. At double the fee AI lost **576.688 USDT**, and non-AI lost **388.318 USDT**. The no-ML strategy was in a position for **99.641% of September**. [Audited machine evidence](evidence/m2/2026-10-17-september-30day-comparison.json).

**Conclusion:** A profitable-looking first October week did not survive a full September test. **Neither fixed-universe strategy is profitable in September. M2 release still NO-GO; no M3, unattended 20-slot paper or live orders.** The owner-requested future universe selector is still separate/unbuilt and its benefits are not assumed.



The all-25-pair seven-day Freqtrade M2 comparison is fully documented in [M2_EVIDENCE.md](M2_EVIDENCE.md). At the official base historical 0.05%-per-side fee: **no-ML +169.849 simulated USDT (31 trades)**; **FreqAI −135.640 simulated USDT (34 trades)**; **NO TRADE 0 USDT**. That is **one historical week only**, not proven profitability.

**New risk and execution findings:**

- Historical Binance public funding settlements were independently matched to all **65** original trades: all within five cents ([funding evidence](evidence/m2/2026-10-17-public-binance-funding-reconciliation.json)).
- Real archived **30-second market depth** was checked at 130 simulated entries/exits, with **113 fresh matches, 17 unverified/stale**. Matched visible liquidity inside 0.2% was at least **40×** the $1k order size, but the October 2026 public best-bid/ask archive is unavailable, and depth alone **cannot prove an actual fill price**. [Historical liquidity evidence](evidence/m2/2026-10-17-historical-depth-trade-time-audit.json).
- A **severe hypothetical extra-cost scenario** (20 bps per matched trade side and 100 bps per stale/unverified side) turned the non-ML baseline **negative at −24.784 USDT**; AI became **−335.160 USDT**. These are *stress assumptions* and unchanged trades, not observed transaction costs. [Scenarios](evidence/m2/2026-10-17-snapshot-quality-cost-stress.json).
- A real [AI decision audit](evidence/m2/2026-10-17-original-model-decision-gates.json) counted **50,400** market-candle decisions, **6,837** technical setups, **28** blocked by unusable AI predictions, **6,661** removed by model direction/return threshold, and **148** potential AI setup signals before portfolio constraints; 34 positions were opened.
- The simple strategy had its single allowed position open **99.802%** of that week; the AI strategy was exposed only **46.776%**. [Risk-time evidence](evidence/m2/2026-10-17-original-risk-exposure.json). Their profits therefore carry quite different market risk.
- **BTC and ETH controlled forecasts were invariant** under both single-pair/full-universe context ([evidence](evidence/m2/2026-10-17-prediction-invariance-btc-eth.json)) and deliberately omitting five later days ([evidence](evidence/m2/2026-10-17-asof-future-truncation-predictions.json)). **However**, official FreqAI lookahead-analysis on eight signals still returned `has_bias=Yes` with changing model/entry/exit indicator columns. We will **not** label all 25 AI signals leak-free until that is explained.

**Final M2 research decision: NO-GO.** The assessment has been carried out and published, but **M2's release/quality acceptance FAILED** because exact historical fills, fee tiers and stop slippage cannot be proven from these archives, and the AI diagnostic warning remains unresolved. **Do not advance M3, start unattended M4 paper trading, enable M5A live universe rotation or unlock M7 real trading.**

The planned **up-to-20-position virtual paper mode** remains an unstarted and independent future research profile; the **8-hour 25-candidate intelligent selector** is also a separate unbuilt milestone. See the honest checked/unchecked [roadmap](ROADMAP.md) and [draft PR #50](https://github.com/samqju/Nbot/pull/50).

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

Do not assume this historical run will pass without adapting to an exact pinned Freqtrade version. These **Docker** commands have **not** been executed on either existing VPS. Actual **native Freqtrade** market download and reduced one-pair FreqAI backtesting were successfully executed in Observation's isolated V6 research folder as documented above.

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
