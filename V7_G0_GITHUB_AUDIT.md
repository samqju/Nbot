# NBOT V7 — G0 GitHub-Only Legacy Source & Evidence Audit

**Audit date:** 2026-10-20 (IST). **Scope:** GitHub repository `samqju/Nbot` only. **Execution:** READ-ONLY source/reports inspection; no SSH/VPS, private output ZIP, Docker, market download, trading, code runtime, or new backtests.  
**Disposition:** **G0 GITHUB SOURCE/EVIDENCE AUDIT COMPLETE — CONDITIONAL REUSE**, not a certification of archived VPS results or live readiness. Those checks remain later data-reproduction and G5 execution gates.

## Audited reference points

- V6 source parent: `prototype/v6-freqtrade-freqai-20261016`, base commit `fd966f6a3891468f81c46d56b53c51ccbe4a518a` (248 files in the fetched recursive Git tree).
- V3–V5 combined source: `main` Git tree `d497e961e2891c43669d64f2a16d210011d703a4` (311 files in the fetched recursive Git tree). Historical features coexist in main; documents alone are not proof of original deployment.
- Source and docs reviewed through GitHub `fetch_file` and repo Git tree. Test files were **inspected, not executed**; reports were **read, not independently recomputed**.
- Read [V7_ROADMAP.md](V7_ROADMAP.md) and [V7_LEGACY_EVIDENCE_LEDGER.md](V7_LEGACY_EVIDENCE_LEDGER.md) before relying on this audit.

## Executive G0 answer

**Keep the engines; replace/rework their integration and economic decision contracts.** We already own extensive counterfactual simulation, LightGBM learning-to-rank, matched exit studies, paper champion governance, historical data bootstrap, native Freqtrade backtesting and cost-audit scaffolding. V7 should not rewrite them wholesale. What is missing is: a historically correct full-exchange 20-of-N selector; strategy-quality and out-of-universe controls; consistent, fill-aware and causally valid cross-sectional labels; a V7 comparator/ranker tied to one-slot portfolio economics; and rigorous fresh holdout promotion evidence.

## Code-level reuse verdict

| Prior | Module / source (exact branch) | Verified code characteristics | V7 recommendation |
|---|---|---|---|
| V3 | `nbot/observation/research_replay.py` on main, blob `db225ec0d32247f71775191f701efca4c8015645` | `ResearchReplayBook` tracks overlapping independent long/short hypotheses, accumulates chronological market ticks, matures outcomes and invalidates gaps | **Reuse with adapter**; extend to all eligible entries, unified execution policy, source-quality flags |
| V3 | `nbot/observation/decision_ledger.py`, blob `fc7ca2a9baa97a9e14d4fdd23fca2817cb8afa40` | `FrozenDecision`, `MaturedOutcome`, SQLite append-only update/delete prevention, unresolved outcomes | **Reuse data contract**; add versioned V7 schema and decision-group IDs, no historical DB modification |
| V3 | `nbot/observation/counterfactual_learning.py`, blob `8328a6d55b3ff694af1562e8d038b89bbc6afa12` | Samples matured rejected AND approved research outcomes, verifies source digests and receipt cutoff, purges overlap; conditioned on high-resolution sampled pool | **Reuse logic**, do not mistake sampled high-res coverage for all-market coverage |
| V3 | `nbot/observation/live_two_tier.py`, blob `f046564288acd8659dfcfe4d9ead5bb0621a867a` | Credential-free broad research scanner with limited high-resolution stream; prior 100/20 tier concept | **Reuse architecture**, not exact old watch membership |
| V4 | `nbot/observation/v4_generation.py`, blob `72c6ba883b72f3c23a33441c0d4c20fe834072c8` | Groups same-timestamp events, label-maturity purge, LightGBM **`lambdarank`** with NDCG@1/3/5 and per-group weighting | **Top-priority reuse**; test whether utility-aware outcomes and groups align with V7 target |
| V4 | `nbot/observation/v4_paper_contest.py`, blob `9f16167655e4d997fb94975c2e74d8b3d2d66d7` | Frozen model generations, paper-only one-position separate books, explicit reviews, unscorable paths never invented | **Reuse staged governance**, do not copy old numeric gates as V7 approval |
| V4 | `nbot/observation/v4_promotion.py`, blob `dd6660971f81fb9c14166cd990fecb33bb193e6d` | Immutable paper evidence and promotion review; no order authority; numerical V4 gates | **Reuse governance mechanics**, set new prespecified V7 gates |
| V5 | `nbot/observation/v5_paired_exits.py`, blob `1784077f1ec9f392bc9c8f0f6e273788096c3b8d` | Same-entry independent exits, first executable crossing and next-tick stop activation, signed funding and gap-invalidated samples | **Reuse trade-path primitives**, keep frozen V6 negative exit evidence |
| V5 | `nbot/observation/v5_selection.py`, blob `3f7916cd6283309972e8695afb592f307a10ece2` | Directional setups, liquidity/funding/ATR and side-aware initial stop gates | **Reuse eligibility/risk primitives**, not assumed profitable signals |
| V5 | `nbot/observation/v5_market_quality.py`, blob `655d31f49e8fa8299dd93c7527d3e41079b890d9` | Exchange-info and depth parsing; public-data-only, no private order authority | **Reuse with historical as-of metadata validation** |
| V6 | `scripts/bootstrap_history.py`, blob `2209eb25319fc6fdb07a0041debbe9d172700f27` | Futures OHLCV/mark/funding bootstrap planner, normalized USDT pairs, readiness caveats | **Reuse/acquire broader exchange scope** |
| V6 | `scripts/m2r_binance_historical_universe_inventory.py` on V6 parent | Read-only Binance Vision archive-object metadata enumerator; explicitly not certification of exact listing status | **Reuse discovery technique**, supplement listing dates/suspensions/delistings |
| V6 | `scripts/m5a_universe_selector.py`, blob `4d510990b822c34dc7c2ba096d8ded2eadb153f9` | As-of snapshot checks, 8-hour reviews, hysteresis, at-most-10 rotations, readiness; proposal only | **Adapt** 25 to 20, update selection objective; no assumption turnover/volatility is alpha |
| V6 | `scripts/m2r_v6_global_dataset.py`, blob `58d234774cb3f516d3565669569ac59460f4991b` | Generates all qualified 25×8 side/family labels from future candles, LightGBM regression/classification, time-block calibration and saved rejected forecasts | **Reuse dataset/provenance patterns**, replace proxy-first label economics |
| V6 | `scripts/m2r_v6_global_opportunity_ranker.py`, blob `f64b3af9a027aa0bdf9471a43be7e1a3d2b74915` | Global cross-coin score, fixed 25, one occupied-slot gate, NO TRADE, causal checks | **Adapt**, remove arbitrary economics gates only via preregistered challenger, connect full actual portfolio occupancy |
| V6 | `scripts/m2r_purged_split.py`, blob `a914d5b9513082545daf132716116d9ec847dcb9` | Excludes training trades whose exit overlaps chronological test cutoff | **Reuse and extend** with full maturity/prediction cutoffs |
| V6 | `scripts/m2r_v6_global_batch.py`, blob `8f79dfef945362ae5699c4fcfcecfc792549cd63` | Finite Docker/native backtests, 1× 1,000-USDT slot, fee controls, ZIP hashes, no active live authority | **Reuse reference economic harness**, adapt selected universe/policy |
| V6 | `scripts/m5a_historical_ohlcv_proxy_replay.py`, blob `c1be6dfacb04b63855a05047b9ea45d4475122fe` | Honest 75-current-survivor proxy and lookback; explicitly flags survivorship, missing depth/funding and overlap | **Reuse negative control**, not as production historical universe proof |

## Audited tests — inspection only

- `main/tests/test_v3_redesign_foundation.py`: overlapping uncapped hypotheses, immutable ledger, gap handling, 100 broad/20 precise, does not force 20 if only 12 eligible.
- `main/tests/test_counterfactual_learning.py`: rejected outcomes do train, future receipts not available early, gaps excluded, one-slot policy comparison.
- `main/tests/test_v4_research_factory.py`, `test_v4_paper_contest.py`, `test_v4_promotion.py`: fail-closed research, explicit promotion, numerical gate tests.
- `main/tests/test_v5_paired_exits.py`: same-price-path three arms, short executable ask, missing funding and feed-gap handling.
- `V6/tests/test_m2r_v6_global_opportunity_ranker.py`, `test_m2r_v6_global_batch_contract.py`, `test_m2r_purged_split.py`, `test_m5a_universe_selector.py`: synthetic global candidate selection and no-trade, fixed 25 contract, times, rejected forecast preservation, native safety and readiness.

**No tests were executed by this audit**; passing test names/assertions are not the same as fresh CI green, real fills or reproduced profitability.

## Code findings that V7 MUST fix or independently challenge

1. **Global ranker hard-codes 25**: `choose_global_opportunity` explicitly requires `len(original_25_pairs)==25`. M5A `select` requires 25 incumbents. V7 uses up to 20 and a point-in-time rotation scheme.
2. **Hardcoded 50% filter**: `m2r_v6_global_dataset.py` `learn_and_rank` skips forecasts with `win_probability < .50` before economic rank; this can discard a positive expected-return, asymmetrically paying candidate.
3. **Cost/exit proxy is not a native fill**: dataset `proxy_label` uses next 5m open, conservative same-bar stop-first, fixed ROI/horizon, and base 10bp roundtrip only; explicitly excludes funding, real book spread and queue/slippage, so actual future executable PnL unverified.
4. **Hypothetical volume-as-depth**: `available_market_depth_usdt` in V6 dataset is derived from last candle traded value divided by 100, NOT historical order-book depth. Must not call it fillability proof.
5. **Ranker/portfolio timing gap**: `learn_and_rank` invokes `choose_global_opportunity(... portfolio_has_open_position=False)` for every 5m decision. Later separate **native Freqtrade** backtest enforces `max_open_trades=1`. The ranker forecast stage is therefore not a complete dynamic capital-occupation policy; avoid presenting its proposed trade count as realizable PnL. V7 needs a chronological portfolio state.
6. **Family scope differs**: `m2r_v6_global_dataset.py` generated **eight** families; ranker synthetic test checks a known family library of **ten** names. Do not claim actual 25×10 model outcomes on the basis of a 25×8 dataset.
7. **Limited historical eligibility**: universe M5A selector has good live as-of and model-ready checks, but the historical proxy uses 75 *currently listed* symbols and confirms survivorship bias. G1 must build historically eligible delisted-inclusive as-of universe or flag unobserved markets explicitly.
8. **Risk of contaminated holdouts**: V6 evaluated/revisited July–September repeatedly. V7 cannot rename the same months an untouched final evaluation.
9. **Unresolved bias/fill warning**: V6 M2 lookahead FreqAI official audit still flagged changed prediction/entry columns, exact historical spread/fill unknown. V7 should not inherit a “validated” certificate.
10. **Confusing technical completion with edge**: 914,878 V6 proxy candidate labels existed; four global windows generated **zero actual selected/native trades**. After-cost original strategy families were negative; no economic approval.

## V3–V6 economic evidence — documented, not newly rerun

| Evidence | Historical report result | Limitation |
|---|---|---|
| V6 M1 | 25/25 candle files passed basic audit; FreqAI model fitting ran | Infra, not profits |
| V6 M2 | Final **NO-GO**; lookahead/fill uncertainties | Do not promote |
| V6 Stage1 | 63/63 planned jobs completed; 0/8 standalone families positive on after-cost studied period | Strategy entry-edge blocker |
| V6 Stage3 global | 12/12 jobs; 914,878 labels; **zero** native entries in all test windows | Censored by confidence/uncertainty/risk/edge gates |
| V6 no-time exit | 64 native runs; 0/16 uninterrupted portfolio variants positive under 25bp additional stress | Longer hold alone not cure |
| V6 exact 1% trail | 8/8 worse than earlier trailing; 0/8 profitable | Freeze negative exit experiment |
| V6 M5A | 75 survivor symbols, 234 eight-hour points; unstable market-quality gain | No valid dynamic selector edge proof |

Original sources retained in [V7_LEGACY_EVIDENCE_LEDGER.md](V7_LEGACY_EVIDENCE_LEDGER.md); see especially `M2_EVIDENCE.md` and `evidence/m2r/2026-10-19-*-final-*.md`.

## G0 output: keep/adapt/new

**Keep / version / unit-test first:** V3 data/event replay + immutable ledger; V4 LambdaRank grouping and challenger governance; V5 paired fill/exit accounting + market readiness; V6 bootstrap, native Freqtrade comparator, data/audit scaffolding.

**New V7-specific development required:**
- Full historical USDT-perpetual registry including point-in-time listing/delisting/eligibility and acquired data manifest.
- 10–15 independently diagnosed families, including old eight as negative controls (no false implication old eight are positive edge).
- Versioned **20-of-all** universe proposal with out-of-universe sampling and documented inclusion probabilities.
- Unified same-time opportunity panel with matured conditional fill-aware exit labels and liquidity/source uncertainty; no leakage.
- Adapt/retrain compare-and-rank output to utility-aware after-cost portfolio choice with NO TRADE and one occupied slot; deploy historical controls.
- Native/equivalent chronological portfolio replay with model score/time validation, stress tests and untouched forward champion gates.
- Continual performance/evidence status, reproducibility manifests and mandatory GitHub handover maintenance.

## G0 completion condition and remaining dependencies

**G0 GitHub-only audit: COMPLETE** as a source review with explicit technical reuse/no-reuse verdicts and evidence lineage above.

**NOT verified:** Private VPS Freqtrade ZIPs, raw historical feather/parquet, downloaded funding/depth data, systemd status, live state, historical execution equivalence, currently installed dependencies, model calibration on genuine fresh holdout or any new profitable portfolio. These are NOT necessary for the G0 GitHub-only audit; they are **required when claiming later end-to-end economic validation**, and may demand separate future VPS access/permission.

**No VPS access was used or required. No code changed. No training, backtest, paper or live order started.**

**Next after G0:** Owner reviews [V7_NUMERIC_GATE_PROPOSAL.md](V7_NUMERIC_GATE_PROPOSAL.md); numeric thresholds remain **proposed, not frozen**, unless the owner explicitly approves. G1 data planning before historical downloads; no automatic runtime authorization.
