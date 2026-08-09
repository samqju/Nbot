# Phase 5.10 — Automatic Promotion Controller

## Purpose

Phase 5.10 turns the Phase 5.9 shadow evidence report into an automatic,
fail-closed governance decision for the currently registered shadow
challenger.

The controller runs in a separate low-priority process. It is not called from
the WebSocket loop, stop supervision, paper-position management, or state
persistence.

## Evidence isolation

Promotion evidence is filtered to the exact pair being tested:

- current `SHADOW` challenger model ID;
- current champion model ID;
- current environment;
- `VIRTUAL_TRADE` after-cost outcomes.

Evidence from an older challenger or a different champion is never mixed with
the current promotion decision.

## Default gates

- matched top-one candidate outcomes: at least 1,000;
- independent market-event comparisons: at least 150;
- paired disagreement events: at least 75;
- average after-cost R lift over champion: at least +0.10R;
- challenger after-cost expectancy: strictly positive;
- challenger win-rate deterioration: no more than 2 percentage points;
- registered test Brier score: no more than 0.25;
- registered test calibration gap: no more than 0.10;
- registered maximum feature PSI: no more than 0.25;
- recent independent-event expectancy: strictly positive.

The recent period defaults to the newest 30 independent market events.
Brier, calibration, PSI, checksum, artifact path, and dataset fingerprint come
from the immutable Phase 5.8 registry record. Forward R, win rate, and recent
expectancy come from Phase 5.9 virtual decisions and completed outcomes.

## Outcomes

### HOLD

There is too little independent evidence to make a reliable decision.
The model remains `SHADOW`.

### EXTEND_SHADOW

At least half of each evidence-count requirement is present and the early
forward results remain positive and safe, or the full counts exist but a
positive model has not yet passed every promotion threshold.
The model remains `SHADOW`.

### REJECT

The artifact or model-quality record is unsafe, or sufficient forward evidence
shows negative lift, non-positive after-cost expectancy, non-positive recent
expectancy, or excessive win-rate deterioration.
The model becomes `REJECTED` and the shadow slot is cleared atomically.

### PROMOTE_TO_PAPER_CANARY

Every configured gate passes. The model becomes `PAPER_CANARY`, the shadow slot
is cleared, and `current_paper_canary_model_id` is written in the same atomic
registry replacement.

Phase 5.10 reserves the paper-canary registry slot only. It deliberately does
not alter candidate routing or create paper orders. Canary order allocation,
risk limits, and rollback supervision require their own explicit execution
phase. The current champion remains unchanged and real-order authority remains
`NONE`.

## Atomicity and failure behavior

Before canary assignment, the controller reopens the registered artifact and
verifies:

- file existence;
- SHA-256 checksum;
- pickle readability;
- supported artifact family;
- matching model ID;
- `runtime_activation=DISABLED`.

Registry changes use a temporary file, `fsync`, and `os.replace`. If the final
replace fails, the old registry remains authoritative and no canary slot is
created. A status/report-write failure cannot partially write the registry.

## Automatic process

The controller is run by:

```bash
python3 -m scripts.learning.promotion_controller --watch
```

The poll interval only checks for newly completed evidence. A timer alone does
not promote a model. Repeated checks with no new completed pairs do not rewrite
the registry.

The included user service is:

```text
deploy/observation/install_services.py (canonical Phase 6A.0+ deployment; see deploy/README.md)
```

## Files

Environment-specific defaults:

```text
data/promotion_controller_status_live.json
data/promotion_controller_status_testnet.json
data/promotion_evidence_report_live.json
data/promotion_evidence_report_testnet.json
runtime/AUTOMATIC_PROMOTION_LIVE.lock
runtime/AUTOMATIC_PROMOTION_TESTNET.lock
```

The shared model registry remains:

```text
models/model_registry_live.json
models/model_registry_testnet.json
```
