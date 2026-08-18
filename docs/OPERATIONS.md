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

## V3.2.2 operator mechanics and telemetry

V3.2.2 keeps the same standalone `TESTNET_MECHANICAL_ONLY` authority and adds
operator actions needed for the physical canary campaign.  These actions do not
create Observation communication and do not change risk, sizing, leverage,
spread, trailing, or stop semantics.

After Testnet credentials are deliberately installed and the profile is armed:

```bash
./run_execution.py --profile testnet-trade --testnet-reconcile --yes
./run_execution.py --profile testnet-trade --testnet-force-close --yes
```

`--testnet-reconcile` performs one capital-first reconciliation.  It may restore
or clean protective state according to the existing V3.1 reconciliation rules,
so it requires both the Testnet arm gate and explicit `--yes`.

`--testnet-force-close` first disables new entries, uses the same bounded
verified-flat close boundary as emergency handling, then runs authoritative
reconciliation to recover close/PnL evidence.  A close request by itself is
never reported as success.  Any resulting mechanical outcome is ACKed only into
the local Testnet mechanical record.

Every V3.2 mechanical action writes a per-run operational telemetry journal
under:

```text
data/execution/testnet/mechanical_canary_telemetry/<run_id>.jsonl
```

The records are always labeled:

```text
authority=TESTNET_MECHANICAL_ONLY
evidence_class=TESTNET_MECHANICAL_ONLY
research_evidence=false
```

The V3.2 telemetry set covers:

- market-order request/fill latency;
- initial protective-stop placement/verification latency;
- stop-replacement latency;
- reconciliation latency;
- existing position-management latency from the durable Execution health monitor;
- emergency requests/results and close attempts;
- recovery attempts/results, stop recoveries, and orphan-stop cleanup;
- duplicate-prevention events;
- process CPU percentage samples and resident-memory high-water mark.

Telemetry failure is intentionally non-capital-bearing: a telemetry write failure
must not interrupt stop protection, position management, reconciliation, or a
verified flatten.  The telemetry summary exposes a `write_failures` count.

During V3.2.4 physical recovery, close settlement may itself prune an orphan
protective stop before the generic orphan-cleanup pass runs.  Mechanical
telemetry therefore counts the verified stop-count reduction around close
recovery as `orphan_stops_removed`; the counting probes are best-effort and
never allowed to interrupt recovery.

`./nbotctl status` continues to report the last accepted Execution checkpoint as
`phase=V3.1`, while also reporting `active_execution_phase=V3.2` during the
mechanical-canary campaign.  This avoids falsely declaring V3.2 accepted before
the complete physical/fault gate passes.

V3.2.2 does **not** add fault injection.  Ambiguous entry/stop, post-fill breach,
and emergency-failure deterministic equivalents belong to V3.2.3.  Physical LONG/SHORT,
restart/offline, trailing and force-close evidence belongs to V3.2.4.

## V3.2.3 deterministic fault-equivalent campaign

V3.2.3 closes the code-side entry/stop/emergency fault campaign without adding
an artificial failure switch to the capital runtime.  The canonical V3.2 gate
allows capital-safety faults to be proven by deterministic equivalents, and the
existing V3.1 Execution core already contains the real safety mechanisms being
exercised.

The registry in `nbot/execution/fault_campaign.py` maps all **20 canonical
entry/stop/emergency fault requirements** to deterministic tests:

- 10 entry faults;
- 7 stop faults;
- 3 emergency faults.

The campaign explicitly **does not add runtime fault injection**.  There is no
`--fault-scenario`, `--inject-fault`, or equivalent switch that can deliberately
corrupt a real Testnet capital path.  Tests instead drive the actual
EntryLifecycle, Position/Reconciliation safety boundaries, EmergencyFlattener,
and Binance Testnet adapter against deterministic fault fixtures.

Two restart-sensitive stop cases retain an additional physical V3.2.4 follow-up
requirement even though their deterministic equivalents remain permanent
regressions:

- missing protective stop after restart;
- orphan protective stop after an exchange-side close.

The targeted code-side campaign is:

```bash
./.venv/bin/python -m unittest \
  tests.test_v323_fault_equivalents \
  tests.test_v323_fault_campaign -v
```

A green deterministic campaign is **not** permission to declare V3.2 complete.
V3.2.4 still performs the deliberate physical Binance Testnet LONG/SHORT,
trailing, force-close, restart/offline, missing-stop/orphan-stop and exchange
truth campaign.  Only V3.2.5 may close the phase acceptance gate and create the
`v3.2-execution-testnet-mechanical-proven` tag.
