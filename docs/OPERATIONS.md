# NBOT V3 Operations

For today's learned-Testnet installation, start with the
[beginner guide](TWO_VPS_BEGINNER_GUIDE.md) and
[small-VPS settings](SMALL_VPS_LEARNER.md). This reference also preserves older
phase-specific commands and evidence; those sections are not a fresh-install
checklist. See the [documentation index](DOCUMENTATION_INDEX.md).

## Current operating boundary

Current checkpoint: `V3.9 IMPLEMENTATION COMPLETE / ECONOMIC EVIDENCE ACCUMULATING`.

The intended deployment architecture is the two-VPS split below. Check runtime
status to establish which services and releases are actually installed:

- **Observation VPS** — LIVE/Testnet evidence, compact research memory, continuous challenger learning, governance, recommendation/control service; no Binance order authority.
- **Execution VPS** — independent market/account truth, proposal validation, risk, orders where the profile permits them, stops, OPEN management, reconciliation, emergency action and durable outcomes.

Current authority state must be read from runtime status and never inferred from phase completion. Until a Research Champion is explicitly eligible and promoted under the frozen V3.9 boundary:

- Research Champion = `NONE`;
- Paper Champion = `NONE`;
- Execution research authority = `NONE`;
- Paper Champion evidence collection remains blocked;
- An explicit small mainnet trial is available; see [mode setup and recovery](TRADING_MODES.md). Automatic Champion approval remains unpassed.

The explicit `TESTNET_LEARNED_EXPERIMENT_V1` path can use an unevaluated,
non-rejected model without a Research Champion. It does not grant research
authority or change the LIVE/PAPER operational canary. Normal Testnet selection
is learned; mechanical selection requires an explicit test-mode choice.

### Current learning and resource checks

On Observation, `.venv/bin/python nbot_admin.py learning-report` explains setup
support and saved rejection reasons. Add `--output logs/learning-report.md`
to save it, then copy it and consistent database backups off-server yourself.
No automatic off-server backup is installed.

The learner combines accumulated Ridge training with a recent 20-day
setup/condition filter. It evaluates frozen models on disjoint future events;
a complete 20+20 window takes roughly seven days plus final label maturity.
Research targets use four-hour simulated ATR-based R, not actual execution P&L.
Use the opt-in `tiny` resource profile for the planned 1 CPU / 1 GB learner;
monitor the actual machine because service limits are not a capacity guarantee.

### Continuous research cadence

`nbot-research-epoch.timer` is a 15-minute maturity checker, not an 8-hour scheduler. The research system advances only when a genuine new 96-event epoch plus required future context is mature. After a successful durable epoch commit, the epoch-to-challenger transition creates exactly one challenger opportunity.

Required semantics:

- `WAIT_FOR_MATURE_EPOCH` -> no challenger;
- unhealthy/failing epoch -> no challenger;
- uncommitted epoch -> no challenger;
- new durable epoch commit -> exactly one challenger opportunity;
- retry/restart of the same consumed epoch -> no duplicate challenger;
- challenger failure after epoch commit -> transition remains durable and retryable.

An opportunity can evaluate an existing frozen challenger and return
`EVALUATE_WAIT`; it need not train a new model. New epochs continue while
that challenger waits. Its training cutoff may precede the current epoch end.

The former fixed daily `nbot-challenger-cycle.timer` is retired. `nbot-challenger-cycle.service` remains only as a low-priority recovery/oneshot surface for the durable transition path.

### Safe current checks

On Execution:

```bash
./nbotctl status
./nbotctl doctor live-paper
./nbotctl doctor testnet-trade
```

On Observation:

```bash
./.venv/bin/python nbot_admin.py research-epoch-status
./.venv/bin/python nbot_admin.py challenger-status
./.venv/bin/python nbot_admin.py governance-status
./.venv/bin/python nbot_admin.py research-champion-review
./.venv/bin/python nbot_admin.py paper-champion-status
```

Do not run `research-epoch-run` or `challenger-cycle` merely to force evidence. Natural market maturity owns the research clock.

### Pre-V3.10 operator-tooling debt

The remaining operator-tooling gaps are tracked in `docs/PRE_V310_GAP_LEDGER.md`. Observation database integrity and local/control-link protocol compatibility are part of `nbotctl doctor`. The remote compatibility probe is an operator/pre-start diagnostic only; Execution worker startup deliberately excludes that network dependency so an existing OPEN position can still reconcile/manage during Observation loss. The V3.9 pre-V3.10 cluster orchestration surface is implemented as an Execution-side operator tool and remains outside all worker/reconciliation hot paths.

### Pre-V3.10 cluster orchestration

The **Execution VPS is the cluster control point** for the current two-VPS deployment. This is deliberate: Execution already owns the installed, strict-host-key-checked SSH tunnel identity used to reach Observation. Cluster tooling derives the SSH target, identity-file path, service user and pinned loopback forward from the installed `nbot-control-tunnel-<profile>.service`; it does not introduce a second hostname/key configuration and does not copy private keys into Git.

Supported operator commands are:

```bash
./nbotctl cluster doctor live-paper
./nbotctl cluster start live-paper
./nbotctl cluster stop
./nbotctl cluster status
```

`testnet-trade` uses the same orchestration contract when its learned-Testnet Observation control/tunnel units are installed and Testnet is legitimately armed. The separate live-trade route requires explicit small-trial authorization; see [the mode guide](TRADING_MODES.md).

`cluster doctor` is read-only. It fails closed on local/remote doctor failure, dirty trees, wrong roles, wrong profile contract, protocol mismatch, SHA mismatch, tag asymmetry, missing units, unpinned control endpoint, invalid SSH tunnel definition, or incompatible authenticated runtime control health when the tunnel is active. Both sides may be untagged only when they are on the exact same SHA; if either side has an exact tag, tag parity is required.

`cluster start` performs orchestration only while local Execution durable state is safe for orchestration. If an Execution runtime is already active, the command becomes an idempotent health/compatibility check. If Execution is not active but durable state contains an OPEN position, entry-inflight, pending outcome, or recovery-critical state, **cluster start refuses before creating an SSH/network dependency**. Use the local Execution service/recovery procedure for that capital state. Cluster start must never be used to recover an OPEN position.

For a safe FLAT start, ordering is:

1. static local + SSH remote doctor and exact release/protocol/profile checks;
2. create/retain the durable local operator entry block;
3. restart only the profile Observation control service;
4. restart only the profile Execution-to-Observation SSH tunnel;
5. prove authenticated runtime control compatibility;
6. start the Execution worker;
7. prove the running Execution release/READY state and rerun cluster doctor.

Cluster start **never enables entries** and creates no research, Paper Champion, or real-capital authority. LIVE_PAPER still requires its separate fresh operator `/enable` gate.

`cluster stop` is intentionally conservative. Before any SSH, service stop, or tunnel mutation it reads local durable Execution truth and refuses if any of the following are present:

- OPEN position;
- entry inflight;
- pending outcome;
- recovery-critical state;
- entries currently enabled;
- unreadable/invalid Execution state.

When safe and FLAT, it preserves the durable operator entry block, stops Execution first, rechecks safe durable state, then stops the profile tunnel and optional Observation control plane. It does **not** stop `nbot-observation-live.service`, `nbot-research-epoch.timer`, or `nbot-observer.target`.

SSH orchestration is therefore an operator convenience only. It is not imported by `run_execution.py` and never participates in OPEN position pricing, protection, trailing, reconciliation, emergency action, or durable outcome creation.

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

Historical phase procedure: the current Testnet control service defaults to
learned recommendations. Reproducing the old mechanical experiment requires
explicit `--testnet-selection mechanical` in a separate test run. Use the
beginner guide for normal learned-Testnet startup.

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
is deliberately active. `nbot-observation-testnet-control.service` is separately enabled for learned
Testnet operation; it is not part of the base target. The installer defaults
to learned selection. Mechanical canaries remain explicit test tools.

From the prepared repository root, install and enable the base units with:

```bash
sudo .venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" \
  --python "$PWD/.venv/bin/python" \
  --user "$(id -un)" \
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

The Execution bot registers exactly eight commands at startup:

| Command | What it does |
|---|---|
| /help | Lists the eight commands |
| /status | Trading state, recommendation readiness and waiting reason |
| /position | Current trade, size and stop-loss |
| /recent | Most recently completed trade and result |
| /pnl | Current UTC-day results and daily risk limits |
| /learning | Model test progress, later evidence, passes and rejections |
| /enable | Requests new trades, subject to every safety gate |
| /disable | Pauses new trades while continuing open-position management |

Only /enable and /disable change trading permission. They do not switch trading
mode or start real-money trading. Daily reporting uses UTC (05:30 IST reset).
Learning test counts alone do not prove increasing profitability.

Status and learning use authenticated read-only requests to the Learning VPS.
Requests run on the command listener, never on the open-position management
thread. If the Learning VPS is unavailable, local status remains available.

Detailed diagnostics remain available through nbotctl, nbot_admin.py and the
authenticated operator-status API. Removed Telegram commands are rejected.

For channel notifications plus private commands, set these in the Execution
profile's private env file:

- EXECUTION_TELEGRAM_CHAT_ID: notification channel's numeric ID.
- EXECUTION_TELEGRAM_OPERATOR_USER_ID: your personal numeric Telegram user ID.
- EXECUTION_TELEGRAM_COMMAND_CHAT_ID: your private chat's numeric ID (normally
  the same as your personal user ID). Open the bot privately and press Start.

Command replies go to the command chat; automatic trade notifications stay in
the notification channel. Only the configured user in the configured command
chat is accepted. Channel posts are not commands. Leave COMMAND_CHAT_ID empty
to keep using the notification chat for both commands and replies, as before.
After env changes, restart the execution service and re-enable entries.
Do not commit private env files.

Observation owns no Telegram command listener. Safety gates, research evidence
and server-side diagnostic reports are unchanged by this simpler menu.

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
trade panel, restart panel recovery, status/position/PnL/recent-trade
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
