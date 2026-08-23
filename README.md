# NBOT V3

NBOT V3 is a clean two-VPS rebuild of NBOT.

The architecture has two independent roles:

- **EXECUTION** — capital guardian: risk, entry, stops, position management, reconciliation, emergency handling, durable execution outcomes.
- **OBSERVATION** — market truth and intelligence: broad market collection, research evidence, features, outcomes, model evaluation, training, recommendation snapshots.

V3 starts from clean runtime state and clean databases. V1/V2 remain engineering references in Git history and immutable tags; they are not active V3 runtime dependencies.

## Current phase

`V3.7 OPERATIONALLY PROVEN -> V3.8`

NBOT is now operating with the intended capital-first two-VPS boundary: Observation owns market evidence, research, learning and recommendations; Execution independently owns account truth, risk, orders, protection, position management, reconciliation and emergency action. Observation has no Binance order authority.

Accepted implementation includes the earlier `V3.1 EXECUTION CORE`, the V3.2 standalone Testnet mechanical canary, V3.3 Observation evidence foundation, the V3.4 research/learning stack including V3.4.6 Research Champion evaluation and V3.4.7 Continuous Learning Foundation, V3.5 communication, and V3.6 two-VPS dry integration.

Current V3.7 operational status:

- **A — Normal LONG: PASS.** The integrated Testnet LONG completed through Execution-managed protective-stop closure, authoritative accounting, durable outcome delivery, and exactly-once Observation recording/ACK.
- **B — Normal SHORT: PASS.** The integrated Testnet SHORT completed through protected entry, independent OPEN management, autonomous protective-stop closure, authoritative Binance accounting, durable outcome delivery, and exactly-once Observation recording/ACK.
- **C–V fault/operational campaign: PASS.**

The original canonical V3.7 acceptance gate was not weakened. The previously deferred Testnet SHORT debt was physically closed on 2026-08-23 by proposal `PROP-33b8005daa79db45b237a3c449ec677c3d2d4db6`, autonomous `PROTECTIVE_STOP_TRIGGERED` closure, deterministic outcome `OUT-9b671e52f3e35e5ca9138358a96df3ae`, and exactly-once Observation recording/ACK. Together with the already accepted Normal LONG and C–V campaign, V3.7 is operationally proven. Its canonical tag becomes eligible only after this closure release passes validation and the same SHA is deployed on both VPSs.

At this V3.7 closure boundary Testnet Execution is FLAT, has no entry inflight or pending outcome, is DISARMED, and has new entries disabled. The LIVE Observation collector remains protected and active.

Next implementation phase: **V3.8 LIVE_PAPER**. `live-trade` remains forbidden until V3.10 and its evidence/arming gates.

## Local role identity

Each VPS has an ignored `.nbot-role` file at repository root:

```text
EXECUTION
```

or:

```text
OBSERVATION
```

## Operating profiles

- `testnet-trade`
- `live-paper`
- `live-trade`

Execution checks:

```bash
./nbotctl doctor live-paper
./nbotctl doctor testnet-trade
./nbotctl status
./run_execution.py --profile testnet-trade --self-check
python3 -m unittest discover -s tests -p 'test_*.py'
```

Do **not** arm `testnet-trade` merely to make `doctor` pass. V3.2 is the deliberate Testnet mechanical-canary phase.

The canonical implementation contract is `docs/NBOT_V3_ROADMAP.md`.
