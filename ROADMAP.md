# NBOT V6 — Development and Release Roadmap

**Roadmap version 1.1, October 17 2026**  
**Project:** Small Binance USDT-M trading bot using Freqtrade + FreqAI.  
**Release state:** Prototype. M0 and M1 technical integration are complete, but the 25-pair FreqAI test lost money. M2 benchmark/fee-stress has begun; realistic costs, M3 validation and paper/live release have NOT been accepted.  
**This document controls V6 scope.** Legacy V5 documentation is historical, not an active V6 specification.

## A. What we are building

NBOT should observe approximately 50 liquid coins eventually, including Bitcoin context; recognize directional setups; learn whether opportunities might deliver positive after-cost performance; select LONG, SHORT or NO TRADE; and—if future live trading is separately approved—hold no more than ONE actual position in total. Improve trade selection, not trading frequency.

Current **configured candidate scope: 25 fixed futures markets** (all 25 passed M1 contract/candle validation; M2/M3 liquidity/market-impact/economic acceptance remains outstanding) including BTC, completed 5m candles, correlated BTC 5m/1h information, one FreqAI LightGBM model, a few causal EMA/breakout/pullback rules, and one simulated portfolio. Expansion to 50 pairs is conditional, not a day-one requirement.

**Nothing in the roadmap guarantees profitability.** Evidence must establish whether there is any tradeable advantage.

## B. Component boundaries

| Responsibility | V6 owner | Do NOT rebuild |
|---|---|---|
| Exchange data and connection | Freqtrade | Custom Binance WebSocket network |
| Backtesting and trades | Freqtrade | Independent order/fill/accounting engine |
| Model training and rolling inference | FreqAI + LightGBM | G5/G6 ML factories or independent serving |
| Market regime, BTC context, simple setups | One NbotV6 strategy | G1–G4 distributed observation pipeline |
| Stop, sizing, one-position constraint | Freqtrade settings and simple strategy safeguards | G7 execution and custom portfolio service |
| Logs and performance | Standard Freqtrade artifacts plus brief experiments | Second research database and raw-tick archive |
| Deployment | One Docker Compose project | Two-VPS distributed control architecture |

No G1–G7 runtime dependencies. No V4/V5 SQLite data automatically imported. No microservices, message bus, additional databases or new ML frameworks absent measured necessity.

## B2. VPS deployment prerequisites and copy/paste setup (documented, NOT yet commissioned)

The source now includes **[DEPENDENCIES.md](DEPENDENCIES.md)** (hardware, Docker/FreqAI/Python dependency specifications, internet and security requirements), **[VPS_SETUP.md](VPS_SETUP.md)** (beginner's step-by-step Ubuntu/PuTTY commands, M1 history/backtest, future paper operation, logs, safe updates and troubleshooting), **[scripts/install_docker_ubuntu.sh](scripts/install_docker_ubuntu.sh)** (guarded official-Docker installer **only for fresh Ubuntu VPSs**) and **[scripts/check_vps.sh](scripts/check_vps.sh)** (read-only RAM/disk/dependency/Binance API preflight). The guides distinguish Docker image dependencies (bundled) from the historical low-memory native/Python experiment.

**Measured hardware evidence:** 1-GB/2-vCPU Observation VPS proved a 3-day BTC micro-model and failed a full 30-day model under a deliberately tight 440-MB scope. The new **8-GB/2-vCPU** private VPS successfully trained **all 25** normal 30-day LightGBM models and backtested a complete historical week using short-lived Docker runs limited to **6 GiB**. This is an *execution limit*, NOT measured peak RAM or evidence that 8 GB is the required minimum. Record actual resource peaks before choosing a future persistent paper-server size. No V5 services were touched.

**Release rule:** Publishing the full setup guide and passing M1 does **not** authorize starting a persistent bot, upgrading V5, automatically running the eight-hour selector, enabling Telegram real-money control, or placing Binance real orders. M2–M4 and later M5A/M6/M7 gates remain in force. Until a tested immutable Docker image digest is approved, the Compose image's `stable_freqai` tag is **mutable** and must not be treated as a production pin.

## C. Evidence vocabulary

- IMPLEMENTED = code exists and focused unit tests run.
- VERIFIED = official Freqtrade/FreqAI runtime and real historical/public data were successfully exercised, with exact commands and outputs.
- ACCEPTED = predeclared operating, safety and independent economic criteria are met.

Passing unit tests or strategy discovery is NOT a backtest, economic validation, healthy VPS or production release.

## M0 — Clean V6 source tree

**Goal:** A checked-out branch with only V6 files, tests, roadmap and one V6-specific CI workflow.

Work:
- Move the existing V6 strategy, config, Compose and focused tests to repository root.
- Remove every V5 source file, historical deployment script and old workflow from the V6 branch tree. Do not delete or rewrite the legacy main branch, release tags, VPS databases or backups.
- Update CI to run only V6 unit tests, Python/JSON checks and strategy discovery using the official FreqAI Docker image.
- Confirm no credentials and no implicit real-money order authority.

**Gate M0:** Verified root file manifest, V6 unit tests PASS and official framework import PASS. Historical ancestry may still contain V5; a separate new repository is required for a clean Git history rather than only a clean current checkout.

## M1 — Official framework end-to-end proof

**Goal:** Make a reproducible Freqtrade/FreqAI backtest work on isolated development hardware, independent of old VPS.

Work:
- Record Docker version, machine memory/CPU/disk, then pin the tested FreqAI Docker image by immutable digest.
- Validate exchange/pairs, official Freqtrade config, strategy loading and a completed LightGBM fit.
- Validate all 25 candidate perpetual markets and their Binance data quality. Then download sufficient 5m and 1h futures candles (M1 may smoke-test fewer markets first): at least the 30d training window, indicator warmup and the historical backtest period. Identify gaps; do not invent candles or forward-fill missing futures data without a scientific justification.
- Run documented official Freqtrade backtest with FreqAI and record exact Git SHA, timerange, image digest, logs, model and result artifacts.
- Explicitly test prediction abstention, one-position cap and long/short behavior.

**Gate M1:** Real backtest exits successfully, predictions are produced with no time/data-integrity errors, and failure/restart produces no hidden real trading behavior. Do NOT commission VPS yet.

### M1 execution record — October 16, 2026 (TECHNICAL GATE PASSED, economic quality FAILED)

- A new owner-authorized **8GB-Observation** VPS with 2 vCPU, 7.8 GiB reported RAM, Docker **29.9.1** and Compose **v5.6.0** passed Binance public **spot and futures HTTP 200** checks. The official Freqtrade **2026.9 FreqAI image** (digest in [M1_EVIDENCE.md](M1_EVIDENCE.md)) ran in a separate `/root/nbot-v6-m1-20261016/source` research folder with `--memory=6g --cpus=2`. These are Docker caps, not measured peak usage.
- Real Freqtrade public Binance download-data completed for **25/25 configured USDT-M pairs**, fetching a nominal **60 days** of 5m/1h futures prices, hourly mark prices and funding events (**100 source files**).
- The additional [full-data continuity/quality audit](evidence/m1/2026-10-16-8gb-vps-full25-candle-audit.json) verified **25/25 pairs**; no gap/duplicate/invalid OHLCV checks failed in 5m/1h futures and hourly mark data; funding observations were checked as irregular exchange events rather than forced into 1h candles.
- FreqAI successfully trained **25/25** separate LightGBM models using the intended **30-day** history (September 1–October 1), native full **5m/1h feature** configuration, then completed a seven-day **October 1–8** backtest. Official process exit code **0**, no ERROR lines, and no persistent Docker containers after completion.
- **Honest trade outcome:** **34** simulated closed trades, **9 winners/25 losers**, **26.5%** win rate, **-135.640 USDT simulated P&L**, **-0.14% account return**, **165.156 USDT max drawdown**, profit factor **0.49**. Long/short trades both occurred (**25/9**) and **68** entry signals were rejected. Earlier BTC+ETH smoke: 4 trades, -1.720 USDT.
- **Gate decision: M1 TECHNICAL INTEGRATION ACCEPTED.** The original official-framework/data/30-day-fit/seven-day-replay requirement is now evidenced. This is **NOT** evidence of profitable, cost-robust AI, and it does **NOT** authorize M4 forward-paper operation or M7 real trading.
- Full method, tested Docker image digest, reproducible commands, fee limitations, logs and checklist: [M1_EVIDENCE.md](M1_EVIDENCE.md). The earlier [1GB bounded micro-test](evidence/m1/2026-10-16-observation-vps-1gb-freqai-trial.md) and GitHub 451 errors remain historical context, not current blockers.
- **Immediate next task: M2.** Compare realistic after-cost trades to a fixed non-ML baseline and independent controls. Continue to M3 longer multi-period out-of-sample/walk-forward studies only with preserved historical as-of checks. A single losing seven-day run cannot establish a tradable advantage.

## M2 — Honest non-ML baseline and after-cost evaluation

**Goal:** Establish what basic trading signals achieve without assuming ML is helpful.

**Status: IN PROGRESS — evidence collected, release gate NOT PASSED.** Source results and exact limitations: [M2_EVIDENCE.md](M2_EVIDENCE.md); [machine-readable fee/cost/coin/side comparison](evidence/m2/2026-10-17-first-week-cost-sensitivity.json).

### M2 detailed checklist (tick only proven items)

- [x] **Frozen no-ML comparator**: the same EMA20/EMA50 trend, prior-20-candle breakout and pullback setups, independent no-FreqAI strategy [NbotV6NoML](user_data/strategies/NbotV6NoML.py); original AI strategy unchanged.
- [x] **NO TRADE baseline**: zero positions, zero trading P&L and exposure, no fees.
- [x] **Matching first-week official backtests:** all 25 USDT-M candidates, **2026-10-01 through 2026-10-08**, fixed 1× / one position / 1,000-USDT stake, 100,000 simulated wallet. **AI: 34 trades, -135.640 USDT; no-ML: 31 trades, +169.849 USDT** at 0.05% per side.
- [x] **Official fee sensitivity:** both strategies rerun using 0.10% per side; **AI: 34 trades, -169.555 USDT; no-ML: 30 trades, +138.554 USDT**. Fee choices may change the trade path.
- [x] **Additional hypothetical cost stress:** exported-trade **+10/+25/+50/+100 roundtrip bps** sensitivity, labeled as *fixed-fill illustrative deductions*, not measured actual fills. The positive non-ML result vanishes under the +100 bps stress.
- [x] **Trade-level coin, side, duration and funding-field audit:** reproducible [scripts/m2_evaluate.py](scripts/m2_evaluate.py) generates per-pair/per-side closed-trade summaries, fees, approximate exposure and hypothetical adjusted returns; official ZIP results remain private on the V6 research VPS.
- [x] **Non-ML signal lookahead screening:** official `lookahead-analysis` checked **30** baseline signals, with **0 detected** biased entries/exits (not proof of every possible signal).
- [ ] **Realistic historical spread, maker/taker fill probability, slippage/market impact, and adverse stop fills:** estimate from independently sourced timestamped exchange data or defensible conservative ranges, not cherry-picked present-day quotes. Re-evaluate all-pair net P&L.
- [x] **Historical funding-event reconciliation:** all **65** official trades (34 AI + 31 no-ML) cross-checked against public Binance USD-M settlement timestamps/rates/mark prices; aggregate AI −0.721885 vs −0.721893 USDT; baseline +0.367678 vs +0.367662 USDT; zero trades differ by more than five cents. [Per-trade evidence](evidence/m2/2026-10-17-public-binance-funding-reconciliation.json). Actual order type fee tiers/quality remain [ ] unverified.
- [ ] **AI lookahead/label isolation:** a separate historical-only, credential-free audit subclass passed the framework invocation without weakening the original strategy and tested **8 entry/exit signals**. Official result: `has_bias=Yes` (0 explicitly biased entry/exit *signals*, but changed `do_predict`, `DI_values`, `enter_long`, `exit_*` and label columns). Offline full-series-vs-prefix features and isolated 12-candle labels passed; **do not certify AI leakage-free until the changed prediction/decision columns are explained**. [Evidence](evidence/m2/2026-10-17-ai-lookahead-and-signals.md).
- [x] **Export and reconcile actual entered/rejected/exited signal rows** from full original-strategy Freqtrade reruns: AI **34/68/34**, no-ML **31/6,531/31**. Repeated rejected rows are not independent trades. [Evidence](evidence/m2/2026-10-17-ai-lookahead-and-signals.md).
- [ ] **Full raw decision eligibility, FreqAI `do_predict` abstention and slot-occupancy exposure accounting:** the official entered/rejected/exported rows alone do not distinguish model abstention from structural gating.
- [ ] **Additional independent market periods, statistical uncertainty and regime comparisons:** M3's explicit multi-window walk-forward acceptance; one losing AI week / one winning non-ML week prove neither strategy's dependable edge.

**First M2 finding:** The no-ML strategy beat FreqAI by **305.489 USDT** in this one week at the baseline simulated fee. This does **not** isolate the *causal* effect of AI because the compared strategies also differ in their exit rules, nor does it prove the simple approach is profitable. Do not tune features to fit this single period. The historical **M2 gate remains OPEN** until defensible execution costs and leakage controls are verified.

**Gate M2:** Complete reproducible metrics, defensible costs and no known decision leakage. A loss-making benchmark is a valid finding, not a reason to fabricate performance.

## M3 — FreqAI incremental value test

**Goal:** Demonstrate whether one LightGBM model meaningfully improves M2 after-cost decisions.

Work:
- Use small causal BTC/coin momentum, structure, relative-volume and volatility features. Do not automatically import 24 detectors.
- Train/evaluate with chronological walk-forward windows and untouched later intervals. Test multiple regimes; never shuffle time-series labels.
- Keep prediction target interpretation exact: 12-candle future close return is NOT actual after-cost trade PnL.
- Review prediction drift, stale/outlier rejection, retraining runtime, model identifier, cost sensitivity, uncertainty and trading frequency.
- Compare net and risk-adjusted outcomes to both non-ML and NO TRADE baselines, using predeclared criteria. Record failures. If results are weak, HOLD rather than deploy another model farm.

**Gate M3:** Credible out-of-sample, after-cost and risk results, or explicit rejection. Do not call any continuously retrained FreqAI model a validated Champion merely because it exists.

### Planned adaptive-learning hypothesis — NOT AUTHORIZED UNTIL M2 PASSES

The owner's hypothesis is sound enough to test **only after M2**: rather than let AI freely rewrite strategies, use a **small transparent library of frozen entry/exit candidates** (initial EMA trend/breakout/pullback plus later evidence-based alternatives) and train a lightweight **regime-conditioned accept/reject/router** that chooses a candidate or **NO TRADE**. Inputs may include causal BTC regime, liquidity, volatility, trend strength and observed relative costs. Define target as **after-cost realized opportunity outcome**, not merely the 12-candle forward close return; use holdouts, fees, funding and cost-stressed execution.

**Governance:** continuous model fitting may occur during **authorized research**, but automatic promotion must not happen. Any new model/selection policy is a **Challenger** until it beats both the non-ML baseline and NO TRADE in independent chronological walk-forward periods, has no unresolved leakage, meets risk/turnover limits, and a specific owner-approved release/rollback process is established. Underperformance chooses **NO TRADE / safe hold**, not model churn.

This remains **design only**: no meta-learner, dynamic strategy switching, model auto-promotion, universe selector daemon, or 20-position forward paper bot has been coded or commissioned for M3.

## M4 — Isolated VPS paper/dry-run reliability

**Goal:** Continuous operation of one Freqtrade dry-run bot without real orders.

Work:
- Evaluate available VPS CPU, RAM, swap and disk under FreqAI training. If the legacy VPS is too small, use isolated appropriately-sized hardware. Do not disrupt old protected operations.
- Install only the pinned V6 version. Keep dry_run true, blank credentials, no exposed API, no forced/manual-entry route, 1x leverage and global max_open_trades=1.
- Observe approximately 30 calendar days across changing market conditions, with no quota for trades. Record gaps, signals, abstentions, simulated fills, model retraining, PnL, resource pressure and any runtime errors.
- Test planned restart, stale-data and connectivity faults, idempotent trade recovery, loss of model availability and safe no-trade behavior.
- Retain basic config/result backups and daily visibility without a custom distributed evidence store.

**Gate M4:** Dated forward-paper report, controlled resource use, restart reliability and zero real exchange orders. Profitability still requires independent evidence, not just a healthy daemon.

### M4 research lane — Continuous independent paper feedback (added 2026-10-16)

This is a **sub-feature of M4**, not a new research architecture or permission to skip M1–M3. It is already implemented at source/config level but **not deployed, backtested or forward-paper accepted**.

- Run an additional, explicitly selected **Freqtrade dry-run process against Binance mainnet public market data**, using the SAME NbotV6 strategy/LightGBM family, but a distinct model identifier, SQLite file and config overlay.
- Permit up to **20 concurrent simulated paper positions by default** (also the absolute ceiling) via configuration and a strict dry-run startup guard. These are capacity limits, never trade quotas. With 25 configured candidates, at most 20 can be simultaneously paper-traded under normal Freqtrade one-trade-per-pair behavior.
- Keep single-position execution separate. Research should continue collecting candles and FreqAI retraining regardless of whether that separately configured bot has an open position. With two independently retraining FreqAI instances, measure cumulative CPU/RAM and schedule staggered updates if needed; do not assume a small VPS can run both.
- Paper trades from Freqtrade's dry-run database provide **forward operational and economic feedback** (with simulated fills/limits). FreqAI continues learning from candle features and future-price targets. **Paper PnL is NOT fed back into the LightGBM model automatically** and must never be presented as such.
- Review the first **10–20 completed simulated trades** for debugging assumptions, order lifecycle and measured costs; do not label 20 examples statistically sufficient for model promotion or live approval. Require a longer, multi-regime forward window and held-out, after-cost comparison in M2/M3/M4.
- No custom virtual-trade factory, separate exchange connector, new optimizer, duplicated historical database or automatic live model promotion. Prefer standard Freqtrade trade history and reports.
- **Fail-closed release controls:** dry_run=true required, exchange keys must be blank on researcher, 1x leverage, max 20 simulated slots, disabled remote API, separate DB/identifier and explicit process start. This V6 source has no real-order mode. M7 remains separately locked.

**M4 research-lane acceptance:** both config variants pass official Freqtrade import/schema checks, research startup accepts 20 (and no more than 20) simulated slots, unexpected live/order credentials are rejected, model/DB isolation is verified, and an isolated forward dry-run proves independent operation and no real orders. Source tests do not satisfy the forward gate.

## M5 — Controlled market and feature expansion

**Goal:** Expand only when justified.

Work:
- Validate the candidate 25; if training/market quality fails, reduce to 8–15 and expand in measured stages; later consider 25 -> up to roughly 50 coins; verify quote/candle quality, running memory, training time and trade-selection outcomes each time.
- Evaluate historical V4 24-pattern detectors as optional *indicators*, one at a time, only when causal tests and incremental out-of-sample improvements warrant a port.
- Continue to allow NO TRADE. Do not turn 24 pattern descriptions into 24 trading microservices.
- Use standard Freqtrade dashboard/Telegram features later if necessary; avoid inventing another control plane.

**Gate M5:** No integrity, resource, robustness or risk-adjusted net degradation relative to accepted M3/M4 baseline. Expansion can stop below 50.

### M5A — Eight-hour intelligent candidate rotation (selector NOT implemented; optional bootstrap helper coded)

#### New coin bootstrap: implemented in source, NOT an activated rotation system

**Agreement:** There is NO requirement to monitor a newly discovered coin for 30 days before FreqAI can train it. Standard Freqtrade can download already-existing Binance USDT-M market history. The current FreqAI setting **train_period_days=30** means **each training run consumes a sliding 30-day history**, not that the bot must run for 30 days. Configured **live_retrain_hours=24** is the minimum retrain spacing, not a waiting period for a new coin.

**Why fetch more than 30 days?** V6 has 5m and 1h features and startup_candle_count=200. Its 1h startup may require about 8.3 additional days before the 30-day training window; 12 future 5m target candles require matured outcomes. Request **60 days by default**, minimum 45 days under these 5m/1h parameters. Requested coverage is NOT proof that all candles exist. Existing archives with too little old data may require official Freqtrade historical prepend.

**Source code added:** scripts/bootstrap_history.py with tests/test_bootstrap_history.py. It:
- accepts 1–10 unique candidate symbols, validates USDT-M-style pair names, includes BTC correlated-pair history, and rejects operation under a non-dry-run, non-Binance or non-futures project configuration;
- uses the **official Freqtrade download-data** CLI for 5m and 1h candles, with normal Freqtrade futures mark/funding download; not a home-made exchange downloader or trading database;
- prints command plans by default; runs actual download-data and list-data --show-timerange only with an explicit --execute flag, with a fixed argv and no shell interpolation;
- writes a small ignored local record **DOWNLOADED_UNVERIFIED**, never MODEL_READY or ACTIVE. It changes **no** strategy watchlist, model state, risk setting, protected open position or real order authority.

**Example from clean V6 repository root:**

    python scripts/bootstrap_history.py --pair SOL --pair NEAR --days 60
    python scripts/bootstrap_history.py --pair SOL --pair NEAR --days 60 --execute

**Still required before promoting a coin:** independent Binance contract/liquidity validation, actual candle timerange and gap checks on 5m/1h/BTC, mature labels, funding/spread evidence, successful per-pair FreqAI LightGBM training, out-of-sample performance and valid predictions, then a safe active-position-aware whitelist update. The helper implements NONE of those post-download gates yet. A downloaded 5-day-old market is NOT automatically accepted as 60-day-ready.

**Implementation status:** The bounded history *preparation/request* helper is coded. The market-wide eight-hour selector, independent ranking quality proof, automatic history/model readiness, retraining, safe activation/restart, ongoing scheduled rotation and approved shared research/real-trading models are **NOT implemented**. There is still no eight-hour VPS scheduler or automatic new-pair training/activation from M5A. Separately, baseline M1 has now downloaded all 25 candidate histories and trained 25 LightGBM models. M2/M3 economic proof precedes any M5A deployment.



**User requirement:** Scan the entire eligible Binance USDT-M PERPETUAL market **every 8 hours**. Maintain **exactly 25 active research/trading candidate pairs**, replace **at most 10 incumbent pairs in one review**, and allow **zero changes** when alternatives are not convincingly better. Do not confuse changing *candidate eligibility* with immediately taking an actual trade. **BTC remains permanently available for market context** and is not casually removed from the candidate universe.

**Design choice: lightweight scheduled selector, not a second ML service.**
- **Discovery input:** Public Binance USDT-M exchange metadata and market statistics, initially exchangeInfo, 24-hour quote turnover, current bid/ask spread and 24-hour price range; use a bounded recent candle sample for shortlisted markets when economically/resource feasible. Verify all pairs are TRADING, USDT-quoted and settled, PERPETUAL, sufficiently old, liquid, tradeable in 1,000-USDT size, and have a reasonable spread. Reject incomplete/stale market data. Never include spot, coin-margined or suspended contracts.
- **Opportunity score:** A simple, transparent ranking of *research suitability*, combining liquidity, volatility/range, recent directional movement, spread, funding and data availability. Do not equate high recent price gain or wild volatility with a positive trade edge. Prefer robust candidates in different regimes; no mandatory turnover. Do not call a rules-based score "AI". Add a learned selector **only after** it outperforms this transparent baseline in independent tests.
- **Rotation rule:** Keep a 25-pair active set; rank eligible newcomers against weaker incumbents; replace **0–10 pairs** only when the newcomer clears meaningful improvement/hysteresis thresholds and is ready. Pin BTC and any pair with an open (simulated or future real) position; never strand position/exit/stop management to force 25 slots. If removing a protected pair prevents a clean 25-pair update, **defer changes**. Limit churn and preserve at least 15 old candidates per review.
- **FreqAI compatibility gate:** Official FreqAI explicitly warns that dynamic pairlists which introduce previously unseen pairs **cannot be used directly in a running instance** because candle history is preloaded at startup (https://www.freqtrade.io/en/stable/freqai/). The selector therefore emits a **proposal only**: old list, proposed list, scores, exclusions, UTC timestamp, source snapshot and reason codes. It must NOT hot-edit the active FreqAI whitelist or restart a process that still controls open positions.
- **Promotion preparation:** Before an external operator/orchestrated safe transition approves a proposed list, download sufficient 5m/1h market data and BTC context, verify gaps, retrain or warm-start each new pair's FreqAI model using proper independent training windows, check prediction readiness and all closed-order/position safeguards, then atomically activate a fully validated new *versioned configuration* at a safe Freqtrade restart. Any missing data/model or stale snapshot is **HOLD**, meaning leave the prior 25 intact.
- **Learning and paper:** The 25 selected research candidates then feed the existing FreqAI/LightGBM and independent 20-slot dry-run research portfolio. FreqAI market-data learning continues regardless of open positions. Paper PnL is performance feedback, **not automatically a supervised training target**. Rotating the universe must not bypass independent safety and economic model approval for future live trading.
- **Schedule:** UTC 00:00, 08:00 and 16:00 are sensible scanner review times. This is a proposed future VPS cron cadence, **not an automation or deployed service now**. Runtime/staging must be bounded, optional and auditable; do not add another always-on daemon, database, message bus or custom trading gateway.
- **Paper-first gates:** Test on recorded Binance market snapshots, evaluate stability across multiple days, enforce exactly 25/unique/USDT PERPETUAL, max10 change, BTC pin, active-position protection, no-change valid, deterministic score/reason logging, stale-input HOLD, historic data warmup, model readiness and clean rollback. Replay actual out-of-sample periods to check whether turnover increases after-cost candidate quality versus a fixed-25 watchlist.

#### M5A detailed readiness contract — selector quality is a first-class gate (October 16, 2026)

**Two separate acceptance decisions must never be confused.**

- **Candidate discovery** requires **no prior FreqAI model and no prior paper/actual trades**. It uses only public, as-of-time market metadata, book quotes, candle statistics and supported contract information. An untrained candidate may be **proposed**, but MUST NOT enter a trade.
- **Active FreqAI eligibility** requires **complete historical OHLCV candles and BTC context; mature target history; acceptable quote/liquidity/funding evidence; successful per-pair LightGBM training; compatible model feature schema; valid/available/non-expired predictions**. A candidate can be screened without these, but not promoted to an active tradeable slot.
- The current V6 target is raw forward return **12 x 5-minute bars** (one hour), NOT realized paper profit. The current FreqAI rolling window is **30 days**, requiring additional 5m/1h indicator warmup (the strategy startup_candle_count is 200); 30d alone is not automatically sufficient history for a robust model. Future-price targets must be mature; never label from incomplete future intervals.
- Freqtrade candle history belongs in the framework's managed market data files, and FreqAI models/metadata in `user_data/models/<identifier>/`. Paper trades and hypothetical fills remain in Freqtrade's separate dry-run SQLite trade DB; never claim those fills were used to train LightGBM by default. Do not invent a custom trading-history DB to solve candidate onboarding.

**Promotion state machine** (one small scheduled Python program plus native Freqtrade, not additional services):

| State | Required evidence | Allowed behavior |
|---|---|---|
| DISCOVERED | Current exchange metadata/symbol market exists | Public screening only |
| SCREENED | Perpetual USDT contract, fresh book quote, volume, funding and bounded turnover/range checks | Candidate proposal only |
| HISTORY_READY | Exact 5m/1h closed-candle windows, BTC data, warmup coverage, gaps/missingness/age checks | May train model off the running bot |
| MODEL_READY | Compatible trained per-pair LightGBM, meaningful chronological validation, fresh prediction compatibility | Eligible for paper-list activation proposal |
| APPROVED | Slot, max-10 rotation budget, safety/position checks, independent quality tests | Versioned configuration change at safe boundary only |
| ACTIVE | Restart/preloaded data verified and model `do_predict` validity | Paper research trades may be considered by standard strategy gating |
| PROTECTED/RETIRED | Still-open trade -> protected; when flat and safe -> retired | Continue trade management or stop opening new trades |

**Ranking and protection contract:**

1. Screen ALL supported USD-M perpetual contracts cheaply, but do **not** train LightGBM on every listed futures contract every 8h. Fetch a bounded shortlist for expensive candles/model readiness. Respect Binance weights and API failures; no live keys.
2. Eligibility always precedes ranking. Reject stale prices, crossed/wide spreads, abnormal book depth, too-small minimum order limits, poor 1,000-USDT fill capacity, missing funding info, unsupported or recently listed contracts lacking 30d+warmup, insufficient BTC/candle continuity, nonpositive volume and unreliable timestamps. No silently fabricated candles or scores.
3. Rank **future research/tradability**, not yesterday's biggest gainers. Use *as-of* liquidity, executable quoted spread, funding burden, volatility with penalties for chaotic spikes, multi-hour structure/momentum and portfolio/correlation diversity. Weight choices and required score improvement must be **fixed before forward evaluation**, not tuned from future outcomes.
4. Incorporate hysteresis and minimum tenure for incumbents; evidence for a *material* new advantage must exceed estimated transition/training cost. A zero-change result is fully valid. New listings should normally be excluded until sufficient historical coverage. Do not continually reshuffle candidates for cosmetic activity.
5. BTC context is permanently pinned. All pairs with open paper/live trades, unfilled orders, or required protective exits are pinned too. Atomic versioned list must stay **exactly 25 unique supported pairs**, with **0–10 replacements per 8h proposal** and at least 15 incumbents retained. If this cannot be satisfied safely, reject the change and keep the old 25.
6. **Do not hot-swap a running FreqAI whitelist.** Stage/verify historical files and models first; never restart or alter the only process managing open positions just to activate a different list. It is acceptable to review every 8 hours but deploy fewer than three times per day—or never—when training, open positions or safety conditions prevent a safe transition.
7. Make the selector's shortlist, incumbent scores, source timestamps, exclusion reasons, proposed pairs, old/new list, preflight evidence and final applied/not-applied decision reproducible from a compact local timestamped JSON audit record. No event bus, external database or extra dedicated server.

**Scientific test program and explicit go/no-go gates:**

- **Contract tests:** using frozen mock exchange snapshots: 25 unique maintained, pinned BTC, 0–10 changes, no forced churn, correct handling of 20 simultaneous paper positions, insufficient slots, suspended/delisted contract, duplicated symbol, invalid settlement asset, stale quote, liquidity collapse, incomplete candle history, and missing model; in every failure case **HOLD**.
- **Historical as-of replay:** at UTC 00:00/08:00/16:00 snapshots, compute proposals from data available **at that moment only**; no hindsight or selecting from a present-day symbol list when simulating delisted/historical markets. Account for 30d warmup/training delay, FreqAI model age and funding/slippage, and a realistic 8h rotation budget.
- **Benchmarks:** identical starting dates and risk: (A) fixed 25 pairs, (B) basic liquidity-only rotating 25, (C) candidate-selector rotated 25. Hold strategy, FreqAI settings, costs and position limits fixed; evaluate qualified signal rate, real vs hypothetical fill conditions, after-cost expectancy, drawdown, missed opportunities, pair diversity, churn, training/runtime resource use and failure-to-train rate. Compare by independent weeks/regimes and report negative results too.
- **Forward paper acceptance:** after M1–M4, run shadow selection for multiple review cycles where recommendations are logged but NOT activated, then a bounded 8-hour scheduled paper trial. Verify no real orders, healthy memory/CPU/disk, restarts, data/model availability, protected exits and rollback. Compare forward quality to frozen fixed-25 baseline; refuse promotion of the selector without credible after-cost benefit and reliable operations.
- **Rollback:** if Binance metadata/quotes fail, current snapshot is incomplete, models are stale, historic coverage fails, any position remains unprotected or baseline degradation appears, continue unchanged with the last known-good 25 and log why. The selector **never** overrides the per-trade FreqAI `do_predict` or V6 dry-run/live safety gates.

**Status:** DESIGN SPECIFICATION only. Nothing above implies the selector, staged model preparation, live 8-hour scheduler, shadow evaluation or safe-restart mechanism has been implemented. The next priority is M2 economic baseline and then M3 held-out model validation.

**Order of work:** This is a scoped M5 enhancement, *not* permission to skip M1 historic training/backtest, M2 cost baseline, M3 walk-forward ML and M4 isolated VPS paper operation. Prototype the scanner off-line if useful, but do not activate scheduled rotations before the gates above are established.

## M6 — Lightweight model lifecycle

**Goal:** Reproducible model/config changes with rollback, not institutional Champion infrastructure.

Work:
- Use FreqAI's built-in rolling training and artifact storage. Keep one active model family.
- Record code SHA, feature/label versions, training dates, model identifier and paper results.
- Compare a proposed change offline and on forward paper evidence before approving replacement.
- For future live mode, require separate explicit reviewed promotion; built-in latest-model retraining is not a validated Champion/Challenger protocol.

**Gate M6:** Versioned and reversible releases, clear no-trade fallback, no automatic real-money authority.

### M6L — Owner-gated live release code (IMPLEMENTED source, NOT authorized)

The V6 strategy includes **optional, fail-closed owner live authorization**. There is no live private config, Telegram credential, Binance exchange key, approval token or live order in this repository. The live-locked Docker profile does not auto-start.

- Server-side approval from scripts/owner_live_approval.py, 1–24 hours, owner-only terminal challenge and a chmod 0600 file outside Git. No Telegram /enable_live command.
- Requires private single-user Telegram chat_id/authorized_users match, separate untracked private Binance config, isolated futures, max one actual position, 1x, stake <=1,000 USDT, FreqAI validity/expiry, API off, forced manual entry off and market stoploss_on_exchange.
- Both startup and **every real entry callback** verify authorization; expiration/revocation blocks new real orders but does not intentionally block the management/exits of an existing trade. A separate explicit operator/owner review of abort, external account reconciliation and partial-failure handling remains mandatory.
- Code staged under LIVE_SAFETY.md; actual live model release governance is **not implemented**. FreqAI may use the latest retrained model, so an operator token is NOT sufficient to certify the strategy or approve model changes. M6 must establish versioned research->execution model release and rollbacks before M7.
- Native Freqtrade Telegram is for owner-only monitoring, pause, status, results and operational resumes. Telegram group chats are forbidden for live authority; it is **not** the sole security factor. Use /pause to block new entries while preserving active exit management; /stop requires awareness of open exposure and off-bot emergency procedures.
- Tests must independently cover missing/expired/revoked approval, wrong owner, chat-group rejection, mixed authorized users, excess stake/position count, secret leak, on-exchange stop disabled, strategy import, VPS container/file UID mapping, Telegram authorization, restart behavior and stop order reconciliation.

**Status: LIVE CAPABILITY CODE-STAGED ONLY. No persistent deployment or permission to place real Binance orders.** M1 technical historical integration is now proven but showed losses. M2–M6 and separate owner approval remain mandatory before M7.

## M7 — Optional real trading (LOCKED)

Only after M1–M6, compelling after-cost evidence, proven stability and a distinct owner approval may a separate live risk/security design be considered. Review private API permissions, protective stop behavior, liquidation/funding/slippage, maximum loss and emergency shutdown, reconnection and simultaneous-pair one-position enforcement. Nothing in this roadmap or the starter permits real orders now.

## C2. Revised paper amounts, evaluation and knowledge-sharing contract (October 16, 2026)

Requested initial **simulated** configuration, pending risk/market validation:
- Paper wallet **100,000 USDT**, fixed position **1,000 USDT**, **1x** leverage, **2% initial stoploss**, **5% initial ROI goal**, decisions on closed **5m candles**, FreqAI setting **live_retrain_hours=24**. Rough 1,000 USDT notional price risk at 2% is **20 USDT before fees/funding/slippage**; gap/slippage may exceed this.
- Configured **25-symbol static universe**, not 25 open trades. The single mode permits only **1** open simulated trade; independent paper research permits up to **20 simultaneous simulated trades** (a ceiling, not a target), meaning at most **20,000 USDT nominal concurrent 1x exposure** and a nominal combined initial price stop risk around **400 USDT** before fees/funding/slippage; correlated coins can gap together.
- All 25 must be checked against Binance USDT-M supported perpetual contracts, data depth, liquidity/spread, FreqAI training duration and VPS capacity before operation. No assumption a listed symbol is tradable or sufficiently liquid.
- FreqAI evaluates each fixed universe pair independently with historical candle/volume/volatility features, BTC context, strategy structure, prediction validity and a provisional +/-0.6% model threshold. This is **AI-guided entry filtering**, not AI choosing/replacing membership in the top 25. FreqAI expressly disallows dynamic pairlists that add/remove pairs midrun without preloaded data.
- The global best-ranked among 25 simultaneous signals is **not currently guaranteed**: Freqtrade may take the first qualifying pair. If needed, implement/test a deterministic global ranking after M1–M3, never claim it exists in the baseline.
- **Learning is not yet shared** between the two processes: independent identifiers and per-pair LightGBM retraining, separate paper ledgers. This is deliberate until model reuse and promotion safety are verified.
- **M6 planned low-complexity sharing:** train market models with one paper-research owner, record/version models and features, validate candidates on unseen historical + forward paper data, then let a separate one-position inference/decision process consume only *approved model snapshots*. Keep separate databases and position limits. Test native FreqAI/Freqtrade sharing interfaces on the pinned image; avoid custom model-server/microservices. FreqAI retraining on new candles does not itself learn from simulated or real trade PnL; this feedback affects scientific evaluation until separate leakage-safe labels are built.
- Automatic sharing of **unapproved** newly trained models with live order execution is forbidden. Any real-money enablement remains M7 and separately authorized.
- **M1–M4 resource gate:** 25 pairs plus multiple training instances may exceed existing VPS memory/CPU; benchmark on isolated hardware and degrade to fewer pairs rather than pressure a protected production VPS.

## D. What gets tested at each change

Every V6 code change should include the smallest suitable test:
1. Source tests: can import; no future information in features; blank/invalid predictions abstain; global limit and dry-run guard.
2. Official-image test: actual Freqtrade 2026.x strategy-discovery and valid config.
3. Data test: real futures candles, all required timeframes/pairs, BTC context and no silent gaps.
4. Backtest: actual model fit, completed trades, leakage detection, explicit commissions/funding.
5. Forward test: dry-run startup, restart recovery, no order authority, stable resources.
6. Economic acceptance: risk-adjusted net vs non-ML and no-trade, untouched periods, credible uncertainty.

If a check does not run, label it NOT TESTED. Never present a unit test as a live-trading proof.

## E. Main-branch and VPS release policy

**Existing main is legacy V5.** It remains untouched until separately reviewed release migration. A clean V6 branch may show a large deletion diff when compared with V5; DO NOT merge that diff into legacy main as an ordinary feature PR.

For **genuinely separate Git history**, create a new NBOT-V6 GitHub repository with the clean files. This connected GitHub integration cannot itself create a repository. Otherwise, retain the current repo, preserve the original main using protected archive branch/tag and verified backups, then deliberately change the GitHub default branch to V6. Git history still retains V5 commits in that option.

V6 may become the default/main development line when **M0+M1** pass and an owner-reviewed cutover plan preserves V5. That is separate from operational readiness: deployment/dry-run needs **M2/M3** checks, and reliable paper operation needs **M4**. Real trading is separate approval. Never set main or enable services purely because code was copied onto a VPS.

## F. Anti-overengineering rules

- Add one feature only to solve a measured failing requirement.
- Prefer native Freqtrade/FreqAI; no new runtime services, databases, wrappers or infrastructure without evidence.
- No more than one model family until the baseline has passed meaningful evaluation.
- Do not enforce a trade quota, paper Champion requirement or 2,000-row counting ceremony without measurable value.
- Favor tests and reproducible performance over architecture diagrams, coding milestones or code volume.
- Do not silently bring V5 files/CI/history assumptions into V6. V5 is read-only reference.
- A losing result should trigger diagnosis or pause, not uncontrolled new indicator development.
- Never use the words profitable, verified or deployed without the corresponding dated evidence.

### Reviewed milestone checklist (2026-10-17)

- [x] **M0: Clean V6 source and baseline CI** — isolated from V5; CI and strategy discovery passed.
- [x] **M1: Historical engine/model technical proof** — all 25 Binance USDT-M datasets and 30-day FreqAI models checked, seven-day official historical backtest completed. *Returns were negative; M1 is not a profitability approval.*
- [ ] **M2: Honest after-cost/non-ML baseline** — non-ML strategy and first-week comparisons completed; realistic execution/funding verification **OPEN**.
- [ ] **M3: Credible FreqAI improvement** — untouched multiple-regime walk-forward and cost-adjusted model attribution not established.
- [ ] **M4: 20-slot simulated research forward trial** — configuration **exists**; independent VPS daemon/restarts/position safety not yet approved or tested.
- [ ] **M5A: Eight-hour intelligent 25-candidate universe selector** — **not built**; ranking, liquidity, churn caps, BTC anchoring, history/model readiness, open-trade protection and replay acceptance still required. A 25-coin fixed history test does NOT replace the selector.
- [ ] **M6: Approved-model governance** — shared model version qualification/rollback not built.
- [ ] **M7: Any live funds** — explicitly **LOCKED**; owner-only code-staged release hook is not deployment approval.

## G. Progress ledger — 2026-10-17

| Milestone | State | Required next proof |
|---|---|---|
| M0 clean tree | COMPLETE — source isolation only | Clean-tree commit 3e642508; V6 CI run 38906351380 passed both jobs (offline + official strategy discovery) |
| M1 real FreqAI backtest | **TECHNICAL COMPLETE**: 25/25 full-history fit + independent 7-day 34-trade backtest; **-135.64 USDT** | M2 fee/spread/funding/slippage baseline, M3 broader held-out replay; no deployment |
| M2 honest baseline | **PARTIAL — gate still BLOCKED**; no-ML +169.849 vs AI −135.640 USDT; matched doubled-fee, historical funding and exact signal exports verified; **AI lookahead flagged differences** | Verify historical execution/slippage, fee tiers, root-cause changing AI prediction/signal indicators and full `do_predict` abstentions; NOT ACCEPTED |
| M3 FreqAI edge | NOT STARTED | Multi-period walk-forward results |
| M4 forward dry-run VPS | NOT STARTED; research mode source implemented | Capacity, two-profile official checks, independent forward-paper report |
| M5 expand and port selected features | DEFERRED | M3/M4 evidence |
| M5A universe selection/rotation | SELECTOR NOT BUILT; offline history bootstrap coded | Market screening, scientific selector validation, model readiness and safe activation still missing |
| M6 lightweight model governance | DEFERRED | Demonstrated need |
| Owner-only live release hook | CODE STAGED; NOT EXECUTED | Native framework smoke + private-file/Telegram/risk tests; M7 acceptance still required |
| M7 any live money | LOCKED | Separate user-approved risk plan |

**Current priority: Finish M2 after-cost assumptions/AI no-leakage checks, then M3 multi-regime held-out tests. M5A universe selector and the separate up-to-20-position paper-research mode remain explicit future milestones, NOT forgotten or silently replaced by a one-slot historical benchmark. No continuous VPS trading daemon, default-branch change, real-money permission or legacy data migration is authorized.**
