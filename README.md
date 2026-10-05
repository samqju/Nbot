# NBOT V3

**2026-10-05 three-mode command audit:** use [the all-mode operator command reference](docs/ALL_MODES_COMMANDS.md) for validated `testnet-trade`, `live-paper`, and `live-trade` syntax. Current guides distinguish these active commands from historical phase examples.

**2026-10-05 paper-feedback V4 research branch:** supported paper-feedback means are conservatively shrunk toward neutral before changing ranking, and the paper report now audits frozen pre-feedback choices versus adaptive choices without inventing counterfactual PnL.

**Shadow experiment update:** [One main position plus up to 10 shadow simulations](docs/SHADOW_TRADING.md) in learned mainnet-paper and mainnet-trading. Shadow results stay separately labelled; valid paper shadows can now adjust paper ranking at reduced weight.

**2026-10-03 candidate expansion:** [24-candidate paper learner and larger-VPS setup](docs/CANDIDATE_LIBRARY.md). Learned paper selection now tests 24 versioned rules with separate completed-trade attribution. Use the standard profile for 4 CPU / 8-12 GB RAM.

Paper feedback update: [30-day auto-learning experiment](docs/PAPER_AUTO_LEARNING.md). Learned mainnet-paper now adapts setup rankings from its own settled paper trades. Testnet and real-money selection remain separate; economic proof is still unestablished.


Current learner/operator documentation reviewed 2026-10-05 against the V3.9 three-mode CLI and this research branch.
Use the [documentation index and current behavior summary](docs/DOCUMENTATION_INDEX.md)
to distinguish setup instructions, frozen contracts, and historical evidence.
Three-mode execution and its setup guide were updated 2026-10-02.
A GitHub update is not proof that either VPS is running that release.

NBOT V3 is a clean two-VPS rebuild of NBOT.

The architecture has two independent roles:

- **EXECUTION** — capital guardian: risk, entry, stops, position management, reconciliation, emergency handling, durable execution outcomes.
- **OBSERVATION** — market truth and intelligence: broad market collection, research evidence, features, outcomes, model evaluation, training, recommendation snapshots.

V3 starts from clean runtime state and clean databases. V1/V2 remain engineering references in Git history and immutable tags; they are not active V3 runtime dependencies.

## Start here: two VPSs, step by step

New to servers? Follow the [beginner two-VPS installation guide](docs/TWO_VPS_BEGINNER_GUIDE.md).
For private settings and placeholders, see the [environment-file guide](docs/ENVIRONMENT_SETUP.md).

It covers creating both servers, connecting them securely, starting learned
Testnet trading, daily checks, restarts, backups, and updates. After the initial
Testnet path is understood, use the [three-mode guide](docs/TRADING_MODES.md) and
[all-mode command reference](docs/ALL_MODES_COMMANDS.md) for LIVE paper or the
separately authorized bounded LIVE-trading trial.

## Small VPS learning upgrade

For a 1 CPU / 1 GB learning VPS, use the [small-VPS learner guide](docs/SMALL_VPS_LEARNER.md).
The new version adds recent setup/market-condition calibration, explicit rejection
explanations, and an opt-in 20-coin resource profile. It is an experimental
research-ranking system, not a proven profitable trader.

## Current phase

### Learned Testnet testing

Testnet control now defaults to a LIVE-trained model instead of hash-generated
mechanical proposals. It waits for mature training data, scores fresh market
features, and abstains when the best prediction is non-positive. Testnet trades
remain experimental and never become LIVE training evidence. Execution retains
all risk, arm, session-limit and one-position controls. The explicit mechanical
canary remains available with `--testnet-selection mechanical`.

See [setup and operating instructions](docs/LEARNED_TESTNET_SETUP.md) and the
[versioned contract](docs/LEARNED_TESTNET_CONTRACT.md). This addition does not
enable real-money trading or claim economic validation.

`V3.9 — continuous challenger learning / long-term Paper Champion evidence`

Current status is deliberately split:

- **V3.9 implementation:** complete enough for continuous research operation, including compact 96-event research epochs, immutable challenger artifacts, rolling governance, market/operational regime evidence, the frozen Research Champion promotion boundary, and the frozen Paper Champion gate.
- **V3.9 economic proof:** **NOT PASSED**. Do not infer a Research or Paper Champion from code completion; read runtime governance status. The experimental Testnet route does not require or create either champion.
- **V3.10:** **BLOCKED** until genuine Research Champion then sustained LIVE/PAPER Paper Champion evidence satisfies the frozen gates.

Challenger cadence is epoch-driven. `nbot-research-epoch.timer` checks for maturity every 15 minutes, but a challenger opportunity is created only after a genuinely new 96-event epoch is durably committed. `WAIT_FOR_MATURE_EPOCH`, unhealthy/failing epochs, and replay of an already-consumed epoch do not create additional challengers. A committed epoch whose challenger transition fails retains a durable retryable transition.
An opportunity may evaluate the existing frozen model and return `EVALUATE_WAIT`;
it does not promise a new model every eight hours.

The Observation/Execution authority boundary remains unchanged: Observation owns research and recommendations but has no Binance order authority; Execution owns capital safety and independently validates any future approved recommendation.

### Preserved operational history

The earlier `V3.1 EXECUTION CORE` and subsequent V3.2–V3.8 operational milestones remain preserved as history. V3.7 is historically **OPERATIONALLY PROVEN**. Normal LONG, Normal SHORT, and the C–V fault campaign passed without weakening the canonical gate. V3.8 LIVE_PAPER operational canary work is also preserved as operational evidence. Those historical proofs do not imply V3.9 economic completion.

An explicit, bounded mainnet trial is now available after your own testing and confirmation. It is independent of the still-unpassed automatic V3.10 Champion gates. Follow [the three-mode setup guide](docs/TRADING_MODES.md); publication does not activate trading.

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

Execution read-only checks for every mode:

```bash
./nbotctl status
./nbotctl doctor testnet-trade
./nbotctl doctor live-paper
./nbotctl doctor live-trade
./run_execution.py --profile testnet-trade --self-check
./run_execution.py --profile live-paper --self-check
./run_execution.py --profile live-trade --self-check
python3 -m unittest discover -s tests -p 'test_*.py'
```

For start/enable/pause/stop/recovery commands for all three profiles, use
[docs/ALL_MODES_COMMANDS.md](docs/ALL_MODES_COMMANDS.md).

Do **not** arm `testnet-trade` merely to make `doctor` pass. Follow the current
learned-Testnet setup and explicitly enable entries only when ready to test.
The V3.2 mechanical canary is a separate historical/test procedure.

The canonical implementation contract is `docs/NBOT_V3_ROADMAP.md`.

### Telegram menu

Use /help, /status, /position, /recent, /pnl, /learning, /enable and /disable.
For channel notifications and private commands, configure a separate command
chat as explained in [docs/OPERATIONS.md](docs/OPERATIONS.md#telegram-commands).
