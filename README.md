# NBOT V3

NBOT V3 is a clean two-VPS rebuild of NBOT.

The architecture has two independent roles:

- **EXECUTION** — capital guardian: risk, entry, stops, position management, reconciliation, emergency handling, durable execution outcomes.
- **OBSERVATION** — market truth and intelligence: broad market collection, research evidence, features, outcomes, model evaluation, training, recommendation snapshots.

V3 starts from clean runtime state and clean databases. V1/V2 remain engineering references in Git history and immutable tags; they are not active V3 runtime dependencies.

## Current phase

`V3.1 EXECUTION CORE — ACCEPTANCE CLOSURE`

The V3.1 Execution capital components and `ExecutionWorker` are implemented. The local Execution runtime can now perform capital-first startup/reconciliation for the permanent `testnet-trade` laboratory, but V3.1 intentionally contains no integrated recommendation source. New Testnet entries therefore remain disabled until an explicit V3.2 mechanical canary supplies one.

`live-paper` remains non-runnable until the independent LIVE public market source is built for the later LIVE/PAPER phase. `live-trade` remains forbidden until V3.10. Observation/research/communication are later phases.

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
