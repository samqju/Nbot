# NBOT V5 G3 — Causal BTC Regime and Coin Structure Acceptance
**Recorded 14 October 2026 IST.**  
**Stage:** Original roadmap V5-03 / G3 (market context; no trading)  
**Overall result:** **PASS for the original G3 frozen-clock feature correctness exit requirements, on a bounded real source-qualified G2 sample and synthetic regime faults.** Operational deployment and economic-edge validation are separate future gates.

## 1. Proven branch ancestry and worktree isolation

Verified on Observation VPS using read-only git ancestry:
- Frozen G2 parent reference: `feature/v5-observation-g2-20261014` commit `af6d5a458eeca047c43d0360ce6a8fd3f76ec799`.
- New isolated G3 branch `feature/v5-observation-g3-20261014` at initial acceptance commit `d818bc173c04c4279a7f6a3dff52faff35209c99`, with Git `merge-base` **exactly equal to the G2 parent SHA**, branch divergence **0 behind, 11 ahead**.
- Distinct detached Observation VPS development worktree: `/home/ubuntu/nbot_v5_g3_audit_dev`.
- Authoritative V5 roadmap branch `v5-clean-restart-20261013` is NOT the G3 code branch; used only for documented roadmap governance and existing running G1f source. Execution branch `feature/v5-execution-foundation-20261014` remains independent/untouched; historical `feature/v5-live-evidence-recovery` prototype excluded.
- No merges into G2, Execution or active Observation code; no source-code changes to existing live `/home/ubuntu/nbot_v5_sandbox` runtime.

## 2. Implemented frozen-market contract

G3 code:
- `nbot/v5/g3_market_context.py`: independent, side-effect-free BTC global regime, altcoin-only contemporaneous 1h breadth (BTC excluded from its own breadth measure), 50-coin per-event market structure, past-only 5m/15m/1h/4h rollups, ATR14, 12/48 closes/range, strict original local WSS quote/trade generation and receipt clocks, confirmed swing highs/lows requiring TWO later bars that already closed, and versioned deterministic SHA256 outputs.
- `nbot/v5/g3_frozen_replay.py`: independent read-only G3 replay that first requires the original G2 source witness acceptance PASS, verifies 96 source candles' SHA256 and first-known/decision clocks per coin, recomputes contextual features deterministically twice, and returns HOLD if evidence, clocks or qualification fail.
- `tests/test_v5_g3_market_context.py`, `tests/test_v5_g3_frozen_replay.py`: synthetic upward/downward BTC shocks and trends, missing/stale BTC feed, zero-vs-unknown distinction, isolated invalid coin handling, BTC-excluded breadth, explicit source generation, 1h BTC-relative LONG and SHORT positive/negative/missing fixtures, no right-side candle lookahead in swing confirmation, corrupt source SHA and late-data HOLDs.
- `docs/NBOT_V5_G3_BTC_REGIME_COIN_STRUCTURE_CONTRACT_2026-10-14.md`: complete version/threshold, feature, regime taxonomy, no-hindsight reference methods, BTC-shock fixtures and data-quality/availability matrix.

### Original G3 exit conditions

| Original V5-03 condition | Independent acceptance |
|---|---|
| Causal reproducibility at frozen clocks | PASS: twice-reconstructed identical deterministic feature SHA on each qualified live event, with 96 as-of candle SHA/receipt proofs per original selected coin |
| Missing/stale BTC yields withheld/UNKNOWN, not fabricated zero | PASS: synthetic absent BTC, delayed quote/trade, bad epochs, zero ATR and price-history faults; all BTC-conditioned coin results UNKNOWN and BTC-relative tag UNAVAILABLE |
| Source-path feature availability tested | PASS: original frozen G2 rank/quote/trade sources required before G3 sample admission, plus missing/witness corruption and 80%-breadth tests |
| Regime labeling deterministic at timestamp | PASS: versioned quantitative thresholds with shock-up/down, persistent trend, range, transition, data-stale fixtures, no future swing confirmation and repeatable hashing |

**Heuristic confidence scores are NOT calibrated probabilities; regime categories are not edge claims or trade decisions.**

## 3. Real original-source-qualified G2 sample, independent read-only replay

Replayed the unchanged G2 proof database:

`/home/ubuntu/nbot_v5_g2_proof_20261014/g2_witnessed.sqlite`, SHA256 `acc7dcb1e7de9c8a7f65041dffa1ca38a267d8bfa4c252d84e8500562995664f`.

- Original two genuinely observed five-minute opens at **2026-10-14 05:45 UTC** and **05:50 UTC**. They originated from the 50-market frozen original G2 927-exchange-symbol/525-rankable/50-selected/475-excluded source witness. **Never assign states to the 475 excluded markets.**
- Two original past-only 96-bar sequences per selected market (50 x 2 = **100 qualified coin-time classifications**), **0 unknown** and **100/100** per-event source witness rows. 100 LONG/SHORT candidate slots per original event were independently verified by G2, but G3's units are COIN-EVENT contexts, NOT 200 trade outcomes.
- Both accepted BTC regime labels were **TRANSITION**, with explicitly heuristic strength/confidence score 0.4. Both were valid, not missing-data coerced neutrals. Breadth across **49 altcoins excluding BTC**: first `-0.7959183673`, second `-0.9183673469`; both available and negative (no performance assertion).
- Across the 100 selected coin-time classifications: `BREAKOUT_DOWN=33`, `COMPRESSION=24`, `TREND_DOWN=30`, `TRANSITION=13`. These are descriptive state counts, not trades or successes.
- Explicit matched BTC-relative direction-setup hypotheses: first event LONG=5/50, SHORT=40/50; second LONG=4/50, SHORT=43/50. They are tags only and may overlap strategies; **NOT 92 executed or profitable trades**.
- Frozen feature SHA256 for 05:45 UTC: `b0e80fa347fb76c8f313a8efab02d3fe4f6a4d4c42f355864381c361c59820c6`; for 05:50 UTC: `639ed0a41ca2bfe002ca9d70fd17bdef4c4e233376cb3893d109e119efb630e4`. Repeated source replay produced exactly identical codes and values; no database writes.
- No training labels, trade recommendations, orders, portfolio fills, execution credentials or online REST/WSS calls from G3. Returned `model_labels_created=0`, `recommendation_authority=NONE`, `order_authority=NONE`.

## 4. Test and live operational integrity

- Observation VPS G3-focused suites **27/27 PASS** on code commit `516745b866d83fb1768b766a1e0572f5e4ffc5f4` and completed acceptance document commit above.
- GitHub Actions V5 isolated Observation full suite **233/233 PASS**, workflow https://github.com/samqju/Nbot/actions/runs/38521549149 (same code version; documents are intentionally CI-excluded).
- Read-only G3 replay **PASS**, no source violations.
- Original G1f permanent Observation service untouched: `nbot-v5-observation-only.service` active, enabled, original MainPID 1082, unexpected restarts 0, ~106MB used versus 200MiB cap. Independently rerun G1g service/data health `status=PASS`, SQLite `quick_check=ok`, 169 accepted/held 5-minute events, 16,790 OBSERVED + 110 UNSCORABLE directional historical G1f records, seven V4 units inactive and disabled original boot entries.
- G3 code exists only in isolated feature branch and worktree; neither long-running G1f source nor Execution service was restarted, deployed or connected.

## 5. Caveats, no skipped milestones

**G3 frozen feature-correctness gate: PASS.** This is the original stage exit for reproducible BTC regime/coin structure *observation*. It does NOT prove out-of-sample regime stability, profitability or a calibrated ML probability. Real BTC shocks and unobserved network interruptions were tested as **synthetic safety fixtures**, not claimed to have occurred in the two real five-minute proof windows.

**Critical future G4 dependency:** the permanent G1f worker does not yet persist G2-source-witness data or G3 features. The accepted G2/G3 sample is only a separate, short-lived and preserved proof database. Before building or scoring genuine continuous G4 economic labels, a separately engineered, backed-up, rollout-tested persistent G2-qualified collector must collect new real source-witnessed events and preserve old G1f history without backfilling. The owner previously requested following every roadmap gate in order, so G4 outcome study/trading remains HOLD until those prerequisites are evidenced. 

**Never treat** G3 pattern-momentum matches, regime tags or 100 coin-event contexts as training outcomes, independent trade samples, paper trades, real orders, positive net expectancy or grounds to resume Execution. G5 baselines, G6 Champion/Challenger and E6B operational connection are not unlocked.

**Disposition:** G3 deterministic research classifier **technical exit PASS**, G3 *production deployment not attempted*, G4 source-qualified ongoing evidence prerequisite **HOLD**. The next user-authorized roadmap task, if advanced, is the controlled source-qualification rollout/validation prerequisite and then G4 versioned strategy-pattern/counterfactual specifications—not accelerated training.
