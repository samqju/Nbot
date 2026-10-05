# Learning on a 1 CPU / 1 GB VPS

The tiny Observation learner can serve the current three-mode architecture:
`testnet-trade`, learned `live-paper`, and the separately authorized bounded
`live-trade` route. Only one Execution mode should run at a time. See
[ALL_MODES_COMMANDS.md](ALL_MODES_COMMANDS.md) for operator syntax.

Paper feedback update: [30-day auto-learning experiment](PAPER_AUTO_LEARNING.md). Learned mainnet-paper now adapts setup rankings from its own settled paper trades. Testnet and real-money selection remain separate; economic proof is still unestablished.


Reviewed 2026-10-05 against the current V3.9 tiny-service and three-mode operator behavior. See the
[documentation index](DOCUMENTATION_INDEX.md) for current instructions and historical contracts.

This is an experimental Testnet learner. It learns numerical relationships and
recent setup reliability. It does not read news, understand every chart pattern,
invent strategy code, or guarantee profits. Real-money order permission is unchanged.

## What is new

The existing price model is now checked against recent evidence for five setups:

| Setup | What the bot measures |
|---|---|
| Trend continuation | A longer move and a shorter move agree |
| Trend pullback | A short move goes against an established longer move |
| Stretched reversal | A short recovery follows a large opposing longer move |
| Volatility expansion | The current candle range is large relative to recent typical ranges |
| Relative strength | A coin is among the stronger or weaker recent performers |

These are fixed, measurable proxies. They are not a complete swing-point,
support/resistance, breakout, or order-book structure detector. The learned part
is how these setups have actually performed, including modeled costs, under
aligned, opposed or mixed market direction and low, normal or high volatility.

The main regression retains its accumulated history. A new calibration layer
uses only the latest 20 days, so setup reliability can change. It uses one mean
per setup and market event, not hundreds of coins counted as independent trials.
Its samples are separated by 4 hours 5 minutes to avoid overlapping outcome paths.
Each supported condition needs at least eight such samples. A sparse condition
falls back to the broader setup; if that is also sparse, the original regression
remains in use and the proposal explicitly says that setup evidence is insufficient.

Supported weak setups lower a candidate's score; non-positive cautious setup
results veto it. An optimistic setup cannot increase the original score or turn
a negative regression prediction into a trade. This deliberately starts as a
conservative learned filter, rather than a large strategy search likely to fit noise.
The caution margin is a heuristic based on sample variance, not a probability
that a trade will win. Frozen models are evaluated on new data with the existing
strict gates; those gates have not been relaxed to make rejection disappear.

One material limitation remains: targets are four-hour, candle-based research
simulations with ATR-based risk units. Execution uses its own fixed-dollar risk
and position-management lifecycle. Thus a predicted research R is not a forecast
of actual trade P&L. Proposal metadata and the report now state that distinction.
Execution outcomes remain mode-scoped. Testnet outcomes test the Testnet route;
learned paper outcomes can feed the paper-only feedback layer; bounded LIVE-trade
outcomes do not silently become paper-feedback labels. None of these alone proves
economic usefulness.

## Mode-specific control service choices

The base LIVE collector and research timer are shared. Start only the control
service for the selected mode. The installer supports these mode flags:

~~~bash
# Testnet control
--enable-testnet-control --start-testnet-control

# Learned LIVE-paper control
--enable-live-paper-control --start-live-paper-control

# Bounded LIVE-trade control
--enable-live-trade-control --start-live-trade-control
~~~

Do not run multiple Execution modes merely because multiple control units exist.

## Fresh server installation

Follow [the beginner guide](TWO_VPS_BEGINNER_GUIDE.md), with this change to the
Observation service installer on the **learning VPS**:

```bash
cd "$HOME/Nbot"
sudo .venv/bin/python deploy/observation/install_services.py \
  --repo "$PWD" --python "$PWD/.venv/bin/python" --user "$(id -un)" \
  --resource-profile tiny \
  --enable --start --enable-testnet-control --start-testnet-control
```

Tiny mode watches up to 20 eligible coins, uses two candle-fetch workers and
limits each gap-recovery pass to four events. Both LIVE and Testnet collectors
use it. The training batch remains 96 events; it is not shrunk to obtain easier
pass results. Only one research timer should run.

The installer gives research a 60% CPU quota and a 384 MB memory ceiling, and
each collector a 160 MB ceiling. Limits apply to the installed services; manual
research commands do not inherit them. The normal research timer is the supported
way to train on this machine. Read-only status commands are fine to run manually.

These are protective limits, not a guarantee every free VPS can keep up. A memory
limit failure must be investigated, not ignored; inspect the journal and epoch
status. Do not repeatedly restart failed jobs, add collectors, or delete memory.
If the machine cannot finish a batch before the next eight hours of data arrives,
use more RAM/CPU. Swap may prevent an OS crash but is not a substitute for capacity.

For a manual collector/configuration check with the same profile, prefix that
command with `NBOT_OBSERVATION_RESOURCE_PROFILE=tiny`. Keep the service profile
consistent for the generation. Moving to standard settings later changes the
observed universe and requires a deliberate, documented experiment transition.

## See whether learning is doing anything

On the **learning VPS**:

```bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py learning-report --output logs/learning-report.md
.venv/bin/python nbot_admin.py challenger-status
.venv/bin/python nbot_admin.py research-epoch-status
sudo journalctl -u nbot-research-epoch.service -n 50 --no-pager
```

The report shows setup sample counts, training descriptions, latest evaluation
results, and plain-English reasons for each failed requirement.
 Learned-paper reporting additionally shows raw versus shrunk feedback means and
the frozen-base versus adaptive decision audit. It also shows
candidate/benchmark results, the confidence-bound comparison, minimum-trade
count and doubled-cost result. A positive average alone is not a pass.

A first regression model may appear after roughly 16 hours plus processing.
Useful independent setup evidence takes longer. The 20 validation and 20 test
events are separated, so a full evaluation needs roughly seven days of future
data plus the last outcome's maturity, potentially longer with missing data.
Successive model replacements follow these evaluation windows; this is not a
model retrained after every order. Testnet results remain separate from LIVE labels.

Save the report off the VPS after each evaluation. Also maintain a consistent,
private off-server backup of research memory as described in the beginner guide.
No off-server backup is automatically configured: that needs your chosen backup
destination. A report alone cannot restore trained models or evidence.

## Version and upgrade rules

This learner has its own selector and `v39:context-v4:` model/evaluation namespace.
Old artifacts are not rewritten or relabeled as evaluations of the new learner.
Both VPSs must run the same release. Use a fresh learning generation for the
planned new VPS. For an existing research installation, back up and review its
immutable governance/eligibility contracts before migration; do not delete them
to force a new learner through. An incompatible contract can correctly block it.

The execution exit policy and one-position limit are unchanged. Learned proposals
include a setup explanation and evidence count. An unevaluated model may still
be used by the explicitly experimental Testnet path; it is not a proven champion.

## What the tests establish

Automated tests check causal sampling, context-dependent losses, sparse-evidence
fallback, no inflation of sample count by adding coins, identical scoring in
evaluation/inference, numerical rejection and tiny-service configuration.
They establish code behavior, not market profitability. Judge progress using
saved out-of-sample results and actual fresh-server resource measurements.

## Linux verification for this release

- Full regression run: 1,058 tests passed before the final report/contract check.
- Final Linux focused run: 33 tests passed, including the report, causal setup
  calibration, tiny-service settings and learned HTTP/order/stop/restart/close/ACK flow.
- Synthetic benchmark: 20 symbols, 192 raw events, one complete 96-event research
  epoch and model training; 3,840 training rows; peak process RSS 78.49 MiB;
  epoch plus model training 123.92 seconds on the verification host.
- The benchmark used simulated public data/network responses. It does not measure
  two simultaneous live collectors, free-provider CPU throttling, or long-run disk
  growth. It is not a test of trading returns or a promise of those timings on a
  free server.

To reproduce the synthetic benchmark, use a separate checkout with no bot
credentials or runtime data, then run:

~~~bash
python3 deploy/observation/benchmark_learner.py
~~~

The script uses a temporary data directory and repository test fixtures. Do not
run it alongside production research on a 1 GB VPS.
