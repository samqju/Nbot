# Phase 7.5C.4 — Learning cycle visibility

## Purpose

The automatic trainer uses two different evidence concepts that the historical
`/learning` display previously mixed together:

1. fresh evidence since the latest completed challenger cutoff, which decides
   **when** the next retraining cycle may start; and
2. the cumulative qualified ledger snapshot, which decides **what** data is
   rebuilt into the chronological train/validation/test cohort.

After a challenger completed, the old display reset to values such as
`563 / 1000` outcomes and `28 / 200` events without saying those were fresh
post-cutoff counters. It also stopped showing the completed cumulative
50/20/20-style split because `cohort_readiness` only exists while a current
cohort is waiting.

The human-facing headings `TRAINING (7.4)` and `FORWARD CHALLENGE (7.5)` also
exposed historical implementation labels rather than the continuing learning
cycle described by the roadmap.

## Changes

This patch is operator-visibility only. It does not modify candidate selection,
model training, evidence qualification, split mathematics, promotion gates,
paper authority, or order authority.

### Automatic training status

Every auto-training supervisor status now includes all configured thresholds:

- minimum fresh outcomes;
- minimum fresh independent market events;
- minimum cumulative train market events;
- minimum cumulative validation market events;
- minimum cumulative test market events.

This allows the dashboard to retain the configured 50/20/20-style denominators
even after the trainer returns to `WAITING_FOR_DATA`.

### Learning status document

The status document keeps its existing machine-readable fields for backward
compatibility and additionally exposes:

- fresh qualified outcomes since the latest completed-model cutoff;
- fresh independent events since that cutoff;
- lifetime qualified ledger outcomes;
- fresh-evidence cutoff timestamp;
- current configured thresholds;
- a compact summary of the latest completed training run.

The latest completed training summary is read from the model registry and
contains the cumulative snapshot event count, cumulative train/validation/test
split counts, selected candidate, offline result, metrics, calibration, drift,
and offline gate evidence.

### Console / Telegram wording

The human-facing display now uses:

- `CHALLENGER TRAINING`;
- `CURRENT CUMULATIVE COHORT` when a cohort is presently being built;
- `LAST COMPLETED TRAINING` for the latest completed cumulative split;
- `SHADOW FORWARD VALIDATION`.

Historical `(7.4)` and `(7.5)` headings are removed from the operator display.
The internal phase fields remain unchanged for compatibility.

## Important semantics

Fresh counters decide **WHEN** to retrain.

The cumulative qualified ledger snapshot decides **WHAT** the challenger trains
on. The cumulative split is rebuilt from scratch each cycle; it is not the
previous split plus a separate new split.

For example, a last completed split of `357 / 45 / 71` is labelled cumulative.
A simultaneous current-cycle display of `563 / 1000` fresh outcomes and
`28 / 200` fresh events means only that the next retraining trigger is still
collecting post-cutoff evidence.

## Safety

- No execution code is changed.
- No learning gate is relaxed.
- No model authority changes.
- Paper authority is unchanged.
- Real-order authority remains `NONE`.
