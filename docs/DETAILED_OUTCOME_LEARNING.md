# Automatic learning from detailed opportunity outcomes

Current implementation: Selective ML V3 tick-paper learner. Publishing this
code on GitHub does not update either VPS. Deploy both roles at the same tested
release using the safe update procedure; preserve the current paper position,
execution receipts, Observation databases and research memory.

## In the simplest language

The Learning VPS keeps a notebook of what it knew before a possible trade. It
watches what happens afterward, including opportunities it rejected. When it
has enough reliable examples, it trains a replacement model. It then waits for
new market observations to test that model. Only a model that passes both later
evaluation windows can become the active **paper** model automatically.

A missed winner is one lesson, not permission to relax risk checks. The Trading
VPS still manages only one main position. Research simulations use no trading
balance, and the legacy ten shadow accounts remain a separate experiment.

## What changes and what remains separate

- Broad scanning targets up to 100 eligible symbols; actual coverage depends on
  the collector settings and usable history. A tiny collector configured for 20
  cannot supply 100 merely because the research target is 100.
- Detailed public WebSocket monitoring covers up to 20 symbols. Both LONG and
  SHORT decisions can start new overlapping hypotheses on each completed event,
  even when their predictions are negative or below the trade threshold.
- There is a hard maximum of 1,920 active hypotheses. A symbol accepts new
  hypotheses for one hour, then drains its remaining four-hour paths before
  rotating. No active path is deliberately discarded just to chase a new score.
- Pool admission includes strong scores, disagreements, near-threshold cases,
  diversity and deterministic controls. Training covers the **observed pool**;
  it does not pretend these samples represent every coin or rejected decision.
- Each decision freezes its exact features, original score/reason, entry quote,
  risk distance, policy, cost settings, source identity and release.
- The new target uses `TICK_INTEGER_R_V1`, ATR risk geometry, estimated taker
  fees of 0.05% each way and one basis point of modeled slippage each way.
  Funding is currently zero in this contract. This is **not actual trade PnL**
  and not an exact reproduction of Execution's quote cadence or risk geometry.
- V2 completed-bar labels, actual paper fills and legacy shadow-account results
  are not silently relabelled as detailed tick training examples. Existing main
  paper/shadow ranking feedback and repeated-loss pauses continue separately.

## Which examples can train

The bridge reads `data/observation/live/decision_outcomes.db` and verifies both
decision and outcome digests. It requires the versioned feature and cost
contracts, finite inputs, correct time ordering, resolved chronological trades,
at least two observations, and price coverage near entry and horizon boundaries.
It also independently checks that the stored net result matches the entry,
exit and cost calculation. An event is read only after its full possible path
has had time to finish, avoiding a training set made mainly of fast stopouts.

Interrupted streams, missing aggregate IDs, restart-lost paths, invalid costs,
future receipts, actual execution outcomes and ambiguous/unresolved results
are excluded. Old records without frozen features cannot be reconstructed using
later information. They remain historical records; the new learner must collect
new qualifying examples. No database reset or migration deletion is needed.

## Training and automatic paper replacement

The existing research timer runs the new learner on each check under the same
research command lock, independently of whether a new 96-event coarse epoch is
ready. A detailed-learning error is logged and cannot undo a committed epoch.
There is no model fitting in the quote/WebSocket or execution request threads.

The fitting process reads at most 60,000 recent rows / 3,000 events. All rows in
one event share total training weight one. The old 80/20 chronological split is
used as the starting boundary for training and diagnostic early stopping. The
diagnostic window is extended backward when needed to reserve ten disjoint
events under the row cap; overlapping labels and late
receipts are purged at the boundary, with an additional five-minute separation.
Diagnostic events are spaced four hours five minutes apart. At least 80 purged
training events and 10 diagnostic events are required. Sparse evidence means
waiting; no weaker substitute label is created to make training succeed.

The fitted mean and lower-quantile boosters are frozen with model/data digests,
library versions, settings, release identity and training availability time.
The V3 score is 70% predicted mean and 30% predicted lower quantile; it does not
blend the different bar-based Ridge target into this tick prediction. The fixed
score gate is +0.08R and best-versus-second gap is +0.05R.

After training, collect 20 **new** mature events, each spaced four hours five
minutes apart: ten for validation and ten for the final test. The candidate and
its incumbent comparator are frozen before these observations. If no V3 model
exists, the frozen decision-time Ridge scores provide a clearly labelled
diagnostic comparator. No thresholds are fitted on either future window.

Both windows must satisfy all of these checks:

1. Prediction error beats always predicting zero and is no worse than the
   incumbent comparator, with event-level weights.
2. At least five hypothetical trades qualify under the fixed score/gap gates.
3. Net R is positive after modeled costs and an extra 0.1R-per-trade stress.
4. Net R is no worse and drawdown is no larger than the comparator.
5. No volatility group with at least three selected trades has mean net R at or
   below -1R. Sparse groups remain explicitly unproven. The report also counts
   rejected hypothetical winners and avoided losses without calling them actual
   trades or profit.

The comparison chooses at most one position, skips overlapping opportunities
and uses exactly the same observed candidates for both models. It is conditional
on detailed-path coverage; it cannot calculate missing candidates or duplicate
all hypothetical winners into one portfolio. Actual feedback and live entry
checks can further change paper behaviour. These gates permit a **paper trial**,
not a profitability claim or Research/Paper Champion promotion.

Results are immutable. A failed model leaves the previous model/fallback in use.
A passed model receives a durable paper activation record effective only for
later events. Restart recovery completes a reviewed activation idempotently.
The exact-release rule applies to active V3 models; a new release falls back
until a candidate from that release passes. Compatible old *examples* with this
same frozen contract can still train; their original release IDs are preserved.

Allow several days for future testing after candidate training, and potentially
much longer to collect the initial diagnostic history. Missing data, low
coverage and fewer opportunities extend that time. There is no promised daily
replacement or trade count. Replacement candidates require genuinely newer
evidence beyond the last finalized window.

## Commands on the Learning VPS

Check status without changing permission or models:

```bash
cd "$HOME/Nbot"
.venv/bin/python nbot_admin.py counterfactual-learning-status
```

Perform the same train/evaluate step as the timer, under its exclusive lock:

```bash
.venv/bin/python nbot_admin.py counterfactual-learning-train
```

Restore the previous paper model (or V2 fallback for the first activation):

```bash
.venv/bin/python nbot_admin.py counterfactual-learning-rollback
```

To keep using V2 while investigating, put this in Learning's private `.env`
and restart the relevant Learning services using the mode guide:

```text
NBOT_COUNTERFACTUAL_LEARNING=0
```

Default is `1`. It controls V3 automatic training/use, not trading permission.
`NBOT_SELECTIVE_ML=0` still disables both nonlinear inference paths.
`NBOT_TWO_TIER_RESEARCH=0` stops new detailed collection. These switches do not
delete history. An operator rollback wins over an in-flight candidate compared
against a different active incumbent.

The existing eight Telegram commands remain. `/learning` reports usable detailed
examples, usable rejected opportunities, V3 model activation and review status.
The detailed status command explains exclusions and window metrics. `/recent`
and `/pnl` show the actual main paper account; research net R is separate.

## VPS limits and deployment

The fitting defaults use one thread, shallow trees and bounded history. Existing
`NBOT_ML_THREADS`, `NBOT_ML_TREES` and tree-resource settings apply to fitting.
V3 admission thresholds remain frozen at 0.08R / 0.05R. Set
`NBOT_RESEARCH_MAX_HYPOTHESES=240` for a smaller initial resource test; allowed
values are 1–1,920. Raising research collection to 100 symbols requires a
separate collector configuration and capacity check.

The expanded workload is not yet proven to fit the old 1 GB VPS or its installed
memory ceilings. Prefer the planned 4 CPU / 8 GB machine for the larger profile.
Even there, measure CPU, peak RAM, dropped messages, path exclusions, reconnects,
disk growth and quote age during a sustained paper soak before expanding load.
No real-network resource benchmark is claimed by synthetic regression tests.

Back up all three Observation databases (`observer.db`, `research_memory.db`,
`decision_outcomes.db`) consistently, plus Execution state/history. Models,
reviews, data digests and activation/rollback records live in research memory.
Old notebook entries survive restarts; unfinished precise paths are honestly
marked unresolved because missed prices cannot be recreated.
An unresolved stream gap also causes a fresh research feed to start; old
interrupted hypotheses are invalidated, never repaired by simply clearing a flag.

Testnet and real-money model selectors do not consume V3. Learning cannot arm
real trading, change credentials, create Binance orders or increase the main
position limit. Test the resulting paper account forward for the planned 30 days
and compare drawdown, net returns, repeated losses, abstention and different
market conditions. A passed internal comparison is not a substitute for that
forward experiment.
