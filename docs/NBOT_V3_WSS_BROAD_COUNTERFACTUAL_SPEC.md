# NBOT V3 — WebSocket-first broad research and chronological decision outcomes

Status: DEVELOPMENT SPECIFICATION, NOT DEPLOYED. Base release: 4dfe34b442f12f4f7118eec1fd2df4d15fabf7b8.

## Goals and non-negotiable boundaries

1. Preserve the deployed V2 96-hour live-paper cohort, release identity, safety gates, data, and model. Do not deploy this branch, restart either VPS, change thresholds, or grant real-order authority as part of this branch.
2. Expand the **research** universe from the currently deployed tiny 20-symbol configuration toward 100 then 200 liquid USD-M perpetual symbols, subject to CPU, memory, network, API rate, disk, and causal-integrity benchmarks. Keep a separately configurable **execution-eligible** universe. Do not silently increase actual order exposure.
3. Preserve causal five-minute decision features and 4-hour horizon, but generate **chronological path-based** after-cost counterfactual exit-policy labels for eligible LONG and SHORT candidate decisions, including rejected decisions, instead of relying solely on 5m OHLC chronology.
4. WSS-first for market data in paper and eventual live execution; REST remains for initial snapshots, exchange metadata, historical gap repair, account/order reconciliation, and independent safety checks.
5. Preserve actual paper fills as the execution truth. Never present counterfactual results as executed PnL or as independent simultaneous portfolio opportunities.

## Market data: two different truths

- `bookTicker`: best bid/ask and spread for executable entry checks; timestamps, receipt times, sequence/continuity where supplied, and source identity must be recorded. Reject stale or crossed quotes.
- `aggTrade`: chronological contract trade prices for intrabar path, MFE/MAE, research stop chronology and contract-price-oriented trailing logic. Exchange trade prices are **not** historical bid/ask fills.
- The canonical stream envelope records exchange event time, trade time when available, local monotonic receipt time, symbol, type, event/trade IDs, and source. Maintain symbol-local ordering, detect duplicate IDs and gaps, and quarantine unrecoverable discontinuities.
- Never promise a trade on every 100ms interval: Binance publishes aggregated trade events when market trades occur.
- For live futures, reconcile stop trigger semantics (including `CONTRACT_PRICE` and exchange-hosted stops), position/order status and user-data streams. Local paper quote-driven stop behavior is **not** equivalent to exchange-hosted stop triggering.

## Transport reliability

- Combined/multiplexed market subscriptions with measured sharding and bounded queues; subscribe only to permitted symbols.
- Heartbeats, ping/pong, connection health, proactive connection rotation before 24h, exponential backoff/jitter, resubscription and bounded catch-up.
- Fail closed for new entries on stale market state, disconnected subscription, invalid ordering, missing best bid/ask or unresolved recovery. No stale REST quote may be silently treated as fresh WSS data.
- Gap recovery from Binance historical aggregated trades when supported, respecting pagination/time limits and retention; otherwise explicitly label the outcome unresolved or lower fidelity. Historical public archives are a separate verified backfill source.
- Backpressure, queue depth, latency percentiles, event loss/duplication, stream staleness and per-symbol coverage are observable.
- Market-data transport migration precedes any optional authenticated WebSocket order-transport migration; latter requires its own security review and independent tests.

## Broad research universe

- Keep 5m signal construction causally aligned to *completed* candles and event-time available quotes; never feed future data into features.
- Universe selection must use point-in-time information, with liquidity, volume, spread, availability, delisting and minimum-history gates. Record membership and reason per event.
- Benchmark 20 -> 100 -> 200, rather than assume a small VPS can handle 200 simultaneous high-volume aggTrade feeds. Consider separate broad 5m feature feed and deep high-resolution path subscription pools.
- 100 symbols x two sides x 288 events/day = 57,600 **correlated candidate observations**, not independent trades.
- Preserve event-level weighting, chronological training/validation split, model versioning and leakage prevention. Distinguish scored symbol/side rows from distinct strategy-family decisions.

## Decision Outcome Ledger (immutable decisions)

Freeze at decision time:
- release/model/artifact digest, decision ID, market event ID, symbol, side, setup/strategy ID, frozen feature digest and causal membership;
- Ridge score, ML mean, ML lower quantile, ensemble/conservative score, ranking, runner-up, gap, gates, cooldowns and explicit reject/approve reason;
- observed bid/ask, quote source, reference price, risk unit, hypothetical entry rule, fees/slippage assumptions, policy ID and position capacity;
- no-trade decisions and Ridge/ML disagreements, not only approved proposals.

The ledger is append-only: decision -> pending -> matured or unresolved. Future outcomes never rewrite the original prediction, threshold or reason. Link to existing `paper_feedback_checks` and durable `research_memory.db`, not disposable epoch scratch data. Store compact policy outcomes **before** raw data pruning.

## Counterfactual replay

- For each eligible frozen candidate, create an independent research-only state machine. No exchange order, capital reservation or shadow-position limit; one symbol feed may update multiple overlapping LONG/SHORT hypothetical positions.
- Replay chronological trades from the decision's eligible hypothetical entry instant for up to 4h. Explicitly define hypothetical entry pricing and after-cost model. No fabricated exact bid/ask fills from `aggTrade` alone.
- Preserve initial -1R risk and versioned `INTEGER_R_STEP_CONTROL` policy, with explicit alternative semantics: (a) market-truth chronological policy, (b) execution-cadence replay matching observed/prescribed NBOT quote sampling, (c) actual paper execution outcome.
- Carefully specify stop update timing. Current 5m control only tightens on completed bars; a tick-driven trailing stop that tightens intrabar is a **different policy**. Do not silently train on a new policy while calling it the old one. Version both and compare on identical paths.
- Record stop transitions, crossings, exit reason/time/price, MFE/MAE, peak, giveback, post-exit extension, fees, funding proxy, slippage assumptions, net R, latency, path coverage, ambiguity, gap handling and source digests.
- Research outcomes: `AGGTRADE_RESOLVED`, `1M_RESOLVED`, `5M_UNAMBIGUOUS`, `5M_AMBIGUOUS`, `GAP_UNRESOLVED`. Unresolved/ambiguous outcomes must not masquerade as precise labels.
- Counterfactual classifications are *policy-specific*: avoided loss, missed profitable policy outcome, neutral, unresolved. Profitability after hypothetical fill is not evidence the capital-constrained live portfolio could have taken every candidate.
- Preserve real paper outcomes as higher-fidelity observed execution feedback; separately track their difference from research estimates.

## Shadow and learning design

- Do not confuse existing 10-slot next-bar shadow simulator with the new uncapped-by-capital research replay ledger. Keep legacy shadow telemetry isolated from immediate-entry policy calibration.
- Candidate sampling policy must not select only ML winners: include every feasible symbol/side when capacity allows, plus stratified threshold-near cases, Ridge/ML disagreements, varied strategy families, random controls, volatile and low-volatility regimes. Record sampling probability and missingness to avoid selection bias.
- The full broad 5m research set remains useful as coarse outcomes, but never conflate coarse and high-fidelity targets. Measure label disagreement and missingness before replacing production model targets.
- Train separate outcome-prediction and decision-policy calibration evaluations. Compare fixed .08R conservative threshold and .05R edge gap against pre-registered challenger gates **out of sample**, without auto-deploying any gate change.
- Report score-bin calibration, rejected/approved counts, matured coverage, Ridge-vs-ML disagreement outcomes, policy-specific expected after-cost R, selection/capacity bias, correlated-event uncertainty, and execution-vs-counterfactual deltas.
- No claims of profitability without independent forward paper evidence.

## Deployment and verification gates

A. Offline deterministic fixtures: +3R-before--1R vs -1R-before-+3R, same OHLC different outcome; gap-through stop, short side, crossed quotes, stale quote, duplicate/out-of-order trade, missing range, reconnect and fail-closed; tick-policy vs bar-close-policy divergence.
B. Replay equivalence: existing 5m control matches prior 5m labels when same bar-close policy and same candles; high-resolution chronology resolves only genuinely resolvable cases.
C. Unit/integration/soak tests: 20/100/200 universe throughput, memory, CPU, websocket messages/sec, lag, backpressure, reconnects, raw pruning and ledger permanence; check execution risk boundaries and one-position limit.
D. Shadow transport comparison in a separate release: REST vs WSS quotes measured concurrently with **no execution authority changes**; record divergence and outages.
E. Explicit separate approval for deployment after the V2 cohort; paper-first rollout, then testnet, with real-money authority remaining disabled until independently authorized.

## Delivery tracking

This document records the entire agreed scope. Branch creation and this specification do **not** constitute implementation or test completion. Implement and verify each module before requesting merge or deployment.


## Implementation status — 2026-10-09

The branch now contains an integrated **research-only** implementation foundation. This does not authorize deployment and does not change either running VPS.

Implemented on this branch:
- WSS-first market-state primitives for `bookTicker` and `aggTrade`, symbol-local ordering, duplicate/gap accounting, quote freshness, fail-closed executable-quote access, deterministic 100/200-symbol stream sharding, reconnect backoff, bounded queueing, ping-capable combined-stream transport, and proactive rotation.
- Credential-free bounded REST `aggTrade` range recovery with strict continuity validation.
- Separate point-in-time research and execution-eligible universe selection. Execution remains an explicit subset and is never expanded merely because research expands.
- Append-only immutable decision ledger tables that capture approved and rejected decisions, sampling probability, model diagnostics, quote source, policy identity and immutable matured/unresolved outcomes. Actual execution outcomes are stored separately from research counterfactuals.
- Capital-uncapped overlapping research replay, allowing many LONG/SHORT hypotheses for the same symbol without consuming paper balance or the legacy ten shadow slots.
- Explicit `TICK_INTEGER_R_V1` and `BAR_CLOSE_INTEGER_R_V1` policies. They are evaluated as different learning targets rather than silently substituted.
- After-cost counterfactual fields for taker fees, entry/exit slippage and funding proxy, plus MFE/MAE and source digests.
- Evidence-quality classes for aggTrade-resolved, 1m-resolved, 5m-unambiguous, 5m-ambiguous and gap-unresolved outcomes. Coarse OHLC paths that cannot establish chronology are not promoted to precise labels.
- Deterministic stratified candidate sampling that explicitly includes threshold-near cases, Ridge/ML disagreements, setup-family coverage, volatility coverage and stable controls, with inclusion probability recorded for downstream weighting.
- Chronological calibration helpers, inverse-probability score bins, event-level correlation-aware policy summaries, Ridge-vs-ML disagreement reports and challenger threshold grids. All challenger evaluation is marked research-only with no auto-deployment.
- An integrated `V3ResearchRuntime` that records decisions, consumes chronological trades, matures research outcomes into the ledger, preserves actual paper outcomes as a separate truth, and has no order method (attempted order submission fails closed).
- A pinned V3 WSS dependency isolated in `requirements-wss.txt`; the existing Execution authority and production profiles are unchanged.

Verification now present:
- Opposite intrabar chronology fixtures.
- Tick-policy versus completed-bar-policy divergence.
- WSS stale/disconnected/gap fail-closed behavior.
- 200-symbol combined-stream sharding.
- Immutable decision identity and separate actual-vs-counterfactual outcomes.
- Uncapped overlapping replay beyond the legacy ten-position shadow limit.
- Bounded aggTrade recovery.
- 5m ambiguity classification and bar-close resolvability.
- Research/execution universe subset enforcement.
- Chronological/event-weighted calibration and disagreement-policy reporting.
- Integrated research runtime explicitly rejecting order submission.

Still required before any deployment or merge approval:
1. GitHub full regression must be green on the final head.
2. Real-network WSS soak tests and reconnect/gap-repair exercises must be run separately from the active cohort.
3. 20 -> 100 -> 200 symbol CPU, memory, messages/sec, queue depth, disk and p95/p99 lag benchmarks must be recorded on representative infrastructure.
4. REST-vs-WSS shadow transport comparison must be performed with no execution-authority change.
5. Existing V2/legacy 5m label parity must be demonstrated against historical fixtures at scale.
6. Paper-first rollout and explicit operator approval remain mandatory. Real-money authority stays disabled until independently authorized.
