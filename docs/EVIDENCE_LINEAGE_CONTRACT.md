# Evidence Lineage Contract

Current learner applicability reviewed 2026-10-01 at `9fff54c`. The
[learned-Testnet contract](LEARNED_TESTNET_CONTRACT.md) permits experimental
Testnet proposals from LIVE features; Testnet outcomes remain operational only.

Status: V3.9 implemented lineage contract; V3.9 economic proof remains open.

The canonical implementation authority remains `docs/NBOT_V3_ROADMAP.md`. This document describes implemented lineage boundaries; it does not create research, paper, or execution authority.

## 1. Permanent evidence separation

V3 keeps evidence classes physically and logically distinct.

- TESTNET is operational evidence only.
- LIVE canonical market evidence owns research truth.
- LIVE_PAPER operational evidence cannot retroactively rewrite frozen research windows.
- Research Champion is not automatically Paper Champion.
- Research or Paper Champion labels do not themselves bypass Execution safety authority.

## 2. Canonical LIVE raw evidence

Canonical research truth originates from the Observation LIVE database:

`data/observation/live/observer.db`

The collector stores completed 5-minute market events with point-in-time market/universe context and durable provenance. Research eligibility requires the necessary decision-time information to have been genuinely available at the decision clock.

Historical recovery may restore objectively available candles/funding evidence, but historical bid/ask, spread, ranking or other point-in-time context must never be invented.

## 3. TESTNET lineage

TESTNET outcomes are `TESTNET_OPERATIONAL_ONLY`.

They may prove order mechanics, idempotency, stop protection, reconciliation, failure/restart behavior, and protocol behavior. They cannot create or promote a LIVE Research Champion and are never merged into canonical LIVE economic proof.

## 4. LIVE_PAPER lineage

LIVE_PAPER uses LIVE public market truth with local paper execution. Its operational outcomes are linked through versioned proposal/outcome identity. Operational canary evidence does not become research proof merely because it uses LIVE prices.

Sustained Paper Champion evidence remains blocked until a legitimate Research Champion exists.

## 5. Compact research memory and 96-event epochs

V3.9 compacts mature canonical LIVE evidence into `data/observation/live/research_memory.db`. `RESEARCH_MEMORY_V1` advances through durable 96-event research epochs.

Each successful epoch proves its compact-memory commit before the epoch-to-challenger transition becomes eligible. The research build workspace is disposable. Durable lineage includes compact research memory, epoch commit identity, source/training digests, cumulative Ridge state, challenger/model artifacts, immutable evaluations, and governance records.

The generation floor prevents pruned/pre-generation history from silently re-entering the current research workspace.

## 6. Epoch-to-challenger lineage

A challenger opportunity is tied to a genuine durable epoch commit, not to every 15-minute research timer invocation.

- `WAIT_FOR_MATURE_EPOCH` -> no challenger;
- unhealthy/failing epoch -> no challenger;
- uncommitted epoch -> no challenger;
- new committed epoch -> exactly one transition opportunity;
- replay/restart of an already-consumed epoch -> no duplicate challenger;
- challenger failure after epoch commit -> durable retryable transition.

The transition preserves epoch identity, cutoff, state, attempt information, challenger identity, completion state and failure detail. An already-created immutable challenger is recognized rather than recreated.
A new epoch can evaluate the existing frozen model, whose training cutoff may
precede (but must not exceed) that epoch end. Waiting for evaluation does not
block later epoch commits.

## 7. Decision-time versus future evidence

Decision-time features/signals may use only information knowable at or before the event. Future candles, future paths, MFE/MAE, barrier outcomes, future volatility, crossed funding and simulated exit results are label/evaluation evidence only. Future-label caches are never same-event decision features.

Training remains chronological: past training -> later validation -> later untouched final test. Historical final-test definitions and decisions are immutable.

## 8. After-cost economics

Research evaluates after-cost outcomes under the versioned fee/spread/slippage/funding contract. Cost stress remains part of the frozen evaluation definition. Gross returns alone cannot satisfy a Research Champion gate.

## 9. Immutable definitions and digests

Important transformations, model/challenger definitions and evaluation artifacts preserve versioned definitions plus hashes/digests tying them to source evidence, artifacts and release/code identity. A version string may not be reused with changed semantics.

## 10. Challenger / validation / final-test lineage

V3.9 challengers preserve immutable challenger/model identity, challenger family, training cutoff, definition hash, artifact digest, and release SHA.

The current evaluator, `V39_CONTEXT_DISJOINT_20_20_V4`, uses 20 validation
and 20 untouched final-test events after model availability and training-label
maturity. Samples are separated by 49 five-minute bars so their four-hour future
paths do not overlap. It retains 2000 bootstrap samples, 95% confidence,
1.0x / 1.5x / 2.0x cost stress, and a minimum of five simulated selected trades
in the final-test window. These are research decisions, not Binance fills.

New artifacts use `v39:context-v4:` and the saved
`CONTEXT_SETUP_CALIBRATION_V1` alongside the Ridge model. The recent calibration
uses disjoint event means from at most 20 days and cannot use future evaluation
labels. Old namespace artifacts retain their original definitions and results.

Later rolling windows add evidence without rewriting historical final-test decisions.

## 11. Research Champion lineage

Research Champion promotion requires the frozen multi-window eligibility contract and explicit promotion boundary. The durable governance lineage includes immutable qualifying windows, eligibility epoch, current/previous champion pointer, model identity, and promotion record.

Research Champion authority remains `RESEARCH_ONLY_NO_EXECUTION`. No Research Champion is a valid scientific result.

## 12. Paper Champion lineage

`V39_PAPER_CHAMPION_GATE_V1` is frozen before qualifying paper evidence is judged. Paper evidence collection remains blocked while no Research Champion exists. When legitimately enabled, qualifying LIVE/PAPER evidence must remain linked to the approved Research Champion and its market/operational regime companions. TESTNET economic results cannot count toward this gate.

## 13. ExecutionProposal / ExecutionOutcome lineage

Observation proposals are advisory versioned messages. Execution independently revalidates current market truth, account truth, position state, spread, risk, profile/environment, and authority.

Completed Execution outcomes are durable locally before transport. Observation records/ACKs the exact `ExecutionOutcome` idempotently. Execution retains the pending outcome until an exact valid ACK, and pending outcome delivery blocks eligibility for a new trade. Duplicate delivery creates one durable Observation record. Execution vetoes are operational decisions, not losing research trades.

## 14. LIVE_REAL_CAPITAL boundary

`LIVE_REAL_CAPITAL` lineage is reserved for V3.10+. V3.9 must not fabricate or pre-authorize real-capital evidence. Real-order capability may exist only after genuine V3.9 Paper Champion proof and the separate V3.10 adapter, arming and regression gates. Observation continues to have no Binance order credentials.
