# Observation VPS services

**2026-10-02 mode update:** [The three-mode guide](../../docs/TRADING_MODES.md) describes Testnet trading, learned mainnet paper, and the separately authorized small mainnet trial. Earlier V3.10-only restrictions below describe the original automatic Champion roadmap. This manual trial does not declare those economic gates passed. No Testnet-paper mode is supported.


For a complete new installation, use the [beginner guide](../../docs/TWO_VPS_BEGINNER_GUIDE.md).
For the 1 CPU / 1 GB learner, also read [tiny mode](../../docs/SMALL_VPS_LEARNER.md).
Reviewed against learner release `9fff54c` on 2026-10-01.

The base boot-managed role has two responsibilities:

1. `nbot-observation-live.service` continuously collects LIVE raw evidence.
2. `nbot-research-epoch.timer` checks every 15 minutes and invokes the research
   oneshot. It waits until a 96-event batch and its future labels are mature.

A timer check is not a retraining promise. Epochs keep collecting evidence while
a frozen challenger waits for its disjoint future validation/test window.

SQLite is embedded; there is no separate database daemon. Research uses a bounded
disposable workspace, commits compact permanent memory, removes successful scratch
work and prunes raw evidence only behind the qualified dependency watermark.

The separate `nbot-observation-testnet-control.service` is needed for learned
Testnet operation. It defaults to learned selection and can be explicitly enabled
for reboot persistence. Mechanical selection is an explicit runtime test option.
LIVE/PAPER control is optional and remains an operational canary.

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

For deliberate LIVE/PAPER use, the installer also provides
`--enable-live-paper-control` and `--start-live-paper-control`. These do not
grant Research or Paper Champion authority.

The Observation services are boot-managed. The current Testnet cluster launcher
starts Execution as a managed local process; after a trader reboot, follow the
beginner guide's checked recovery/start sequence.
