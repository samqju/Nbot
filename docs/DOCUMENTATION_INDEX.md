# Documentation index and current bot behavior

**2026-10-06 Selective ML V1:** [Selective ML architecture and operations](SELECTIVE_ML.md)
documents the bounded LightGBM mean-R, lower-quantile and entry-feasibility
models used only by learned `live-paper`. Ridge remains a fallback/benchmark;
Execution safety and real-money authority are unchanged.

**2026-10-05 command audit:** [All-mode operator commands](ALL_MODES_COMMANDS.md)
is the canonical current syntax reference for `testnet-trade`, `live-paper`,
and `live-trade`. Historical phase documents keep their original command scope.

**2026-10-05 paper-feedback V4 research branch:** supported paper-feedback means
are shrunk toward neutral before ranking changes, and reporting records the
frozen pre-feedback choice beside the adaptive choice without assigning invented
PnL to an unchosen alternative.

**Shadow experiment update:** [One main position plus up to 10 shadow simulations](SHADOW_TRADING.md) in learned mainnet-paper and mainnet-trading. Shadow results stay separately labelled; valid paper shadows can now adjust paper ranking at reduced weight.

**2026-10-03 candidate expansion:** [24-candidate paper learner and larger-VPS setup](CANDIDATE_LIBRARY.md). Learned paper selection now tests 24 versioned rules with separate completed-trade attribution. Use the standard profile for 4 CPU / 8-12 GB RAM.

Paper feedback update: [30-day auto-learning experiment](PAPER_AUTO_LEARNING.md). Learned mainnet-paper now adapts setup rankings from its own settled paper trades. Testnet and real-money selection remain separate; economic proof is still unestablished.


**2026-10-02 mode update:** [The three-mode guide](TRADING_MODES.md) describes Testnet trading, learned mainnet paper, and the separately authorized small mainnet trial. Earlier V3.10-only restrictions below describe the original automatic Champion roadmap. This manual trial does not declare those economic gates passed. No Testnet-paper mode is supported.


Reviewed: **2026-10-05** against the current V3.9 three-mode CLI and documentation tree.
The review covers every tracked Markdown file in the current V3 repository, including the Observation service README.
Documentation publication does not install code or prove that the services are running.
A follow-up adds the [environment-file field guide](ENVIRONMENT_SETUP.md) and
explicit Testnet template, plus the safe disarm procedure.

## Start here

1. [Beginner two-VPS guide](TWO_VPS_BEGINNER_GUIDE.md): create both servers,
   install the same release, connect them, and start Testnet safely.
2. [Three-mode guide](TRADING_MODES.md): configure and switch among Testnet,
   LIVE paper, and the separately authorized bounded LIVE-trading trial.
3. [All-mode command reference](ALL_MODES_COMMANDS.md): exact current operator
   syntax for all three profiles.
4. [1 CPU / 1 GB learner guide](SMALL_VPS_LEARNER.md): use tiny mode, understand
   what learning can do, inspect rejected models and monitor resources.
5. [Selective ML V1](SELECTIVE_ML.md): nonlinear learned-paper ranking,
   abstention gates, entry-feasibility learning and operator commands.
6. [Short Testnet setup](LEARNED_TESTNET_SETUP.md): a concise Testnet-specific
   reference; it links back to the all-mode command matrix for other profiles.

For private-file creation and every placeholder, use the
[environment-file setup guide](ENVIRONMENT_SETUP.md).

## What the bot currently does, in simple English

The learning server collects real market prices. It waits until future labels
are causally mature, then stores compact symbol/side examples for each market
event. Ridge remains the stable linear benchmark. In learned `live-paper`, an
eligible Selective ML artifact can additionally learn nonlinear relationships
from those same causal examples while giving every market event total training
weight 1.

The live-paper selector combines Ridge, nonlinear mean-R, a lower-quantile
confidence estimate, V4 paper/shadow feedback and (when sufficiently sampled)
a learned entry-feasibility probability. It can reject the entire event rather
than choosing the least-bad coin. If no eligible ML artifact exists, it falls
back to the existing Ridge + V4 behavior.

The learning server can recommend one positive-ranked opportunity using fresh
Testnet prices. The trading server independently checks permission, prices,
risk, existing position and protective orders. It keeps at most one position.
Missing/stale data, incompatible models or no positive opportunity can correctly
mean no trade.

Completed Testnet trades are saved and acknowledged. They test the order
machinery; they do not become training examples from the real market.

## How long learning takes

- The first model needs roughly 16 hours of continuous usable collection plus
  processing. Missing data or slow hardware can extend this.
- Research works in batches of 96 five-minute target events. The timer checks
  every 15 minutes; it does not create a new model every 15 minutes.
- A frozen model's full evaluation uses 20 validation and 20 final-test events,
  spaced four hours five minutes apart. Allow roughly seven days of new data
  plus the last outcome's maturity, longer with gaps.
- `EVALUATE_WAIT` is normal while that evidence arrives. Collection and new
  research epochs should continue. Replacement models follow the evaluation cycle.
- On Learning, run `.venv/bin/python nbot_admin.py learning-report` to see
  saved support counts, results and rejection reasons. A rejection is not itself
  a software failure. A lost database's old rejection reasons cannot be recovered
  from the new server.

## What is not established

This is an experimental research-ranking learner, not a proven profitable bot.
It does not recognize every market structure, read news, invent arbitrary
strategies or autonomously replace the execution exit algorithm.

Its training target is a simulated four-hour result measured using ATR risk units.
Execution uses its own fixed-dollar risk and exit lifecycle. A model score is
therefore not a forecast of actual trade profits.

Testnet may use a non-rejected model before its research evaluation finishes.
This does not promote a Research Champion or Paper Champion. LIVE/PAPER remains
an operational canary unless separately granted qualifying authority. Automatic Research/Paper-Champion approval remains blocked behind the frozen
V3.9/V3.10 economic gates. Separately, the code exposes a bounded, explicitly
operator-authorized `live-trade` trial; that route is not Champion approval and
does not establish profitability.

Fresh research generations cannot recreate the old date-specific market-regime
calibration; `UNAVAILABLE_HISTORICAL_CALIBRATION` does not mean that audit passed.
The new setup filter does not replace that frozen regime contract.

The synthetic small-server benchmark and automated tests are described in the
[small-VPS guide](SMALL_VPS_LEARNER.md). They do not prove free-VPS capacity,
authenticated Binance operation, or profitability. Verify both servers with
the intended release and preserve test evidence.

## Document map

| Document | How to use it now |
|---|---|
| [Repository README](../README.md) | Current overview and entry point |
| [All-mode commands](ALL_MODES_COMMANDS.md) | Canonical current commands for testnet-trade, live-paper and live-trade |
| [Beginner installation](TWO_VPS_BEGINNER_GUIDE.md) | Primary step-by-step operator instructions |
| [Small-VPS learner](SMALL_VPS_LEARNER.md) | Tiny profile, learner limits, reports, verification scope |
| [Short Testnet setup](LEARNED_TESTNET_SETUP.md) | Current concise deployment and checks |
| [Observation services](../deploy/observation/README.md) | Current service rendering and installation |
| [Operations](OPERATIONS.md) | Current boundary plus clearly identified historical phase procedures |
| [Learned-Testnet contract](LEARNED_TESTNET_CONTRACT.md) | Current model selection, calibration and Testnet invariants |
| [Evidence lineage](EVIDENCE_LINEAGE_CONTRACT.md) | Current causal sampling and separation of research/Testnet evidence |
| [Execution safety](EXECUTION_SAFETY_CONTRACT.md) | Continuing capital-safety rules; final V3.1 subsection is historical |
| [Protocol](PROTOCOL_CONTRACT.md) | Frozen wire schema with current authority applicability |
| [Research governance](V3_9_RESEARCH_GOVERNANCE_CONTRACT.md) | Frozen review gates; no automatic promotion |
| [Market regimes](V3_9_MARKET_REGIME_CONTRACT.md) | Frozen historical calibration; fresh-generation limitations apply |
| [Operational regimes](V3_9_OPERATIONAL_REGIME_CONTRACT.md) | Evidence classes and required physical/current-release checks |
| [Paper Champion gate](V3_9_PAPER_CHAMPION_GATE_CONTRACT.md) | Frozen sustained-paper requirements, not a completion claim |
| [Research promotion](V3_9_RESEARCH_CHAMPION_PROMOTION_CONTRACT.md) | Explicit first promotion after genuine eligibility |
| [Seven safety fixes](SEVEN_SAFETY_FIXES.md) | Historical changes/test record and migration cautions |
| [Pre-V3.10 gaps](PRE_V310_GAP_LEDGER.md) | Outstanding deployment, operational and evidence requirements |
| [V3 roadmap](NBOT_V3_ROADMAP.md) | Current addendum, original architecture, historical phases and future goals |

V1/V2 roadmaps and source snapshots are historical Git references, not additional
active Markdown deployment guides in this V3 tree. Root-path examples, one-time
reset instructions and test counts in historical sections retain their original
scope. Never reset current databases just because an old phase began from zero.

## Updates, restarts and backups

GitHub main is the source to deploy, not evidence of deployment. Check the actual
release on both VPSs and use the beginner guide's safe update/recovery procedure.
Preserve trading state, receipts, pending outcomes, exchange-budget state and
research memory. Do not bypass a safety block by deleting files.

Observation's installed services can restart at boot. The current Testnet trader
needs the checked startup/recovery sequence after a reboot. An open position
must be recovered through the local capital-first path, not a forced cluster start.

Reports are useful explanations, but cannot restore learning. Configure a
consistent private off-server backup separately; no automatic backup destination
is installed for you. Lost historical data cannot be regenerated by this update.
