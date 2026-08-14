# Phase 7.5C.3 — Challenger diagnostics retention and regime-aware PSI

## Purpose

Challenger #1 proved two separate issues in the learning-validation plumbing:

1. Rejected-model storage pruning correctly reclaimed the large model/snapshot
   workspace, but it also removed the detailed calibration-bin and per-feature
   PSI report that explained the rejection.
2. The single `max_feature_psi` gate treated explicit market-regime descriptor
   movement as ordinary model-input instability. A legitimate SIDEWAYS ->
   BEARISH transition could therefore fail PSI by itself even when the model's
   candidate/score/liquidity inputs remained stable.

This hardening patch fixes those two issues without granting any trading or
paper authority and without weakening predictive-quality gates.

## Diagnostic retention

Each completed challenger now stores a compact `evaluation_diagnostics`
object in the model registry before rejected-model pruning runs. It retains:

- validation and test row counts;
- all validation/test calibration bins and max gaps;
- per-feature PSI, severity, validation/test means, and drift scope;
- all/stability/regime-context PSI maxima and top feature names.

The large snapshot, model artifacts, split JSONL files, and training workspace
are still pruned for rejected challengers exactly as before.

## Drift scopes

PSI is still measured for every feature that the evaluator previously
measured. The patch only separates how that evidence is interpreted.

### MODEL_STABILITY_GATE

These features remain subject to the configured PSI limit:

- all base candidate features;
- `rule_score` and `final_score`;
- `ctx_market_coverage`;
- `ctx_spread_pct`;
- `ctx_log10_quote_volume_usd`.

Drift in these inputs can indicate candidate-distribution, data-quality, or
tradability instability and therefore remains a fail-closed gate.

### REGIME_CONTEXT_DIAGNOSTIC

These features remain measured and retained, but their PSI is diagnostic rather
than an automatic rejection reason:

- BTC 24h change;
- broad-market advancing/declining/unchanged fractions;
- broad-market median change and median absolute change;
- market-regime one-hot features;
- volatility-regime one-hot features;
- BTC-regime one-hot features.

These fields intentionally describe changing market conditions. A regime shift
is not, by itself, proof that a model is invalid. The model must instead prove
that its predictive performance survives the shift.

## Gates that remain unchanged

The patch does not relax:

- sealed-test ROC AUC;
- Brier score;
- calibration gap;
- stability-feature PSI threshold;
- Phase 7.5 independent-event requirements;
- disagreement-event requirements;
- expectancy/lift requirements;
- explicit regime-robustness requirements;
- the Phase-7 paper-promotion lock;
- real-order authority (`NONE`).

A challenger that enters a different market regime and loses predictive power
still fails through its performance/calibration/regime-robustness evidence.

## Compatibility

Old registry records that only contain `max_feature_psi` remain valid. The
training and promotion controllers fall back to the legacy field when the new
`max_stability_feature_psi` field is absent.
