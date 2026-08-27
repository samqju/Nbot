# NBOT V3

NBOT V3 is a clean two-VPS rebuild of NBOT.

The architecture has two independent roles:

- **EXECUTION** — capital guardian: risk, entry, stops, position management, reconciliation, emergency handling, durable execution outcomes.
- **OBSERVATION** — market truth and intelligence: broad market collection, research evidence, features, outcomes, model evaluation, training, recommendation snapshots.

V3 starts from clean runtime state and clean databases. V1/V2 remain engineering references in Git history and immutable tags; they are not active V3 runtime dependencies.

## Current phase

`V3.9 — continuous challenger learning / long-term Paper Champion evidence`

Current status is deliberately split:

- **V3.9 implementation:** complete enough for continuous research operation, including compact 96-event research epochs, immutable challenger artifacts, rolling governance, market/operational regime evidence, the frozen Research Champion promotion boundary, and the frozen Paper Champion gate.
- **V3.9 economic proof:** **NOT PASSED**. Research Champion is currently `NONE`; Paper Champion is `NONE`; Execution research authority is `NONE`.
- **V3.10:** **BLOCKED** until genuine Research Champion then sustained LIVE/PAPER Paper Champion evidence satisfies the frozen gates.

Challenger cadence is epoch-driven. `nbot-research-epoch.timer` checks for maturity every 15 minutes, but a challenger opportunity is created only after a genuinely new 96-event epoch is durably committed. `WAIT_FOR_MATURE_EPOCH`, unhealthy/failing epochs, and replay of an already-consumed epoch do not create additional challengers. A committed epoch whose challenger transition fails retains a durable retryable transition.

The Observation/Execution authority boundary remains unchanged: Observation owns research and recommendations but has no Binance order authority; Execution owns capital safety and independently validates any future approved recommendation.

### Preserved operational history

The earlier `V3.1 EXECUTION CORE` and subsequent V3.2–V3.8 operational milestones remain preserved as history. V3.7 is historically **OPERATIONALLY PROVEN**. Normal LONG, Normal SHORT, and the C–V fault campaign passed without weakening the canonical gate. V3.8 LIVE_PAPER operational canary work is also preserved as operational evidence. Those historical proofs do not imply V3.9 economic completion.

`live-trade` remains forbidden until V3.10 and cannot be reached merely by finishing maintenance/documentation work.

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
