# NBOT Everyday Operations

This is the simple operator command guide for the two-VPS architecture.

## Normal start order

1. Start Observation.
2. Verify Observation health.
3. Start Execution.
4. Verify the tunnel and Execution state.
5. Enable new trading only when you intentionally want it enabled.

---

## Observation: start everything

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

---

## Observation: stop everything

```bash
sudo systemctl stop nbot-observer.target
```

Stopping Observation does not stop the Execution Worker on the other VPS.

If Execution already has a position, it is designed to continue managing it.
If Execution is flat, it must not invent a new trade while Observation is
unavailable.

---

## Observation: restart everything

```bash
sudo systemctl restart nbot-observer.target
```

---

## Observation: restart only one component

Observation Worker:

```bash
sudo systemctl restart nbot-observation.service
```

Automatic training:

```bash
sudo systemctl restart nbot-auto-training.service
```

Promotion controller:

```bash
sudo systemctl restart nbot-promotion-controller.service
```

Paper-canary controller:

```bash
sudo systemctl restart nbot-paper-canary-controller.service
```

---

## Execution: start everything

```bash
sudo systemctl start nbot-execution.target
```

Check:

```bash
systemctl is-active nbot-execution.target
systemctl is-active nbot-observation-tunnel.service
systemctl is-active nbot-execution.service
```

---

## Execution: check current state

From the NBOT repository:

```bash
/opt/nbot/.venv/bin/python - <<'PY'
import json
from pathlib import Path
import config
from execution.outcome_outbox import ExecutionOutcomeOutbox

bot_path = Path(config.BOT_STATE_PATH)
paper_path = Path(config.PAPER_STATE_PATH)

bot = json.loads(bot_path.read_text()) if bot_path.exists() else {}
paper = json.loads(paper_path.read_text()) if paper_path.exists() else {}

print("ENGINE_STATE =", bot.get("engine_state"))
print("ENGINE_HALT_REASON =", bot.get("engine_halt_reason"))
print("OPEN_POSITION =", paper.get("open_position"))
print("COMPLETED_TRADES =", paper.get("completed_trade_count"))
print(
    "OUTBOX_PENDING =",
    ExecutionOutcomeOutbox(config.EXECUTION_OUTBOX_PATH).pending_count(),
)
PY
```

---

## Execution: disable new trades

This is the normal first step before planned Execution maintenance.

It does not force-close an existing position.

From the NBOT repository:

```bash
printf '%s\n' '{"action":"DISABLE_TRADING"}' > operator_command.json.tmp
mv operator_command.json.tmp operator_command.json
```

Wait a few seconds and check state.

Expected:

```text
ENGINE_STATE = TRADING_DISABLED
ENGINE_HALT_REASON = OPERATOR_DISABLE
```

If a position is open, Execution continues managing it.

For planned maintenance, wait until:

```text
OPEN_POSITION = None
```

and preferably:

```text
OUTBOX_PENDING = 0
```

before stopping/restarting Execution.

---

## Execution: enable new trades

Only do this when you intentionally want new trades to be allowed.

From the NBOT repository:

```bash
printf '%s\n' '{"action":"ENABLE_TRADING"}' > operator_command.json.tmp
mv operator_command.json.tmp operator_command.json
```

Execution performs reconciliation before returning to `RUNNING`.

Check state afterward.

---

## Execution: safe planned stop

Do not casually stop Execution while a position is open.

First:

1. disable new entries;
2. wait until flat;
3. check the pending outbox;
4. then stop the role.

Command:

```bash
sudo systemctl stop nbot-execution.target
```

---

## Execution: safe planned restart

First disable new entries, wait until flat and check the outbox.

Then:

```bash
sudo systemctl restart nbot-execution.target
```

The persisted disabled state is independent of the systemd restart. Enable new
entries separately only when intended.

---

## Execution: restart only the Observer tunnel

```bash
sudo systemctl restart nbot-observation-tunnel.service
```

Check:

```bash
systemctl is-active nbot-observation-tunnel.service
```

The tunnel is intentionally not a hard dependency that can terminate the
Execution Worker.

---

## Execution: restart only the Execution Worker

The command exists:

```bash
sudo systemctl restart nbot-execution.service
```

Open-position recovery has been physically tested.

However, this is a recovery capability, not the preferred routine-maintenance
procedure. For planned maintenance, disable new entries and wait until flat.

---

## Check Observation health on Observation

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

`order_authority` must be `NONE`.

---

## Check Observation connectivity from Execution

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

---

## View Execution logs

Recent:

```bash
sudo journalctl -u nbot-execution.service -n 100 --no-pager
```

Follow live:

```bash
sudo journalctl -u nbot-execution.service -f
```

Project log if present:

```bash
tail -n 100 logs/system.txt
```

---

## View Observation logs

Observation:

```bash
sudo journalctl -u nbot-observation.service -n 100 --no-pager
```

Training:

```bash
sudo journalctl -u nbot-auto-training.service -n 100 --no-pager
```

Promotion:

```bash
sudo journalctl -u nbot-promotion-controller.service -n 100 --no-pager
```

Paper canary:

```bash
sudo journalctl -u nbot-paper-canary-controller.service -n 100 --no-pager
```

---

## Check clock synchronization

On both VPSs:

```bash
timedatectl status
```

You want:

```text
System clock synchronized: yes
```

---

## Check deployed Git version

From the repository on both VPSs:

```bash
git rev-parse HEAD
git describe --tags --exact-match 2>/dev/null || true
git status --short
```

The two deployed roles should use the same approved SHA.

---

## Planned shutdown order

1. Disable new entries on Execution.
2. Allow any open position to finish.
3. Confirm Execution is flat.
4. Confirm/understand pending outcome state.
5. Stop Execution.
6. Stop Observation if required.

Do not force-close a trade merely because maintenance is convenient.

---

## If Observation fails during a trade

Do not stop Execution just because Observation is unavailable.

Execution is designed to continue:

- receiving its own Binance market data;
- managing the open position;
- trailing protection;
- closing the position;
- persisting the outcome.

After close, it keeps the outcome locally until Observation returns and remains
flat.

---

## If Execution fails

Observation can continue independently.

Restore/restart Execution and allow startup reconciliation to determine whether
a position must be recovered.

See:

```text
deploy/recovery/DISASTER_RECOVERY.md
```

---

## Never do these

Never:

- start legacy `run.py` beside the workers;
- run two Execution Workers;
- expose port `8765` publicly;
- disable SSH host-key verification;
- delete a pending outcome to hide a delivery error;
- copy mutable Observation state onto Execution;
- copy mutable Execution state onto Observation;
- put future order-writing credentials on Observation;
- stop Execution casually during an open position.
