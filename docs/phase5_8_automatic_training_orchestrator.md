# Phase 5.8 — Automatic Training Orchestrator

Phase 5.8 connects the existing offline learning tools into a reproducible,
automatic challenger-training pipeline. It runs as a separate low-priority
process and has no trading authority.

## Safety boundary

The training supervisor is not imported or called by the trading engine.
It runs through:

```bash
python3 -m scripts.learning.auto_train --watch
```

The included user-systemd service starts that command independently with a
higher nice value, low CPU weight, idle I/O scheduling, and a restrictive
umask. A training crash cannot stop WebSocket processing, position
supervision, stop management, or engine-state persistence.

Phase 5.8 never changes:

- `SHADOW_MODEL_ARTIFACT_PATH`;
- `SHADOW_MODEL_SCORING_ENABLED`;
- the model registry's current champion pointer;
- paper-trade selection;
- real-order capability.

Every created artifact keeps `runtime_activation=DISABLED`,
`paper_authority=UNCHANGED`, and `real_order_authority=NONE`.

## Trigger

A cycle starts only when both conditions are true relative to the latest
completed registered model:

```text
new completed outcomes       >= 1,000
new independent market events >= 200
```

The configured outcome type defaults to `VIRTUAL_TRADE`. A polling interval
only checks the trigger; elapsed time by itself cannot start training.

A separate non-blocking file lock prevents concurrent training cycles.

## Pipeline

```text
Scan new material outcomes
        ↓
Copy complete JSONL source boundaries
        ↓
Build and validate joined dataset
        ↓
Keep current-contract, labeled, event-linked rows
        ↓
Create read-only immutable snapshot
        ↓
Generate SHA-256 dataset fingerprint
        ↓
Create purged chronological splits
        ↓
Train logistic baseline
        ↓
Train ensemble candidates and validation-selected blend
        ↓
Evaluate validation/test calibration and feature drift
        ↓
Choose winner using validation data only
        ↓
Apply untouched-test offline gates
        ↓
Register OFFLINE_VALIDATED or REJECTED challenger
```

The selected model is never chosen using test metrics. Test results are used
only after selection as final offline gates.

## Immutable snapshot

Each run stores:

```text
data/training_snapshots_<environment>/<snapshot_id>/
    source/candidate_observations.jsonl
    source/candidate_outcomes.jsonl
    training_dataset_all.jsonl
    training_dataset.jsonl
    dataset_integrity_report.json
    snapshot_manifest.json
```

`training_dataset.jsonl` contains only:

- the configured outcome type;
- current experiment-contract records;
- labeled rows;
- rows with `market_event_id`.

The fingerprint covers the exact eligible dataset bytes plus its schema and
environment metadata. Snapshot files and directories are made read-only after
creation.

## Model directory

Each attempt stores its complete evidence under:

```text
models/challengers_<environment>/<model_id>/
    splits/train.jsonl
    splits/validation.jsonl
    splits/test.jsonl
    time_split_report.json
    baseline.pkl
    baseline_report.json
    baseline_evaluation.json
    ensemble.pkl
    ensemble_report.json
    ensemble_evaluation.json
    challenger.pkl
    challenger_selection_report.json
```

A failed run may retain partial files for audit, but its registry status is
`INVALID` and the champion is unchanged.

## Registry

The environment-specific registry is an atomic JSON document:

```text
models/model_registry_live.json
models/model_registry_testnet.json
```

Each model record contains:

- `model_id`;
- `parent_model_id`;
- `dataset_fingerprint`;
- `dataset_snapshot_path`;
- `training_started_at_ms`;
- `training_completed_at_ms`;
- `feature_schema_version`;
- `strategy_schema`;
- `training_rows`;
- `independent_event_count`;
- `validation_metrics`;
- `test_metrics`;
- calibration and drift summaries;
- `artifact_checksum_sha256`;
- `artifact_path`;
- `data_cutoff_ms`;
- lifecycle `status`.

Supported lifecycle values are:

```text
TRAINING
INVALID
OFFLINE_VALIDATED
SHADOW
PAPER_CANARY
PAPER_CHAMPION
REJECTED
ROLLED_BACK
ARCHIVED
```

Phase 5.8 may create only `TRAINING`, `INVALID`, `OFFLINE_VALIDATED`, or
`REJECTED` records. Later phases own shadow and paper transitions.

## Offline gates

The validation-selected winner becomes `OFFLINE_VALIDATED` only when the
untouched test report passes all configured gates:

```text
test ROC AUC              >= 0.50
test Brier score          <= 0.25
test max calibration gap  <= 0.10
max feature PSI           <= 0.25
```

Failure of a valid offline gate produces `REJECTED`, not `INVALID`.
Pipeline, schema, artifact, or training failures produce `INVALID`.

## Running once

```bash
python3 -m scripts.learning.auto_train --once
```

Expected early status:

```text
WAITING_FOR_DATA
```

## Continuous operation

Install the service as a user service:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/observation/install_services.py (canonical Phase 6A.0+ deployment; see deploy/README.md) \
  ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nbot-auto-training.service
```

Inspect it with:

```bash
systemctl --user status nbot-auto-training.service
journalctl --user -u nbot-auto-training.service -f
```

The supervisor writes the latest machine-readable state to:

```text
data/auto_training_status_live.json
data/auto_training_status_testnet.json
```

## Phase boundary

Phase 5.8 creates reproducible offline challengers only. Phase 5.9 will consume
`OFFLINE_VALIDATED` registry entries and run continuous champion–challenger
shadow decision snapshots. Phase 5.8 cannot activate a challenger.
