# Selective ML V2

Selective ML V2 is the nonlinear, abstention-first learner for learned `live-paper`.
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
4. LightGBM 25th-percentile R prediction used as a conservative uncertainty signal.
5. Ridge/LightGBM ensemble mean, then a risk-adjusted score made from 70% ensemble
   mean and 30% lower-quantile prediction. This avoids demanding an unrealistic
   75%+ winning distribution while still penalizing weak downside estimates.
6. Hard abstention gates:
   - conservative score must exceed the configured minimum;
   - the best symbol/side must be sufficiently better than second place.
7. Existing paper/shadow outcome feedback and loss cooldowns.
8. Realtime Execution entry checks using the current executable quote:
   proposal freshness, quote freshness, spread, reference-price drift, margin,
   protective-stop feasibility and a final quote/drift recheck.
9. Market entry followed by post-fill notional, slippage, stop-identity and
   risk validation.

The old V1 binary "fill probability" gate is removed. It was trained from the
next five-minute candle and therefore measured delayed next-bar drift, not
whether an immediate market order could be entered safely.

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

## Realtime entry feasibility

Entry feasibility is owned by Execution, not by a five-minute prediction model.

After Observation has passed the ML confidence and edge gates and produced a
fresh proposal, Execution checks current market truth immediately before the
market-order-capable call. The current safety policy checks quote age, spread,
proposal/reference drift, account margin and protective-stop feasibility, then
takes a final quote and repeats the freshness/drift checks. After a proven fill,
post-fill notional, slippage and risk limits remain fail-closed.

This aligns the gate with the actual live-paper execution path. A fast-moving
asset is not rejected merely because the *next five-minute candle* opens far
from the decision price. It can still be rejected if it moves too far during
the real decision-to-execution interval.

Shadow `ENTRY_DRIFT_REJECTED` records are retained as **next-bar signal-decay
research telemetry**. They do not train a binary fill model and do not lower
paper ranking. This preserves the historical evidence without confusing
five-minute signal decay with immediate market-order feasibility.

Learned live-paper outcomes also retain execution-entry telemetry such as
proposal-to-fill latency and reference-to-fill deterioration. That evidence can
support a future calibrated execution-quality model after enough unbiased
examples exist; V2 does not manufacture such a probability from sparse data.

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
Selective ML V2.

## Small-VPS defaults

Defaults are intentionally bounded for the existing small Observation VPS:

- one LightGBM training thread;
- at most 600 recent research-memory events;
- at most 60,000 training rows;
- 160 boosting rounds before early stopping;
- maximum tree depth 4;
- at most 15 leaves;
- minimum 80 rows per leaf;
- minimum risk-adjusted score +0.08R;
- minimum best-vs-second-best gap +0.05R.

There is no learned fill-probability threshold in V2. Execution's existing
realtime safety limits remain authoritative.

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

Do not loosen gates merely to increase trade count. A quieter bot can be correct.

## Larger Learning VPS

On a 4 CPU / 8 GB Learning VPS, the same architecture can use a longer bounded
history and up to four training threads. Increase one resource dimension at a
time and retain the same chronological/future evaluation rules. Execution does
not need a larger server.

## Safety boundaries

Selective ML V2 cannot:

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
