# NBOT V3 Operations

## Current operating boundary

V3.1 closes the Execution core in code. Actual Binance Testnet mechanical validation is V3.2; Observation deployment begins later.

### Read-only / safe checks

```bash
./nbotctl status
./nbotctl doctor live-paper
./nbotctl doctor testnet-trade
./run_execution.py --profile testnet-trade --self-check
```

`testnet-trade` doctor is expected to fail while DISARMED. Do not arm it before the V3.2 canary procedure. Missing Testnet credentials are reported as V3.2 runtime readiness, not hidden as V3.1 readiness.

### Testnet runtime controls

After the V3.2 procedure deliberately installs credentials and arms Testnet:

```bash
./nbotctl start testnet-trade
./nbotctl status
./nbotctl logs testnet-trade
./nbotctl stop
```

`start` performs an authenticated Testnet preflight before spawning the Execution process. The process must create its READY marker only after capital-first reconciliation succeeds. It starts with new entries disabled and no proposal source.

`stop` sends SIGTERM and waits for graceful shutdown; it does not automatically SIGKILL the capital process if shutdown times out.

### Deferred profiles

- `live-paper`: runtime start deferred until the independent LIVE public market path required for LIVE/PAPER exists.
- `live-trade`: runtime and arming forbidden until V3.10.
- cluster commands: deferred until the V3.5/V3.6 communication and two-VPS integration phases.

Runtime state, locks, PID/READY markers and logs remain under the role/profile-specific ignored `data/`, `runtime/`, and `logs/` directories.

## V3.2 standalone Testnet mechanical canary

V3.2 adds an explicitly manual, one-shot proposal authority:

`TESTNET_MECHANICAL_ONLY`

It is not Observation, research, learning, model, or production recommendation authority.
A completed canary outcome is ACKed only into the local profile-scoped
`data/execution/testnet/mechanical_canary_outcomes.jsonl` record and is marked
`research_evidence=false`.

After code validation and only when the operator deliberately wants a Binance
Testnet order, the direct runtime action is:

```bash
./run_execution.py --profile testnet-trade --testnet-canary --symbol BTCUSDT --side LONG --yes
```

The Testnet profile must already be explicitly armed.  The canary creates at
most one fresh proposal per invocation.  If restart reconciliation finds an
existing protected position, the invocation resumes management and creates no
new proposal.  Ctrl+C leaves an open position protected for deliberate
restart/reconciliation testing.
