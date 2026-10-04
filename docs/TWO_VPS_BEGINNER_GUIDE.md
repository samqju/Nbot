# Two VPSs, one learning bot: beginner setup guide

**2026-10-02 mode update:** [The three-mode guide](TRADING_MODES.md) describes Testnet trading, learned mainnet paper, and the separately authorized small mainnet trial. Earlier V3.10-only restrictions below describe the original automatic Champion roadmap. This manual trial does not declare those economic gates passed. No Testnet-paper mode is supported.


This guide takes you from **two empty servers** to a connected bot running
**Binance USD-M Futures Testnet trades with pretend money**.

You do not need to write software. Follow the steps in order. Every command says
which computer to use. Read the explanation before pasting a command.

This is the **learned Testnet setup**, not a real-money launch. The bot can collect
data, train its existing model, recommend trades, and manage one Testnet position
at a time. This does not mean the strategy is profitable or every roadmap phase
has passed. A new installation needs time to learn.

Checked against the code at commit
[9fff54c](https://github.com/samqju/Nbot/commit/9fff54c3889e26c21dd217d439783af4803993d6).
Documentation consistency review: 2026-10-01. This identifies the reviewed code,
not the code automatically installed on your servers.
Updated October 1, 2026. Commands assume **Ubuntu Server 24.04 LTS**, a normal
login named **ubuntu**, SSH on port **22**, and the bot at **/home/ubuntu/Nbot**.

> Already have a running bot? Do not overwrite its folder, keys, or databases
> using the fresh-install steps. Start at [Existing installations and updates](#17-existing-installations-and-updates).
> Replacing only the learning VPS is covered there too.

## Contents

1. [Understand the two servers](#1-understand-the-two-servers)
2. [Create the VPSs](#2-create-the-vpss)
3. [Open two terminal windows](#3-open-two-terminal-windows)
4. [Prepare Ubuntu on both servers](#4-prepare-ubuntu-on-both-servers)
5. [Download the same code on both servers](#5-download-the-same-code-on-both-servers)
6. [Give each server its job](#6-give-each-server-its-job)
7. [Allow the trading server to contact the learning server](#7-allow-the-trading-server-to-contact-the-learning-server)
8. [Create their shared connection password](#8-create-their-shared-connection-password)
9. [Start the learning services](#9-start-the-learning-services)
10. [Install the encrypted connection](#10-install-the-encrypted-connection)
11. [Add Binance Testnet credentials](#11-add-binance-testnet-credentials)
12. [Start the trader, then allow new entries](#12-start-the-trader-then-allow-new-entries)
13. [Understand the first day](#13-understand-the-first-day)
14. [Daily commands](#14-daily-commands)
15. [Pause, stop, and restart](#15-pause-stop-and-restart)
16. [Fix common problems](#16-fix-common-problems)
17. [Existing installations and updates](#17-existing-installations-and-updates)
18. [What to back up](#18-what-to-back-up)
19. [Final checklist and reference links](#19-final-checklist-and-reference-links)

## 1. Understand the two servers

A **VPS** is a rented computer that stays on when your laptop is off.

| Friendly name | Name used by the bot | What it does | Binance private key? |
|---|---|---|---|
| Learning VPS | OBSERVATION | Watches public markets, saves examples, trains models, sends suggestions | No |
| Trading VPS | EXECUTION | Checks suggestions, decides whether an order is allowed, opens and protects Testnet positions | Testnet key only |

The connection works like this:

~~~mermaid
flowchart LR
    M["Binance public LIVE data"] --> L["Learning VPS: collect, learn, score"]
    Q["Binance public Testnet data"] --> L
    L -->|"Trade suggestion through SSH tunnel"| T["Trading VPS: risk checks and one-position control"]
    T -->|"Request a suggestion; report completed trade"| L
    T -->|"Orders and protective stops"| B["Binance Futures Testnet"]
    B -->|"Order, position and balance information"| T
~~~

The **trading server opens the connection** to the learning server. You do not
need a second reverse tunnel. Requests, replies, and completed-trade reports all
use the same connection.

The learning server fetches public market data itself. You do not copy price
files or trained models to the trading server. A failed connection blocks new
suggestions; the trader handles an existing position independently, provided
the trader itself is running and can reach Binance.

## 2. Create the VPSs

In your chosen VPS provider's website:

1. Choose **Create server**, **Create instance**, or the equivalent.
2. Choose **Ubuntu Server 24.04 LTS**. Do not choose Windows.
3. Use a region where your provider and Binance allow the required access.
4. Give the first server a recognizable name, such as **nbot-learning**.
5. Enable an SSH login key. Save its private key somewhere safe on your computer.
6. Repeat for **nbot-trading**.
7. Give both servers stable public IPv4 addresses. Write them down.
8. Enable the provider's backup option if available.

Practical starting allocations, **not measured minimums or performance promises**:

| Server | CPU | RAM | SSD space |
|---|---:|---:|---:|
| Learning | 2 virtual CPUs | 4 GB | 60 GB |
| Trading | 1 virtual CPU | 2 GB | 25 GB |

Learning watches many symbols, even though trading allows only one position.
Watch disk space and research processing time; increase capacity if needed.
No GPU is required by this version.

Write down this small worksheet:

| Item | Your value |
|---|---|
| Learning VPS public IP | |
| Trading VPS public IP | |
| Your computer's public IP | |
| Your SSH private-key location | |
| GitHub username with repository access | |

For the provider's **firewall/security-group** settings:

- Learning VPS: allow incoming TCP **22** from your computer and from the trading VPS.
- Trading VPS: allow incoming TCP **22** from your computer.
- Allow outgoing internet connections. The bot needs HTTPS, DNS, time synchronization,
  and trading-to-learning SSH.
- Do not open **8766** or **18766** publicly. The encrypted tunnel carries that traffic.
- Keep access to the provider's browser/serial console in case SSH fails.

Provider screens differ. These rules apply to their firewall; Ubuntu's firewall
will be configured separately below.

## 3. Open two terminal windows

Use two separate windows and label them **LEARNING** and **TRADING**.

### If you use PuTTY on Windows

For each window:

1. Enter that VPS's IP as **Host Name** and use port **22**, connection **SSH**.
2. Select your private **.ppk** key under the SSH authentication settings.
3. Save a session with the server's friendly name.
4. Open it and log in as **ubuntu**.
5. On the first connection, compare the server fingerprint with the one shown
   by your provider's trusted console. Accept it only if it matches.

If your provider gave you an OpenSSH **.key** or **.pem** file, you can instead
use Windows PowerShell's built-in SSH:

~~~powershell
ssh -i "C:\YOUR-KEY-FOLDER\your-server.key" ubuntu@YOUR_VPS_IP
~~~

Replace the key path and IP before running it. A .ppk file is for PuTTY, not
normally for this OpenSSH command.

On macOS/Linux, use Terminal and an OpenSSH key:

~~~bash
chmod 600 /path/to/your-server.key
ssh -i /path/to/your-server.key ubuntu@YOUR_VPS_IP
~~~

These login commands run on **your computer**. Almost everything below runs
**inside the logged-in VPS terminal**, not in Windows PowerShell.

On **each VPS**, check:

~~~bash
whoami
pwd
~~~

Expected: user **ubuntu**, home folder **/home/ubuntu**.

If your provider only gives you **root**, use its Ubuntu-user setup instructions.
For a fresh root-only Ubuntu image, this is an alternative; run it as root once,
then log in again as ubuntu using the same key:

~~~bash
adduser ubuntu
usermod -aG sudo ubuntu
install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh
install -m 600 -o ubuntu -g ubuntu /root/.ssh/authorized_keys /home/ubuntu/.ssh/authorized_keys
~~~

This alternative assumes your working root login key is in
/root/.ssh/authorized_keys. If that file is absent, stop and use the provider's
instructions. Keep the original working session open until ubuntu login works.

**How to paste commands:** paste one whole code block at a time, including its
last line. A block ending with PY or EOF must include that closing line.
If a command reports an error, stop at that step; do not paste all later steps.

Whenever you see a password prompt, typing may show nothing on screen. That is
normal. **Ctrl+C** stops a following-log display or cancels the current command.

## 4. Prepare Ubuntu on both servers

**Run on BOTH VPSs as ubuntu:**

~~~bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip openssh-client openssh-server curl ca-certificates nano ufw
python3 --version
sudo timedatectl set-ntp true
timedatectl status
~~~

Expected: Python **3.12.x**, and eventually **System clock synchronized: yes**.
If Ubuntu requests a restart, restart now, before installing the bot:

~~~bash
sudo reboot
~~~

Reconnect afterward. If time synchronization still says no, fix the VPS time
service before proceeding. Do not increase the bot's clock tolerance to hide it.

### Ubuntu firewall — trading VPS

Run this only on a **fresh server**, keeping your current SSH window open.
At the prompt, enter the public IPv4 address of your own computer:

~~~bash
read -rp "Your computer's public IPv4 address: " ADMIN_IP
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from "$ADMIN_IP" to any port 22 proto tcp
sudo ufw enable
sudo ufw status
~~~

Open a **second** SSH login to confirm you can still connect before closing
the first. If your home IP changes later, update the cloud and Ubuntu firewall
rules through a working session or the provider console.

### Ubuntu firewall — learning VPS

Enter your computer IP and the trading VPS IP when asked:

~~~bash
read -rp "Your computer's public IPv4 address: " ADMIN_IP
read -rp "Trading VPS public IPv4 address: " TRADE_IP
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from "$ADMIN_IP" to any port 22 proto tcp
sudo ufw allow from "$TRADE_IP" to any port 22 proto tcp
sudo ufw enable
sudo ufw status
~~~

Again, test a second login. If your provider already manages special firewall
rules, retain those rules and apply the equivalent restrictions rather than
resetting its networking.

### Check public Binance access — both VPSs

~~~bash
curl --fail --show-error --max-time 15 https://fapi.binance.com/fapi/v1/time
curl --fail --show-error --max-time 15 https://demo-fapi.binance.com/fapi/v1/time
~~~

Each should return a small reply containing **serverTime**. This checks public
access only; it does not prove your private API key works. If you get a geographic
restriction or access denial, resolve it through the services' supported access
options. Do not try to bypass their restrictions.

## 5. Download the same code on both servers

A **repository** is the bot's project folder on GitHub. A **commit** is one exact
saved version of that project. Both VPSs must use the same commit.

If the repository is private, its owner must grant your GitHub account access.
A guide link does not grant access. For HTTPS cloning, GitHub may ask for:

- **Username:** your GitHub username.
- **Password:** a GitHub personal access token, not your normal GitHub password.

Create a suitably scoped, preferably read-only token for this repository using
[GitHub's token instructions](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
For a supported fine-grained token, select the repository and **Contents: Read-only**;
organization approval may also be required. Keep it in a password manager.
Paste it only at Git's password prompt, never into the clone URL or this guide.
GitHub explains HTTPS authentication in its
[remote repository guide](https://docs.github.com/en/get-started/git-basics/about-remote-repositories).

### First, on TRADING

~~~bash
cd "$HOME"
git -c credential.helper= clone https://github.com/samqju/Nbot.git Nbot
cd "$HOME/Nbot"
git rev-parse HEAD
~~~

Copy the full 40-character version printed by the last command into your notes.
If using your own fork, use its clone URL on **both** VPSs.

### Then, on LEARNING

~~~bash
cd "$HOME"
git -c credential.helper= clone https://github.com/samqju/Nbot.git Nbot
cd "$HOME/Nbot"
read -rp "Paste the full version from the trading VPS: " NBOT_RELEASE
git checkout --detach "$NBOT_RELEASE"
git rev-parse HEAD
~~~

The two printed versions must match exactly. **Detached HEAD** is normal here:
it means the learning VPS is pinned to that exact version.

If Nbot already exists, stop and use the update section. Do not delete a folder
to make cloning work.

### Install Python's private workspace — BOTH

~~~bash
cd "$HOME/Nbot"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
git status --short
~~~

The last command should print nothing. That means the tracked code is unchanged.
An empty requirements file is normal in this version; its runtime currently uses
Python's standard library. Do not add unrelated ML/Binance packages.

## 6. Give each server its job

### LEARNING only

~~~bash
cd "$HOME/Nbot"
printf 'OBSERVATION\n' > .nbot-role
./nbotctl bootstrap
./nbotctl status
~~~

Expected: **role: OBSERVATION** and **layout: READY**.

### TRADING only

~~~bash
cd "$HOME/Nbot"
printf 'EXECUTION\n' > .nbot-role
./nbotctl bootstrap
./nbotctl status
~~~

Expected: **role: EXECUTION** and **layout: READY**.

These commands make the required folders. They do not arm trading or place an
order. Do not copy the other server's data folders across or change roles later.

## 7. Allow the trading server to contact the learning server

This creates a **separate server-to-server SSH key**. It is different from your
computer's login key, your GitHub token, and your Binance API key.

### TRADING: create the connection key

~~~bash
install -d -m 700 "$HOME/.ssh"
ssh-keygen -t ed25519 -f "$HOME/.ssh/nbot_observation" -N "" -C "nbot-trading-to-learning"
chmod 600 "$HOME/.ssh/nbot_observation"
cat "$HOME/.ssh/nbot_observation.pub"
~~~

If told the file already exists, **do not overwrite it**. Reuse the installed
connection after checking it, or ask for help.

Copy the entire printed line beginning **ssh-ed25519**. This is the **public**
key and is safe to copy to the other VPS. Never copy the file without **.pub**
off the trading VPS. This particular key has no passphrase because the tunnel
starts without a person typing one.

### LEARNING: authorize that public key

~~~bash
install -d -m 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
nano "$HOME/.ssh/authorized_keys"
~~~

In nano, go to the end and add the copied public key as **one new line**.
Keep all existing lines, including your own login key.

For this new line, put these options before ssh-ed25519, replacing
TRADING_VPS_IP with your trading server's actual public IPv4 address:

~~~text
from="TRADING_VPS_IP",no-agent-forwarding,no-X11-forwarding,no-pty,permitopen="127.0.0.1:8766" ssh-ed25519 PASTE_THE_REST_OF_THE_PUBLIC_KEY_HERE
~~~

Do not paste the placeholder literally. Save with **Ctrl+O**, **Enter**, then
exit with **Ctrl+X**.

This key permits the tunnel and the remote commands that nbotctl needs. It is
not a tunnel-only key; protect the trading server accordingly. The source-IP
restriction assumes that the trading server connects from its recorded public IP.

### LEARNING: display its real SSH fingerprint

~~~bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
~~~

Keep the displayed **SHA256:...** fingerprint available for the next step.

### TRADING: verify the destination, then connect

~~~bash
read -rp "Learning VPS public IPv4 address: " OBS_IP
ssh-keyscan -T 10 -t ed25519 "$OBS_IP" > "$HOME/.ssh/nbot_observation.hostkey"
ssh-keygen -lf "$HOME/.ssh/nbot_observation.hostkey"
~~~

The fingerprint must match the one you just displayed in your trusted learning
VPS session. **ssh-keyscan alone does not verify identity.** If it differs, stop.

Only after comparing and confirming the fingerprint:

~~~bash
cat "$HOME/.ssh/nbot_observation.hostkey" >> "$HOME/.ssh/known_hosts"
chmod 600 "$HOME/.ssh/known_hosts"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -i "$HOME/.ssh/nbot_observation" "ubuntu@$OBS_IP" 'whoami'
~~~

Expected: **ubuntu**, with no password prompt.

If you reopen this terminal, OBS_IP is forgotten. Run the read prompt again
before any later command that uses "$OBS_IP".

### Allow only the service-control commands the bot needs

The cluster command runs sudo without an interactive password. Some Ubuntu cloud
images already allow this. These specific rules also work when they do not.

**LEARNING:**

~~~bash
NBOT_SUDO_FILE=$(mktemp)
cat > "$NBOT_SUDO_FILE" <<'EOF'
ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl start nbot-observation-testnet-control.service, /usr/bin/systemctl stop nbot-observation-testnet-control.service, /usr/bin/systemctl restart nbot-observation-testnet-control.service
EOF
sudo visudo -cf "$NBOT_SUDO_FILE" &&
sudo install -o root -g root -m 440 "$NBOT_SUDO_FILE" /etc/sudoers.d/nbot-testnet-control
rm -f "$NBOT_SUDO_FILE"
~~~

**TRADING:**

~~~bash
NBOT_SUDO_FILE=$(mktemp)
cat > "$NBOT_SUDO_FILE" <<'EOF'
ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl start nbot-control-tunnel-testnet.service, /usr/bin/systemctl stop nbot-control-tunnel-testnet.service, /usr/bin/systemctl restart nbot-control-tunnel-testnet.service
EOF
sudo visudo -cf "$NBOT_SUDO_FILE" &&
sudo install -o root -g root -m 440 "$NBOT_SUDO_FILE" /etc/sudoers.d/nbot-testnet-control
rm -f "$NBOT_SUDO_FILE"
~~~

Expected: **parsed OK**. These additions do not remove any broader sudo rights
your provider already gave ubuntu.

For a table of every private file, template and field, see
[environment-file setup](ENVIRONMENT_SETUP.md). V3 uses files under
`config/secrets/`, not a root `.env`.

## 8. Create their shared connection password

This long random token lets the bot recognize messages from its other half.
The following command generates it without printing it.

**TRADING:**

~~~bash
cd "$HOME/Nbot"
.venv/bin/python - <<'PY'
from pathlib import Path
import secrets
path = Path("config/secrets/control-link.env")
with path.open("x", encoding="utf-8") as handle:
    path.chmod(0o600)
    handle.write(
        "NBOT_CONTROL_AUTH_TOKEN=" + secrets.token_hex(32) + "\n"
        "NBOT_OBSERVATION_TESTNET_URL=http://127.0.0.1:18766\n"
        "NBOT_OBSERVATION_TIMEOUT_SECONDS=2.0\n"
    )
print("Created the private connection file; token was not displayed.")
PY
~~~

FileExistsError means a file already exists. Stop and preserve it; do not
generate a different token over a working installation.

Copy it through the verified SSH connection to the **fresh** learning VPS:

~~~bash
read -rp "Learning VPS public IPv4 address: " OBS_IP
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -i "$HOME/.ssh/nbot_observation" "ubuntu@$OBS_IP" 'test ! -e /home/ubuntu/Nbot/config/secrets/control-link.env' &&
scp -o BatchMode=yes -o StrictHostKeyChecking=yes -i "$HOME/.ssh/nbot_observation" \
  config/secrets/control-link.env \
  "ubuntu@$OBS_IP:/home/ubuntu/Nbot/config/secrets/control-link.env"
~~~

If the remote file already exists, the copy is deliberately not performed.
For a new deployment, both files must contain the same token.

**LEARNING:**

~~~bash
cd "$HOME/Nbot"
chmod 700 config/secrets
chmod 600 config/secrets/control-link.env
stat -c '%a %n' config/secrets config/secrets/control-link.env
~~~

Expected: **700** for the folder and **600** for the file.

Never post either secret file on GitHub or paste it into a support message.

## 9. Start the learning services

**Using 1 CPU and 1 GB RAM?** Use the installer command with **--resource-profile tiny**
in the [small-VPS learner guide](SMALL_VPS_LEARNER.md). It watches up to 20 coins
and installs resource limits. The plain command below retains standard settings.

**LEARNING:**

~~~bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py research-memory-init
sudo .venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" \
  --python "$PWD/.venv/bin/python" \
  --user "$(id -un)" \
  --enable --start \
  --enable-testnet-control --start-testnet-control
~~~

This installs and starts:

| Service | Plain-English job |
|---|---|
| nbot-observation-live.service | Collect public real-market evidence |
| nbot-research-epoch.timer | Periodically check whether enough evidence is ready |
| nbot-research-epoch.service | Process an eligible batch and advance learning |
| nbot-observation-testnet-control.service | Collect matching Testnet data and answer the trader |

The memory initialization command does not reset an already initialized memory
store. Do not start additional research loops, a second collector, or the
optional challenger service alongside this setup.

Check the services:

~~~bash
systemctl is-active nbot-observation-live.service
systemctl is-active nbot-observation-testnet-control.service
systemctl is-active nbot-research-epoch.timer
systemctl list-timers --all --no-pager nbot-research-epoch.timer
sudo journalctl -u nbot-observation-live.service -n 30 --no-pager
sudo journalctl -u nbot-observation-testnet-control.service -n 30 --no-pager
~~~

The first three should say **active**. The research service itself is a scheduled
job, so **inactive between jobs is normal**. The timer checks about every
15 minutes after a job finishes; it does not retrain every 15 minutes.

Allow at least a few five-minute market cycles for initial data. Then:

~~~bash
./nbotctl doctor live-paper
./nbotctl doctor testnet-trade
~~~

On this server, **live-paper** names the LIVE data profile. It does not make
Observation place orders. Resolve errors about database initialization, time,
permissions, or incomplete startup before continuing. Waiting for training is
different from a broken installation.

## 10. Install the encrypted connection

**TRADING:** render the repository's supplied tunnel template for your own server:

~~~bash
cd "$HOME/Nbot"
read -rp "Learning VPS public IPv4 address: " OBS_IP
export OBS_IP
.venv/bin/python - <<'PY'
from pathlib import Path
import ipaddress
import os
ip = str(ipaddress.IPv4Address(os.environ["OBS_IP"]))
text = Path("deploy/systemd/nbot-control-tunnel-testnet.service.in").read_text()
text = text.replace("@NBOT_USER@", "ubuntu")
text = text.replace("@NBOT_SSH_KEY@", str(Path.home() / ".ssh/nbot_observation"))
text = text.replace("@OBSERVATION_SSH_TARGET@", "ubuntu@" + ip)
assert "@NBOT_" not in text and "@OBSERVATION_" not in text
path = Path("runtime/nbot-control-tunnel-testnet.service")
path.write_text(text)
print("Prepared:", path)
PY
sudo install -o root -g root -m 644 \
  runtime/nbot-control-tunnel-testnet.service \
  /etc/systemd/system/nbot-control-tunnel-testnet.service
sudo systemctl daemon-reload
sudo systemctl enable --now nbot-control-tunnel-testnet.service
systemctl is-active nbot-control-tunnel-testnet.service
sudo journalctl -u nbot-control-tunnel-testnet.service -n 30 --no-pager
~~~

Expected: **active**, with no repeating SSH/authentication/forwarding errors.

The route is:

~~~text
Trading VPS 127.0.0.1:18766
        -> encrypted SSH to learning VPS port 22
        -> Learning VPS 127.0.0.1:8766
~~~

**127.0.0.1 means "this computer only."** Keep those addresses unchanged. This is
why no public HTTP port, domain name, or TLS certificate is needed here.

Check the authenticated link without showing its token:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from nbot.communication.config import control_link_config_for_profile
from nbot.communication.client import probe_observation_health
from nbot.config.profiles import get_profile
link = control_link_config_for_profile(Path.cwd(), get_profile("testnet-trade"))
health = probe_observation_health(
    base_url=link.base_url, auth_token=link.auth_token,
    timeout_seconds=link.timeout_seconds,
)
print(json.dumps(health, indent=2, sort_keys=True))
PY
~~~

A reply means the authenticated connection works. **NOT_READY** with a learning
wait reason can be normal. Check that the reply identifies **testnet-trade**,
**TESTNET**, and **LEARNED_TESTNET** selection. A healthy connection does not mean
a model or a trade is ready.

## 11. Add Binance Testnet credentials

Do this in your browser first:

1. Open Binance's official [Futures Demo/Testnet instructions](https://www.binance.com/en-IA/support/faq/detail/ab78f9a1b8824cf0a106b4229c76496d).
2. Open the Futures Demo Trading environment linked there. Use **USD-M Futures**,
   not Spot Testnet or COIN-M Futures.
3. Create a **Testnet/demo API key and secret** suitable for HMAC authentication.
   This version uses the key-and-secret method, not an RSA/Ed25519 private API key.
4. If permission/IP controls are offered, allow the required Futures trading
   access and the **trading VPS's** public IP.
5. Make sure the demo account has pretend USDT available.
6. Use **One-way position mode**, not Hedge Mode. Begin with no positions or
   pending orders. Keep this demo account for this bot during the trial.

Menu labels can change. Follow the official page if the screen looks different.
The bot's Testnet endpoints are pinned to **demo-fapi.binance.com** and
**demo-fstream.binance.com**, consistent with
[Binance's Futures API documentation](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info).
Do not edit those endpoints to make a real-account key work.

**TRADING only:** this asks for the two secrets without displaying them or putting
them in your shell's command history:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python - <<'PY'
from getpass import getpass
from pathlib import Path
path = Path("config/secrets/execution-testnet.env")
if path.exists():
    raise SystemExit("File already exists. Preserve it; do not overwrite blindly.")
key = getpass("Paste your Futures TESTNET API key: ").strip()
secret = getpass("Paste your Futures TESTNET API secret: ").strip()
if not key or not secret or any(c.isspace() for c in key + secret):
    raise SystemExit("Empty value or whitespace found. Nothing was saved.")
with path.open("x", encoding="utf-8") as handle:
    path.chmod(0o600)
    template = Path("config/examples/execution-testnet.env.example").read_text(encoding="utf-8")
    template = template.replace("TESTNET_API_KEY=\n", "TESTNET_API_KEY=" + key + "\n", 1)
    template = template.replace("TESTNET_API_SECRET=\n", "TESTNET_API_SECRET=" + secret + "\n", 1)
    handle.write(template)
print("Saved Testnet credentials without displaying them.")
PY
stat -c '%a %n' config/secrets/execution-testnet.env
~~~

Expected file permission: **600**. Nothing from this step belongs on the learning
VPS. Do not export API keys globally or put them in the tracked profile files.

The [Testnet template](../config/examples/execution-testnet.env.example) lists
optional settings; [the field guide](ENVIRONMENT_SETUP.md) explains what each
value means. Leave default limits unchanged for the first trial.

## 12. Start the trader, then allow new entries

**TRADING:** first check the installed versions and state:

~~~bash
cd "$HOME/Nbot"
git status --short
./nbotctl status
~~~

Git should print nothing. On a fresh installation, no trading runtime should be
active. State may say **ABSENT_CLEAN_START**; that is normal before first startup.

Now deliberately authorize this Testnet trial:

~~~bash
./nbotctl arm testnet-trade
./nbotctl cluster doctor testnet-trade
~~~

Expected: the doctor reports **PASS**. If it fails, read the warnings and use
the troubleshooting section. Do not keep rearming to clear an unrelated error.

**arm** means "allow this Testnet session." It does not place an order. Arming
starts a new persistent session budget, so it is not a routine daily health check.

Start the connected trader:

~~~bash
./nbotctl cluster start testnet-trade
./nbotctl cluster status testnet-trade
~~~

This command checks both servers, restarts the Testnet control service and tunnel,
and starts one trading worker. New entries remain **blocked** at this stage.

Look for:

- Matching release/commit on both VPSs.
- A running worker: **alive: true** and **ready: true**.
- An active tunnel and reachable Observation service.
- No recovery-critical error or unresolved order.
- On a fresh account, **open_position: null** and **pending_outcomes: 0**.

Only after those checks pass, allow new Testnet entries:

~~~bash
./nbotctl entries enable testnet-trade
./nbotctl cluster status testnet-trade
./nbotctl logs testnet-trade --lines 50
~~~

The request may take a worker cycle to appear in status. A trade happens only if
the model is ready, it finds a suitable opportunity, and all trading checks pass.
Do not change to the mechanical selection mode merely to make trades appear.

The trader continues after you close your terminal. **In this version its Testnet
launcher is a managed background process, not a boot-enabled trading systemd
service.** Observation and the tunnel restart after a VPS reboot; Testnet
Execution needs the checked recovery/start procedure in section 15.
Do not install the LIVE_PAPER service as a substitute for Testnet.

## 13. Understand the first day

An empty learning server normally needs approximately **16 hours of continuous
usable data, plus processing time**, before its first model can be available.
This is an estimate, not a deadline:

- About four hours of earlier market context.
- A batch of 96 five-minute target events: about eight hours.
- About four more hours to observe the future outcomes of the latest examples.
- Time for scheduled research to finish.

Missing/incomplete data, slow hardware, or collection failures can extend this.
A trained model can still choose no trade.

Learning continues in batches. Existing frozen models are assessed on later
events that were not part of their training. Testnet suggestions can use an
experimental model before its full research evaluation is finished; this does
not make it a proven Research Champion.

A full evaluation uses 20 validation and 20 final-test events spaced four hours
five minutes apart. Expect roughly seven days of new data plus the last outcome
maturity; gaps can make it longer. `EVALUATE_WAIT` during this period is normal.

The learner combines a numerical price model with a recent filter for five fixed
setup types: trend continuation, trend pullback, stretched reversal, volatility
expansion and relative strength. It checks these against market direction and
volatility. This is not recognition of every chart pattern. The filter can lower
scores or reject a suggestion, but cannot raise the original prediction.

Its targets are simulated four-hour outcomes using ATR risk units. The trader
uses its own fixed-dollar risk and exit rules, so a predicted research score is
not a prediction of money earned. Read the [small-VPS guide](SMALL_VPS_LEARNER.md)
for details and use `learning-report` to understand rejected models.

Testnet trade results are stored and acknowledged, but **they do not become
LIVE-market training labels**. The training examples come from collected market
evidence. The model ranks the existing features; it does not invent unrestricted
new strategy programs.

**LEARNING:**

~~~bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py research-memory-status
.venv/bin/python nbot_admin.py research-epoch-status
.venv/bin/python nbot_admin.py challenger-status
sudo journalctl -u nbot-research-epoch.service -n 60 --no-pager
~~~

Useful messages:

| Message | Meaning | What to do |
|---|---|---|
| WAIT_FOR_MATURE_EPOCH | Not enough completed examples yet | Keep collection running; check progress later |
| LEARNING_WAIT_FOR_COMPATIBLE_MODEL | No suitable saved model for this release yet | Check learning jobs; allow training time |
| LEARNING_WAIT_FOR_FULL_FEATURE_HISTORY | Not enough recent market context | Keep collection running |
| LEARNING_WAIT_FOR_LIVE_EVENT | No usable LIVE event yet | Check the LIVE collector |
| LEARNED_NO_POSITIVE_OPPORTUNITY | The current model did not select a positive opportunity | Normal abstention; do not force an order |
| EVALUATE_WAIT | A frozen model is waiting for its future evaluation window | New data collection and epochs should continue |
| UNAVAILABLE_HISTORICAL_CALIBRATION | A fresh server cannot reproduce one old date-specific research report | Expected for this setup; it is not a passed historical audit |

The bot has risk and session limits. The default Testnet session permits up to
100 entries and caps entry notional at 1,000 pretend USD; further risk checks also
apply. A blocked entry can be correct behavior. A new trade every five minutes
is not promised.

## 14. Daily commands

Commands assume you have logged in as ubuntu and entered the bot folder.

### TRADING: everyday checks

~~~bash
cd "$HOME/Nbot"
./nbotctl cluster status testnet-trade
./nbotctl position testnet-trade
./nbotctl health testnet-trade
./nbotctl recent testnet-trade
./nbotctl pnl testnet-trade
~~~

**null** for the open position means no position is recorded. **pending_outcomes**
counts completed-trade reports still waiting for acknowledgement from learning.

Follow the trader log:

~~~bash
./nbotctl logs testnet-trade --follow
~~~

Press Ctrl+C to stop viewing. This does **not** stop the bot.

### LEARNING: everyday checks

~~~bash
cd "$HOME/Nbot"
systemctl is-active nbot-observation-live.service
systemctl is-active nbot-observation-testnet-control.service
systemctl is-active nbot-research-epoch.timer
.venv/bin/python nbot_admin.py research-epoch-status
sudo journalctl -u nbot-research-epoch.service -n 40 --no-pager
~~~

### BOTH: disk and memory

~~~bash
df -h "$HOME"
free -h
~~~

Growing logs, data, and backups need space. If space is low, expand the disk or
arrange a reviewed retention plan. Do not delete databases, order records, or
runtime files just to clear an error. The scheduled research command already
uses its supported raw-data pruning option.

## 15. Pause, stop, and restart

### Pause new trades while continuing to protect an open position

**TRADING:**

~~~bash
cd "$HOME/Nbot"
./nbotctl entries disable testnet-trade
./nbotctl status
~~~

Wait for **entries_enabled: false**. The worker continues handling an existing
position. Pausing new entries does not close an open position.

To resume, after checking the same session is still healthy:

~~~bash
./nbotctl cluster status testnet-trade
./nbotctl entries enable testnet-trade
~~~

### Stop the Testnet system safely

Disable entries first. Wait until status shows:

- entries_enabled is false
- open_position is null
- entry_inflight is null
- pending_outcomes is 0
- recovery_critical is false

Then, **TRADING:**

~~~bash
./nbotctl cluster stop testnet-trade
~~~

This stops the Testnet worker, tunnel, and remote Testnet control service.
The learning VPS's LIVE collector and scheduled research continue.
If stopping is refused, resolve the stated condition; do not kill processes,
delete state, or reboot as a shortcut.

### Disarm after safely ending a Testnet trial

Arming means "authorize a Testnet session" and initializes its saved entry counter.
Enabling entries means "allow new trades within that session." You do not arm or
disarm every day. Normally use entries disable/enable to pause or resume.

To end the authorization, first follow the safe-stop procedure above. Only when
the worker is stopped, the account is flat and no entry/outcome is unresolved:

~~~bash
./nbotctl disarm testnet-trade
./nbotctl status
~~~

Disarm does not close positions or replace the pause command. Do not disarm an
open position. To begin another trial later, use section 12's explicit arm,
doctor, start, status and enable sequence.

### Restart after a normal safe stop

If the release and arm session have not changed:

~~~bash
cd "$HOME/Nbot"
./nbotctl cluster start testnet-trade
./nbotctl cluster status testnet-trade
./nbotctl entries enable testnet-trade
~~~

Run the enable command only after status is healthy.

### After a VPS reboot or an unexpected trader crash

Observation services and the tunnel are boot-enabled. The Testnet worker is not.

On **TRADING**, first block entries and inspect saved state:

~~~bash
cd "$HOME/Nbot"
./nbotctl entries disable testnet-trade
./nbotctl status
~~~

- **Flat, no unresolved entry/outcome:** use cluster start and check status before
  enabling entries.
- **Saved open position, entry in progress, or pending outcome:** use the local
  recovery start below. The cluster launcher deliberately refuses these states.

~~~bash
./nbotctl start testnet-trade
./nbotctl status
./nbotctl health testnet-trade
~~~

Local startup lets Execution reconcile its saved state with Binance without
requiring a successful remote learning connection first. Keep entries disabled
until reconciliation and any outcome delivery are resolved. If recovery is
critical or startup fails, preserve logs and get help; do not initialize a fresh
state over an existing exchange position.

A server that is off cannot actively manage a position. An exchange-held
protective stop is not a replacement for keeping the worker operational.

### A Testnet session limit has been reached

Do not delete the session files. First disable entries, reach the safe flat state,
and stop the cluster. If you deliberately want another trial session, then:

~~~bash
./nbotctl arm testnet-trade
./nbotctl cluster start testnet-trade
./nbotctl cluster status testnet-trade
~~~

Enable entries separately after checks. Do not rearm while a worker or position
is active. Rearming is a deliberate new session, not a bypass for a recovery error.

## 16. Fix common problems

Always begin with the logs for the relevant server. Do not include API keys,
tokens, private SSH keys, or complete secret files when asking for help.

| Symptom | Check and next action |
|---|---|
| SSH times out | Check VPS is on, correct IP/port, provider firewall and Ubuntu firewall |
| Permission denied (publickey) | Check login user, key path, copied public-key line, its source-IP restriction and file permissions |
| SSH host identification changed | Verify the new fingerprint through the provider console; do not disable host-key checking |
| GitHub repository not found | Check the URL and whether your GitHub account has access |
| GitHub password rejected | Use a suitable personal access token at the password prompt |
| FileExistsError while creating secrets | A file already exists; preserve it and check whether this is an existing installation |
| Connection refused on 18766 | Check the trading tunnel service and learning Testnet control service |
| HTTP authentication failure | Both control-link files must have exactly the same token |
| Remote release mismatch | Run git rev-parse HEAD on both; update them to the same reviewed commit |
| Dirty worktree / uncommitted files | Run git status --short; preserve and review changes rather than resetting them |
| Secret file mode invalid | Apply chmod 600 to the named secret file and chmod 700 to config/secrets |
| Clock not synchronized / timestamp rejected | Fix Ubuntu time synchronization and recheck timedatectl |
| Wrong role / forbidden role path | Use the intended role-specific installation; do not merge mutable folders from the two VPSs |
| Testnet credentials missing/invalid | Check the exact Testnet env filename, key type, Futures demo environment, permissions and IP restrictions |
| Hedge mode unsupported | Use a dedicated flat demo account in One-way mode |
| Another runtime/lock is active | Use nbotctl status; do not start a second worker or delete its lock |
| Other profile active | Disable entries in that profile and safely stop it before switching |
| Stale market data | Check time, public Binance access, collector logs and server load |
| Rate limit / HTTP 429 or 418 | Let backoff/recovery work; do not repeatedly restart or run extra collectors |
| No trades after training | Check model reason and risk vetoes; no positive opportunity is a valid result |
| Research job says inactive | Normal between runs; check timer and last journal result |
| Research service failed | Read its journal and epoch status; do not reset memory to hide the failure |
| Session limit reached | Use the explicit safe rearm procedure, only when stopped and flat |

Useful targeted logs:

**LEARNING:**

~~~bash
sudo journalctl -u nbot-observation-live.service -n 100 --no-pager
sudo journalctl -u nbot-observation-testnet-control.service -n 100 --no-pager
sudo journalctl -u nbot-research-epoch.service -n 100 --no-pager
~~~

**TRADING:**

~~~bash
sudo journalctl -u nbot-control-tunnel-testnet.service -n 100 --no-pager
cd "$HOME/Nbot"
./nbotctl logs testnet-trade --component runtime --lines 100
./nbotctl logs testnet-trade --component execution --lines 100
~~~

A plain doctor run while a worker holds its lock can report that lock. Prefer
**cluster doctor testnet-trade** for a running connected cluster; it recognizes
the matching worker's own lock.

## 17. Existing installations and updates

### Replacing only the learning VPS

Keep the trading VPS's private keys, execution state, receipts, and session files.

1. Pause entries on Trading; leave an open position under the existing worker's
   management. Schedule the change for a safe flat state.
2. Preserve or back up the old learning evidence if you intend to retain it.
   A blank learning server starts learning from zero; GitHub does not hold models.
3. Set up the new learning VPS using this guide's learning steps.
4. Pin it to the **currently deployed trading commit**, not simply latest main.
5. Authorize the existing server-to-server public key on the new learning VPS.
6. Copy the **existing** control-link.env over the verified connection. Do not
   generate a new token on just one side.
7. Render the trading tunnel with the new learning IP using section 10.
8. Verify the new host fingerprint, both firewalls, and cluster status.
9. Allow the new server to accumulate evidence; then restart/enable the checked
   Testnet trial when appropriate.

If the old learning VPS is gone and cluster stop cannot reach it, disable entries,
wait for safe flat state, and use **./nbotctl stop** on Trading to stop the local
worker **only if it is the unmanaged Testnet worker**. A systemd-managed
LIVE_PAPER worker rejects that local stop command.

For an existing LIVE_PAPER installation, first run the following on Trading:

~~~bash
cd "$HOME/Nbot"
./nbotctl entries disable live-paper
./nbotctl status
~~~

Wait for the LIVE_PAPER profile to show entries disabled, no open position,
no entry in flight, zero pending outcomes, and no recovery-critical state.
Only after those checks, stop its systemd service. If permanently switching
to Testnet, also disable its automatic startup:

~~~bash
sudo systemctl stop nbot-execution-live-paper.service
sudo systemctl disable nbot-execution-live-paper.service
./nbotctl status
~~~

Do not start Testnet while the old profile is still active. A previously deployed
LIVE_PAPER installation has additional profile-specific gates; do not treat its
configuration as interchangeable with Testnet.

### Updating both VPSs later

Even a documentation-only commit changes Git's version number. This bot compares
the exact commit across servers. Update both together; do not change a running
checkout just because a new document appeared on GitHub.

1. On Trading, disable entries. Wait for the safe flat conditions in section 15.
2. Run cluster stop testnet-trade while the old learning server is still reachable.
3. On Learning, pause the research timer. Let any current research job finish
   before stopping the collector:

~~~bash
sudo systemctl stop nbot-research-epoch.timer
while systemctl is-active --quiet nbot-research-epoch.service; do
  echo "Waiting for the current research job to finish..."
  sleep 10
done
sudo systemctl stop nbot-observer.target nbot-observation-testnet-control.service
~~~

If research has failed, inspect its journal and preserve the failure state first.
The wait can take a long time for a large batch; do not interrupt an active job
just to speed up an update.

4. Take the stopped backups described in section 18.
5. On Trading, fetch and choose the exact new revision:

~~~bash
cd "$HOME/Nbot"
git status --short
git -c credential.helper= fetch origin
git rev-parse origin/main
~~~

Stop if git status showed unexpected changes. Write down the printed target
commit. Review the release notes, including any migration instructions.

6. On **BOTH VPSs**, enter that same target commit:

~~~bash
cd "$HOME/Nbot"
git -c credential.helper= fetch origin
read -rp "Paste the chosen full 40-character commit: " NBOT_RELEASE
git checkout --detach "$NBOT_RELEASE"
.venv/bin/python -m pip install -r requirements.txt
git rev-parse HEAD
git status --short
~~~

Do not use git reset --hard, git clean, or delete data/runtime/config to force an
update. Database migrations, if required by a future release, need that release's
specific instructions.

7. On Learning, rerun the Observation installer command from section 9, retaining
   existing memory and secrets. Do not reset its research memory.
8. On Trading, verify the tunnel configuration. When deliberately ready for the
   new release's trial, arm a fresh Testnet session and run cluster doctor,
   cluster start, status, then entries enable as in section 12.
9. Expect **LEARNING_WAIT_FOR_COMPATIBLE_MODEL** until this release has a compatible
   model. Models are tied to their producing release. An update does not erase
   saved evidence, but may temporarily remove model eligibility.

If an update fails, keep entries disabled, preserve the backup and logs, and
review the failure. Do not restore an older trading-state snapshot over newer
exchange orders. Code rollback and state rollback are different operations.

## 18. What to back up

**GitHub holds the program, not your private keys or learned history.**

| Server | Important saved items |
|---|---|
| Both | config/secrets, .nbot-role, exact Git commit, installed NBOT service files |
| Learning | data/observation, runtime/observation, relevant logs |
| Trading | data/execution, runtime/execution, receipts/outcomes, relevant logs, its server-to-server SSH key |

For a consistent simple backup, use a maintenance window: Trading must be safely
stopped and flat; Learning's timer, research job, and collectors must be stopped
as described above. Do not copy an actively written SQLite file by itself.

After those stops, **run on EACH VPS**:

~~~bash
cd "$HOME/Nbot"
umask 077
NBOT_BACKUP_DIR="$HOME/nbot-backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$NBOT_BACKUP_DIR"
git rev-parse HEAD > "$NBOT_BACKUP_DIR/release.txt"
tar -czf "$NBOT_BACKUP_DIR/private-state.tar.gz" \
  config data runtime logs .nbot-role
chmod 600 "$NBOT_BACKUP_DIR/"*
printf 'Backup folder: %s\n' "$NBOT_BACKUP_DIR"
~~~

The archive contains secrets. Store a protected copy outside the VPS, using your
provider's secure backup facility or encrypted private storage. Never upload it
to GitHub. Preserve /etc/systemd/system/nbot-* and the relevant SSH/sudoers settings
through a protected server snapshot or separately reviewed backup procedure.

A backup on the same disk does not protect against losing that VPS. Make a
restore plan before depending on a long-running installation. Restoring Trading
requires checking actual Binance positions/orders against the saved state.

Restart Learning's services and the checked Testnet startup sequence after the
maintenance window.

## 19. Final checklist and reference links

Before considering the installation connected:

- [ ] Both VPSs use Ubuntu/Python as specified and their clocks are synchronized.
- [ ] The two roles are correct and the Git commits match.
- [ ] Git status is clean on both.
- [ ] Observation has no Binance private credentials.
- [ ] The inter-server SSH fingerprint was verified.
- [ ] Only SSH is exposed; the control service and tunnel bind to loopback.
- [ ] Shared tokens match and secret-file permissions are correct.
- [ ] LIVE collector, Testnet control, research timer, and tunnel are active.
- [ ] Authenticated control health returns the learned Testnet profile.
- [ ] Trading is armed only when you intend to test.
- [ ] One worker runs, with no unresolved recovery state.
- [ ] You know how to disable new entries and how to recover after reboot.
- [ ] Private backups exist outside GitHub.

Then verify an **actual Testnet trade**, when a legitimate learned opportunity
appears: entry, protective stop, eventual close, and acknowledged outcome.
Confirm the one-position rule and later perform supervised restart/link-failure
checks. Do not invent a successful test because the processes are running.
Do not intentionally reboot with a position on your first day merely to tick a box.

This guide's shell/Python examples and service rendering were checked against
the repository. A real fresh two-VPS deployment and authenticated Binance
acceptance still need to be verified in your own environment.

More detail:

- [Short learned-Testnet setup](LEARNED_TESTNET_SETUP.md)
- [Learned-Testnet behavior contract](LEARNED_TESTNET_CONTRACT.md)
- [Previous safety fixes and migration notes](SEVEN_SAFETY_FIXES.md)
- [V3 roadmap](NBOT_V3_ROADMAP.md)
- [Ubuntu OpenSSH documentation](https://ubuntu.com/server/docs/how-to/security/openssh-server/)
- [Ubuntu firewall documentation](https://documentation.ubuntu.com/server/how-to/security/firewalls/index.html)

### Telegram menu

Use /help, /status, /position, /recent, /pnl, /learning, /enable and /disable.
For channel notifications and private commands, configure a separate command
chat as explained in [OPERATIONS.md](OPERATIONS.md#telegram-commands).
