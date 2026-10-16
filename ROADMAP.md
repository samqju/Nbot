# NBOT V6 — Development and Release Roadmap

**Roadmap version 1.0, October 16 2026**  
**Project:** Small Binance USDT-M trading bot using Freqtrade + FreqAI.  
**Release state:** Prototype. No accepted backtest, no VPS deployment, no live trading authorization.  
**This document controls V6 scope.** Legacy V5 documentation is historical, not an active V6 specification.

## A. What we are building

NBOT should observe approximately 50 liquid coins eventually, including Bitcoin context; recognize directional setups; learn whether opportunities might deliver positive after-cost performance; select LONG, SHORT or NO TRADE; and—if future live trading is separately approved—hold no more than ONE actual position in total. Improve trade selection, not trading frequency.

Initial scope: 8 fixed futures markets including BTC, completed 5m candles, correlated BTC 5m/1h information, one FreqAI LightGBM model, a few causal EMA/breakout/pullback rules, and one simulated portfolio. Expansion to 50 pairs is conditional, not a day-one requirement.

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
- Download sufficient 5m and 1h futures candles for 8 markets: at least the 30d training window, indicator warmup and the historical backtest period. Identify gaps; do not invent candles or forward-fill missing futures data without a scientific justification.
- Run documented official Freqtrade backtest with FreqAI and record exact Git SHA, timerange, image digest, logs, model and result artifacts.
- Explicitly test prediction abstention, one-position cap and long/short behavior.

**Gate M1:** Real backtest exits successfully, predictions are produced with no time/data-integrity errors, and failure/restart produces no hidden real trading behavior. Do NOT commission VPS yet.

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
- Permit up to **10 concurrent simulated paper positions by default**, with an absolute optional ceiling of 20 via configuration and a strict dry-run startup guard. These are capacity limits, never trade quotas. Current 8-pair watchlist limits distinct simultaneous paper trades to 8 in normal Freqtrade behavior.
- Keep single-position execution separate. Research should continue collecting candles and FreqAI retraining regardless of whether that separately configured bot has an open position. With two independently retraining FreqAI instances, measure cumulative CPU/RAM and schedule staggered updates if needed; do not assume a small VPS can run both.
- Paper trades from Freqtrade's dry-run database provide **forward operational and economic feedback** (with simulated fills/limits). FreqAI continues learning from candle features and future-price targets. **Paper PnL is NOT fed back into the LightGBM model automatically** and must never be presented as such.
- Review the first **10–20 completed simulated trades** for debugging assumptions, order lifecycle and measured costs; do not label 20 examples statistically sufficient for model promotion or live approval. Require a longer, multi-regime forward window and held-out, after-cost comparison in M2/M3/M4.
- No custom virtual-trade factory, separate exchange connector, new optimizer, duplicated historical database or automatic live model promotion. Prefer standard Freqtrade trade history and reports.
- **Fail-closed release controls:** dry_run=true required, exchange keys must be blank on researcher, 1x leverage, max 20 simulated slots, disabled remote API, separate DB/identifier and explicit process start. This V6 source has no real-order mode. M7 remains separately locked.

**M4 research-lane acceptance:** both config variants pass official Freqtrade import/schema checks, research startup accepts 10 (and no more than 20) simulated slots, unexpected live/order credentials are rejected, model/DB isolation is verified, and an isolated forward dry-run proves independent operation and no real orders. Source tests do not satisfy the forward gate.

## M5 — Controlled market and feature expansion

**Goal:** Expand only when justified.

Work:
- Scale 8 -> 15 -> 25 -> up to roughly 50 coins; verify quote/candle quality, running memory, training time and trade-selection outcomes each time.
- Evaluate historical V4 24-pattern detectors as optional *indicators*, one at a time, only when causal tests and incremental out-of-sample improvements warrant a port.
- Continue to allow NO TRADE. Do not turn 24 pattern descriptions into 24 trading microservices.
- Use standard Freqtrade dashboard/Telegram features later if necessary; avoid inventing another control plane.

**Gate M5:** No integrity, resource, robustness or risk-adjusted net degradation relative to accepted M3/M4 baseline. Expansion can stop below 50.

## M6 — Lightweight model lifecycle

**Goal:** Reproducible model/config changes with rollback, not institutional Champion infrastructure.

Work:
- Use FreqAI's built-in rolling training and artifact storage. Keep one active model family.
- Record code SHA, feature/label versions, training dates, model identifier and paper results.
- Compare a proposed change offline and on forward paper evidence before approving replacement.
- For future live mode, require separate explicit reviewed promotion; built-in latest-model retraining is not a validated Champion/Challenger protocol.

**Gate M6:** Versioned and reversible releases, clear no-trade fallback, no automatic real-money authority.

## M7 — Optional real trading (LOCKED)

Only after M1–M6, compelling after-cost evidence, proven stability and a distinct owner approval may a separate live risk/security design be considered. Review private API permissions, protective stop behavior, liquidation/funding/slippage, maximum loss and emergency shutdown, reconnection and simultaneous-pair one-position enforcement. Nothing in this roadmap or the starter permits real orders now.

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
| M1 real FreqAI backtest | NOT STARTED | Historical download, training and replay |
| M2 honest baseline | NOT STARTED | Baseline and after-cost report |
| M3 FreqAI edge | NOT STARTED | Multi-period walk-forward results |
| M4 forward dry-run VPS | NOT STARTED; research mode source implemented | Capacity, two-profile official checks, independent forward-paper report |
| M5 expand and port selected features | DEFERRED | M3/M4 evidence |
| M6 lightweight model governance | DEFERRED | Demonstrated need |
| M7 any live money | LOCKED | Separate user-approved risk plan |

**Current priority: M1 — prove actual FreqAI historical training and backtesting on isolated hardware. The optional research lane does not bypass this gate. No VPS deployment, default-branch changes, real trading permissions or legacy data migrations are yet authorized.**
