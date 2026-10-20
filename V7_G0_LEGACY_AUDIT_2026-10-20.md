# NBOT V7 — G0 GitHub Legacy Source and Evidence Audit

**Report:** `V7_G0_LEGACY_AUDIT_2026-10-20.md`  
**Audit date:** 2026-10-20 (IST)  
**Scope:** Read-only GitHub source-and-archived-evidence audit of NBOT V3–V6; **NO VPS access**  
**Disposition:** **G0 GITHUB AUDIT COMPLETE / PASS WITH DEFERRED RUNTIME-EVIDENCE VERIFICATION**. Proceed to a carefully scoped **G1 historical data inventory/design**. All previously reported economic, lookahead and execution blockers remain OPEN and prevent paper/live authorization.  
**Owner-authorized activity:** Complete G0 without accessing the VPS.  
**Repository:** [samqju/Nbot](https://github.com/samqju/Nbot)  
**V7 branch:** `roadmap/v7-comparative-learning-20261019`  
**Pinned V6 audited source parent:** commit `fd966f6a3891468f81c46d56b53c51ccbe4a518a` on `prototype/v6-freqtrade-freqai-20261016`  
**Main history tree object retrieved:** `d497e961e2891c43669d64f2a16d210011d703a4` (main code/doc tree at audit retrieval; freeze individual audited code blob IDs below).

## 1. Methods and explicit evidence boundaries

- Queried the connected GitHub repository, enumerated both recursive trees, and read the relevant **actual source files and unit-test source**, not just roadmap prose.
- V6 source tree retrieval: **248 Git blobs**; main history tree retrieval: **311 Git blobs**. Counts include more than code and are *repository inventory*, not claims of independently audited behavior for each file.
- Read V6 global dataset generator, ranker, orchestration, chronological purge, M5A scanner/replay, historical contract inventory, data bootstrap and unit test source. Read V3 decision ledger, counterfactual learner and replay, V4 ranker/generation/promotion/paper test code, V5 selection, market-quality and paired-exit code, and supporting test source on main.
- Reviewed GitHub-stored V6 technical/economic reports (M1/M2, Stage 1 and Stage 3, M5A historical proxy, no-time research and exact 1% trailing) and original V3–V5 architectural documentation.
- **No tests were newly executed, no models newly trained, no private result ZIPs downloaded/verified, no network market-data archive downloaded, no VPS reached, no service restarted, and no trading orders placed.**
- The historical *results* cited below are **as reported in committed evidence**. Their SHA-audited reports describe previous VPS validations, not validations conducted anew in G0.
- GitHub source existence, unit-test cases and reported prior passing results mean **candidate code for reuse**, NOT verified V7 integration, profitability, or restored historical runtime state.

## 2. Direct answer: what V6 actually did versus our founding assumption

**Incorrect simplified premise:** 'V6 ran one trade, so it had no comparative trade outcomes.'

**Verified source reality:** V6 source `scripts/m2r_v6_global_dataset.py`:
- `pair_events` (lines 93–128) iterates every configured pair, each active strategy family, both sides, and each qualifying entry. It generates independent next-open / conservative candle-path stop/target `net_proxy` outcomes (lines 63–91).
- `build` (138–155) consolidates **25 pairs** and hashes source histories. `numeric_matrix` (130–136) includes feature columns, strategy family, side and pair indicators.
- `learn_and_rank` (157–280) fits LightGBM regression plus classification where possible, calibrates win probabilities, then evaluates candidate forecasts at common 5m timestamps. It creates both selected-decision and rejected-forecast files, preserving rejected candidates' prediction records.
- Its **probability prefilter** at lines 218–220 rejects any candidate with calibrated win probability below **0.50** before the global ranker sees it. Additional risk/edge/regime screening occurs downstream.
- The ranker `scripts/m2r_v6_global_opportunity_ranker.py` (114–220) enforces fixed 25-pair membership, time/candidate conditions, one occupied portfolio slot and a conservative expected-edge formula. Native Freqtrade orchestration separately enforces `max_open_trades=1`.
- V6 global batch `scripts/m2r_v6_global_batch.py` sets a 1-position, 1× research backtest and exports true native ZIPs as **portfolio** evidence. That single-slot constraint is not the number of independent conditional research labels.
- The V6 Stage 3 archived report records **914,878** candidate label rows, four forecast lookbacks, **12/12** scheduled jobs completed and **zero AI-selected native trades across all four windows**. The model's predicted economics/gates produced universal NO TRADE. There is no demonstrated profitable selection.

**Interpretation:** V7's novelty must be **better comparative data quality, actual economic target alignment, broader historical candidate selection, validated ranking/calibration and proven one-slot portfolio uplift**, not merely 'run parallel simulations for the first time'.

## 3. V3: verified modules, strengths, and reuse verdict

| Original module (main) | Actual code behavior | V7 decision |
|---|---|---|
| `nbot/observation/decision_ledger.py` | `FrozenDecision`, `MaturedOutcome`, `DecisionLedger`; SQLite `frozen_decisions`, `matured_outcomes`, `unresolved_outcomes`; SQL triggers prohibit UPDATE/DELETE of original records | **REUSE architecture**; adapt schema for strategy/version/side and 20-pair decisions |
| `nbot/observation/research_replay.py` | `ResearchReplayBook` tracks overlapping per-decision hypotheses without capital limit, ingests trade events by symbol, marks gap-unresolved and produces matured results independently | **REUSE core replay concepts**; reverify long/short, stop timing, scalable memory, execution truth |
| `nbot/observation/counterfactual_learning.py` | `load_samples` only accepts matured, timestamp-consistent research outcomes, checks feature/evidence digests, gaps, costs and receipt availability. `purged_split` purges horizon/availability overlaps; `portfolio_metrics` separately simulates one-position selection | **REUSE temporal governance/test fixtures**, not hard-coded cost settings as V7 ground truth |
| `nbot/observation/live_two_tier.py` | `BroadResearchScanner` + high-resolution WSS, research-only authority, explicitly separate broad observation from detailed paths | **REUSE budgeted market scanning design**, not wholesale production runtime before G1 proof |
| `nbot/observation/chronological_replay.py` | Tick-event chronological trailing-state engine with STOP path and data-quality status | **REUSE stop-chronology tests**, but old integer-R policy does not imply V7's approved exit |
| `nbot/observation/v3_universe.py` | Broad and detailed selection primitives | **REUSE conceptual selection contracts**, must extend point-in-time contract availability |

**Tests present and read:** `tests/test_v3_redesign_foundation.py` includes immutable records, overlapping research, broad-vs-20 WSS pool, temporal/path and no-forced-20 checks; `tests/test_counterfactual_learning.py` covers rejected-trade training, time receipts, data gaps and one-slot portfolio diagnostics. **These tests were not run in G0.**

**V3 limitation:** Some older data coverage was conditional on admission to a high-resolution WSS pool; the learning module explicitly labels its samples `CONDITIONAL_ON_HIGH_RES_POOL_NOT_MARKET_WIDE`. V7 must not claim these labels represent the whole exchange.

## 4. V4: verified source — major high-value discovery

**V4 ALREADY HAS A CROSS-SECTIONAL LIGHTGBM LEARNING-TO-RANK MODEL.** Do not code another from scratch before benchmarking it.

- `nbot/observation/v4_generation.py` contains `_groups` grouping contemporaneous training candidates by event (198–201), `_purge_training_groups` using a full 4-hour horizon and matured receipts (204–223), `_matrix` converting same-event net-R outcomes to ranking relevance labels with group normalization (226–242), and `_train_ranker` using LightGBM **`objective="lambdarank"`**, `metric="ndcg"`, explicit groups and 1 CPU thread (245–256). `_top1_metrics` is present.
- `nbot/observation/v4_research.py` implements a separate research candidate/scanner/store and factory. `v4_promotion.py` recomputes qualification from immutable data, requires review, and reports `automatic_promotion=False`.
- `nbot/observation/v4_paper_contest.py` contains two isolated one-position paper books, explicit champion vs challenger, unscorable path tracking and model governance. Source says no order authority and not automatic promotion.
- Tests `tests/test_v4_research_factory.py`, `test_v4_promotion.py` and `test_v4_paper_contest.py` are present and include nominal unit scenarios around batch thresholds, gaps, blocked auto-promotion and explicit review.

**V7 reuse verdict:** **HIGHEST PRIORITY**: port/refactor the V4 chronological **groupwise learning-to-rank** approach and its evidence/promotion gates after G1. Benchmark against simple selectors and V6 LightGBM regressors. Do not assume old V4 features, integer-R labels, universe and stop-policy outcomes are directly comparable to V7's exit- and dollar-normalized targets. Test exact requirements for training with sparse/same-event groups.

**Remaining verification:** V4 source existence proves an implemented code path, not that its model beat V6 or made positive after-cost live returns. Code/test reuse still requires controlled validation.

## 5. V5: verified code and reuse verdict

- `nbot/observation/v5_paired_exits.py` implements `PairedEntry`, `PairedTick`, per-policy state arms, tick-path replay, gap invalidation, funding-aware results, and no order authority. `_Arm.apply` (115–136) checks stop/target before lifting a trailing stop; records executable quote crossing and overshoot rather than idealized stop fills. This is useful for avoiding same-bar fantasy execution.
- `nbot/observation/v5_selection.py` computes signals with directional/recovery and risk/lending-cost checks; has `evaluate`, `plan_event` and ranked candidate score contracts. This is a reusable **baseline** and test harness, **not proof of alpha**.
- `nbot/observation/v5_market_quality.py` builds public exchange/filter and depth snapshots and refuses private order authority. Historical as-of market-quality snapshots remain unproven without timestamped source.
- `tests/test_v5_paired_exits.py` contains cases for matched arms, funding proof, disconnect/gap invalidation and short executable ask; tests for V5 quality/selection also present in main tree.

**V7 reuse verdict:** **REUSE event/exit replay and market-quality parsing**; treat V5 selection as a comparator not a V7 winning model. Do not copy hard-coded R-step or cost schedules without defining V7 policy.

## 6. V6: component reuse and explicit engineering gaps

| Source module | Verified code / artifact | Reuse disposition |
|---|---|---|
| `scripts/m2r_v6_global_dataset.py` | 25×8 × long/short synchronized signal/path labels, hashed Feather histories, parquet cache, LightGBM regression + classifier, chronologically separated calibration and saved predictions/rejections | **REFRACTOR/REUSE** core dataset and output/provenance format; do not reuse weak probability gate or approximate label economics as truth |
| `scripts/m2r_v6_global_opportunity_ranker.py` | Global ranking of coherent candidates, time checks, NO TRADE and one-slot safety, risk-adjusted score | **REFRACTOR/REUSE** safety and API; remove fixed 25, allow true 20-of-N as-of membership and compare economic scores |
| `scripts/m2r_purged_split.py` | Filters labels whose exit index crosses test cutoff, with explicit purged rows | **REUSE chronological guard** but extend to precise outcome receipt time, variable horizons and cross-sectional folds |
| `scripts/m5a_universe_selector.py` | As-of public snapshots, eligibility/readiness proof, BTC pin, max ten replacements per eight-hour review, HOLD on incomplete readiness, no order authority | **REFRACTOR/REUSE** proposal/hysteresis safety; original `CONTRACTS=25` requires V7 20 pair parameterization |
| `scripts/m5a_historical_ohlcv_proxy_replay.py` | Compares 25 fixed/liquidity/quality universes with hourly-momentum proxy; explicitly flags current-survivor sampling and missing historical spread/funding; no full native real-wallet proof | **REUSE control methodology** only, not its proxy as profitable signal |
| `scripts/m2r_binance_historical_universe_inventory.py` | Read-only Binance Vision S3 **directory/ZIP metadata** listing for USDT futures | **REUSE as G1 archive discovery**; not proof of historical contract active status |
| `scripts/bootstrap_history.py` | Freqtrade download planning for bounded candidate pairlist | **REUSE as bounded detailed-history bootstrap**; no exchange-wide point-in-time lifecycle support by itself |
| `scripts/m2r_v6_global_batch.py` | Docker/native backtests with one global position, fee guards, audit hashes and source permission repairs | **REUSE RESEARCH-ONLY orchestration patterns**; freeze unit/fee/exit definitions and independently reproduce on G5 |
| `scripts/m2r_v6_global_final_audit.py` & `scripts/m2r_v6_exact_one_trail_final_audit.py` | Prior native result ZIP/file integrity and deterministic report crosschecks | **REUSE verifier pattern**; G0 did not execute on private archives |

**Critical code issues that V7 must explicitly test:**
1. **50% probability suppression:** dataset generator line 219: `if x.win_probability<0.50: continue`. Positive expected payoff can exist below 50% win rate. Change **only in a preregistered V7 challenger**, never retrofit old V6 results.
2. **Confidence/policy cost construction:** dataset generator uses a global 75th-percentile absolute residual `error`, global downside decile, an extra assumed execution penalty and a downstream positive-edge minimum. These can eliminate every opportunity; need score calibration and policy ablation on *development-only* folds, not retrospective threshold tuning on already-seen test months.
3. **Unverified flags:** lines 239–241 set `historical_market_eligible=True` and `training_label_embargo_verified=True` for all constructed forecasts without per-row independent source receipts. The model training uses some chronology protections, but the flags are not individual audit attestations. Replace with verified evidence bound to each decision.
4. **Not genuine depth:** line 237 passes a 5-minute **turnover-derived proxy** as `available_market_depth_usdt`. It is not historical top-of-book depth/filled liquidity.
5. **Proxy vs native path:** entry price uses next open, target/stop outcome from 5-minute candle first touch with stop-first tie, fixed round-trip fee, no funding/spread/queue/slippage in training label. Native engine may differ. Reconcile entry horizon and fee/funding/policy semantics before calling labels realizable economics.
6. **Pair count and lifecycle:** V6 ranker rejects any list with fewer/more than **25 fixed pairs**; M5A also holds fixed 25. Both need true 20-of-N and historical listing/delisting awareness. Never use today's surviving pairs to determine past opportunity set.
7. **Frozen regime rules:** ranker rejects trend-opposing sides and high volatility; it is not established that these gates improve net trade quality. Preserve old controls; test justified alternatives on new holdout.
8. **One-slot interpretation:** V6 generator ranks every timestamp with `portfolio_has_open_position=False` (line 244), then the native backtest separately restricts actual execution to one position; V7 should explicitly reconcile *all offered signals* with *which choices were feasible while capital was locked*.
9. **Feature limitations:** basic indicators plus pair/family/side embeddings; no guaranteed source-matched microstructure/regime intelligence or improved payoff distribution. Do not confuse model complexity with statistical edge.
10. **Installed tests not executed here:** tests cover synthetic global ranker, purged splits, safety overlays, M5A readiness and 1% trailing policies; behavior beyond their fixtures still requires actual non-regression runs.

**Explicit outcome change from earlier chat:** Since archived V6 labels already include rejected candidates, do not frame V7 as solving a nonexistent absence. The key research gap is quality, generality, economics and validation of comparative decisions.

## 7. Archived V6 economic findings — preserve negative evidence

| Source-reported experiment | Reported finding | G0 interpretation |
|---|---|---|
| M1 data/model technical gate | 25 pair history/model fitting and bounded FreqAI completed | Technical proof only |
| M2 acceptance | **NO-GO**; official AI lookahead flag differences, 17/130 depth sample timing gaps in documented early study, true historical fill/queue uncertainty | Unresolved deployment blockers |
| Stage 1 eight families | **63/63** planned jobs; all eight unprofitable under native fees in studied monthly windows, all 24 individual stressed family-month results negative | Do not nominate old indicators as alpha |
| Stage 2 exit variants | **120/120** documented completion | No automatic economic pass |
| Global 25×8 model | **914,878** labeled candidates; **12/12** jobs; zero selected trades/zero PnL in one-slot native runs | Demonstrates candidate-label infrastructure, not good trade ranking |
| No-time exit trial | **64/64** completed; **0/16 uninterrupted native portfolios** positive under additional hypothetical 25bp stress | Holding longer did not establish an after-cost edge |
| Exact 1% activation trail | **8/8 strategy family trials worse** than prior trailing and **0/8 positive** | Do NOT re-run as V7 default 'solution' |
| Rotating universe proxy | **75 market** currently surviving-symbol historical hourly study, **234 eight-hour review points**; unstable prospective proxy benefit; missing delistings and full native fills | Good G1 hypothesis control; not directional ranking validation |

The fixed V6 date windows **July–September 2026** and earlier studied portions of October are already repeatedly inspected and **must not be described as clean untouched V7 holdouts**. Unseen proof requires later truly uninspected observations and lock-before-observe rules.

Original evidence URLs within this branch:
- [M1](M1_EVIDENCE.md); [M2](M2_EVIDENCE.md)
- [Stage 1](evidence/m2r/2026-10-19-stage1-final-research-report.md)
- [Global 25×8 final](evidence/m2r/2026-10-19-global-25x8-native-recovery-final-report.md)
- [Ranking/exit audit](evidence/m2r/2026-10-19-trailing-exit-and-global-ai-design-audit.md)
- [M5A proxy final](evidence/m2r/2026-10-19-m5a-75-market-historical-replay-final-findings.md)
- [No-time exit final](evidence/m2r/2026-10-19-no-time-exit-final-64-native-research-report.md)
- [Exact 1% trail final](evidence/m2r/2026-10-19-exact-one-percent-trailing-final-eight-native-report.md)

## 8. Reuse register — verified source blob IDs

GitHub blob SHA validates the static Git object **content at this source ref**, not a runtime result checksum. Preserve in V7 port manifests.

| V7 purpose | Source path / ref | Git blob SHA |
|---|---|---|
| V3 immutable ledger | `main:nbot/observation/decision_ledger.py` | `fc7ca2a9baa97a9e14d4fdd23fca2817cb8afa40` |
| V3 capital-uncapped replay | `main:nbot/observation/research_replay.py` | `db225ec0d32247f71775191f701efca4c8015645` |
| V3 causal counterfactual trainer | `main:nbot/observation/counterfactual_learning.py` | `8328a6d55b3ff694af1562e8d038b89bbc6afa12` |
| V3 two-tier scanner/WSS | `main:nbot/observation/live_two_tier.py` | `f046564288acd8659dfcfe4d9ead5bb0621a867a` |
| V4 cross-sectional Lambdarank | `main:nbot/observation/v4_generation.py` | `72c6ba883b72f3c23a33441c0d4c20fe834072c8` |
| V4 research factory | `main:nbot/observation/v4_research.py` | `6d141f0163168fd8b95a30e3dfef839d2bd1bf70` |
| V4 promotion rules | `main:nbot/observation/v4_promotion.py` | `dd6660971f81fb9c14166cd990fecb33bb193e6d` |
| V4 paper contest | `main:nbot/observation/v4_paper_contest.py` | `9f16167655e4d997fb94975c2e74d8b3d2d66d7d` |
| V5 paired exit lab | `main:nbot/observation/v5_paired_exits.py` | `1784077f1ec9f392bc9c8f0f6e273788096c3b8d` |
| V5 entry evaluation | `main:nbot/observation/v5_selection.py` | `3f7916cd6283309972e8695afb592f307a10ece2` |
| V5 market quality | `main:nbot/observation/v5_market_quality.py` | `655d31f49e8fa8299dd93c7527d3e41079b890d9` |
| V6 candidate generator | `prototype/v6-freqtrade-freqai-20261016:scripts/m2r_v6_global_dataset.py` | `58d234774cb3f516d3565669569ac59460f4991b` |
| V6 global ranker | `prototype/v6-freqtrade-freqai-20261016:scripts/m2r_v6_global_opportunity_ranker.py` | `f64b3af9a027aa0bdf9471a43be7e1a3d2b74915` |
| V6 purged train/test split | `prototype/v6-freqtrade-freqai-20261016:scripts/m2r_purged_split.py` | `a914d5b9513082545daf132716116d9ec847dcb9` |
| V6 M5A selector | `prototype/v6-freqtrade-freqai-20261016:scripts/m5a_universe_selector.py` | `4d510990b822c34dc7c2ba096d8ded2eadb153f9` |
| V6 global native coordinator | `prototype/v6-freqtrade-freqai-20261016:scripts/m2r_v6_global_batch.py` | `8f79dfef945362ae5699c4fcfcecfc792549cd63` |
| V6 historical archive scanner | `prototype/v6-freqtrade-freqai-20261016:scripts/m2r_binance_historical_universe_inventory.py` | Inspect/refreeze blob in G1 if using |
| V6 exact 1% trailing negative report | `prototype/v6-freqtrade-freqai-20261016:evidence/m2r/2026-10-19-exact-one-percent-trailing-final-eight-native-report.md` | Preserve separately; report is negative |

**Important:** Main may later change. Porting source into V7 requires the above actual source blob versions or a newer separately audited version. Treat this register as an **inventory**, not a dependency lockfile executing automatically.

## 9. G0 exit criteria and verification status

| G0 requirement | Result |
|---|---|
| Find legacy V3–V6 repo docs and source | **PASS** — on GitHub; V3/V4 code present in main, V5 code/main + branches, V6 prototype/ref |
| Inspect reusable actual Python code, not just plans | **PASS** — targeted source reads with blob SHAs and function inspection |
| Find before/after historic negative-economic lessons | **PASS AS ARCHIVED EVIDENCE** — M1/M2, Stage 1/3, M5A, no-time, exact 1% trailing |
| Document the mistaken 'no comparative V6 history' assumption | **PASS** — corrected with dataset code and 914,878 rows reported |
| Identify reuse vs rewrite and concrete gaps | **PASS** — sections 3–8 |
| Identify tests/source references for regression | **PASS** — GitHub test source inspected; **NOT RE-RUN** |
| Independently verify private VPS historical ZIP/data/model bytes | **DEFERRED**, not needed for repository-only G0; becomes necessary only before reusing archived runtime results to validate performance |
| Audit full market point-in-time historical completeness | **G1** (not in G0) |
| Prove V7 model/portfolio economics | **G3–G5** (not in G0) |
| Paper/live permission | **NO-GO; unchanged** |

**G0 final verdict:** The bounded **GitHub-only G0 has been completed**, with no VPS need and no claims of full runtime reproduction. This unlocks **planning/implementation of G1 only**, not model promotion or paper/live orders. Any future step that needs private VPS archives must declare that need and seek scope-specific authorization.

## 10. G1 exact next bounded task (no unnecessary VPS)

**First G1 step: all-market historical data feasibility and point-in-time contract registry specification using GitHub/public exchange sources.**

1. Inventory original V6 archive scanner and available downloaded **manifest/source-shape contracts**. Define a historical all-USDT-M USDT-perpetual (including delisted) registry with confidence flags, listing/delisting/suspension timestamps or `unknown`, not just current exchangeInfo survivors.
2. Compute expected metadata/candle/funding coverage and storage budget for **three contiguous months**. Source files in small per-symbol/time partitions; 5m/1h broad coverage; conditional 1m/tick for precise replay. Exclude using future information to select Month 1 universe.
3. Draw strict `record_asof`, `signal_asof`, `label_matured`, `training_cutoff` and `holdout_locked` boundaries, including delisting survival, late-listed coins and entire-universe screening.
4. Preserve existing V6 25-pair and 75-current-survivor historical assets as **known limited pilot**, not replacement for full exchange coverage.
5. Identify whether historical data can be stored/accessed from GitHub-friendly manifests first; if an eventual VPS storage/data download is needed, prepare an explicitly bounded plan and ask for authorization then.
6. Pre-register and protect genuinely unseen later chronological validation data: already explored 2026 Jul/Sep and studied October cannot serve as new pristine holdouts.

**Do not start downloading 3 months, run backtests or change deployment under G0.** The G1 design and storage decision precede any expensive jobs.

## 11. Decisions carried forward

- Reuse V3 ledger/replay, V4 true groupwise ranking/promotion, V5 paired execution and V6 dataset/native research as **audited inputs**, but no unverified trading edge.
- Maintain V7's 20-candidate top-of-market comparator plus excluded-universe controls and one-slot executable account.
- Preserve original negatives, never cherry-pick from inspected windows.
- Establish all 10–15 strategies only if independent and measurably promising; initial eight V6 families are **negative controls**.
- Continue every material step/decision with an update to [V7_CHAT_HANDOVER.md](V7_CHAT_HANDOVER.md). Failure to commit the journal means the step is incomplete for project continuity.
- **G0 did not require or use VPS access.**
