# Phase 7.5B — Memory-Safe Training Pipeline

## Purpose

Phase 7.5B is an operational hardening subphase inside Phase 7. It fixes the
Observation-side automatic trainer after production evidence showed repeated
Linux OOM kills while rebuilding the learning dataset on an 8 GiB VPS.

This phase does **not** change trading logic or learning acceptance rules.

## Runtime evidence that triggered the phase

The Observation VPS kernel repeatedly killed the process owned by
`nbot-auto-training.service`. Several attempts reached roughly 3.7–7.1 GiB RSS
before termination. Observation itself remained healthy when the trainer was
stopped.

The old training path could simultaneously retain:

- the complete candidate-observation history,
- the complete candidate-outcome history,
- an in-memory observation lookup,
- a complete joined dataset list,
- a second complete eligible-row list,
- and a full byte copy of the eligible dataset for fingerprinting.

That design was correct for small datasets but was not sustainable as the
logical JSONL history grew.

## Changes

### 1. Memory-safe training inventory

`TrainingInventory.scan()` now streams logical JSONL history and uses a small
on-disk SQLite workspace for observation lookup and duplicate-material-outcome
tracking. It keeps only counters, the independent market-event set, and the
current parsed row in Python memory.

Qualification semantics are unchanged.

### 2. Memory-safe dataset join

`TrainingDatasetBuilder` now streams observations and outcomes and uses a
disposable SQLite workspace for:

- observation identity lookup,
- fail-closed duplicate observation handling,
- duplicate outcome detection,
- joined-row storage,
- deterministic external sorting.

The final dataset remains deterministic JSONL ordered by observation time,
outcome time, candidate ID, and outcome type.

### 3. Streaming eligible snapshot

The automatic trainer no longer executes a full
`read_text().splitlines()`/`eligible_rows` materialization and no longer reads
the final dataset into one `bytes` object for hashing.

Eligibility filtering is streamed to `training_dataset.jsonl`; fingerprinting
is performed in fixed-size chunks. Only small schema sets, counters, and the
independent market-event set remain in memory.

### 4. Persistent cohort diagnostics

`WAITING_FOR_COHORT` status now retains the splitter's lightweight diagnostics:

- raw input counts,
- final train/validation/test market-event counts,
- purge exclusions,
- embargo exclusions,
- split configuration,
- splitter issues.

The `/learning` operator view displays the cohort split counts plus purged and
embargoed event-group counts when those diagnostics exist.

## Explicit non-changes

Phase 7.5B does not change:

- `AUTO_TRAINING_MIN_NEW_OUTCOMES`,
- `AUTO_TRAINING_MIN_NEW_MARKET_EVENTS`,
- train/validation/test ratios,
- embargo duration,
- train/validation/test event floors,
- complete-context requirements,
- complete-cost requirements,
- sealed-test policy,
- baseline/ensemble model definitions,
- offline validation gates,
- Phase 7.5 forward comparison gates,
- champion/promotion authority,
- paper routing,
- Execution Worker code or capital authority.

## Runtime acceptance

The subphase is runtime-complete only after the real Observation VPS proves:

1. Observation remains healthy while the trainer runs.
2. The trainer completes at least one inventory + snapshot + cohort cycle
   without Linux OOM intervention.
3. Memory remains bounded with substantial headroom on the 8 GiB VPS.
4. `/learning` reports fresh auto-training status and cohort diagnostics.
5. Existing qualified evidence remains intact; no learning data is deleted.
6. If the cohort is ready, normal Phase 7.4 challenger training proceeds.
7. If the cohort is not ready, `WAITING_FOR_COHORT` is a fresh deliberate
   status rather than a stale artifact left by an OOM-killed process.
