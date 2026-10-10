# Three trading modes: simple setup and switching guide

**Current detailed-outcome learning:** [Automatic paper learning from accepted and rejected opportunities](DETAILED_OUTCOME_LEARNING.md) documents the V3 tick-outcome bridge, future evaluation, automatic paper-model replacement, rollback and resource limits. V2 remains the fallback.


For a compact validated command matrix, see
[ALL_MODES_COMMANDS.md](ALL_MODES_COMMANDS.md).

See also [the shadow simulation guide](SHADOW_TRADING.md): up to ten additional, separate simulated positions; the main account still permits only one position.

Paper feedback update: [30-day auto-learning experiment](PAPER_AUTO_LEARNING.md). Learned mainnet-paper now adapts setup rankings from its own settled paper trades. Testnet and real-money selection remain separate; economic proof is still unestablished.


Updated 2026-10-05. This is a small, manually approved mainnet trial, not automatic
Research/Paper Champion approval or a promise of profit.

| Mode name in commands | Prices | Orders |
|---|---|---|
| testnet-trade | Binance Testnet | Pretend-money exchange orders |
| live-paper | Real market | Local simulation, no exchange orders |
| live-trade | Real market | Real-money exchange orders, only after explicit approval |

There is no Testnet-paper mode. Run only one Execution mode at a time.
The Learning VPS never receives Binance trading keys.

## 1. Finish the basic two-server installation first

Follow [the beginner guide](TWO_VPS_BEGINNER_GUIDE.md) through the two-server
installation, SSH verification, shared connection token, and Testnet testing.
That guide creates the ubuntu user setup, ~/Nbot checkout, .venv, role file,
Learning database, and ~/.ssh/nbot_observation on Trading. The commands below
assume those exact paths and user. Use the same Git commit on both servers.

On an existing installation, first follow section 6 below to disable entries and
stop Execution only after it is flat. Then, on **both servers**:

~~~bash
cd "$HOME/Nbot"
git status --short
git pull --ff-only origin main
git rev-parse HEAD
~~~

Both printed commit IDs must match. If Git reports local changes or a conflict,
stop and resolve them; do not delete private settings or stored trading state.
Follow the beginner guide's dependency installation steps if this is a fresh VPS.

## 2. Create private mode settings on Trading

Keep your existing config/secrets/control-link.env and its shared token.
Edit it with:

~~~bash
cd "$HOME/Nbot"
nano config/secrets/control-link.env
~~~

Add or update these lines, without changing the token:

~~~ini
NBOT_OBSERVATION_TESTNET_URL=http://127.0.0.1:18766
NBOT_OBSERVATION_LIVE_PAPER_URL=http://127.0.0.1:18765
NBOT_OBSERVATION_LIVE_TRADE_URL=http://127.0.0.1:18767
~~~

Save in nano with Ctrl+O, Enter, Ctrl+X.

Create the paper and real-mode private files only if they do not already exist:

~~~bash
cd "$HOME/Nbot"
install -d -m 700 config/secrets
.venv/bin/python - <<'PY'
from pathlib import Path
for name in ("execution-live-paper", "execution-live"):
    target = Path("config/secrets") / (name + ".env")
    if target.exists():
        print("Kept existing:", target)
        continue
    with target.open("x") as handle:
        target.chmod(0o600)
        handle.write((Path("config/examples") / (name + ".env.example")).read_text())
    print("Created:", target)
PY
nano config/secrets/execution-live-paper.env
~~~

Set NBOT_PAPER_SELECTION=learned. Telegram fields may stay blank.
Do not put Binance keys in the paper file.

Only when preparing your own mainnet trial, edit:

~~~bash
nano config/secrets/execution-live.env
~~~

| Field | What to fill |
|---|---|
| LIVE_API_KEY | Your mainnet USD-M Futures API key |
| LIVE_API_SECRET | The matching secret |
| LIVE_RISK_PER_TRADE_USD | Keep 0.25 initially; planned stop risk |
| LIVE_MAX_ENTRY_NOTIONAL_USD | Keep 25 initially; maximum total position value |
| LIVE_LEVERAGE | Keep 1 initially |
| LIVE_MAX_SESSION_ENTRIES | Keep 1; stops new entries after one attempt/session allowance is used |
| LIVE_REST_TIMEOUT_SECONDS | Keep 5 |
| LIVE_RECV_WINDOW_MS | Keep 5000 |
| EXECUTION_TELEGRAM_* | Optional operator bot fields; see the environment guide |

Do not paste keys into chat, GitHub, screenshots or the Learning VPS.
Use an API key without withdrawal permission and restrict it to your Trading
VPS IP. The adapter requires One-way position mode and Single-Asset Mode; it
refuses incompatible settings and does not silently change them.

The software caps this trial at $1 planned risk, $100 position value, 2x
leverage and 10 entries per approved session. Defaults are smaller.
A stop is not a guaranteed maximum loss: slippage, gaps and exchange faults
can cause a larger loss. Some symbols have exchange minimum order sizes above
the default $25 cap; refusing those trades is correct. The bot never increases
your limit to force an order through.

## 3. Install Learning control services

On **Learning**, render the additional services without starting trading:

~~~bash
cd "$HOME/Nbot"
sudo .venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" --python "$PWD/.venv/bin/python" --user ubuntu \
  --resource-profile standard
sudo mkdir -p /etc/systemd/system/nbot-observation-live-paper-control.service.d
printf '%s\n' '[Service]' 'Environment=NBOT_PAPER_SELECTION=learned' | \
  sudo tee /etc/systemd/system/nbot-observation-live-paper-control.service.d/selection.conf >/dev/null
sudo systemctl daemon-reload
~~~

Keep the existing base collector and research timer running. For 4 CPU / 8-12 GB, use standard as above and see the
[24-candidate guide](CANDIDATE_LIBRARY.md). On a 1 CPU/1 GB server, replace standard
with tiny and use [tiny settings](SMALL_VPS_LEARNER.md). Start only the control service
for the mode you use; cluster start below does this.

## 4. Install Trading tunnels and the paper worker

On **Trading**, using the SSH key and verified Learning host from the beginner
guide, render both additional tunnels:

~~~bash
cd "$HOME/Nbot"
read -rp "Learning VPS public IPv4 address: " OBS_IP
export OBS_IP
.venv/bin/python - <<'PY'
from pathlib import Path
import ipaddress
import os
ip = str(ipaddress.IPv4Address(os.environ["OBS_IP"]))
Path("runtime").mkdir(exist_ok=True)
for mode in ("live-paper", "live-trade"):
    name = "nbot-control-tunnel-" + mode + ".service"
    text = (Path("deploy/systemd") / (name + ".in")).read_text()
    text = text.replace("@NBOT_USER@", "ubuntu")
    text = text.replace("@NBOT_SSH_KEY@", str(Path.home()/".ssh/nbot_observation"))
    text = text.replace("@OBSERVATION_SSH_TARGET@", "ubuntu@" + ip)
    assert "@NBOT_" not in text and "@OBSERVATION_" not in text
    (Path("runtime")/name).write_text(text)
PY
sudo install -o root -g root -m 644 runtime/nbot-control-tunnel-live-paper.service /etc/systemd/system/
sudo install -o root -g root -m 644 runtime/nbot-control-tunnel-live-trade.service /etc/systemd/system/
sudo .venv/bin/python deploy/execution/install_services.py \
  --repo "$PWD" --python "$PWD/.venv/bin/python" --user ubuntu
sudo systemctl daemon-reload
~~~

The Learning IP belongs in the SSH service; all control HTTP addresses stay
127.0.0.1. Do not expose ports 8765, 8766 or 8767 publicly.
The mainnet worker uses nbotctl's managed process, like Testnet; it does not
have a new automatically enabled execution systemd service.

## 4a. Allow the additional service controls

The beginner guide grants password-free control of Testnet services only.
Add the matching new permissions so cluster start/stop can work.

On **Learning**:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python - <<'PY'
from pathlib import Path
units = ("nbot-observation-live-paper-control.service", "nbot-observation-live-trade-control.service")
commands = ["/usr/bin/systemctl " + action + " " + unit for unit in units for action in ("start", "stop", "restart")]
Path("runtime").mkdir(exist_ok=True)
Path("runtime/nbot-mode-controls.sudoers").write_text("ubuntu ALL=(root) NOPASSWD: " + ", ".join(commands) + chr(10))
PY
sudo visudo -cf runtime/nbot-mode-controls.sudoers &&
sudo install -o root -g root -m 440 runtime/nbot-mode-controls.sudoers /etc/sudoers.d/nbot-mode-controls
~~~

On **Trading**:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python - <<'PY'
from pathlib import Path
units = ("nbot-control-tunnel-live-paper.service", "nbot-control-tunnel-live-trade.service", "nbot-execution-live-paper.service")
commands = ["/usr/bin/systemctl " + action + " " + unit for unit in units for action in ("start", "stop", "restart")]
Path("runtime").mkdir(exist_ok=True)
Path("runtime/nbot-mode-controls.sudoers").write_text("ubuntu ALL=(root) NOPASSWD: " + ", ".join(commands) + chr(10))
PY
sudo visudo -cf runtime/nbot-mode-controls.sudoers &&
sudo install -o root -g root -m 440 runtime/nbot-mode-controls.sudoers /etc/sudoers.d/nbot-mode-controls
~~~

Expected: parsed OK. These commands add only the named service controls.
They do not start any service or change the existing Testnet permissions.

## 5. Start the chosen mode from Trading

Start with Testnet, then learned paper. Successful simulated operation does not
prove that a strategy will earn money.

**Testnet trading:**

~~~bash
cd "$HOME/Nbot"
./nbotctl arm testnet-trade
./nbotctl cluster doctor testnet-trade
./nbotctl cluster start testnet-trade
./nbotctl cluster status testnet-trade
./nbotctl entries enable testnet-trade
~~~

No real keys are used. Arming creates the explicit Testnet session boundary; it
does not bypass model or risk readiness.

**Learned mainnet paper:**

~~~bash
cd "$HOME/Nbot"
./nbotctl cluster start live-paper
./nbotctl cluster doctor live-paper
./nbotctl cluster status live-paper
./nbotctl entries enable live-paper
~~~

Paper does not need an arm file. Enabling entries requests permission; missing
models, stale data, safety vetoes or no eligible signal can still mean no trade.
The Observation and Execution paper selections must both be learned as above.

**Real-money trial, only after your own testing and decision:**

~~~bash
cd "$HOME/Nbot"
./nbotctl arm live-trade --confirm-real-money
./nbotctl cluster start live-trade
./nbotctl cluster doctor live-trade
./nbotctl cluster status live-trade
./nbotctl entries enable live-trade
~~~

Read each result before running the next command. Do not continue after an
error. Arming records your approval of the current clean Git commit, key and
risk settings. It does not start trading. Entries enable is the separate final
step. A settings/key/code change requires a new deliberate approval while
stopped and flat. Do not repeatedly re-arm to bypass the session allowance.

The learner proposes a ranked opportunity; Execution separately checks its
authority, freshness, one-position state, limits and protective orders.
The experimental route can use a compatible model that has not yet completed
economic validation, but excludes rejected models. It is not Champion approval.

## 6. Pause, stop, disarm and change modes

Pause **new entries** with the command for the selected profile:

~~~bash
./nbotctl entries disable testnet-trade
./nbotctl entries disable live-paper
./nbotctl entries disable live-trade
~~~

An existing position continues to be managed. Disabling entries does not close it.
Check the matching profile, and wait for no open position, no entry in progress,
no pending outcome and no recovery-critical state:

~~~bash
./nbotctl cluster status testnet-trade
./nbotctl cluster status live-paper
./nbotctl cluster status live-trade
~~~

Then stop only the selected profile:

~~~bash
./nbotctl cluster stop testnet-trade
./nbotctl cluster stop live-paper
./nbotctl cluster stop live-trade
~~~

Testnet and LIVE-trade sessions can then be deliberately disarmed:

~~~bash
./nbotctl disarm testnet-trade
./nbotctl disarm live-trade
~~~

LIVE paper has no arm/disarm state. When switching away from a paper installation
that was previously enabled at boot, after it safely stops run:

~~~bash
sudo systemctl disable nbot-execution-live-paper.service
~~~

Now start the next mode using section 5. Mode locks and durable-state checks
reject overlapping workers or a switch with unfinished work. Never delete lock,
guard, pending-outcome or state files to bypass a refusal.

## 7. Restart and crash recovery

Every learned paper/mainnet worker restart blocks new entries until you enable
them again. Session usage is persisted; restarting does not reset it.

If a Testnet or LIVE-trading managed process crashes, use the local recovery
path for that same profile:

~~~bash
cd "$HOME/Nbot"
./nbotctl start testnet-trade
./nbotctl status
./nbotctl health testnet-trade

./nbotctl start live-trade
./nbotctl status
./nbotctl health live-trade
~~~

The installed LIVE-paper worker is systemd-managed, so use its installed unit:

~~~bash
sudo systemctl start nbot-execution-live-paper.service
./nbotctl status
./nbotctl health live-paper
~~~

The worker reconciles exchange state before considering any entry. If saved
state shows an open position, in-flight entry or pending outcome, the direct
start path permits recovery without a current arm, provided other local checks
pass. An Observation outage must not prevent existing-position management.
Do not use cluster start as the emergency recovery path; its remote checks can
fail while Learning is offline. Do not switch modes or erase state to recover.

Mainnet's managed process does not automatically restart after a VPS reboot.
You must restart it and inspect reconciliation. An exchange-side protective stop
can survive the process, but local management needs the process running.
Automatic mainnet boot recovery remains future work.

## 8. What this release verifies

Automated tests exercise fake exchange responses, entry/stop/close handling,
uncertain responses, durable session limits, restart reconciliation, authority
separation, mode locking and permission checks. No real-money acceptance test
or profitability test is performed by publishing this release.

Low-level shared adapter errors may still contain TESTNET in their historical
names. Inspect the selected profile and endpoint; these labels do not switch
accounts.

See [environment settings](ENVIRONMENT_SETUP.md), [documentation index](DOCUMENTATION_INDEX.md)
and the [Binance USD-M API](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/general-info).

Operational note: the paper-only economic-approval disclaimer is informational.
Cluster startup still blocks actual safety, release, state and connection failures.

### Paper price-feed interruptions

If Binance supplies an old/invalid price timestamp or the public quote request
fails while a learned paper position is open, the worker keeps that position and
retries after at least five seconds. It never trades or moves the simulated stop
using the rejected price. Warnings (PAPER_QUOTE_UNAVAILABLE) are logged at most
once per minute during a continuous interruption; PAPER_QUOTE_RECOVERED records
recovery. The timestamp warning includes source time, receive time and quote age.
This avoids repeated worker restarts and their entry-disable side effect.
Actual process restarts still require entries to be enabled again.

A paper stop cannot be evaluated while fresh prices are unavailable. On recovery,
it uses the next valid observed quote; it does not invent fills for the missing
interval. This limitation matters when interpreting paper results.
