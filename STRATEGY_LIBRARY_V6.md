# NBOT V6 — Expanded open-indicator strategy library and AI/RL research

**Owner-approved 2026-10-17. Source-only GitHub work on \`prototype/v6-freqtrade-freqai-20261016\`. No VPS historical jobs started, restarted, stopped or modified for this new feature. No paper/live trading permitted. All implementations are RESEARCH CANDIDATES, not independently proven winners.**

## Scope and open-source provenance

Review [Freqtrade's public strategy examples](https://github.com/freqtrade/freqtrade-strategies) and official [strategy customization](https://www.freqtrade.io/en/stable/strategy-customization/), [Hyperopt](https://docs.freqtrade.io/en/stable/hyperopt/), [native protections](https://www.freqtrade.io/en/stable/plugins/) and [FreqAI RL](https://www.freqtrade.io/en/stable/freqai-reinforcement-learning/) documentation. The community strategy repo is **GPL-3.0**. To avoid copying unreviewed GPL strategy source, hyperoptimized settings, outdated interface code or unvalidated backtest outcomes into this private project, NBOT's candidate indicators were implemented **independently in pandas/numpy** from standard public technical-analysis definitions. This is NOT a claim of guaranteed profitability or that any third-party "winning strategy" was licensed/imported.

Existing original V6 **breakout/pullback** AI research remains unchanged. The new code provides **eight named and independently testable candidate families**:

| Family | Long/short 5m idea | High-level distinct hypothesis | Status |
|---|---|---|---|
| EMA crossover | EMA20/EMA50 trend change with EMA100 filter | Trend follow after slope transition | coded; native test pending |
| Donchian breakout | Close beyond prior 20-bar high/low with EMA trend | Momentum through range boundary | coded; native test pending |
| Bollinger reversion | Price recovers inside 20-bar standard-deviation band | Mean reversion after extreme | coded; native test pending |
| RSI reversion | RSI14 crosses recovery threshold in opposite long-term trend | Oversold/overbought reversal | coded; native test pending |
| MACD momentum | MACD12/26 crosses signal9 while EMA trend agrees | Momentum acceleration | coded; native test pending |
| Stochastic reversal | %K crosses smoothed %D from 20/80 zone | Short oscillation reversal | coded; native test pending |
| ATR breakout | Price crosses lagged midband ± ATR multiple | Volatility-expanded trend breakout | coded; native test pending |
| Volume-confirmed trend | Prior 20-bar breakout with 24-bar volume surge | Liquidity-confirmed momentum | coded; native test pending |

**Implementation:** [native Freqtrade candidate classes](user_data/strategies/NbotV6LibraryResearch.py), [independent per-family FreqAI LightGBM research variants](user_data/strategies/NbotV6LibraryLightGBMResearch.py). Native eight standalone classes share a frozen, explicit 5m signal interface, 2% stop, 5% ROI target, at most 60m holding and one 1x $1000 *simulated* global portfolio position. Signals use current *completed* 5m candle and past bars; next-open fills and funding must be modeled by native Freqtrade. Hyperopt may change only predefined entry thresholds on a tuning period, not strategy family definitions or holdout intervals. **ROI/stop/fee values are not optimized/promoted here.**

## Owner-requested capabilities — concrete implementations and boundaries

| Requested capability | Implementation in V6 | Operational caveat |
|---|---|---|
| Automatically retrain on new data | FreqAI native \`live_retrain_hours=24\`, rolling \`train_period_days\` and \`backtest_period_days\` in [base](user_data/config.json) and isolated research overlays | *Configured but not deployed* as a live/dry trading service; current historical jobs already train chronologically |
| Predict with LightGBM | Eight opt-in independent \`NbotV6*LightGBMResearch\` classes + existing breakout/pullback; one isolated FreqAI model identifier per family; native \`NbotV6PurgedLightGBMRegressor\` with 12×5m label embargo | Target uses a conservative 60m trade outcome **proxy**; not actual tradable bid/ask fills. Not yet native-tested per new family |
| Compare multiple strategies | Eight standalone native Freqtrade strategy classes; [single-job plan runner](scripts/m2r_v6_library_native_job.py) generates isolated full-engine 25-coin portfolio backtests, per family/time block | No native new-family portfolio outcomes or OOS results executed yet |
| Hyperopt optimization | Native Freqtrade \`IntParameter\` and \`DecimalParameter\` in \`buy\` space; runner uses native Optuna/Hyperopt with \`MultiMetricHyperOptLoss\`, randomized search seed fixed, only **May–June tuning window**, no automatic parameter export | Optimized settings cannot be promoted automatically; independent July/Aug/Sep tests and native lookahead required |
| Loss and drawdown stops | Native Freqtrade \`CooldownPeriod\`, \`StoplossGuard\`, \`MaxDrawdown(calculation_mode=equity)\` properties, with \`--enable-protections\` in native backtest/Hyperopt plans | Requires native tests; no protection bypass on paper/live because these candidates refuse those modes entirely |
| NO TRADE on unfavorable opportunities | Every signal family requires present/causal data; explicit empty signal defaults, neither side on conflicting directions. Selector also fails closed on missing evidence, high volatility, weak cost-stressed returns or overdraw | Regime candidate routing is research only; no real trading or paper activation |
| Learn actions via reinforcement learning | Isolated [PPO five-action FreqAI model](user_data/freqaimodels/NbotV6CostAwareRLResearch.py) and [RL strategy](user_data/strategies/NbotV6RLResearch.py): neutral, long enter/exit and short enter/exit. Cost, stop-risk and duration penalties; holding neutral not penalized | FreqAI's RL training environment does **not** reproduce Freqtrade order fills/stoploss logic. Needs train, out-of-sample full-engine backtests, and comparisons with LightGBM; not assumed better |
| Best validated strategy per market regime | Strict [8h native-evidence-based selector](scripts/m2r_strategy_library_selector.py), and [research-only native Freqtrade adapter](user_data/strategies/NbotV6AdaptiveLibraryResearch.py). Uses a causal 5m EMA/ATR trend/range/high-vol classifier, requires two non-overlapping native test blocks *ending before* selection timestamp, positive extra-cost-stressed PnL, 20+ trades/block, max 5% drawdown and verified audit hashes and no-lookahead evidence | **No candidate currently has verified qualifying evidence**, so the checked-in [scorecard manifest](user_data/v6_library_scorecards.offline.json) has an empty \`blocks\` list and real adapter emits **NO TRADE**. No automatic model selection in original V6; native candidate ML models are not yet wired to parallel production inference |

## Exact next scientific sequence (do not skip)

1. **Preserve the active VPS Jan–Sep 30/60/90/180 experiment** unchanged. Never launch new strategy training or Hyperopt while Docker is busy, and do not change V5, main, existing trained models or PR status.
2. **Run official Freqtrade strategy discovery and full CI** for all 18 new native strategy classes, causal unit tests, config no-key guards, and RL imports. Fix any errors before making economic claims.
3. **Frozen candidate shortlist**: First 8 independent native Freqtrade strategy backtests with official engine, 25 identical USDT-M contracts and **matching test dates**, 0.05%/side historical fee, native historical funding, one 1x $1000 position, native protections enabled. Compare **NO TRADE=0**, the existing non-AI and original AI baselines. Do not infer performance from count of signals or synthetic labels.
4. **Train/Hyperopt only in May–June 2026**, save frozen parameters with data hashes; never Hyperopt on July/August/September evaluation sets. July = first validation; August/September = **already-inspected replication**, not a pristine final holdout. Require truly later never-inspected market regime before claiming an unbiased final advantage.
5. Repeat top native families using individually trained FreqAI LightGBM after-cost models. Add the RL PPO as **separate challenger**, not the default. Track accuracy, rejected opportunities, trade count, fees, funding, assumed +10/+15/+25bp extra round-trip cost, and missing executable historical bid/ask/stop fills.
6. Independently verify native Freqtrade lookahead-analysis, model split embargo, cost/funding audit, and at least **two non-overlapping chronological positive extra-cost-stressed blocks in the same regime** with enough trades. Only then produce candidate scorecards referencing actual native ZIP/data SHA256. Scorecards consumed at strict 8h as-of selection times must not contain evidence from the future, must be updated with point-in-time available data, and must not be shared across unrelated model families.
7. Run adaptive router **in offline historical replay** against per-regime frozen qualified candidates and NO TRADE. Compare it to the best fixed qualified strategy, naive switching, and NO TRADE. An OOS improvement is not established until this is done. New RL and ML action models require a separate independently checked native adapter; current selector routes eight **non-ML** native setups only.
8. **Only after independent proof and owner review** consider paper-research deployment (M4); it is NOT authorized now. Live money (M7) remains owner-locked.

## How to preview native research plans WITHOUT starting VPS jobs

From the V6 repository checkout (any computer with Python3):

\`\`\`bash
python3 scripts/m2r_v6_library_native_job.py plan native ema_cross validation_july
python3 scripts/m2r_v6_library_native_job.py plan hyperopt ema_cross tuning_may_june
python3 scripts/m2r_v6_library_native_job.py plan lgbm ema_cross validation_july
python3 scripts/m2r_v6_library_native_job.py plan rl ema_cross validation_july
python3 scripts/m2r_v6_library_native_job.py plan adaptive ema_cross validation_july
\`\`\`

\`plan\` is read-only. The optional **ONE-job-at-a-time** \`execute\` mode is deliberately gated by owner environment variable \`NBOT_V6_LIBRARY_OFFLINE_EXECUTION=OWNER_AUTHORIZED_OFFLINE_RESEARCH_ONLY\`, root on V6-only VPS, clean authorized research branch, **NO other Docker containers**, existing verified offline history, and no-key research config. This assistant did **NOT** invoke execute or access the busy VPS for this new library work. No background automation was created. Backtesting is not proof that new models improve performance; auditing still required.

**New files are isolated from the existing V6 active trading config. No original NbotV6 strategy, live/owner approval hook, M2R full Jan–Sep configs or active VPS research scripts were changed. M2 NO-GO; M4 PAPER OFF; M7 LIVE LOCKED; keep PR #50 DRAFT.**
