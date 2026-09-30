# Learned Testnet V1

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
