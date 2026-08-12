# Phase 7.5 — Forward Champion/Challenger Validation

## Goal

Phase 7.5 proves whether a Phase-7 challenger actually makes better forward
trade selections than the current approved champion, initially
`RULE_SYSTEM_V1`.

This phase does **not** grant paper or real trading authority to the challenger.
It strengthens the Observation-side shadow comparison only.

## Trusted evidence contract

Phase 7.5 forward evidence is fail-closed. A completed shadow comparison may be
used only when:

- the decision snapshot belongs to the requested challenger and champion;
- the selected candidates contain `COMPLETE_PHASE7_1` market context;
- the linked `VIRTUAL_TRADE` outcome contains
  `FEES_SLIPPAGE_SPREAD_FUNDING_COMPLETE_PHASE7_3` cost evidence;
- the result can be grouped by `market_event_id`;
- duplicate candidate outcomes are excluded.

The return basis is therefore the Phase-7.3 complete after-cost virtual result,
not the older fees/slippage-only estimate.

## Phase-7 challenger eligibility

Production shadow testing now accepts only challenger records that declare all
of the following:

- a Phase-7 model record;
- complete market context required;
- complete cost evidence required;
- final test policy `SEALED_UNTIL_FINAL_CANDIDATE_SELECTED`;
- model selection did not use test data;
- Phase-7 paper-promotion lock remains active.

If a legacy pre-Phase-7 model already occupies the shadow slot, it is archived
and removed from the active slot. Its registry record/artifact is preserved.
Legacy offline models are not selected for Phase-7 shadow validation.

## Independent-event comparison

Raw candidate outcomes are not treated as independent evidence. Shadow results
are grouped by `market_event_id` before promotion statistics are calculated.

The primary comparison is challenger TOP_ONE versus champion TOP_ONE.
The report continues to keep TOP_K evidence separate.

For paired events the evaluator reports:

- completed raw pairs;
- independent market-event pairs;
- agreement and disagreement events;
- challenger and champion after-cost average R;
- average R lift over champion;
- win rates;
- which side performed better on paired events.

When the challenger and champion disagree, selection-quality comparison uses
those disagreement events as the primary basis. If there are no disagreements,
all paired events are retained as the fallback basis.

## Regime robustness

Phase 7.5 adds pairwise regime comparison for:

- broad market regime;
- volatility regime;
- BTC regime.

The automatic promotion gate uses broad `market_regime` as the primary
robustness dimension. BTC and volatility regime results remain visible as
supporting diagnostics.

Production defaults require:

- at least 20 independent paired events inside a market-regime group before
  that group is considered supported;
- at least 2 supported broad market regimes;
- challenger R lift versus champion must be non-negative in every supported
  market regime;
- challenger absolute after-cost expectancy must be positive in every
  supported market regime.

These gates are in addition to the existing overall forward gates for matched
outcomes, independent events, disagreements, overall R lift, after-cost
expectancy, win-rate deterioration, recent expectancy, Brier score,
calibration gap, PSI, and artifact integrity.

## Decision behavior

The controller remains fail-closed:

- insufficient evidence -> `HOLD`;
- promising evidence but insufficient counts/regime coverage ->
  `EXTEND_SHADOW`;
- sufficient evidence showing a materially weak challenger -> `REJECT`;
- every Phase-7.5 gate passes -> the logical decision would be promotion, but
  Phase 7 converts it to `EXTEND_SHADOW` with
  `PHASE7_PAPER_PROMOTION_LOCKED`.

Therefore Phase 7.5 can prove that a challenger deserves later consideration,
but it cannot make that challenger choose paper trades.

## Authority boundary

Unchanged:

- current champion remains authoritative for the approved recommendation;
- challenger scoring is Observation-only;
- Execution does not run training or promotion logic;
- no real-order authority is created;
- paper routing is unchanged;
- Phase 8 remains the earliest phase where a proven learned selection authority
  can be considered for controlled paper-selection authority.
