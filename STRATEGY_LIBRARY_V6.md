# NBOT V6 — Expanded open-indicator strategy library and AI/RL research

> **2026-10-19 03:45 UTC VERIFIED FINAL: ALL THREE QUEUED RESEARCH STAGES COMPLETE (NO TRADING APPROVED).** Original strategy library **63/63**; profit protection **120/120 official native ZIPs, zero failures** (separate optional loss-path diagnostic still flagged failed); global AI 25×8 **12/12 complete, 0 job failures**, 4 reused LightGBM model windows and 8 native official portfolio backtests. The initial Stage3 stop was a **research-only Freqtrade guard mismatch**, NOT data loss or P&L; isolated native diagnostic succeeded, guard remained fail-closed (named check failures/no credentials), one-time [strict hash-preserving recovery](scripts/m2r_v6_global_native_recovery.py) verified original ML source unchanged and archived original error, resumed only 8 native jobs. [Final **Stage3 economic and recovery evidence**](evidence/m2r/2026-10-19-global-25x8-native-recovery-final-report.md) + [read-only independent ZIP and forecast SHA256 verifier](scripts/m2r_v6_global_final_audit.py). Global shared dataset contained **914,878** candidate rows; each lookback scored **263,937** valid signals on common 2026-07-15–09-30 and selected **ZERO trades** due to frozen calibrated probability, cost, downside, regime and conservative expected edge policies. ALL 8 native portfolios executed **ZERO trades, P&L 0**, and were independently SHA256 audited. This establishes NO TRADE under those conservative gates, **NOT profitable AI selection/learning**. Original forecast source commit `8c458c8f...` preserved; resumed native commit `1a17ab62...`; original failed status, logs, forecasts, archives and risk thresholds all preserved. Services now stopped successfully, Docker idle. Owner to evaluate pre-specified challenger ablations on untouched future dates; **do not loosen gates based on seen historical results, promote a strategy, enable paper/live, merge PR50, or overwrite any prior output without separate approval**. First-stage results report: [63-job final study](evidence/m2r/2026-10-19-stage1-final-research-report.md).


> **2026-10-18 global integration implemented, NOT validated economically:** [Global 25×8 queue evidence](evidence/m2r/2026-10-18-global-eight-strategy-implementation-vps-queue.md). Our eight frozen family signals now have a separate historical LightGBM candidate generator, global simultaneous timestamp ranker and native portfolio strategy adapter; a third finite study is enabled on VPS and WAITING behind the library + profit-protection batches. Original strategy families and existing native trade archives are preserved. This does **not** authorize trading or make all models validated; full native selected-portfolio results are still pending.


> **Next integration design (owner approved 2026-10-18):** [Global 25×8 opportunity competition](V6_GLOBAL_OPPORTUNITY_SELECTION_DESIGN.md). Keep all eight independent families as separate candidates evaluated for all 25 pairs at each eligible completed 5m decision candle; rank calibrated after-cost opportunity forecasts globally, not merely the best single family or 8h regime. FreqAI multi-family inference and one-slot native Freqtrade replay **remain to be built**. Original breakout/pullback are optional separate controls/challengers. No source deployment, new VPS job, promotion, paper/live authorization or result deletion is implied.

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

## Engineering verification and critical image dependency

- **One-off official strategy discovery:** Eight independent native Freqtrade candidate classes + eight supervised LightGBM variants + one offline adaptive candidate + one offline RL candidate = **18 new Freqtrade strategy classes**. They must all show `OK` in official `freqtradeorg/freqtrade:stable_freqai list-strategies` on every relevant CI run.
- **RL uses a different official Docker image:** `freqtradeorg/freqtrade:stable_freqairl`, NOT `:stable_freqai`. The standard FreqAI image omits PyTorch; first new RL-model import test correctly found `ModuleNotFoundError: No module named 'torch'`, leading to the dedicated RL image fix. Native historical LightGBM stays on the smaller `:stable_freqai`. The RL image is multi-gigabyte and its own FreqAI internal rewards do not prove actual native fills or profitable policy.
- **Native portfolio protections apply to every new candidate class**, including the eight LightGBM variants, PPO RL and adaptive selector. The one-job research plan runner includes `--enable-protections` for each native backtest and Hyperopt. This is **not** a live or paper trading permission.
- **The regime selector is time-safe and computationally bounded:** unique as-of 8h regime selections are cached then mapped to candles in roughly linear time. The empty verified scorecard file intentionally means **NO TRADE across all 25 coins**. An externally supplied non-empty scorecard is *not accepted* unless each evidence block has matching audited archive hashes, model-training time before evaluation, causal/lookahead gate, minimum 20 actual native trades, nonoverlapping historical dates, positive after-additional-cost PnL, <=5% max drawdown, and at least two completed blocks per regime. Those assertions validate a scorecard contract, not the truthfulness of an unaudited external source; end-to-end provenance and full native strategy tests remain future gates.

## Exact next scientific sequence (do not skip)

1. **Preserve the active VPS Jan–Sep 30/60/90/180 experiment** unchanged. Never launch new strategy training or Hyperopt while Docker is busy, and do not change V5, main, existing trained models or PR status.
2. **Run official Freqtrade strategy discovery and full CI** for all 18 new native strategy classes, causal unit tests, config no-key guards, and RL imports. Fix any errors before making economic claims.
3. **Frozen candidate shortlist**: First 8 independent native Freqtrade strategy backtests with official engine, 25 identical USDT-M contracts and **matching test dates**, 0.05%/side historical fee, native historical funding, one 1x $1000 position, native protections enabled. Compare **NO TRADE=0**, the existing non-AI and original AI baselines. Do not infer performance from count of signals or synthetic labels.
4. **Train/Hyperopt only in May–June 2026**, save frozen parameters with data hashes; never Hyperopt on July/August/September evaluation sets. July = first validation; August/September = **already-inspected replication**, not a pristine final holdout. Require truly later never-inspected market regime before claiming an unbiased final advantage.
5. Repeat top native families using individually trained FreqAI LightGBM after-cost models. Add the RL PPO as **separate challenger**, not the default. Track accuracy, rejected opportunities, trade count, fees, funding, assumed +10/+15/+25bp extra round-trip cost, and missing executable historical bid/ask/stop fills.
6. Independently verify native Freqtrade lookahead-analysis, model split embargo, cost/funding audit, and at least **two non-overlapping chronological positive extra-cost-stressed blocks in the same regime** with enough trades. Only then produce candidate scorecards referencing actual native ZIP/data SHA256. Scorecards consumed at strict 8h as-of selection times must not contain evidence from the future, must be updated with point-in-time available data, and must not be shared across unrelated model families.
7. Run adaptive router **in offline historical replay** against per-regime frozen qualified candidates and NO TRADE. Compare it to the best fixed qualified strategy, naive switching, and NO TRADE. An OOS improvement is not established until this is done. New RL and ML action models require a separate independently checked native adapter; current selector routes eight **non-ML** native setups only.
8. **Only after independent proof and owner review** consider paper-research deployment (M4); it is NOT authorized now. Live money (M7) remains owner-locked.

## Native trade/evidence extraction (not a shortcut to promotion)

Once a historical native backtest completes in its own isolated results directory, use [the actual native trade scorecard extractor](scripts/m2r_v6_library_scorecards.py) to inspect cost-stressed outcomes **by the market regime at trade-entry decision time**. The extractor reads the Freqtrade ZIP itself, requires 25 pairs, exact 1× $1000 native fills, the 0.05%/side native fee, compares saved trade PnL to Freqtrade portfolio totals, and reads the exact public archived 5m candles for each pair. For each entry, it classifies regime from the **last completed 5m candle before the native entry open**, not from the eventual exit or a full-window hindsight label. It computes at least +25bp additional hypothetical round-trip execution stress, independent by-regime trade PnL, conservative per-regime closed-trade drawdown, and SHA256 fingerprints of each source ZIP and the original market dataset.

Example command **only after** the native family test has actually finished and while no competing Freqtrade training is running:

```bash
python3 scripts/m2r_v6_library_scorecards.py \
  --zip /root/nbot-v6-m1-20261016/library-20261017/native/ema_cross/validation_july/backtest_results/ACTUAL_NATIVE_ZIP.zip \
  --family ema_cross \
  --history /root/nbot-v6-m1-20261016/january-2026-public-history-stage/futures \
  --training-ended 2026-06-30T23:55:00Z \
  --extra-cost-bps 25 \
  --output /root/nbot-v6-m1-20261016/library-20261017/native/ema_cross/validation_july/scorecards-review-only.json
```

Replace `ACTUAL_NATIVE_ZIP.zip` with the file's *real* filename. The scorecard extractor **deliberately sets `decision_boundary_passed=false` and `scorecard_selector_ready=false`**. Passing the trade arithmetic audit is **not** the same as independently clearing Freqtrade's native lookahead analysis, all FreqAI model/target embargo checks, or certifying actual executable bid/ask/stop-market fills. It cannot populate the positive/approved adaptive-selector manifest by itself. Explicit independent lookahead/cost review, separate qualified windows and a point-in-time evidence ledger are necessary before any candidate selection. This prevents self-validation or gaming the untouched test set.

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
