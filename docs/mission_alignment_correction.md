# Mission-Alignment Correction — Autonomous Learning Loop

## Purpose

This correction brings the deployed Phase 5.11 code back to the original
self-learning paper-trading mission:

- Binance Futures LIVE market data;
- local SHADOW paper execution only;
- one paper position at a time;
- many parallel virtual candidate and strategy experiments;
- automatic challenger training, validation, shadow testing and staged paper
  deployment;
- automatic retreat when a later safety controller detects deterioration;
- no real Binance order authority.

## Paper rollout

A challenger that passes shadow promotion begins at:

```text
PAPER_CANARY_10_PERCENT
```

The paper-canary controller may then advance it atomically through:

```text
PAPER_CANARY_10_PERCENT
  -> PAPER_CANARY_25_PERCENT
  -> PAPER_CANARY_50_PERCENT
  -> PAPER_CHAMPION
```

Assignment is deterministic from environment, model ID and decision batch ID.
The same decision batch always receives the same allocation sample. Each stage
uses cumulative completed-paper-trade and independent-market-event gates. The
thresholds are configurable but must be non-decreasing.

## Unchanged risk

Every model-selected paper trade uses:

```text
paper_risk_multiplier = 1.0
```

The model selects only among candidates that have already passed the rule,
structure and execution-universe filters. It cannot change:

- risk budget;
- notional limit;
- stop placement;
- trailing-stop supervision;
- one-position policy;
- execution mode;
- exchange authority.

## Champion retention

When a 50% canary becomes paper champion, the registry atomically records:

- the new `current_champion_model_id`;
- the old `previous_champion_model_id`;
- immutable champion history;
- the promoted artifact path and checksum already stored on the model record.

The previous champion record and artifact are not deleted. Phase 5.12 will use
this retained pointer for complete automatic rollback of canaries and model
champions.

Rules remain the permanent benchmark in every champion–challenger shadow
snapshot. A model paper champion affects only local paper candidate selection.

## Strategy-policy learning

The automatic strategy-policy recommender consumes completed Phase 5.6
`VIRTUAL_TRADE` and `VIRTUAL_STRATEGY_VARIANT` outcomes. It groups results by
`market_event_id`, compares after-cost `net_exit_r`, and writes a pattern-level
recommendation to the environment-specific atomic JSON file.

A recommendation can only reference a variant present in the fixed approved
catalog built by `strategy.strategy_lab.build_approved_variant_catalog`.
Unapproved, random or pattern-incompatible variant IDs are ignored and counted
as issues.

The recommendation is research-only in this correction:

```text
activation = RESEARCH_RECOMMENDATION_ONLY
paper_authority = UNCHANGED
real_order_authority = NONE
```

It does not alter paper stops, targets, timeout rules or risk. Its purpose is to
close the strategy-learning evidence loop safely before any later strategy
policy activation is considered.

## Automatic operation

The existing paper-canary controller service now refreshes the approved
strategy-policy recommendation on every governance cycle, even while no canary
exists. Manual report generation is optional and not required for learning.

## Safety invariant

All new registry records, routing decisions, status files and strategy-policy
recommendations state:

```text
real_order_authority = NONE
```

The correction does not add an order-submission path.
