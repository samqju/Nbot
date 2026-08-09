# NBOT Fresh Two-VPS Installation

This is the beginner-friendly rebuild guide for the final Phase 6A.0
two-worker architecture.

Use this guide when starting from two fresh Ubuntu VPSs.

## The simple picture

NBOT uses two machines:

- **Observation VPS**: the larger machine. It observes the market, runs virtual
  trades, learning, training, promotion and the recommendation service.
- **Execution VPS**: the smaller machine. It owns the single capital-bearing
  paper/real position, risk, entry, stop, trailing, reconciliation and outcome
  delivery.

Both machines use the **same Git repository and same exact release**.

The final Phase 6A.0 release is:

```text
phase6a0-final
```

Do not expose TCP port `8765` publicly. Execution reaches Observation through
an encrypted SSH tunnel.

For disaster recovery rather than a brand-new bot, also read:

- `deploy/recovery/BACKUP_RESTORE.md`
- `deploy/recovery/DISASTER_RECOVERY.md`

---

## 1. Before you start

Have these ready:

- two Ubuntu 24.04 VPSs;
- admin/SSH access to both;
- the NBOT GitHub repository SSH URL;
- permission to add a GitHub Deploy Key;
- Observation VPS IP address;
- Execution VPS public IP address;
- secure copies of `.env` and role-owned state if this is recovery.

For a brand-new SHADOW installation, there may be no runtime state to restore.

---

## 2. Install basic software

Run on **both VPSs**:

```bash
sudo apt-get update
sudo apt-get install -y git openssh-client python3 python3-venv python3-pip
```

Run additionally on **Observation**:

```bash
sudo apt-get install -y openssh-server
```

Enable normal system clock synchronization on **both**:

```bash
sudo timedatectl set-ntp true
timedatectl status
```

You want:

```text
System clock synchronized: yes
```

Correct clocks matter because proposals have expiry timestamps.

---

## 3. Give each VPS GitHub access

Run separately on each VPS:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh

ssh-keygen -t ed25519 -f ~/.ssh/nbot_github -N ''
chmod 600 ~/.ssh/nbot_github
```

Show the **public** key:

```bash
cat ~/.ssh/nbot_github.pub
```

In GitHub, add that public key as a Deploy Key for the NBOT repository.

Recommended:

- Observation maintenance VPS: write access only if you intentionally use it
  for Git maintenance.
- Execution VPS: read-only.

Never copy the private key into Git.

Tell SSH to use this key for GitHub:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/nbot_github
    IdentitiesOnly yes
EOF

chmod 600 ~/.ssh/config
```

Before accepting GitHub's SSH host key, verify its fingerprint from a trusted
GitHub source.

Test:

```bash
ssh -T git@github.com
```

A GitHub message saying authentication succeeded but shell access is not
provided is normal.

---

## 4. Clone the exact same NBOT release

Replace this placeholder with the real repository SSH URL:

```text
git@github.com:OWNER/Nbot.git
```

On **both VPSs**:

```bash
export NBOT_REPO="$HOME/Nbot"
export NBOT_VERSION="phase6a0-final"
export NBOT_GIT_URL="git@github.com:OWNER/Nbot.git"

git clone "$NBOT_GIT_URL" "$NBOT_REPO"
cd "$NBOT_REPO"

git fetch --tags --prune
git checkout --detach "$NBOT_VERSION"

git rev-parse HEAD
git describe --tags --exact-match
git status --short --branch
```

Record the SHA from both machines.

They must be identical.

Do not deploy an arbitrary `main` revision just because it is newer.

---

## 5. Install Python dependencies

On **both VPSs**:

```bash
export NBOT_REPO="$HOME/Nbot"
export NBOT_VENV="/opt/nbot/.venv"

sudo mkdir -p /opt/nbot
sudo python3 -m venv "$NBOT_VENV"

sudo "$NBOT_VENV/bin/python" -m pip install --upgrade pip

sudo "$NBOT_VENV/bin/python" \
  -m pip install -r "$NBOT_REPO/requirements.lock.txt"

"$NBOT_VENV/bin/python" -m pip check
```

`pip check` must finish without dependency errors.

---

# OBSERVATION VPS

## 6. Create Observation `.env`

On Observation:

```bash
cd "$NBOT_REPO"

cp deploy/examples/observation.env.example .env
chmod 600 .env
nano .env
```

Replace:

```text
OBSERVATION_CONTROL_TOKEN=CHANGE_ME
```

with a strong random secret of at least 32 characters.

Do not post that secret in chat and do not commit `.env`.

The same exact token must later be installed on Execution.

Verify without printing the token:

```bash
"$NBOT_VENV/bin/python" - <<'PY'
import config

print("TRADING_ENV =", config.TRADING_ENV)
print("EXECUTION_MODE =", config.EXECUTION_MODE)
print("CONTROL_TOKEN_SET =", bool(config.OBSERVATION_CONTROL_TOKEN))
print("CONTROL_TOKEN_LENGTH =", len(config.OBSERVATION_CONTROL_TOKEN))
PY
```

For the currently proven deployment you should see:

```text
TRADING_ENV = LIVE
EXECUTION_MODE = SHADOW
```

---

## 7. Create the restricted tunnel account

On Observation:

```bash
sudo useradd --system --create-home --shell /bin/bash nbot-tunnel 2>/dev/null || true

sudo install \
  -d -m 700 \
  -o nbot-tunnel -g nbot-tunnel \
  /home/nbot-tunnel/.ssh

sudo touch /home/nbot-tunnel/.ssh/authorized_keys
sudo chown nbot-tunnel:nbot-tunnel /home/nbot-tunnel/.ssh/authorized_keys
sudo chmod 600 /home/nbot-tunnel/.ssh/authorized_keys
```

---

# EXECUTION VPS

## 8. Create Execution's tunnel key

On Execution:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh

ssh-keygen -t ed25519 -f ~/.ssh/nbot_observer_tunnel -N ''
chmod 600 ~/.ssh/nbot_observer_tunnel
```

Show only the public key:

```bash
cat ~/.ssh/nbot_observer_tunnel.pub
```

Copy that public key.

---

# OBSERVATION VPS

## 9. Authorize the Execution tunnel key

On Observation, replace the two placeholders:

```bash
EXECUTION_PUBLIC_IP="PUT_EXECUTION_PUBLIC_IP_HERE"
TUNNEL_PUBLIC_KEY='ssh-ed25519 PUT_EXECUTION_PUBLIC_KEY_HERE'
```

Install it:

```bash
printf '%s\n' \
"from=\"$EXECUTION_PUBLIC_IP\",no-agent-forwarding,no-X11-forwarding,no-pty,no-user-rc,permitopen=\"127.0.0.1:8765\" $TUNNEL_PUBLIC_KEY" \
| sudo tee /home/nbot-tunnel/.ssh/authorized_keys >/dev/null

sudo chown nbot-tunnel:nbot-tunnel /home/nbot-tunnel/.ssh/authorized_keys
sudo chmod 600 /home/nbot-tunnel/.ssh/authorized_keys
```

Install the restricted SSH rule:

```bash
sudo tee /etc/ssh/sshd_config.d/90-nbot-tunnel.conf >/dev/null <<'EOF'
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
EOF
```

Validate SSH configuration:

```bash
sudo sshd -t
```

Only if that command reports no error:

```bash
sudo systemctl reload ssh
```

---

## 10. Get Observation's SSH host key

On Observation:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub

sudo awk \
  '{print $1" "$2}' \
  /etc/ssh/ssh_host_ed25519_key.pub
```

Record:

- the fingerprint;
- the `ssh-ed25519 AAAA...` public host key.

Verify the fingerprint through a trusted source/provider console.

---

# EXECUTION VPS

## 11. Pin Observation's verified SSH host key

On Execution:

```bash
OBSERVER_HOST="PUT_OBSERVER_IP_HERE"
OBSERVER_HOST_KEY='ssh-ed25519 PUT_VERIFIED_OBSERVER_HOST_KEY_HERE'

printf '%s %s\n' \
  "$OBSERVER_HOST" \
  "$OBSERVER_HOST_KEY" \
  > ~/.ssh/nbot_observer_known_hosts

chmod 600 ~/.ssh/nbot_observer_known_hosts
```

Do not use `StrictHostKeyChecking=no`.

---

# OBSERVATION VPS

## 12. Install and start the Observation role

On Observation:

```bash
cd "$NBOT_REPO"
export NBOT_VENV="/opt/nbot/.venv"

sudo "$NBOT_VENV/bin/python" \
  deploy/observation/install_services.py \
  --repo "$NBOT_REPO" \
  --python "$NBOT_VENV/bin/python" \
  --user "$(id -un)" \
  --enable
```

Start the complete Observation role:

```bash
sudo systemctl start nbot-observer.target
```

Check:

```bash
systemctl is-active nbot-observer.target
systemctl is-active nbot-observation.service
systemctl is-active nbot-auto-training.service
systemctl is-active nbot-promotion-controller.service
systemctl is-active nbot-paper-canary-controller.service
```

All should report:

```text
active
```

Check Observation's local health API:

```bash
python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:8765/health",
    timeout=5,
) as r:
    print(json.dumps(json.loads(r.read()), indent=2, sort_keys=True))
PY
```

During warmup `NOT_READY` is allowed.

When ready, status should be `READY`.

`order_authority` must always be:

```text
NONE
```

Do not expose port `8765` publicly.

---

# EXECUTION VPS

## 13. Create Execution `.env`

On Execution:

```bash
cd "$NBOT_REPO"

cp deploy/examples/execution.env.example .env
chmod 600 .env
nano .env
```

Replace `CHANGE_ME` with the exact same `OBSERVATION_CONTROL_TOKEN` used on
Observation.

Verify without printing the token:

```bash
"$NBOT_VENV/bin/python" - <<'PY'
import config

print("TRADING_ENV =", config.TRADING_ENV)
print("EXECUTION_MODE =", config.EXECUTION_MODE)
print("CONTROL_TOKEN_SET =", bool(config.OBSERVATION_CONTROL_TOKEN))
print("CONTROL_TOKEN_LENGTH =", len(config.OBSERVATION_CONTROL_TOKEN))
PY
```

Current proven mode:

```text
TRADING_ENV = LIVE
EXECUTION_MODE = SHADOW
```

LIVE + SHADOW uses real public Binance market data and local paper execution.
Private/order-writing Binance credentials are not required for this mode.

---

## 14. Install the Execution role

On Execution:

```bash
cd "$NBOT_REPO"

export NBOT_VENV="/opt/nbot/.venv"
export OBSERVER_HOST="PUT_OBSERVER_IP_HERE"
export TUNNEL_KEY="$HOME/.ssh/nbot_observer_tunnel"
export OBSERVER_KNOWN_HOSTS="$HOME/.ssh/nbot_observer_known_hosts"

sudo "$NBOT_VENV/bin/python" \
  deploy/execution/install_services.py \
  --repo "$NBOT_REPO" \
  --python "$NBOT_VENV/bin/python" \
  --user "$(id -un)" \
  --identity-file "$TUNNEL_KEY" \
  --known-hosts-file "$OBSERVER_KNOWN_HOSTS" \
  --observer-host "$OBSERVER_HOST" \
  --observer-ssh-user nbot-tunnel \
  --enable
```

Before starting Execution confirm:

- Observation is running;
- both VPSs have the same Git SHA;
- Execution `.env` exists with mode `600`;
- the tunnel private key exists;
- the pinned Observer host-key file exists;
- role-owned state has been restored first if this is disaster recovery.

Start:

```bash
sudo systemctl start nbot-execution.target
```

Check:

```bash
systemctl is-active nbot-execution.target
systemctl is-active nbot-observation-tunnel.service
systemctl is-active nbot-execution.service
```

All should report:

```text
active
```

---

## 15. Verify the encrypted Observer connection

On Execution:

```bash
python3 - <<'PY'
import json
import urllib.request

with urllib.request.urlopen(
    "http://127.0.0.1:8765/health",
    timeout=5,
) as r:
    print(json.dumps(json.loads(r.read()), indent=2, sort_keys=True))
PY
```

This reaches Observation through the SSH tunnel.

---

## 16. Final role separation checks

On both VPSs:

```bash
cd "$NBOT_REPO"

git rev-parse HEAD
git describe --tags --exact-match
git status --short
```

Both SHAs must be identical.

On Observation:

```bash
pgrep -af 'python.*run_execution\.py' || true
```

There should be no Execution Worker.

On Execution:

```bash
pgrep -af 'run_observation\.py|scripts\.learning' || true
```

There should be no Observation/learning worker.

The two-worker deployment is now installed.

For everyday start, stop, restart, status and safe maintenance commands read:

```text
deploy/OPERATIONS.md
```

---

## Safety rules

Never:

- run legacy `run.py` beside the split workers;
- run two Execution Workers;
- expose TCP `8765` publicly;
- disable SSH host-key checking;
- copy one mutable `data/` directory onto both VPSs;
- put future order-writing credentials on Observation;
- delete pending outcomes just to clear an error;
- stop Execution casually while a position is open;
- deploy different Git revisions to the two roles.
