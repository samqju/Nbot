# NBOT V2 — Research-First Rebuild Roadmap

Version: 2026-08-16
Foundation generation: `NBOT_V2_FOUNDATION_V1`
Current development baseline: **V2.1 evidence integrity under live validation; V2.2 canonical feature/signal code milestone complete; V2.3 future-path/outcome engine in development; Observer-only; no trading authority**

---

## 1. Mission

Build NBOT so that, before any capital is exposed, it can demonstrate with
point-in-time evidence that it:

1. observes a broad liquid crypto-futures market without a legacy strategy
   deciding what data is allowed into the dataset;
2. records what was knowable at decision time and what happened afterward;
3. compares multiple entry ideas on the same market events;
4. compares multiple exit policies on the same entries;
5. selects opportunities with better after-cost outcomes than weak/unselected
   opportunities on unseen chronological data;
6. preserves more of strong winners without increasing initial capital risk;
7. promotes models/policies only after independent evidence across different
   market conditions;
8. later executes exactly one position through an isolated Execution Worker
   whose safety authority remains final.

The target is **not** “make every trade profitable.” The target is:

> Select good opportunities materially better than bad opportunities, capture
> a high share of available favorable movement, keep losing risk bounded, and
> prove the advantage survives unseen data and real operational constraints.

---

## 2. Non-negotiable V2 principles

### 2.1 The market owns the dataset

The canonical dataset is created from eligible market snapshots, not from
legacy Rule V1 candidates.

A strategy may annotate a snapshot later, but it cannot decide whether that
snapshot exists.

### 2.2 Rule V1 has no inherited authority

The frozen old Rule V1 can return later only as a **benchmark**. It does not:

- gate evidence collection;
- define “truth” labels;
- become the default champion;
- decide which symbols the learner may see;
- receive production authority because it existed first.

### 2.3 Observer first; Execution off

Until the first Research Champion exists:

- Observation uses public LIVE Binance USD-M market data;
- no Execution service is required;
- no SHADOW paper position is required;
- no Testnet order is required;
- no recommendation/control API is required;
- no control token is required.

### 2.4 One canonical evidence database

V2 begins with one SQLite database:

`data/observer.db`

No new JSONL maze, split files, per-phase ledgers, shadow-decision files,
promotion-status files, or canary state files are allowed unless a later phase
proves that SQLite is genuinely insufficient.

### 2.5 Derived features are reproducible, raw evidence is durable

Store raw point-in-time candles and market context. Features such as momentum,
volatility, trend, regime and breadth should normally be derived from canonical
raw data using versioned feature code so feature definitions can improve
without corrupting historical evidence.

### 2.6 No look-ahead

Anything used to select a trade at event T must be knowable at or before T.
Future paths are labels/evaluation evidence only.

### 2.7 Costs are first-class

Evaluation uses after-cost results. At minimum:

- taker fees;
- observed spread;
- explicit slippage assumption;
- exact funding events when the holding period crosses them.

### 2.8 Exit quality is a separate learning problem

“Which trade?” and “How should this trade be managed?” are distinct problems.
Entry and exit authorities are evaluated separately before later combinations
are approved.

### 2.9 Initial risk is not increased to manufacture returns

V2 profitability work must not depend on:

- averaging down;
- widening the initial stop after adverse movement;
- removing protective stops;
- increasing leverage because a model sounds confident;
- opening multiple capital-bearing positions to hide poor selection.

### 2.10 Execution remains isolated when it returns

The old two-worker safety principle survives the rebuild:

- Observation researches and recommends;
- Execution validates and owns capital;
- Execution has its own market truth;
- an open position never requires Observation to remain alive.

---

## 3. Configuration policy

### 3.1 Version-controlled settings

Behavioural settings belong in `nbot/config.py`, including:

- public market endpoint;
- research interval;
- universe size;
- liquidity/spread eligibility limits;
- cost assumptions;
- collection delays/retries;
- later research-policy definitions and evaluation rules.

Changing these settings is a code/configuration change visible in Git.

### 3.2 Secret settings

Secrets never enter `config.py`, Git history, patches, logs or status output.
When Execution networking is rebuilt, an ignored local secret file may contain
only true credentials, for example:

- `TESTNET_API_KEY`
- `TESTNET_API_SECRET`
- `LIVE_API_KEY`
- `LIVE_API_SECRET`
- `OBSERVATION_CONTROL_TOKEN`
- `TELEGRAM_BOT_TOKEN`

The previously pasted control token must be rotated before it is ever reused.

### 3.3 Machine-specific but non-secret settings

If later needed, hostnames, private IPs, Telegram chat/operator IDs or machine
paths should use a small ignored local deployment file rather than turning the
secret environment file into another 200-setting configuration system.

### 3.4 V1 environment migration

The Observation V1 settings are retired as follows:

| V1 setting family | V2 treatment |
|---|---|
| `TRADING_ENV`, `EXECUTION_MODE` on Observer | Removed from Observer. V2 research uses LIVE public data and has no execution mode. |
| Binance public REST URLs | Version-controlled in `nbot/config.py`. |
| Binance public WS URLs | Removed from V2.0; foundation uses simple public REST collection. Add streaming only if evidence shows it is necessary. |
| `OBSERVATION_CONTROL_TOKEN` | Not used until Execution returns; later secret only and must be rotated. |
| `STRATEGY_MODE` | Removed. No strategy has runtime authority in V2.0. |
| shadow/model/canary/promotion flags | Removed from foundation. Reintroduced only as evidence-driven V2 concepts. |
| paper fee/slippage assumptions | Renamed to explicit version-controlled cost units (`TAKER_FEE_RATE`, slippage bps). |
| observation universe settings | Consolidated into one point-in-time universe policy in code. |
| structure/execution universe split | Removed from evidence collection. Strategies cannot gate the raw dataset. |
| virtual-trade capacity settings | Removed. Future-path/policy evaluation will be database driven. |
| log level | Version-controlled initially. |

Execution V1 settings remain archived and unused until the Execution rebuild.
At that stage, behaviour/risk/timeouts move into versioned configuration while
API secrets/tokens remain local secrets.

---

# PHASE V2.0 — Clean Foundation

## Goal

Create the smallest trustworthy Observation system possible.

## Runtime after this phase

```text
Binance LIVE public REST
        |
        v
point-in-time liquid USDT perpetual universe
        |
        v
completed 5-minute candles + spread/liquidity/funding context
        |
        v
atomic SQLite market event
        |
        v
data/observer.db
```

There is no strategy arrow and no execution arrow.

## Foundation schema

### `market_events`

One row represents one completed five-minute decision clock event.

### `candles_5m`

Canonical completed OHLCV/trade-count candle for every selected symbol.

### `market_snapshots`

Point-in-time eligibility/ranking context:

- selection rank;
- 24h quote volume;
- best bid/ask;
- spread percentage;
- current funding-rate context;
- mark price;
- index price.

## Atomicity rule

An event is either completely committed or absent.

If symbol collection fails midway, V2 must not mark a half-populated event as
complete. It retries the same event later.

## V2.0 acceptance criteria

- [ ] Current V1 dataset/models/runtime have already been archived outside the active tree.
- [ ] Old learning/trading modules are absent from active V2 runtime imports.
- [ ] `nbot/config.py` reads no `.env`.
- [ ] Observer starts without API credentials.
- [ ] Observer has no order-writing methods.
- [ ] SQLite uses WAL mode and transactional event writes.
- [ ] Re-running the same event is idempotent.
- [ ] At least 150 eligible symbols are required; normal target is 200.
- [ ] One live validation stores a complete market event.
- [ ] `nbot_admin.py status` shows the event and row counts.
- [ ] Only the V2 Observer service is running.
- [ ] Execution remains stopped.

V2.0 is a **foundation**, not a claim that NBOT can trade profitably.

---

# PHASE V2.1 — Evidence Completeness and Recovery

## Goal

Make the raw evidence layer dependable enough that later research cannot blame
missing/stale data for false results.

## Work

1. Add deterministic gap detection by expected 5-minute close times.
2. Add controlled historical catch-up/backfill after Observer downtime.
3. Record universe membership point-in-time for every event.
4. Validate candle continuity per symbol.
5. Detect duplicate, future, malformed and incomplete candles.
6. Add exact funding-history ingestion for periods that cross funding events.
7. Preserve contemporaneous spread; later add spread-path evidence if needed.
8. Record data-source/server timestamps for clock-skew diagnostics.
9. Add database integrity/checkpoint/backup commands.
10. Add storage-growth telemetry and retention policy only if disk evidence
    proves one is necessary. Do not rotate raw evidence casually.

### Recovery truthfulness rule

Historical recovery must never manufacture decision-time context that Binance no
longer exposes historically. Canonical candles and timestamped funding history
may be recovered. A missed event's historical bid/ask, spread and 24h ranking
must **not** be replaced with values observed later. Candle-only recovery is
therefore explicitly marked context-incomplete and is excluded from later
point-in-time selector training unless a future source can reconstruct that
context honestly.

### Live time-integrity rule

A live event is research-ready only when its decision-time context is genuinely
near the completed candle boundary. V2.1 fails closed when local time differs
from Binance server time by more than 5 seconds, or when the live universe /
spread context finishes more than 30 seconds after the candle close. A late
missed candle may later be recovered only as context-incomplete evidence.

## Required metrics

- expected events;
- complete events;
- missing events;
- incomplete symbols per event;
- candle gaps;
- duplicate conflicts;
- funding coverage;
- spread coverage;
- data age;
- database size/growth rate.

## Acceptance

A multi-day validation must show no unexplained event gaps and no use of future
information in stored decision-time context.

---

# PHASE V2.2 — Canonical Feature and Signal Layer

## Goal

Let many strategies study the same evidence without owning it.

## Architecture

```text
raw market event
      |
      +--> feature set version A
      +--> feature set version B later
      |
      +--> legacy Rule V1 benchmark annotation
      +--> cross-sectional momentum annotation
      +--> time-series momentum annotation
      +--> intraday conditional momentum/reversal annotation
      +--> future research families
```

Signals are annotations. A snapshot with **no signal** remains in the database.
This is essential because the learner needs examples of weak/non-opportunities,
not only trades the old rules already liked.

## Initial feature families

Only features available at decision time may be used:

- returns at frozen lookbacks;
- realized volatility;
- range/ATR-style volatility measures;
- quote-volume/liquidity measures;
- spread;
- BTC state;
- broad market breadth;
- cross-sectional rank/percentile;
- time-of-day/day-of-week;
- funding context;
- structure/trend features if precisely versioned.

## Legacy Rule V1

If reintroduced, its old ten setup families are marked:

`LEGACY_BENCHMARK_ONLY`

They cannot become V2 champion by inheritance.

## V2.2 implementation contract

The first frozen feature version is `CANONICAL_FEATURES_V1`. A row is created
for every research-ready point-in-time snapshot, including rows with incomplete
long-history features and rows for which every signal is inactive. Derived rows
store source-time bounds and deterministic digests. Reusing a feature/signal
version with changed parameters is rejected.

The first transparent signal annotations are:

- `CSM_RANK_1H_4H_V1`;
- `TSMOM_4H_VOL_ADJ_V1`;
- `INTRADAY_CONDITIONAL_MOM_REV_V1`.

These are research annotations only. They have no champion, recommendation or
execution authority. The legacy Rule V1 is intentionally not reconstructed in
this phase; if it returns later, it remains `LEGACY_BENCHMARK_ONLY`.

## Acceptance

- feature generation is deterministic from raw evidence;
- a feature version can be reproduced later;
- no future candle is read;
- every research-ready snapshot gets a canonical feature row;
- incomplete-history/no-signal observations remain present;
- signals never alter the existence of raw snapshots;
- every signal has a version and frozen parameter set;
- stored feature/signal digests reproduce exactly from the database.

---

# PHASE V2.3 — Future Path / Outcome Engine

## Goal

Record what happened after every eligible observation so entry and exit ideas
can be tested against the same objective path.

## Future-path evidence

For each researchable snapshot, calculate or make reproducible:

- forward returns at 5m, 15m, 30m, 1h, 2h, 4h and longer frozen horizons;
- maximum favorable excursion (MFE);
- maximum adverse excursion (MAE);
- time to MFE;
- time to MAE;
- first hit of +0.5R, +1R, +2R, etc. where R is defined by a frozen risk plan;
- first hit of adverse barriers;
- realized volatility after entry;
- exact funding events crossed;
- spread/fee/slippage-adjusted outcomes;
- maximum continuation after any simulated exit.

## Critical distinction

Future evidence is **not** an input feature for the same event. It is a label or
simulation path only.

## V2.3 implementation contract

The first frozen outcome version is `FUTURE_PATH_4H_V1`. It labels only V2.2
`CANONICAL_FEATURES_V1` rows after the full 4-hour future window has matured.
The decision-event close is the entry reference. Forward closes at 5m, 15m,
30m, 1h, 2h and 4h are stored alongside long/short MFE, MAE, excursion timing
and realized future volatility.

The research-only R unit is `ATR14_1X_RESEARCH_R_V1`: one R is exactly the
decision-time ATR14 fraction when that feature exists. Rows without ATR remain
valid future paths, but R-barrier fields are explicitly unavailable. If both a
favorable and adverse R barrier are crossed inside the same 5-minute candle,
the sequence is recorded as `AMBIGUOUS_SAME_CANDLE`; intrabar order is never
invented.

Future candles already present in canonical evidence are reused. If a symbol
leaves the point-in-time observation universe during the 4-hour label window,
only its missing historical Binance klines are cached in `future_candle_cache`.
That table is label-only and V2.2 feature code never reads it. This preserves
future paths without widening or contaminating decision-time evidence.

Cost labels use `TAKER_SPREAD_SLIPPAGE_FUNDING_PROXY_V1`: two taker fees, frozen
entry/exit slippage assumptions, the decision-time observed spread as the
round-trip spread proxy, and the exact timestamped funding events crossed. No
cost-complete path is committed unless funding-history coverage spans the whole
future window. Source-candle and funding digests make later source corrections
auditable and force an explicit rebuild rather than silently changing labels.

Policy-neutral continuation evidence records the maximum favorable extension
after hypothetical exits at each frozen horizon through the 4-hour endpoint.
This gives V2.4 an objective basis for measuring missed winner extension.

## Acceptance

For any historical snapshot we can answer:

> What was known then, and what happened afterward?

without reading an old strategy-specific virtual-trade JSONL file.

---

# PHASE V2.4 — Exit Policy Laboratory / Profit Capture

## Goal

Find exit behaviour that captures more of strong winners without increasing
initial risk.

## Control policy

The old integer-R staircase is retained only as the control:

`INTEGER_R_STEP_CONTROL`

## Initial challenger families

1. **Continuous-R giveback**
   Avoid large discontinuities caused by integer-only R steps.

2. **ATR/volatility trail**
   Trail distance expands/contracts with volatility.

3. **Chandelier-style trail**
   Protect profit from the favorable extreme using volatility distance.

4. **Structure trail**
   Use recent swing/structure invalidation rather than an arbitrary R stair.

5. **Runner policy**
   Give unusually strong trend/expansion trades more room.

6. **Stagnation/time exit**
   Release the one-position slot when a setup fails to develop.

7. **Exhaustion tightening**
   Tighten only after evidence of momentum deterioration/extension.

Do not begin with dozens of variants. Start with a small frozen catalog and
expand only when results identify a specific weakness.

## Profit Capture Efficiency

For winning paths, record at minimum:

`capture_ratio = realized_net_R / MFE_R`

Additional metrics:

- gross R;
- net R;
- MFE R;
- MAE R;
- peak giveback R;
- time to MFE;
- holding time;
- post-exit MFE;
- missed extension R;
- stop distance through time;
- exit reason.

Capture ratio is not optimized alone. A policy that captures 95% only because
it takes tiny profits can still have poor expectancy.

## Exit-policy promotion objective

Primary:

- higher after-cost expectancy;
- acceptable drawdown/tail loss;
- better capture of meaningful winners;
- robustness across regimes/setup families;
- no increased initial risk.

Secondary:

- holding efficiency;
- stagnation reduction;
- reduced unnecessary giveback.

## Acceptance

At least one challenger must beat the integer-R control on unseen chronological
evidence with stable results across independent market events. Otherwise the
control remains the benchmark and no adaptive exit is promoted.

---

# PHASE V2.5 — Entry Selection Learning

## Goal

Teach NBOT to choose the best opportunity from simultaneous alternatives.

## Problem definition

The main problem is not generic binary classification:

> “Will this coin win?”

It is:

> “Given all opportunities available at this market event, which one has the
> highest expected after-cost value under an approved exit policy?”

## Baselines

Compare challengers against transparent baselines:

- random eligible selection;
- highest liquidity only;
- legacy Rule V1 ranking if reconstructed;
- simple cross-sectional momentum;
- simple time-series momentum;
- other frozen research baselines.

## Candidate model objectives

Research may compare:

- expected net R regression;
- pairwise/listwise ranking;
- probability of reaching reward before risk barriers;
- multi-objective ranking that penalizes adverse tail risk.

A model claiming calibrated probabilities must pass calibration/Brier tests.
A pure ranking model is not rejected simply because probability calibration is
irrelevant to its output.

## Main selection metrics

- selected mean/median net R;
- expectancy lift versus benchmark;
- event-level selection regret;
- selected win/loss distribution;
- profit factor where useful;
- drawdown of sequential one-position selections;
- top-vs-bottom predicted bucket outcome separation;
- symbol concentration;
- regime stability;
- performance after all costs.

## “Good better than bad” proof

The model should demonstrate ordered economic separation. For example, on
unseen data:

```text
highest predicted opportunity bucket
        > middle bucket
        > lowest predicted opportunity bucket
```

in after-cost outcome, with enough independent events that the ordering is not
a handful of lucky trades.

## Acceptance

No model becomes Research Champion unless it improves actual economic
selection metrics on untouched chronological data.

---

# PHASE V2.6 — Walk-Forward Research Champion

## Goal

Promote the first model/policy pair worthy of live operational testing.

## Evaluation design

1. Chronological train window.
2. Later validation window.
3. Frozen candidate/parameters.
4. Later untouched test window.
5. Walk-forward repetition across time.
6. Independent market-event clustering so 200 coins in one market shock are
   not treated as 200 independent proofs.
7. Regime breakdowns.
8. Cost stress tests.
9. Symbol/concentration checks.
10. No threshold tuning on the final test set.

## Research Champion gate

Promotion requires evidence for all of these categories:

### Economic advantage

- positive after-cost expectancy on the required unseen evaluation;
- meaningful lift over the strongest transparent benchmark;
- selected opportunities outperform rejected/low-ranked alternatives.

### Exit quality

- approved exit policy beats or justifiably matches control net expectancy;
- winner capture is not systematically poor;
- gains do not come from wider initial risk.

### Reliability

- sufficient independent events;
- no single symbol or narrow date range explains the result;
- no catastrophic regime failure hidden by aggregate averages;
- model behaviour is reproducible from frozen artifacts.

### Data integrity

- no leakage;
- complete required cost/context evidence;
- deterministic dataset version.

Exact numeric promotion thresholds should be frozen only after the V2 baseline
distributions are measured. We should not invent arbitrary AUC/calibration or
trade-count gates first and then force the research problem to fit them.

## Output

The first successful authority becomes:

`RESEARCH_CHAMPION_<version>`

It still has **no order authority**.

---

# PHASE V2.7 — Execution Worker Rebuild

## Goal

Reintroduce only the proven capital-management boundary from the frozen V1
architecture, not the old learning stack.

## Proposal contract

A future proposal should include at least:

- proposal ID;
- environment;
- symbol/direction;
- generated/expires timestamps;
- reference price;
- entry authority/model version;
- exit policy ID/version;
- feature/data generation IDs needed for audit;
- advisory initial risk metadata.

Execution still independently checks:

- current price drift;
- spread;
- balance/margin;
- position state;
- leverage/risk limits;
- proposal expiry/duplication;
- exchange health;
- protective stop feasibility.

## Exit policy execution

The approved exit policy is deterministic/versioned code loaded locally by
Execution before entry. Once a position is open, no Observer request is needed.

## Acceptance

The old architecture's strongest statement must again be true:

> Observation can be powered off while a position is open and Execution still
> manages, protects, reconciles and closes it safely.

---

# PHASE V2.8 — TESTNET TRADE Mechanical Canary

## Decision: use Testnet, but only for mechanics

Testnet is valuable because it exercises real Binance order APIs:

- order submission;
- client-order idempotency;
- stop creation/update/cancel;
- partial/ambiguous order recovery;
- user-stream handling;
- restart reconciliation;
- exchange error paths.

However, Testnet fills/liquidity are **not** treated as evidence that the
strategy is profitable on the real market.

## Acceptance

Repeated controlled Testnet sessions prove:

- one position maximum;
- no duplicate entries;
- stop always protected;
- exit policy state survives restart;
- reconciliation recovers truth;
- Observation outage does not affect an open position;
- failures remain fail-closed.

---

# PHASE V2.9 — LIVE-MARKET Paper Operational Canary

## Why this still exists after Testnet

Testnet proves mechanics; it does not reproduce mainnet opportunity quality,
spread, timing or fills well enough for economic validation.

Therefore the Research Champion is also run against **LIVE public market data
with local paper execution** before real capital.

This stage is not used to discover the strategy. It asks:

> Does the already-proven research authority retain its advantage when the
> real-time proposal, delay, price drift, spread, veto and local exit engine are
> included?

## Compare research vs operational reality

For every proposal:

- reference price vs executable paper price;
- proposal latency;
- entry-price deterioration;
- spread veto;
- execution veto reason;
- simulated research outcome;
- operational paper outcome;
- exit-policy divergence;
- after-cost R difference.

## Acceptance

Operational degradation must remain within frozen tolerances. If it destroys
the research edge, the Research Champion is not promoted further.

---

# PHASE V2.10 — Paper Champion / Long-Term Validation

## Goal

Prove the complete one-position system across enough time and market regimes.

Required regimes/conditions include:

- bullish trend;
- bearish trend;
- sideways/chop;
- low volatility;
- high volatility;
- sudden shocks;
- high/low liquidity;
- Observer restart;
- Execution restart;
- network failure;
- model/policy rollback.

Monitor:

- after-cost expectancy;
- drawdown;
- profit factor;
- winner capture;
- selection regret;
- veto rate/reasons;
- opportunity utilization;
- concentration;
- model drift;
- operational errors.

Only after this stage is the authority called a **Paper Champion**.

---

# PHASE V2.11 — Micro Real Capital

## Goal

Validate the same architecture with tiny real exposure, not redesign it again.

Rules:

- one position maximum;
- very small fixed risk;
- initial stop mandatory;
- no risk increase from ML confidence;
- hard kill switch;
- Execution-only order credentials;
- Observation remains unable to place orders;
- automatic rollback when frozen evidence gates fail;
- human supervision.

---

## 4. What V2 removes from the old active tree

The frozen pre-V2 tag/archive remains the recovery source. The active V2 tree
should not carry phase archaeology as runtime architecture.

Removed/retired categories:

- old `learning/` model/promotion/canary stack;
- old `strategy/` candidate/Rule-V1/virtual-trade stack;
- old `communication/` API until Execution is rebuilt;
- old `execution/`, `risk/`, `engine/`, `state/` runtime from active V2 main;
- phase-numbered scripts;
- phase-numbered test suite;
- phase-numbered implementation documents;
- huge environment-driven `config.py`;
- candidate/outcome/virtual JSONL storage architecture;
- auto-training/promotion/canary services.

Valuable ideas from V1 are **not forgotten**. They are reintroduced from the
frozen tag only when V2 reaches the relevant responsibility and only in a form
that fits the new evidence model.

---

## 5. Target source shape

Do not split files simply because they become a few hundred lines long.
Fragment only at real responsibility boundaries.

Foundation:

```text
Nbot/
├── nbot/
│   ├── __init__.py
│   ├── config.py
│   ├── binance.py
│   ├── db.py
│   └── observer.py
├── run_observation.py
├── nbot_admin.py
├── tests/
├── deploy/v2/
├── docs/NBOT_V2_REBUILD_ROADMAP.md
├── data/                  # ignored runtime data
└── runtime/               # ignored locks/runtime state
```

Later phases should add only a few genuine modules such as:

```text
features.py
signals.py
outcomes.py
policies.py
learning.py
contracts.py
execution.py
```

The target is a small comprehensible system, not another phase-numbered forest.

---

## 6. Final proof that NBOT is better than its bad alternatives

NBOT V2 is not “done” because a model trains successfully or a backtest is
green. The completed system must provide a reproducible evidence report showing:

### Observation proof

- broad point-in-time market coverage;
- complete raw data;
- exact time ordering;
- no strategy-gated dataset.

### Selection proof

On unseen chronological evidence:

- selected opportunities have higher mean/median after-cost R than weak or
  low-ranked alternatives;
- economic outcome improves monotonically enough across predicted quality
  buckets to show the model is actually distinguishing quality;
- event-level selection regret beats transparent baselines;
- the result persists across enough independent events/regimes.

### Exit proof

- approved exit policy improves after-cost expectancy or equivalent economic
  objective versus integer-R control;
- strong winners retain materially more favorable excursion where evidence
  supports doing so;
- drawdown/tail risk is not made unacceptable;
- initial risk is not increased.

### Operational proof

- Testnet proves order mechanics/recovery;
- LIVE paper proves research edge survives real-time delays/spreads/vetoes;
- Execution stays safe with Observation offline;
- duplicate/stale proposals cannot create duplicate exposure.

### Capital proof

Only after the above can micro real capital begin.

When all proofs hold, we can make the defensible statement:

> NBOT observes the market independently of its old rules, learns from complete
> point-in-time evidence, selects stronger opportunities better than weaker
> alternatives on unseen data, uses an evidence-approved exit policy to capture
> profitable movement more efficiently, and executes those decisions through a
> separate fail-closed capital-management worker.

That is the V2 definition of success.
