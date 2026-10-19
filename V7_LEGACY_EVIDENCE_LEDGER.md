# NBOT V7 — Legacy Evidence Ledger and Reuse Register

**Freeze date:** 2026-10-19  
**Source base:** `prototype/v6-freqtrade-freqai-20261016`; prior V3/V4/V5 docs on `main`.  
**Evidence scope:** This ledger reflects **documents/source accessible in GitHub at the freeze**, not a fresh independent SSH inspection of VPS runtime, private ZIPs, trade logs or exchange fills. Preserve original evidence archives, statuses, timestamps and code hashes; independent reproduction remains a future V7 G0 gate.

## A. Findings that must constrain V7

| Prior version / evidence | What the archived source actually says | Implication for V7 | Status |
|---|---|---|---|
| V3 broad counterfactual research | Detailed accepted/rejected LONG/SHORT outcome paths, broad scan vs ~20-symbol precise-path capture, uncapped shadow research ledger, separate actual PnL | Reuse event identity, matured-label semantics, source quality and 20-symbol resource idea | Documentary evidence; audit implementation |
| V4 research factory | Virtual research book, outcome memory, champion/challenger training and forward gate; separate one-position paper contest | Reuse governance and forward data discipline; do not claim every prior proposed component survives in current code | Documentary evidence; audit current implementation |
| V5 paired exits | Same qualified entry with independent frozen policy arms, path ambiguity, fee/slippage/funding cost accounting | Reuse same-entry fair exit comparison and fail-closed tick semantics; V7 must avoid endlessly re-optimizing exits | Design/prototype evidence |
| V6 M1 | 25/25 historical pair data integrity basic checks, 25 model fits, FreqAI research runs on a constrained VPS | Existing 25-coin dataset and training setup may accelerate G0/G1 | Technical feasibility proven for that bounded workload, not economic viability |
| V6 M2 | AI/non-ML benchmark, actual native fees, modeled spread/impact stress, native funding reconciliation; official FreqAI lookahead flagged differences, true fills unverified | Keep execution uncertainty and leakage warning on V7 blocker ledger | Official M2 gate **NO-GO** |
| V6 Stage 1 | 63/63 jobs completed, eight standalone strategy families negative in native after-fee results across investigated July–September; native extra-cost stress also negative | The old eight families are controls, not presumptive V7 alpha | Negative economic evidence |
| V6 Stage 3 global 25×8 | 914,878 historical labeled candidates, model forecasts; 12/12 planned runs completed; every one-slot native portfolio took **0 trades** because gates rejected every opportunity | **Do not assert V6 only trained on the executed one trade**. Diagnose entry labels, true conditional alpha, calibration and probability/uncertainty gates | Technical simulation existed; economic proof absent |
| V6 global design audit | 50% win-probability gate, conservative residual and cost penalties, proxy-label mismatch, and lack of pristine unseen proof identified | Pre-register ablations; optimize for expected net payoff & opportunity cost instead of hard win probability | Documented diagnostic causes; causal importance to be tested |
| V6 exact 1% trail | 8/8 native A/B tests completed, 0/8 families positive, 8/8 worse than original trailing; no new exit variant requested | Freeze old exit experimentation and baseline; do not call exact 1% trailing a V7 winner | Negative after-cost evidence |
| V6 M5A rotating universe | 75/75 historical hourly data acquired; 234 matched review points, unstable September/October proxy improvement; NOT an actual one-slot strategy PnL proof | Historical whole-market universe selection may help *eligibility*; directional edge must be measured, not assumed from volume/volatility | Proxy research only |
| V6 proposed edge-first integration | Explicit separation of broad as-of universe selection from entry-quality ranker and 1-slot native portfolio | Carry this architecture into V7 and refine 20-pair contract | Approved research direction, not proven strategy |

## B. Evidence links — original, unchanged

### V6 on preserved source branch
- [V6 global opportunity selection design](V6_GLOBAL_OPPORTUNITY_SELECTION_DESIGN.md)
- [V6 strategy library and queued research summary](STRATEGY_LIBRARY_V6.md)
- [V6 M1 technical evidence](M1_EVIDENCE.md)
- [V6 M2 final NO-GO and lookahead/fill blockers](M2_EVIDENCE.md)
- [V6 Stage 1 final — eight negative strategy families](evidence/m2r/2026-10-19-stage1-final-research-report.md)
- [V6 Stage 3 final — 25×8 candidate labels, zero AI-selected/native trades](evidence/m2r/2026-10-19-global-25x8-native-recovery-final-report.md)
- [V6 native exit + global selector design audit](evidence/m2r/2026-10-19-trailing-exit-and-global-ai-design-audit.md)
- [V6 exact 1% activation trailing A/B — eight negative native trials](evidence/m2r/2026-10-19-exact-one-percent-trailing-final-eight-native-report.md)
- [V6 75-market M5A historical proxy final](evidence/m2r/2026-10-19-m5a-75-market-historical-replay-final-findings.md)
- [V6 integrated universe + entry-quality research direction](evidence/m2r/2026-10-19-universe-selector-and-edge-first-integration.md)
- [V6 edge-first AI research plan](evidence/m2r/2026-10-19-proposed-edge-first-ai-research-plan.md)
- Relevant existing research code: `scripts/m2r_v6_global_dataset.py`, `scripts/m2r_v6_global_opportunity_ranker.py`, `scripts/m2r_v6_global_native_recovery.py`, `scripts/m5a_universe_selector.py`, and associated tests.

### V3, V4, V5 history on main (do not rewrite)
- [V3 broad counterfactual research specification](https://github.com/samqju/Nbot/blob/main/docs/NBOT_V3_WSS_BROAD_COUNTERFACTUAL_SPEC.md)
- [V3 detailed accepted/rejected outcome learning](https://github.com/samqju/Nbot/blob/main/docs/DETAILED_OUTCOME_LEARNING.md)
- [Legacy main position plus ten-shadow account engine](https://github.com/samqju/Nbot/blob/main/docs/SHADOW_TRADING.md)
- [V4 research factory and champion/challenger milestones](https://github.com/samqju/Nbot/blob/main/docs/NBOT_V4_RESEARCH_FACTORY.md)
- [V5 paired exit research lab](https://github.com/samqju/Nbot/blob/main/docs/V5_PAIRED_EXIT_RESEARCH_LAB.md)
- [V5 market intelligence architecture](https://github.com/samqju/Nbot/blob/main/docs/NBOT_V5_MARKET_INTELLIGENCE_ARCHITECTURE_AND_ROADMAP_2026-10-13.md)
- [V5 evidence lineage contract](https://github.com/samqju/Nbot/blob/main/docs/EVIDENCE_LINEAGE_CONTRACT.md)

**Branch discovery on 2026-10-19:** existing `main`, V5 feature/deploy branches, `v6/review-base-20261016`, and `prototype/v6-freqtrade-freqai-20261016` found. No branch with `v3` in its name was returned by branch search; V3 docs remain on main. The V4 materials are present in main even without a standalone `v4` branch returned by search. Therefore do **not** imply all historical V3/V4 branches still exist.

## C. Reuse priority matrix

| Target V7 component | First inspect | Reuse decision required |
|---|---|---|
| Full market discovery, point-in-time eligibility | V6 M5A scripts + V3 broad WSS research + V5 exchange readiness | Needs coverage extension to all historical USDT-settled perp contracts; old 75-market proxy not enough |
| Strategy candidates | V6 eight-family library | Keep frozen negative controls; add 2–7 truly distinct families only with causal test contracts |
| Simultaneous independent outcomes | V6 25×8 dataset/model code + V3 counterfactual ledger | Distinguish proxy labels vs price-path evidence vs actual fills; preserve all entry alternatives |
| Candidate scoring / NO TRADE | V6 global ranker; V3 comparative score/gap; V4 champion/challenger | Remove unexplained binary cutoffs only through predeclared comparison; no forced positive trades |
| Trade replay | V6 native Freqtrade adapter + V5 paired-exit replay | Demonstrate native-equivalent fills, funding, fee parity, stop chronology and same-candle handling |
| Model governance | V4 challenger control, V5 source/provenance gate, V6 purged split scripts | Immutable version hashes, completed label cutoffs, embargo, rollback |
| Runtime architecture | V3 low-resource scanning, V6 official 2vCPU/6GiB research checks | Broad inexpensive scanner and targeted heavy processing; fail-closed and no execution authority by default |

## D. Exact discrepancies to investigate in V7 G0

1. **One-slot trading vs all-candidate learning:** verify whether V6's 25×8 labels were genuinely stored for *all simultaneously eligible long/short strategy candidates*, and which entries were omitted by eligibility/candle rules. The prior narrative 'only one trade was run, thus no comparisons existed' is incomplete.
2. **After-cost economic signal:** determine whether candidate labels are mostly negative because strategies lack alpha, targets/exits mismatch payoff opportunities, adverse costs, regime misfit or flaws in proxy path chronology. Never infer alpha by merely forcing more trades.
3. **Model gating:** inspect how the >=50% calibrated-win gate, downside reserve, residual confidence adjustment, regime-side agreement and minimum conservative net edge contributed to universal NO TRADE. Test each gate only on predeclared non-leaking development folds and separate new unseen evidence.
4. **Unselected coins:** verify whether M5A's historical out-of-universe controls contain real qualified strategy/side entry outcomes; if not, first make missed-opportunity rate measurable.
5. **Official lookahead:** reconcile M2 flags against specific features, model fit cutoffs, prediction revisions, and native replay. No deployment pass without closure.
6. **Microstructure:** actual book spread/queue/fill/stop slippage and account fees were never fully proven from old public data. Record scenario assumptions and uncertainty bands, not fictitious exact fills.
7. **Holdout contamination:** July–September are already inspected. V7's initial three-month split may be engineering development-only; reserve a genuinely fresh later period as a blind economic test.
8. **Policy freeze:** V6 trailing family comparisons do not permit retrospectively swapping in whichever policy looks best. Preserve selected common exit policy and compare on independently new evidence.
9. **Prior V3/V4 reusable source:** compare historical docs to actual corresponding branch/main commits rather than assuming written architecture was ever deployed as advertised.

## E. Evidence management rules

- Each reused component must have: `origin_branch`, `origin_commit_sha`, `original_report_path`, `artifact_sha256` (if available), `scope`, `reproduction_command`, `verified_result`, `known_limitations`, `reuse_verdict`, `V7_test_id`.
- Evidence claim levels: **proposed**, **documented as implemented**, **unit tested**, **native historically replayed**, **independently reconciled**, **untouched forward validated**, **accepted**. Do not silently upgrade a claim.
- Historic virtual PnL never equals executed wallet return. A selected order that was not fillable must remain unresolved/rejected, not a simulated perfect fill.
- Never delete or replace an original failed audit. Supplemental fixes get new paths and new timestamps.
- If the evidence needed for a claim is unavailable, record **unknown/unverified** and retain the no-go gate.
- All V7 experiments must write fresh versioned artifacts, not modify old V6 results.

## F. Freeze outcome

The technical work from V3–V6 is **not discarded**. The negative economic results are **not ignored**. The next measurable hypothesis is:

> With point-in-time whole-market eligibility, a bounded 20-pair detailed universe, independently simulated eligible trade paths, and a leak-free after-cost cross-sectional ranker, can a truly capital-constrained one-slot V7 portfolio outperform simple selectors, the historical V6 approach and NO TRADE on fresh untouched periods?

Until that hypothesis clears data, causality, economics and forward paper gates, **V7 remains a research project with zero live authority**.
