# Phase 6A.0 Two-VPS Architecture Acceptance

Phase 6A.0 is complete.

## Final architecture

NBOT now runs as two physically separated workers from the same Git repository
and exact revision.

### Observation Worker

Responsibilities:

- Market observation and candidate generation
- Virtual trades and virtual outcomes
- Learning and automatic training
- Champion/challenger evaluation
- Promotion and paper-canary governance
- Execution recommendation API
- Execution-outcome ingestion

Observation has no real order authority.

### Execution Worker

Responsibilities:

- Obtain recommendations while flat
- Independently consume Binance public market data
- Validate and execute approved proposals
- Own the single paper/live position
- Manage trailing stops and exits
- Persist execution-owned runtime state
- Persist and retry execution outcomes

Execution performs no Observation or learning workload.

## Role deployment

The canonical role entrypoints are:

- Observation: `run_observation.py`
- Execution: `run_execution.py`

The canonical systemd role targets are:

- `nbot-observer.target`
- `nbot-execution.target`

Individual services are not independently enabled at boot; the role target owns
role startup.

The Execution service has only a weak dependency on the Observation tunnel.
Loss of Observation or the tunnel must not terminate an already-running
Execution worker.

## Phase 6A.0 physical acceptance results

The two-VPS deployment was tested in LIVE market-data + SHADOW execution mode.

### Observer failure during an open position

PASS.

Observation was stopped while Execution had an open position.

Verified:

- Execution remained alive.
- Execution continued consuming its own Binance market data.
- Open-position high/low state continued updating.
- Trailing stop management continued.
- The position closed without Observation being available.

### Durable outcome during Observer outage

PASS.

After the position closed while Observation was unavailable:

- Execution became flat.
- The completed execution outcome remained in the local durable outbox.
- Delivery was retried while Observation was unavailable.
- New entries remained blocked while the pending outcome existed.
- No outcome was lost.

### Observer recovery and outcome delivery

PASS.

After Observation was restored:

- The pending execution outcome was delivered.
- Observation acknowledged it as `RECORDED`.
- Execution removed it from the outbox.
- The Observation dataset contained exactly one executed-trade record for the
  execution outcome.

### Execution restart during an open position

PASS.

Execution was restarted while a paper position was open.

Verified:

- The previous Execution process stopped.
- A new Execution process acquired the instance lock.
- The same trade ID, symbol, side, entry, quantity and stop were recovered.
- Startup reconciliation succeeded.
- Binance public market connectivity was restored.
- Position management resumed.
- No duplicate entry was created.

### Observer CPU isolation

PASS.

Three CPU-burning processes were run on the separate Observation VPS.

Verified:

- Observation remained healthy.
- Observation services remained active.
- Execution remained active on the separate Execution VPS.
- Execution CPU/load remained unaffected.
- The open position continued receiving market updates.
- No Execution restart or state corruption occurred.

## Final resting state

At Phase 6A.0 closeout:

- Execution mode: SHADOW
- Trading state: TRADING_DISABLED
- Halt reason: OPERATOR_DISABLE
- Open position: none
- Pending execution outcomes: zero
- Completed paper trades: 45
- Observer role: active
- Execution role: active
- Observation tunnel: active

## Test suite

The final repository test suite before Phase 6A.0 runtime acceptance completed:

- 421 tests
- all passed

## Phase 6A.0 conclusion

The two-worker architecture is accepted.

The following properties have been physically demonstrated:

- Observation may be unavailable during open-position management.
- Execution owns and manages its open position independently.
- Execution does not depend on Observation market-data relay.
- Execution restart recovers an existing position without duplication.
- Execution outcomes survive Observation outages.
- Flat Execution does not continue trading while a required outcome is pending.
- Cross-VPS execution outcomes are idempotent.
- Heavy Observation workload does not materially affect Execution.

The next phase is Phase 6A Execution Stabilization After the Split.
