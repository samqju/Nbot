# WSS-first execution and high-resolution decision learning

Status: **research branch only**. This design is not active on the running V2
cohort unless this branch is deliberately deployed later.

## Why this exists

NBOT already creates broad 5-minute research labels for eligible symbol/side
rows, but the operational feedback loop is much narrower:

- actual paper trades are few;
- the legacy shadow book is capped at 10 global positions;
- the live observation universe can be as small as 20 symbols in tiny mode;
- 5-minute OHLC hides intrabar chronology, so a candle that touched both +3R
  and -1R cannot prove which happened first;
- rejected decisions do not currently get an execution-like chronological
  replay showing whether the rejection was economically sensible.

The objective of this branch is **not to force more trades**. The objective is
to turn far more decisions into useful experiments while keeping actual capital
authority unchanged.

## Architecture

The branch separates four different jobs.

1. **5-minute signal/research clock** remains the causal decision clock. Existing
   features, candidate rules, Ridge and Selective ML continue to make one frozen
   decision from information available at that event.
2. **WebSocket market truth** becomes the realtime hot path for LIVE paper and
   the bounded LIVE-trade route. bookTicker provides current executable bid/ask.
3. **Decision Outcome Ledger** freezes every eligible symbol/side decision,
   including rejected and lower-ranked candidates, then follows chronological
   Binance aggTrade events for up to four hours.
4. **Selective ML V3 / gate calibration** uses only resolved high-resolution
   counterfactual outcomes. The old 5-minute path remains useful research
   evidence but is not silently substituted for the new V3 target.

The two evidence classes stay explicit:

- **actual execution outcome**: a paper or real order actually entered and was
  managed by Execution;
- **counterfactual research outcome**: a hypothetical decision replay using a
  frozen decision-time entry assumption and the observed Binance market path.

A counterfactual result is never reported as actual PnL.

## Realtime market transport

`nbot/exchange/binance_stream.py` implements a dynamic Binance USD-M WSS
client.

- `<symbol>@bookTicker` is the primary source for fresh bid/ask used by
  Execution.
- `<symbol>@aggTrade` is the chronological trade-price source used by the
  research replay service.
- subscriptions are dynamic and bounded;
- ping/pong, reconnect and resubscription are handled by the stream worker;
- quote freshness is checked before a WSS quote is returned;
- disconnects notify listeners so research paths can be marked incomplete until
  repaired.

REST remains deliberately separate:

- clock/bootstrap validation;
- historical candle/funding collection;
- aggregate-trade backfill after a WSS gap;
- explicit recovery quotes while an already-open position remains protected.

A new entry is not allowed to silently convert an unavailable WSS quote into a
REST entry quote.

## LIVE paper and later LIVE trading

LIVE paper uses the WSS market adapter directly. The existing local
`PaperExchange` still owns simulated capital, fees, slippage and protective
stop state.

The bounded LIVE-trade route uses `MarketRoutedExchange`:

- capital/order methods continue to use the existing authenticated
  `BinanceLiveExchange`;
- public market reads are routed to the WSS market adapter;
- order authority, arm gates, one-position limits and existing risk checks are
  unchanged.

For an open position, Execution waits for the next fresh bookTicker update
instead of sleeping and polling REST. If WSS becomes unavailable, the position
remains protected and a clearly labelled REST recovery quote may be used for
already-open management. That recovery path is not an entry path.

## Why aggTrade is used for rejected-decision learning

A five-minute candle can contain both a large favorable excursion and a stop
crossing. OHLC cannot prove the order.

For example, for a LONG with entry 100 and 1R = 1:

- high 103.2;
- low 98.9.

The candle is compatible with both:

- `100 -> 98.9 -> 103.2`: initial stop first, roughly -1R;
- `100 -> 103.2 -> 98.9`: +1R/+2R/+3R first, trailing protection may lock a
  profit before the reversal.

Chronological aggTrade events resolve that ordering at transaction-event
granularity. They do **not** reconstruct historical order-book depth or promise
an exact historical market fill. Entry/exit costs therefore remain explicit
counterfactual assumptions.

## Decision Outcome Ledger

`nbot/observation/decision_ledger.py` stores one immutable hypothesis for each
eligible event/symbol/side. Multiple setup IDs can be attached to the same
hypothesis for attribution.

Each frozen hypothesis records, among other fields:

- event and decision timestamps;
- symbol and side;
- approved or rejected status;
- rejection blocker;
- raw rank and model scores;
- Ridge, ML mean, lower quantile and conservative score when available;
- matched candidate/setup IDs;
- decision-time bid/ask;
- model digest and feature vector;
- fixed counterfactual entry/risk/cost assumptions.

The replay state tracks:

- entry price;
- current protective stop;
- peak R;
- MFE and MAE;
- +1R/+2R/... crossing timestamps;
- every integer-R stop update;
- last aggregate-trade ID/time;
- WSS-gap and REST-backfill counts.

The current control rule is replayed sequentially:

1. evaluate the active stop on the current aggTrade;
2. if the stop is crossed, seal the exit;
3. otherwise update favorable R;
4. if a new integer-R level was reached, tighten the stop for subsequent
   events.

That chronology is intentionally different from a 5-minute OHLC assumption.

## Gap handling and evidence quality

A WSS disconnect marks active hypotheses with an unresolved gap. The replay
service then:

1. subscribes the symbol again;
2. buffers live events arriving during repair;
3. REST-backfills the recent missing aggTrade interval;
4. replays backfill in chronological order;
5. replays the buffered live events;
6. marks the gap resolved only after the repair succeeds.

Only results with `AGGTRADE_RESOLVED` path quality and complete funding
accounting become Selective ML V3 training targets. An unresolved chronology is
kept for diagnostics but excluded from V3 training.

## Funding and costs

Counterfactual results include:

- decision-time executable side of the quote;
- fixed adverse entry/exit slippage proxy;
- taker fees;
- actual funding events that occurred while the hypothetical position was open.

These assumptions make the target closer to the trading policy NBOT actually
uses, but it remains a research approximation rather than actual execution PnL.

## Broadening the learning universe

Observation breadth is now independently configurable with:

`NBOT_OBSERVATION_UNIVERSE_SIZE`

and candle fetch parallelism with:

`NBOT_OBSERVATION_CANDLE_WORKERS`.

This means a small VPS can be benchmarked at, for example, 100 symbols without
changing the rest of the resource profile. The existing limits still validate
the requested universe.

The example configuration uses 100 as the first benchmark target. Do not assume
that a tiny VPS can safely run 200 symbols plus high-rate aggTrade replay until
CPU, memory, network traffic, Binance request budgets and epoch duration have
been measured.

At 100 symbols and two sides, up to roughly 200 hypotheses can be frozen per
five-minute decision event. These are correlated research rows, not 200
independent trades. Event weighting and chronological validation must continue
to prevent false sample-size inflation.

## Legacy shadow system

The existing shadow book remains intact and separately labelled.

Its 10 global slots continue to serve the old bounded candle-based shadow
experiment. Those slots do **not** cap the new Decision Outcome Ledger because
counterfactual hypotheses do not reserve capital and do not submit orders.

This prevents a migration from accidentally changing the meaning of historical
shadow evidence.

## Selective ML V3

`nbot/observation/selective_ml_v3.py` introduces a new model target based only
on high-resolution resolved counterfactual outcomes.

Important properties:

- no 5-minute target fallback inside V3;
- chronological train/validation split;
- event-level weighting so a wide correlated universe does not pretend to be
  independent experiments;
- mean and lower-quantile LightGBM models;
- eligibility still requires chronological validation MAE to beat an always-zero
  baseline;
- until enough V3 evidence exists, the existing same-release V2 artifact remains
  the explicit fallback.

Actual executed paper outcomes remain a separate higher-quality execution
feedback stream.

## PASS/REJECT policy learning

`nbot/observation/decision_policy.py` evaluates whether fixed confidence and
edge gates are themselves sensible.

It uses only resolved counterfactual rows, preserves chronological separation,
and applies a one-position capacity model while evaluating alternative
thresholds.

The current gates remain the baseline:

- confidence: +0.08R;
- winner/runner edge: +0.05R.

A different gate is only a research recommendation after it improves a later
holdout with minimum support. This branch does not automatically loosen gates
just to manufacture trades.

## Services and storage

The passive research service is:

`nbot-counterfactual-replay.service`

It has no API credentials and no order authority. It reads the Decision Outcome
Ledger, subscribes the symbols with open hypotheses, repairs WSS gaps using
public REST history, and finalizes funding.

The compact durable database is:

`data/observation/live/decision_outcomes.db`

Raw aggTrade events do not need to be retained forever. Once a path has been
resolved and the result sealed, the durable product is the compact decision,
stop trace, path-quality metadata and matured outcome.

## Environment settings

Observation/replay:

- `NBOT_OBSERVATION_UNIVERSE_SIZE`
- `NBOT_OBSERVATION_CANDLE_WORKERS`
- `NBOT_COUNTERFACTUAL_ENABLED`
- `LIVE_PUBLIC_WS_FIRST_EVENT_TIMEOUT_SECONDS`
- `LIVE_PUBLIC_WS_MAX_QUOTE_AGE_MS`
- `LIVE_PUBLIC_WS_MAX_SYMBOLS`
- `LIVE_PUBLIC_REST_TIMEOUT_SECONDS`
- `LIVE_PUBLIC_MAX_CLOCK_SKEW_MS`

Execution uses the same LIVE public WSS settings.

## Safety and deployment boundary

This branch is intentionally separate from the running V2 release. Building and
testing it does not change either VPS.

Before deployment:

- full regression must pass;
- Observation VPS capacity must be benchmarked at the chosen universe size;
- WSS reconnect/gap-repair tests must pass;
- paper open-position management must be tested under disconnect/reconnect;
- Decision Outcome Ledger growth and replay lag must be monitored;
- V3 must accumulate enough high-resolution outcomes before it can replace V2;
- real-money activation remains separately armed and is not enabled by this
  research redesign.

Nothing in this design claims profitability. It expands and improves the
quality of evidence available to the learner.
