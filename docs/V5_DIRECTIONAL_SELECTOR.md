# NBOT V5 directional selector — experimental contract

This selector is **pure research preparation**, not a trading engine or model.
It cannot open an exchange order, initiate WSS streams, create an evidence
database, score a trade or install a service.

## Why this is different from V4

- Only a **confirmed direction-specific** structure qualifies: break beyond
  the previous 20 fully closed bars with directional candle body and volume,
  recovery after a moving-average trend pullback, or rejection of a 20-bar
  boundary during a measured range. No `MODEL_ONLY` filler entries.
- A side is evaluated independently; a LONG signal does not imply SHORT.
- A candidate can be SCANNED, REJECTED, QUALIFIED, SELECTED or EXPLORATORY.
  Every evaluation reports its reason, regime and feature digest.
- **100 is the total concurrent research cap**, not a required count.
  Empty qualification produces no qualified entry. An explicit active
  (symbol,side) pair is never entered twice.
- At most **four** separately labeled, near-miss exploratory observations can
  be selected from otherwise safe candidates, never from a bad-data or
  excessive-cost rejection. Uniform deterministic min-hash sampling records
  the per-event inclusion probability when eligible capacity permits.
  Exploration is not a profitable trade recommendation.
- Qualifying priority currently favors lower modeled roundtrip cost in R,
  then collector universe rank, then stable identity. It is NOT a validated
  profitability score and does not use old fitted V4 models.

## Required point-in-time evidence

`v5_market_reader.read_completed_event` opens a caller-specified collector
SQLite database in **read-only** mode. It checks the completed event,
LIVE_POINT_IN_TIME evidence, complete context, point-in-time universe
membership, snapshot and candle chronology. It loads 49 contiguous 5-minute
candles ending at the requested completed event. No future candle is accessed.

**Instrument trading rules** (tick size, quantity step, minimum notional,
TRADING status and acquisition timestamp) are **required** to pass
qualification, but are NOT stored in the current market snapshots. A future
read-only exchange-info metadata bridge must supply them at or before the
decision clock. Without metadata, the selector fails closed. This release
does not assert that full depth-of-book information exists; volume and spread
are provisional proxies. A separate, causal depth check remains a task.

## Frozen prospective thresholds (not historically optimized)

- 24h quote volume >= **$3 million**; spread <= **0.15%** of mid-price.
- Modelled roundtrip cost-to-risk estimate <= **0.30R**. This
  initial filter includes the current bid/ask spread plus frozen fee/slippage
  estimates (0.05% taker fee and 0.01% slippage **per side**). It is a
  conservative *entry-quality budget*, not a second charge in accounting.
- Snapshot absolute funding rate <= **0.20%** and finite. Funding snapshot
  is **not** a known actual charge. Actual settlement costs require full
  evidence later under Milestone 4.
- Market snapshot freshness <= **120 seconds**; instrument metadata freshness
  <= **24 hours**; ATR-sized initial stop at least **3 price ticks** away.
- Trend uses 8/21 EMAs of known closed bars; trend regime if the EMA
  separation is at least 0.35 x ATR; range if <= 0.20 x ATR,
  otherwise UNKNOWN. This is a provisional classifier.
- Body/volume thresholds and exact entry definitions live in
  `v5_selection.py` and are frozen under VERSION. They must be
  prospectively validated; these numbers are not promises of profitability.

## Known limitations before a runtime can be built

- No network or exchange-info bridge, no verified depth, no live WSS entry
  path and no replay/state persistence wiring in this milestone.
- No empirical evidence these entry triggers generate positive R. V4
  performance motivates study, but V4 completed outcomes do not train V5.
- The sampling probability describes the deterministic candidate set
  under a fixed active/side/capacity state. Later selection bias, symbol
  clusters and overlapping entry times require separate sensitivity tests.
- Multiple active positions from correlated symbols are not yet constrained
  by an independently measured correlation matrix; an exposure-diversity
  check is needed before any actual selection pipeline is activated.
- All outcome paths must still have a frozen -1R initial stop, true fees
  and funding, and verified chronological evidence (future milestones).
- No deployment or V4 service changes are made by this PR.

## Future acceptance

Test counterexamples and rejected reasons, verify source data path purity,
add point-in-time instrument metadata and depth checks, simulate WSS
paired-exit policies, validate cost gates and entry signal quality on
**new** forward observations, then update the master roadmap before
considering V5 deployment.


## Milestone 2 quality bridge — prospective public snapshots (PR #34)

The V2 selector contract requires **two independent, time-stamped inputs**:
(1) exchangeInfo instrument rules and (2) public order-book depth. The
collector's 24h volume and spread do NOT prove an order can be filled.

A credential-free public Binance USD-M client may request exchangeInfo and
depth, recording local started/finished times and SHA-256 source digests.
`PRICE_FILTER.tickSize`, `LOT_SIZE.stepSize/minQty/maxQty`,
`MIN_NOTIONAL.notional`, TRADING status and USDT PERPETUAL contract identity
are validated; unsupported/missing filter fields fail closed.

The depth checker verifies sorted, non-crossed bid/ask ladders, positive
quantities, quote consistency within about one price tick, no future/stale
capture or out-of-order capture relative to the market snapshot, and at
least a hypothetical $100 USDT probe on **both** entry and exit sides,
including a maximum 10bp estimated sweep impact. This is not a guaranteed
fill, and is a **prototype threshold**, not proven profitability.

The collector itself is NOT modified. V5 still lacks a scheduled capture
service, persistent quality snapshot ledger, portfolio correlation exposure
limit, funding settlement bridge and trade replay. V5 cannot yet operate
as a live research factory. Old V4 observations cannot be retroactively
endowed with depth or exchange rules captured later.
