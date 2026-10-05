# Observation VPS services

**2026-10-02 mode update:** [The three-mode guide](../../docs/TRADING_MODES.md) describes Testnet trading, learned mainnet paper, and the separately authorized small mainnet trial. Earlier V3.10-only restrictions below describe the original automatic Champion roadmap. This manual trial does not declare those economic gates passed. No Testnet-paper mode is supported.


For a complete new installation, use the [beginner guide](../../docs/TWO_VPS_BEGINNER_GUIDE.md).
For the 1 CPU / 1 GB learner, also read [tiny mode](../../docs/SMALL_VPS_LEARNER.md).
Reviewed 2026-10-05 against the current three-mode Observation service installer.

The base boot-managed role has two responsibilities:

1. `nbot-observation-live.service` continuously collects LIVE raw evidence.
2. `nbot-research-epoch.timer` checks every 15 minutes and invokes the research
   oneshot. It waits until a 96-event batch and its future labels are mature.

A timer check is not a retraining promise. Epochs keep collecting evidence while
a frozen challenger waits for its disjoint future validation/test window.

SQLite is embedded; there is no separate database daemon. Research uses a bounded
disposable workspace, commits compact permanent memory, removes successful scratch
work and prunes raw evidence only behind the qualified dependency watermark.

Profile control services are separate from the shared base collector/research jobs:

- `nbot-observation-testnet-control.service` — learned Testnet control (mechanical is an explicit test option);
- `nbot-observation-live-paper-control.service` — learned/operational LIVE-paper control;
- `nbot-observation-live-trade-control.service` — bounded LIVE-trade recommendation control.

Only the selected Execution mode should be active. See
[all-mode commands](../../docs/ALL_MODES_COMMANDS.md).

## Preview generated units without installing or starting

From an already prepared checkout, as the normal service user:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" --python "$PWD/.venv/bin/python" --user "$(id -un)" \
  --resource-profile tiny --destination runtime/rendered-units
~~~

## Install the fresh learning server

First complete the beginner guide's role identity, Python environment, control
token, private file permissions and SSH preparation. Both VPSs need the same
release. Observation needs no Binance private/order credentials.

On a fresh learning installation:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py research-memory-init
sudo .venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" --python "$PWD/.venv/bin/python" --user "$(id -un)" \
  --resource-profile tiny \
  --enable --start --enable-testnet-control --start-testnet-control
~~~

Tiny mode is opt-in; the default profile is standard. Tiny uses up to 20 coins,
two candle workers and four gap-recovery events per pass. Installed research
services have a 60% CPU quota and 384 MB memory ceiling; each collector/control
service has a 160 MB ceiling. Manual commands do not inherit these limits.
Monitor the real machine; these limits do not prove that it can keep up.

Do not start units while a manually launched collector still owns its runtime
lock. Existing installations require a controlled handover, consistent backups
and review of immutable research-generation contracts. Never delete state to
make an upgrade pass.

The installer exposes explicit flags for every profile control:

~~~bash
# Testnet
--enable-testnet-control --start-testnet-control

# LIVE paper
--enable-live-paper-control --start-live-paper-control

# bounded LIVE trade
--enable-live-trade-control --start-live-trade-control
~~~

These flags only enable/start Observation control units. They do not arm
Execution, enable entries, grant Research/Paper Champion authority, or approve
real-money trading.

The Observation services are boot-managed. The current Testnet cluster launcher
starts Execution as a managed local process; after a trader reboot, follow the
beginner guide's checked recovery/start sequence.


## Check profile control services

~~~bash
systemctl is-active nbot-observation-testnet-control.service
systemctl is-active nbot-observation-live-paper-control.service
systemctl is-active nbot-observation-live-trade-control.service
systemctl is-active nbot-observation-live.service
systemctl is-active nbot-research-epoch.timer
~~~

Use the selected mode's control service; do not treat three installed unit files
as permission to run three Execution modes.
