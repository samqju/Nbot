# NBOT two-VPS deployment guide

## Start here

For a completely new pair of VPSs:

- `deploy/FRESH_INSTALL.md`

For everyday start/stop/restart/status commands:

- `deploy/OPERATIONS.md`

For replacement/disaster recovery:

- `deploy/recovery/BACKUP_RESTORE.md`
- `deploy/recovery/DISASTER_RECOVERY.md`

The immutable Phase 6A rollback anchor remains:

```text
phase6a-final
```

The clean pre-Phase-6B deployment checkpoint produced by the Phase 6 Plan
Audit is:

```text
pre-phase6b-clean
```

Both VPSs must deploy the same exact approved tag/commit. The
`pre-phase6b-clean` tag is created only after the final Plan Audit acceptance
checks pass. Never move or rewrite an immutable release tag after publication.

This is the canonical deployment guide for the current two-worker NBOT
architecture.

NBOT uses **one Git repository and one exact Git version on both machines**.
The machines differ only by which role is started and which role-owned state
and secrets are restored.

```
                         Binance
                       /         \
                      /           \
             Execution VPS     Observation VPS
             -------------     ---------------
             run_execution.py  run_observation.py
             position/risk     candidate research
             paper/real state  virtual trades
             outcome outbox    learning/training
             SSH tunnel  ----> recommendation API
```

Never split this deployment into two independent repositories. Communication
contracts, schemas, strategy code, tests, and migration history must stay on the
same Git revision.

## 1. Role ownership

### Execution VPS

Execution owns capital-bearing state and order authority:

- `data/bot_state_<env>.json`
- `data/paper_state_<env>.json` in SHADOW mode
- `data/paper_trades_<env>.jsonl` in SHADOW mode
- `data/execution_outbox_<env>/`
- processed proposal IDs stored in bot state
- Execution logs and operator controls
- future Binance order-writing credentials

It runs:

- `nbot-observation-tunnel.service`
- `nbot-execution.service`

The umbrella unit is `nbot-execution.target`.

### Observation VPS

Observation owns research and learning state:

- candidate observations
- candidate outcomes
- virtual trades
- universe snapshots
- learning runtime state
- model registry/artifacts
- training, promotion, canary and learning status files

It runs:

- `nbot-observation.service`
- `nbot-auto-training.service`
- `nbot-promotion-controller.service`
- `nbot-paper-canary-controller.service`

The umbrella unit is `nbot-observer.target`.

Observation must not have order-writing authority.

## 2. Required operating-system packages

Ubuntu 24.04 is the reference environment. Install at least:

```bash
sudo apt-get update
sudo apt-get install -y git openssh-client python3 python3-venv python3-pip
```

The Observation VPS also needs `openssh-server` because Execution connects to
its restricted tunnel account:

```bash
sudo apt-get install -y openssh-server
```

## 3. GitHub access

Use a repository-scoped GitHub deploy key on each VPS.

- Observation may use a read/write deploy key when it is the maintenance host.
- Execution should use a read-only deploy key.
- Pin GitHub's SSH host key in a dedicated `known_hosts` file.
- Do not place private keys in Git.

After installing the deploy key, clone the repository and check out the exact
release tag selected for both machines:

```bash
export NBOT_REPO=/path/to/Nbot
export NBOT_VERSION=pre-phase6b-clean

git clone git@github.com:OWNER/Nbot.git "$NBOT_REPO"
cd "$NBOT_REPO"
git fetch --tags --prune
git checkout --detach "$NBOT_VERSION"
git status --short --branch
git rev-parse HEAD
```

Do not deploy `main` merely because it exists. Deploy the approved tag/commit.

## 4. Python environment

Use an explicit virtualenv path. Example:

```bash
export NBOT_VENV=/opt/nbot/.venv
sudo python3 -m venv "$NBOT_VENV"
sudo "$NBOT_VENV/bin/python" -m pip install --upgrade pip
sudo "$NBOT_VENV/bin/python" -m pip install -r "$NBOT_REPO/requirements.lock.txt"
"$NBOT_VENV/bin/python" -m pip check
```

The service installer deliberately preserves the supplied virtualenv launcher
path rather than resolving it to the system interpreter.

`requirements.lock.txt` is the production/runtime lock. The separate
`requirements-dev.lock.txt` layers lint/development tooling on top of it and
should not be installed merely to run either VPS role.

## 5. Runtime `.env`

`.env` is machine-local and must never be committed.

Restore it through a secure channel and set restrictive permissions:

```bash
chmod 600 "$NBOT_REPO/.env"
```

Each VPS has one role-specific `.env`; do not copy one role's file onto the
other machine. Start from the tracked templates:

- Execution: `deploy/examples/execution.env.example`
- Observation: `deploy/examples/observation.env.example`

Both workers must use the same `TRADING_ENV`, `EXECUTION_MODE`, and
`OBSERVATION_CONTROL_TOKEN`. One Execution `.env` contains both LIVE and
TESTNET surfaces so the operator can deliberately switch between LIVE+SHADOW,
TESTNET+SHADOW, and armed TESTNET+TRADE without maintaining multiple files.
One Observation `.env` contains both public LIVE/TESTNET market endpoints and
Observation/learning controls, but no private Binance credentials or
trade-arming authority. LIVE+TRADE order writing remains intentionally
fail-closed until the later real-capital roadmap stage.

Never print secrets to terminal history while validating deployment. Compare a
SHA-256 fingerprint of the control token instead of displaying its value.

## 6. Build the restricted Observer tunnel account

On the Observation VPS create a dedicated account that can only create the
local forward needed by NBOT:

```bash
sudo useradd --system --create-home --shell /bin/bash nbot-tunnel || true
sudo install -d -m 700 -o nbot-tunnel -g nbot-tunnel /home/nbot-tunnel/.ssh
sudo touch /home/nbot-tunnel/.ssh/authorized_keys
sudo chown nbot-tunnel:nbot-tunnel /home/nbot-tunnel/.ssh/authorized_keys
sudo chmod 600 /home/nbot-tunnel/.ssh/authorized_keys
```

Generate the tunnel key on Execution:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/nbot_observer_tunnel -N ''
chmod 600 ~/.ssh/nbot_observer_tunnel
```

Add the public key to the Observer account with restrictions. Replace
`EXECUTION_PUBLIC_IP` and the public-key text:

```text
from="EXECUTION_PUBLIC_IP",no-agent-forwarding,no-X11-forwarding,no-pty,no-user-rc,permitopen="127.0.0.1:8765" ssh-ed25519 PUBLIC_KEY
```

Install `/etc/ssh/sshd_config.d/90-nbot-tunnel.conf` on Observation:

```text
Match User nbot-tunnel
    AuthenticationMethods publickey
    PubkeyAuthentication yes
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding local
    PermitOpen 127.0.0.1:8765
    X11Forwarding no
    AllowAgentForwarding no
    PermitTTY no
    PermitUserRC no
    ForceCommand /bin/false
```

Validate before reloading SSH:

```bash
sudo sshd -t
sudo systemctl reload ssh
```

Do not expose TCP 8765 publicly. Observation listens on loopback; the SSH
tunnel transports the control API securely between VPSs.

## 7. Pin the Observer SSH host key on Execution

Obtain the Observer host-key fingerprint from an independent trusted source
(provider console or already-trusted session). Do not trust an unverified
`ssh-keyscan` result by itself.

Store the verified host key in a dedicated file such as:

```text
~/.ssh/nbot_observer_known_hosts
```

Set:

```bash
chmod 600 ~/.ssh/nbot_observer_known_hosts
```

## 8. Restore role-owned state

For a brand-new installation there may be no state to restore.

For replacement/disaster recovery, restore only the state owned by that role.
See `deploy/recovery/BACKUP_RESTORE.md` and
`deploy/recovery/DISASTER_RECOVERY.md` before starting services.

Never copy one mutable `data/` directory between both VPSs.

## 9. Install Observation services

From the repository on the Observation VPS:

```bash
sudo "$NBOT_VENV/bin/python" deploy/observation/install_services.py \
  --repo "$NBOT_REPO" \
  --python "$NBOT_VENV/bin/python" \
  --user "$(id -un)" \
  --enable
```

This installs the four service units plus `nbot-observer.target` and enables
the target for boot.

Start the complete Observation role with one command:

```bash
sudo systemctl start nbot-observer.target
```

Or on a fresh machine install, enable and start in one installer invocation by
adding `--start`.

Check:

```bash
systemctl status nbot-observer.target --no-pager
systemctl is-active nbot-observation.service
systemctl is-active nbot-auto-training.service
systemctl is-active nbot-promotion-controller.service
systemctl is-active nbot-paper-canary-controller.service
```

Verify the local recommendation API:

```bash
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=5) as r:
    print(json.dumps(json.loads(r.read()), indent=2))
PY
```

Expected order authority is `NONE`.

## 10. Install Execution services

Set machine-specific values on Execution:

```bash
export OBSERVER_HOST=OBSERVER_PUBLIC_OR_PRIVATE_IP
export TUNNEL_KEY="$HOME/.ssh/nbot_observer_tunnel"
export OBSERVER_KNOWN_HOSTS="$HOME/.ssh/nbot_observer_known_hosts"
```

Render/install the two services and umbrella target:

```bash
sudo "$NBOT_VENV/bin/python" deploy/execution/install_services.py \
  --repo "$NBOT_REPO" \
  --python "$NBOT_VENV/bin/python" \
  --user "$(id -un)" \
  --identity-file "$TUNNEL_KEY" \
  --known-hosts-file "$OBSERVER_KNOWN_HOSTS" \
  --observer-host "$OBSERVER_HOST" \
  --observer-ssh-user nbot-tunnel \
  --enable
```

Before starting Execution verify:

1. the repository SHA matches Observation;
2. `.env` exists with mode 600;
3. role-owned state is restored if this is recovery;
4. no manual process owns local port 8765;
5. Observation is healthy or, during recovery, it is understood that Execution
   will fail closed for new entries until Observation returns.

Start the complete Execution role with one command:

```bash
sudo systemctl start nbot-execution.target
```

Check:

```bash
systemctl status nbot-execution.target --no-pager
systemctl is-active nbot-observation-tunnel.service
systemctl is-active nbot-execution.service
```

The Execution service intentionally **Wants**, but does not `Require` or
`BindsTo`, the tunnel. Loss of Observation must never make systemd terminate an
open position manager.

## 11. Normal role operations

Observation:

```bash
sudo systemctl start nbot-observer.target
sudo systemctl status nbot-observer.target
sudo systemctl restart nbot-observer.target
sudo systemctl stop nbot-observer.target
```

Execution:

```bash
sudo systemctl start nbot-execution.target
sudo systemctl status nbot-execution.target
```

**Do not casually stop or restart `nbot-execution.target`.** First verify there
is no open capital-bearing position and, for planned maintenance, disable new
entries through the operator control. An explicit target stop/restart is allowed
to stop both Execution and its tunnel; a tunnel failure by itself is not.

## 12. Final acceptance checks

Both VPSs must report the same Git SHA:

```bash
git rev-parse HEAD
git status --short
```

Observation must have no Execution process:

```bash
pgrep -af 'python.*run_execution\.py' || true
```

Execution must have no Observation/learning worker processes.

While flat, Execution may request a proposal. While a position is open,
position management uses Execution's own Binance stream and does not depend on
Observation. On close, the outcome is persisted locally, delivered to
Observation, ACKed, and removed from the outbox only after a valid ACK.

## 13. What Git does and does not recover

Git recovers:

- source code;
- service templates/installers;
- tests;
- deployment and recovery instructions.

Git does **not** recover:

- `.env`;
- private SSH keys;
- pinned machine host keys;
- current open-position/account state;
- pending outcome outbox;
- Observation learning datasets/models.

Those items require the backup process documented under `deploy/recovery/`.
