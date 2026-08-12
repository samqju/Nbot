# Phase 7.2 — Context-Aware Learning Features

## Goal

Make newly trained challengers consume the complete Phase 7.1 market context
without changing the nine symbol-local candidate features or granting new paper
or execution authority.

## Context feature contract

Phase 7.2 adds a separate versioned context feature schema.  New challengers
use:

- BTC 24h percentage change;
- broad-market advancing, declining, and unchanged fractions;
- broad-market median 24h change and median absolute 24h change;
- market-context coverage;
- candidate spread percentage;
- log10 candidate 24h quote volume;
- one-hot broad-market regime;
- one-hot broad-market volatility regime; and
- one-hot BTC regime.

The original nine candidate features remain schema version 3 and are not
redefined.

## Historical data policy

Only rows whose market context is `COMPLETE_PHASE7_1` are eligible for new
Phase 7.2 challenger training.  Historical `PARTIAL_PHASE5_5` and
`PARTIAL_PHASE7_1` rows remain unchanged and are excluded rather than imputed.

Automatic-training inventory also counts only completed outcomes linked to
complete Phase 7.1 context.  This prevents the historical partial dataset from
triggering a context-aware training job prematurely.

## Artifact compatibility

Old artifacts remain valid.  A model requires market context only when its
artifact explicitly declares:

- `requires_complete_market_context = true`;
- `context_feature_schema_version = 1`; and
- the fixed `context_feature_names` list.

Registered and shadow scorers append the context vector only for such artifacts.
A context-aware artifact fails closed when a live candidate lacks complete
market context.

## Evaluation and drift

Context-aware baseline and ensemble challengers are evaluated on the same
untouched chronological validation/test splits.  Calibration and PSI drift
reports now include the declared context features as well as the original local
features and scores.

## Authority boundary

Phase 7.2 does not change the current champion.  New challengers are trained
with `runtime_activation = DISABLED`, may enter observation-only shadow testing,
and carry `paper_promotion_allowed = false`.  The registry refuses a Phase 7.2
attempt to enter paper canary.  Paper selection remains a later Phase 8 step.

## Acceptance

Phase 7.2 is accepted when:

1. complete-context rows produce the fixed context vector;
2. historical partial rows are excluded from context-aware training;
3. baseline and ensemble artifacts advertise the context schema;
4. challenger evaluation and drift consume the context fields;
5. registered/shadow scoring works with complete live candidate context;
6. partial live context fails closed for a context-aware model;
7. the rules champion remains unchanged and paper promotion is locked; and
8. the complete NBOT regression suite passes.
