# Selective ML V1

Selective ML V1 is the nonlinear, abstention-first learner for learned `live-paper`.
It does **not** grant exchange authority, change Execution risk limits, arm real money,
or claim profitability.

## Why it exists

The older learned-paper path used a causal Ridge model, fixed candidate rules and
paper/shadow feedback. Those pieces remain useful, but Ridge is linear and a
fixed rule library cannot learn arbitrary nonlinear interactions between momentum,
volatility, liquidity, BTC context and other market conditions.

Selective ML keeps Ridge as a benchmark and adds bounded LightGBM models on the
Observation/Learning VPS. Execution remains deterministic.

## Decision stack

For every mature five-minute market event the research memory already contains
all eligible symbol/side training rows from the control-policy simulation. The
independent statistical unit is the **market event**, not the coin row. During ML
training every event receives total weight 1, split across its rows. A market
event with 100 symbol/side examples therefore does not count as 100 independent
market observations.

The live-paper decision stack is:

1. Causal research features plus deterministic engineered interaction features.
2. Existing Ridge expected-R score retained as a stable benchmark.
3. LightGBM mean after-cost control-policy R prediction.
4. LightGBM lower-quantile R prediction used as a conservative uncertainty signal.
5. Ridge/LightGBM ensemble mean, with the conservative score capped by the
   lower-quantile prediction.
6. Hard abstention gates:
   - conservative score must exceed the configured minimum;
   - the best symbol/side must be sufficiently better than second place.
7. Existing V4 paper/shadow candidate feedback.
8. A separate LightGBM entry-feasibility model, when enough historical shadow
   fills and drift rejections exist.
9. Existing deterministic Execution risk/order/position checks.

The bot is allowed to produce **NO TRADE**. It is never required to choose the
least-bad opportunity.

## What the nonlinear model sees

V1 reuses the existing causal feature vector and adds deterministic continuous
interactions including ATR-normalized returns, range/ATR, spread/ATR, BTC-relative
returns, short-vs-long momentum curvature, pullback strength, 1h/4h volatility
ratio, breadth change, relative-strength centering, trend/volatility interaction,
liquidity/volatility interaction and signal-alignment strength.

The existing 24 named candidate rules remain useful for interpretability,
paper-feedback attribution and shadow experiments. They are no longer the sole
source of adaptation when Selective ML is active.

V1 deliberately does not pretend that a candlestick name or one fixed threshold
is a discovered market law. A later feature-generation revision can add more
raw-candle/swing/level measurements, but changing the causal feature contract
must be versioned and evaluated rather than silently mixed with old evidence.

## Training target and execution alignment

The primary ML target is:

`CONTROL_POLICY_AFTER_COST_NET_R_NOT_EXECUTION_PNL`

It is produced by the existing research control policy. That policy uses the
same integer-R staircase idea as Execution and includes the research cost model,
so it is more execution-aligned than a plain future price return.

It is still **not actual Execution PnL**: research uses completed-bar simulation
and does not reproduce every live tick, queue, entry delay or fill. Actual
live-paper outcomes remain separate calibration evidence.

This distinction is intentionally stored in every ML-backed proposal.

## Entry-feasibility learning

The existing shadow database already records filled simulations and
`ENTRY_DRIFT_REJECTED` outcomes. Selective ML uses those records to train a
separate binary entry model when there are enough examples of both classes.

Inputs include the opportunity score, spread, side, decision timing, market
context and candidate identity. Cancelled/missing-data shadow records other than
measured drift rejection are not relabelled as trading losses.

When the learned fill probability is below the configured threshold, the
live-paper recommendation abstains.

## Model eligibility

Training uses a chronological holdout. A new nonlinear model is marked eligible
only when its validation mean absolute error is lower than an always-predict-zero
baseline on the same held-out events.

This is a **model usefulness gate, not a profitability proof**.

After that check the bounded history is refit for future live-paper inference.
The model may only serve events after both its training cutoff and its creation
time. Ordinary Ridge/challenger research continues independently.

If no eligible Selective ML artifact is available, learned paper falls back to
the existing Ridge + V4 path. Testnet and live-trade do not automatically use
Selective ML V1.

## Small-VPS defaults

Defaults are intentionally bounded for the existing small Observation VPS:

- one LightGBM training thread;
- at most 600 recent research-memory events;
- at most 60,000 training rows;
- 160 boosting rounds before early stopping;
- maximum tree depth 4;
- at most 15 leaves;
- minimum 80 rows per leaf.

The runtime dependency is isolated in `requirements-ml.txt`. The Execution VPS
does not need LightGBM.

Install on the **Learning VPS only**:

```bash
cd "$HOME/Nbot"
.venv/bin/python -m pip install -r requirements-ml.txt
```

Current Linux LightGBM wheels support common x86-64 and ARM64 servers. If
installation fails, do not bypass the dependency error; leave entries disabled
and investigate the platform.

## Operator commands

Train/update from compact research memory:

```bash
.venv/bin/python nbot_admin.py selective-ml-train
```

Inspect dependency, artifact, holdout error and eligibility:

```bash
.venv/bin/python nbot_admin.py selective-ml-status
```

Force a same-cutoff rebuild only for diagnosis:

```bash
.venv/bin/python nbot_admin.py selective-ml-train --force
```

Normal successful research epochs call `train_if_needed` automatically. An ML
training failure is reported but does not roll back or corrupt an already
committed research epoch.

## Configuration

`NBOT_SELECTIVE_ML=1` is the learned-paper default. Set it to `0` to fall back
to the legacy Ridge/V4 selector without deleting any ML artifact.

Optional bounded tuning variables:

- `NBOT_ML_MAX_EVENTS`
- `NBOT_ML_MAX_ROWS`
- `NBOT_ML_TREES`
- `NBOT_ML_MIN_LEAF`
- `NBOT_ML_THREADS` (1 to 4)
- `NBOT_ML_MIN_LOWER_R`
- `NBOT_ML_MIN_EDGE_GAP_R`
- `NBOT_ML_MIN_FILL_PROB`

Do not loosen gates merely to increase trade count. A quieter bot can be correct.

## Larger Learning VPS

On a 4 CPU / 8 GB Learning VPS, the same architecture can use a longer bounded
history and up to four training threads. Increase one resource dimension at a
time and retain the same chronological/future evaluation rules. Execution does
not need a larger server.

## Safety boundaries

Selective ML V1 cannot:

- change maximum account risk or leverage;
- bypass one-position or daily-risk controls;
- change API credentials;
- arm live trading;
- overwrite Execution stop/reconciliation logic;
- turn a failed model into an eligible one;
- use future labels before their causal maturity;
- claim a profitable strategy from paper or simulated results.

Model artifacts are immutable in compact research memory. Keep the existing
off-VPS backups of research memory, Observation databases and Execution history.
