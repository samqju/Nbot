# NBOT V7 — Approved 9-Month Engineering Experiment and New Branch Implementation Contract

**Recorded:** 2026-10-20 IST  
**Owner agreement:** Build an end-to-end V7 research system in new branch `V7`, selectively port V3/V4/V5/V5.1/V6 code, then perform a nine-month historical experiment with adaptive brain replacement. **Do not connect/deploy to the VPS until coding is complete and local/CI tests establish technical readiness.** Paper/live trading is separate and remains unapproved.  
**Repository:** [samqju/Nbot/V7](https://github.com/samqju/Nbot/tree/V7)  
**Frozen predecessor:** [Original V7 roadmap](V7_ROADMAP.md); [adaptive brain proposal](V7_ADAPTIVE_TRADING_BRAIN_PROPOSAL.md); [G0 source audit](V7_G0_LEGACY_AUDIT_2026-10-20.md).

## Owner's final experiment design

1. **Months 1–3:** Train Brain A on matured, causal, after-cost comparative outcomes across historically eligible markets. Record rich feature labels, including BTC as-of context and future MFE/MAE/exit outcomes separately.
2. **Months 4–6:** Freeze A and chronologically evaluate its decisions and unselected opportunities using a one-slot capital model and up-to-20 watch symbols. No fitting to these 3 months during A's examination.
3. **After month 6:** Freeze A. Train **B1**, identical architecture with six months' matured evidence, and **B2**, a contextual adaptive challenger that can change trading style/regime preference and abstain.
4. **Months 7–9:** Simultaneously but independently replay A, B1 and B2 using their own capital-constrained one-slot accounts over identical synchronized histories, preserving all rejected shadow outcome data. Determine whether extra data and/or adaptive architecture measurably improves decisions after costs. Compare simple and NO TRADE baselines.
5. **Baseline may be positive or negative.** Engineering success means system functioning, not presumed alpha. Statistically significant positive economic uplift in genuine unseen periods is a separate promotion gate. Re-running an already inspected nine-month dataset hundreds of times does not confer new unseen evidence.

## Engineering implementation state (as of initial V7 coding 2026-10-20)

| Area | Initial V7 branch state | Limitations / next proof |
|---|---|---|
| Branch and docs | **CREATED** branch `V7` from roadmap branch; legacy docs preserved | This document and handover record overrides for experiment only; original roadmap remains historical founding freeze |
| V3 replay + ledger | Selected exact legacy module blobs copied, imports verified by CI | Not yet deeply integrated into all 5m and 1m paths |
| V5 exits | Select paired-exit/accounting source blobs copied | 5m research proxy in V7 isn't native Freqtrade fill equivalent |
| V5.1 data governance | Selected learning/source modules copied, imports verified by CI | Caller source claims alone do not prove historical exchange eligibility |
| V4 ranking | **ADAPTED** event-grouped LightGBM LambdaRank and return regressor | Economic uplift, calibration, alternative expert models unproven |
| Broad USDT market history | Read-only public Binance Vision metadata listing / bounded ZIP download module coded | No source inventory or nine-month download performed; lifecycle from ZIP presence != historical tradeable status |
| Causal feature/entry opportunities | BTC and coin past returns/volatility/structure and 11 proposal families | Simplified V7 candidate proposal families; inherited V6 families are historical negative controls and not automatically winning |
| Shadow labeled database | SQLite per-symbol/time candidate labels and watch selection targets; MFE/MAE; path-quality and source digests | OHLC first-touch **proxy**, no verified historical orderbook, funding, precise fill path; future outcome labels separate from features |
| 9-month brains | A train months1-3, A B-window exam, B1/B2 train 1-6, A/B1/B2 C-window exam, independent one-position wallet | Not yet independently proven on real nine-month exchange history |
| Automated regression | GitHub Actions source compile + **nine offline tests passing** as of 2026-10-20 | Synthetic tests are not trading edge, broad stress, archive coverage or native equivalence |
| VPS deployment | **NOT STARTED** | Wait until source and validation gates pass and owner confirms research-only deployment scope |
| Paper/live | **NOT AUTHORIZED** | Separate gates later |

## Prescribed frozen prototype policy — do not present as live strategy

V7 current software uses a documented *engineering-only* 5-minute candle proxy: next-open entry; adverse-first on a candle touching both +3% target and −2% stop; 60-minute maximum holding; 0.05% entry and exit fees; 1bp modeled entry and exit slippage; additional +0.25% roundtrip stress in post hoc tests. **Funding is not accounted for with verified historical settlements and the no-longer-recommended +1% exact trailing stop is NOT treated as a winning V7 policy.**

The A/B/C results must explicitly carry `OFFLINE_5M_PROXY_NOT_ACTUAL_NATIVE_EXECUTION` and cannot satisfy G5 economic proof or paper/live approval. A complete G5 native economic study needs real source provenance, complete funding/mark and execution scenario sensitivity; ambiguous intrabar sequences must not be scored as certain.

## Strict code provenance and branch safety

No blanket merge of main or V5.1 into V7. Initial selective copies:
- `nbot/observation/{decision_ledger,chronological_replay,counterfactual,research_replay}.py` from main V3;
- `nbot/observation/{v5_accounting,v5_paired_exits}.py` from main V5;
- `nbot_v5_1/{core,research_intent,learning_contract,learning_science}.py` from `nbot-v5.1`;
- V6 `scripts/*` archive discovery and native harness retained in base.
- Brand-new package `nbot_v7/` is research-only and has no live exchange order authority.

Exact copy blob IDs are in [G0 legacy audit](V7_G0_LEGACY_AUDIT_2026-10-20.md); model/label contracts are in the source and [V7_README.md](V7_README.md).

## Numeric gates and no shortcuts

The existing [proposed G0–G8 numerical matrix](V7_NUMERIC_GATE_PROPOSAL.md) remains a **proposal until explicitly owner frozen**. Never silently lower risk/data-confidence gates because the first nine-month results are disappointing. An engineering passing CI is **not** G5 pass.

Explicit blockers to code-complete research go/no-go:
- Prove point-in-time historical lifecycle eligibility (including delisted contracts) and source coverage for all markets.
- Verify no lookahead in **both** universe-target and current entry-target label generation.
- Verify 5m model output and detailed 1m/tick/native/funding cost behavior; quality tier every label.
- Complete meaningful matched simple selector baselines and stability/statistical confidence analyses (V4's original thresholds aren't V7 proof).
- Audit resource/time budget on actual 150–300 market nine-month workload and bounded disk retention.
- Ensure no real exchange API, order authority, auto-model promotion or paper deployment is bundled into this research stage.
- Keep [V7_CHAT_HANDOVER.md](V7_CHAT_HANDOVER.md) synchronized after each material action, failure, test and decision.

**Current outcome:** The original complete request is still IN PROGRESS. Nine-month engineering code exists and nine synthetic offline tests pass on GitHub CI; a **fully verified real-exchange research system** has NOT been established. The VPS has not been touched.
