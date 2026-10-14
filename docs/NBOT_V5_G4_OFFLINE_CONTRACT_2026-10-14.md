# NBOT V5 — G4 offline counterfactual contract v0.1 (NOT operational acceptance)

**Date:** 2026-10-14; **source ancestry:** immutable integrated G1/G2/G3 SHA `1e7c090d05dc118b290c764d58c2944f56ad4b3b`; **branch:** `feature/v5-g4-offline-contract-20261014` (temporary; no VPS worktree). **Stage status: G4 DESIGN AND SYNTHETIC SOURCE-PREFLIGHT ONLY.** This document does not amend the approved live release or grant paper, training or real-order authority.

## 1. Strict dependency and sample truth

G1 existing isolated 12h evidence PASS remains valid within its limits; the *new integrated* G1 24h soak beginning 2026-10-14 06:46:04 UTC remains PENDING until independently accepted no earlier than 2026-10-15 06:46:04 UTC. G2 original market witness and G3 BTC/coin context had initial technical/operational PASS on bounded genuine events. Neither G2/G3 generates prices after candidate entry, matured virtual outcomes, fill evidence or trade profit. Source-qualified candidates and market context MUST NOT count toward the proposed 2,000-matured learning target. Operational G4 must not start until the integrated gate and independent G4 source specification are accepted.

## 2. Canonical interpretation and record relationships

One frozen five-minute event has an observed frozen top-50 denominator (BTC included at existing pin), **100 coin × direction candidates**, original G2 quotes/trade receipts and one G3 event context. The 24 detector tags annotate each candidate and are **not 24 independent trades**. Candidate `decision_id`, event, symbol, side, frozen top-50 membership, G2/closed-bar digest, G3 feature SHA, detector/catalog versions and pre-decision timestamps must match EXACTLY. Missing candidate, source, BTC context, policy or path => withheld research label, never silent deletion, negative return or zero-value imputation.

Proposed immutable research label key: `(decision_id, frozen_policy_sha256, label_contract_version)`. A different policy is an explicit independent *counterfactual label*, not another independent candidate/trade. Persist all eligible and unselected cases with blocker codes; store source manifests and per-event/market interdependence. Terminal status `SCORED` requires independently reproduced path and verified net-economic calculation; `UNRESOLVED` means missing/contradictory required evidence, `CENSORED` means declared horizon/exit cannot be fully observed, `PENDING` means maturity not yet reached. Terminal transitions must be single-assignment with append-only corrections, never contradictory scored+unresolved dual terminals.

## 3. Twenty-four tagged hypothesis specifications (not profitability claims)

Initial detector implementation is the already-approved, digest-pinned `nbot/v5/pattern_adapter.py` and frozen imported V4 *definitions* only. No re-interpretation, indicator retuning, expanding historical lookback or importing old V4 profitability/selection logic. Validity requires 49–96 contiguous fully closed 5m bars, original G2/G3 timestamps, valid quote/trade receipts, frozen universe and side, and no future candles or unconfirmed pivots.

| Hypotheses | Pattern IDs | Preconditions and regimes to stratify (pre-registered hypotheses, NOT confirmed advantage) |
|---|---|---|
| Momentum | TREND_CONTINUATION_V1, EMA_CROSS_V1, MACD_CROSS_V1, MULTITIMEFRAME_TREND_V1 | completed cross/return/multi-timeframe data; test BTC trend, transition and shock |
| Pullback | TREND_PULLBACK_V1, EMA_PULLBACK_V1 | confirmed trend plus as-of-decision retracement; test trend versus range |
| Breakout | VOLATILITY_EXPANSION_V1, DONCHIAN_BREAKOUT_V1, BREAKOUT_RETEST_V1, SQUEEZE_BREAKOUT_V1, VOLUME_BREAKOUT_V1, INSIDE_BAR_BREAKOUT_V1 | valid past-only extrema, ATR, volumes and retest chronology; test compression, shock, BTC stress |
| Reversal | STRETCHED_REVERSAL_V1, FAILED_BREAKOUT_V1, OUTSIDE_BAR_REVERSAL_V1, ENGULFING_REVERSAL_V1, PIN_BAR_REJECTION_V1 | closed confirmation candles and structure, no post-decision pivot; test transitions versus trending BTC |
| Mean reversion | RANGE_EDGE_REJECTION_V1, BOLLINGER_REENTRY_V1, RSI_RECLAIM_V1, VWAP_RECLAIM_V1 | source-complete range/band/RSI/VWAP features; test ranges and trend breakdown |
| Relative momentum | RELATIVE_STRENGTH_V1, BTC_RELATIVE_MOMENTUM_V1 | point-in-time comparative 50-coin coverage; latter requires explicit BTC valid/fresh; test BTC/coin divergence |
| Structure | CONFIRMED_SWING_CONTINUATION_V1 | swing confirmed only using candles already closed at decision; test trend/transition |

Both LONG and SHORT are independently represented for every 5m coin candidate. Exact detector-side conditions, fixed indicator thresholds and rules version follow the pinned adapter/library; the table above only defines future analysis strata, not new live detector logic. `UNAVAILABLE` is distinct from `NO_MATCH`. A matched technical rule does **not** imply a permissible economic entry.

## 4. Frozen labels, maturity and strict evidence tiers

Before seeing future price movement, freeze an entry reference convention (bid/ask and timing), the risk/invalidation geometry, exit policy, horizon (initial synthetic fixture = 4h, not yet authorized as live research policy), side, quote-age thresholds, cost policy, fee tier assumptions, funding logic, and funding interval. Record `declared_at_ms <= decision_at_ms` with SHA256 digests. Never select the best exit retrospectively and call it the predeclared policy.

Separate grades, NEVER cross-label them:
1. `HISTORICAL_AGGTRADE_PATH`: original-price chronology/digest verified, complete covered horizon and gap accounting. **NOT** an executable bid/ask trade or actual fill; no execution-level profitability claim.
2. `QUOTE_CONSTRAINED_SIMULATION`: additionally verified chronological bid/ask receipts, quote age, fee schedule, explicit slippage/impact bounds, funding accrual/coverage and fee/R calculation. Costs unknown => HOLD, never default to zero.
3. `FORWARD_PAPER`: independently accounted future Execution VPS portfolio trades. NOT G4 historical-source replay and not fungible with virtual research rows.
4. `REAL_EXCHANGE_FILL`: genuine exchange-accounting grade, unavailable and never authorized by this change.

Final economic net-R (future independently reviewed labeler only) requires a nonzero, side-correct **initial risk distance**, frozen realistic entry/exit, fees, spread, slippage, funding when applicable, rounding/minimum tick/lot conventions and a gap/stop ambiguity policy. Gross = side-adjusted price move / initial risk distance; net = gross - conservative actual/modelled costs/R. Ambiguous intrabar stop/take-profit ordering must apply a frozen pessimistic or CENSORED treatment, not choose whichever wins. No trade / ABSTAIN benchmark = **0R**, and genuine invalid costs cannot be interpreted as profitability. This change implements **no return calculation**, fill inference, scoring or ledger mutation.

## 5. Offline-only function and tests

`nbot/v5/g4_offline_gate.py`: deterministic `assess_replay_prerequisites` returns ONLY `PENDING`, `HOLD` or `REPLAY_READY` and always `scored_outcomes=0`, `order_authority=NONE`, `recommendation_authority=NONE`, `training_authority=NONE`. `REPLAY_READY` **never** means `SCORED`; it merely allows a distinct future independent original-source replay. Required inputs are qualified candidate with all 24 pattern states, same-event causal G3 context digest, predeclared versioned policy, maturity clock, SHA-checked contiguous price path, and cost sources for quote-grade claims.

`tests/test_v5_g4_offline_gate.py` uses synthetic fake digests and time series contracts only: positive and negative paths, not-matured, gap, late data, mismatched event, missing BTC/G3/source, unfrozen policy, unavailable detectors, cost/funding and quote-grade refusal, unrelated forward-paper grade, both side/tag overlap, no order or label creation. No production data read or server changes. *A passing unit suite is not G4 scientific acceptance.*

## 6. Acceptance work remaining, in strict order

1. Finish current uninterrupted integrated G1 24h operational gate and independent G2/G3 replay; continue safe G4 offline mocked tests without altering production.
2. Prespecify original policy/risk/exit choices, costs, funding, entry/exit witness clocks and path archive sources *before* deriving outcomes. Independent reviewers must assess source authenticity and realistic fill-grade feasibility.
3. Build isolated original Binance aggTrade/path retrieval and immutable receipt hashes; deterministic independent replay with explicit gaps, late or conflicting data, outages and source epochs. Never backfill an old window without a separately marked historical origin and compatible proof.
4. Implement future append-only SQLite G4 research ledger *separate from the running collector*; maturity calendar, idempotent terminal exclusivity, independent source verification and no-trade baseline. No counterfactual ledger deployed now.
5. Scientifically audit coverage, rejected/censored cases, after-cost uncertainty, event correlation, regime/sides and unselected denominator before requesting G4 operational GO. Then advance to G5 baselines; only later consider 2,000 quality-matured outcomes, training and Execution paper portfolios.

## 7. Infrastructure/rollback and explicit exclusions

This temporary Git branch descends from the accepted integrated SHA and creates **no** worktree, new permanent VPS folder, SQLite, service or scheduler. Running collector remains pinned and immutable; on any offline regression, close/abandon this branch/PR without changing release. Never cherry-pick G4 experimental code into the running release during the soak. Governance copies and final consolidation checklist stay on `v5-clean-restart-20261013`. No V4 prototype merge, no Execution merger, no real trades, no ledger reset, no prior historical evidence deletion.
