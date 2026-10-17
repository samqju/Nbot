# NBOT V6 — Development and Release Roadmap

**Starting a new ChatGPT conversation?** Read [NEW_CHAT_HANDOFF.md](NEW_CHAT_HANDOFF.md) first. It preserves the owner's exact V6 research permissions, Sep/Oct results, active M2R priority, outstanding safety gates, authorized VPS context and a copy-ready continuation prompt. **No paper/live permission is implied.**

**Roadmap version 1.2, October 17 2026**  
**Project:** Small Binance USDT-M trading bot using Freqtrade + FreqAI.  
**Release state:** Prototype. M1 technical proof complete; full September M2 research found losses in AI and non-ML. **M2 release gate NO-GO.** A separate M2R offline design for after-cost learning and bounded strategy routing is authorized for **code/research only**; M3, paper and live trading NOT accepted.  
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

**Status: M2 INVESTIGATION COMPLETE WITH NO-GO; M2 ACCEPTANCE GATE FAILED. DO NOT ADVANCE TO M3 OR PAPER TRADING.** Source results and exact limitations: [M2_EVIDENCE.md](M2_EVIDENCE.md); [machine-readable fee/cost/coin/side comparison](evidence/m2/2026-10-17-first-week-cost-sensitivity.json).

### M2 detailed checklist (tick only proven items)

- [x] **Owner-requested FULL September 2026 (30 days) instead of seven days only:** 25/25 July-through-September historical data audits passed; **125** rolling 30-day LightGBM fits completed without ERROR lines (five historical weekly model windows × 25 coins). Separate prior-data training prevents simply reusing September as the initial training sample. [September full-month study](evidence/m2/2026-10-17-september-full-month-analysis.md).
- [x] **September 1–30, identical 25-pair baseline/AI/NO TRADE test:** AI **137 trades, −444.980 USDT**; non-ML **163 trades, −242.894 USDT**; NO TRADE **0 USDT** at 0.05% fees per side. Both strategies **lost**, unlike the prior no-ML +169.849-USDT October week.
- [x] **September official fee and exposure retest:** at 0.10% per side AI **−576.688** and non-ML **−388.318 USDT**. One-position time-at-market: AI **40.637%**, non-ML **99.641%**. [Exact machine report](evidence/m2/2026-10-17-september-30day-comparison.json).
- [x] **September historical funding cross-check completed with exceptions:** 137 AI / 163 non-ML trades evaluated against Binance's real public funding events. Two forced month-boundary exits (AI ATOM, baseline INJ) each show ~0.10 USDT engine-vs-external discrepancy; small but **NOT cleanly reconciled**.
- [ ] **Resolve September 30/October 1 forced-exit funding treatment** before claiming exact long-window funding accounting.


- [x] **Frozen no-ML comparator**: the same EMA20/EMA50 trend, prior-20-candle breakout and pullback setups, independent no-FreqAI strategy [NbotV6NoML](user_data/strategies/NbotV6NoML.py); original AI strategy unchanged.
- [x] **NO TRADE baseline**: zero positions, zero trading P&L and exposure, no fees.
- [x] **Matching first-week official backtests:** all 25 USDT-M candidates, **2026-10-01 through 2026-10-08**, fixed 1× / one position / 1,000-USDT stake, 100,000 simulated wallet. **AI: 34 trades, -135.640 USDT; no-ML: 31 trades, +169.849 USDT** at 0.05% per side.
- [x] **Official fee sensitivity:** both strategies rerun using 0.10% per side; **AI: 34 trades, -169.555 USDT; no-ML: 30 trades, +138.554 USDT**. Fee choices may change the trade path.
- [x] **Additional hypothetical cost stress:** exported-trade **+10/+25/+50/+100 roundtrip bps** sensitivity, labeled as *fixed-fill illustrative deductions*, not measured actual fills. The positive non-ML result vanishes under the +100 bps stress.
- [x] **Trade-level coin, side, duration and funding-field audit:** reproducible [scripts/m2_evaluate.py](scripts/m2_evaluate.py) generates per-pair/per-side closed-trade summaries, fees, approximate exposure and hypothetical adjusted returns; official ZIP results remain private on the V6 research VPS.
- [x] **Non-ML signal lookahead screening:** official `lookahead-analysis` checked **30** baseline signals, with **0 detected** biased entries/exits (not proof of every possible signal).
- [x] **Download and inspect independent time-aligned historical Binance order-depth:** **59** symbol/day public bookDepth archives requested, **57** available; **113/130** entry/exit events had a fresh <=45s snapshot; **17** were stale/unverified. In the 113 matched snapshots, USD-M depth within 0.2% was at least **40.22×** a $1k position, but this does **not** prove executable bid/ask quotes. [Detailed per-event data](evidence/m2/2026-10-17-historical-depth-trade-time-audit.json).
- [x] **Historically conditioned conservative extra-cost scenarios:** under assumed matched/stale cost of **5/25 bps per side**, AI **−185.520**, baseline **+121.191 USDT**; at **20/100 bps per side**, AI **−335.160**, baseline **−24.784 USDT**. Those are **stress assumptions, NOT actual fills**. [Scenario evidence](evidence/m2/2026-10-17-snapshot-quality-cost-stress.json).
- [ ] **Exact realized historical spread/maker-taker queue/slippage, account fee tier and severe stop-gap fills:** public October 2026 USD-M bookTicker archive returned **HTTP 404** and depth snapshots are insufficient. This **cannot be certified from available data**; a prospective order-book capture/paper execution test is needed.
- [x] **Historical funding-event reconciliation:** all **65** official trades (34 AI + 31 no-ML) cross-checked against public Binance USD-M settlement timestamps/rates/mark prices; aggregate AI −0.721885 vs −0.721893 USDT; baseline +0.367678 vs +0.367662 USDT; zero trades differ by more than five cents. [Per-trade evidence](evidence/m2/2026-10-17-public-binance-funding-reconciliation.json). Actual order type fee tiers/quality remain [ ] unverified.
- [x] **Controlled BTC/ETH FreqAI future-data checks:** all **2,016** predictions per coin match exactly across full 25-pair vs 1-pair training; **576** early predictions per coin also match perfectly between two-day evaluation and seven-day evaluation. Original FreqAI score, mean/std, `do_predict`, and `DI_values` unchanged. [Context invariance](evidence/m2/2026-10-17-prediction-invariance-btc-eth.json) / [as-of prefix](evidence/m2/2026-10-17-asof-future-truncation-predictions.json).
- [ ] **AI leak-check certification:** official eight-signal lookahead still reports `has_bias=Yes` and changed model/entry/exit indicator columns despite these controlled two-coin checks. Root cause and all-25 decision consistency **unresolved; release BLOCKED**. [Lookahead detail](evidence/m2/2026-10-17-ai-lookahead-and-signals.md).
- [x] **Export and reconcile actual entered/rejected/exited signal rows** from full original-strategy Freqtrade reruns: AI **34/68/34**, no-ML **31/6,531/31**. Repeated rejected rows are not independent trades. [Evidence](evidence/m2/2026-10-17-ai-lookahead-and-signals.md).
- [x] **Audit original 50,400 candle-and-coin predictions:** **6,837 raw EMA setups → 28 blocked by invalid AI forecast, 6,661 removed by score/direction filter → 148 potentially eligible AI signal rows** (128 long, 20 short); original engine actually entered **34**, explicitly rejected **68**; other **46** candidates were not labeled in the exported engine rejection category. [Full per-pair audit](evidence/m2/2026-10-17-original-model-decision-gates.json).
- [x] **Time actually at risk:** AI global position occupied **78.583h / 168h = 46.776%**; no-ML baseline **167.667h / 168h = 99.802%**; no overlapping positions. [Risk exposure](evidence/m2/2026-10-17-original-risk-exposure.json). The non-ML one-week gain was achieved while almost always exposed!
- [ ] **Engine-level explanation of the 46 additional eligible AI signal rows not recorded as accepted or explicit rejections** and live-versus-historical full latency/order life cycle. These cannot be classified as independent missed trades.
- [ ] **Additional independent market periods, statistical uncertainty and regime comparisons:** M3's explicit multi-window walk-forward acceptance; one losing AI week / one winning non-ML week prove neither strategy's dependable edge.

**Updated M2 finding:** No-ML beat FreqAI by **305.489 USDT** during the October week but both lost in full September (no-ML **−242.894 USDT**, AI **−444.980 USDT**). The earlier winning week is **not dependable proof of profitability**. The no-ML strategy was invested **99.641%** of September. Original October detail: no-ML beat FreqAI by **305.489 USDT** in that first week. This does **not** isolate the *causal* effect of AI because the compared strategies also differ in their exit rules, nor does it prove the simple approach is profitable. Do not tune features to fit this single period. The historical **M2 gate remains OPEN** until defensible execution costs and leakage controls are verified.

**Gate M2:** Complete reproducible metrics, defensible costs and no known decision leakage. A loss-making benchmark is a valid finding, not a reason to fabricate performance.

## M2R — Research-only upgrade: learn from complete trades, after costs, then controlled strategy selection

**Owner decision — October 17, 2026:** Build the three requested capabilities in the following order. **This authorizes offline source development and short-lived historical research tests ONLY.** It does not overturn the M2 NO-GO, authorize a 20-slot persistent paper bot or approve live money.

**Why change the learning task?** September 2026 proved the current "price in one hour" FreqAI target did not give an economic edge: current AI **−444.980 USDT**, no-ML **−242.894 USDT** (25 markets, single global slot). The frozen no-ML approach was exposed **99.641% of September**. Trade profitability after realistic costs—not directional forecasting alone—is the research target. A new model is a **Challenger** until tested on untouched future dates.

### January-onward history: downloaded and integrity-audited on V6 VPS (October 17); model comparisons NOT RUN

The owner proposes extending the **existing fixed-25-market** public Binance USDT-M research archive back to **January 1, 2026** for richer market-regime coverage. This is a sound *data collection and independent-testing* direction, **not** a proven model improvement or a change to the existing M2R model. The current research override explicitly sets `train_period_days=30` and `backtest_period_days=7`: extra files alone will not increase each model's historical training window, and saved predictions do not retrain on all history for each decision.

**Correct order:** FIRST audit the native FreqAI 12-bar future-label train cutoff and investigate official `has_bias=Yes`; then acquire/verify Jan-2026-onward 5m/1h futures, mark and funding public data for the original 25 markets (as available by listing date), with exact last complete UTC candle, gaps, disk/resource metrics and data fingerprints. BEFORE examining results, freeze several previously uninspected independent chronological regime windows, untouched validation splits, costs, strategy thresholds and all baselines (original AI/non-AI, matched no-AI, NO TRADE). Compare 30-day baseline versus **proposed 60/90/180-day** rolling fits under equal as-of evaluation dates where warmup and 8-GB VPS limits permit; preserve separate experiment identifiers. Do not mistake overlapping hypothetical labels for executed trades or retrospectively optimize on September/October results. **Update: January public history acquisition and source/installed-image label-prefix checks HAVE NOW RUN AND PASSED as recorded below; the independent all-25 fixed-model leakage test, execution/funding fixes, and May–August 30/60/90/180-day trading comparisons are still NOT RUN. M2 release NO-GO; M3/M4/M5A/M7 gates unchanged.**


**NEW VERIFIED V6 VPS result:** Existing root-owned research checkout accessed via saved PuTTY `8GB-Observation` with explicit SSH user `root`, fast-forwarded to the isolated branch; installed Freqtrade **2026.9** image executed real 12-bar BTC training-prefix tests. All three after-cost target families left **12/12** suffix labels NaN at Oct 8 cutoff; combined **1,145**, breakout **617**, pullback **539** valid counterfactual training examples, **not executed trades**. Native FreqAI original-price training logs independently dropped **12/8,640** future-label rows.

**NEW DOCUMENTED HISTORY ACQUISITION:** Public Binance USDT-M Jan 1–Oct 16 2026 (UTC, end Oct 17 exclusive), **original 25 frozen markets** × 5m futures + 1h futures + 1h mark + 1h funding event = **100/100 staged files** in a separate non-active V6-only folder (~51 MiB). Two download phases exited 0; independent read-only audit exited 0, **0 missing files, 0 gaps in 5m/1h candles, 0 duplicate timestamps, 0 invalid OHLCV, 0 changed/absent rows in the original July–October overlap**. [Full reproducible report](evidence/m2r/2026-10-17-vps-resumed-cutoff-lookahead-history.md) / [compact JSON](evidence/m2r/2026-10-17-vps-history-runtime-summary.json) / [auditor](scripts/m2r_history_stage_audit.py). **This is data readiness, NOT extra model learning or an accepted trading result.**

**Repeated original official AI lookahead:** 25-pair 8-signal native Freqtrade test again reported `has_bias=Yes`, **0 explicit biased entries, 0 exits**, and changes to `&-`, `do_predict`, DI and decisions. Tagged upstream detector *deletes FreqAI model identifiers and retrains shortened one-pair probes*, a documented confounder **not yet proved to explain every changed decision**. Conservative real BTC/ETH label-only internal 80/20 validation boundary checks show small unpurged overlap; actual fitted-row embargo and all-25 frozen-model as-of invariance remain unchecked. **M2 integrity gate STILL NO-GO; no M3, paper or live.**

- [x] **Download and independently verify Jan 1–Oct 16 frozen-25 public history in a separate read-only-audited staging archive**, with exact source artifacts and deterministic hashes logged.
- [x] **Run actual pinned-research-image source/prefix target check and fresh official 25-pair lookahead repeat**, retaining the unresolved `has_bias=Yes`.
- [ ] **Qualify January historical data for actual 30/60/90/180-day FreqAI fitting** only after all-25 frozen-model/prefix and execution/funding validity concerns are addressed; preserve the frozen May–August preregistration and NO TRADE benchmark. **NO fresh historical trading comparisons yet.**

**NEW OCTOBER 17 M2R VALIDATION — verified and still non-release:** [Frozen native model / embargo / funding audit](evidence/m2r/2026-10-17-frozen-model-embargo-funding-audit.md) and [repeatable 25-pair native probe](scripts/m2r_frozen_native_prefix_probe.py) document **25 fitted four-feature after-cost native FreqAI models, 100 same-model full-versus-as-of-prefix comparisons, zero feature/prediction/`do_predict`/DI/model-hash mismatches**. An **experimental opt-in 12×5m internal validation embargo** excluded **45** crossing train rows across 25 models, left **zero boundary violations** in that experiment and repeated **100/100** invariant prefix checks. This has **not** been installed into the original full **72-feature** FreqAI strategy or validated against all correlation/informative timeframes. Independent [execution/funding audit](scripts/m2r_execution_funding_quality_audit.py) on already-seen Sept–October found **208/3,375 funding events above the flat 1-bp funding reserve**, max **18.5769 bp**; NO observed bid/ask/fills. Original full-stack `has_bias=Yes` persists, cost/fill gate NO-GO, and **new May–August portfolio backtests are NOT RUN**.

- [x] **Real 25-pair native 4-feature after-cost fixed-model as-of prefix test**, 100/100 forecasts identical; tested separately with **experimental 12-bar internal purge** (45 rows excluded, zero residual boundary violations). Scope carefully limited; evidence is not full strategy acceptance.
- [x] **September–October funding-event and mark/futures data-quality analysis**, showing why 1bp flat funding plus hypothetical slippage reserve cannot substantiate true executable returns.
- [ ] **Test/fix full native FreqAI 72-feature lookahead under frozen model identifiers and as-of correlation/1h inputs, and integrate audited internal purge in a separate research route**; cost/funding and owner release gates MUST still pass before untouched May–August backtests.

**NEW OCTOBER 17 ORIGINAL FULL-FEATURE AI INTEGRITY CHECK — VERIFIED, LIMITED SCOPE:** The [real 25-pair original-price FreqAI frozen-model audit](evidence/m2r/2026-10-17-original-72feature-fixed-model-audit.md) used Freqtrade 2026.9 native feature generation (**5m + 1h + BTC correlation, 14/28 periods, one shifted candle, 36 BTC / 72 other-pair features**), original `&-forward_return` label, native `LightGBMRegressor.train/predict` and original `NbotV6` entry/exit formulas. **25 newly fitted then frozen models × 10 Oct 8 2026 five-minute candle-close instants = 250/250 exact as-of feature/forecast/`do_predict`/DI/entry/exit comparisons, zero mismatch and zero changed model hashes.** A broader test initially produced **50 mismatches and 10 changed decisions** by erroneously treating the 5m **open** instead of 5m **close** as decision time at `HH:55`; native Freqtrade informative-merge code intentionally makes hourly `HH:00` data available at `HH:55` 5m bar **close**, when both candles complete. After correcting the audit-only cutoff, **zero mismatches** in all 250 checks. Preserved both failed and passing raw outputs with hashes.

**NO release implication:** prior official full-engine `has_bias=Yes` remains, because its shortened replays retrain models; the experiment fitted new ephemeral models once and injected their frozen predictions into original signal functions, it did **not** replay identical saved model artifacts through the full engine. Native internal 80/20 split remains unembargoed in this original model test; execution/funding and strategy economics remain unresolved. **M2 NO-GO; May–August model-performance comparisons NOT RUN; no M3/M4/M5A/M7 activation.**

- [x] **Original 25-market 36/72-feature 5m+1h+BTC-correlated native FreqAI same-model as-of checks, 250 exact five-minute candle-close decisions**, 0 features/predictions/gates/signals/model-hash differences. Audited intermediate 5m-open vs close harness confounder; formal full-engine warning NOT cleared.
- [ ] **Reproduce original full-engine inference with immutable saved native model bundles through single-pair replay and certified internal purge.** The above fresh-fit frozen-model/strategy-hook check is not this final release gate.

**LATEST OCTOBER 17 — actual native full-engine saved model replay AND purged train split (executed):** [Detailed VPS proof and limits](evidence/m2r/2026-10-17-native-saved-model-purge-event-funded-research.md). **25 original raw-price models** were trained once with a separate [12×5m native internal embargo model](user_data/freqaimodels/NbotV6PurgedLightGBMRegressor.py), saving complete fitted on-disk binaries and native pipelines. **300 total 12-candle-overlap rows purged** across 25 raw-price fits, 0 allowed cutoff overlaps. The complete Freqtrade two-day 25-market engine test ran **7 simulated trades, −28.799 USDT**. A shorter one-day native-engine replay reused all **25 exact model files without retraining**; [assertion script](scripts/m2r_native_model_replay_assert.py) verified **25/25 identical binary hashes and all 7,200 overlapping five-minute FreqAI predictions identical**. This is **strong evidence on the sampled full-engine lifecycle**, but the original official `lookahead-analysis` still says `has_bias=Yes` (it purges model directories/retrains); don't claim the warning cleared or native unbiased certification.

**Training improvement ready for research only:** model is **opt-in** with research-only backtest guards; the sparse-label-funded challenger revealed that zero rows removed can be correct if an existing >1h gap already guarantees safe labels. Native model now accepts zero removals **only after strict timestamp proof**; new clean v2 identifier BTC removed 0, ETH 1, saved both valid fitted model binaries. All original default/strategy/approval gates unchanged.

**Trading cost improvement implemented but real-fill gate remains blocked:** Added event-aware **signed, per-market historical funding** supervised targets and [25-market audit](scripts/m2r_event_funding_label_audit.py): **7,732 overlapping hypothetical Oct 8–15 opportunities, 2,563 positive under constant 1bp funding vs 2,605 with event-dependent funding, 53 ambiguous funding/exit boundaries**. The separate [funding-aware research challenger](user_data/strategies/NbotV6TradeOutcomeFundingResearch.py) with the native 12-bar purge completed a 25-pair two-day native-engine backtest: **24 simulated trades, +39.085 USDT**; short previously inspected window, does **not** prove performance after unobserved slippage and stop fills. No real bid/ask or precise settlement mark/fill receipt in historical candles, so **M2 cost gate still NO-GO**. A matched original **unpurged** 25-market native control was launched but its result is **UNVERIFIED** after owner Windows desktop relay became unresponsive; check existing bounded run on V6 VPS rather than claiming completion.

- [x] **Native full-engine saved-model fixed-weight rerun, 25 frozen joblibs and 7,200 identical overlapping forecasts**, run both 2-day and 1-day timeranges; no retraining on second run. Original `has_bias=Yes` remains open.
- [x] **Opt-in native 12-bar internal embargo for original and sparse after-cost LightGBM training**, actual 25+2 market runs and regression tests; does NOT silently change original strategy.
- [x] **Signed event-funded after-cost labels and strict historical research challenger**, 25-market funding/mark audit and separate native engine training. Exact live bid/ask/slippage and stop-fill gate **not** passed.
- [ ] Independently close official lookahead-analysis FreqAI refit warning, obtain defensible real fill/spread costs, and evaluate preregistered May–August windows on unseen samples. M2 NO-GO; paper/live inactive.

**LATEST OCTOBER 17 — VERIFIED NATIVE COST STRESS:** Interrupted original unpurged 25-pair control completed: **13 trades −33.762866 USDT** in Oct 8–9, versus native original internally purged **7 trades −28.799423** and native funded aftercost internally purged **24 trades +39.085015**; NO TRADE **0**. Historical 25-pair one-position Freqtrade control ZIPs. Funding-aware small-period gain is entirely reversed by **+20bps** hypothetical extra roundtrip execution charge (**−8.885390 USDT**) and **+25bps** (**−20.877991**); breakeven **+16.2955bps**. Full [date-scoped actual-engine cost stress evidence](evidence/m2r/2026-10-17-native-three-way-matched-cost-stress.md). **Do not declare actual measured bid/ask/slippage/stop or precise funding paid; not observed.** 25-model/7,200-sample native saved replay PASS limited; gated native research-only internal 12-candle purge PASS; official Freqtrade lookahead still `has_bias=Yes`, real fill gate NO-GO, M2 NO-GO. No release or Jan May–August backtest.

**NEW OCTOBER 17 — IMMUTABLE NATIVE FREQAI LOOKAHEAD TERMINAL ROW ROOT CAUSE ISOLATED IN SAMPLED THREE TRADES:** The owner-authorized VPS executed a bounded *stock Freqtrade 2026.9 lookahead* with all **25 native saved original-price-model binaries preserved**, no retraining, and only model-deleting `rmtree` suppressed inside a separate scratch identifier. Official output **STILL `has_bias=Yes`**, **three analyzed historical trades**, **zero falsely flagged entry/exit trade events**, indicator columns `&-forward_return`, mean, std, `do_predict`, DI, `exit_short`. Native complete-indicator comparisons (**3 entries and 3 exits**) were **identical at EVERY row through the actual decision candle**; **all six differed only at the *one subsequent terminal candle***, where shortened FreqAI prediction was missing and `fill_predictions` zero-filled it. Diagnostic 5m padding moved the zero to the new terminal row, not to past decisions. [Fail-closed decision verifier](scripts/m2r_verify_native_decision_boundary.py) exit 0; **stock warning is NOT removed**, and an eight-signal extended trace did NOT pass due to separate experimental wrapper schema compare; do not claim universal unbiasedness. [Evidence](evidence/m2r/2026-10-17-immutable-model-lookahead-terminal-cost-ledger.md).

**Step 3 actual saved-engine funding/fee ledger DONE; actual-execution certification still NO-GO:** A new [24-trade historical native backtest funding ledger](scripts/m2r_native_trade_funding_ledger.py) verified **24 trades across 10 coins**, Freqtrade modeled fee math **23.981704 USDT**, Freqtrade modeled funding income **+0.09019117 USDT** vs public historical signed funding/previous completed mark proxy estimated paid **−0.09020991 USDT** (max disagreement **0.00001874 USDT**). **3** funding events in filled simulations, **1** ambiguous exit-at-settlement, **3** simulated stop losses, **24/24** entries at public 5m *open* (a backtest convention, not actual bid/ask). Earlier extra +20bps roundtrip execution stress takes two-day challenger to **−8.88539 USDT**. No historical executable bid/ask, real stop fill, order-book liquidity or actual settlement receipts are available; owner cannot claim Step 3 fully verified in actual venue conditions. **M2 NO-GO**, no model replacement, no paper/live, no Jan May–Aug model generalization run.

### Build checklist — distinguish code existence from earned approval

**Stage A — Frozen candidate setups + after-cost outcome labels (implement offline first)**
- [x] Define causal breakout and EMA pullback **LONG/SHORT** as four frozen setups with past-only indicators; hypothetical entry at **next 5-minute OPEN**. Implemented in [research opportunity library](user_data/strategies/nbot_trade_outcome.py).
- [x] Label every historical setup including rejected/unexecuted choices: 12-bar 60-minute horizon, 2% stop/5% target, adverse gap open, stop-first intrabar, **0.05% exchange fee + 0.05% extra slippage each side + 0.01% conservative funding reserve** (0.21% modeled roundtrip), all labeled **assumptions**, not observed Binance fills. [M2R explanation](M2R_RESEARCH.md).
- [x] Keep future outcomes solely in FreqAI `&-trade_net_return` training label, never a `%-` feature; missing/nonsetup/final-horizon outcomes are **NaN**. Offline [purged chronological split](scripts/m2r_purged_split.py) removes training samples whose trade exits enter the future test window.
- [ ] Independently certify the **actual FreqAI rolling train/test boundary purge**, all-pair model lookahead and realistic fill/stop accounting. The offline split tool is **not automatically integrated** into FreqAI's training internals.

- [x] **Static FreqAI 2026.9 outer-cutoff source review** (not runtime certification): upstream historical path truncates to `date < train.stop` **before** invoking V6 12-candle target calculation; NBOT leaves the last 12 bars NaN; upstream label filter discards NaNs. [Source audit](evidence/m2r/2026-10-17-native-cutoff-source-audit.md); [new boundary/counterexample tests](tests/test_m2r_native_cutoff_contract.py). Static inspection found a **separate UNPURGED 80/20 internal split boundary**; internal validation metrics cannot be treated as purged. This narrows but **does not close** the native/runtime/leakage check; previous official `has_bias=Yes` persists.
- [ ] **Run installed-image runtime boundary/prediction invariance proof** and isolate `has_bias=Yes` changing `do_predict`/decision columns; check internal 12-candle train/validation embargo rather than silently altering the frozen benchmark. **BLOCKED (updated retry)**: saved PuTTY `8GB-Observation` session now has a matching cached host key but batch SSH still refuses an interactive authentication prompt; a configured private key exists and Pageant is not running. Owner must locally complete/unlock authentication; no credentials should be sent here. Still **no authenticated VPS access**, no new model data or history verified.
- [x] **Pre-register calendar-based May/June/July/August 2026 research dates and frozen 30/60/90/180-day comparisons before viewing their outcomes**, with current original AI/non-AI/matched controls, NO TRADE and costs. **Protocol recorded; tests/data NOT RUN**: [multi-window protocol](evidence/m2r/2026-10-17-january-history-multiwindow-preregistration.md).

- [x] Add [after-cost/exit/router tests](tests/test_m2r_trade_learning.py) and [split tests](tests/test_m2r_purged_split.py), covering stop-first, next open, fee/funding/slippage, invalid data, trailing missing labels, historical model safety, market regimes and no-trade fallback. Unit tests exercise code contracts only.

**Stage B — After-cost LightGBM Challenger (research only)**
- [x] Keep original `NbotV6` and `NbotV6NoML` unchanged; introduce [historical-only after-cost LightGBM Challenger](user_data/strategies/NbotV6TradeOutcomeResearch.py) and [separate no-key FreqAI config](user_data/config.m2r-trade-outcome.json). Code rejects paper/live startup, has 2% stop, 5% ROI target and approximated 12-candle time exit.
- [x] Run **real official Freqtrade BTC-only FreqAI smoke** on Oct 1–8 (already-inspected data). Training/strategy load **exit 0**; one simulated BTC trade **−1.104 USDT**, holding **60 minutes**. This is only a technical proof, NOT model edge or M3.
- [x] **Actually run official full-25 Freqtrade comparisons**: September 1–30 after-cost AI **−442.471 USDT / 332 trades** vs original AI **−444.980** and original no-ML **−242.894**; October 8–15 after-cost combined **+113.046**, breakout **+62.552**, pullback **+146.237**, original price AI **+205.976**, original no-ML **+24.135**, NO TRADE **0**. [Predeclared Oct comparison](evidence/m2r/2026-10-17-preregistered-setup-comparison.md) and [official trade evidence](evidence/m2r/2026-10-17-oct08-16-eight-strategy-official-backtests.json). Original strategies have different exits; **three new no-ML matched 60min/2%/5% exit controls** make like-for-like setup selection tests possible (all three matched no-ML controls lost). Fees remain simulated; actual execution costs unproved.
- [x] **No-promote decision applied:** after-cost AI lost full September, did not beat original price AI in Oct 8–15, and its October combined +113.046-USDT base result fell to **+15.112** under extra 10bps hypothetical roundtrip costs and **−33.855** under extra 15bps. Breakout went negative at extra 10bps; pullback went negative at extra 25bps. **Do not authorize trading or automatic model replacement.** [Cost sensitivity](evidence/m2r/2026-10-17-oct08-16-full-cost-sensitivity.json).

**Stage C — Bounded strategy selection / regime routing (do not activate early)**
- [x] Freeze four candidate setup labels (breakout/pullback × LONG/SHORT), no auto-invented strategy code. The [September all-25 offline audit](evidence/m2r/2026-10-17-september-all25-opportunity-labels.json) found **29,033 hypothetical setup outcomes** across 216,000 market candles; only **32.332%** positive after assumptions, mean hypothetical net **−0.246% per overlapping opportunity**. These are not portfolio trades/returns.
- [x] **Train and score candidate-specific models** with isolated identifiers: [NbotV6BreakoutResearch and NbotV6PullbackResearch](user_data/strategies/NbotV6FamilyResearch.py) used their own historical after-cost examples on the Oct 8–15 chronological test. Heldout forecast checks: breakout **235 favored of 4,295 eligible** (43.404% after-cost positive vs 34.109% raw), pullback **154 of 3,437** (44.156% vs 31.946% raw), combined **302 of 7,732** (45.364% vs 33.148% raw). These are **overlapping hypothetical signals, not actual portfolio fills**. [Model selection audit](evidence/m2r/2026-10-17-aftercost-model-learning-results.md).
- [ ] Validate separate candidate models on **multiple additional untouched dates/market regimes**, check native FreqAI cutoff purging and independent observed execution costs. Eight days is not enough to certify a stable model.
- [x] Code an [offline deterministic research-only router](user_data/strategies/nbot_strategy_router.py) accepting **externally provided, as-of predicted** after-cost scores. It checks known candidate names, current optional market regime (up/down/range), risk/uncertainty, model age, liquidity and extra cost stress; returns **one** candidate or **NO TRADE**, never an actual order.
- [ ] Connect only **approved candidate-specific models** to any runtime router after separate M2/M3 validation; nothing here auto-switches live or paper positions.
- [x] Test multiple candidate rankings, zero-qualified NO TRADE, stale/unready model, NaNs, insufficient liquidity, unfavorable stress, sideways regime and opposing regime/direction; router has no Freqtrade order placement, model replacement or promotion permissions.
- [ ] Only after separate multi-regime forward tests can governance consider promoting a Champion, with owner-controlled rollback; default is **NO TRADE** on uncertainty or failure.

**Non-negotiable existing safety gates**
- [ ] Resolve the M2 FreqAI `has_bias=Yes` lookahead-diagnostic differences and historical order execution/slippage limitations, including September's two ~0.10-USDT funding exit exceptions. Offline feature and model-prefix checks help but do not clear all warning columns.
- [ ] After M2 acceptance, conduct M3 *genuine* independent chronological walk-forward tests with realistic extra costs and confidence intervals. September 2026, Oct 1–7 and now **Oct 8–15 2026** have been inspected; **none can be silently reused as a fresh blind final test after design changes**.
- [ ] **M5A intelligent universe selector:** still must sample markets every **8 hours**, find up to **25** eligible/fundable/liquid candidates with model-history readiness, limit churn, and protect open positions. The existing fixed 25-coin comparison does **not** substitute for this.
- [ ] **M4 virtual paper up to 20 positions:** source-level future paper configuration already exists but is **not commissioned**. A 20-slot cap refers to paper-research **only**; real-money one-position lock remains.
- [ ] **M7 live funds:** **LOCKED**, requiring separate explicit owner approval, independent M2–M6 quality and safety evidence, and no changes to legacy V5 VPSes.

**Evidence and state:** [M2R_RESEARCH.md](M2R_RESEARCH.md) and [the final first-round research report](evidence/m2r/2026-10-17-aftercost-model-learning-results.md) document all-25 **125-fit September after-cost AI** (332 trades, **−442.471 USDT**), and **predeclared October 8–15** full-25 combined, breakout and pullback LightGBM runs with matched one-hour non-ML controls and frozen NO TRADE. Forecasts improved the hypothetical hit rate in that short period, but **the original price-only AI earned more simulated USDT**, costs can erase new-model gains, and **M2 release NO-GO** remains. The offline router is NOT connected to a trading service and M3 multi-regime validation has NOT begun.

### Acceptance checkpoints
**A code written + unit tests pass ≠ model trained ≠ historical profits ≠ accepted trading system.** Every implementation must be compared against non-ML and NO TRADE, with explicit funding, trading-cost and lookahead limitations. It is acceptable—and scientifically important—to conclude "no edge; NO TRADE."

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
- [x] **M2: Full historical research assessment run; conclusion NO-GO** — one-week baseline, true funding, depth quality, execution stress, 50,400 original AI decisions and BTC/ETH as-of invariance reviewed. **This ticks assessment completion, NOT release acceptance.**
- [ ] **M2 release/quality acceptance** — blocked by missing historical bid/ask/fill proof, unexplained official AI `has_bias=Yes` warning, and no proven after-cost trading edge.
- [ ] **M3: Credible FreqAI improvement** — untouched multiple-regime walk-forward and cost-adjusted model attribution not established.
- [ ] **M4: 20-slot simulated research forward trial** — configuration **exists**; independent VPS daemon/restarts/position safety not yet approved or tested.
- [ ] **M5A: Eight-hour intelligent 25-candidate universe selector** — **not built**; ranking, liquidity, churn caps, BTC anchoring, history/model readiness, open-trade protection and replay acceptance still required. A 25-coin fixed history test does NOT replace the selector.
- [ ] **M6: Approved-model governance** — shared model version qualification/rollback not built.
- [ ] **M7: Any live funds** — explicitly **LOCKED**; owner-only code-staged release hook is not deployment approval.

### OCTOBER 17 LATEST — actual 25-market 30/60/90/180-day August native learning comparison COMPLETED

- [x] **Completed bounded initial four-lookback research experiment**, explicitly **NOT full May–August independent multi-month acceptance**: actual native Freqtrade 2026.9 one-week **Aug 1–8 2026** historical backtests, exact **25 fixed markets × 4 time windows = 100/100 fitted native models, 100/100 safe 12-candle internal split-purge logs with 0 boundary overlap**, same funded-aftercost LightGBM strategy/parameters/fees, 1× and single $1,000 simulated trade max. All runs exited 0. [Complete dated reproducible results](evidence/m2r/2026-10-17-august-25pair-four-lookback-results.md).
- [x] **Cross-window real archive results audited**: 30-day **28 trades −39.976652 USDT**; 60-day **27 trades −21.427845**; 90-day **23 trades −79.701474**; 180-day **10 trades −19.463025**. **NO TRADE = 0 beats every version**. Additional **+25bps round-trip hypothetical execution costs** yield **−109.955250 / −88.913681 / −137.183390 / −44.456832 USDT**, respectively. More training time did not show a robust positive net edge in this inspected week.
- [ ] **FULL pre-registered May–August monthly / weekly retrained multiwindow benchmark and all matched controls remain pending**. One inspected August week cannot decide 30/60/90/180 winner; May/June 180day is not eligible from January history. Do not change model/entry rules based on this week. Official lookahead `has_bias=Yes` and unobserved executable bid/ask/stops/settlement still block M2 release. **Owner explicitly ordered: PAPER TRADING ON HOLD for this extra historical experiment.** No paper daemon started or model promoted; M2 NO-GO, M3 not formally started, M7 LOCKED.

### OCTOBER 17 OWNER-APPROVED FULL JAN–SEP + HISTORICAL UNIVERSE TWO-STAGE LONG-RUN — IN PROGRESS, RESULTS NOT YET AVAILABLE


- [x] **VERIFIED recovered operational status, 2026-10-17 16:26:49 UTC:** Fixed second `set -euo pipefail` research-runner bug: absent 60/90/180 model output folders were causing `find ... | wc -l` to abort the guarded safe recovery despite the completed native 30d archive. V6 research-only commit `1c264dcf69eef7ff0a9783d90fd0f74224738be2` checks the existence of each folder before counting. Pulled on clean isolated V6 VPS; dry-run `bash scripts/m2r_jansep_research_runner.sh --status` exited 0 after printing verified 30d native models and NEXT 60d = 0/725. `bash scripts/m2r_jansep_vps_safe_restart_once.sh` then exited 0, audited 30d native ZIP, started distinct finite **`nbot-v6-jansep26-retryonce-20261017.service`**. Separately independently verified **active/running** systemd PID 102374, exactly one running Freqtrade Docker id `e8778f620d9e`, and `w60/run-state.txt` `STARTED_UTC=2026-10-17T16:26:18Z`, first 60d BTC fit logged `boundary_violations=0`, models 60d plan 25×29 = **725**. **60d research is now RUNNING; 90d and 180d are still QUEUED and not executed; stage2 not yet executed**. NO second Docker, paper/live, keys, model promotion or V5/main changes. Server-side unit runs independently of this chat while VPS remains online but not across reboot; the owner deleted the ChatGPT scheduled checker (do not recreate). [Full verified recovery, Freqtrade ledger, costs, exact commands](evidence/m2r/2026-10-17-30day-audited-and-vps-60day-restart-verified.md).
- [x] **30d first complete historical economic audit PASSED:** original saved 825 FreqAI LightGBM models, Freqtrade 25-coin historical Feb15–Sep30, **1,930 simulated 1x $1000 trades, −2,311.594335 USDT after engine fees/funding, max drawdown 2,346.179218 USDT**. Native ZIP/model/trade/cost auditor exited 0 and saved `jansep-native-30day-only-audit.json` on authorized V6 VPS. Additional **hypothetical** +10/+15/+25 bps roundtrip cost stress: **−4,240.161941/−5,204.445743/−7,133.013349 USDT** vs NO TRADE 0. Only **493/825** training split purge checks were retained in original truncated SSH stdout, zero boundary violations among 493, **332 not independently logged**. This is an economic loser in that interval, **not** proof no other training period or market regime can work. Release remains M2 NO-GO.


- [x] **Latest Oct 17 15:47 UTC native 30-day original result and finite-automation failure:** Exact native Freqtrade ZIP has **825 fitted models, 1,930 simulated 1× $1,000 trades, net −2,311.5943346 USDT, native max drawdown 2,346.17921763 USDT** over Feb15–Sep30 2026; zip CRC valid, 25 markets, one global slot. Only **493/825** FreqAI inner label-purge fit checks captured in original truncated SSH stdout, zero observed boundary violations, **332 fit logs NOT independently verified**; extra costs and full trade ledger audit still needed. This result is already worse than NO TRADE 0 without extra cost. **The original finite VPS research systemd supervisor FAILED at 15:23 UTC on broken Bash parser**, leaving 60/90/180 models/trades at zero and Stage2 not started; **do not claim autonomous jobs still running**. Root cause corrupted historical research shell-script contents, not model-failure. Rebuilt source-only runner/coordinator and native auditor in GitHub plus Bash CI test; first repaired CI passed, but **the owner laptop SSH relay stopped responding**, so **GitHub fixes NOT yet confirmed pulled/deployed on VPS**, and no replacement service verified started. Guarded owner-approved manual recovery entrypoint: `scripts/m2r_jansep_vps_safe_restart_once.sh`; inspect Docker (must be idle) and original failed unit, `git pull --ff-only` research branch, then `bash scripts/m2r_jansep_vps_safe_restart_once.sh`. Checks 30d native ZIP and full 30d auditor BEFORE a *new finite* research-only VPS systemd service starts 60/90/180 sequentially. Read [full latest 30d proof and stop reason](evidence/m2r/2026-10-17-30day-native-long-history-automation-blocker.md). The owner **deleted the ChatGPT hourly reminder**; do NOT create a new ChatGPT task. M2 NO-GO, PAPER OFF, LIVE LOCKED.

- [x] **Owner's no-chat-limit dependency requirement (Oct 17, 14:02 UTC):** User **deleted the ChatGPT scheduled checking task** (do not recreate it) and requested GitHub handoff continuity. V6-only **finite one-shot VPS systemd research coordinator** `nbot-v6-jansep26-historical.service` independently verified ACTIVE, initially WAITING for the existing 30-day Docker run rather than competing with it. Bootstrap and logs are V6-only `/root/nbot-v6-m1-20261016/jansep-20261017/vps-research-bootstrap.{sh,log}`; after original research container ends, the service fast-forwards this authorized branch, syntax-checks, and invokes [safe finite offline coordinator](scripts/m2r_jansep_vps_sequential_coordinator.sh) to recover/resume the current model cache and run the remaining 60/90/180-day tests, native ZIP audit, historical S3 symbol inventory and restricted fixed-25 as-of selector diagnostics. Unlike a ChatGPT reminder it does not require the chat or Windows SSH client to stay connected; **NOT persistent across VPS reboot** and HALTS on unknown Docker/Git/model failures. **DO NOT CALL THIS A TRADING DAEMON OR A COMPLETED TEST**. Read the [new complete VPS continuation runbook](evidence/m2r/2026-10-17-vps-finite-research-continuation-handoff.md).
- [ ] **Latest physical native progress checkpoint at Oct 17 14:01 UTC:** **510/825 30-day research model binary fits saved**, 0 full-period native portfolio ZIPs, all remaining 60/90/180 long-period windows NOT completed; Stage 2 pending. Original laptop-connected launcher session disappeared without an EXIT_CODE marker while its Docker process kept running (preserve all saved fitted models; native archive-orphan reconciliation specifically required). The completed 825/825 and profit results must be independently certified after the native ZIP exists. Stage 2 complete broad-market matched Freqtrade economic comparison is still BLOCKED by lack of historical alternative symbol contract and real fill data: the systemd finite job can only complete **archive metadata + original-25 as-of diagnostic**, never pretend the full economic selector is done.

- [x] **Authorized offline research only**, explicitly keep PAPER and LIVE OFF. [Frozen two-stage methodology](evidence/m2r/2026-10-17-jansep-full-history-two-stage-protocol.md) distinguishes 30-day Feb15, 60-day Mar15, 90-day Apr15, 180-day Jul15 valid beginnings (2026 UTC), with 7-day rolling FreqAI fits and identical 25 fixed coins, risk controls, costs, 12×5m research-only split embargo. Shared Jul15–Sep30 comparison required before identifying better lookback. Previously inspected September/August remains replication, not untouched holdout. No January 1 profitable trades are asserted without earlier warmup.
- [ ] **Native 30-day rolling Feb15–Sep30 job running on V6-only VPS** in `/root/nbot-v6-m1-20261016/jansep-20261017/w30`, using one bounded Freqtrade 2026.9 Docker; plans **25 pairs × 33 weekly model fits = 825 model fits**. Only a partial working training log is available so far; **no full native portfolio ZIP, PnL or completed Jan–Sep benchmark exists yet**. Later 60/90/180 7-day rolling jobs are staged/config parity checked, NOT executed. Historical results validator [`scripts/m2r_jansep_native_rolling_audit.py`](scripts/m2r_jansep_native_rolling_audit.py) fails on incomplete artifacts. [Fail-closed one-shot next-window runner](scripts/m2r_jansep_research_runner.sh) handles bounded saved-model timeout/resume without model deletion or unattended trading. **Superseded:** owner deleted that ChatGPT hourly checking task. A separate finite VPS-only research coordinator was instead verified active at 14:02 UTC; see newest bullets and runbook.
- [ ] **Stage 2 broad-market real historical selector remains unexecuted.** [Read-only Binance Vision USDT-M historical archive directory inventory](scripts/m2r_binance_historical_universe_inventory.py) can potentially discover delisted candidate symbols using monthly S3 ZIP keys, without hindsight Oct-only whitelists. [Twenty-five-symbol 8h strict as-of liquidity-rank diagnostic](scripts/m2r_asof_25market_selector_diagnostic.py) can run on existing public 1h files. **The existing archive is exactly 25 symbols, so selecting a new top25 from it is the SAME fixed universe by construction**. An actual historically qualified all-market pool, historical spreads and a matched FreqAI rotated-25 economic test are still not proven: do not fabricate improvement. All stages remain **M2 NO-GO, M3 not approved, M4 paper ON HOLD, M5A uncommissioned, M7 LIVE LOCKED**.

## G. Progress ledger — 2026-10-17

| Milestone | State | Required next proof |
|---|---|---|
| M0 clean tree | COMPLETE — source isolation only | Clean-tree commit 3e642508; V6 CI run 38906351380 passed both jobs (offline + official strategy discovery) |
| M1 real FreqAI backtest | **TECHNICAL COMPLETE**: 25/25 full-history fit + independent 7-day 34-trade backtest; **-135.64 USDT** | M2 fee/spread/funding/slippage baseline, M3 broader held-out replay; no deployment |
| M2 honest baseline | **RESEARCH EXTENDED TO ALL SEPTEMBER — NO-GO; ACCEPTANCE FAILED**. Sep: **125 actual LightGBM fits**, AI 137 trades **−444.980 USDT**, no-ML 163 trades **−242.894 USDT**, no-trade **0**; both worse after doubled fees; no-ML in a position **99.641%** of month. Prior Oct-week checks and 65-trade funding/depth evidence retained | **BLOCKERS:** no precise historical executable bid/ask fills (October depth had 17/130 stale), official `has_bias=Yes` AI warning, two Sep month-boundary funding differences, no proven edge. Do not advance M3/M4 |
| M2R after-cost AI + strategy router (offline) | **SOURCE + SEPT/OCT 25-PAIR AFTER-COST COMPARISONS + JAN HISTORY ARCHIVE AUDIT COMPLETE, NOT ACCEPTED**. Four setup labels, 29,033 Sept hypothetical outcomes, LightGBM BTC 1 trade −1.104 USDT, fail-closed offline regime router and purged split tests. | Train candidate-specific validated models, audit FreqAI label boundary, full after-cost holdouts and M2 leak/fill fixes; NO PAPER/LIVE |
| M3 FreqAI edge | NOT STARTED | Multi-period walk-forward results |
| M4 forward dry-run VPS | NOT STARTED; research mode source implemented | Capacity, two-profile official checks, independent forward-paper report |
| M5 expand and port selected features | DEFERRED | M3/M4 evidence |
| M5A universe selection/rotation | SELECTOR NOT BUILT; offline history bootstrap coded | Market screening, scientific selector validation, model readiness and safe activation still missing |
| M6 lightweight model governance | DEFERRED | Demonstrated need |
| Owner-only live release hook | CODE STAGED; NOT EXECUTED | Native framework smoke + private-file/Telegram/risk tests; M7 acceptance still required |
| M7 any live money | LOCKED | Separate user-approved risk plan |

**Current priority: M2 NO-GO REMEDIATION. The assessment has been completed honestly, but the M2 technical/market-integrity gate FAILED. Before M3, resolve the AI diagnostic differences, secure a defensible prospective fill-cost method and prove why a candidate approach could beat NO TRADE. M5A eight-hour universe selector and the up-to-20-position M4 paper-research mode remain explicitly REQUIRED but INACTIVE. No persistent VPS trading, V5 changes, default-branch merge or live-money permission is authorized.**
