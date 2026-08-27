# NBOT V3 Operations

## Current operating boundary

Current checkpoint: `V3.9 IMPLEMENTATION COMPLETE / ECONOMIC EVIDENCE ACCUMULATING`.

The deployed architecture remains the real two-VPS split:

- **Observation VPS** — LIVE/Testnet evidence, compact research memory, continuous challenger learning, governance, recommendation/control service; no Binance order authority.
- **Execution VPS** — independent market/account truth, proposal validation, risk, orders where the profile permits them, stops, OPEN management, reconciliation, emergency action and durable outcomes.

Current authority state must be read from runtime status and never inferred from phase completion. Until a Research Champion is explicitly eligible and promoted under the frozen V3.9 boundary:

- Research Champion = `NONE`;
- Paper Champion = `NONE`;
- Execution research authority = `NONE`;
- Paper Champion evidence collection remains blocked;
- `live-trade` remains forbidden before V3.10.

### Continuous research cadence

`nbot-research-epoch.timer` is a 15-minute maturity checker, not an 8-hour scheduler. The research system advances only when a genuine new 96-event epoch plus required future context is mature. After a successful durable epoch commit, the epoch-to-challenger transition creates exactly one challenger opportunity.

Required semantics:

- `WAIT_FOR_MATURE_EPOCH` -> no challenger;
- unhealthy/failing epoch -> no challenger;
- uncommitted epoch -> no challenger;
- new durable epoch commit -> exactly one challenger opportunity;
- retry/restart of the same consumed epoch -> no duplicate challenger;
- challenger failure after epoch commit -> transition remains durable and retryable.

The former fixed daily `nbot-challenger-cycle.timer` is retired. `nbot-challenger-cycle.service` remains only as a low-priority recovery/oneshot surface for the durable transition path.

### Safe current checks

```bash
./nbotctl status
./nbotctl doctor live-paper
./nbotctl doctor testnet-trade
./.venv/bin/python nbot_admin.py research-epoch-status
./.venv/bin/python nbot_admin.py challenger-status
./.venv/bin/python nbot_admin.py governance-status
./.venv/bin/python nbot_admin.py research-champion-review
./.venv/bin/python nbot_admin.py paper-champion-status
```

Do not run `research-epoch-run` or `challenger-cycle` merely to force evidence. Natural market maturity owns the research clock.

### Pre-V3.10 operator-tooling debt

The remaining operator-tooling gaps are tracked in `docs/PRE_V310_GAP_LEDGER.md`. `nbotctl cluster doctor/start/stop/status` remains unimplemented, and the two mature foundation-doctor checks remain open until separately implemented and validated. They must not be falsely described as complete.

### Preserved historical operational proof

V3.7-A Normal LONG is physically proven end-to-end. V3.7-B Normal SHORT is physically proven end-to-end. V3.7 C–V operational/fault evidence remains accepted. The historical Testnet regression/canary procedures below are retained intentionally; they are not current economic authority.

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

During the V3.2 mechanical-canary campaign, `./nbotctl status` reported the
last accepted Execution checkpoint as `phase=V3.1` and
`active_execution_phase=V3.2`.  After V3.2.5 acceptance closure it reports
`phase=V3.2` and `active_execution_phase=V3.2`.

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

## V3.2.5 acceptance closure

V3.2 standalone Binance Testnet mechanical execution is accepted only as
operational evidence under `TESTNET_MECHANICAL_ONLY`.  It provides no research,
learning, model-selection or profitability authority.

Physical V3.2.4 evidence established:

- authenticated read-only Testnet preflight while disarmed;
- explicit arm -> capital-first reconcile -> FLAT -> disarm with no entry;
- real Testnet LONG entry, fill, initial protection, restart recovery and close;
- real Testnet SHORT entry, fill, initial protection, restart recovery and close;
- verified controlled protective-stop replacement;
- real protective-stop managed close with authoritative recovered PnL;
- kill while OPEN followed by protected restart recovery;
- missing protective stop followed by exact restart restoration;
- exchange-side/manual-equivalent close while Execution was offline;
- orphan protective stop physically absent after restart recovery;
- corrupt durable state rejected fail-closed and authoritative state restored;
- unexpected exchange OPEN / local FLAT mismatch rejected as
  `UNMANAGED_EXCHANGE_POSITION`, entries disabled and recovery-critical set;
- journal-before-order-result recovery proved unfilled without duplicate order;
- filled entry / missing-stop crash-state recovery restored protection;
- stop-placed / pre-local-OPEN-promotion crash-state recovery preserved protection;
- OPEN position management with no Observation process present, including
  position-loop and CPU/RAM telemetry;
- verified operator force-close and final-flat cleanup paths.

The canonical `stop closes while process offline` case is accepted by documented
deterministic equivalent plus supporting physical Testnet evidence rather than by
forcing Testnet market movement.  Two physical attempts proved that the native
exchange stop remained present while Execution was offline; one attempt remained
open and reconciled safely, while an intentionally over-tight replacement was
correctly rejected as `TESTNET_STOP_ALREADY_BREACHED_OR_INVALID` without removing
the existing protection.

Permanent deterministic coverage for the offline-stop settlement path includes:

- `StopRecoveryTests.test_active_breached_stop_settles_during_grace`, proving
  settlement during reconciliation returns `POSITION_CLOSE_RECOVERED`;
- `V319CloseRecoveryTests.test_recover_finished_algo_stop_when_user_trades_missing`,
  proving finished Binance algo-stop evidence recovers the close as
  `PROTECTIVE_STOP_TRIGGERED`.

This use of deterministic-equivalent evidence follows the canonical V3.2
acceptance rule and avoids adding dangerous runtime fault-injection controls.

V3.2 acceptance requires all of the following to remain true:

- no duplicate exposure defect;
- no accepted unprotected exposure defect;
- deterministic restart/reconciliation;
- no invented close price or realized PnL;
- corrupt/contradictory state fails closed;
- Execution manages OPEN capital with no Observation dependency;
- all 20 V3.2.3 entry/stop/emergency deterministic fault scenarios remain green;
- physical missing-stop and orphan-stop follow-ups remain proven;
- Testnet is FLAT and DISARMED at closure;
- full automated suite and compile checks pass;
- Git worktree is clean before the final phase tag.

Only after those checks pass may the release be tagged:

`v3.2-execution-testnet-mechanical-proven`

The next implementation phase is V3.3 Observation evidence foundation.

## V3.6 two-VPS dry integration

V3.6 converts the V3.5 protocol into a real two-VPS runtime while the
integrated Binance order gate remains physically disarmed.

### Observation Testnet operational canary

The protected LIVE collector remains a separate service and continues to own:

```text
data/observation/live/observer.db
runtime/observation/live/observation.lock
```

The V3.6 Testnet canary uses the normal Observation runtime with a different
profile, database, lock, service identity and control port:

```text
profile=testnet-trade
data/observation/testnet/observer.db
runtime/observation/testnet/observation.lock
127.0.0.1:8766
nbot-observation-testnet-control.service
```

Install the service from:

```text
deploy/systemd/nbot-observation-testnet-control.service.in
```

The service sources only `config/secrets/control-link.env`; Observation must
still contain no Binance private/order credential.

### Encrypted Execution -> Observation transport

The canonical V3.6 deployment uses a loopback-only Observation API behind an
SSH-encrypted forward.  The tracked template is:

```text
deploy/systemd/nbot-control-tunnel-testnet.service.in
```

The Execution-side endpoint is therefore normally:

```text
NBOT_OBSERVATION_TESTNET_URL=http://127.0.0.1:18766
```

Direct HTTPS/private-network transport may replace the SSH tunnel later without
changing the protocol or Execution capital boundary.

### Disarmed integrated dry cycle

With Testnet explicitly DISARMED:

```bash
./run_execution.py --profile testnet-trade --v36-dry-cycle
```

This command never constructs an exchange adapter or `EntryLifecycle`.  It may:

1. validate authenticated Observation health and exact release/profile lineage;
2. deliver already-durable pending outcomes and remove them only after valid ACK;
3. request one recommendation while FLAT;
4. record a returned Testnet operational proposal as vetoed with
   `V3_6_INTEGRATED_ORDER_GATE_DISARMED`;
5. log what the integrated path would have done.

It cannot place an order.  If Testnet is armed, local capital state is OPEN or
inflight, recovery is critical, Observation is unavailable, release/profile
validation fails, or a pending outcome lacks valid ACK, the dry path fails
closed and does not request/consume new execution permission.

Actual integrated Binance Testnet order writes remain V3.7.

## V3.8 Observation base-role services

After V3.8.4 physical epoch acceptance, Observation is boot-managed as a small
base role rather than a collection of manual Python processes.

Always enabled on the Observation VPS:

```text
nbot-observer.target
  |- nbot-observation-live.service    # continuous raw LIVE collector
  `- nbot-research-epoch.timer        # persistent scheduler
       `- nbot-research-epoch.service # low-priority oneshot only when invoked
```

The epoch service runs `research-epoch-run --prune-raw`. If 96 mature events do
not yet exist it exits normally with a wait status; it is not a permanent Python
daemon. Collector and research commands use separate responsibilities and
research is scheduled with lower CPU/I/O priority.

There is no SQLite or "DB atomic split" service. SQLite is embedded. The epoch
application copies one bounded raw dependency window to disposable workspace,
imports only sealed compact memory, then deletes scratch after success and
prunes raw data only behind the qualified dependency watermark.

`nbot-observation-live-paper-control.service` is optional and should be enabled
for reboot persistence only while the integrated LIVE_PAPER Execution boundary
is deliberately active. `nbot-observation-testnet-control.service` remains
regression-only and disabled outside explicit Testnet campaigns.

Render/install the base units with:

```bash
/root/Nbot/.venv/bin/python deploy/observation/install_services.py \
  --repo /root/Nbot \
  --python /root/Nbot/.venv/bin/python \
  --user root \
  --enable
```

Do not pass `--start` while a manually launched LIVE collector still owns
`runtime/observation/live/observation.lock`. Perform a controlled handover so
there is never a duplicate writer.

## V3.8 operator visibility, Telegram and trade panel

V3.8 restores the useful V1/V2.8.5 operator surface before persistent
LIVE_PAPER execution begins.  Operator tooling is observational/control-plane
only; it never becomes research or capital authority.

### Rotating logs

Execution LIVE_PAPER:

```text
logs/execution/paper/execution.log       # capital/runtime/operator operations
logs/execution/paper/trades.log          # concise trade lifecycle/audit
logs/execution/paper/runtime.stdout.log  # nbotctl-launched stdout/stderr only
```

Observation LIVE:

```text
logs/observation/live/collector.log
logs/observation/live/control.log
logs/observation/live/research.log
```

All rotating files use the V3 common logger default: 5 MiB, three backups.
Systemd journal remains available independently for boot/restart/process
forensics.

Examples:

```bash
# Execution
./nbotctl logs live-paper --component execution --lines 200
./nbotctl logs live-paper --component trades --follow
./nbotctl position live-paper
./nbotctl health live-paper
./nbotctl recent live-paper
./nbotctl pnl live-paper

# Observation
./nbotctl logs --component collector --lines 200
./nbotctl logs --component control --follow
./nbotctl logs --component research --lines 200
```

### Telegram secret files

Execution LIVE_PAPER optionally reads:

```text
config/secrets/execution-live-paper.env
```

Example keys:

```text
EXECUTION_TELEGRAM_BOT_TOKEN=
EXECUTION_TELEGRAM_CHAT_ID=
EXECUTION_TELEGRAM_OPERATOR_USER_ID=
NBOT_TELEGRAM_TIMEOUT_SECONDS=5
```

Observation may optionally read:

```text
config/secrets/observation-live.env
```

for best-effort **outbound notifications only**:

```text
OBSERVATION_TELEGRAM_BOT_TOKEN=
OBSERVATION_TELEGRAM_CHAT_ID=
NBOT_TELEGRAM_TIMEOUT_SECONDS=5
```

The Observation VPS does **not** own a Telegram command listener and does not
consume `getUpdates`. The single operator command bot runs on Execution.
Observation/research commands are served through Execution's authenticated
read-only control-link proxy. Both secret files remain ignored by Git and should
be mode `0600`.

### Execution trade panel

Execution owns one best-effort editable Telegram panel for the capital-bearing
position.  The panel is created only after the position is durably OPEN and the
protective stop is verified.  The same message is edited after meaningful
verified protection changes and finally edited from authoritative close history.

The panel includes profile, symbol/side, entry, initial/current/final stop,
quantity, initial risk, MFE/MAE, authority, exit policy, proposal ID, realized
PnL/R, exit reason, outcome ID and Observation ACK state where available.

Panel metadata lives at:

```text
data/execution/<profile-leaf>/operator_state.json
```

It is deliberately outside `execution_state.json`.  Corrupt/missing Telegram
metadata must never fail closed capital management; the panel may be recreated
from durable position/history truth after restart.

### Telegram commands

Execution bot:

```text
/status
/position
/health
/recent
/pnl

# read-only Observation/research proxy
/observation
/recommendation
/memory
/epoch
/champion
/challenger
/governance
/research
/paper
/learning
/db

# capital controls
/disable
/enable
/help
```

The Observation/research commands above use the authenticated control link as a
read-only proxy. Observation builds the status document; Execution only displays
it. No Observation research/learning module is imported into the Execution
worker, and a failed/slow status request runs only on the Telegram listener
thread. It cannot block or mutate open-position management, entry state, risk,
stops, promotion, rollback, or research evidence. This preserves the useful V1
`/learning` proxy pattern while keeping the V3 worker boundary.

`/disable` creates an additional durable local entry block and leaves OPEN
position management fully active.  `/enable` can remove only that operator
block and then must pass current reconciliation/profile/arm/risk/authority
gates. At the V3.8.6 checkpoint `NON_PROMOTIONAL_DRY` rejects `/enable` by design. V3.8.7 replaces only that gate with an authenticated one-entry operational-canary gate; all capital/risk/reconciliation checks remain final.
Emergency flatten is intentionally not exposed through Telegram.

There is exactly one Telegram **command** surface: the Execution bot above.
It registers all 19 supported commands with Telegram at startup using the Bot
API. Registration is best-effort and runs on the Telegram dispatcher thread, so
Telegram latency/failure cannot delay capital management. The eleven
Observation/research views remain read-only remote status requests: Observation
builds the documents and Execution displays them. Observation itself never
long-polls Telegram and never owns a second command menu.

Queued Telegram commands are discarded when a listener starts.  This prevents
an old `/enable` retained by Telegram while a worker was offline from changing
a restarted worker.

### LIVE_PAPER Execution systemd unit

Render/install without starting:

```bash
/home/ubuntu/Nbot/.venv/bin/python deploy/execution/install_services.py \
  --repo /home/ubuntu/Nbot \
  --python /home/ubuntu/Nbot/.venv/bin/python \
  --user ubuntu \
  --enable
```

The unit uses both ignored local files:

```text
config/secrets/execution-live-paper.env  # Telegram/runtime operator settings
config/secrets/control-link.env          # authenticated Observation endpoint
```

and runs `run_execution.py --profile live-paper` with `Restart=always`.
Installing/enabling the unit does not create paper-entry authority. V3.8.7 startup/restart still begins with entries disabled; a fresh Telegram `/enable` succeeds only while authenticated Observation health is `READY` with exact authority `LIVE_PAPER_OPERATIONAL_CANARY_V1`, and one protected OPEN immediately consumes that permission.

### V1 operator capability inventory retained in V3

Useful V1 concepts retained or reintroduced in V3 are: separate system/trade
logs, startup/reconciliation visibility, open/close trade receipts, editable
trade panel, restart panel recovery, status/position/health/PnL/recent-trade
queries, safe enable/disable semantics, stale Telegram-command flushing,
read-only learning/research visibility, and fire-and-forget notification
failure handling.  V3 deliberately does not restore V1 Strategy/Universe or
learning writes inside Execution, shared state files, or Telegram emergency
flatten authority.


## V3.8.7 LIVE/PAPER operational canary

This subphase is mechanical/operational only. It deliberately does not invent a Research Champion or expected economic edge. Observation proposals are labeled `LIVE_PAPER_OPERATIONAL_CANARY_V1`, `research_evidence=false`, `economic_claim=false`, and use a 30-second TTL from a fresh canonical LIVE point-in-time event.

Execution remains fail-closed on startup and after every restart. To permit one paper entry, the operator sends `/enable` to the running Execution Telegram bot. The command first checks authenticated Observation health, same release/protocol/lineage, `READY`, and exact operational authority, then reconciles locally before opening the entry gate. The first eligible FLAT proposal attempt immediately disables new entries again, whether or not a position opens.

Operational evidence is retained in Execution proposal receipts and the Observation outcome record: proposal receive latency, Execution-owned bid/ask/mid/spread, reference-price deterioration, fill deterioration, actual paper R, MAE/MFE, holding time, and outcome-delivery timing. Review it with:

```bash
./.venv/bin/python nbot_admin.py live-paper-canary-report
```

The report must continue to state `economic_claim=false` and `NO_RESEARCH_CHAMPION_EXPECTED_R_IN_OPERATIONAL_CANARY` until a later validated research authority supplies an expected after-cost result. Operational PASS must never be relabeled as economic PASS.
