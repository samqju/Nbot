# A 30-day paper auto-learning experiment

This experiment applies only to learned `live-paper` feedback. The base learner
and operator tooling also support `testnet-trade` and the separately authorized
bounded `live-trade` route; see
[ALL_MODES_COMMANDS.md](ALL_MODES_COMMANDS.md) for their current commands.

See also [the shadow simulation guide](SHADOW_TRADING.md): up to ten additional, separate simulated positions; the main account still permits only one position.

This experiment combines completed mainnet PAPER feedback with the existing
market-data learner. It keeps the one-position limit, sizing, stops and exits.
Selective ML V2 optionally adds the CPU-only `lightgbm` dependency on the
Learning VPS; no GPU or language-model API is required. Execution does not
install that dependency.

## What it learns

The paper selector still records [24 named candidates](CANDIDATE_LIBRARY.md),
with one selected candidate receiving each completed trade outcome. When an
eligible [Selective ML V2](SELECTIVE_ML.md) artifact exists, nonlinear ranking
is learned from the causal all-symbol/all-side research examples first; the
candidate library then remains an interpretable V4 feedback and shadow layer.
Ridge remains the fallback/benchmark.

The new paper learner asks: when this setup, market direction, volatility and
LONG/SHORT direction were actually traded by our paper engine, what happened?
It uses settled paper profit/loss after the paper engine's simulated fees,
divided by initial risk. It never treats an unexecuted suggestion as a loss.
It can then change which positive-scoring opportunity ranks highest.

This is genuine feedback-based adaptation over supported setups. It does not
invent new strategy code, learn from news, change risk settings or guarantee profit.
It does not force a trade when the base learner has no positive opportunity or
when Execution refuses one. Continuous operation does not mean continuous entries.

## How the loop works

1. Save a recommendation, its original score, feedback weight and model identity.
2. Execution independently decides whether it can trade and maintains at most
   one open position.
3. When the paper position closes, Execution durably records its result and
   delivers it to Learning with an acknowledgement.
4. Learning verifies the saved result against its original recommendation.
   Duplicate deliveries count once. Invalid, mismatched and overlapping-position
   records are excluded, with reasons retained.
5. At subsequent market events, update a small setup-ranking model using only
   results that were closed AND received before the recommendation decision.
6. Store the model and its training cutoff. Save predictions before later trades,
   so the report cannot credit hindsight as a successful prediction.

The observation supervisor trains the feedback model. The flat-side proposal
request gate also ingests a bounded batch of already-acknowledged outcomes and
checks loss pauses, so a close arriving between supervisor refreshes cannot
immediately bypass a pause. A remaining receipt backlog blocks new proposals
until caught up. This work never runs on the open-position management loop. Even when the base model is temporarily
unavailable, received paper outcomes can be archived by the supervisor.

## Resources and bounds

Use standard mode on the planned 4 CPU / 8-12 GB Learning VPS; see the
[candidate library setup](CANDIDATE_LIBRARY.md). The tiny profile remains available
for 1 CPU / 1 GB testing with fewer collected coins.
The feedback layer imports at most 256 receipts per pass and trains on at most
2,048 recent main outcomes plus at most 2,048 recent shadow records. It makes no new exchange requests.

It uses a 30-day rolling window with a 14-day recency half-life. Trades in the
same 4-hour-5-minute time bucket contribute one group average per source.
Main outcomes have weight 1; all shadow outcomes in that group/bucket together
have weight 0.25. Downranking needs at least four buckets, three effective
recency-weighted buckets, and a negative result beyond the caution margin.
Increasing preference additionally needs at least eight buckets.
Buckets reduce repetition; they do not prove statistical independence.

Before a supported group's result can change ranking, its clipped mean R is
shrunk toward a neutral 0R prior with four evidence-mass units. This does not
invent winning or losing trades. It deliberately makes small samples move ranking
less aggressively; the influence of the neutral prior fades as independent
evidence mass grows. The report shows both raw and shrunk means.

With insufficient evidence the weight is 1.0, meaning unchanged.
Outcome weights range from 0.25 to 1.5. An active loss pause sets the final
factor to zero. A negative base prediction never becomes an entry because of
feedback. Weak setups are downranked rather than permanently removed, allowing
later evidence to change their preference.

Entry practicality is no longer inferred from the next five-minute candle.
Immediate entry acceptance is decided by Execution from its current quote,
spread, proposal/reference drift and post-fill safety checks. Historical
next-bar drift remains visible as signal-decay research telemetry but contributes
no ranking penalty.

Learning clips individual results to -3R/+3R to limit outlier influence.
The report retains UNCLIPPED actual paper profit/loss and R: bad losses do not
disappear. The caution margin is a heuristic, not a calibrated probability.

A benchmark of the earlier main-only feedback component at 2,048 stored samples took
0.377 seconds and used 31.84 MB peak process memory on the small Trading VPS.
This historical measurement does not benchmark the expanded shadow-feedback implementation.

The existing collector and research jobs remain the main resource users.
Do not run extra collectors or parallel training jobs on the tiny VPS.
Use the [small-VPS guide](SMALL_VPS_LEARNER.md) for resource limits.
If journals report memory-limit failures, missing collection or training jobs
that cannot keep up, upgrade capacity before judging the learning.
A faster VPS cannot create missing trade evidence or make a strategy profitable.

## Mode boundary

The paper-feedback weights in this document are not silently shared into Testnet
or real-money ranking. Operator syntax remains mode-specific:

~~~bash
# Testnet
./nbotctl arm testnet-trade
./nbotctl cluster start testnet-trade
./nbotctl entries enable testnet-trade

# Learned paper
./nbotctl cluster start live-paper
./nbotctl entries enable live-paper

# Bounded LIVE trade
./nbotctl arm live-trade --confirm-real-money
./nbotctl cluster start live-trade
./nbotctl entries enable live-trade
~~~

Only one Execution profile may run at a time. These examples show command
equivalence, not permission to skip the setup/safety steps in the mode guide.

## Start the experiment

Follow [the three-mode guide](TRADING_MODES.md) to install the same Git release
on both servers, create the private configuration and set up the paper SSH tunnel.

On Learning, the paper control service must have NBOT_PAPER_SELECTION=learned
(the mode guide installs its systemd override). On Trading, set the same value in
config/secrets/execution-live-paper.env. Feedback is automatic in learned paper
mode; mechanical paper, Testnet and real-money trading do not use it.

On Trading, after any previous mode is safely flat and stopped:

~~~bash
cd "$HOME/Nbot"
./nbotctl cluster start live-paper
./nbotctl cluster doctor live-paper
./nbotctl cluster status live-paper
./nbotctl entries enable live-paper
~~~

Resolve errors before enabling. The first model and adequate completed-trade
evidence take time. No compatible model or no positive opportunity means no trade.
The existing daily risk and safety controls can pause entries; learning never
overrides them.

Leave one base collector, the research timer and the learned paper control service
running on Learning. Leave the single paper worker running on Trading.
After a worker restart, entries are disabled and must be explicitly enabled again.
A VPS or service failure can interrupt the experiment: inspect status daily.

The bot does NOT automatically switch to real money or stop on day 30.
You decide when to stop and review.

## Read progress

On Learning:

~~~bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py learning-report --output logs/learning-report.md
.venv/bin/python nbot_admin.py paper-learning-report --output logs/paper-learning-report.md
cat logs/paper-learning-report.md
~~~

The first report explains market-data models and research rejection reasons.
The second shows:

- a frozen-base decision audit: what the original model/rule ranking would have chosen
  before paper feedback versus what the adaptive ranking selected;
- completed eligible paper trades and elapsed days since the first recommendation;
- weekly paper PnL, win counts and closed-trade drawdown;
- completed trades and paper profit/loss for each of the 24 candidates, plus MODEL_ONLY;
- current candidate/condition weights and evidence support;
- how many executed choices differed from the original ranking;
- prediction error on trades completed AFTER their prediction was made;
- the same-trade error of an always-predict-zero reference;
- insufficient evidence, excluded records and training/report size limits.

The error uses clipped paper R, matching the learner's target. Lower error is
better, but it does not itself prove profitable selection. Weekly PnL is not a
controlled before/after experiment: market conditions may have changed.

The original top choice is logged for every comparable decision and summarized
against the adaptive choice. This is a causal selection audit, not invented PnL.
An unchosen alternative is never labelled as a win or loss. A true counterfactual
profit comparison still requires a separately matched forward simulation that
actually follows the frozen choice.

## After 30 days

On Trading, disable new entries, let the position finish, then inspect status:

~~~bash
cd "$HOME/Nbot"
./nbotctl entries disable live-paper
./nbotctl cluster status live-paper
~~~

Once flat with no unfinished entry or pending outcome:

~~~bash
./nbotctl cluster stop live-paper
~~~

Generate and save both reports on Learning. Check whether evidence accumulated,
whether supported weights changed, whether forward prediction error improved,
and whether paper PnL and drawdown were acceptable across different conditions.
Fewer than 20 scored completed trades produces an insufficient-evidence warning;
20 trades alone is NOT a profitability pass. Thirty days may be inconclusive.

Paper fills and costs differ from live execution. Funding is not currently
included in the paper PnL. Do not turn a good paper result into a profitability
claim or automatic mainnet approval.

## Persistence and upgrades

Feedback samples, models, exclusions and decision records are stored in the LIVE
Observation SQLite database alongside the control records. Research memory and
Execution trade history remain separate. Ordinary restarts preserve them.
Keep consistent off-server backups using the beginner guide; deleting a VPS
without backup still loses its memory.

A Git release defines an experiment cohort. Updating code starts a separate
feedback cohort so changed behaviour is not silently mixed with earlier results.
Keep one release for the planned 30 days unless a necessary fix requires a new
documented experiment. Earlier records remain available; review an older cohort:

~~~bash
.venv/bin/python nbot_admin.py paper-learning-report --release-sha YOUR_40_CHARACTER_OLD_COMMIT
~~~

This update does not modify Binance credentials, arm mainnet, install a new
Learning VPS, enable entries, change the one-position rule or auto-deploy itself.

## Release verification

On 2026-10-02 the full Linux suite passed 1,150 tests. The feedback tests cover
late-result exclusion, duplicate/restart handling, evidence support, rolling
expiry, outcome integrity, bounded training, changed recommendations and the
HTTP-to-paper-execution-to-feedback path. Tests use simulated data; no 30-day
market result is claimed.

The 2026-10-03 [candidate expansion](CANDIDATE_LIBRARY.md) adds 24 named rules,
per-candidate results and larger-VPS instructions. Its full regression run passed
1,162 tests; final edge-case changes passed 56 focused checks.

### Restarts, updates and recommendation timing

A service restart retains saved training data and models. For paper and testnet,
an older model can also survive an operational update when Git proves its
training, feature, data-contract, shared utility, configuration and dependency
sources unchanged. Missing Git history, changed training sources or invalid
artifact contracts block reuse. The original model provenance is retained.
Rejected models, corrupt artifacts and models with future/unmature labels remain
blocked. Real-money trials still require an exact-release model. Both VPSs must
still run the same deployed release.

New market events arrive every five minutes. The recommendation supervisor
refreshes every five seconds by default; the execution worker polls every two
seconds while flat and every 0.5 seconds while managing a position, plus request
time. These faster checks do not retrain or create new market events.
Recommendations expire after their existing short freshness window; between
events, waiting for fresh data is expected. No trade is forced each cycle.

The /learning report now includes recommendation readiness and its waiting
reason, compatible-model availability, shadow positions open/pending, completed
and excluded results, and last opportunity/result timestamps in UTC. Counts across
releases show historical activity; net simulated PnL is reported for the current
release only. Cancelled/unscorable results are not counted as completed scored
trades. Valid shadow outcomes now train the paper ranking layer at reduced weight. The main paper
position and its results remain separate (/position, /recent, /pnl).

### Feedback, loss pauses and entry cancellations (October 2026)

The experimental paper ranking layer now uses two labelled evidence sources:
main paper outcomes and valid completed paper-shadow outcomes. It does not
retrain the base research labels or enable real-money trading. Within each
candidate/direction/context and 4-hour-5-minute block, main outcomes contribute
weight 1 and all parallel shadow outcomes together contribute weight 0.25.
This limits, but does not eliminate, correlation. Old shadow records without
saved market context contribute only to the broad candidate/direction group.
New simulations save their decision-time context; no hindsight context is invented.

Feedback from older releases is reused only when Git history proves that the
fill, risk, attribution, shared configuration and outcome contracts match.
Original release IDs and digests remain intact. Shadow cost/risk configuration
and candidate catalog must also match. Missing history, incompatible contracts,
future receipts, invalid records and unknown candidates are excluded.

After three consecutive losing main paper trades in the same coin and direction
within six hours, that coin/direction is paused until one hour after the latest
loss. A different setup label cannot bypass this pause. A non-losing trade breaks
the streak. The pause is rebuilt from durable verified outcomes after restart,
does not close a position, and cannot create another position. Shadow results
do not trigger this main-account loss pause.

Shadow entries still wait for a forward candle and retain the original price
drift rule so historical shadow-account semantics are not silently rewritten.
Those drift cancellations are now classified as **next-bar signal-decay
research only**. They do not train the profit model, do not reduce candidate
preference and do not decide whether an immediate market entry is feasible.
Missing-data and main-candidate-reservation cancellations remain excluded from
trade-outcome learning.

Use /learning to see evidence counts, the Ridge winner, true raw ML winner,
ML confidence/edge gates, post-feedback candidate, the explicit
`REALTIME AT EXECUTION` entry-gate mode, next-bar signal-decay telemetry and
loss pauses.
The database also retains a per-event paper_feedback_checks record, including
no-trade decisions. Comparing two choices is an audit of behaviour, not proof
that the changed choice will be more profitable. Use /pnl and /recent to judge
the main paper account; shadow balances remain separate.
