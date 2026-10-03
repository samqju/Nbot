# A 30-day paper auto-learning experiment

This update adds feedback from completed mainnet PAPER trades to the existing
market-data learner. It keeps the one-position limit, sizing, stops and exits.
No new packages, neural network, GPU or language-model API is required.

## What it learns

The paper selector now checks [24 named candidates](CANDIDATE_LIBRARY.md), with
one selected candidate receiving each completed trade outcome. The base research
learner still studies price features and five measurable setup families:
trend continuation, pullback, stretched reversal, volatility expansion and relative
strength. These are limited proxies for market structure, not every chart pattern.

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
   results that were closed AND received before that event.
6. Store the model and its training cutoff. Save predictions before later trades,
   so the report cannot credit hindsight as a successful prediction.

The observation supervisor performs this work, not the HTTP request handler or
the trading position-management loop. Even when the base model is temporarily
unavailable, received paper outcomes can be archived by the supervisor.

## Resources and bounds

Use standard mode on the planned 4 CPU / 8-12 GB Learning VPS; see the
[candidate library setup](CANDIDATE_LIBRARY.md). The tiny profile remains available
for 1 CPU / 1 GB testing with fewer collected coins.
The feedback layer imports at most 256 receipts per pass and trains on at most
2,048 recent completed trades. It makes no new exchange requests.

It uses a 30-day rolling window with a 14-day recency half-life. Trades in the
same 4-hour-5-minute time bucket contribute one group average. At least eight
buckets AND eight effective recency-weighted buckets are required for adjustment.
Buckets reduce repetition; they do not prove statistical independence.

With insufficient evidence the weight is 1.0, meaning unchanged.
Supported weights range from 0.25 to 1.5. A negative base prediction never becomes
an entry because of feedback. Weak setups are downranked rather than permanently
removed, allowing later evidence to change their preference.

Learning clips individual results to -3R/+3R to limit outlier influence.
The report retains UNCLIPPED actual paper profit/loss and R: bad losses do not
disappear. The caution margin is a heuristic, not a calibrated probability.

A development benchmark of the feedback component at 2,048 stored samples took
0.377 seconds and used 31.84 MB peak process memory on the small Trading VPS.
This is an observed component measurement, not total bot usage or a capacity guarantee.

The existing collector and research jobs remain the main resource users.
Do not run extra collectors or parallel training jobs on the tiny VPS.
Use the [small-VPS guide](SMALL_VPS_LEARNER.md) for resource limits.
If journals report memory-limit failures, missing collection or training jobs
that cannot keep up, upgrade capacity before judging the learning.
A faster VPS cannot create missing trade evidence or make a strategy profitable.

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

The original top choice is logged but is not traded in a second account.
There is no claimed profit result for unchosen alternatives or a parallel frozen
baseline. That would require a separate, carefully matched simulation study.

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
