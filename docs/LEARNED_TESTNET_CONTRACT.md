# Learned Testnet V1

## Current learner addendum - 2026-10-01

Reviewed implementation: `9fff54c`. The authority remains
`TESTNET_LEARNED_EXPERIMENT_V1`; proposal/outcome wire schema versions are unchanged.

- Selector: `CONTEXT_CALIBRATED_RIDGE_V1`.
- Calibration: `CONTEXT_SETUP_CALIBRATION_V1`.
- Challenger family: `CONTEXT_CALIBRATED_RIDGE_ABSTAIN_V1`.
- Evaluator: `V39_CONTEXT_DISJOINT_20_20_V4`.
- Artifact namespace: `v39:context-v4:`. Older evaluations remain historical;
  they are not rewritten as evidence for this learner.
- The accumulated Ridge model is filtered using the latest 20 days of supported
  setup/condition evidence. Samples are event means spaced 49 five-minute bars
  apart, with at least eight samples per supported group. Sparse condition
  evidence falls back to the broader setup, then to Ridge with an explicit
  insufficient-evidence explanation. Scores can only decrease.
- Both evaluation and live inference use the saved calibration. Its caution
  margin is a heuristic, not a win probability. The 14 evaluation gates remain.
- Twenty validation and twenty final-test events need roughly seven days of
  future data plus final label maturity. Collection continues during `EVALUATE_WAIT`.
- Prediction target: `SIMULATED_ATR_R_4H_NOT_EXECUTION_PNL`. Execution keeps its
  fixed-dollar risk and `INTEGER_R_STEP_CONTROL`; neither the research horizon
  nor a simulated R prediction determines realized trade P&L.
- `learning-report` describes training support separately from unseen evaluation
  results and explains recorded rejection reasons. It cannot recover lost data.

See [small-VPS operation](SMALL_VPS_LEARNER.md) and the
[documentation index](DOCUMENTATION_INDEX.md). Resource limits change collection
capacity, not evaluation thresholds or order authority.

## Execution and evidence invariants

This additive V3 contract connects the existing learner to autonomous Testnet
execution. It does not enable LIVE orders or grant a Research/Paper Champion.

- LIVE public evidence remains the only training source. Testnet outcomes are
  operational evidence and never enter the LIVE training labels.
- The existing isolated epoch/challenger jobs train immutable causal models.
  Testnet may exercise an unproven challenger, explicitly labelled experimental.
- Use the newest non-rejected challenger whose model was available before the
  decision event, trained on fully mature labels with the current release and
  feature/statistics definitions. Reject corrupt or incompatible artifacts.
- Compute the same features and signals used during training on the newest
  complete LIVE event. Rank both sides of symbols also present in the matching
  fresh Testnet event. A non-positive best prediction means NO_TRADE.
- Reference prices come from Testnet, and Execution independently checks current
  Testnet prices, spread, balance, risk, stop protection and arm/session gates.
- Freeze one decision per event on disk. Refresh/restart/model replacement cannot
  change an already-issued decision or extend its expiry.
- Missing models, incomplete history, mismatched clocks/events, rejected models,
  stale data and inference failures block entries. No hash/random fallback.
- Models and inference stay on Observation. Execution receives a small versioned
  proposal with model/source identity and retains sole order authority.
- Existing operational canaries remain explicit mechanical test tools. Normal
  Testnet control uses the learned route. LIVE/PAPER behavior is unchanged.
- Automatic Testnet model replacement does not mutate research promotion records
  or relax their evaluation rules. Failed challengers cease being eligible;
  an older non-rejected compatible model may be used, otherwise stay flat.
- A committed epoch may finish its challenger transition by evaluating an older
  active frozen model. Its training cutoff must not exceed the epoch end. Waiting
  for a final test window must never prevent the next epoch from adding evidence.

Completion evidence must distinguish automated tests, deployment, and actual
authenticated Binance Testnet acceptance. New servers and keys are operator setup.

For generations starting after the historical V3.9.4 calibration cutoff, that
specific regime report returns `UNAVAILABLE_HISTORICAL_CALIBRATION`, with no
execution or promotion authority and an unsuccessful audit. Independent learning
epochs continue. Historical generations retain all calibration checks; an
existing regime contract in an incompatible new generation raises an error.
