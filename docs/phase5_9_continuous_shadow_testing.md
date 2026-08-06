# Phase 5.9 — Continuous champion–challenger shadow testing

Phase 5.9 separates virtual decision testing from paper-position availability.
The trading engine continues to feed candles and complete virtual outcomes while
paper exposure is open. A five-minute decision-cycle coordinator releases one
batch only after the configured share of the observation universe has rolled to
the new candle bucket.

For each valid cycle the bot records:

- the permanent rule benchmark;
- the current champion (rules initially, a registered model later);
- one registered `SHADOW` challenger;
- top-one and equal-weight top-K selections;
- agreement, disagreement, and overlap metadata;
- the market-event ID and market regime attached to each selection.

All selections are virtual. The Phase 5.9 path has `runtime_effect=NONE`, does not
change paper ranking, and has no real-order authority.

## Evidence report

Run:

```bash
python3 -m scripts.learning.evaluate_shadow_decisions
```

The evaluator joins baseline `VIRTUAL_TRADE` outcomes to each selection and
reports both raw completed batches and independent market-event results. It
uses `net_exit_r`, so fees and configured slippage estimates are included.
Top-one and top-K portfolios are evaluated separately. A top-K portfolio is
included only when every selected candidate has a completed outcome.

The report includes average net R, gross R, estimated costs, win rate, maximum
drawdown, maximum losing streak, pairwise agreement/disagreement performance,
and regime breakdowns by market regime, trend, volatility, direction, and
pattern.

Phase 5.9 cannot promote a model. Promotion remains a later governance phase.
