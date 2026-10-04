# Private environment files: fresh-VPS guide

An environment file is a small settings file containing lines such as
`NAME=value`. A template contains field names and safe defaults, not your secrets.
The private copy contains your actual values and stays on your VPS.

**V3 does not use a single .env file at the repository root.** It uses separate
files under `config/secrets/`. A legacy root `.env` makes the V3 doctor fail.
If an old server has one, preserve it privately and identify the old installation
before migration. Do not delete it blindly or copy it onto the learning VPS.

Follow the [beginner guide](TWO_VPS_BEGINNER_GUIDE.md) in order. This page explains
its private-file steps; it is not an alternative service-start procedure.

## Which file belongs where?

| Server | Private file under config/secrets/ | Tracked template | Required? |
|---|---|---|---|
| Trading | execution-testnet.env | [execution-testnet.env.example](../config/examples/execution-testnet.env.example) | Yes for Testnet orders |
| Both | control-link.env | [control-link.env.example](../config/examples/control-link.env.example) | Yes for the server connection |
| Trading | execution-live-paper.env | [execution-live-paper.env.example](../config/examples/execution-live-paper.env.example) | Only for separate LIVE/PAPER operator setup |
| Learning | observation-live.env | [observation.env.example](../config/examples/observation.env.example) | Optional outbound Telegram notifications |

The old `execution.env.example` name now points to the specific templates.
For a deliberately approved small mainnet trial, copy [execution-live.env.example](../config/examples/execution-live.env.example) to config/secrets/execution-live.env on Trading only. Follow [the three-mode guide](TRADING_MODES.md) for every field and the separate approval steps.

The tracked `config/profiles/*.env` files define operating profiles. They are
not secret templates and must not contain your API keys or tokens.

## Create the private directory on each new VPS

After cloning and creating the Python environment:

~~~bash
cd "$HOME/Nbot"
install -d -m 700 config/secrets
~~~

Do not use these fresh-file steps to overwrite an existing working installation.
Private files are deliberately excluded from Git, so cloning cannot restore them.

## Trading: create the Testnet file

The easiest route is [beginner guide section 11](TWO_VPS_BEGINNER_GUIDE.md#11-add-binance-testnet-credentials).
It prompts invisibly for both keys and creates the private file from the template.
The required values are:

| Field | What to enter |
|---|---|
| TESTNET_API_KEY | The API key generated for your Binance USD-M Futures Testnet/demo account |
| TESTNET_API_SECRET | The matching Testnet API secret from that same key creation |
| TESTNET_MAX_SESSION_ENTRIES | Keep 100 initially; maximum entries in one explicitly armed session |
| TESTNET_MAX_ENTRY_NOTIONAL_USD | Keep 1000 initially; maximum position value in pretend USD, not loss allowance |
| TESTNET_REST_TIMEOUT_SECONDS | Keep 5; maximum wait for a REST request |
| NBOT_EXECUTION_IDLE_POLL_SECONDS | Keep 2; idle loop interval |
| NBOT_EXECUTION_OPEN_POLL_SECONDS | Keep 0.5; open-position loop interval |
| NBOT_TELEGRAM_TIMEOUT_SECONDS | Keep 5; timeout for optional Telegram calls |

Do not enter an SSH key, GitHub token or real-money Binance key in either
Testnet credential field. Endpoints are pinned by code; do not override them.

If you prefer to fill in the template with an editor, use this **instead of**
the beginner guide's key-prompt step, on Trading only:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python - <<'PY'
from pathlib import Path
source = Path("config/examples/execution-testnet.env.example")
target = Path("config/secrets/execution-testnet.env")
with target.open("x", encoding="utf-8") as handle:
    target.chmod(0o600)
    handle.write(source.read_text(encoding="utf-8"))
print("Created private template copy. Fill both required Testnet fields.")
PY
nano config/secrets/execution-testnet.env
~~~

In nano, enter values after `=`, press **Ctrl+O**, **Enter**, then **Ctrl+X**.
If the file already exists, the creation command refuses to replace it.
Do not erase an existing file to repeat this step.

## Both servers: create the connection token once

Use [beginner guide section 8](TWO_VPS_BEGINNER_GUIDE.md#8-create-their-shared-connection-password).
It generates one random token on Trading without printing it, then copies that
private connection file through verified SSH to the fresh Learning server.

| Field | What to enter |
|---|---|
| NBOT_CONTROL_AUTH_TOKEN | The generated token; exactly the same on both VPSs |
| NBOT_OBSERVATION_TESTNET_URL | Keep http://127.0.0.1:18766 for the guide's Testnet SSH tunnel |
| NBOT_OBSERVATION_TIMEOUT_SECONDS | Keep 2.0 |
| NBOT_OBSERVATION_LIVE_PAPER_URL | Only for separately configured paper mode: http://127.0.0.1:18765 |
| NBOT_OBSERVATION_LIVE_TRADE_URL | Mainnet trial tunnel: http://127.0.0.1:18767 |
| NBOT_OBSERVATION_CA_FILE | Leave absent for the SSH setup; advanced HTTPS certificate path only |

A blank token is invalid. Do not generate a different token independently on each
server. The learning VPS's public IP belongs in the SSH tunnel configuration,
not in the loopback URL. The optional paper URL alone does not configure paper mode.

## Optional Telegram fields

For Testnet, leave all Telegram fields blank if you only want terminal controls.
The older mechanical LIVE/PAPER canary needs Telegram /enable. Learned paper uses NBOT_PAPER_SELECTION=learned on both sides and supports terminal entries enable live-paper. Mainnet trial also supports terminal controls.

| Field | What to enter |
|---|---|
| EXECUTION_TELEGRAM_BOT_TOKEN | Your Execution Telegram bot's token |
| EXECUTION_TELEGRAM_CHAT_ID | Numeric ID of the chat receiving the bot's messages |
| EXECUTION_TELEGRAM_COMMAND_CHAT_ID | Optional separate numeric private/group chat ID for commands and replies; empty uses the notification chat |
| EXECUTION_TELEGRAM_OPERATOR_USER_ID | Numeric Telegram user ID of the person authorized to issue commands |
| OBSERVATION_TELEGRAM_BOT_TOKEN | Optional separate notification bot token for Learning |
| OBSERVATION_TELEGRAM_CHAT_ID | Numeric destination chat ID for Learning notifications |
| NBOT_TELEGRAM_TIMEOUT_SECONDS | Keep 5 |

IDs are not usernames, phone numbers, VPS IP addresses or API keys. Keep a
negative sign if your chat ID has one. Observation does not listen for operator
commands. If using optional Learning notifications, use a separate bot token
to keep its notifications distinct from the Execution command bot.

The paper template also contains `LIVE_PUBLIC_REST_TIMEOUT_SECONDS=3` and
`LIVE_PUBLIC_MAX_CLOCK_SKEW_MS=5000`. Keep these defaults initially; they govern
public-market request timeouts and clock checks, not real-order permission.

## File format and checks

Use one `NAME=value` per line. Keep comments on their own lines starting with
`#`. Do not add `export`, shell commands, inline comments after values, or
placeholder brackets. This parser does not expand `$VARIABLE` references:
enter the actual intended value. Keep optional settings blank only where the
template permits it; required keys and tokens must be filled.

Confirm permissions without printing contents:

~~~bash
cd "$HOME/Nbot"
stat -c '%a %n' config/secrets
find config/secrets -maxdepth 1 -type f -name '*.env' -printf '%m %f\n'
git status --short
~~~

Expect directory mode **700** and private file mode **600**. Private files must
not appear as new files to commit. Never use `git add -f config/secrets`.
Run the beginner guide's doctor checks at the specified stage: before Testnet
arming, a disarmed warning is expected and is not fixed by changing credentials.

The bot reads these named private files; you do not need to source them in your
shell. Exported environment variables can override file values, so avoid global
exports of credentials. File changes normally require a controlled restart to
reach a running worker; do not restart an open position casually.

Back up these files privately and separately from GitHub. Do not post file
contents, screenshots of keys or secret-bearing shell commands when asking for help.

## Learning-only shadow simulation settings

The control-link template now includes optional NBOT_SHADOW_* fields. These
configure separate simulated accounts, never real-order permission or Trading
risk. Defaults enable up to ten shadow slots in learned LIVE modes. Read the
[shadow guide](SHADOW_TRADING.md) before changing settings; simulation settings
are frozen per release/mode to keep experiment results comparable.
