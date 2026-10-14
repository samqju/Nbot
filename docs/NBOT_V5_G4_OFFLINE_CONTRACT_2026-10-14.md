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

## 8. Offline implementation expansion and strict G4 hold (14 October, later checkpoint)

This *unmerged* branch now contains five G4 modules:

- `g4_offline_gate.py` freezes eligible candidate, BTC/G3 context, policy and clock, then returns PENDING/HOLD/REPLAY_READY only; G4 never creates a trade from G1/G2/G3 candidates.
- `g4_price_path.py` replays source-manifested original-format Binance public aggTrade rows `a/f/l/T/p/q/m` with canonical digest, agg-ID and underlying trade-ID continuity, frozen stop/target/horizon and side-specific Decimal gross price-path R. Missing original source/archive authenticity, data gaps, future policy, impossible geometry or future decision = HOLD. Its `PATH_REPLAYED` is NOT executable fill evidence and always `net_r=None`.
- `g4_economics.py` describes a **QUOTE_CONSTRAINED_SIMULATION** only when original as-of decision bid/ask, original exit-time bid/ask and independent fee, slippage, funding interval, source manifest and cost-version witnesses are supplied. It models conservative LONG ask-in/bid-out or SHORT bid-in/ask-out and signed funding, with Decimal net R. Its `COST_REPLAYED` is not an actual exchange fill or automatically approved SCORE.
- `g4_research_ledger.py` represents frozen independent label intents and a single immutable terminal per (candidate ID, predeclared exit/risk policy SHA); either SCORED with independently verified quote-grade source, PATH_ONLY with gross price path and no net, or CENSORED/UNRESOLVED with explicit reasons and no invented returns. SQLite tables have permanent no-update/no-delete triggers, replay-idempotence and conflicting-terminal rejection. The initializer **refuses known G1/G2/G3/historical schema tables**, and must operate only on a new isolated offline SQLite when individually approved. No G4 research DB, order service or logger is currently deployed.
- `maturity_calendar` reports the full frozen denominator including PENDING vs MATURE_BUT_UNRESOLVED, separate source-grade terminal counts and distinct five-minute event-group coverage. It **always** reports training gate unlocked=false, because a counter and clock do not prove regime diversity, independent samples or positive after-cost edge.

The code is pure/offline and the demonstrated source strings/digests in its tests are **synthetic**, including test booleans that attest authenticity. A Boolean `independently_source_verified` in mock input is **not itself a real third-party provenance proof**. A future original-data collector and independent source audit must bind actual bytes and source transport/URL/time/origin, plus original Binance trade-ID/clock/quote and funding coverage, to an independently reproducible archived SHA manifest and cutover time. Until this exists for mature G2/G3-qualified candidates, G4 operational scientific acceptance is **HOLD**. No historical V4 aggregate-only sample is used to impersonate a live executable fill.

**Latest official tests:** https://github.com/samqju/Nbot/actions/runs/38532119643 ran **332/332 PASS**, including the 247 accepted pre-G4 integrated suite and 85 new synthetic G4 tests. Draft PR https://github.com/samqju/Nbot/pull/39 remains **unmerged** and must not automatically deploy. The live integrated Observation service is still pinned at 1e7c090d05dc118b290c764d58c2944f56ad4b3b. There is **no operational G4 source ingestion, after-cost trading ledger, paper trading, model training, or real-money permission**.

### Operational closure criteria remaining (stop/go, not optional)

1. Independent >=24h G1 integrated runtime and continuous G2/G3 source-quality acceptance no earlier than Oct 15 2026 06:46:04 UTC; journal/time/5m-event and quote/feature replay audited with no shortcut.
2. Predeclare and lock actual virtual research entry, invalidation, exit and horizon policies plus cost/fee/funding conventions *before future observation*, including restart/censoring treatment, quote freshness, exposure and minimum independent event/regime diversity.
3. Recover actual original after-decision aggTrade chronology from trusted Binance archives or separately bounded public-source acquisition, with independently attested SHA, trade-ID/gap proof and event/coin/source epochs; preserve missing/corrupt outcomes as explicit holds.
4. Independently source and validate quote/funding/fee coverage and realistic after-cost sim bounds. Forward paper actual fills remain a separate future Execution evidence grade.
5. In an isolated, versioned research dataset (never the current active observation database), run real case-to-terminal replay, redo independent price-path/time and cost calculations and prove immutability/restart/restore on source-authentic entries, with full eligible candidate denominator including nontrades, PENDING, CENSORED, UNRESOLVED and PATH_ONLY.
6. Record a reviewed G4 scientific GO/HOLD using real source evidence, selected/unselected coverage and attrition, cost/R uncertainty and distinct event/regime groups. Even a future G4 PASS does **not** mean 2,000 qualified outcomes, proven after-cost edge, training approval, or permission to enter G6/G7+.

**Do not extend the 24-hour soak without cause, but do not call the G4 offline suite a complete operational G4.**

## 9. Original G1/G2/G3 snapshot binding and archive integrity expansion (2026-10-14)

**This is OFFLINE verification development only; operational/scientific G4 remains HOLD.** New `g4_source_binding.py` opens a pre-made SQLite snapshot in `mode=ro`, never initializes a schema or changes the active collector. It ties one researched coin/side to the **entire 50-coin/100-direction cohort**, validating all candidate record SHA digests, mandatory selection snapshot, frozen event manifest, matching original G2 quote/trade witness clocks and hashes, and the G3 top-level and nested feature digests. A missing/corrupted unrelated coin or side holds the event rather than silently shrinking the denominator. Its output is `SOURCE_BOUND` or `HOLD` and permanently reports zero scored outcomes, no model/training, no recommendation/order authority. `SOURCE_BOUND` is local-original WSS/REST observational evidence, NOT an exchange-signed source, original daily aggTrade byte provenance or a fill. It deliberately refuses to be interpreted as after-cost trade proof.

The existing original Binance daily archive ZIP parser `g4_archive_import.py` now has separate tests for checksum identity, ZIP traversal/multi-member content, corrupted original bytes, canonical trade IDs and underlying trade-ID gaps, time reorder, malformed fields and unsupported one-row paths. Its input ZIP + companion checksum are supplied by the caller; hashes match one another but **original HTTPS origin and capture custody have not been independently proven by that alone**. Its output explicitly retains `original_archive_verified=False`. Do not flip that Boolean without an independently captured transport/provenance record and reviewed archive SHA. Real G4 adoption requires authenticated source acquisition, cross-check against actual selected event/clock, source epochs and both original price and quote/funding evidence; an arbitrary user-created ZIP + matching checksum never suffices.

**Independent GitHub CI:** G4 branch head `b5a8bf4d2db96d58ae21d42897d85978692681a7`, https://github.com/samqju/Nbot/actions/runs/38535274905, **367/367 PASS**. This expands prior 332 to 18 synthetic G1/G2/G3 binding tests plus 17 synthetic archive importer tests. No new server folders/services, original DB write, live branch merge, or G4 economic outcome occurred.

**Operational blockers remain non-negotiable, even after 367 tests:**
- The integrated G1/G2/G3 service began its distinct 24h soak Oct 14, 06:46:04 UTC and may only be independently accepted no earlier than Oct 15, 06:46:04 UTC with continuous evidence.
- A real archived/recorded aggTrade *price path* must span the full frozen decision-to-exit/horizon with authenticated original byte provenance and agg+underlying-trade ID continuity; the current service persists candle closes and 5m original G2 source witnesses, not a complete continuously witnessed post-decision trade tape.
- Price path alone does **not** deliver bid/ask at an arbitrary stop/target exit, historical executable order fills, known funding or exchange fees. The present at-event G2 source snapshots cannot retroactively create those. Prospective independent quote-cost/funding coverage is needed for credible after-cost `SCORED` grade; otherwise `PATH_ONLY`, `CENSORED`, `UNRESOLVED`, or `PENDING` remains correct.
- No actual versioned original entry/stop/target/risk/exit/maturity policy has yet been locked before *future* observation; synthetic tests' past-clock declarations are not independent original timestamp proof. Define/approve the real prospective policy and original trade path collection before claiming a G4 source-qualified economic label.
- Even with correct price replay, no batch can automatically approve scientific G4: independently reproduce source/economics, record source grade & attrition, all unselected denominators and correlated regime/event blocks, and complete formal acceptance. 2,000 matured outcome threshold and G5/G6 remain separately gated.

After the existing Oct 15 review, if G1 passes, proceed with a **separate isolated G4 evidence acquisition design and approved deployed component**, without modifying the frozen G1/G2/G3 collector or its current SQLite. Preserve all original G1/G2/G3/G1f/F0 records and version G4 research/paper ledgers separately. Do not rewrite observed candidate clocks to fabricate predeclared policies.
