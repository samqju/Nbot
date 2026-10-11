# NBOT V4 research factory

V4 is a clean model lineage. Existing V2/V3 databases and artifacts are not
training inputs for V4 and are not deleted.

## Research book

- Capacity: **100** concurrent virtual trades.
- Entry/refill cadence: completed **5-minute candle** boundaries only.
- Exit management: public Binance aggTrade WSS, continuously.
- Duplicate rule: at most one open trade for a given `symbol + side`.
  LONG and SHORT on the same symbol may coexist.
- Policy: tick-level integer-R trailing policy, four-hour maximum horizon.
- No exchange credentials and no order authority.

If 100 trades are open and 20 resolve before the next 5-minute boundary, no
replacement is opened immediately. At the next boundary V4 counts 80 open
positions and fills at most 20 fresh eligible candidates.

## Bootstrap research selection

Before the first V4 model exists, V4 does not borrow V2/V3 scores. Canonical
point-in-time features and candidate-structure tags are used. Recognized
structures are prioritized, then structure agreement and point-in-time universe
rank; deterministic hashing only breaks exact ties.

## Generation cadence

Every **1,000 resolved V4 virtual research trades** closes a training batch.
Training is a separate resource-limited process and never runs in the WSS
research process.

Generation 1 is a provisional baseline candidate. Later generations must pass
protected held-out research qualification before entering paper Champion vs
Challenger evaluation.

## Champion vs Challenger

The primary checkpoint is **100 completed strategy paper trades per model**.
The eventual promotion gate must also require adequate elapsed time/regime
coverage and risk/after-cost quality; reaching trade 100 alone does not grant
promotion.

During a Champion-vs-Challenger exam the Challenger is frozen. Research
continues accumulating data for later generations.

## Storage

V4 uses a fresh namespace:

- `data/observation/v4/research_ledger.db`
- `data/observation/v4/research_meta.db`
- `data/observation/v4/generations.db`

Old V2/V3 evidence is left untouched for audit and rollback.

## Authority

All V4 research/model artifacts are `order_authority=NONE`. Real order
placement remains an Execution-VPS concern and requires a separately proven and
explicitly authorized live Champion.
