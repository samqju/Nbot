# NBOT V7 — Frozen Comparative Opportunity Learning Roadmap

**Roadmap version:** V7.0 / 2026-10-19  
**Status:** OWNER-APPROVED DESIGN FREEZE — planning only; NO V7 training, paper, or live deployment authorized by this document  
**Branch:** `roadmap/v7-comparative-learning-20261019`  
**Parent source:** `prototype/v6-freqtrade-freqai-20261016` (preserved unchanged)  
**Primary lesson:** Compare *all eligible opportunities* at a common decision time; execute only those with demonstrable positive risk-adjusted, after-cost portfolio value.

> **V7 operating principle:** Broadly observe, selectively simulate, learn comparatively, decide with one capital-aware portfolio. **NO TRADE is always valid.** Claims of profitable AI require truly unseen, after-cost, capital-constrained evidence.

## 0. Scope, source of truth, and strict freeze

1. This branch is **documentation-only at inception**. Do not restart VPS processes, change exchange credentials, change V5/V6 deployments, merge V6 PRs, arm dry-run, or place real orders.
2. Treat existing V3, V4, V5 and V6 documents, tests, scripts, and archived historical results as **prior evidence to audit and reuse**; never overwrite their provenance, hashes, original economic conclusions or runtime safety controls.
3. Freeze failed exit-policy experimentation. **The exact +1% activation / 1%-point step trailing rule was tested and did not rescue V6.** Its results are a *negative research control*, not an automatically adopted V7 live exit. For V7, choose a single versioned evaluation exit policy **in advance** on development data and keep it fixed across comparator arms. An independently prespecified alternative exit policy requires a distinct holdout, not a search on already-viewed dates.
4. Previously inspected **July–September 2026 are development/exploration, not a pristine unseen validation set.** A calendar third month is only a true holdout if it and its outcomes have not influenced any prior design/selection decision; otherwise obtain a later genuinely untouched period.
5. No daily-profit guarantee (including a 1% daily portfolio target), no retrospective cherry-picked winner, and no paper/live promotion by completion of jobs alone.
6. Track actual implementation states explicitly: `proposed | implemented | tested | economically validated | accepted`. Nothing begins at `accepted`.

## 1. What has already been learned (do not rebuild blindly)

- **V3:** documented broad-market scanning plus an uncapped-by-capital counterfactual replay, with a 20-symbol high-resolution feed cap; preserve independent accepted/rejected outcome treatment and tick/bar-policy distinctions.
- **V4:** documented research outcome memory, asynchronous challenger generations and paper Champion-vs-Challenger gates; reuse concepts only after verifying source and operating behavior.
- **V5:** documented paired exit research, market intelligence and evidence lineage; preserve real-vs-counterfactual accounting and low-resource, fail-closed controls.
- **V6:** implemented 25-coin × 8-family global candidate labeling/forecasting and native one-slot integration. Archived global study produced **914,878 labeled candidates** yet made **ZERO trades across four windows** because all were rejected. This refutes the simplified claim that V6 simulated only one candidate; the actual diagnosed issue involves weak underlying entry economics and selection/calibration/risk-gate design.
- **V6 exit evidence:** the exact +1% activation trailing policy completed 8/8 native family studies; 0/8 profitable and 8/8 worse than the previous trailing variant. All eight original strategy families also failed robust positive after-cost tests.
- **V6 universe evidence:** a 75-market historical M5A proxy comparison did not establish a stable benefit for rotating market-quality universes. Do not assume liquidity/volatility ranking predicts directional entry payoff.
- **V6 technical blockers:** first-week AI lookahead analysis flagged differences, and historical execution spread/queue/slippage could not be fully proven. Do not silently mark these resolved.

The audited references and evidence-status table live in [V7_LEGACY_EVIDENCE_LEDGER.md](V7_LEGACY_EVIDENCE_LEDGER.md).

## 2. V7 architecture — five separately testable decisions

**A. Market intelligence:** observe every historically eligible Binance USD-M **USDT-settled perpetual** contract using lightweight, no-order broad scanning.

**B. Universe selector:** at a scheduled review (initial research default: **every 8 hours**, subject to predeclared testing), rank a **capacity of 20 model-/data-ready candidate symbols**. Zero changes and fewer than 20 are valid. Require liquidity, sufficient history, historical listing, mark/funding coverage, risk eligibility and hysteresis; do not force turnover or trade.

**C. Entry/opportunity generator:** test **10–15 genuinely distinct strategy families** (trend, breakout, reversion, pullback, range, relative strength, volatility, etc.). Strategies emit LONG/SHORT/NO SIGNAL. Existing eight V6 families are retained as *negative controls* and potential code assets, **not promoted winning signals**. Admit each new family only after disjointness, causal-signal and after-cost checks.

**D. Parallel shadow laboratory:** independently simulate **every valid candidate entry across all 20 pairs, sides and strategies**; do not cap research labels by the number of real positions. Maintain a sampled, point-in-time eligible *out-of-universe control* to detect missed superior opportunities. Multiple overlapping independent hypotheses are allowed in research; they are not jointly executable portfolio profits.

**E. AI opportunity ranker + portfolio decision:** score comparable **expected net after-cost payoff distributions, downside, capital occupation and uncertainty**. Rank simultaneous opportunities by economic usefulness given cash, margin, exposure and current positions; select the best *or NO TRADE*. Evaluate actual selected trades with **one global concurrent slot initially**. Never select the hindsight-best candidate during model evaluation.

The V7 paired engines have different truth labels:
- **Counterfactual/virtual research ledger:** what a frozen entry/exit policy could have done, with explicit fill uncertainty.
- **Paper/real execution ledger:** what the constrained execution policy actually did. Never sum uncapped shadow PnL and call it wallet returns.

## 3. Initial historical data phase: three months, entire eligible exchange

**Goal:** first acquire a point-in-time market record of *all* USD-M USDT-settled perpetual futures, not only today's surviving contracts. Retrieve exchange-info/listing/delisting histories or mark eligibility unknown when inaccessible. Preserve contract and exchange filter changes where data permits.

Acquire in stages to fit the existing ~**2 vCPU / 8 GiB** VPS:
- Broad level: exchange metadata, timestamped liquidity/turnover proxies, 5m and 1h OHLCV, BTC context, futures mark and funding; partition by coin/time.
- Precise replay: 1m candle and/or verified tick/depth data for the research shortlist/event windows as feasible. Distinguish candle approximations from actual executable bid/ask and stop-fill chronology.
- Integrity: UTC alignment; exchange open/close; delisted/suspended contracts; missing/duplicate intervals; point-in-time availability; funding schedule and timestamps; source URLs/digests; symbol lifecycle; network/time limitations; fee tier assumptions.
- No uncontrolled full-exchange heavy FreqAI training. Lightweight broad scanner first; bounded detailed replay and per-coin model training after readiness.

**Development split:**
- **Month 1:** acquire and inspect market data; engineer candidate strategies and a preliminary as-of universe selector; predeclare policy and economic benchmarks.
- **Month 2:** run the frozen **20-pair independent parallel historical opportunity replay** over all valid signals; collect simultaneous winners, losers, reversals, time-at-risk and rejected-candidate labels; train first causal comparative ranker on matured outcomes only.
- **Month 3:** chronologically replay the full pipeline with models and policy frozen before each decision, using month-appropriate point-in-time universe construction, realistic 1-slot capital constraints and accepted cost assumptions; **only call this a holdout if not previously inspected or used for design.** Otherwise use it for exploratory replication and reserve new future untouched data for promotion.

Three months are a feasibility/prototype dataset, **not enough by themselves** to establish robustness across bull/bear/range/liquidation regimes. Expand to 6–12+ months and new untouched future periods for stronger claims.

## 4. Frozen opportunity outcome contract

At every common completed-candle decision time `t`, materialize an immutable candidate row:
`decision_utc, known_asof_utc, eligible_universe_version, symbol, side, strategy_family_version, feature_schema/hash, signal_id, model_id/fit_cutoff, frozen_exit_policy_id, observed_cost_source, candidate_quality_flags`.

**Never use future prices, later universe membership, later funding, later exchange listings or retrained model fits in features at t.**

After the trade path has fully matured, append a separately keyed **outcome** row:
`signal_id, maturity_utc, shadow_entry/exit_time, conditional_net_pnl_usdt, net_return_pct, fees, funding, modeled_slippage, quote_depth_confidence, MFE, MAE, stop/ROI/time exit reason, intrabar_ambiguity, capital_occupation_duration, source hashes`.

- Label entry/exit using the same predetermined side-aware policy, initial stop, order sizing and fill assumptions. For ambiguous OHLC candles use conservative first-touch or unresolved labels (never favorable hindsight sequencing); finer-data audit overrides only via documented evidence.
- Pairwise comparisons are valid only among **simultaneously eligible** decisions with consistent notional/risk/cost conventions; account for correlated strategies, overlapping labels and different holding periods.
- Include every qualifying trade and all rejected candidates, plus sampled eligible outside-universe pairs with known sampling policy. **No forced 20 entries.**
- Preserve both executed-portfolio PnL and conditional research outcomes, including unresolved/unfillable cases.
- After-cost target must consider **payoff magnitude as well as win probability**. Never impose arbitrary 50% or 75% win-probability gates without measured economic justification.

## 5. Model-learning objective and fair benchmarks

Start with **simple, auditable baselines** before training more powerful models (liquidity-only, fixed universe, momentum, volatility, randomized eligible entry with matched frequency, original V6, and NO TRADE).

First AI model: CPU-appropriate regularized regression / boosted trees / ranking model trained on matured Month-2 opportunity histories, as time coverage permits. No language model makes trade decisions. Track per-family/coin calibration and sample support; avoid pretending a small sample generalizes to a newly listed coin.

Train to predict an **after-cost outcome distribution** and expected marginal value of capital for each candidate; compare *eligible contemporaneous candidates* so the model learns opportunity differences, not just isolated price directions.

Use purged and embargoed chronological validation for overlapping label horizons. Store predictions *before* their outcomes, immutable champion/challenger hashes, feature provenance and promotion receipts. The ranker may abstain; separate whether failure comes from the universe, entry generator, prediction or gate.

**Diagnostics:** top-1/top-k selection uplift vs matched-frequency selectors, regret vs hindsight-best diagnostic ceiling (never live benchmark), calibration, risk-adjusted realized 1-slot after-cost PnL, exposure/turnover, rejected-winner coverage, excluded-universe missed opportunity rate, regime-by-regime performance, drawdown, fee/funding/slippage sensitivity. Benchmark timing and liquidity must be matched.

## 6. Phased rollout with hard promotion gates

| Gate | Stage | Minimum deliverable | Decision |
|---|---|---|---|
| G0 | Legacy audit & freeze | V3–V6 verified reuse inventory, failures, hashes, dependency/risk inventory | No coding new predictor until audit complete |
| G1 | All-market history | Three-month historical eligible contract registry, deterministic downloaded source manifest, integrity/rate/memory audit | Data readiness, *not profitability* |
| G2 | 10–15-family research library | Signal independence checks; controls preserve known V6 losers | Causality and entry-lab eligibility |
| G3 | Month-2 20-pair shadow replay | Every valid selected/rejected entry + sampled excluded-pair controls; matching comparable conditional outcomes | Mature labeled dataset, baseline comparison |
| G4 | Comparative ML training | First champion+simple baselines; frozen features, exit and selection policy; purged splits | Training fit only |
| G5 | Month-3 chronological replay | One-slot native/execution-equivalent results; unseen or explicitly labelled exploratory; cost/risk and lookahead verification | No paper without robust unseen improvement |
| G6 | 20-pair prospective paper/shadow study | Real-time 20-pair scanner; every eligible valid signal shadowed and outcome matured; challenger trained separately | No automatic model replacement |
| G7 | One-active-paper-slot trial | Champion selects ONE eligible trade or NO TRADE; other ~19 remain independently shadowed; compare same-time alternatives | Needs positive forward after-cost portfolio evidence vs controls |
| G8 | Minimal live experiment | Separate owner approval, locked risk/leverage/kill-switch and reconciliation of actual fills vs paper | Never automatic; fail closed |

For **G6**, '20 paper trades' refers to 20 monitored pairs and independent paper/shadow opportunities; it does not require forcing simultaneous positions, funding 20 real slots or allowing account constraints to censor the learning sample. If testing 20 account-paper positions too, record them as a *separate unconstrained research account*, never merge their wallet PnL with the eventual one-slot account.

Before G7/G8 require preregistered objective thresholds (minimum observations/regime coverage, positive net expectancy with uncertainty bounds, no fatal bias, acceptable drawdown, stable costs, independent replay parity), reported as pass/fail with numerical evidence, not an arbitrary claimed win rate. **Insufficient data => NO-GO.**

## 7. Champion/challenger continuous learning after paper starts

1. At each 8h (provisional) universe review, compute point-in-time candidate eligibility. Archive additions, removals, non-replacements and reasons.
2. At each signal decision, freeze *all* eligible pair×family×side candidates with model scores and NO TRADE reasons.
3. Generate virtual/shadow entries for all valid signals independent of actual capital, mature each when observable; save fill-quality and ambiguity diagnostics.
4. Track the single selected paper/live trade separately from every counterfactual; allow one slot to remain occupied until it exits.
5. At a predeclared training interval, fit a **challenger** using only previously matured labels. Do not retrain/promote continuously on currently-open unresolved trades.
6. Compare challenger vs champion using prospective frozen forecasts and new untouched evidence. Promote only after passing gates; retain rollback artifacts and authorization. Continue shadow learning for as long as trading exists.

## 8. Safety and engineering requirements

- **No privileged exchange access** for market-data research, no live order key on research VPS, public scanner and read-only/historical capture isolated from executor.
- All large jobs time-bounded, checkpointed, resumable, with 2 vCPU / 8 GiB memory caps, CPU thread limits, object-level storage/hash manifests, and no concurrent heavy FreqAI jobs; audit disk and data retention.
- Version control universe membership, signals, scores, labels, execution assumptions, and model selection; deterministic replay and reconciliation. Never silently mutate legacy policy files.
- Strict currency units: % move of underlying vs % return on staked equity vs USDT stake/wallet; leverage, maker/taker side, slippage and funding all declared separately.
- Stop simulation must specify **before-activation initial protective stop**, trailing activation/step conventions for LONG and SHORT, bar-close vs intrabar update, same-candle stop ambiguity, worse-than-stop gaps, and fees at both entry and exit.
- Test ranking and execution separately. Reconcile shadow outcomes against native Freqtrade fills and analyze lookahead bias; existing V6 bias warnings remain open until demonstrably resolved.
- Explicit portfolio tests for 1-slot contention, cross-pair correlated exposure, NO TRADE, simultaneous signals, locked capital, reentry timing, exits that free capital, fees, liquidation/insolvency, and stale-data fail-closed mode.
- New strategy/exit/calibration ideas must be *predeclared challengers with new holdouts*, not tuned on the exact same failed/successful month.

## 9. First concrete work items after this branch freeze

1. **Read-only V3–V6 source/evidence inventory**: map code/modules, tests, stable assets and negative findings to V7 component IDs; verify existing 25×8 dataset is reusable rather than rebuild.
2. **All-USDT-M futures archive inventory**: per-symbol listing and source coverage, data volume, 5m/1h vs 1m cost/precision choices, and 3-month manifest; detect survivorship gaps and infeasible price-path labels.
3. **Deterministic common-timestamp 20-of-N selection contract** with sampled excluded candidates and separately frozen 10–15 strategy eligibility.
4. **Cross-sectional learning dataset specification and prototype tests** on older *development-only* windows, including closed-before-training label guarantees.
5. **Pre-register numeric success/failure criteria and holdout**, then run complete one-slot matched native/equivalent comparisons. Evidence determines the next step; do not start paper automatically.

## 10. Explicitly NOT approved

- Assuming V6 never constructed counterfactual labels (it did).
- Declaring V6 or any other prior version economically successful without new evidence.
- Defaulting the disproven tight 1% trail into a profitable V7 policy.
- Training all Binance futures pairs with heavy ML every review cycle.
- Treating all 20 virtual trades as simultaneously investable with one slot.
- Using historical winner hindsight, current survivor listings or already viewed July–September as untested proof.
- Disabling NO TRADE or arbitrarily loosening filters to manufacture trades.
- Auto-upgrading challenger or promoting to paper/live on a technical smoke-test pass.
- Changing V5/main or V6 branch deployments as a side effect of this roadmap.

**Frozen success definition:** A separately versioned V7 universe-selector + comparative AI must make **better capital-constrained, after-cost choices** than preregistered simple alternatives and the V6 baseline on sufficiently broad **genuinely unseen** periods, with risk and execution fidelity verified. Until then this is a scientific roadmap, **not a profitable bot**.

## 11. Mandatory new-chat continuity and per-step handover protocol (owner approved 2026-10-19)

The canonical **living handover** is [V7_CHAT_HANDOVER.md](V7_CHAT_HANDOVER.md), stored and maintained on **this same V7 roadmap branch**. It contains the restart prompt, branch and gate status, full project decision history, prior V3–V6 lessons, current blockers, next actionable G0 work and an append-only chronology.

**Mandatory Definition of Done:** After **every material NBOT V7 discussion/decision, research job, successful or failed test, implementation step, repository modification, change of approval, or handoff**, update the handover in GitHub before claiming the action is fully finished:
1. Refresh the handover's current status, gate, blockers, last verified result and next concrete step.
2. Append a dated journal entry with decision, actual action taken, results including negative/no-go outcomes, source files/artifact digests/commit links, open uncertainties and trading permission state.
3. Commit to `roadmap/v7-comparative-learning-20261019` and verify branch/head/readback. Prefer recording the handover update with the task's artifact commit, otherwise link the two commits.
4. If GitHub update fails, explicitly report it as **uncommitted continuity work** with the pending text. No new chat or assistant may imply auto-sync or successful saving without an actual commit.
5. Preserve historic entries; append corrections instead of deleting earlier decisions. Do not put secrets or credentials into the GitHub handover.

**New-chat initiation:** Read [V7_CHAT_HANDOVER.md](V7_CHAT_HANDOVER.md) FIRST, then this roadmap and [V7_LEGACY_EVIDENCE_LEDGER.md](V7_LEGACY_EVIDENCE_LEDGER.md); verify branch and latest commit and only then plan the next step. The handover protocol applies independently of how a chat ends (limit, deletion, handoff, new model or new contributor).

This governance rule **does not change** the existing design freeze or authorize VPS operations, paper trading, or live trading.

## 12. Owner scope update — 2026-10-20 IST (takes precedence over founding freeze)

The exact owner instruction is preserved in `V7_OWNER_AUTHORIZATION_2026-10-20.md`. Implement a complete auto-learning/auto-trading architecture, keeping historical research removable. Paper/live interfaces must exist but real credentials/orders remain separately unauthorized. Controlled isolated V7 VPS development, public data acquisition, training and historical evaluation are now authorized via saved PuTTY session `8GB-Observation`; prior no-VPS statements above describe earlier scope.

Fixed experiment: January–March 2026 train/freeze A; April–June evaluate frozen A then train/freeze adaptive B and same-architecture B1 control on matured January–June evidence; July–September independently compare A/B/B1. A later B2/C trained on July–September may only be assessed on subsequent data. All January–September results are an exploratory engineering baseline because of prior V6 inspection. Production readiness and economic acceptance require evidence, not implementation labels.

## 13. Step 6 resumed Work continuity — verified small-market pilot and end-window fix (2026-10-20)

The implementation branch `V7` has advanced beyond the original planning-state G0 roadmap. Follow the current [Step 6 source and result audit](evidence/v7-step6-real-pilot-boundary-audit-2026-10-20.md) and the append-only [V7_CHAT_HANDOVER.md](V7_CHAT_HANDOVER.md) rather than treating historic G0/G1 statements as current.

- **Nine-month pilot actually completed:** 54 exchange-SHA-checked BTC/ETH/SOL kline/funding archives, 249,685 conditional candidate labels, A fit Jan–Mar, A reviewed Apr–Jun, B1/B adaptive fit Jan–Jun and assessed Jul–Sep. Data sample is **three coins**, not the 900 USDT-style archive directories; eligibility is archive-observed and **historical active listing is unverified**.
- **No positive learning edge in pilot:** July–September after-cost 5m-proxy simulated net A **−340.6883 USDT**, B1 **−660.0041 USDT**, B adaptive **−953.6469 USDT**, on separate initial 10,000-USDT trading sleeves. No model promotion.
- **Causal boundary repair:** Model may enter only if its entire fixed 60-minute maximum holding horizon can fit before the **known, predeclared** examination end time. Unknown outcomes elsewhere still fail the capital/account completeness gate. Incomplete comparisons no longer output bootstrap uplift. VPS **34/34 V7 tests PASS** and corrected pilot replay exited successfully. Original pilot outputs have been preserved; complete fixed results are in separate `experiment-boundary-fixed/`.
- **Market archive inventory:** 1,056 raw S3 directories, 900 USDT-style candidate names, 876 with period objects, 12,234 relevant historical ZIPs (1,791,265,945 declared compressed bytes). These are **data availability facts, not a tradeable 900-contract exchange universe**.
- **Full-market scale preflight is now mandatory before bulk ingestion:** the three-coin SQLite research DB uses ~344 MiB. Naively scaling independent per-signal rows to all archive candidate symbols risks exhausting the 96 GiB VPS. Implement checkpoint/resume, explicit storage budget and a compact labeled data schema before bulk jobs; audit per-symbol history coverage and source quality.
- **Status:** Current engineering prototype runs and historical 3-coin negative baseline exists. G1/G3/G4 broad-market completeness, truly native fills, production paper and live authority remain **NO-GO / NOT VERIFIED**. Owner authorization still permits isolated VPS data/research work, not trading.
- **Next bounded step:** Bounded, resumable and disk-safe all-universe ingestion with source-attested historical contract eligibility or honest provisional grading; followed by a broader finite history/model run and updated evidence, never a claim of blind profitability.

## 14. Step 7 checkpointed data builder and real-pilot replay parity (2026-10-20)

See [Step 7 verifier](evidence/v7-step7-checkpointed-dataset-real-replay-2026-10-20.md) and [V7_README.md](V7_README.md) for exact commands.

- **Implemented:** One atomic, durable `build_progress` record per source-verified symbol; strict resume only for incomplete datasets with matching time window, label policy, registry SHA, source symbol set, BTC context and per-symbol source bytes. No overwrite of complete datasets.
- **Resource controls:** CLI defaults `--max-db-gib 12`, `--min-free-gib 8`; builder checks SQLite/WAL/SHM storage and required free space on both sides of each symbol transaction. A single pending symbol can overshoot quota before it is checked; operators must retain a sufficient free-space reserve. Interrupted output always remains **incomplete**.
- **Verified actual Binance archive replay:** Three-coin BTC/ETH/SOL Jan–Sep sample, intentionally forced early at 0.08 GiB quota (proper `DATASET_DB_BUDGET_EXCEEDED_INCOMPLETE`), resumed successfully with a 1 GiB quota (1 checkpoint reused), 249,685 labels and 2,454 8h reviews. 36/36 V7 Linux tests passed. Refit model and replay created byte-identical C_A / C_B decision logs compared with original corrected pilot.
- **Remaining scale blocker:** 900 USDT-style archive directories are not confirmed active perpetuals, and 344 MiB per three historically continuous coins suggests large storage growth. Need qualified historical source registry, deliberate 20–50-market stress, compact label representation and correctly bounded broad-market scanner before full 9-month all-market training.
- **Status:** Engineering ingestion/recovery PASS, economic readiness and broad-market completion NOT PASSED; models A/B1/B remain negative on 3-coin historical 5m-proxy. Do not enable private exchange orders, continuous paper or live mode.
- **Next:** Profile finite larger cohort and reduce redundant repeated feature data if quotas require it, preserve real-source SHA chain and source authority, and update GitHub handover after each step.

## 15. Owner-ordered learning first — mandatory pause on expanding coins (2026-10-20)

**Owner decision overrides the earlier Step 7 next-action priority to expand the 3-coin pilot to 20–50 coins.** The V7 project remains an auto-learning, auto-trading bot with eventual all-market selection, but it must **first provide evidence that its Trading Brain actually learns to make better economic trade/no-trade decisions** from observed outcomes. Without this, increasing the coin count would mostly multiply invalid labels, compute/storage cost and bad simulated trades.

**New gate:** `LEARN-3C` — BTCUSDT/ETHUSDT/SOLUSDT **three-coin learning demonstration**. Market-wide expansion is **ON HOLD** until (a) model/label/time/cost correctness audited; (b) frozen A vs B1 vs adaptive B and NO TRADE compared under matched chronological and one-slot constraints; (c) concrete overtrading and calibration failure modes identified and addressed with pre-registered challenger hypotheses; (d) improvement in new, properly isolated chronological decisions demonstrated, including quality of abstentions and after-cost portfolio decisions; and (e) owner explicitly reviews evidence and approves unlocking a broader-market test. No blanket promise that the first 3-coin result will become profitable.

**Baseline facts to preserve:** Jul–Sep 2026 fixed BTC/ETH/SOL replay on separate $10,000 research sleeves: A **233 trades/−340.6883 USDT**, B1 **377/−660.0041 USDT**, adaptive B **630/−953.6469 USDT**. Zero-trade baseline **0 USDT**. B adaptation increased activity/loss; present evidence is **negative**. Reports were 5m historical proxies and Jul–Sep 2026 was previously inspected; they do not certify any new OOS economic performance.

**Immediate next milestone:** `V7_THREE_COIN_LEARNING_AUTOPSY.md`, based on **existing** BTC/ETH/SOL training and decision/label artifacts. Analyze scored predicted net return vs realized outcome, BTC-entry regime and coin-relative structure, MFE/MAE/label integrity, cost/funding/proxy assumptions, distribution of model family choices and trade frequency, NO TRADE calibration, alternative opportunity cost and separate market-capital occupancy. Create tests as required, not gratuitous strategy or exit experiments. Only afterward propose small well-specified challengers and re-evaluate on untouched later chronological data when it exists; cannot manufacture fresh data by repeating the same nine months.

**No relaxation of governance:** Owner's earlier proposed G0–G8 numeric thresholds remain proposals until frozen. The mandatory learning-first pause itself **is approved** by the owner. No external library may be treated as a plug-and-play winning brain. Before a future 20–50 coin or 900-directory download, refer to this hard gate and [V7_LEARNING_FIRST_GATE_AND_OPEN_SOURCE_REVIEW_2026-10-20.md](V7_LEARNING_FIRST_GATE_AND_OPEN_SOURCE_REVIEW_2026-10-20.md) for upstream research on FreqAI/FreqAI-RL, Microsoft Qlib, River ADWIN, FinRL/FinRL-X, Stable-Baselines3 and maintenance limitations of Quants Lab.

**Explicitly retained:** Step 7's disk-bounded resumption and 20-of-N market selector design are useful for an eventual validated expansion; their previously proposed immediate sequencing is **superseded**. Existing VPS historical data and results must be preserved; **do not** start new bulk data collection, automated real/paper trades, new deployment or alternate-exchange execution under this decision.

## 16. LEARN-3C factual audit result — gate HOLD, do not expand (2026-10-20)

**Completed on real existing BTC/ETH/SOL January–September archived pilot; report: [V7_THREE_COIN_LEARNING_AUTOPSY.md](V7_THREE_COIN_LEARNING_AUTOPSY.md).** This is a **read-only audit** of the fully saved and corrected three-coin run, not another retrospective trading-policy experiment or model retrain. On isolated Linux VPS the updated **39/39 V7 tests passed**. Source audit [scripts/v7_three_coin_learning_audit.py](scripts/v7_three_coin_learning_audit.py) validates saved output file digests and event hash chains, joins selected predictions to matured after-cost outcomes and verifies PnL against frozen saved model ledgers.

**Verified learning failure mechanism (not hypothetical):**
- July–September on separate $10,000 proxy wallets: A **233 trades / −340.6883 USDT**; B1 **377 / −660.0041 USDT**; adaptive B **630 / −953.6469 USDT**.
- Forecast net return **on selected trades** vs actual average net (basis points of notional): A **+16.66 vs −14.62**; B1 **+15.11 vs −17.51**; B adaptive **+13.17 vs −15.14**. All have ~28–33bp selected-trade optimism errors. This does not establish full-market model calibration on unselected rows.
- **522** of adaptive B's 630 trades occurred at instants when A abstained, losing **−657.4179 USDT**. This is the dominant excess-exposure diagnosis; simultaneous timestamp does not mean a trade could replace another wallet's occupied position.
- The six-month B1/B artifacts have identical source SHA256 for both base trade and watch models; the adaptive B switches to up/down/range specialist heads, and more trades plus greater losses resulted. **Regime experts have not earned trust.**
- The trained six-month trade head used **18,903 of 171,482 (11.0%)** available matured candidates, versus A's 18,142 of 90,235 (20.1%). Group thinning/reward calibration need scientific ablation, not a blind larger download.
- Label source check: **249,693** candidate signals, **249,685** matured outcomes, **8** unresolved paths, **0** prematurely matured labels, **0** missing contextual outcomes, **11** OHLC both-touch ambiguous outcomes. All source lifecycle grades remain unverified archive presence and fills remain OHLC proxy.
- Current entry control considers candidates with predicted return **greater than zero**, then uses *relative* LambdaRank score to choose. There is no validated uncertainty/cost-margin threshold or independently calibrated zero-exposure utility.

**Decision:** Mandatory gate `LEARN-3C = HOLD`; **no 20–50 coin or full-market expansion**, no live/paper model promotion, no funding of a larger universe to compensate for these findings. Next bounded stage: full as-of candidate/probability calibration and net-return/NO TRADE audit on **development-only** earlier periods, followed by explicitly preregistered abstention/calibration/independent-context-expert challenger comparisons using purged chronological splits. Do not retune to the already inspected July–September 2026; new truly unseen chronological proof is still needed. A negative or zero-trade model is an honest baseline.

**Truth boundary:** Root causes of return overprediction are still competing hypotheses (feature drift, reward/label proxy, cost, calibration, sample thinning, model overfit). No untested fix, RL library, or rewritten exit has been proven. Keep all old historical outputs and the immutable V7 source hash chain.

## 17. LEARN-3C method feasibility trials — Qlib, FreqAI, FinRL ideas + actual River (2026-10-20)

**Owner requested:** “Do you have solution? The four open source you mentioned can be used anywhere to make things better? If yes try them.” Completed an **offline, bounded, existing-three-coin test**, not a model-promotion claim. Full [methods report](V7_THREE_COIN_OPEN_SOURCE_METHODS_TRIAL_2026-10-20.md) preserves library provenance, date cutoffs, costs, input model checksums, reproducible code, actual VPS results and scientific limits.

- Frozen **A trained Jan–Mar** unchanged, *April-only* matured (5,606 1h-sampled conditional candidate records) used to learn a bias/reward overlay. **May–June** fresh-to-this-fit but already historically inspected is the **development** replay, $10k separate sleeve, same full policy and one actual slot.
- **Results:** frozen A 196 trades/−423.3050 USDT; FreqAI-inspired all-candidate mean-residual correction 212/−382.1335; adding **25bp extra predicted-net buffer** 69/−26.4029; FinRL-inspired one-step regime enter/NO TRADE Q policy 0/0.0. The buffer **reduced loss by ~93.8%** but did not create positive returns, and NO TRADE beats all approaches.
- **Most significant learning:** April all-candidate residual correction was **−1.2493bp** (negative), yet selected trades from the prior July–Sep audit had **+28–33bp optimistic forecast errors**. **Selection-conditioned calibration failure** appears more important than population calibration; simply feeding more all-candidate rows cannot fix this without rank/portfolio context.
- **River actual package:** independently installed **River 0.22.0** in a VPS research-only `--target` directory, **not** in V7 production requirements. ADWIN `delta=.002` monitored 255 frozen A April–June matured selected-trade errors, detected **0** statistical drift alerts. Absence of alerts does not establish good trading or no drift.
- **Accurate framework claim:** FreqAI, Microsoft Qlib and FinRL packages were **NOT installed/run**; only their *method ideas* were implemented on existing V7 source and one-slot replay. Actual FinRL-style experiment was a one-step contextual action-reward gate, **not a full trained RL agent**. The three other upstream packages are not automatically compatible with BTC/ETH/SOL perpetual execution and would add unvalidated simulator/dependency complexity if installed blindly.
- **Software verification:** **41/41 Linux V7 tests passed** with new causal calibration and NO TRADE gating tests; no legacy 530-test rerun, no new market data or bot executor changes.
- **Verdict:** `LEARN-3C = HOLD` continues. Focus next on selected-top-rank conditional payoff calibration, confidence/abstention with timestamp/time-block validation, and reward tied to actual one-slot after-cost occupancy. Do not backfit July–September 2026 or unlock additional coins merely because abstention reduced one retrospective loss.
