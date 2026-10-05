# NBOT V3.9 Research Governance Contract

Current applicability (2026-10-05): the eligibility gates below are preserved. The current learner/evaluator has its own `v39:context-v4:`
namespace; historical evaluations must not be relabeled or mixed into new-family
proof. Its setup filter is not a probability model and does not replace the
frozen market-regime companion. See [current lineage](EVIDENCE_LINEAGE_CONTRACT.md)
and [explicit promotion](V3_9_RESEARCH_CHAMPION_PROMOTION_CONTRACT.md).
The bounded operator-authorized `live-trade` trial is separate from this
automatic Champion-governance path and does not satisfy these gates. Current
mode commands are documented in [ALL_MODES_COMMANDS.md](ALL_MODES_COMMANDS.md).

**Contract version:** `V39_RESEARCH_CHAMPION_ELIGIBILITY_V1`
**Registry version:** `V39_MODEL_REGISTRY_V1`
**Rolling reevaluation version:** `V39_ROLLING_REEVALUATION_V1`
**Authority:** `RESEARCH_ONLY_NO_EXECUTION`

This contract implements the V3.9.2 model-registry/artifact boundary and the
V3.9.3 rolling Champion/challenger reevaluation boundary on permanent compact
research memory. If immutable challenger windows already exist when governance
is first activated, they remain visible as historical rolling evidence but are
excluded from Research Champion eligibility. The active unevaluated challenger
at governance activation becomes the immutable eligibility-epoch start.

## Immutable artifact rule

Observation owns all model artifacts. Every V3.9 model artifact is stored both
as an immutable compact-memory record and as canonical JSON under the local
Observation data tree. The file SHA-256 must equal the compact-memory artifact
digest. Execution never reads this directory and no artifact creates order
authority.

The registry records immutable model metadata including training cutoff, event
and row counts, feature/target/policy versions, hyperparameters, source digests,
model digest, release SHA, artifact filename and checksum.

## Challenger state

A challenger registration is immutable. Its current state is derived from the
presence/absence of its immutable final evaluation:

- no final evaluation -> `ACTIVE_WAITING_FUTURE_EVIDENCE`;
- final PASS -> `PASS_RESEARCH_GATE`;
- final REJECT -> `REJECT_RESEARCH_GATE`.

Historical final-test windows are never extended, overwritten, or reinterpreted
when later evidence arrives.

## Rolling reevaluation metrics

Every finalized challenger window gets an immutable rolling report containing:

- after-cost mean/median expectancy and 95% confidence interval;
- paired lift and 95% confidence interval;
- drawdown and profit factor;
- trade utilization / abstention;
- winner capture;
- selection regret;
- symbol and UTC-date concentration;
- direction and volatility regime summaries;
- 1x/1.5x/2x cost stress;
- model-training distribution drift using
  `TRAINING_STANDARDIZED_MEAN_SHIFT_RMS_V1`;
- calibration/Brier marked not applicable for Ridge expected-R regression;
- LIVE/PAPER operational degradation marked deferred until a Research Champion
  has actual LIVE/PAPER recommendation authority.

## Frozen Research Champion review eligibility

The first governance sync freezes an immutable eligibility epoch at the active
unevaluated challenger training cutoff. Final windows with earlier training
cutoffs remain audit history but cannot contribute to promotion eligibility.
This prevents a result observed before this contract existed from being
retroactively counted toward a promotion gate.

This patch does **not** automatically promote a model. It only declares a
challenger family eligible for a later explicit Research Champion review when
all of the following are true for the latest eligible chronological windows:

1. three consecutive immutable windows are `PASS_RESEARCH_GATE`;
2. at least 60 untouched final-test market events are included;
3. at least 15 simulated selected trade events occurred (abstentions do not count;
   this research gate counts simulated decisions, not Binance fills);
4. the considered test evidence spans at least 48 hours;
5. the test evidence covers at least three distinct UTC dates;
6. at least two model-to-model drift transitions were measured;
7. weighted after-cost mean R across the considered windows is positive;
8. weighted paired lift versus the frozen validation-selected baselines is
   positive;
9. every considered window remains positive under 2x cost stress;
10. every historical final-test record remains immutable.

Meeting these gates returns only:

`ELIGIBLE_FOR_RESEARCH_CHAMPION_REVIEW`

It does **not** change the Champion pointer.

## Champion and rollback state

V3.9.2 initializes an append-only Champion-pointer genesis record with no
Research Champion and an append-only rollback-state genesis record with rollback
disabled. This patch does not mutate either state automatically.

The later V3.9.6B contract implements the explicit first Research Champion
promotion after eligibility; see the linked promotion contract. Automatic
promotion and rollback remain disabled/deferred. `PAPER_CHAMPION` and all
Execution/order authority remain out of scope.
