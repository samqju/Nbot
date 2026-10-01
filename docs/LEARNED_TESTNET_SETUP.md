# Running the learning bot on Testnet

For a complete first-time installation with copy-and-paste commands, use the
[beginner two-VPS guide](TWO_VPS_BEGINNER_GUIDE.md).

The bot watches LIVE markets and learns from completed examples. It uses its
saved model to rank buying/selling opportunities, then recommends one suitable
opportunity using a matching fresh Testnet quote. The Execution VPS independently
checks risk and manages at most one Testnet position. It repeats while explicitly
armed and enabled, within daily-risk and persistent session limits.

No LIVE orders are enabled. Testnet results test the machinery and are recorded
separately; they never become LIVE training labels or proof of profitability.
The learned model combines Ridge regression over momentum, reversal, volatility,
liquidity and market-context features with a recent setup/condition filter.
The filter can reduce scores or veto a trade; it cannot raise the original score.
Research compares
the existing exit-policy families; executed trades retain INTEGER_R_STEP_CONTROL.
The bot does not invent arbitrary strategy code or automatically deploy new exit
algorithms. Positive model predictions are estimates, not guarantees.

For a 1 CPU / 1 GB test server, follow the [small-VPS learner instructions](SMALL_VPS_LEARNER.md).
Use **learning-report** to see setup evidence and plain-English rejection reasons.

## New Observation VPS

Use Linux and Python 3.12. Clone this repository, create `.venv`, install
`requirements.txt`, and put `OBSERVATION` in `.nbot-role`. Use the same Git commit
as Execution. No Binance private key belongs on this VPS.

Create `config/secrets/control-link.env` from the example with a strong shared
control token matching Execution. Keep that directory mode 0700 and the file
0600. Use an SSH tunnel or TLS; do not expose an unauthenticated public endpoint.

From the repository root, as the service user:

```bash
.venv/bin/python nbot_admin.py research-memory-init
sudo .venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" --python "$PWD/.venv/bin/python" --user "$(id -un)" \
  --enable --start --enable-testnet-control --start-testnet-control
```

This starts the LIVE collector, periodic research jobs, and a separate Testnet
collector/control service on loopback port 8766. Training stays out of the
collector and HTTP request threads. `research-memory-init` is idempotent and
does not reset an existing initialized memory store.

If retaining old learning, migrate a copy with the instructions in
[SEVEN_SAFETY_FIXES.md](SEVEN_SAFETY_FIXES.md) before starting research writers.
Do not run a fresh reset over that memory. A missing/corrupt/incompatible model
blocks suggestions; it does not fall back to random trades.

## Existing Execution VPS

1. Update to the same Git commit. Stop the old profile only when it is flat with
   no unresolved entry or pending outcome; preserve all state and receipts.
2. Put **Testnet** credentials in `config/secrets/execution-testnet.env` and the
   matching control token in `config/secrets/control-link.env` (both mode 0600).
3. Point the installed `nbot-control-tunnel-testnet.service` at the new Observation
   SSH host, user and key. Its forwarding is local 18766 to Observation 8766.
   Verify the SSH host key. The template is in `deploy/systemd/`.
4. Verify both roles and clock synchronization with `nbotctl doctor`; configure
   the new SSH destination before using the cluster commands.
5. When ready to test, explicitly arm and start the Testnet profile:

```bash
./nbotctl arm testnet-trade
./nbotctl cluster start testnet-trade
./nbotctl entries enable testnet-trade
./nbotctl cluster status testnet-trade
```

Arming does not bypass model readiness. While waiting, the worker stays flat.
`./nbotctl entries disable testnet-trade` blocks new entries while open-position
protection continues. Never use deletion of state/arm/session files to bypass a
limit or an unresolved order. The existing explicit re-arm/session controls apply.

The current Testnet cluster launcher starts Execution as a managed local process;
after a VPS reboot, rerun the checked start sequence. Observation's installed
services are boot-managed. Do not start a second execution process manually.

## What to expect

A new empty installation does not trade immediately. It needs 48 past bars,
96 eligible five-minute targets and their 48-bar future outcomes: roughly
16 hours of continuous usable data, plus research processing time. Gaps and
incomplete evidence can extend that. A model with no positive opportunity can
correctly make no trades for longer.

Every completed research epoch advances saved learning. A frozen challenger is
evaluated on genuinely future, non-overlapping events; epochs continue even
while it waits. Twenty validation and twenty final-test events are spaced four
hours five minutes apart: allow roughly seven days of future data plus the final
outcome maturity, longer with gaps. Once evaluation finishes, the cycle trains its successor. A
rejected model is not used; a compatible older non-rejected model may be used.
Testnet experimental use does not promote a Research or Paper Champion.

Useful Observation commands:

```bash
.venv/bin/python nbot_admin.py research-epoch-status
.venv/bin/python nbot_admin.py challenger-status
.venv/bin/python nbot_admin.py learning-report --output logs/learning-report.md
.venv/bin/python nbot_admin.py research-memory-status
journalctl -u nbot-observation-testnet-control.service -n 50
journalctl -u nbot-research-epoch.service -n 50
```

Health reasons distinguish waiting for LIVE collection, a compatible model,
feature history or a matching Testnet event. Stale data, corrupt artifacts and
inference errors stop new recommendations. `LEARNED_NO_POSITIVE_OPPORTUNITY`
means the model chose not to trade. To exercise order plumbing without a learned
model, explicitly use `--testnet-selection mechanical` in a separate mechanical
test run; those suggestions are not learned selections.

## Acceptance on the actual servers

A fresh server cannot reproduce the old date-specific market-regime research
report. It will show `UNAVAILABLE_HISTORICAL_CALIBRATION`. This does not stop
Testnet learning, and does not count as passing that historical research audit.

Automated tests simulate exchange behavior. After both VPSs are configured,
verify authenticated Testnet LONG/SHORT entry, protective stop, close and outcome
acknowledgement; restart Execution while open; interrupt the Observation link;
and confirm duplicate proposals cannot create another order. Preserve the logs.
Do not call those physical tests passed merely because unit tests passed.
