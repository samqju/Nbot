# Phase 5.5 — Versioned Experiment Data Contract

Phase 5.5 changes data identity and traceability only. It does not change
candidate ranking, paper-trade selection, risk sizing, stop management, or
real-order capability.

## Contract version

Every new candidate carries `experiment_context.contract_version = 1`.
Append-only observation and outcome records also expose the most important
identity fields at the top level for efficient joins and reporting.

## Required identity

- `candidate_observation_id`: one candidate.
- `decision_batch_id`: candidates ranked in one strategy decision.
- `market_event_id`: deterministic grouping for the same environment and
  completed five-minute market bucket.
- `strategy_version`: version of the strategy implementation.
- `strategy_variant_id`: exact candidate-generation variant.
- `selection_model_version`: decision authority used by the rule path.
- `feature_schema_version`: version of the numeric feature vector.
- `outcome_variant_id`: virtual, forward, or paper outcome policy.

## Required context

The contract includes:

- environment and execution mode;
- candle interval and bucket;
- available symbol structure, trend, volatility, and compression context;
- explicit nulls for BTC regime, breadth, spread, and quote volume when those
  measurements are not yet available;
- paper fees and slippage assumptions;
- virtual stop, target, timeout, and ambiguous-candle policy;
- paper execution and trailing-stop policy.

Missing context is never invented. New fields that are not yet measured are
stored as null and the context is marked `PARTIAL_PHASE5_5`.

## Propagation

The same context is preserved through:

1. strategy candidates;
2. candidate observations;
3. pending forward simulations;
4. active and completed virtual trades;
5. shadow-model predictions;
6. trade intents and engine open-position state;
7. persistent paper positions and paper-trade history;
8. executed-trade outcomes, including reconciliation closes;
9. joined training-dataset rows.

## Validation and compatibility

- New contract records are validated strictly.
- Observation/outcome identity mismatches are excluded from training and
  reported by the dataset integrity report.
- Existing legacy JSONL and state records remain readable.
- Legacy rows are marked with `experiment_contract_version = 0` and
  `legacy_record = true` in newly generated training datasets.
- New and legacy rows are never silently treated as the same contract version.
