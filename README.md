# NBOT V3

NBOT V3 is a clean two-VPS rebuild of NBOT.

The architecture has two independent roles:

- **EXECUTION** — capital guardian: risk, entry, stops, position management, reconciliation, emergency handling, durable execution outcomes.
- **OBSERVATION** — market truth and intelligence: broad market collection, research evidence, features, outcomes, model evaluation, training, recommendation snapshots.

V3 starts from clean runtime state and clean databases. V1/V2 remain engineering references in Git history and immutable tags; they are not active V3 runtime dependencies.

## Current phase

`V3.7 -> V3.8 TRANSITION — V3.7-A PASS / V3.7-B DEFERRED`

NBOT is now operating with the intended capital-first two-VPS boundary: Observation owns market evidence, research, learning and recommendations; Execution independently owns account truth, risk, orders, protection, position management, reconciliation and emergency action. Observation has no Binance order authority.

Accepted implementation includes the earlier `V3.1 EXECUTION CORE`, the V3.2 standalone Testnet mechanical canary, V3.3 Observation evidence foundation, the V3.4 research/learning stack including V3.4.6 Research Champion evaluation and V3.4.7 Continuous Learning Foundation, V3.5 communication, and V3.6 two-VPS dry integration.

Current V3.7 operational status:

- **A — Normal LONG: PASS.** The integrated Testnet LONG completed through Execution-managed protective-stop closure, authoritative accounting, durable outcome delivery, and exactly-once Observation recording/ACK.
- **B — Normal SHORT: DEFERRED.** This remains explicit Testnet operational evidence debt.
- **C–V fault/operational campaign: PASS.**

The original canonical V3.7 acceptance gate is not being rewritten. Because B is deferred, `v3.7-testnet-e2e-operational-proven` must not be claimed or tagged as passed. An explicit sequencing exception in `docs/NBOT_V3_ROADMAP.md` permits V3.8 implementation to begin while keeping V3.7-B visibly deferred. A later LIVE_PAPER SHORT does not retroactively convert V3.7-B into a Testnet PASS.

At this transition boundary Testnet Execution is FLAT, has no entry inflight or pending outcome, is DISARMED, and is stopped. The LIVE Observation collector remains protected and active.

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
