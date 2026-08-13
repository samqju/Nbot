# Phase 7.5B.1 — End-to-End Memory-Safe Training Hotfix

## Purpose

Phase 7.5B removed the first large in-memory copies from inventory scanning,
dataset joining, and snapshot filtering. Production validation on the 8 GiB
Observation VPS then showed the auto-training process climbing past 3 GiB
before it could write a fresh cohort status.

The remaining hotspot was the chronological splitter, which still retained the
entire nested JSON training dataset plus grouped/split copies in Python memory.
The downstream baseline, ensemble, and challenger evaluator also retained full
JSON dictionaries before creating compact numeric matrices.

This hotfix completes the memory-safety work across the Phase-7 training path.

## Changes

- `TimeAwareDatasetSplitter` stages full JSON rows in temporary SQLite storage.
- Only compact candidate/market-event group metadata remains in Python memory.
- Train/validation/test JSONL files are streamed atomically from the disk-backed
  staging store.
- Baseline and ensemble training scan split files first, then fill compact NumPy
  matrices directly without retaining full JSON row dictionaries.
- Final challenger validation/test evaluation uses compact NumPy matrices and
  derives PSI inputs from those matrices.
- Sealed-test SHA-256 checks stream file contents rather than using `read_bytes()`.
- Cohort status reports the split build mode so `/learning` can prove the active
  memory-safe path.

## Deliberately unchanged

- 1,000 qualified outcome trigger.
- 200 independent market-event trigger.
- 70/15/15 chronological split ratios.
- One-hour embargo.
- Label-window purging.
- 50/20/20 independent-event floors.
- Market-event isolation.
- Feature schema and context requirements.
- Complete Phase-7.3 cost requirements.
- Baseline/ensemble model families and hyperparameters.
- Validation-only winner selection.
- Sealed final test policy.
- Offline gates and Phase-7 paper-promotion lock.
- Execution worker, risk, order, stop, and paper-routing behavior.

## Runtime acceptance

Do not tag this hotfix complete until the real Observation VPS demonstrates:

1. one fresh inventory + snapshot + cohort cycle completes;
2. `split_build_mode=DISK_BACKED_STREAMING_SQLITE` is persisted;
3. the auto-training status timestamp advances past service start;
4. no new kernel OOM event occurs;
5. trainer memory remains comfortably below the previous multi-gigabyte climb;
6. Observation remains healthy throughout.

If the cohort is ready and model training starts, continue observing through
baseline, ensemble, and selected-challenger evaluation before final tagging.
