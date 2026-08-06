# Phase 5.11 — Controlled Paper-Canary Execution and Rollback

## Purpose

Phase 5.10 reserves a `PAPER_CANARY` model-registry slot after a challenger
passes offline and forward-shadow gates. Phase 5.11 gives that slot narrowly
bounded authority over **local paper entries only** and continuously monitors
completed canary trades for automatic rollback.

This phase does not replace the champion. It does not grant testnet or live
order authority. It does not alter position supervision, stop handling, daily
risk controls, or the one-position policy.

## Authority boundary

Paper-canary routing is permitted only when:

- `EXECUTION_MODE=SHADOW`;
- the registry has exactly one current `PAPER_CANARY` model;
- the registered artifact exists and its SHA-256 checksum matches;
- the artifact schema is supported and declares `runtime_activation=DISABLED`;
- the deterministic traffic bucket is inside the configured allocation;
- the model probability passes the configured floor;
- the UTC daily canary-trade cap has not been reached.

Any failed condition returns the existing rule-selected candidate. No failed
canary decision can suppress rule paper trading.

The engine and registry continue to report:

```text
current_champion_model_id = unchanged
real_order_authority = NONE
```

## Deterministic traffic allocation

The default allocation is 10% of otherwise paper-eligible five-minute decision
batches. The bucket is derived from:

```text
environment | canary model ID | decision batch ID | PHASE5_11
```

using SHA-256. This makes the allocation auditable and independent of whether
the challenger agrees with the rule system.

Default limits:

```text
PAPER_CANARY_ALLOCATION_FRACTION=0.10
PAPER_CANARY_RISK_MULTIPLIER=0.25
PAPER_CANARY_MAX_TRADES_PER_UTC_DAY=5
PAPER_CANARY_MIN_MODEL_PROBABILITY=0.50
```

A canary paper entry therefore uses 25% of the normal notional and 25% of the
normal dollar risk. Scaling both values preserves the existing stop-distance
shape while reducing absolute exposure.

## Decision provenance

Every routing decision is appended to the environment-specific file:

```text
data/paper_canary_decisions_live.jsonl
data/paper_canary_decisions_testnet.jsonl
```

The record includes:

- decision batch and market-event IDs;
- rule-selected and executed candidate observation IDs;
- allocation ID and deterministic allocation sample;
- model ID and model probability;
- selection authority (`RULES` or `PAPER_CANARY`);
- risk multiplier;
- fail-closed reason;
- `real_order_authority=NONE`.

Canary provenance is also persisted in the open paper position and completed
paper trade:

```text
selection_authority
paper_canary_model_id
paper_risk_multiplier
paper_allocation_id
```

## Automatic rollback controller

The rollback controller runs separately from the trading engine:

```bash
python3 -m scripts.learning.paper_canary_controller --watch
```

It reads completed local paper trades and validates the registered artifact on
every evaluation. The default rollback gates are:

```text
Minimum trades before expectancy gates: 20
Maximum drawdown:                       5.0R
Maximum losing streak:                 5 trades
Minimum full-period average:          -0.10R
Recent window:                         10 trades
Minimum recent average:               -0.25R
```

Artifact/checksum failure, drawdown breach, or losing-streak breach can trigger
rollback before the minimum sample count. Full-period and recent-expectancy
gates activate after the minimum completed-trade count.

Rollback is one atomic registry update:

```text
model status: PAPER_CANARY -> ROLLED_BACK
current_paper_canary_model_id: model ID -> null
paper activation: RULE_CHAMPION_ONLY
current champion: unchanged
real-order authority: NONE
```

A failed atomic replace leaves the prior registry intact, so a partially
written state cannot remove or activate authority.

## Separate processes

```text
run.py
  market data, decision cycles, virtual experiments, local paper execution

nbot-auto-training.service
  immutable snapshots and challenger training

nbot-promotion-controller.service
  shadow-evidence promotion governance

nbot-paper-canary-controller.service
  completed canary-trade health and rollback governance
```

The rollback process is low priority and is not imported by the WebSocket,
position-management, stop-supervision, or state-persistence loops.

## Completion gate

Phase 5.11 is complete when:

1. an eligible `PAPER_CANARY` receives only deterministic bounded local-paper
   traffic;
2. non-canary traffic continues to use the current champion/rule system;
3. canary notional and risk are lower than normal paper-trade limits;
4. every executed canary trade has immutable model and allocation provenance;
5. all artifact/scoring/configuration failures fall back to rules;
6. canary routing is impossible outside `EXECUTION_MODE=SHADOW`;
7. health evidence is evaluated automatically by a separate process;
8. rollback atomically clears the canary slot and leaves the champion
   unchanged;
9. real-order authority remains `NONE`.

## Deliberate non-goals

Phase 5.11 does not promote a canary to `PAPER_CHAMPION`. It does not allocate
more than one paper position, modify live capability gates, or submit Binance
orders. Paper-champion promotion and champion rollback policy belong to the
next governance phase.
