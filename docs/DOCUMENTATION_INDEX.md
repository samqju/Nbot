# Documentation index and current bot behavior

**2026-10-03 candidate expansion:** [24-candidate paper learner and larger-VPS setup](CANDIDATE_LIBRARY.md). Learned paper selection now tests 24 versioned rules with separate completed-trade attribution. Use the standard profile for 4 CPU / 8-12 GB RAM.

Paper feedback update: [30-day auto-learning experiment](PAPER_AUTO_LEARNING.md). Learned mainnet-paper now adapts setup rankings from its own settled paper trades. Testnet and real-money selection remain separate; economic proof is still unestablished.


**2026-10-02 mode update:** [The three-mode guide](TRADING_MODES.md) describes Testnet trading, learned mainnet paper, and the separately authorized small mainnet trial. Earlier V3.10-only restrictions below describe the original automatic Champion roadmap. This manual trial does not declare those economic gates passed. No Testnet-paper mode is supported.


Reviewed: **2026-10-01**, against learner code
[9fff54c](https://github.com/samqju/Nbot/commit/9fff54c3889e26c21dd217d439783af4803993d6).
This review covers all **18 existing tracked Markdown files**, plus this new index.
Documentation publication does not install code or prove that the services are running.
A follow-up adds the [environment-file field guide](ENVIRONMENT_SETUP.md) and
explicit Testnet template, plus the safe disarm procedure.

## Start here

1. [Beginner two-VPS guide](TWO_VPS_BEGINNER_GUIDE.md): create both servers,
   install the same release, connect them, and start Testnet safely.
2. [1 CPU / 1 GB learner guide](SMALL_VPS_LEARNER.md): use tiny mode, understand
   what learning can do, inspect rejected models and monitor resources.
3. [Short Testnet setup](LEARNED_TESTNET_SETUP.md): a shorter reference once you
   understand the complete installation.

For private-file creation and every placeholder, use the
[environment-file setup guide](ENVIRONMENT_SETUP.md).

## What the bot currently does, in simple English

The learning server collects real market prices. It waits to see what happened
over the next four hours, then uses completed examples to train a numerical model.
A second layer checks recent results for five fixed setup types: trend
continuation, trend pullback, stretched reversal, volatility expansion and
relative strength. It checks them against market direction and volatility.

That layer can reduce a score or reject an opportunity. It cannot boost the
original prediction. If there are too few independent examples, it says so and
falls back to broader setup evidence or the original model.

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
an operational canary unless separately granted qualifying authority. Real-money
trading remains blocked behind the V3.10 requirements.

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
