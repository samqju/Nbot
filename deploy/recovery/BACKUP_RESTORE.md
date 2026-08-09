# NBOT backup and restore

Git is the rebuild source for code. Runtime state and secrets require separate
backups.

Keep Observation and Execution backups separate. Never restore an entire shared
`data/` directory onto both machines.

## 1. General rules

1. Record the exact deployed Git tag and SHA with every backup.
2. Encrypt backup storage.
3. Store secrets separately from normal state archives when possible.
4. Never commit `.env`, private SSH keys, exchange keys, live state or model
   artifacts merely to make recovery easier.
5. Test restore procedures periodically in SHADOW/test conditions.
6. Do not stop/restart Execution for backup while a position is open.

## 2. Version manifest

Capture on each VPS:

```bash
cd /path/to/Nbot
{
  echo "ROLE=OBSERVATION_OR_EXECUTION"
  echo "UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "BRANCH=$(git branch --show-current)"
  echo "SHA=$(git rev-parse HEAD)"
  git describe --tags --exact-match 2>/dev/null || true
} > /secure/backup/location/manifest.txt
```

## 3. Execution state to back up

Execution owns:

- `BOT_STATE_PATH`
- `PAPER_STATE_PATH` when using SHADOW paper execution
- `PAPER_TRADES_PATH` when using SHADOW paper execution
- `EXECUTION_OUTBOX_PATH`
- `.env` separately
- Execution-to-Observer tunnel private/public key and pinned Observer
  `known_hosts` file, or a documented procedure to rotate/regenerate them

The bot state includes processed proposal IDs and the current/last execution
state. The durable outbox is critical: an outcome waiting for Observation must
survive loss of the Execution VPS backup/recovery chain.

Print configured paths without printing secrets:

```bash
cd /path/to/Nbot
/path/to/venv/bin/python - <<'PY'
import config
for name in (
    "BOT_STATE_PATH",
    "PAPER_STATE_PATH",
    "PAPER_TRADES_PATH",
    "EXECUTION_OUTBOX_PATH",
):
    print(name, "=", getattr(config, name, None))
PY
```

### Consistent manual Execution backup

Preferred maintenance window:

1. operator disables new entries;
2. confirm bot and paper positions are flat;
3. confirm or record pending outbox contents;
4. create the state archive;
5. leave/restart services according to the maintenance plan.

Do not force-close a position merely to create a backup.

Example after verifying flat/disabled:

```bash
cd /path/to/Nbot
BACKUP=/secure/backup/location/execution-$(date -u +%Y%m%dT%H%M%SZ).tar.gz
tar -czf "$BACKUP" \
  data/bot_state_live.json \
  data/paper_state_live.json \
  data/paper_trades_live.jsonl \
  data/execution_outbox_live
sha256sum "$BACKUP" > "$BACKUP.sha256"
```

Adjust filenames for the configured environment. The config-path printout is
the authority, not these example LIVE filenames.

## 4. Observation state to back up

Observation owns, as configured for the active environment:

- candidate observations;
- candidate outcomes;
- virtual trades;
- learning runtime state;
- universe/observation-universe snapshots;
- model registry and model artifacts;
- automatic training state/status;
- promotion controller state/status/evidence;
- paper canary state/status/decisions;
- automatic learning status and other governance evidence required to resume
  the approved model state;
- `.env` separately;
- restricted tunnel account SSH configuration, or a documented procedure to
  recreate it.

Because exact model/status paths evolve, do not maintain a second hard-coded
copy of every path in backup automation. Build a manifest from the active
configuration and repository ownership documentation, then verify the archive.

At minimum the primary split-owned paths include:

```text
data/candidate_observations_live.jsonl
data/candidate_outcomes_live.jsonl
data/virtual_trades_live.jsonl
data/learning_runtime_state_live.json
data/universe_live.json
data/observation_universe_live.json
models/
```

Include additional Observation-owned status/governance files present in the
active deployment.

## 5. Secrets backup

Secrets should be encrypted and access-controlled separately.

Observation secret set normally includes:

- project `.env` including the shared Observation control token;
- GitHub deploy key if you choose to preserve rather than rotate it;
- tunnel account `authorized_keys` and SSH Match User configuration, or the
  information needed to recreate them.

Execution secret set normally includes:

- project `.env`;
- GitHub read-only deploy key;
- private Execution-to-Observer tunnel key;
- pinned GitHub/Observer host-key files;
- future exchange order-writing credentials.

Never put these inside the Git repository.

## 6. Restore order

### Restore Observation

1. install OS packages;
2. clone the exact Git tag/SHA;
3. build the pinned virtualenv;
4. restore `.env` securely;
5. restore Observation-owned data/models;
6. recreate/restore the restricted `nbot-tunnel` account;
7. install `nbot-observer.target` and services;
8. start the target;
9. verify `/health` returns READY/NOT_READY as appropriate and
   `order_authority=NONE`;
10. verify candidate/virtual/learning processes continue.

### Restore Execution

1. install OS packages;
2. clone the exact same Git tag/SHA as Observation;
3. build the pinned virtualenv;
4. restore `.env` securely;
5. restore Execution-owned state and outbox;
6. restore/rotate the tunnel key and pin the current Observer host key;
7. install `nbot-execution.target` and services;
8. start Execution;
9. verify startup reconciliation completes before allowing new entries;
10. verify an existing position, if one is represented by the recovered
    execution state/exchange truth, is recovered without duplicate exposure;
11. verify pending outcomes retry and are deleted only after valid ACK;
12. enable new entries only after reconciliation and operator checks succeed.

## 7. Restore validation

After restore:

```bash
git status --short
git rev-parse HEAD
```

Compare the SHA on both VPSs.

Execution checks:

- exactly one Execution worker;
- tunnel active;
- no Observation worker/learning sidecars;
- bot/paper position state matches reconciliation truth;
- outbox count understood;
- no duplicate proposal execution.

Observation checks:

- exactly one Observation worker;
- approved learning sidecars active;
- no Execution worker;
- recommendation health valid;
- candidate/outcome/virtual datasets writable;
- model/governance state loaded.

## 8. Backup retention

Keep enough generations to recover from both infrastructure loss and accidental
state corruption. At minimum keep:

- the latest known-good backup;
- several previous generations;
- the Git tag/SHA manifest for every backup;
- archive SHA-256 checksums.

Provider snapshots are useful but are not a substitute for independent backup
storage. A provider account or region failure can remove both the VPS and its
local snapshots.
