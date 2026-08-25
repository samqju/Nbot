# V3.9.4 Market Regime Evidence Contract

Version: `V39_MARKET_REGIME_EVIDENCE_V1`

V3.9.4 adds an Observation-only, immutable companion report for each finalized
V3.9 challenger window. It does **not** rewrite V3.9.1 challenger evaluations,
V3.9.3 rolling reports, Research Champion state, Paper Champion state, or any
Execution authority.

## Freeze boundary

The taxonomy was frozen from the explicit pre-cutoff audit of the permanent
compact research memory through market event `1787581200000`:

- 480 pre-cutoff events;
- zero post-cutoff events were used when the thresholds were chosen;
- database quick check was `ok` and foreign-key errors were zero;
- broad-market feature invariance errors were zero.

That cutoff is also the V3.9.2/.3 eligibility-epoch cutoff. The already-finalized
first challenger window remains descriptive/audit history only. The taxonomy is
therefore frozen before the first eligibility-counting challenger receives
future evaluation evidence.

## Frozen taxonomy

### Trend

Use three independent broad-market votes: BTC 1h return, median-market 1h
return, and 1h positive breadth. A bullish or bearish trend requires at least
two aligned votes; otherwise the event is `SIDEWAYS_CHOP`.

The bullish/bearish thresholds are the audited pre-cutoff 75th/25th percentile
values.

### Volatility

`LOW`, `NORMAL`, and `HIGH` use the audited event-median realized-volatility
25th/75th percentiles. `SHOCK` is assigned when event-median realized volatility
reaches the audited 95th percentile or the absolute median-market 5m move is at
least 0.35%.

### Breadth

`RISK_OFF`, `BALANCED`, and `RISK_ON` use the audited 25th/75th percentiles of
1h positive breadth.

### Funding

The entire calibration cohort had the same event-median funding value
(`0.00005`), so V3.9.4 does not manufacture empirical low/high buckets from
nonexistent variation. The semantic frozen bands are:

- `LOW`: median funding <= 0;
- `NORMAL`: 0 < median funding < 0.0001;
- `HIGH`: median funding >= 0.0001.

The contract explicitly reports `INSUFFICIENT_VARIATION` until different
funding environments actually occur.

### Liquidity

Liquidity uses both quote volume and spread. `HIGH` requires audited upper-
quartile quote volume together with lower-quartile spread. `LOW` requires
lower-quartile quote volume together with upper-quartile spread. Other events
are `NORMAL`.

## Anti-leakage rule

Regime distributions for the currently active challenger are not persisted or
shown. A regime companion report is generated only after its 20-event untouched
final test is already immutable. This prevents V3.9.4 monitoring from becoming
a human tuning channel during an active final window.

## Coverage rule

Coverage is monitored **as available**. Missing regimes are reported as missing;
NBOT must never synthesize a regime or weaken a threshold to manufacture
coverage. Market-regime coverage is evidence for later long-term Paper Champion
judgment, not automatic promotion authority.

Authority remains `RESEARCH_ONLY_NO_EXECUTION`.
