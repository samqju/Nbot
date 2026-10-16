# NBOT V6 — Development and Release Roadmap

**Roadmap version 1.0, October 16 2026**  
**Project:** Small Binance USDT-M trading bot using Freqtrade + FreqAI.  
**Release state:** Prototype. No accepted backtest, no VPS deployment, no live trading authorization.  
**This document controls V6 scope.** Legacy V5 documentation is historical, not an active V6 specification.

## A. What we are building

NBOT should observe approximately 50 liquid coins eventually, including Bitcoin context; recognize directional setups; learn whether opportunities might deliver positive after-cost performance; select LONG, SHORT or NO TRADE; and—if future live trading is separately approved—hold no more than ONE actual position in total. Improve trade selection, not trading frequency.

Current **configured candidate scope: 25 fixed futures markets** (subject to M1 exchange and data checks) including BTC, completed 5m candles, correlated BTC 5m/1h information, one FreqAI LightGBM model, a few causal EMA/breakout/pullback rules, and one simulated portfolio. Expansion to 50 pairs is conditional, not a day-one requirement.

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

**Measured hardware evidence:** 1-GB/2-vCPU Observation VPS successfully downloaded 60-day BTC public futures history and trained a reduced 3-day/5m-only LightGBM model, finishing a one-day backtest with **zero trades**. The 30-day full 5m/1h BTC model and a 30-day lean model both exited **137** inside a **440-MB** process memory cap. **2 GB** is the *first next experiment* for full M1; only consider **4 GB** when results justify it. The 25-pair research footprint is **unmeasured**; **8 GB is NOT a starting requirement** and must not be provisioned without evidence. All future deployments require measured peak RAM/CPU and no existing V5 service disruption.

**Release rule:** Publishing the full setup guide does **not** authorize starting a persistent bot, upgrading V5, automatically running the eight-hour selector, enabling Telegram real-money control, or placing Binance real orders. M1–M4 and later M5A/M6/M7 gates remain as written. Until a tested immutable Docker image digest is approved, the Compose image's `stable_freqai` tag is **mutable** and must not be treated as a production pin.

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

### M1 execution record — 2026-10-16 (real exchange and FreqAI evidence; M1 NOT ACCEPTED)

- Both authorized Ubuntu PuTTY VPS sessions accessible; each **2 vCPU, 954 MiB RAM**, no Docker, Observation with no swap. Original V5 systems and services were left unchanged. Observation has an isolated `/home/ubuntu/nbot-v6-m1-20261016/` research folder, with a *private local Python virtualenv only* and no persistent bot.
- Real public Binance USDT-M market metadata and 5m/1h sampled historical candles were checked for all **25/25 configured candidates** (no failures). [Detailed report](evidence/m1/2026-10-16-binance-public-preflight.json). This is not complete 60-day data or model-quality verification.
- GitHub's official FreqAI Docker import passed for Freqtrade **2026.9**, immutable image digest `freqtradeorg/freqtrade@sha256:e0ca51420b80357edcbec3970fd8a33ebebeacd53b914aed2735a9c14fe94535`. The [second GitHub M1 attempt](https://github.com/samqju/Nbot/actions/runs/38927259804) reached Binance but was blocked by **451 geographical restrictions**. No real model training occurred **on that runner**.
- **User-requested small-VPS experiment:** Native, user-local **Freqtrade 2026.9 / LightGBM 4.7** installed successfully without Docker/system packages, all under the cgroup **440-MB memory cap**. Official `freqtrade download-data` fetched BTC 5m **17,476** candles, BTC 1h **1,456** candles, mark-price **1,456** records and funding-rate **183** records, using the public real Binance API. No exchange credentials.
- **Proof of actual FreqAI end-to-end integration:** An explicitly reduced, **BTC-only 3-day training/5m-only diagnostic** trained LightGBM on **681** valid examples and **5** features (0.51-second logged model fit), and successfully completed an official native one-day **October 1–2** backtest with **zero trades**. This verifies that FreqAI can technically train/backtest on a 1-GB VPS in *small* mode, **not that it makes money or that intended V6 parameters pass**.
- **M1 target still blocked by memory:** One BTC pair, **original 30-day/5m+1h** features exited **137 (killed)** during training under the 440-MB cap. A separate **30-day lean 5m-only/30-tree configuration also exited 137** at the same point, with no completed full-window model fit. Host remained responsive; ~534 MiB available RAM and ~42 GiB free disk afterward. All experiments have hard limits and no live mode.
- Exact case configurations and proof: [evidence/m1/2026-10-16-observation-vps-1gb-freqai-trial.md](evidence/m1/2026-10-16-observation-vps-1gb-freqai-trial.md); overall acceptance checklist and Docker-region issue: [M1_EVIDENCE.md](M1_EVIDENCE.md).
- **Status: PARTIALLY VERIFIED; M1 NOT ACCEPTED.** Do not advance to M2, start VPS paper trading or authorize live orders until the original **30-day training window, full 5m/1h feature set, seven-day independent historical backtest, predictions and strategy economic metrics** are verified.
- **Capacity policy changed based on evidence:** **Do not assume 8 GB RAM is needed.** One GB proved sufficient for 3-day/1-coin training, while the 30-day test was stopped by a deliberately strict 440-MB cap. Try full 30-day training first on an isolated **2-GB** host; only test **4 GB** or higher if peak-memory measurements justify the expense. Benchmark the 25-pair research workload before choosing production memory. V5 VPS machines should never be overloaded to speed up M1.

## M2 — Honest non-ML baseline and after-cost evaluation

**Goal:** Establish what basic trading signals achieve without assuming ML is helpful.

Work:
- Freeze the initial EMA20/EMA50 trend and 20-candle breakout/pullback hypotheses.
- Run a simple non-ML strategy benchmark and a NO TRADE benchmark on the same historical periods.
- Evaluate after fees, spread/slippage assumptions and relevant futures funding. State which charges are simulated and which are observed. The starter 0.2% roundtrip proxy is a placeholder, not a fill-derived label.
- Measure eligible decisions, signals, abstentions, opened/closed trades, net returns, drawdown, profit factor, win/loss distribution, exposure, holding time and results by coin and side.
- Execute leakage/lookahead checks. The future-return FreqAI training target must never appear as a decision-time feature.

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

**Implementation status:** The bounded history *preparation/request* helper is coded. The market-wide eight-hour selector, independent ranking quality proof, automatic history/model readiness, retraining, safe activation/restart, ongoing scheduled rotation and approved shared research/real-trading models are **NOT implemented**. There are no VPS scheduler, actual historical data downloads or model-training results from this change. M1 historical FreqAI backtesting comes first.



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

**Status:** DESIGN SPECIFICATION only. Nothing above implies the selector, staged model preparation, live 8-hour scheduler, shadow evaluation or safe-restart mechanism has been implemented. M1 actual FreqAI backtesting remains the immediately next required milestone.

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

**Status: LIVE CAPABILITY CODE-STAGED ONLY. No server deployment or permission to place real Binance orders.** The first development milestone is still M1 genuine historical data retrieval and FreqAI model training/backtesting; after M1, pursue M2-M6 before M7.

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

## G. Progress ledger — 2026-10-16

| Milestone | State | Required next proof |
|---|---|---|
| M0 clean tree | COMPLETE — source isolation only | Clean-tree commit 3e642508; V6 CI run 38906351380 passed both jobs (offline + official strategy discovery) |
| M1 real FreqAI backtest | PARTIAL VERIFIED: 25/25 market checks + BTC 3-day LightGBM fit/1-day 0-trade backtest; 30-day model hit 440MB cap | Test 30-day real fit + 7-day historical replay on 2–4GB isolated host before 25 pairs |
| M2 honest baseline | NOT STARTED | Baseline and after-cost report |
| M3 FreqAI edge | NOT STARTED | Multi-period walk-forward results |
| M4 forward dry-run VPS | NOT STARTED; research mode source implemented | Capacity, two-profile official checks, independent forward-paper report |
| M5 expand and port selected features | DEFERRED | M3/M4 evidence |
| M5A universe selection/rotation | SELECTOR NOT BUILT; offline history bootstrap coded | Market screening, scientific selector validation, model readiness and safe activation still missing |
| M6 lightweight model governance | DEFERRED | Demonstrated need |
| Owner-only live release hook | CODE STAGED; NOT EXECUTED | Native framework smoke + private-file/Telegram/risk tests; M7 acceptance still required |
| M7 any live money | LOCKED | Separate user-approved risk plan |

**Current priority: M1 — complete the original 30-day/5m+1h FreqAI training and seven-day backtest, next testing 2–4 GB in an isolated Binance-accessible host if feasible. The one-day 3-day-trained smoke is a partial technical proof, not M1 acceptance. The optional research lane does not bypass this gate. No VPS deployment, default-branch changes, real trading permissions or legacy data migrations are yet authorized.**
