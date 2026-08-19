# NBOT V3

NBOT V3 is a clean two-VPS rebuild of NBOT.

The architecture has two independent roles:

- **EXECUTION** — capital guardian: risk, entry, stops, position management, reconciliation, emergency handling, durable execution outcomes.
- **OBSERVATION** — market truth and intelligence: broad market collection, research evidence, features, outcomes, model evaluation, training, recommendation snapshots.

V3 starts from clean runtime state and clean databases. V1/V2 remain engineering references in Git history and immutable tags; they are not active V3 runtime dependencies.

## Current phase

`V3.2 EXECUTION TESTNET MECHANICAL — ACCEPTANCE CLOSURE`

Previous accepted checkpoint: `V3.1 EXECUTION CORE — ACCEPTANCE CLOSURE`
(`v3.1-execution-core-parity`).

The standalone Execution worker has completed the V3.2 Binance Testnet mechanical-canary and restart/reconciliation acceptance campaign. LONG/SHORT lifecycle, protection, trailing replacement, force close, exchange/local recovery and capital-safety fault behavior are proven by physical Testnet evidence and permanent deterministic equivalents where deliberate physical fault injection would add unnecessary risk.

V3.2 remains `TESTNET_MECHANICAL_ONLY`; it is operational evidence, not research or profitability evidence. There is still no integrated Observation recommendation source.

Next is V3.3: the independent Observation evidence worker and fresh LIVE passive evidence collection.

`live-paper` remains deferred to V3.8. `live-trade` remains forbidden until V3.10.

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
