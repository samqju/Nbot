# Phase 5.12 — Complete Automatic Rollback

## Mission

Phase 5.12 keeps the previously proven paper champion immediately available and
removes an unsafe canary or model paper champion without requiring a human to
diagnose the cause first.

The controller runs outside the trading engine. It may alter only the atomic
model registry. It cannot submit Binance orders and every decision records:

```text
execution_mode = SHADOW
real_order_authority = NONE
```

## Evidence sources

The controller joins append-only and immutable evidence:

- local paper trades for after-cost expectancy, drawdown and losing streak;
- deterministic paper-routing decisions for prediction health and probability;
- baseline virtual outcomes for paired champion-relative comparison;
- candidate observations for fresh runtime features;
- the immutable training snapshot referenced by the model registry for PSI;
- the registered artifact and SHA-256 checksum for model integrity.

Only evidence created after the model entered its current canary or champion
role is used for runtime rollback.

## Automatic rollback triggers

A rollback is required when any applicable gate fails:

- model artifact missing, corrupt, unsupported or checksum-invalid;
- required feature missing;
- feature-schema mismatch between registry, artifact and runtime;
- prediction failures exceed the configured count or rate;
- actual paper maximum drawdown exceeds the limit;
- actual paper losing streak exceeds the limit;
- overall or recent after-cost paper expectancy falls below its limit;
- independent paired virtual outcomes materially underperform the benchmark;
- forward Brier score or calibration gap deteriorates beyond its limit;
- fresh feature PSI exceeds its limit.

Artifact, required-feature and schema failures are fail-closed immediately.
Statistical gates require their configured minimum evidence.

## Canary rollback

A staged canary rollback atomically:

```text
PAPER_CANARY -> ROLLED_BACK
current_paper_canary_model_id -> null
paper authority -> current champion
```

The current champion is unchanged. If the champion is a model, model-champion
paper selection continues. If the champion is `RULE_SYSTEM_V1`, routing returns
to rules only.

## Paper-champion rollback

A model paper champion rollback atomically:

```text
PAPER_CHAMPION -> ROLLED_BACK
current_champion_model_id -> retained previous champion
```

The retained previous model artifact is checksum-validated before restoration.
If the retained model is unavailable, the fail-safe restoration target is the
permanent `RULE_SYSTEM_V1` benchmark.

A canary slot may remain present while its champion is restored; on the next
controller cycle it is evaluated against the restored champion.

## Atomicity

Registry changes use a temporary file, `fsync`, and `os.replace`. A failed write
leaves the old registry intact. Rollback history records the disabled model,
its role, restored champion, reason codes and `real_order_authority=NONE`.

## Automatic operation

The existing service performs both staged canary governance and Phase 5.12
rollback checks:

```text
nbot-paper-canary-controller.service
```

Manual controller runs are diagnostics only. Normal Phase 6 operation will use
the continuous service.
