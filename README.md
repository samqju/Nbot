# NBOT V3

NBOT V3 is a clean two-VPS rebuild of NBOT.

The architecture has two independent roles:

- **EXECUTION** — capital guardian: risk, entry, stops, position management, reconciliation, emergency handling, durable execution outcomes.
- **OBSERVATION** — market truth and intelligence: broad market collection, research evidence, features, outcomes, model evaluation, training, recommendation snapshots.

V3 starts from clean runtime state and clean databases. V1/V2 remain engineering references in Git history and immutable tags; they are not active V3 runtime dependencies.

## Current phase

`V3.0 CLEAN FOUNDATION`

This phase provides role identity, named operating profiles, fail-closed profile validation, common utility primitives, `nbotctl` bootstrap commands, and the clean repository layout. Trading/research workers are intentionally not implemented yet.

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

Run foundation checks with:

```bash
./nbotctl doctor testnet-trade
./nbotctl status
python3 -m unittest discover -s tests -v
```

`LIVE_TRADE` remains fail-closed unless explicitly armed, and no V3 worker can place orders in V3.0 because exchange/runtime workers have not yet been built.

The canonical implementation contract is `docs/NBOT_V3_ROADMAP.md`.
