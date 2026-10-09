# All-mode operator command reference

Reviewed 2026-10-09 against the current NBOT V3 `nbotctl` parser and three-mode
cluster unit map. This is an operator syntax reference, not economic approval.
Run only one Execution mode at a time.

| Profile | Market prices | Orders | Arm required? |
|---|---|---|---|
| `testnet-trade` | Binance Testnet | Pretend-money exchange orders | Yes: `./nbotctl arm testnet-trade` |
| `live-paper` | Binance LIVE public market | Local simulated orders only | No arm file |
| `live-trade` | Binance LIVE market/account | Real-money exchange orders | Yes: `./nbotctl arm live-trade --confirm-real-money` |

There is no Testnet-paper profile.

## Read-only checks for every mode

On the Execution VPS:

~~~bash
cd "$HOME/Nbot"
./nbotctl status

./nbotctl doctor testnet-trade
./nbotctl doctor live-paper
./nbotctl doctor live-trade

./run_execution.py --profile testnet-trade --self-check
./run_execution.py --profile live-paper --self-check
./run_execution.py --profile live-trade --self-check
~~~

`doctor` and `--self-check` do not authorize entries. A live-trade doctor may
correctly report missing real-money authorization until that separate trial is
deliberately configured.

## Start and enable

### Testnet trading

~~~bash
cd "$HOME/Nbot"
./nbotctl arm testnet-trade
./nbotctl cluster doctor testnet-trade
./nbotctl cluster start testnet-trade
./nbotctl cluster status testnet-trade
./nbotctl entries enable testnet-trade
./nbotctl cluster status testnet-trade
~~~

### LIVE paper

~~~bash
cd "$HOME/Nbot"
./nbotctl cluster doctor live-paper
./nbotctl cluster start live-paper
./nbotctl cluster status live-paper
./nbotctl entries enable live-paper
./nbotctl cluster status live-paper
~~~

`live-paper` has no arm/disarm command. Learned paper still requires compatible
Observation health and can correctly remain flat when no positive opportunity exists.

### LIVE trading

Only after the user has deliberately configured and accepted the bounded
real-money trial:

~~~bash
cd "$HOME/Nbot"
./nbotctl arm live-trade --confirm-real-money
./nbotctl cluster doctor live-trade
./nbotctl cluster start live-trade
./nbotctl cluster status live-trade
./nbotctl entries enable live-trade
./nbotctl cluster status live-trade
~~~

Arming and enabling are separate gates. Neither guarantees that an order will be
placed; all normal risk, freshness, one-position, session and protection checks
still apply.

## Daily state and logs

Use the same operator surface for each profile:

~~~bash
./nbotctl cluster status testnet-trade
./nbotctl position testnet-trade
./nbotctl health testnet-trade
./nbotctl recent testnet-trade
./nbotctl pnl testnet-trade
./nbotctl logs testnet-trade --lines 100

./nbotctl cluster status live-paper
./nbotctl position live-paper
./nbotctl health live-paper
./nbotctl recent live-paper
./nbotctl pnl live-paper
./nbotctl logs live-paper --lines 100

./nbotctl cluster status live-trade
./nbotctl position live-trade
./nbotctl health live-trade
./nbotctl recent live-trade
./nbotctl pnl live-trade
./nbotctl logs live-trade --lines 100
~~~

Add `--follow` to a log command when you intentionally want to stream it.

## Pause new entries

These commands do not close an existing position. Position management remains
active.

~~~bash
./nbotctl entries disable testnet-trade
./nbotctl entries disable live-paper
./nbotctl entries disable live-trade
~~~

Resume only after checking the selected profile is healthy:

~~~bash
./nbotctl entries enable testnet-trade
./nbotctl entries enable live-paper
./nbotctl entries enable live-trade
~~~

Testnet must still be armed. LIVE trading must still have a valid current
real-money trial arm. Learned paper enable remains subject to Observation readiness.

## Safe stop

First disable entries. Wait until the chosen profile is safe and flat:
no open position, no entry inflight, no pending outcome, and no recovery-critical
state. Then stop that profile explicitly:

~~~bash
./nbotctl cluster stop testnet-trade
./nbotctl cluster stop live-paper
./nbotctl cluster stop live-trade
~~~

After a safe stop, end session authorization where that concept exists:

~~~bash
./nbotctl disarm testnet-trade
./nbotctl disarm live-trade
~~~

There is no `disarm live-paper`.

## Crash/open-position recovery

Do **not** use `cluster start` as an emergency recovery path for an already-open
or otherwise unresolved capital state. The cluster launcher deliberately performs
remote checks that are not part of the open-position safety path.

For Testnet and LIVE trading, the local Execution recovery command is:

~~~bash
./nbotctl start testnet-trade
./nbotctl status
./nbotctl health testnet-trade

./nbotctl start live-trade
./nbotctl status
./nbotctl health live-trade
~~~

The installed LIVE-paper worker is systemd-managed, so direct `nbotctl start
live-paper` is intentionally refused when that unit is installed. Recover/start
the same paper worker with:

~~~bash
sudo systemctl start nbot-execution-live-paper.service
./nbotctl status
./nbotctl health live-paper
~~~

Recovery never means deleting state, lock, arm, receipt or pending-outcome files.

## Observation-side services

The shared base LIVE collector and research timer are:

~~~bash
systemctl is-active nbot-observation-live.service
systemctl is-active nbot-research-epoch.timer
~~~

Profile control units are:

~~~bash
systemctl is-active nbot-observation-testnet-control.service
systemctl is-active nbot-observation-live-paper-control.service
systemctl is-active nbot-observation-live-trade-control.service
~~~

Execution-to-Observation tunnel units on Trading are:

~~~bash
systemctl is-active nbot-control-tunnel-testnet.service
systemctl is-active nbot-control-tunnel-live-paper.service
systemctl is-active nbot-control-tunnel-live-trade.service
~~~

Only start the control/tunnel set for the selected mode. `nbotctl cluster start`
and `cluster stop` are the preferred orchestration surface once all units are
installed correctly.

## Learning and experiment reports

These Observation-side commands are independent of which Execution profile is
currently selected:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py research-epoch-status
.venv/bin/python nbot_admin.py challenger-status
.venv/bin/python nbot_admin.py governance-status
.venv/bin/python nbot_admin.py learning-report --output logs/learning-report.md
~~~

Learned paper has the additional paper-feedback report:

~~~bash
.venv/bin/python nbot_admin.py paper-learning-report --output logs/paper-learning-report.md
~~~

Shadow simulation exists alongside learned `live-paper` and learned
`live-trade`; Testnet has no shadow engine:

~~~bash
.venv/bin/python nbot_admin.py shadow-report --output logs/shadow-report.md
~~~

## Mode-switch rule

Never switch directly from one active profile to another. Disable entries, let
the current position finish, resolve pending outcomes, stop safely, disarm when
applicable, then run the start sequence for the next profile. Never delete durable
state to force a switch.
